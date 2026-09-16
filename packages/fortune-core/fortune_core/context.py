"""FortuneContext —— AI 层的**唯一输入契约**（材料 §14）。

核心约束：**AI 不直接接收原始用户输入**。
- 不接收原始照片（只有识别出的结构化数据）
- 不接收未加工的生辰文本（只有排盘结果）
- 不接收自由文本结论（只有 `question.text`，且与计算结果分离）

这样设计的目的是让幻觉无处附着（RULE-002）：
LLM 拿到的是**已经算好的结构化事实**，它只能解释、归纳、组织语言，
**没有任何可修改计算值的入口**。

分层输出：
    to_facts()      → FACT            确定性计算结果，只读
    to_tradition()  → TRADITION       传统规则派生描述，只读
    to_ai_payload() → 交给 LLM 的完整载荷（含明确禁令与不确定性清单）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from .bazi.chart import BaziChart
from .bazi.wuxing import ELEMENTS
from .compass import CompassOrientation
from .liuyao import LiuYaoResult
from .naming import NameAnalysis
from .qian import QianResult
from .schools import DEFAULT_SCHOOL, get_school

QuestionCategory = Literal["事业", "婚姻", "健康", "财运", "学业", "人际", "出行", "其他"]

QUESTION_CATEGORIES: tuple[str, ...] = (
    "事业", "婚姻", "健康", "财运", "学业", "人际", "出行", "其他",
)

#：必须触发额外免责声明的敏感类别（对应 RULE-010）
SENSITIVE_CATEGORIES: dict[str, str] = {
    "健康": "涉及健康的问题不构成医疗建议，请以执业医师意见为准",
    "财运": "涉及投资的问题不构成投资建议，请自行判断风险",
}


@dataclass(frozen=True, slots=True)
class QuestionContext:
    """用户所问事由。与计算结果**物理分离**存储。"""

    category: str = "其他"
    text: str = ""
    asked_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def validate(self) -> None:
        if self.category not in QUESTION_CATEGORIES:
            raise ValueError(
                f"问题类别须为 {QUESTION_CATEGORIES} 之一，收到 {self.category!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"category": self.category, "text": self.text, "asked_at": self.asked_at}


@dataclass(frozen=True, slots=True)
class CalculationContext:
    """计算层元信息 —— 让结果**可追溯**（材料 §46 第三原则）。"""

    engine: str = "fortune-core"
    engine_version: str = "0.1.0"
    school: str = DEFAULT_SCHOOL
    school_name: str = ""
    fenjin_table_available: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "school": self.school,
            "school_name": self.school_name,
            "fenjin_table_available": self.fenjin_table_available,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class FortuneContext:
    """一次占测会话的完整结构化上下文。"""

    session_id: str
    compass: CompassOrientation | None = None
    bazi: BaziChart | None = None
    liuyao: LiuYaoResult | None = None
    qian: QianResult | None = None
    name_analysis: NameAnalysis | None = None
    question: QuestionContext | None = None
    calculation: CalculationContext = field(default_factory=CalculationContext)

    # ---------------- 聚合 ----------------

    def uncertainties(self) -> list[str]:
        """汇总所有不确定性来源 —— 供 AI 层原样引用，不得省略。"""
        out: list[str] = []
        if self.compass:
            out.extend(self.compass.warnings)
            if not self.compass.confirmed_by_user:
                out.append("罗盘识别结果尚未经用户确认")
        if self.bazi:
            out.extend(self.bazi.resolved.warnings)
            out.extend(self.bazi.strength.uncertainties)
        if self.qian and self.qian.demo:
            out.append("灵签使用演示签库，非传世签文")
        if self.name_analysis:
            out.extend(self.name_analysis.uncertainties)
        out.extend(self.calculation.warnings)

        school = get_school(self.calculation.school)
        out.extend(school.unverified)

        if self.question:
            extra = SENSITIVE_CATEGORIES.get(self.question.category)
            if extra:
                out.append(extra)

        # 去重保序
        seen: set[str] = set()
        return [x for x in out if x and not (x in seen or seen.add(x))]

    @property
    def has_any_calculation(self) -> bool:
        return any((self.compass, self.bazi, self.liuyao, self.qian, self.name_analysis))

    # ---------------- 三层输出 ----------------

    def to_facts(self) -> dict[str, Any]:
        """FACT：确定性计算结果，**AI 不可修改**。"""
        facts: dict[str, Any] = {}
        if self.compass:
            facts["compass"] = self.compass.to_facts()
        if self.bazi:
            facts["bazi"] = self.bazi.to_facts()
        if self.liuyao:
            facts["liuyao"] = self.liuyao.to_facts()
        if self.qian:
            facts["qian"] = self.qian.to_facts()
        if self.name_analysis:
            facts["name"] = self.name_analysis.to_facts()
        return facts

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION：传统规则派生描述，**AI 不可修改**。"""
        trad: dict[str, Any] = {}
        if self.compass:
            trad["compass"] = self.compass.to_tradition()
        if self.bazi:
            trad["bazi"] = self.bazi.to_tradition()
        if self.liuyao:
            trad["liuyao"] = self.liuyao.to_tradition()
        if self.qian:
            trad["qian"] = self.qian.to_tradition()
        if self.name_analysis:
            trad["name"] = self.name_analysis.to_tradition()
        return trad

    def to_ai_payload(self) -> dict[str, Any]:
        """交给 LLM 的完整载荷。

        显式包含：
        - `facts` / `tradition`：**只读**，附 `immutable` 标记
        - `uncertainties`：必须原样体现在报告中
        - `constraints`：对 AI 的硬性禁令，防止越界
        """
        from .bazi.wuxing import ELEMENT_CN

        payload: dict[str, Any] = {
            "session_id": self.session_id,
            "facts": self.to_facts(),
            "tradition": self.to_tradition(),
            "question": self.question.to_dict() if self.question else None,
            "calculation": self.calculation.to_dict(),
            "uncertainties": self.uncertainties(),
            "constraints": {
                "immutable": ["facts", "tradition"],
                "forbidden": [
                    "修改、重算、覆盖 facts 中的任何数值",
                    "自行排八字、自行推算角度或坐山",
                    "把 uncertainties 中的歧义表述为确定结论",
                    "把传统术数表述包装成科学事实",
                    "对医疗/投资/法律问题给出确定性结论",
                ],
                "required_disclaimer": "以上内容属于传统文化娱乐/学习参考",
                "required_sections": ["事实", "传统解释", "针对问题", "参考建议"],
            },
        }
        if self.bazi:
            payload["constraints"]["day_master"] = self.bazi.day_master
            payload["constraints"]["favorable_elements"] = [
                ELEMENT_CN[e] for e in self.bazi.strength.favorable
            ]
        return payload

    def to_dict(self) -> dict[str, Any]:
        """持久化形态：三层全量 + 汇总。"""
        return {
            "session_id": self.session_id,
            "facts": self.to_facts(),
            "tradition": self.to_tradition(),
            "question": self.question.to_dict() if self.question else None,
            "calculation": self.calculation.to_dict(),
            "uncertainties": self.uncertainties(),
        }


