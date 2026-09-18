"""AI 解释层测试。

重点不在"文本好不好看"，而在**边界是否守得住**：
- AI 拿到的输入是不是只有结构化载荷（RULE-002）
- 三层是否真的物理分离
- provider 篡改计算结果能否被拦下
- 不确定性是否**一定**出现在报告里（不依赖模型自觉）
- 全部模型失败时是否会诚实失败，而不是编造报告
"""

from __future__ import annotations

import pytest

from fortune_core.bazi import BirthInput, calculate_bazi
from fortune_core.compass import calculate_orientation
from fortune_core.context import QuestionContext, build_context
from xuanpan_ai import (
    AIRouter,
    AllProvidersFailedError,
    Attempt,
    DISCLAIMER,
    LLMResponse,
    ProviderCallError,
    ProviderUnavailableError,
    REGISTER_EXPERT,
    REGISTER_PLAIN,
    REGISTER_TITLES,
    REQUIRED_SECTIONS,
    RouterConfig,
    UNCERTAINTY_SECTION_TITLE,
    build_report,
    build_system_prompt,
    build_user_message,
    get_provider,
    list_providers,
    missing_sections,
    parse_sections,
    split_registers,
    unmentioned_uncertainties,
)
from xuanpan_ai.providers import CAPABILITY_MATRIX, list_endpoint_presets
from xuanpan_ai.providers.openai_compat import OpenAICompatProvider, _redact
from xuanpan_ai.providers.template import (
    _CATEGORY_ANGLE,
    _CATEGORY_ANGLE_PLAIN,
    _TERM_GLOSSARY,
)


# ==========================================================================
# 夹具：可编排的假 provider
# ==========================================================================


class ScriptedProvider:
    """按脚本行事 —— 返回固定文本 / 抛指定异常 / 篡改载荷。"""

    registry_id = "scripted"

    def __init__(
        self,
        name: str,
        *,
        capability: str = "reasoning",
        cost_rank: int = 2,
        text: str = "",
        error: Exception | None = None,
        available: bool = True,
        mutate=None,          # type: ignore[no-untyped-def]
        model: str = "scripted-1",
    ) -> None:
        self.name = name
        self.capability = capability
        self.cost_rank = cost_rank
        self.default_model = model
        self.requires_api_key = False
        self._text = text
        self._error = error
        self._available = available
        self._mutate = mutate
        self.calls = 0

    def is_available(self) -> bool:
        return self._available

    def describe(self) -> dict:
        return {"name": self.name, "capability": self.capability, "model": self.default_model}

    def interpret(self, request):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self._mutate is not None:
            self._mutate(request.payload)
        if self._error is not None:
            raise self._error
        return LLMResponse(
            text=self._text,
            provider=self.name,
            model=self.default_model,
            attempts=(Attempt(self.name, self.default_model, True, "scripted"),),
        )


FULL_TEXT = """【事实】
坐山午、向山子，山心角度坐 180°／向 0°。

【传统解释】
午山属火，为阳山。传统上以此观察卦气是否相扶。

【针对问题】
关于事业，传统上多从卦气与喜用是否相扶来观察。

【参考建议】
· 先处理确定性事，再谈取舍。
"""


def _orientation():  # type: ignore[no-untyped-def]
    return calculate_orientation(sitting="午", facing="子")


def _chart():  # type: ignore[no-untyped-def]
    return calculate_bazi(BirthInput(1981, 9, 14, 8, 0, gender="male"))


def _context(category: str = "事业", text: str = "今年适合换工作吗") -> object:
    return build_context(
        "sess-ai-1",
        compass=_orientation(),
        bazi=_chart(),
        question=QuestionContext(category=category, text=text),
    )


# ==========================================================================
# 提示词（RULE-002 / RULE-010 的契约）
# ==========================================================================


