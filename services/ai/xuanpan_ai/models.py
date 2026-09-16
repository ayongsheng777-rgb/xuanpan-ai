"""AI 解释层的数据契约。

**三层物理分离**是本模块的核心约束（基线规范 §3）：

    FACTS            确定性计算结果        —— 只读，AI 不可修改
    TRADITION        流派规则派生描述      —— 只读
    AI_INTERPRETATION LLM 生成的解读       —— 唯一由模型产出的层

它们在这份数据结构里是**三个独立字段**，不是同一个字段里的三段文字。
"防止 AI 幻觉污染盘面事实"靠的就是这个物理隔离：模型无论输出什么，
都不可能写到 `facts` 里去 —— 它连写入的位置都没有。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

#：固定免责声明（基线规范 §3 硬性要求 3，逐字不得改写）
DISCLAIMER = "以上内容属于传统文化娱乐/学习参考"

#：AI 解读标签内的固定子区块与顺序（材料 A 的四段并入此处）
REQUIRED_SECTIONS: tuple[str, ...] = ("事实", "传统解释", "针对问题", "参考建议")

Layer = Literal["FACT", "TRADITION", "AI_INTERPRETATION"]
Role = Literal["user", "assistant"]


# ==========================================================================
# 调用层
# ==========================================================================


@dataclass(frozen=True, slots=True)
class Turn:
    """多轮对话中的一轮。"""

    role: Role
    content: str


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """交给 provider 的请求。

    `payload` 就是 `FortuneContext.to_ai_payload()` 的返回值 ——
    **provider 唯一的业务输入**。它不包含原始照片、不包含未加工的生辰文本。
    """

    session_id: str
    payload: dict[str, Any]
    system_prompt: str
    user_message: str
    history: tuple[Turn, ...] = ()
    max_tokens: int = 2048
    temperature: float = 0.7


@dataclass(frozen=True, slots=True)
class Attempt:
    """一次 provider 尝试的轨迹 —— 对应 §21「已自动切换备用模型」的 UX。"""

    provider: str
    model: str
    ok: bool
    detail: str
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "ok": self.ok,
            "detail": self.detail,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """provider 的返回。"""

    text: str
    provider: str
    model: str
    attempts: tuple[Attempt, ...] = ()
    usage: TokenUsage | None = None
    degraded: bool = False
    warnings: tuple[str, ...] = ()


# ==========================================================================
# 报告层（三层分离的落点）
# ==========================================================================


@dataclass(frozen=True, slots=True)
class ReportSection:
    """AI 解读内的一个子区块。"""

    title: str
    body: str

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "body": self.body}


@dataclass(frozen=True, slots=True)
class Interpretation:
    """AI 解读层（`AI_INTERPRETATION`）—— 唯一由模型生成的层。"""

    sections: tuple[ReportSection, ...]
    raw_text: str
    provider: str
    model: str
    degraded: bool = False
    attempts: tuple[Attempt, ...] = ()
    usage: TokenUsage | None = None
    warnings: tuple[str, ...] = ()

    @property
    def text(self) -> str:
        """把子区块拼回整段文本（供复制/分享）。"""
        return "\n\n".join(f"【{s.title}】\n{s.body}" for s in self.sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "raw_text": self.raw_text,
            "provider": self.provider,
            "model": self.model,
            "degraded": self.degraded,
            "attempts": [a.to_dict() for a in self.attempts],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            } if self.usage else None,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class Report:
    """一次占测会话的完整报告 —— 三层字段**物理分离**。"""

    session_id: str
    facts: dict[str, Any]                 # FACT        只读
    tradition: dict[str, Any]             # TRADITION   只读
    interpretation: Interpretation        # AI_INTERPRETATION
    uncertainties: tuple[str, ...]
    question: dict[str, Any] | None = None
    calculation: dict[str, Any] = field(default_factory=dict)
    disclaimer: str = DISCLAIMER
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict[str, Any]:
        """序列化形态 —— 三层的键名刻意不同，避免任何"合并"的可能。"""
        return {
            "session_id": self.session_id,
            "facts": self.facts,
            "tradition": self.tradition,
            "interpretation": self.interpretation.to_dict(),
            "uncertainties": list(self.uncertainties),
            "question": self.question,
            "calculation": self.calculation,
            "disclaimer": self.disclaimer,
            "generated_at": self.generated_at,
        }


__all__ = [
    "DISCLAIMER", "REQUIRED_SECTIONS", "Layer", "Role",
    "Turn", "TokenUsage", "LLMRequest", "Attempt", "LLMResponse",
    "ReportSection", "Interpretation", "Report",
]
