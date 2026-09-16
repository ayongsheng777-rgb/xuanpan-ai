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

from ..models import Attempt, LLMRequest, LLMResponse, ReportSection
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

        sections = (
            ReportSection("事实", self._facts_text(facts)),
            ReportSection("传统解释", self._tradition_text(facts, tradition)),
            ReportSection("针对问题", self._question_text(question)),
            ReportSection("参考建议", self._advice_text()),
        )
        text = "\n\n".join(f"【{s.title}】\n{s.body}" for s in sections)

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


__all__ = ["TemplateProvider"]