class TestPrompt:
    def test_ai_input_is_structured_payload_only(self) -> None:
        """AI 收到的只有结构化载荷：没有照片、没有图像数据。"""
        ctx = _context()
        payload = ctx.to_ai_payload()          # type: ignore[attr-defined]
        msg = build_user_message(payload)

        assert "【计算事实 · 只读】" in msg
        assert "1981-09-14" in msg             # 来自排盘**结果**
        assert "今年适合换工作吗" in msg        # 用户问题与计算结果分离传入

        # 载荷里不存在任何图像/原始输入通道
        for banned in ("base64", "照片", "图片", "image", "bytes"):
            assert banned not in msg, f"载荷里混入了不该有的东西：{banned}"

        # 不确定性必须一并交给模型
        for u in payload["uncertainties"]:
            assert u in msg

    def test_required_sections_come_from_payload(self) -> None:
        """区块定义的真源是载荷 —— 计算层改结构，AI 层自动跟随。"""
        from xuanpan_ai.prompt import required_sections_of

        payload = _context().to_ai_payload()   # type: ignore[attr-defined]
        assert required_sections_of(payload) == tuple(payload["constraints"]["required_sections"])

        # 换一组自定义区块：提示词与解析都必须跟随
        custom = {**payload, "constraints": {**payload["constraints"],
                                            "required_sections": ["结论", "依据"]}}
        assert required_sections_of(custom) == ("结论", "依据")
        prompt = build_system_prompt(custom)
        assert "【结论】" in prompt and "【依据】" in prompt
        assert "【事实】" not in prompt
        assert [s.title for s in parse_sections("【结论】甲\n【依据】乙", titles=("结论", "依据"))] == [
            "结论", "依据"
        ]

    def test_default_sections_agree_with_calculation_layer(self) -> None:
        """兜底默认值也必须与计算层的当前定义一致（防两处漂移）。"""
        from xuanpan_ai.prompt import required_sections_of

        assert required_sections_of({}) == REQUIRED_SECTIONS
        assert list(REQUIRED_SECTIONS) == list(
            _context().to_ai_payload()["constraints"]["required_sections"]  # type: ignore[attr-defined]
        )

    def test_system_prompt_carries_all_forbidden_items(self) -> None:
        """禁令必须来自 payload，不得在本层另抄一份。"""
        payload = _context().to_ai_payload()   # type: ignore[attr-defined]
        prompt = build_system_prompt(payload)
        for item in payload["constraints"]["forbidden"]:
            assert item in prompt, f"禁令未进入提示词：{item}"

    def test_system_prompt_keeps_core_prohibitions(self) -> None:
        prompt = build_system_prompt(_context().to_ai_payload())  # type: ignore[attr-defined]
        for phrase in ("只读", "不得修改", "不确定", "科学"):
            assert phrase in prompt, f"提示词丢失关键约束：{phrase}"

    def test_system_prompt_lists_four_sections(self) -> None:
        prompt = build_system_prompt(_context().to_ai_payload())  # type: ignore[attr-defined]
        for title in REQUIRED_SECTIONS:
            assert f"【{title}】" in prompt


# ==========================================================================
# 输出解析
# ==========================================================================


class TestParseSections:
    def test_bracket_form(self) -> None:
        got = [(s.title, s.body) for s in parse_sections(FULL_TEXT)]
        assert [t for t, _ in got] == list(REQUIRED_SECTIONS)

    def test_markdown_and_bold_forms(self) -> None:
        text = "## 事实\n甲\n\n**传统解释**\n乙\n\n参考建议\n丙"
        titles = [s.title for s in parse_sections(text)]
        assert titles == ["事实", "传统解释", "参考建议"]

    def test_colon_form(self) -> None:
        assert [s.title for s in parse_sections("事实：甲\n传统解释：乙")] == ["事实", "传统解释"]

    def test_preamble_is_kept(self) -> None:
        sections = parse_sections("先说一句。\n\n【事实】甲")
        assert sections[0].title == "补充"
        assert "先说一句" in sections[0].body

    def test_no_heading_returns_empty(self) -> None:
        assert parse_sections("完全没有任何标题的一段话。") == ()

    def test_missing_sections_reports_gap(self) -> None:
        sections = parse_sections("【事实】甲\n【传统解释】乙")
        assert missing_sections(sections) == ["针对问题", "参考建议"]

    def test_unmentioned_uncertainties(self) -> None:
        got = unmentioned_uncertainties("本文只说了坐向", ["罗盘识别结果尚未经用户确认"])
        assert got == ["罗盘识别结果尚未经用户确认"]


