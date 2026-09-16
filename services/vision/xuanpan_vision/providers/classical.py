"""本地经典 CV provider —— 零成本、离线可用、结果可复现。

能力边界（**必须诚实声明，这决定了 UI 如何提示**）：
✅ 检测罗盘盘体、圆心、半径、透视倾角
✅ 测量鱼丝线（贯通直径的线）的角度 → 映射为二十四山候选
✅ 测量天池磁针方向，判断是否已「对针」
✅ 检测磁针红头端（仅作提示，**不用于判定坐/向**）
❌ **不读印刷文字** —— 无法知道盘面标注的字，也无法确定鱼丝线哪一端为坐山

因此它输出的是**两个对宫候选 + 必须用户确认**。这是当前硬件条件下的
最优解，而不是缺陷：产品方案 §20 的「识别确认页」本来就是这个环节的设计。

若需要"直接读出盘面文字"，用 `openai_compat` provider（需自备 key）。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..models import CompassVisionResult, MountainCandidate
from ..ring import (
    LineMeasure,
    detect_diameter_line,
    detect_needle,
    polar_unwrap,
)
from ..quality import to_gray_array
from .base import PreparedCompass

#：鱼丝线判定的最小显著度（灰度级）
MIN_LINE_PROMINENCE = 10.0


def _red_end_angle(prepared: PreparedCompass) -> tuple[float | None, float]:
    """在半径 ~22% 环带上找「最红」的方位 —— 磁针红头。

    Returns: (角度, 置信度)。找不到返回 (None, 0.0)。
    **该结果只作为提示，不参与坐/向判定**，因为红头指南还是指北因罗盘而异。
    """
    rgb = np.asarray(prepared.rectified.convert("RGB"), dtype=np.float64)
    cx, cy = prepared.center
    r = prepared.radius * 0.22
    n = 720
    angles = np.arange(n, dtype=np.float64) * (360.0 / n)
    t = np.radians(angles)
    xs = np.clip((cx + r * np.sin(t)).astype(np.int64), 0, rgb.shape[1] - 1)
    ys = np.clip((cy - r * np.cos(t)).astype(np.int64), 0, rgb.shape[0] - 1)

    px = rgb[ys, xs]
    redness = px[:, 0] - 0.5 * (px[:, 1] + px[:, 2])

    half = n // 2
    folded = redness[:half] + redness[half:]
    idx = int(np.argmax(folded))
    score = float(folded[idx])
    base = float(np.median(folded))
    prominence = score - base
    if prominence < 20.0:
        return None, 0.0
    return float(idx * (360.0 / n)), float(np.clip(prominence / 120.0, 0.0, 1.0))


class ClassicalVisionProvider:
    """基于几何与极坐标采样的本地识别实现。"""

    name = "classical"
    capability = "local"
    requires_api_key = False

    def __init__(self, *, min_prominence: float = MIN_LINE_PROMINENCE) -> None:
        self.min_prominence = min_prominence

    def is_available(self) -> bool:
        return True

    def analyze(self, prepared: PreparedCompass) -> CompassVisionResult:
        from fortune_core.mountain24 import mountain_at

        gray = to_gray_array(prepared.rectified)
        profile, _ = polar_unwrap(gray, prepared.center, prepared.radius)

        line: LineMeasure = detect_diameter_line(profile, min_prominence=self.min_prominence)
        needle = detect_needle(gray, prepared.center, prepared.radius)
        red_angle, red_conf = _red_end_angle(prepared)

        warnings: list[str] = []
        uncertain: list[str] = []

        # ---- 鱼丝线未找到 → RULE-003：返回空候选，不猜 ----
        if line.confidence <= 0.0:
            return CompassVisionResult.rejected(
                "未能定位鱼丝线（贯通盘面的细线），可能是反光遮挡、线太细或未完整入镜",
                provider=self.name,
                quality=prepared.quality,
                warnings=("可尝试：靠近拍摄使盘面占满画面、避开直射光、保证鱼丝线可见",),
            )

        if needle.angle is None:
            warnings.append("未能定位天池磁针，无法判断罗盘是否已对针")
        elif not needle.aligned:
            warnings.append(
                f"磁针偏离正北 {needle.deviation_deg:.1f}°，罗盘可能未对针；"
                "若未对针，坐向会整体偏移"
            )

        # ---- 两个对宫端都可能为坐山（几何上无法区分）----
        confidence = line.confidence * (0.85 if needle.aligned else 0.7)
        confidence = round(min(confidence, 0.95), 4)

        sitting: list[MountainCandidate] = []
        facing: list[MountainCandidate] = []
        for end in line.ends:
            m_sit = mountain_at(end)
            m_face = mountain_at(end + 180.0)
            if m_sit.name == m_face.name:  # pragma: no cover - 几何上不可能
                continue
            sitting.append(MountainCandidate(m_sit.name, end % 360.0, confidence, "sitting"))
            facing.append(MountainCandidate(m_face.name, (end + 180.0) % 360.0, confidence, "facing"))

        # 按置信度降序，UI 直接取第一个作为「默认建议」
        sitting.sort(key=lambda c: c.name)
        facing.sort(key=lambda c: c.name)

        uncertain.append("几何上无法判断鱼丝线哪一端为坐山，请用户在确认页选择")

        if red_angle is not None:
            warnings.append(
                f"检测到磁针红头位于 {red_angle:.1f}°（置信度 {red_conf:.2f}）；"
                "红头指南或指北因罗盘形制而异，仅作参考"
            )

        return CompassVisionResult(
            compass_detected=True,
            center=prepared.center,
            radius=prepared.radius,
            rotation_deg=None,
            mountain_candidates=tuple(sitting),
            direction_candidates=tuple(facing),
            printed_text=(),
            uncertain_regions=tuple(uncertain),
            needs_user_confirmation=True,
            provider=self.name,
            quality=prepared.quality,
            warnings=tuple(warnings),
        )

    def debug_dump(self, prepared: PreparedCompass) -> dict[str, Any]:
        """调试信息（供 /vision/debug 端点使用，便于现场排查）。"""
        gray = to_gray_array(prepared.rectified)
        profile, ratios = polar_unwrap(gray, prepared.center, prepared.radius)
        line = detect_diameter_line(profile, min_prominence=self.min_prominence)
        needle = detect_needle(gray, prepared.center, prepared.radius)
        return {
            "radii_ratios": [round(float(r), 3) for r in ratios],
            "line": line.to_dict(),
            "needle": needle.to_dict(),
            "valid_samples": int(np.count_nonzero(np.isfinite(profile))),
            "total_samples": int(profile.size),
        }


__all__ = ["ClassicalVisionProvider", "MIN_LINE_PROMINENCE"]
