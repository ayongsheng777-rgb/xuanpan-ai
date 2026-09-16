"""视觉识别层的数据契约 —— 与产品方案 §8 的 JSON 结构一一对应。

设计要点：
- 所有"可能不确定"的字段一律允许 `None`（RULE-003）
- 候选列表可以为空，但必须同时给出 `needs_user_confirmation`
- `uncertain_regions` 用自然语言表述"哪里没看清"，供 UI 高亮
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Severity = Literal["ok", "warn", "fail"]


@dataclass(frozen=True, slots=True)
class QualityIssue:
    """一项图像质量问题。`severity == "fail"` 时不得进入识别流程。"""

    code: str            # blur / glare / too_dark / too_bright / too_small / no_compass
    severity: Severity
    message: str         # 面向用户的白话提示
    metric: float | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "metric": self.metric,
            "threshold": self.threshold,
        }


@dataclass(frozen=True, slots=True)
class QualityReport:
    """图像质量检测报告。**相机与相册两条入口都必须过这一关**。"""

    passed: bool
    blur_score: float          # 拉普拉斯方差，越大越清晰
    glare_ratio: float         # 过曝像素占比 0..1
    brightness: float          # 平均亮度 0..255
    width: int
    height: int
    issues: tuple[QualityIssue, ...] = ()

    @property
    def blocking(self) -> tuple[QualityIssue, ...]:
        return tuple(i for i in self.issues if i.severity == "fail")

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "blur_score": round(self.blur_score, 2),
            "glare_ratio": round(self.glare_ratio, 4),
            "brightness": round(self.brightness, 2),
            "size": [self.width, self.height],
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass(frozen=True, slots=True)
class MountainCandidate:
    """一个山的候选。`confidence` 为 0..1。"""

    name: str
    angle: float
    confidence: float
    end: Literal["sitting", "facing", "unknown"] = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "angle": round(self.angle, 2),
            "confidence": round(self.confidence, 4),
            "end": self.end,
        }


@dataclass(frozen=True, slots=True)
class CompassVisionResult:
    """视觉识别结果 —— 全项目的**契约边界**。

    结构对齐材料 §8 的 JSON 输出，字段名保持一致以免二次翻译出错。
    """

    compass_detected: bool
    center: tuple[float, float] | None = None
    radius: float | None = None
    rotation_deg: float | None = None          # 圆盘旋转量（未测出为 None）
    mountain_candidates: tuple[MountainCandidate, ...] = ()   # 坐山候选
    direction_candidates: tuple[MountainCandidate, ...] = ()  # 向山候选
    printed_text: tuple[str, ...] = ()
    uncertain_regions: tuple[str, ...] = ()
    needs_user_confirmation: bool = True
    provider: str = "unknown"
    quality: QualityReport | None = None
    warnings: tuple[str, ...] = ()

    # ---------------- 便捷判断 ----------------

    @property
    def best_sitting(self) -> MountainCandidate | None:
        return max(self.mountain_candidates, key=lambda c: c.confidence, default=None)

    @property
    def best_facing(self) -> MountainCandidate | None:
        return max(self.direction_candidates, key=lambda c: c.confidence, default=None)

    @property
    def confidence(self) -> float:
        """整体置信度取两侧较低者 —— 任一侧不可靠则整体不可靠。"""
        s, f = self.best_sitting, self.best_facing
        if s is None or f is None:
            return 0.0
        return min(s.confidence, f.confidence)

    @property
    def auto_acceptable(self) -> bool:
        """是否达到"可直接进入下一步、但仍需用户确认"的程度。

        注意：**永远不返回"无需确认"**。RULE-004 要求识别结果必须允许用户修正，
        故该属性只表达"是否需要显式提醒用户复核"。
        """
        return self.compass_detected and self.confidence >= 0.75

    def to_dict(self) -> dict[str, Any]:
        return {
            "compass_detected": self.compass_detected,
            "center": {"x": round(self.center[0], 2), "y": round(self.center[1], 2)} if self.center else None,
            "radius": round(self.radius, 2) if self.radius else None,
            "rotation_deg": round(self.rotation_deg, 2) if self.rotation_deg is not None else None,
            "mountain_candidates": [c.to_dict() for c in self.mountain_candidates],
            "direction_candidates": [c.to_dict() for c in self.direction_candidates],
            "printed_text": list(self.printed_text),
            "uncertain_regions": list(self.uncertain_regions),
            "needs_user_confirmation": self.needs_user_confirmation,
            "confidence": round(self.confidence, 4),
            "provider": self.provider,
            "quality": self.quality.to_dict() if self.quality else None,
            "warnings": list(self.warnings),
        }

    @classmethod
    def rejected(cls, reason: str, *, provider: str, quality: QualityReport | None = None,
                 warnings: tuple[str, ...] = ()) -> CompassVisionResult:
        """构造一个"未检测到 / 不可用"的结果。候选一律为空 —— RULE-003。"""
        return cls(
            compass_detected=False,
            uncertain_regions=(reason,),
            needs_user_confirmation=True,
            provider=provider,
            quality=quality,
            warnings=warnings,
        )


__all__ = [
    "Severity", "QualityIssue", "QualityReport",
    "MountainCandidate", "CompassVisionResult",
]