class TestSplitRegisters:
    """文体切分 —— 两个文体内部用的是**同一套区块标题**，故必须先切再解析。

    若不切而整体解析：两套标题（事实 / 传统解释 / 针对问题 / 参考建议）会混成
    8 个区块且顺序被打乱，之后再也无法还原"哪一段属于哪个文体"。
    """

    def test_both_registers_split_cleanly(self) -> None:
        text = (
            f"【{REGISTER_EXPERT}】\n【事实】甲\n【传统解释】乙\n"
            f"\n【{REGISTER_PLAIN}】\n【事实】丙\n【传统解释】丁\n"
        )
        expert, plain = split_registers(text)
        assert "甲" in expert and "乙" in expert
        assert "丙" not in expert, "白话块的内容漏进了专业块"
        assert "丙" in plain and "丁" in plain
        assert "甲" not in plain, "专业块的内容漏进了白话块"
        # 标记本身必须被摘掉：留着它，parse_sections 会把它当成一个多余区块
        assert REGISTER_EXPERT not in expert
        assert REGISTER_PLAIN not in plain

    def test_plain_only_still_parses(self) -> None:
        expert, plain = split_registers(f"【{REGISTER_PLAIN}】\n【事实】乙")
        assert expert.strip() == ""
        assert "乙" in plain

    def test_no_marker_means_no_plain_register(self) -> None:
        """认不出白话块时返回空串 —— 由调用方记 warning，**不得拿专业版顶上**。"""
        expert, plain = split_registers(FULL_TEXT)
        assert expert == FULL_TEXT
        assert plain == ""

    def test_preamble_before_expert_marker_is_kept(self) -> None:
        """标记之前的文字不能因为切分而丢 —— 丢了就是内容损失。"""
        expert, _ = split_registers(
            f"下面开始分析。\n\n【{REGISTER_EXPERT}】\n【事实】甲\n【{REGISTER_PLAIN}】\n【事实】乙"
        )
        assert "下面开始分析" in expert
        assert "甲" in expert

    def test_markdown_and_bold_marker_forms(self) -> None:
        """模型不会总是用【】。认不出的表现是"白话版凭空消失"。"""
        for form in (f"## {REGISTER_PLAIN}", f"**{REGISTER_PLAIN}**", f"{REGISTER_PLAIN}："):
            _, plain = split_registers(f"【事实】甲\n\n{form}\n【事实】乙")
            assert "乙" in plain, f"{form!r} 这种写法没有被认出"


# ==========================================================================
# 模板 provider（离线兜底）
# ==========================================================================


class TestTemplateProvider:
    def test_available_without_any_key(self) -> None:
        assert get_provider("template").is_available() is True

    def test_deterministic(self) -> None:
        """同一载荷两次生成必须逐字相同 —— 无随机、无时间戳。"""
        ctx = _context()
        router = AIRouter([get_provider("template")])
        a = build_report(ctx, router=router)
        b = build_report(ctx, router=router)
        assert a.interpretation.text == b.interpretation.text

    def test_four_sections_present(self) -> None:
        report = build_report(_context())
        titles = [s.title for s in report.interpretation.sections]
        for title in REQUIRED_SECTIONS:
            assert title in titles

    def test_facts_values_are_quoted_not_invented(self) -> None:
        """模板只能复述计算层给的数值。"""
        ctx = _context()
        facts = ctx.to_facts()                 # type: ignore[attr-defined]
        text = build_report(ctx).interpretation.text
        assert facts["compass"]["sitting"] in text
        assert facts["compass"]["facing"] in text
        assert str(facts["compass"]["sitting_degree"])[:3] in text

    def test_every_domain_quotes_its_core_values(self) -> None:
        """逐领域核对：计算层的关键值必须真的出现在报告文本里。

        `[已确认]` 这条测试的由来：模板 provider 曾把 `pillars` 的键猜成
        「年柱/月柱/日柱/时柱」（实际是 `year/month/day/hour`）、把五行计数
        猜成英文键（实际是中文键），结果是「四柱：—」「木0、火0…」这种
        **看起来正常、实则空转**的输出。字段名靠猜必然踩这个坑，
        所以要有一条按领域逐项核对的测试。可避免的漂移就不该留给人眼。
        """
        from fortune_core.bazi import BirthInput, calculate_bazi
        from fortune_core.liuyao import cast_liuyao
        from fortune_core.naming import analyze_name
        from fortune_core.qian import draw_qian

        ctx = build_context(
            "sess-all",
            compass=calculate_orientation(sitting="午", degree=177.0, source="vision"),
            bazi=_chart(),
            liuyao=cast_liuyao(coins=[(True, True, True)] * 6),   # 3 背 = 老阳
            qian=draw_qian(7),
            name_analysis=analyze_name("张伟"),
        )
        facts = ctx.to_facts()                 # type: ignore[attr-defined]
        text = build_report(ctx).interpretation.text

        # 罗盘
        assert facts["compass"]["sitting"] in text
        assert facts["compass"]["pair"] in text
        # 八字：四柱每一个都必须出现
        assert facts["bazi"]["pillar_list"], "夹具应产出四柱"
        for ganzhi in facts["bazi"]["pillar_list"]:
            assert ganzhi in text, f"四柱「{ganzhi}」未出现在报告里"
        assert facts["bazi"]["day_master"] in text
        # 五行计数不得全为 0（这正是字段名猜错时的症状）
        counts = facts["bazi"]["five_elements_simple"]["counts"]
        assert any(v > 0 for v in counts.values())
        assert any(str(int(v)) in text for v in counts.values() if v > 0)
        # 六爻
        assert facts["liuyao"]["original_gua"] in text
        # 灵签
        assert str(facts["qian"]["number"]) in text
        assert facts["qian"]["title"] in text
        # 姓名
        assert facts["name"]["name"] in text

    def test_unknown_domain_values_never_fabricated(self) -> None:
        """缺规则表时必须说"未提供"，不得编造一个干支填进去。"""
        ctx = build_context("s", compass=calculate_orientation(sitting="午", degree=177.0))
        facts = ctx.to_facts()                 # type: ignore[attr-defined]
        assert facts["compass"]["fenjin_table_available"] is False
        assert facts["compass"]["fenjin"]["ganzhi"] is None
        text = build_report(ctx).interpretation.text
        assert "干支规则表未提供" in text

    def test_compass_without_degree_has_no_fenjin_at_all(self) -> None:
        """没有精确角度时连分金几何格位都不应出现（不猜）。

        计算层此时把 `fenjin` 明确置为 `None`（键在、值为空），
        而不是填一个默认格位 —— 这个区别就是"不猜"与"猜"的分界。
        """
        ctx = build_context("s2", compass=calculate_orientation(sitting="午"))
        facts = ctx.to_facts()["compass"]      # type: ignore[attr-defined]
        assert facts["fenjin"] is None

        report = build_report(ctx)
        fact_block = next(s for s in report.interpretation.sections if s.title == "事实")
        # 事实区块里不得出现分金结论（不确定性区块里解释"为何没有"是应该的）
        assert "分金" not in fact_block.body
        assert any("未提供精确角度" in u for u in report.uncertainties)

    def test_handles_empty_context(self) -> None:
        """没有任何计算结果时也要给出诚实报告，不得编造。"""
        report = build_report(build_context("sess-empty"))
        assert "尚未产生任何确定性计算结果" in report.interpretation.text
        assert report.facts == {}


