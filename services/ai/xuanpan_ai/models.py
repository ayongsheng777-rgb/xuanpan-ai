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

#：AI 解读标签内的固定子区块与顺序（每个文体各一份）
REQUIRED_SECTIONS: tuple[str, ...] = ("事实", "传统解释", "针对问题", "参考建议")

#: 两种文体的块标题。
#:
#: 为什么要**两种**而不是把术语解释塞进同一段：同一份盘面，懂术数的人要的是
#: 精确术语（好去对照手里的盘与书），不懂的人要的是"这说的是什么"。把两者
#: 揉在一段里，前者嫌啰嗦、后者还是看不懂 —— 这是两种读者的两种需求，
#: 不是一种需求的两个措辞。
#:
#: 先专业后白话的顺序是刻意的：先给术语精确的版本，再给讲人话的版本。
#: 反过来会让读者先建立一个模糊理解，再被术语纠正。
REGISTER_EXPERT = "专业分析"
REGISTER_PLAIN = "白话讲解"
REGISTER_TITLES: tuple[str, ...] = (REGISTER_EXPERT, REGISTER_PLAIN)

#: 文体标识（`Interpretation` 的两个字段用它区分）
Register = Literal["expert", "plain"]

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
    """AI 解读层（`AI_INTERPRETATION`）—— 唯一由模型生成的层。

    含**两种文体**（同一件事、同一批数据的深浅两版）：

        sections        专业分析 —— 用术语，面向能对照盘面/命盘的读者
        plain_sections  白话讲解 —— 不用术语，面向第一次接触的读者

    两者是**并列的两份**，不是"白话是专业的注解"：白话版必须自己讲得完整，
    否则读者只能两版对着看才懂，那就等于没有白话版。
    """

    sections: tuple[ReportSection, ...]
    raw_text: str
    provider: str
    model: str
    #: 白话讲解。模型没给出白话块时为 `()` —— **不填充、不拿专业版冒充**，
    #: 由界面如实显示"本篇没有白话版"，并记 warning 说明原因。
    plain_sections: tuple[ReportSection, ...] = ()
    degraded: bool = False
    attempts: tuple[Attempt, ...] = ()
    usage: TokenUsage | None = None
    warnings: tuple[str, ...] = ()

    @property
    def has_plain(self) -> bool:
        """是否有白话版。界面据此决定显示切换还是显示"没有白话版"的说明。"""
        return bool(self.plain_sections)

    @property
    def text(self) -> str:
        """把**专业分析**的子区块拼回整段文本。

        只拼专业版是刻意的：这段文本会作为 assistant 的对话轮次回灌给模型
        （见 `routers/report.py` 的 `add_turn`），专业版更短、术语更准，
        是更好的上下文。白话版是给**人**看的，不必进模型上下文。
        """
        return "\n\n".join(f"【{s.title}】\n{s.body}" for s in self.sections)

    @property
    def plain_text(self) -> str:
        """白话版的整段文本（无白话版时为空串）。"""
        return "\n\n".join(f"【{s.title}】\n{s.body}" for s in self.plain_sections)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "plain_sections": [s.to_dict() for s in self.plain_sections],
            # 冗余一个布尔：前端据此决定显不显示文体切换。若只给数组，
            # 每个消费方都要自己写 `plain_sections.length > 0` 的判断 ——
            # 而漏写这一处判断的表现是"切换按钮点了没反应"。
            "has_plain": self.has_plain,
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
    "DISCLAIMER", "REQUIRED_SECTIONS", "REGISTER_EXPERT", "REGISTER_PLAIN",
    "REGISTER_TITLES", "Register", "Layer", "Role",
    "Turn", "TokenUsage", "LLMRequest", "Attempt", "LLMResponse",
    "ReportSection", "Interpretation", "Report",
]
