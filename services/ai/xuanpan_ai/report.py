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
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .models import (
    DISCLAIMER,
    Interpretation,
    Report,
    ReportSection,
    Turn,
)
from .prompt import (
    missing_sections,
    parse_sections,
    required_sections_of,
    unmentioned_uncertainties,
)
from .router import AIRouter, Task

#：系统追加的不确定性区块标题（带标记，UI 可单独样式化）
UNCERTAINTY_SECTION_TITLE = "不确定性说明"


def _fingerprint(data: dict[str, Any]) -> str:
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


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

    # ---- 2. 解析模型输出为固定区块（区块定义以载荷为准）----
    titles = required_sections_of(payload)
    sections = parse_sections(response.text, titles=titles)
    if not sections:
        warnings.append(
            "模型输出未包含任何可辨识的区块标题，已整段保留为「AI 解读」，内容未丢失"
        )
        sections = (ReportSection("AI 解读", response.text.strip()),)
    else:
        missing = missing_sections(sections, titles=titles)
        if missing:
            warnings.append("模型输出缺少区块：" + "、".join(missing))

    # ---- 3. 观测模型是否漏提不确定性（不是防线，防线在第 4 步）----
    uncertainties = tuple(context.uncertainties())
    unmentioned = unmentioned_uncertainties(response.text, uncertainties)
    if unmentioned:
        warnings.append(
            f"模型正文未提及 {len(unmentioned)} 条不确定性，已由系统补入「{UNCERTAINTY_SECTION_TITLE}」"
        )

    # ---- 4. 系统追加不确定性区块（逐字，模型无法省略）----
    if uncertainties:
        body = "\n".join(f"· {u}" for u in uncertainties)
        sections = sections + (
            ReportSection(
                UNCERTAINTY_SECTION_TITLE,
                body + "\n\n（本区块由系统根据计算层结果直接生成，未经模型改写）",
            ),
        )

    # ---- 5. 三层分离：facts/tradition 只从 context 取 ----
    facts = context.to_facts()
    tradition = context.to_tradition()
    _assert_layers_intact(context, facts, tradition)

    interpretation = Interpretation(
        sections=sections,
        raw_text=response.text,
        provider=response.provider,
        model=response.model,
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