# ==========================================================================
# 双文体（专业分析 / 白话讲解）
# ==========================================================================
#
# 这组测试守的是"两种文体**真的都存在、且真的不同**"。
# 最容易出现的假绿是：实现者偷懒把 plain_sections 直接指向 sections ——
# 那样界面上的切换按钮点了之后内容一模一样，看起来"功能做好了"。


class TestTwoRegisters:
    def test_template_provider_has_both_registers(self) -> None:
        """零成本路径也必须有两文体 —— 不配 key 的用户走的就是这条路。

        少了它，这个能力在默认配置下等于不存在（界面会一直显示"本篇没有白话版"）。
        """
        report = build_report(_context())
        assert report.interpretation.has_plain is True
        titles = [s.title for s in report.interpretation.plain_sections]
        for title in REQUIRED_SECTIONS:
            assert title in titles, f"白话版缺少区块「{title}」"

    def test_plain_register_is_not_a_copy_of_the_expert_one(self) -> None:
        """两个文体的正文必须**真的不同**。

        防的正是"直接把 sections 赋给 plain_sections"这种实现 ——
        那种情况下界面切换按钮点了没变化，而任何结构断言都照样通过。

        「不确定性说明」区块刻意排除在外：它由系统**逐字**追加、两种文体里
        本就应当一模一样（见下一条用例）。把它算进来，这条断言会恒假。
        """
        report = build_report(_context())

        def model_sections(sections) -> dict[str, str]:  # type: ignore[no-untyped-def]
            return {s.title: s.body for s in sections if s.title != UNCERTAINTY_SECTION_TITLE}

        expert = model_sections(report.interpretation.sections)
        plain = model_sections(report.interpretation.plain_sections)
        shared = set(expert) & set(plain)
        assert shared, "两个文体没有任何同名区块，本测试无从比较（实现可能坏了）"
        same = [t for t in shared if expert[t] == plain[t]]
        assert not same, f"以下区块在两种文体里逐字相同，等于没有白话版：{same}"

    def test_plain_register_actually_explains_the_jargon(self) -> None:
        """白话版要**解释**术语，而不只是换个词说同一句。

        取最容易验证的一处：坐山/向山。白话版必须把「坐 = 背面、向 = 正面」
        说出来 —— 否则读者仍然不知道这两个字指什么。
        """
        report = build_report(_context())
        fact = next(s for s in report.interpretation.plain_sections if s.title == "事实")
        assert "背面" in fact.body and "正面" in fact.body

    def test_jargon_in_plain_register_is_always_explained(self) -> None:
        """白话版里出现的术语，必须在同一篇里被解释过。

        🔴 这条守的是"照录"策略的漏洞：白话版会照录核心层的结论原话（照录才
        不走样），而原话里必然带术语（日主、喜用、身弱…）。只照录不解释，
        等于把看不懂的句子原样再贴一遍 —— 界面看起来完全正常，
        但这一版对它的目标读者毫无用处。所以照录之后必须配术语解释。

        「不确定性说明」区块**不在扫描范围内**：它是系统从计算层**逐字**粘来的，
        两种文体里完全相同（见下一条用例），且刻意不加解释 ——
        那一段的价值恰恰在于"与我算出来的原文一字不差"，动它才是错的。
        因此其中的术语（如「身强」）不出现在本断言里是预期行为。
        """
        report = build_report(_context())
        plain_all = "\n".join(
            s.body
            for s in report.interpretation.plain_sections
            if s.title != UNCERTAINTY_SECTION_TITLE
        )

        assert "日主" in plain_all, "本用例的前提是原话里确实出现了「日主」"
        unexplained = [
            term
            for term, gloss in _TERM_GLOSSARY.items()
            if term in plain_all and gloss not in plain_all
        ]
        assert not unexplained, f"白话版用了这些词却没有解释：{unexplained}"

    def test_uncertainty_block_is_identical_in_both_registers(self) -> None:
        """系统追加的不确定性区块在两种文体里逐字相同 —— 这是刻意的，不是巧合。

        它是计算层结果的直接粘贴，与文体无关。任何"让它随文体改写"的改动
        都会引入模型/模板改写风险，而它恰恰是最不该被改写的那一段。
        """
        report = build_report(_context())

        def block_of(sections) -> str:  # type: ignore[no-untyped-def]
            return next(s.body for s in sections if s.title == UNCERTAINTY_SECTION_TITLE)

        assert block_of(report.interpretation.sections) == block_of(
            report.interpretation.plain_sections
        )

    def test_both_registers_carry_the_uncertainty_block(self) -> None:
        """两种文体**各自**都要带不确定性区块。

        🔴 只给专业版追加是错的：白话版的读者恰恰是最容易把结论当承诺的人
        （他看不懂术语、只看结论）。把风险提示只放在他看不懂的那一版里，
        等于没放 —— 而报告看起来完全合规。
        """
        report = build_report(_context())
        assert report.uncertainties, "本用例的前提是这次会话确实有不确定性"
        for name, sections in (
            ("专业分析", report.interpretation.sections),
            ("白话讲解", report.interpretation.plain_sections),
        ):
            block = next(
                (s for s in sections if s.title == UNCERTAINTY_SECTION_TITLE), None
            )
            assert block is not None, f"「{name}」里没有不确定性区块"
            assert report.uncertainties[0][:8] in block.body

    def test_missing_plain_register_is_reported_not_substituted(self) -> None:
        """模型没写白话块时：如实报，**不拿专业版冒充**。

        冒充的表现是界面显示"有白话版"、点进去与专业版一字不差 ——
        读者会以为白话功能坏了，而任何一层都不会报错。
        """
        model = ScriptedProvider("only-expert", text=FULL_TEXT)
        report = build_report(_context(), router=AIRouter([model]))
        assert report.interpretation.has_plain is False
        assert report.interpretation.plain_sections == ()
        assert any(REGISTER_PLAIN in w for w in report.interpretation.warnings), (
            f"没有说明白话版缺失：{report.interpretation.warnings}"
        )
        # 专业版照常解析（不能因为缺白话就整体降级）
        assert [s.title for s in report.interpretation.sections][:1] == ["事实"]

    def test_scripted_two_register_text_lands_in_the_right_fields(self) -> None:
        """模型按格式输出时，两块内容必须各归各位。"""
        model = ScriptedProvider(
            "two-reg",
            text=(
                f"【{REGISTER_EXPERT}】\n【事实】专业的事实\n【传统解释】专业的解释\n"
                "【针对问题】专业的回答\n【参考建议】专业的建议\n"
                f"\n【{REGISTER_PLAIN}】\n【事实】白话的事实\n【传统解释】白话的解释\n"
                "【针对问题】白话的回答\n【参考建议】白话的建议\n"
            ),
        )
        report = build_report(_context(), router=AIRouter([model]))
        expert = {s.title: s.body for s in report.interpretation.sections}
        plain = {s.title: s.body for s in report.interpretation.plain_sections}
        assert "专业的事实" in expert["事实"]
        assert "白话的事实" not in expert["事实"]
        assert "白话的事实" in plain["事实"]
        assert "专业的事实" not in plain["事实"]

    def test_serialized_payload_exposes_both_registers(self) -> None:
        """接口契约：`to_dict()` 必须同时给出两份区块与 has_plain。

        前端靠 `has_plain` 决定显示切换还是显示"没有白话版"的说明。
        少了这个键，前端要么报错、要么自己算（然后漏算）——
        漏算的表现就是"切换按钮点了没反应"。
        """
        body = build_report(_context()).to_dict()
        interp = body["interpretation"]
        assert interp["has_plain"] is True
        assert interp["plain_sections"], "序列化后白话区块为空"
        assert [s["title"] for s in interp["plain_sections"]] == [
            s["title"] for s in interp["sections"]
        ], "两种文体的区块标题与顺序应当一致，否则界面无法并排对照"

    def test_prompt_asks_for_both_registers(self) -> None:
        prompt = build_system_prompt(_context().to_ai_payload())  # type: ignore[attr-defined]
        for title in REGISTER_TITLES:
            assert f"【{title}】" in prompt, f"提示词里没有要求写「{title}」"
        # 白话版必须被明确要求"讲同一件事、不得含糊掉不确定性"
        assert "同一" in prompt and "不确定性" in prompt

    def test_category_angle_tables_are_in_sync(self) -> None:
        """专业版与白话版的问题类别表必须键集合一致。

        只加了一边，表现是那一类问题在白话版里退回一句空话（走 `.get(...)` 兜底），
        而专业版照常有内容 —— 界面上看不出任何异常。
        """
        assert set(_CATEGORY_ANGLE) == set(_CATEGORY_ANGLE_PLAIN)

    def test_report_text_property_is_the_expert_register_only(self) -> None:
        """`text` 只拼专业版：它要回灌给模型当上下文，白话版是给人看的。

        这条钉住契约 —— 哪天有人把白话版也拼进 `text`，
        对话历史会平白翻倍，而看不出任何异常（只是越来越贵、越来越慢）。
        """
        report = build_report(_context())
        assert report.interpretation.text == "\n\n".join(
            f"【{s.title}】\n{s.body}" for s in report.interpretation.sections
        )
        assert report.interpretation.plain_text, "白话版的整段文本应当非空"


