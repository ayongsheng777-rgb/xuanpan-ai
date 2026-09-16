"""VisionProvider 抽象 —— 按**能力**而非品牌划分（产品方案 §28）。

为什么坚持抽象：Vision 是本项目最大成本项。抽象层让「本地经典 CV」与
「云端视觉大模型」可以互换，从而做到：
- 无 key 时用本地实现跑通全链路（成本 0）
- 有 key 时按图片难度择优选路（成本受控）
- 换供应商不改业务代码

**所有 provider 都必须遵守 RULE-003**：无法确认时返回 `null` / 空候选，绝不猜。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from PIL import Image

from ..models import CompassVisionResult, QualityReport


@dataclass(frozen=True, slots=True)
class PreparedCompass:
    """预处理后的罗盘图像包 —— provider 的统一输入。

    圆心与半径均为**校正图坐标系**下的值。
    """

    original: Image.Image
    rectified: Image.Image
    center: tuple[float, float]
    radius: float
    quality: QualityReport
    tilt_deg: float | None = None
    rectified_side: int = 0

    def to_context(self) -> dict[str, Any]:
        """给云端 provider 的文本上下文（不含图像本身）。"""
        return {
            "rectified_side": self.rectified_side,
            "center": [round(self.center[0], 2), round(self.center[1], 2)],
            "radius": round(self.radius, 2),
            "tilt_deg": round(self.tilt_deg, 2) if self.tilt_deg is not None else None,
            "quality": self.quality.to_dict(),
        }


@runtime_checkable
class VisionProvider(Protocol):
    """视觉识别 provider 协议。"""

    name: str
    capability: str          # local / cloud / manual
    requires_api_key: bool

    def analyze(self, prepared: PreparedCompass) -> CompassVisionResult:
        """读取罗盘 → 结构化候选。**不确定必须返回空候选或低置信度。**"""
        ...

    def is_available(self) -> bool:
        """运行环境是否满足（例如云端 provider 需要 API key）。"""
        ...


class ProviderUnavailableError(RuntimeError):
    """provider 在当前环境不可用（缺少依赖、缺 key 等）。"""


__all__ = [
    "PreparedCompass", "VisionProvider", "ProviderUnavailableError",
]
