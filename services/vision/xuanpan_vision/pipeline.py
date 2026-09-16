"""识别管线 —— 相机与相册两条入口**共用同一条链路**（基线规范 §4.1）。

   输入（相机 / 相册）
         ↓
   图像质量检测 ──✗──► 明确拒绝 + 可执行的用户提示
         ↓ ✓
   圆心 / 边界检测 ──✗──► 明确拒绝（未完整入镜 / 对比度不足）
         ↓ ✓
   透视校正 → 归一为正圆
         ↓
   Vision Provider（结构化候选）
         ↓
   确定性几何校验（坐向必须互为对宫）—— 用 fortune_core，不听模型的
         ↓
   输出识别结果（含 confidence / needs_user_confirmation）
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError

from .geometry import (
    CircleDetection,
    circle_geometry_ok,
    detect_circle,
    rectify_to_circle,
    rectified_size,
)
from .models import CompassVisionResult
from .providers.base import PreparedCompass, ProviderUnavailableError, VisionProvider
from .quality import DEFAULT_THRESHOLDS, QualityThresholds, check_quality

DEFAULT_PADDING = 1.08
DEFAULT_CAP = 1024
DEFAULT_MIN_RADIUS_RATIO = 0.12


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    """管线参数。集中定义，避免阈值散落在调用处。"""

    quality: QualityThresholds = DEFAULT_THRESHOLDS
    padding: float = DEFAULT_PADDING
    rectify_cap: int = DEFAULT_CAP
    min_radius_ratio: float = DEFAULT_MIN_RADIUS_RATIO    # 半径相对短边的下限
    min_geometry_confidence: float = 0.5


class CompassAnalyzer:
    """罗盘识别管线。线程安全（无可变状态）。"""

    def __init__(
        self,
        provider: VisionProvider | None = None,
        config: PipelineConfig | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.provider = provider or _default_provider()
        if not self.provider.is_available():
            raise ProviderUnavailableError(
                f"provider {self.provider.name!r} 在当前环境不可用（可能需要 API key）"
            )

    # ------------------------------------------------------------------

    @staticmethod
    def load_image(source: Image.Image | bytes | bytearray) -> Image.Image:
        """接受 PIL 图或原始字节。字节解码失败时抛 ValueError（便于上层返回 400）。"""
        if isinstance(source, Image.Image):
            return source.convert("RGB")
        try:
            return Image.open(io.BytesIO(bytes(source))).convert("RGB")
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError(f"无法解析图像数据：{exc}") from exc

    # ------------------------------------------------------------------

    def _reject(self, reason: str, quality=None, warnings: tuple[str, ...] = ()) -> CompassVisionResult:
        return CompassVisionResult.rejected(
            reason, provider=self.provider.name, quality=quality, warnings=warnings,
        )

    def prepare(self, image: Image.Image) -> tuple[PreparedCompass | None, CompassVisionResult | None]:
        """执行质检 + 几何 → 预处理包。返回 `(prepared, rejection)`，二者恰有一个非空。"""
        cfg = self.config
        w, h = image.size

        quality = check_quality(image, thresholds=cfg.quality)
        if not quality.passed:
            blocking = quality.blocking
            reason = "；".join(i.message for i in blocking) or "图像质量不达标"
            return None, self._reject(reason, quality=quality, warnings=("请按提示重拍或重新选择图片",))

        detection: CircleDetection = detect_circle(image)
        min_radius = max(60.0, min(w, h) * cfg.min_radius_ratio)
        ok, reason = circle_geometry_ok(detection, min_radius=min_radius)
        if not ok:
            return None, self._reject(reason or "罗盘几何不满足识别条件", quality=quality)

        if detection.confidence < cfg.min_geometry_confidence:
            return None, self._reject(
                f"盘体定位置信度过低（{detection.confidence:.2f}），"
                "可能是背景与罗盘颜色太接近或盘体被遮挡",
                quality=quality,
                warnings=(detection.reason,) if detection.reason else (),
            )

        rectified = rectify_to_circle(image, detection, padding=cfg.padding, cap=cfg.rectify_cap)
        side, _ = rectified_size(detection, padding=cfg.padding, cap=cfg.rectify_cap)
        radius_rect = side / (2.0 * cfg.padding)

        prepared = PreparedCompass(
            original=image,
            rectified=rectified,
            center=(side / 2.0, side / 2.0),
            radius=radius_rect,
            quality=quality,
            tilt_deg=detection.tilt_deg,
            rectified_side=side,
        )
        return prepared, None

    # ------------------------------------------------------------------

    def analyze(
        self,
        source: Image.Image | bytes | bytearray,
    ) -> tuple[CompassVisionResult, PreparedCompass | None]:
        """完整链路。返回 `(结果, 预处理包)`；被拒绝时预处理包为 None。"""
        image = self.load_image(source)

        prepared, rejection = self.prepare(image)
        if rejection is not None or prepared is None:
            return rejection or self._reject("预处理失败"), None

        result = self.provider.analyze(prepared)
        result = self._cross_validate(result, prepared)
        return result, prepared

    def _cross_validate(
        self, result: CompassVisionResult, prepared: PreparedCompass
    ) -> CompassVisionResult:
        """用 fortune_core 做确定性几何校验 —— **不听 provider 的**。

        无论 provider 是本地 CV 还是云端大模型，都做两件事：
        1. **角度一律以 fortune_core 的规范山心角为准**（防止 provider 注入任意角度）
        2. 坐向必须互为对宫，否则按坐山重推导向山

        这是 RULE-002 在识别层的落地：识别层没有权力定义"角度是多少"。
        """
        from fortune_core.mountain24 import get_mountain, is_opposite, mountain_at

        from .models import MountainCandidate
        from .providers import is_user_authoritative

        if not result.compass_detected:
            return result

        problems: list[str] = []

        def canonicalize(cands: tuple[MountainCandidate, ...], end: str) -> list[MountainCandidate]:
            out: list[MountainCandidate] = []
            for c in cands:
                try:
                    canonical = get_mountain(c.name).center_degree
                except KeyError:
                    problems.append(f"provider 返回了非法山名「{c.name}」，已丢弃")
                    continue
                if abs((c.angle - canonical) % 360.0) > 1e-6:
                    problems.append(
                        f"「{c.name}」的角度被改写为 {c.angle:.2f}°（应为 {canonical:.2f}°），已纠正"
                    )
                out.append(MountainCandidate(c.name, canonical, c.confidence, end))  # type: ignore[arg-type]
            return out

        sitting = canonicalize(result.mountain_candidates, "sitting")
        facing = canonicalize(result.direction_candidates, "facing")

        # 每个坐山候选都应能在向山候选里找到对宫；缺则补
        if sitting:
            have = {c.name for c in facing}
            for s in sitting:
                opp = mountain_at(s.angle + 180.0)
                if opp.name not in have:
                    facing.append(MountainCandidate(opp.name, opp.center_degree, s.confidence, "facing"))
                    problems.append(f"向山候选缺少「{opp.name}」的对宫项，已补全")
                    have.add(opp.name)

        # 主候选不得同山。
        # 注意：**不能**用"坐山集合 ∩ 向山集合"来判定非法 —— 几何识别本就无法
        # 判断鱼丝线哪一端是坐山，所以「坐=[丑,未]、向=[未,丑]」是完全合法的
        # 候选形态；早先按集合相交一刀切会把向山候选项全部清空。
        # 真正非法的只有「主坐山与主向山指向同一山」。
        if sitting and facing and sitting[0].name == facing[0].name:
            opp = mountain_at(sitting[0].angle + 180.0)
            problems.append(
                f"主候选坐、向同为「{sitting[0].name}」，已按坐山重推导向山「{opp.name}」"
            )
            facing = [MountainCandidate(opp.name, opp.center_degree, sitting[0].confidence, "facing")]

        # 主候选必须互为对宫
        if sitting and facing and not is_opposite(sitting[0].name, facing[0].name):
            base = sitting[0]
            opp = mountain_at(base.angle + 180.0)
            problems.append(
                f"主候选坐「{base.name}」与向「{facing[0].name}」不构成对宫，已按坐山重推"
            )
            facing = [MountainCandidate(opp.name, opp.center_degree, base.confidence, "facing")]

        return CompassVisionResult(
            compass_detected=True,
            center=result.center,
            radius=result.radius,
            rotation_deg=result.rotation_deg,
            mountain_candidates=tuple(sitting),
            direction_candidates=tuple(facing),
            printed_text=result.printed_text,
            uncertain_regions=result.uncertain_regions,
            # RULE-004：只有「用户本人输入」的路径才可以免确认，其余一律强制确认
            needs_user_confirmation=not is_user_authoritative(self.provider),
            provider=result.provider,
            quality=result.quality,
            warnings=result.warnings + tuple(problems),
        )


def _default_provider() -> VisionProvider:
    from .providers import get_provider

    return get_provider("classical")


def analyze_compass(
    source: Image.Image | bytes | bytearray,
    *,
    provider: VisionProvider | str | None = None,
    config: PipelineConfig | None = None,
    **provider_kwargs: Any,
) -> tuple[CompassVisionResult, PreparedCompass | None]:
    """一次性调用入口（无状态）。"""
    if isinstance(provider, str):
        from .providers import get_provider

        provider = get_provider(provider, **provider_kwargs)
    return CompassAnalyzer(provider=provider, config=config).analyze(source)


__all__ = [
    "PipelineConfig", "CompassAnalyzer", "analyze_compass",
    "DEFAULT_PADDING", "DEFAULT_CAP", "DEFAULT_MIN_RADIUS_RATIO",
]