def build_context(
    session_id: str,
    *,
    compass: CompassOrientation | None = None,
    bazi: BaziChart | None = None,
    liuyao: LiuYaoResult | None = None,
    qian: QianResult | None = None,
    name_analysis: NameAnalysis | None = None,
    question: QuestionContext | None = None,
    school: str = DEFAULT_SCHOOL,
) -> FortuneContext:
    """组装 FortuneContext。

    会自动带上流派元信息与规则表就绪状态，让下游能判断"哪些结论是可用的"。
    """
    from .fenjin120 import table_available

    profile = get_school(school)
    warnings: list[str] = []
    if compass is not None and compass.exact_degree is None:
        warnings.append("未提供精确角度，分金仅可给出几何格位")

    calc = CalculationContext(
        school=profile.id,
        school_name=profile.name,
        fenjin_table_available=table_available(profile.fenjin_table),
        warnings=tuple(warnings),
    )
    return FortuneContext(
        session_id=session_id,
        compass=compass,
        bazi=bazi,
        liuyao=liuyao,
        qian=qian,
        name_analysis=name_analysis,
        question=question,
        calculation=calc,
    )


__all__ = [
    "QUESTION_CATEGORIES", "SENSITIVE_CATEGORIES",
    "QuestionContext", "CalculationContext", "FortuneContext", "build_context",
    "ELEMENTS",
]
