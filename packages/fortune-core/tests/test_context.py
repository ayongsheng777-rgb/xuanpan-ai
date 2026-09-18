"""FortuneContext 测试 —— 主要验证 **AI 边界**（RULE-002）。

这些用例守护的是项目的核心安全机制：
**LLM 只能拿到已算好的结构化数据，且没有任何修改计算值的入口。**
"""

from __future__ import annotations

import json

import pytest

from fortune_core.bazi import BirthInput, calculate_bazi
from fortune_core.compass import calculate_orientation
from fortune_core.context import (
    QUESTION_CATEGORIES,
    SENSITIVE_CATEGORIES,
    CalculationContext,
    FortuneContext,
    QuestionContext,
    build_context,
)
from fortune_core.liuyao import cast_liuyao
from fortune_core.naming import analyze_name
from fortune_core.qian import draw_qian
from fortune_core.schools import DEFAULT_SCHOOL, get_school, list_schools
from fortune_core.exceptions import SchoolNotFoundError


@pytest.fixture()
def full_context() -> FortuneContext:
    return build_context(
        session_id="test-session-001",
        compass=calculate_orientation(
            sitting="午", facing="子", degree=180.0, confidence=0.92, confirmed_by_user=True
        ),
        bazi=calculate_bazi(BirthInput(1981, 9, 14, 8, 0, gender="male")),
        liuyao=cast_liuyao(yao_values=[9, 7, 7, 7, 7, 7]),
        qian=draw_qian(2),
        name_analysis=analyze_name("王明"),
        question=QuestionContext(category="事业", text="最近事业是否适合调整方向？"),
    )


class TestQuestionContext:
    def test_valid_category(self) -> None:
        for c in QUESTION_CATEGORIES:
            QuestionContext(category=c, text="x").validate()

    def test_invalid_category(self) -> None:
        with pytest.raises(ValueError):
            QuestionContext(category="彩票", text="x").validate()

    def test_sensitive_categories_have_disclaimer(self) -> None:
        assert "健康" in SENSITIVE_CATEGORIES
        assert "财运" in SENSITIVE_CATEGORIES
        assert "医疗" in SENSITIVE_CATEGORIES["健康"]


class TestLayersSeparation:
    #：解读性字段名 —— 出现在 FACT 层即为污染
    INTERPRETATION_KEYS = frozenset({
        "summary", "suggestions", "advice", "interpretation",
        "note", "uncertainties", "verdict", "text",
    })

    def test_facts_never_contain_interpretation(self, full_context: FortuneContext) -> None:
        """★ 核心不变量：FACT 层不得出现任何解读性字段（RULE-002 的结构保障）。"""
        for section, payload in full_context.to_facts().items():
            overlap = set(payload) & self.INTERPRETATION_KEYS
            assert overlap == set(), f"{section} 的 FACT 层混入解读字段：{overlap}"

    def test_tradition_carries_uncertainty(self, full_context: FortuneContext) -> None:
        """TRADITION 层应携带不确定性标注，供 UI 与 AI 引用。"""
        tradition = full_context.to_tradition()
        assert any("uncertainties" in v for v in tradition.values())
        assert any("note" in v for v in tradition.values())

    def test_top_level_sections_aligned(self, full_context: FortuneContext) -> None:
        """两层应就同一批模块给出各自的视图，不得缺项。"""
        assert set(full_context.to_facts()) == set(full_context.to_tradition())
        assert set(full_context.to_facts()) == {"compass", "bazi", "liuyao", "qian", "name"}

    def test_sections_that_must_be_disjoint(self, full_context: FortuneContext) -> None:
        """无同名概念的模块，两层字段须完全不相交。"""
        for key in ("bazi", "liuyao", "name"):
            facts, tradition = full_context.to_facts()[key], full_context.to_tradition()[key]
            assert set(facts) & set(tradition) == set(), f"{key} 层间字段重叠"

    def test_facts_have_no_free_text_conclusions(self, full_context: FortuneContext) -> None:
        """整层序列化后也不得出现断语式字段名。"""
        raw = json.dumps(full_context.to_facts(), ensure_ascii=False)
        for forbidden in ("suggestions", "summary", "advice", "interpretation"):
            assert forbidden not in raw, f"FACT 层混入了 {forbidden}"

    def test_context_has_all_sections(self, full_context: FortuneContext) -> None:
        assert full_context.has_any_calculation
        assert full_context.compass is not None
        assert full_context.bazi is not None
        assert full_context.question is not None


class TestUncertainties:
    def test_aggregates_from_all_sources(self, full_context: FortuneContext) -> None:
        u = full_context.uncertainties()
        assert u, "必须汇总出不确定性"
        assert any("分金" in x for x in u)
        assert any("阈值" in x for x in u)
        assert any("演示" in x for x in u)

    def test_deduplicated(self, full_context: FortuneContext) -> None:
        u = full_context.uncertainties()
        assert len(u) == len(set(u)), "不确定性条目不应重复"

    def test_unconfirmed_compass_flagged(self) -> None:
        ctx = build_context(
            "s2",
            compass=calculate_orientation(sitting="午", facing="子"),
        )
        assert any("未经用户确认" in x for x in ctx.uncertainties())

    def test_sensitive_question_adds_disclaimer(self) -> None:
        ctx = build_context("s3", question=QuestionContext(category="财运", text="该投资吗"))
        u = ctx.uncertainties()
        assert any("投资建议" in x for x in u)

    def test_neutral_question_no_disclaimer(self) -> None:
        ctx = build_context("s4", question=QuestionContext(category="事业", text="x"))
        assert not any("投资建议" in x for x in ctx.uncertainties())


