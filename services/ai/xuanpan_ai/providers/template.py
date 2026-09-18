"""模板 provider —— 零成本、离线、完全确定性的兜底路径。

存在的理由：云端模型可能没配 key、可能超时、可能被墙。这时候**不能**
退化成"随便生成一段话"（用户会以为那是基于他数据的解读）。
本 provider 只做一件事：把 `facts` / `tradition` 里**已经算好的值**
按固定句式复述出来，措辞不随会话变化、无随机性、无网络。

它的输出**信息量真实**（所有数值都来自计算层），但**风格机械**——
这正是它的定位：可用、可审计、绝不编造。用户接上模型后自然升级。
"""

from __future__ import annotations

from typing import Any

from ..models import (
    REGISTER_EXPERT,
    REGISTER_PLAIN,
    Attempt,
    LLMRequest,
    LLMResponse,
    ReportSection,
)
from .base import BaseLLMProvider

#：问题类别 → 传统术数通常观察的切入点（只描述视角，不下断语）
_CATEGORY_ANGLE: dict[str, str] = {
    "事业": "多从坐向的卦气与命局的喜用是否相扶来观察",
    "婚姻": "多从阴阳配合与日主喜忌是否相济来观察",
    "健康": "传统上会看五行偏枯与旺衰失衡之处",
    "财运": "传统上会看财星与日主的承载关系",
    "学业": "传统上会看印星与文昌类神煞的配合",
    "人际": "传统上会看比劫与官杀的制化关系",
    "出行": "传统上会看方位卦气是否与命局相宜",
    "其他": "只能就现有结果作一般性梳理",
}

#：上表的**白话版** —— 同一视角，改用日常话说。
#
# 为什么不直接复用 `_CATEGORY_ANGLE`：那一列的用词本身就是术语（卦气、喜用、
# 日主、比劫…）。白话文体里出现它们，就等于白话版没写 —— 读者仍然读不懂。
# 两表必须成对维护，故 `tests/ai/test_ai_report.py` 断言两表的键集合完全相同：
# 只加了专业版忘了白话版，表现是白话版在那一类上退回一句空话。
_CATEGORY_ANGLE_PLAIN: dict[str, str] = {
    "事业": "看的是方向带来的气场，跟你生辰里最需要的那个属性合不合得来",
    "婚姻": "看的是双方的阴阳能不能互相补上，以及生辰里的好恶是否相合",
    "健康": "看的是五行里有没有哪一类明显偏多或偏少",
    "财运": "看的是财这一项与你自身的分量是否相称（能不能接得住）",
    "学业": "看的是助学问的那几项与你生辰是否配合",
    "人际": "看的是合作与竞争这两股力量之间能不能互相制约",
    "出行": "看的是要去的方向与你生辰是否相宜",
    "其他": "只能就现有的结果做一般性的梳理",
}

#：白话版里引用传统原文时的引导语。
#：模板 provider 的能力是**忠实复述**，不是重新解释；把术语原文照录、
#：并说清"这是照录"，比用白话转述一遍更安全 —— 转述就可能走样，而走样
#：在这里等于编造（RULE-008）。
_QUOTE_LEAD = "（下面这条只有术语较多的原话，照录如下、不作改写）"

#：核心层自由文本里会出现的术语 → 一句白话解释。
#
# 为什么必须有这张表：白话版会**照录**核心层给的结论原话（照录才不会走样），
# 但照录若只配一句"这是原话"，读者拿到的仍是看不懂的句子 —— 白话版就没意义了。
# 所以照录之后要把其中出现的词逐个解释一遍：**解释术语的含义不是编造数据**，
# 它是让已有数据可被读懂的唯一办法。
#
# ⚠️ 与 `_CATEGORY_ANGLE_PLAIN` 同理，这张表要与核心层实际用词保持同步。
# 核心层改写了措辞、这里没跟上，表现是白话版对某个词不作解释 ——
# 读者读到的仍然是术语（`tests/ai/test_ai_report.py` 有用例守着已知术语）。
_TERM_GLOSSARY: dict[str, str] = {
    "日主": "出生那一天的干支，传统上把它当作「你自己」",
    "身强": "整体力量偏强（这是状态描述，不是说好或坏）",
    "身弱": "整体力量偏弱（这是状态描述，不是说好或坏）",
    "喜用": "对你有帮助的那几类属性",
    "忌神": "对你不利的那几类属性",
    "旺衰": "力量的强弱",
    "月令": "出生的那个月份（传统上认为它影响最大）",
    "用神": "用来把整体调到平衡的那一项",
    "大运": "按十年一段划分的人生阶段",
    "神煞": "传统给某些干支组合起的名字（各流派差异很大）",
    "扶抑法": "一种取用神的思路：太强就压一压，太弱就扶一扶",
    "流派": "不同的传承派别，同一件事各派说法并不完全一致",
    "吉凶": "好与坏",
    "二十四山": "把一圈方位分成 24 份的分类法",
}