# ==========================================================================
# 三层分离
# ==========================================================================


class TestThreeLayerSeparation:
    def test_report_keeps_three_separate_fields(self) -> None:
        report = build_report(_context())
        d = report.to_dict()
        # 三个键并存，而不是一个字段里塞三段文字
        for key in ("facts", "tradition", "interpretation"):
            assert key in d
        assert "AI_INTERPRETATION" not in d          # 没有合并层
        assert d["facts"] is not d["tradition"]

    def test_facts_and_tradition_match_calculation_layer(self) -> None:
        ctx = _context()
        report = build_report(ctx)
        assert report.facts == ctx.to_facts()          # type: ignore[attr-defined]
        assert report.tradition == ctx.to_tradition()  # type: ignore[attr-defined]

    def test_model_text_never_enters_facts(self) -> None:
        """模型输出里塞入看起来像 facts 的键，也不得污染任何只读层。"""
        # 标记用 FACT 层绝无的独特串，避免与合法的干支/神煞内容撞字。
        text = "【事实】EVIL_MARKER_A\n【传统解释】EVIL_MARKER_B\n【针对问题】EVIL_MARKER_C\n【参考建议】EVIL_MARKER_D"
        provider = ScriptedProvider("evil", text=text)
        report = build_report(_context(), router=AIRouter([provider]))
        blob = str(report.facts)
        assert "EVIL_MARKER_A" not in blob and "EVIL_MARKER_C" not in blob

    def test_disclaimer_is_fixed_verbatim(self) -> None:
        report = build_report(_context())
        assert report.disclaimer == DISCLAIMER
        assert report.disclaimer == "以上内容属于传统文化娱乐/学习参考"