class TestAiPayload:
    def test_contains_required_parts(self, full_context: FortuneContext) -> None:
        p = full_context.to_ai_payload()
        for key in ("session_id", "facts", "tradition", "question",
                    "calculation", "uncertainties", "constraints"):
            assert key in p

    def test_facts_marked_immutable(self, full_context: FortuneContext) -> None:
        c = full_context.to_ai_payload()["constraints"]
        assert "facts" in c["immutable"]
        assert "tradition" in c["immutable"]

    def test_forbidden_list_covers_core_rules(self, full_context: FortuneContext) -> None:
        forbidden = " ".join(full_context.to_ai_payload()["constraints"]["forbidden"])
        assert "修改" in forbidden          # RULE-002
        assert "八字" in forbidden
        assert "角度" in forbidden
        assert "医疗" in forbidden or "投资" in forbidden  # RULE-010

    def test_required_disclaimer_present(self, full_context: FortuneContext) -> None:
        c = full_context.to_ai_payload()["constraints"]
        assert "传统文化娱乐" in c["required_disclaimer"]

    def test_no_raw_photo_or_input_leaks(self, full_context: FortuneContext) -> None:
        """AI 载荷中不得出现原始图像、原始文件路径或未加工的输入。"""
        raw = json.dumps(full_context.to_ai_payload(), ensure_ascii=False)
        for forbidden in ("base64", "imageUrl", "image_url", ".png", ".jpg", "data:image"):
            assert forbidden not in raw, f"AI 载荷泄漏了原始输入：{forbidden}"

    def test_day_master_pinned_in_constraints(self, full_context: FortuneContext) -> None:
        """日主与喜用五行写入 constraints，供上层校验 AI 输出是否与计算一致（RULE-002）。"""
        c = full_context.to_ai_payload()["constraints"]
        chart = full_context.bazi
        assert chart is not None
        assert c["day_master"] == chart.day_master == "乙"
        # 喜用必须原样来自计算层，AI 不得自行改判
        from fortune_core.constants import ELEMENT_CN

        assert c["favorable_elements"] == [ELEMENT_CN[e] for e in chart.strength.favorable]
        assert c["favorable_elements"], "喜用五行不应为空"

    def test_payload_is_json_serializable(self, full_context: FortuneContext) -> None:
        """★ 集成属性：整个载荷必须能过 JSON —— 否则 API 层会直接崩。"""
        text = json.dumps(full_context.to_ai_payload(), ensure_ascii=False)
        assert "辛酉" in text
        assert json.loads(text)["session_id"] == "test-session-001"

    def test_to_dict_serializable(self, full_context: FortuneContext) -> None:
        text = json.dumps(full_context.to_dict(), ensure_ascii=False)
        assert "坐午向子" in text


class TestCalculationContext:
    def test_school_metadata(self, full_context: FortuneContext) -> None:
        c = full_context.calculation
        assert c.school == DEFAULT_SCHOOL
        assert c.school_name == get_school().name
        assert c.engine == "fortune-core"
        # 只锁**类型**不锁值：本用例的主题是 school 元数据，而这一位的值
        # 取决于分金规则表在不在 —— 那件事由 test_fenjin120.py 显式构造输入来测。
        # 写成 `is False` 会把它变成"锁现状"：真把表补上时，本用例会第一个报回归。
        assert isinstance(c.fenjin_table_available, bool)

    def test_missing_degree_warns(self) -> None:
        ctx = build_context("s5", compass=calculate_orientation(sitting="午", facing="子"))
        assert any("精确角度" in w for w in ctx.calculation.warnings)


class TestSchools:
    def test_default_school(self) -> None:
        p = get_school()
        assert p.id == "default"
        assert p.bazi_late_zi_sect == 2
        assert p.unverified

    def test_unknown_school_raises(self) -> None:
        with pytest.raises(SchoolNotFoundError):
            get_school("flying_spaghetti")

    def test_only_default_available(self) -> None:
        available = [s for s in list_schools() if s["available"]]
        assert len(available) == 1
        assert available[0]["id"] == "default"

    def test_reserved_schools_declare_unverified(self) -> None:
        for s in list_schools():
            if not s["available"]:
                assert s["unverified"], f"{s['id']} 未声明不可用原因"


class TestEmptyContext:
    def test_empty_is_valid(self) -> None:
        ctx = build_context("empty")
        assert not ctx.has_any_calculation
        assert ctx.to_facts() == {}
        assert ctx.to_tradition() == {}
        assert isinstance(ctx.to_ai_payload(), dict)

    def test_empty_uncertainties_only_school_notes(self) -> None:
        ctx = build_context("empty")
        assert all("规则" in u or "流派" in u or "做法" in u for u in ctx.uncertainties())
