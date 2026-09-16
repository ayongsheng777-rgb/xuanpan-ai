"""手动选择 provider —— RULE-004 的兜底实现。

当自动识别置信度不足、或用户就是要精确指定坐向时，
必须有一条"完全由用户决定"的路径。这条路径**不经过任何模型**，
直接调用 fortune_core 做几何校验。

UI 上的形态是「二十四山环形选择器」（基线规范 §4.3），禁止让用户输入角度数值。
"""

from __future__ import annotations

from ..models import CompassVisionResult, MountainCandidate
from .base import PreparedCompass


class ManualVisionProvider:
    """由用户直接给出坐山（或向山）。"""

    name = "manual"
    capability = "manual"
    requires_api_key = False
    #：与注册表 id 一致 —— 管线据此认定「输出即用户输入」，不必再要求确认
    registry_id = "manual"

    def __init__(self, *, sitting: str | None = None, facing: str | None = None,
                 confidence: float = 1.0) -> None:
        self.sitting = sitting
        self.facing = facing
        self.confidence = confidence

    def is_available(self) -> bool:
        return True

    def analyze(self, prepared: PreparedCompass) -> CompassVisionResult:
        from fortune_core.exceptions import FortuneError
        from fortune_core.compass import calculate_orientation

        if not self.sitting and not self.facing:
            return CompassVisionResult.rejected(
                "手动模式需要用户指定坐山或向山",
                provider=self.name,
                quality=prepared.quality,
            )

        try:
            ori = calculate_orientation(
                sitting=self.sitting,
                facing=self.facing,
                confidence=self.confidence,
                confirmed_by_user=True,
                source="manual",
            )
        except FortuneError as exc:
            # 用户给的值不合法时，如实报错，不替用户"修正"（RULE-008）
            return CompassVisionResult.rejected(
                f"所选坐向不成立：{exc}",
                provider=self.name,
                quality=prepared.quality,
            )

        return CompassVisionResult(
            compass_detected=True,
            center=prepared.center,
            radius=prepared.radius,
            mountain_candidates=(
                MountainCandidate(ori.sitting.name, ori.sitting.center_degree, self.confidence, "sitting"),
            ),
            direction_candidates=(
                MountainCandidate(ori.facing.name, ori.facing.center_degree, self.confidence, "facing"),
            ),
            uncertain_regions=(),
            needs_user_confirmation=False,
            provider=self.name,
            quality=prepared.quality,
            warnings=tuple(ori.warnings),
        )


__all__ = ["ManualVisionProvider"]