class TestUncertaintiesGuarantee:
    """不确定性必须**一定**出现在报告里 —— 与模型是否提及无关。"""

    def test_uncertainties_present_even_if_model_omits_them(self) -> None:
        text = "【事实】甲\n【传统解释】乙\n【针对问题】丙\n【参考建议】丁"
        provider = ScriptedProvider("silent", text=text)
        report = build_report(_context(), router=AIRouter([provider]))

        assert report.uncertainties, "计算层应给出不确定性"
        titles = [s.title for s in report.interpretation.sections]
        assert UNCERTAINTY_SECTION_TITLE in titles
        block = next(s for s in report.interpretation.sections if s.title == UNCERTAINTY_SECTION_TITLE)
        for u in report.uncertainties:
            assert u in block.body
        assert "未经模型改写" in block.body
        assert any("未提及" in w for w in report.interpretation.warnings)

    def test_unconfirmed_compass_produces_uncertainty(self) -> None:
        """未确认的识别结果必须被标为不确定。"""
        ctx = build_context("s", compass=calculate_orientation(sitting="午", facing="子"))
        report = build_report(ctx)
        assert any("尚未经用户确认" in u for u in report.uncertainties)

    def test_health_question_adds_medical_disclaimer(self) -> None:
        report = build_report(_context(category="健康", text="身体如何"))
        assert any("医疗建议" in u for u in report.uncertainties)
        block = next(
            s for s in report.interpretation.sections if s.title == UNCERTAINTY_SECTION_TITLE
        )
        assert "医疗建议" in block.body

    def test_investment_question_adds_investment_disclaimer(self) -> None:
        report = build_report(_context(category="财运", text="该投资吗"))
        assert any("投资建议" in u for u in report.uncertainties)


