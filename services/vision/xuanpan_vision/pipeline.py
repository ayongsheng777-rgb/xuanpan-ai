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

        无论 provider 是本地 CV 还是云端大模型，都做三件事：
        1. **山名以 fortune_core 为准**：非法山名丢弃，山名不得由 provider 自造
        2. **角度必须落在所属山内**（±7.5°）：越界即用山心角覆盖，
           provider 无权把角度挪到别的山去（RULE-002）；山内则保留实测精度
        3. **向山由坐山推导**：坐向是一条直线，向山必然是对宫，没有 provider 说话的余地

        这是 RULE-002 在识别层的落地：识别层没有权力定义"是哪个山、什么角度"。
        """
        from fortune_core.mountain24 import (
            HALF_SPAN,
            angular_distance,
            get_mountain,
            opposite,
        )

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

                # 山名永远是 fortune_core 说了算；角度分两种情形处理：
                #   实测角落在该山范围内（±7.5°）→ **保留**，因为一百二十分金是 3° 级精度，
                #     把实测角粗暴替换成山心角会让分金永远落在正中格，等于丢掉整个分金功能；
                #   实测角与山名矛盾 → 用山心角覆盖。
                # 这样既保住了测量精度，又堵死了 provider「注入任意角度」的通道（RULE-002）：
                # provider 可以让精度更高，但不能让角度跑到另一个山里去。
                if angular_distance(c.angle, canonical) <= HALF_SPAN:
                    angle = c.angle % 360.0
                else:
                    problems.append(
                        f"「{c.name}」的角度被改写为 {c.angle:.2f}°（不在该山范围内，山心 "
                        f"{canonical:.2f}°），已纠正为山心角"
                    )
                    angle = canonical
                out.append(MountainCandidate(c.name, angle, c.confidence, end))  # type: ignore[arg-type]
            return out

        sitting = canonicalize(result.mountain_candidates, "sitting")
        facing = canonicalize(result.direction_candidates, "facing")

        def derive_opposites(src: list[MountainCandidate], end: str) -> list[MountainCandidate]:
            """由一侧候选推导另一侧（互为对宫）。

            为什么是「推导」而不是「校验 provider 给的向山」：
            坐向是一条直线，向山必然是对宫 —— 这件事没有 provider 说话的余地。
            早先的做法是保留 provider 的向山列表再做一致性检查，但 `sitting` 与
            `facing` 是同一组两端的两个平行列表，各自排序后**索引天然对齐成同山**，
            于是"坐向同山"检查被误触发，向山被重推、实测角被替换成山心角。

            推导同时保住了精度：对宫端实测角 = 本端实测角 + 180°，3° 级分金照常可用。
            """
            best: dict[str, MountainCandidate] = {}
            for c in src:
                opp_name = opposite(c.name)
                angle = (c.angle + 180.0) % 360.0
                prev = best.get(opp_name)
                if prev is None or c.confidence > prev.confidence:
                    best[opp_name] = MountainCandidate(opp_name, angle, c.confidence, end)  # type: ignore[arg-type]
            return [best[k] for k in sorted(best, key=lambda n: (-best[n].confidence, n))]

        if sitting:
            derived = derive_opposites(sitting, "facing")
            if facing and {c.name for c in facing} != {c.name for c in derived}:
                problems.append(
                    "provider 给出的向山候选「"
                    + "、".join(sorted(c.name for c in facing))
                    + "」与坐山不构成对宫，已按坐山重推为「"
                    + "、".join(c.name for c in derived)
                    + "」"
                )
            facing = derived
        elif facing:
            problems.append("provider 未给出坐山候选，已按向山候选推导对宫作为坐山")
            sitting = derive_opposites(facing, "sitting")
        else:
            # 声称识别成功却没有任何候选 —— 如实降级，不编造
            problems.append("provider 声称识别成功但未给出任何坐向候选，已按未识别处理")

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