def _explain_terms(text: str) -> str:
    """把 `text` 里出现的术语逐条解释一遍；没命中任何一个时返回空串。"""
    hits = [f"· 「{term}」：{gloss}" for term, gloss in _TERM_GLOSSARY.items() if term in text]
    if not hits:
        return ""
    return "原文里出现的几个词，先解释一下：\n" + "\n".join(hits)

_PILLAR_LABELS: tuple[str, ...] = ("年柱", "月柱", "日柱", "时柱")
_PILLAR_KEYS: tuple[str, ...] = ("year", "month", "day", "hour")
_ELEMENT_CN_ORDER: tuple[str, ...] = ("木", "火", "土", "金", "水")
_CN_TO_EN: dict[str, str] = {
    "木": "wood", "火": "fire", "土": "earth", "金": "metal", "水": "water",
}


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _join(sections: tuple[ReportSection, ...]) -> str:
    """把区块拼成带【标题】的整段 —— 解析层反解回区块就靠这个格式。"""
    return "\n\n".join(f"【{s.title}】\n{s.body}" for s in sections)


def _render_element_counts(stats: dict[str, Any]) -> str:
    """渲染五行计数。

    `[已确认]` 计算层的 `counts` 用**中文键**（木/火/土/金/水），
    另有一份 `counts_en` 备用。两者都读，避免上游换键名时静默输出 0。
    """
    counts = stats.get("counts") or {}
    counts_en = stats.get("counts_en") or {}
    parts: list[str] = []
    for cn in _ELEMENT_CN_ORDER:
        value = counts.get(cn)
        if value is None:
            value = counts_en.get(_CN_TO_EN[cn])
        if value is None:
            continue
        parts.append(f"{cn}{_fmt(value)}")
    return "、".join(parts)


def _render_pillars(b: dict[str, Any]) -> str:
    """渲染四柱。

    `[已确认]` `pillars` 的键是 `year/month/day/hour`（**不是** 年柱/月柱…），
    同时另给了一个按年→时排序的 `pillar_list`。两者都兼容。
    """
    ordered = b.get("pillar_list") or []
    if not ordered:
        pillars = b.get("pillars") or {}
        ordered = [pillars.get(k) for k in _PILLAR_KEYS]
    pairs = [
        f"{label}{gz}" for label, gz in zip(_PILLAR_LABELS, ordered) if gz
    ]
    return " ".join(pairs)