# ==========================================================================
# 路由与降级
# ==========================================================================


class TestRouter:
    def test_falls_back_on_failure_and_records_trail(self) -> None:
        bad = ScriptedProvider("bad", error=ProviderCallError("超时", provider="bad"))
        good = ScriptedProvider("good", text=FULL_TEXT)
        router = AIRouter([bad, good])
        resp = router.generate(_context().to_ai_payload())   # type: ignore[attr-defined]

        assert resp.provider == "good"
        assert resp.degraded is True
        assert [a.ok for a in resp.attempts] == [False, True]
        assert any("自动切换" in w for w in resp.warnings)
        assert bad.calls == 1 and good.calls == 1

    def test_unavailable_provider_is_skipped_not_counted_as_failure(self) -> None:
        """缺 key 是环境问题，不是调用失败 —— 不该混进降级轨迹。"""
        nokey = ScriptedProvider("nokey", available=False)
        good = ScriptedProvider("good", text=FULL_TEXT)
        resp = AIRouter([nokey, good]).generate(_context().to_ai_payload())  # type: ignore[attr-defined]
        assert nokey.calls == 0
        assert resp.degraded is False
        assert [a.provider for a in resp.attempts] == ["good"]

    def test_template_is_last_resort_not_first_choice(self) -> None:
        cloud = ScriptedProvider("cloud", capability="reasoning", cost_rank=3, text=FULL_TEXT)
        tmpl = ScriptedProvider("tmpl", capability="template", cost_rank=0, text=FULL_TEXT)
        resp = AIRouter([tmpl, cloud]).generate(_context().to_ai_payload())  # type: ignore[attr-defined]
        assert resp.provider == "cloud", "模板是兜底，不应抢在真实模型前面"

    def test_mode_cost_prefers_cheaper(self) -> None:
        expensive = ScriptedProvider("pricey", capability="reasoning", cost_rank=3, text=FULL_TEXT)
        cheap = ScriptedProvider("cheap", capability="fast", cost_rank=1, text=FULL_TEXT)
        router = AIRouter([expensive, cheap], RouterConfig(mode="cost"))
        assert router.generate(_context().to_ai_payload()).provider == "cheap"  # type: ignore[attr-defined]

    def test_mode_quality_prefers_stronger(self) -> None:
        strong = ScriptedProvider("strong", capability="reasoning", cost_rank=3, text=FULL_TEXT)
        weak = ScriptedProvider("weak", capability="fast", cost_rank=1, text=FULL_TEXT)
        router = AIRouter([weak, strong], RouterConfig(mode="quality"))
        assert router.generate(_context().to_ai_payload()).provider == "strong"  # type: ignore[attr-defined]

    def test_auto_uses_cost_order_for_followup(self) -> None:
        strong = ScriptedProvider("strong", capability="reasoning", cost_rank=3, text=FULL_TEXT)
        weak = ScriptedProvider("weak", capability="fast", cost_rank=1, text=FULL_TEXT)
        router = AIRouter([weak, strong], RouterConfig(mode="auto"))
        payload = _context().to_ai_payload()                # type: ignore[attr-defined]
        assert router.generate(payload, task="followup").provider == "weak"
        assert router.generate(payload, task="report").provider == "strong"

    def test_all_failed_raises_instead_of_faking(self) -> None:
        p = ScriptedProvider("only", error=ProviderCallError("炸了", provider="only"))
        with pytest.raises(AllProvidersFailedError) as ei:
            AIRouter([p]).generate(_context().to_ai_payload())   # type: ignore[attr-defined]
        assert "only" in str(ei.value)

    def test_provider_exception_does_not_break_chain(self) -> None:
        """provider 自己的缺陷（如 TypeError）也必须被隔离。"""
        broken = ScriptedProvider("broken", error=TypeError("内部实现有 bug"))
        good = ScriptedProvider("good", text=FULL_TEXT)
        resp = AIRouter([broken, good]).generate(_context().to_ai_payload())  # type: ignore[attr-defined]
        assert resp.provider == "good"
        assert any("TypeError" in a.detail for a in resp.attempts)

    def test_invalid_mode_rejected(self) -> None:
        with pytest.raises(ValueError):
            RouterConfig(mode="whatever")  # type: ignore[arg-type]


