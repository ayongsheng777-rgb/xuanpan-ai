"""报告装配 —— 三层物理分离的最终落点（基线规范 §3）。

    FACTS               ← 直接取自 FortuneContext（计算层），模型无写入通道
    TRADITION           ← 同上
    AI_INTERPRETATION   ← 唯一来自模型的部分

三个字段并排存在，不是同一个字段里的三段文字。这样"AI 幻觉污染盘面事实"
在数据结构上就不可能发生。

**不确定性说明由系统追加，不由模型生成**
基线规范 §3 硬性要求 2 说"AI 解读内必须包含 uncertainties"。这条要求若托付
给模型，就等于让幻觉自己决定要不要披露自己 —— 模型漏写一次，用户就少看到
一条风险提示。所以这里由装配层把计算层给出的不确定性清单**逐字**追加为一个
独立区块，并明确标注是系统添加。模型写不写都不影响这条底线。

**两种文体，各自完整**
AI 解读层含【专业分析】与【白话讲解】两块，各含同一套区块，**各自**带
不确定性区块（只给专业版追加 = 让最需要看到风险的人看不到它）。
装配顺序是先按文体切分、再各自解析：两个文体内部用的是同一套区块标题，
不先切就会混成 8 个区块且顺序错乱（见 `prompt.split_registers`）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .models import (
    DISCLAIMER,
    REGISTER_PLAIN,
    Interpretation,
    Report,
    ReportSection,
    Turn,
)
from .prompt import (
    missing_sections,
    parse_sections,
    required_sections_of,
    split_registers,
    unmentioned_uncertainties,
)
from .router import AIRouter, Task

#：系统追加的不确定性区块标题（带标记，UI 可单独样式化）
UNCERTAINTY_SECTION_TITLE = "不确定性说明"


def _fingerprint(data: dict[str, Any]) -> str:
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _uncertainty_block(uncertainties: tuple[str, ...]) -> ReportSection:
    body = "\n".join(f"· {u}" for u in uncertainties)
    return ReportSection(
        UNCERTAINTY_SECTION_TITLE,
        body + "\n\n（本区块由系统根据计算层结果直接生成，未经模型改写）",
    )


def _parse_register(
    text: str, titles: tuple[str, ...], warnings: list[str], *, label: str
) -> tuple[ReportSection, ...]:
    """把一个文体的文本解析成固定区块。

    解析不出任何标题时**整段保留**并记 warning —— 宁可结构丑，不可内容丢。
    用 `label` 区分两种文体的提示文案：只说"解析失败"没法定位是哪一块坏了。
    """
    stripped = text.strip()
    if not stripped:
        return ()
    sections = parse_sections(stripped, titles=titles)
    if not sections:
        warnings.append(
            f"模型的「{label}」部分未包含任何可辨识的区块标题，已整段保留，内容未丢失"
        )
        return (ReportSection(label, stripped),)
    missing = missing_sections(sections, titles=titles)
    if missing:
        warnings.append(f"「{label}」缺少区块：" + "、".join(missing))
    return sections


def build_report(
    context: Any,
    *,
    router: AIRouter | None = None,
    question: str = "",
    history: Iterable[Turn] = (),
    task: Task = "report",
) -> Report:
    """从 `FortuneContext` 生成完整报告。

    Args:
        context: `fortune_core.context.FortuneContext`
        router: 路由器；默认按环境变量构造
        question: 本次提问（追问时用）；留空则用 context 里记录的问题
    """
    # ---- 1. AI 唯一的输入：结构化载荷（RULE-002）----
    payload = context.to_ai_payload()

    router = router or AIRouter()
    response = router.generate(payload, question=question, history=history, task=task)

    warnings: list[str] = list(response.warnings)

    # ---- 2. 按文体切开（两个文体用的是同一套区块标题，必须先切再解析）----
    titles = required_sections_of(payload)
    expert_text, plain_text = split_registers(response.text)

    sections = _parse_register(expert_text, titles, warnings, label="专业分析")

    if not plain_text.strip():
        # 不报错、不拿专业版顶上：如实记 warning，界面据此显示"本篇没有白话版"
        warnings.append(
            f"模型未给出「{REGISTER_PLAIN}」部分，本篇只有专业分析一种文体"
        )
        plain_sections: tuple[ReportSection, ...] = ()
    else:
        plain_sections = _parse_register(
            plain_text, titles, warnings, label=REGISTER_PLAIN
        )

    # ---- 3. 观测模型是否漏提不确定性（不是防线，防线在第 4 步）----
    uncertainties = tuple(context.uncertainties())
    unmentioned = unmentioned_uncertainties(response.text, uncertainties)
    if unmentioned:
        warnings.append(
            f"模型正文未提及 {len(unmentioned)} 条不确定性，已由系统补入「{UNCERTAINTY_SECTION_TITLE}」"
        )

    # ---- 4. 系统追加不确定性区块（逐字，模型无法省略）----
    #
    # 🔴 **两种文体都要追加**，不能只给专业版。
    # 基线规范 §3 硬性要求 2 说的是"AI 解读内必须包含 uncertainties"。
    # 白话版的读者恰恰是最容易把结论当承诺的人（他看不懂术语、只看结论），
    # 只给专业版追加 = 让最需要看到风险提示的读者看不到它。
    if uncertainties:
        block = _uncertainty_block(uncertainties)
        sections = sections + (block,)
        if plain_sections:
            plain_sections = plain_sections + (block,)

    # ---- 5. 三层分离：facts/tradition 只从 context 取 ----
    facts = context.to_facts()
    tradition = context.to_tradition()
    _assert_layers_intact(context, facts, tradition)

    interpretation = Interpretation(
        sections=sections,
        raw_text=response.text,
        provider=response.provider,
        model=response.model,
        plain_sections=plain_sections,
        degraded=response.degraded,
        attempts=response.attempts,
        usage=response.usage,
        warnings=tuple(warnings),
    )

    return Report(
        session_id=context.session_id,
        facts=facts,
        tradition=tradition,
        interpretation=interpretation,
        uncertainties=uncertainties,
        question=context.question.to_dict() if context.question else None,
        calculation=context.calculation.to_dict(),
        disclaimer=DISCLAIMER,
    )


def _assert_layers_intact(context: Any, facts: dict[str, Any], tradition: dict[str, Any]) -> None:
    """内部不变量：报告里的 facts/tradition 必须与计算层**逐字节一致**。

    现在它是恒真的（因为两处都取自同一个 frozen context），
    存在的意义是钉住未来的重构 —— 一旦有人把 provider 的输出喂进 facts，
    这里会立刻炸掉，而不是安静地产出"看起来正常的假报告"。
    """
    if _fingerprint(facts) != _fingerprint(context.to_facts()):
        raise RuntimeError("内部不变量被破坏：报告的 facts 与计算层结果不一致")
    if _fingerprint(tradition) != _fingerprint(context.to_tradition()):
        raise RuntimeError("内部不变量被破坏：报告的 tradition 与计算层结果不一致")


__all__ = ["build_report", "UNCERTAINTY_SECTION_TITLE"]