class TemplateProvider(BaseLLMProvider):
    """基于固定句式的确定性生成器。"""

    name = "template"
    capability = "template"
    requires_api_key = False
    default_model = "rule-template-v1"

    def is_available(self) -> bool:
        return True

    # ------------------------------------------------------------------

    def interpret(self, request: LLMRequest) -> LLMResponse:
        payload = request.payload or {}
        facts = payload.get("facts") or {}
        tradition = payload.get("tradition") or {}
        question = payload.get("question") or {}

        expert = (
            ReportSection("事实", self._facts_text(facts)),
            ReportSection("传统解释", self._tradition_text(facts, tradition)),
            ReportSection("针对问题", self._question_text(question)),
            ReportSection("参考建议", self._advice_text()),
        )
        # 白话文体不是可选项：不配 key 的用户走的就是本 provider，
        # 少了它，双文体这个能力在零成本路径上等于不存在（界面会一直显示
        # "本篇没有白话版"）。故两条路径都产出完整的两份。
        plain = (
            ReportSection("事实", self._facts_plain(facts)),
            ReportSection("传统解释", self._tradition_plain(tradition)),
            ReportSection("针对问题", self._question_plain(question)),
            ReportSection("参考建议", self._advice_plain()),
        )

        text = (
            f"【{REGISTER_EXPERT}】\n{_join(expert)}"
            f"\n\n【{REGISTER_PLAIN}】\n{_join(plain)}"
        )

        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.default_model,
            attempts=(
                Attempt(
                    provider=self.name, model=self.default_model, ok=True,
                    detail="本地规则模板生成，未联网、未调用任何模型", elapsed_ms=0,
                ),
            ),
            usage=None,
            degraded=False,
            warnings=(
                "本报告由本地规则模板生成（未调用大模型）：数值全部来自确定性计算，"
                "但措辞固定、不针对个人处境展开",
            ),
        )

    # ---------------- 事实 ----------------

    def _facts_text(self, facts: dict[str, Any]) -> str:
        if not facts:
            return "本次会话尚未产生任何确定性计算结果。"

        blocks: list[str] = []
        if "compass" in facts:
            blocks.append(self._compass_facts(facts["compass"]))
        if "bazi" in facts:
            blocks.append(self._bazi_facts(facts["bazi"]))
        if "liuyao" in facts:
            blocks.append(self._liuyao_facts(facts["liuyao"]))
        if "qian" in facts:
            blocks.append(self._qian_facts(facts["qian"]))
        if "name" in facts:
            blocks.append(self._name_facts(facts["name"]))
        return "\n".join(b for b in blocks if b)

    @staticmethod
    def _compass_facts(c: dict[str, Any]) -> str:
        lines = [f"坐山：{c.get('sitting', '—')}；向山：{c.get('facing', '—')}（{c.get('pair', '')}）"]
        if "sitting_degree" in c:
            lines.append(
                f"山心角度：坐 {_fmt(c['sitting_degree'])}°／向 {_fmt(c.get('facing_degree', 0))}°"
            )
        if "exact_degree" in c:
            lines.append(
                f"实测朝向：{_fmt(c['exact_degree'])}°"
                f"（偏离坐山山心 {_fmt(c.get('offset_from_center', 0))}°）"
            )
        fen = c.get("fenjin")
        if isinstance(fen, dict):
            ganzhi = fen.get("ganzhi")
            where = f"第 {fen.get('index')} 格之第 {fen.get('sub_index')} 位"
            # 规则表未提供时 ganzhi 为 None —— 只报几何格位，不编造干支
            lines.append(f"分金：{where}，{ganzhi}" if ganzhi else f"分金：{where}（干支规则表未提供）")
        lines.append(
            f"识别来源：{c.get('source', '—')}；置信度 {_fmt(c.get('confidence', 0))}"
            f"{'；已经用户确认' if c.get('confirmed_by_user') else '；尚未经用户确认'}"
        )
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _bazi_facts(b: dict[str, Any]) -> str:
        lines = [
            f"四柱：{_render_pillars(b) or '—'}",
            f"日主：{b.get('day_master', '—')}（{b.get('day_element', '—')}）"
            f"，生于{b.get('solar_term', '—')}后",
        ]

        simple = b.get("five_elements_simple") or {}
        counts_text = _render_element_counts(simple)
        if counts_text:
            lines.append(f"五行分布（只计明现）：{counts_text}")
            extra: list[str] = []
            if simple.get("strongest"):
                extra.append(f"最旺 {simple['strongest']}")
            if simple.get("weakest"):
                extra.append(f"最弱 {simple['weakest']}")
            missing = simple.get("missing") or []
            if missing:
                extra.append("明现缺 " + "、".join(str(x) for x in missing))
            if extra:
                lines.append("／".join(extra))

        if b.get("shengxiao"):
            lines.append(f"生肖：{b['shengxiao']}；农历：{b.get('lunar', '—')}")
        if b.get("nayin"):
            nayin = b["nayin"]
            if isinstance(nayin, dict):
                lines.append("纳音：" + "、".join(f"{k}{v}" for k, v in nayin.items()))
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _liuyao_facts(l: dict[str, Any]) -> str:
        lines = [
            f"起卦方式：{l.get('method', '—')}",
            f"本卦：{l.get('original_gua', '—')}"
            f"（上{l.get('upper_gua', '—')}／下{l.get('lower_gua', '—')}）",
        ]
        if l.get("changed_gua"):
            lines.append(f"变卦：{l['changed_gua']}")
        moving = l.get("moving_positions") or []
        lines.append(f"动爻：{'、'.join(str(x) for x in moving) if moving else '无'}")
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _qian_facts(q: dict[str, Any]) -> str:
        lines = [f"签库：{q.get('set_name', '—')}", f"第 {q.get('number', '—')} 签：{q.get('title', '—')}"]
        if q.get("level"):
            lines.append(f"签等：{q['level']}")
        poem = q.get("poem") or []
        if poem:
            lines.append("签诗：" + "／".join(str(x) for x in poem))
        if q.get("is_demo_data"):
            lines.append("⚠ 当前为演示签库，非传世签文")
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _name_facts(n: dict[str, Any]) -> str:
        wuge = n.get("wuge") or {}
        lines = [f"姓名：{n.get('name', '—')}（姓 {n.get('surname', '—')}／名 {n.get('given', '—')}）"]
        if wuge:
            lines.append("五格：" + "、".join(f"{k}{v}" for k, v in wuge.items()))
        return "· " + "\n· ".join(lines)

    # ---------------- 传统解释 ----------------

    def _tradition_text(self, facts: dict[str, Any], tradition: dict[str, Any]) -> str:
        if not tradition:
            return "本次会话没有可引用的传统规则派生结果。"

        blocks: list[str] = []
        c = tradition.get("compass")
        if isinstance(c, dict):
            s = c.get("sitting") or {}
            blocks.append(
                f"坐山 {s.get('name', '—')} 属{s.get('element', '—')}，"
                f"{s.get('yin_yang', '—')}山，三元为{s.get('sanyuan', '—')}龙，卦属{s.get('gua', '—')}。"
                + (f" {c['note']}" if c.get("note") else "")
            )

        b = tradition.get("bazi")
        if isinstance(b, dict):
            if b.get("summary"):
                blocks.append(str(b["summary"]))
            if b.get("note"):
                blocks.append(str(b["note"]))

        ly = tradition.get("liuyao")
        if isinstance(ly, dict):
            blocks.append(
                f"体卦 {ly.get('body_gua', '—')}（{ly.get('lower_gua_element', '—')}），"
                f"用卦 {ly.get('use_gua', '—')}（{ly.get('upper_gua_element', '—')}）。"
                + (f" {ly['note']}" if ly.get("note") else "")
            )

        q = tradition.get("qian")
        if isinstance(q, dict):
            if q.get("interpretation"):
                blocks.append(f"签解：{q['interpretation']}")
            if q.get("advice"):
                blocks.append(f"签示：{q['advice']}")

        nm = tradition.get("name")
        if isinstance(nm, dict):
            luck = nm.get("number_luck") or {}
            if luck:
                blocks.append(
                    "数理：" + "、".join(f"{k}{v}" for k, v in luck.items())
                )
            if nm.get("note"):
                blocks.append(str(nm["note"]))

        body = "\n".join(blocks) or "没有可用的传统规则派生结果。"
        return body + "\n\n（以上为传统术数的通常说法，属于文化传统而非科学结论。）"

    # ---------------- 针对问题 / 建议 ----------------

    @staticmethod
    def _question_text(question: dict[str, Any]) -> str:
        category = str(question.get("category") or "其他")
        asked = str(question.get("text") or "").strip()
        angle = _CATEGORY_ANGLE.get(category, _CATEGORY_ANGLE["其他"])

        head = f"你所问为「{asked}」" if asked else f"你没有指定具体问题（类别：{category}）"
        return (
            f"{head}。就本类别而言，传统术数{angle}。\n\n"
            "由于本报告未调用大模型，这里不对你的具体处境作展开推演 —— "
            "上方的计算事实与传统解释是全部依据，请自行对照参考。"
        )

    @staticmethod
    def _advice_text() -> str:
        return (
            "· 把结果当作一面镜子：用于自查与换位思考，而不是当作预测。\n"
            "· 优先处理确定性事：作息、节奏、沟通方式，这些不依赖任何术数结论。\n"
            "· 重大决定请咨询对应领域的专业人士，并以你自己的判断为准。\n"
            "· 若对识别结果或排盘有疑问，可回到结果确认页手动修正后重新生成。"
        )

    # ==================================================================
    # 白话文体
    # ==================================================================
    #
    # 与专业版讲的是**同一批数据、同一个结论**，只是换成人话：
    #   · 结构化数值 → 用日常词重讲一遍（模板 provider 能忠实做到）
    #   · 自由文本（核心给的 summary / note / 签解）→ 照录 + 说明是照录
    #        （转述才可能走样，而走样在这里等于编造，见 RULE-008）
    #   · 不新增任何判断，也不替用户分析他的处境 —— 那超出"复述"的范围

    def _facts_plain(self, facts: dict[str, Any]) -> str:
        if not facts:
            return "这次还没有任何算出来的结果。"
        blocks: list[str] = []
        if "compass" in facts:
            blocks.append(self._compass_facts_plain(facts["compass"]))
        if "bazi" in facts:
            blocks.append(self._bazi_facts_plain(facts["bazi"]))
        if "liuyao" in facts:
            blocks.append(self._liuyao_facts_plain(facts["liuyao"]))
        if "qian" in facts:
            blocks.append(self._qian_facts_plain(facts["qian"]))
        if "name" in facts:
            blocks.append(self._name_facts_plain(facts["name"]))
        return "\n".join(b for b in blocks if b)

    @staticmethod
    def _compass_facts_plain(c: dict[str, Any]) -> str:
        lines = [
            f"你测出来的坐向是「坐 {c.get('sitting', '—')}、向 {c.get('facing', '—')}」。",
            "「坐」指你背面朝着哪个方向，「向」指你正面朝着哪个方向，两者正好相反。",
        ]
        if "exact_degree" in c:
            lines.append(
                f"另外还记了一个更精确的角度：{_fmt(c['exact_degree'])}°。"
                "罗盘一整圈是 360°，这个数字就是从正北开始量出来的度数。"
            )
        lines.append(
            "这个结果是你看过并确认过的。"
            if c.get("confirmed_by_user")
            else "注意：这个结果是机器算出来的，还没有经过你本人确认。"
        )
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _bazi_facts_plain(b: dict[str, Any]) -> str:
        lines = [f"你的生辰排出来是：{_render_pillars(b) or '—'}。"]
        lines.append(
            "这是把出生的年、月、日、时各用两个字表示，一共八个字，所以也叫「八字」。"
        )

        simple = b.get("five_elements_simple") or {}
        counts_text = _render_element_counts(simple)
        if counts_text:
            lines.append(
                f"把这八个字按五行（木火土金水）分分类，只数看得见的，结果是：{counts_text}。"
            )
        if b.get("shengxiao"):
            lines.append(f"属相是{b['shengxiao']}。")
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _liuyao_facts_plain(l: dict[str, Any]) -> str:
        lines = [
            f"这一卦是「{l.get('original_gua', '—')}」，由上下两部分组成，"
            f"上面是{l.get('upper_gua', '—')}，下面是{l.get('lower_gua', '—')}。",
        ]
        if l.get("changed_gua"):
            lines.append(f"其中有的位置发生了变动，变过之后成了「{l['changed_gua']}」。")
        moving = l.get("moving_positions") or []
        lines.append(
            f"发生变动的是第 {'、'.join(str(x) for x in moving)} 位。"
            if moving
            else "这一卦没有任何位置发生变动。"
        )
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _qian_facts_plain(q: dict[str, Any]) -> str:
        lines = [
            f"你抽到的是「{q.get('set_name', '—')}」里的第 {q.get('number', '—')} 签，"
            f"签题是「{q.get('title', '—')}」。"
        ]
        poem = q.get("poem") or []
        if poem:
            lines.append("签诗原文如下：" + "／".join(str(x) for x in poem))
        if q.get("is_demo_data"):
            lines.append("提醒：当前用的是演示签库，不是传世签文。")
        return "· " + "\n· ".join(lines)

    @staticmethod
    def _name_facts_plain(n: dict[str, Any]) -> str:
        wuge = n.get("wuge") or {}
        lines = [f"姓名：{n.get('name', '—')}（姓「{n.get('surname', '—')}」，名「{n.get('given', '—')}」）。"]
        if wuge:
            lines.append(
                "按笔画算出来的五格是："
                + "、".join(f"{k}{v}" for k, v in wuge.items())
                + "。五格是传统姓名学给姓名的笔画分组起的名字。"
            )
        return "· " + "\n· ".join(lines)

    def _tradition_plain(self, tradition: dict[str, Any]) -> str:
        if not tradition:
            return "这次没有可以引用的传统说法。"

        blocks = [
            "下面把那套传统说法用日常话讲一遍。"
        ]
        # 照录的原话先收集起来，末尾统一贴一次并配术语解释 ——
        # 逐条贴会出现"同一句解释重复三遍"，而重复会让人以为那三处在讲不同的事。
        quotes: list[str] = []

        c = tradition.get("compass")
        if isinstance(c, dict):
            s = c.get("sitting") or {}
            blocks.append(
                f"传统罗盘把一圈分成 24 份，每一份叫一个「山」，相当于给 24 个方向"
                f"各起了一个名字。你这处坐向落在「{s.get('name', '—')}」这个名字上。"
                f"按传统的分类，它属于{s.get('element', '—')}（五行里的一类），"
                f"阴阳上算{s.get('yin_yang', '—')}，三元里归{s.get('sanyuan', '—')}，"
                f"卦位是{s.get('gua', '—')}。这些只是传统对方向的分类叫法，本身不表示吉凶。"
            )
            if c.get("note"):
                quotes.append(str(c["note"]))

        b = tradition.get("bazi")
        if isinstance(b, dict):
            blocks.append(
                "关于生辰，传统会先定出「代表你自己」的那一项，再看它整体偏强还是偏弱，"
                "然后据此找出对你有帮助和不利的几类属性。"
            )
            for key in ("summary", "note"):
                if b.get(key):
                    quotes.append(str(b[key]))

        ly = tradition.get("liuyao")
        if isinstance(ly, dict):
            blocks.append(
                f"断卦时把卦分成两半看：下面那半叫「体卦」，代表你自己，是"
                f"{ly.get('body_gua', '—')}；上面那半叫「用卦」，代表事情，是"
                f"{ly.get('use_gua', '—')}。两边的关系是这类判断的入手处。"
            )
            if ly.get("note"):
                quotes.append(str(ly["note"]))

        q = tradition.get("qian")
        if isinstance(q, dict):
            blocks.append("签文本身是诗一样的句子，传统上由解签人来对应签意。")
            for key in ("interpretation", "advice"):
                if q.get(key):
                    quotes.append(str(q[key]))

        nm = tradition.get("name")
        if isinstance(nm, dict):
            luck = nm.get("number_luck") or {}
            if luck:
                blocks.append(
                    "按传统姓名学的说法，各格的数理吉凶是："
                    + "、".join(f"{k}{v}" for k, v in luck.items())
                    + "（这是传统说法，不是事实。）"
                )
            if nm.get("note"):
                quotes.append(str(nm["note"]))

        if quotes:
            body = "\n\n".join(quotes)
            explained = _explain_terms(body)
            block = f"{_QUOTE_LEAD}\n{body}"
            if explained:
                block += "\n\n" + explained
            blocks.append(block)

        blocks.append("以上都属于文化传统里的通常说法，不是科学结论。")
        return "\n\n".join(blocks)

    @staticmethod
    def _question_plain(question: dict[str, Any]) -> str:
        category = str(question.get("category") or "其他")
        asked = str(question.get("text") or "").strip()
        angle = _CATEGORY_ANGLE_PLAIN.get(category, _CATEGORY_ANGLE_PLAIN["其他"])

        head = (
            f"你问的是「{asked}」"
            if asked
            else f"你这次没有提出具体问题（归在「{category}」这一类）"
        )
        return (
            f"{head}。\n\n"
            f"这一类问题，传统的问法大致是：{angle}。\n\n"
            "这份报告没有调用大模型，所以不会针对你的具体情况往下推演。"
            "上面算出来的结果和那套传统说法就是全部依据，请自己对照着参考。"
        )

    @staticmethod
    def _advice_plain() -> str:
        return (
            "· 把结果当成一面镜子：用来反思、换个角度看自己，别当成预言。\n"
            "· 先做那些确定的事：作息、节奏、怎么跟人说话 —— 这些跟算不算命无关。\n"
            "· 大事请找对应领域的专业人士，最终拿主意的还是你自己。\n"
            "· 如果觉得方向测错了、或者盘排得不对，可以回去手动改好再重新生成一次。"
        )


__all__ = ["TemplateProvider"]