class TestPayloadIntegrity:
    """RULE-002 的运行时守卫：provider 不得改动只读的计算结果。"""

    def test_mutation_is_reverted_and_reported(self) -> None:
        def tamper(payload: dict) -> None:
            payload["facts"]["bazi"]["day_master"] = "假"

        evil = ScriptedProvider("evil", text=FULL_TEXT, mutate=tamper)
        payload = _context().to_ai_payload()       # type: ignore[attr-defined]
        original = payload["facts"]["bazi"]["day_master"]

        resp = AIRouter([evil]).generate(payload)

        assert payload["facts"]["bazi"]["day_master"] == original, "载荷必须被还原"
        assert any("改动已被丢弃" in w for w in resp.warnings)

    def test_report_facts_survive_tampering_provider(self) -> None:
        def tamper(payload: dict) -> None:
            payload["facts"]["compass"]["sitting"] = "假山"

        evil = ScriptedProvider("evil", text=FULL_TEXT, mutate=tamper)
        ctx = _context()
        report = build_report(ctx, router=AIRouter([evil]))
        assert report.facts["compass"]["sitting"] == "午"
        assert report.facts == ctx.to_facts()          # type: ignore[attr-defined]


# ==========================================================================
# Provider 注册表与密钥安全
# ==========================================================================


class TestProvidersAndSecrets:
    def test_registry_lists_both(self) -> None:
        ids = {p["id"] for p in list_providers()}
        assert ids == {"template", "openai_compat"}

    def test_cloud_requires_key(self) -> None:
        entry = next(p for p in CAPABILITY_MATRIX if p["id"] == "openai_compat")
        assert entry["requires_api_key"] is True
        assert "计费" in entry["cost"]
        assert get_provider("openai_compat", api_key="").is_available() is False

    def test_cloud_available_when_configured(self) -> None:
        p = get_provider(
            "openai_compat", api_key="sk-test", base_url="http://127.0.0.1:9/v1", model="m"
        )
        assert p.is_available() is True

    def test_unavailable_cloud_raises_not_silently_empty(self) -> None:
        p = get_provider("openai_compat", api_key="")
        with pytest.raises(ProviderCallError):
            p.interpret(
                type("R", (), {"payload": {}, "system_prompt": "", "user_message": "",
                               "history": (), "max_tokens": 10, "temperature": 0.7,
                               "session_id": "x"})()
            )

    def test_api_key_never_leaks_in_error_message(self) -> None:
        """密钥绝不能出现在错误消息里（日志会把它带出去）。"""
        secret = "sk-super-secret-1234567890"
        p = OpenAICompatProvider(
            api_key=secret, base_url="http://127.0.0.1:1/v1", model="m", max_retries=0, timeout=0.5
        )
        request = type("R", (), {
            "payload": {}, "system_prompt": "s", "user_message": "u",
            "history": (), "max_tokens": 10, "temperature": 0.7, "session_id": "x",
        })()
        with pytest.raises(ProviderCallError) as ei:
            p.interpret(request)
        assert secret not in str(ei.value)
        assert secret[:8] not in str(ei.value)

    def test_redact_helper(self) -> None:
        assert _redact("key=sk-abcdef123456", "sk-abcdef123456") == "key=***"
        assert _redact("nothing", "") == "nothing"

    def test_endpoint_presets_have_no_hardcoded_model(self) -> None:
        """端点预设只给 base_url —— 预置模型名迟早变成错误信息。"""
        for preset in list_endpoint_presets():
            assert preset["base_url"].startswith("http")
            assert "model" not in preset
