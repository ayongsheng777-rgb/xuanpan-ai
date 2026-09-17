"""断卦层 —— 六爻 / 八字的专业分水岭。

此前内核停在「排盘 + 装卦」：六爻算出了用神 / 旺衰 / 生克冲合，八字判出了
日主旺衰与喜用神，但都**不下吉凶结论**（装卦层明确写「本层不含吉凶断语」）。
本模块补上这最后一环 —— 基于确定性 FACT 数据，产出**结构化的吉凶倾向**。

三条铁律（对齐 RULE-001 / RULE-002 / RULE-006）：

1. **只做组合判断，不越界造数据** —— 断卦的输入是装卦层 / 旺衰层已经算好的
   FACT（用神旺衰、世应、旬空、动爻、日辰关系），断卦只做「把这些事实综合成
   一个倾向」，绝不自行重算历法 / 卦序 / 旺衰。

2. **输出吉凶「倾向」而非「断语」** —— 用「偏吉 / 中平 / 偏凶」这类程度词，
   附上得出该倾向的**具体依据**（用神旺相且得日生 → 偏吉），而非
   「大吉大利」「必有凶灾」这种绝对化、无依据的断语。

3. **每个倾向都显式标注流派不确定性** —— 六爻断卦有多种流派（用神取用、
   旺衰权重、世应主客），八字有扶抑 / 调候 / 通关等多种取用体系。凡属流派
   相关的判断，一律标 `school` 字段并附不确定性说明，不冒充唯一结论。

断卦结果供 AI 层进一步解释，但倾向本身由代码确定，AI 不得改写。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .bazi.chart import BaziChart
from .liuyao.zhuang import LiuYaoDivination, YaoDetail

# 吉凶倾向三档（程度词，非绝对断语）
VERDICT_FAVORABLE = "偏吉"
VERDICT_NEUTRAL = "中平"
VERDICT_UNFAVORABLE = "偏凶"

# 月令旺衰 → 有力/无力（断卦用）
_STRONG_STATES = {"旺", "相"}
_WEAK_STATES = {"休", "囚", "死"}

# 日辰关系 → 对用神是扶是克
_FAVORABLE_DAY = {"临日", "日生", "日合"}
_UNFAVORABLE_DAY = {"日克", "爻生日"}


@dataclass(frozen=True, slots=True)
class LiuYaoDuan:
    """六爻断卦结果。"""

    verdict: str                      # 偏吉 / 中平 / 偏凶
    reasons: tuple[str, ...]          # 得出倾向的具体依据（可读）
    yongshen: str | None
    yongshen_states: tuple[str, ...]  # 用神各爻的旺衰
    shi_yao_state: str                # 世爻旺衰
    uncertainties: tuple[str, ...]    # 流派不确定性标注
    school: str = "通行旺衰断法"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "reasons": list(self.reasons),
            "yongshen": self.yongshen,
            "yongshen_states": list(self.yongshen_states),
            "shi_yao_state": self.shi_yao_state,
            "school": self.school,
            "uncertainties": list(self.uncertainties),
        }


@dataclass(frozen=True, slots=True)
class BaziDuan:
    """八字断卦结果（日主旺衰 + 喜用 + 运程倾向）。"""

    verdict: str                      # 身强 / 身弱（复用旺衰层）
    favorable: tuple[str, ...]        # 喜用神
    unfavorable: tuple[str, ...]      # 忌神
    da_yun_verdicts: dict[str, str]   # 各步大运干支 → 吉凶倾向
    reasons: tuple[str, ...]
    uncertainties: tuple[str, ...]
    school: str = "扶抑法"

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "favorable": list(self.favorable),
            "unfavorable": list(self.unfavorable),
            "da_yun_verdicts": dict(self.da_yun_verdicts),
            "reasons": list(self.reasons),
            "school": self.school,
            "uncertainties": list(self.uncertainties),
        }


def _state_of(yao: YaoDetail) -> str:
    """单爻旺衰综合（月令为主、日辰为辅）。"""
    return yao.month_state


def duan_liuyao(divination: LiuYaoDivination) -> LiuYaoDuan:
    """六爻断卦：综合用神旺衰 / 世应 / 旬空 / 动爻，给出吉凶倾向。

    判断规则（全部基于装卦层的确定性 FACT，只做组合）：
    - 用神旺相（月令旺/相）→ 有力，偏吉倾向
    - 用神休囚死（月令休/囚/死）→ 无力，偏凶倾向
    - 用神旬空 → 用神暂无力（待出空），倾向降档
    - 用神动爻 → 用神有力，倾向升档
    - 用神得日辰生/临/合 → 加吉；被日克 → 减吉
    - 世爻旺衰 → 自身状态参照

    这些规则是「通行旺衰断法」的概括，属流派相关，故全部进 uncertainties 标注。
    """
    reasons: list[str] = []
    uncertainties = [
        "用神取用与旺衰权重属流派规则，本版采用通行旺衰断法",
        "「用神多现取谁」「用神不上卦取伏神」等细则未纳入，倾向仅供参照",
        "吉凶为「倾向」而非定论，须结合具体问题与世应主客综合判断",
    ]

    yongshen_yao = divination.yongshen_yao
    shi = divination.shi_yao

    if not divination.yongshen or not yongshen_yao:
        # 用神不上卦（伏神）：倾向偏中性，标注「用神不上卦，以伏神论，断法不一」
        return LiuYaoDuan(
            verdict=VERDICT_NEUTRAL,
            reasons=("用神不上卦（伏神），旺衰难以直接判断",),
            yongshen=divination.yongshen,
            yongshen_states=(),
            shi_yao_state=shi.month_state,
            uncertainties=uncertainties + ["用神不上卦时以伏神论，不同流派断法不一"],
        )

    states = tuple(_state_of(y) for y in yongshen_yao)
    reasons.append(f"用神「{divination.yongshen}」现于第{divination.yongshen_yao[0].position}爻，月令旺衰：{'、'.join(states)}")

    # 用神旺衰主体判断（取最强的一爻状态）
    strong = any(s in _STRONG_STATES for s in states)
    weak = all(s in _WEAK_STATES for s in states)

    # 逐爻细化：旬空 / 动爻 / 日辰关系
    any_kong = any(y.is_kong for y in yongshen_yao)
    any_moving = any(y.is_moving for y in yongshen_yao)
    day_relations = {y.day_relation for y in yongshen_yao}
    day_favor = bool(day_relations & _FAVORABLE_DAY)
    day_against = bool(day_relations & _UNFAVORABLE_DAY)

    if any_kong:
        reasons.append("用神旬空：用神暂无力，待出空方显")
    if any_moving:
        reasons.append("用神动爻：用神发动，有力")
    if day_favor:
        reasons.append(f"用神得日辰{'/'.join(sorted(day_relations & _FAVORABLE_DAY))}，得日辰扶助")
    if day_against:
        reasons.append(f"用神受日辰{'/'.join(sorted(day_relations & _UNFAVORABLE_DAY))}，减力")

    # 综合判定倾向
    score = 0
    if strong:
        score += 2
    elif weak:
        score -= 2
    if any_kong:
        score -= 1
    if any_moving:
        score += 1
    if day_favor:
        score += 1
    if day_against:
        score -= 1

    if score >= 2:
        verdict = VERDICT_FAVORABLE
    elif score <= -2:
        verdict = VERDICT_UNFAVORABLE
    else:
        verdict = VERDICT_NEUTRAL

    reasons.append(f"综合（旺衰 + 旬空 + 动爻 + 日辰）判为：{verdict}")

    return LiuYaoDuan(
        verdict=verdict,
        reasons=tuple(reasons),
        yongshen=divination.yongshen,
        yongshen_states=states,
        shi_yao_state=shi.month_state,
        uncertainties=tuple(uncertainties),
    )


def duan_bazi(chart: BaziChart) -> BaziDuan:
    """八字断卦：复用旺衰层的日主旺衰 / 喜用神，给大运流年吉凶倾向。

    判断规则（基于旺衰层的确定性结果）：
    - 大运干支五行若属喜用神 → 该步运偏吉
    - 大运干支五行若属忌神 → 该步运偏凶
    - 混合（一喜一忌）→ 中平

    这是扶抑法（抑强扶弱）的概括，属流派相关，进 uncertainties 标注。
    """
    from .constants import ELEMENT_CN, GAN_ELEMENT, ZHI_ELEMENT

    strength = chart.strength
    # strength.favorable/unfavorable 存英文元素键，转中文与 reasons 保持一致
    favorable = tuple(ELEMENT_CN[e] for e in strength.favorable)
    unfavorable = tuple(ELEMENT_CN[e] for e in strength.unfavorable)
    favorable_keys = set(strength.favorable)
    unfavorable_keys = set(strength.unfavorable)

    reasons: list[str] = []
    reasons.append(
        f"日主{chart.day_master}（{ELEMENT_CN[chart.day_element]}），{strength.verdict}；"
        f"喜用 {''.join(favorable)}，忌神 {''.join(unfavorable)}"
    )

    # 大运吉凶倾向
    da_yun_verdicts: dict[str, str] = {}
    yun = chart.to_facts().get("da_yun", {})
    if yun.get("available"):
        for step in yun.get("da_yun", []):
            gz = step.get("gan_zhi", "")
            if not gz or len(gz) < 2:
                continue  # 起运前空档
            gan_el = GAN_ELEMENT.get(gz[0])
            zhi_el = ZHI_ELEMENT.get(gz[1])
            els = {e for e in (gan_el, zhi_el) if e}
            favor = els & favorable_keys
            unfavor = els & unfavorable_keys
            if favor and not unfavor:
                v = VERDICT_FAVORABLE
            elif unfavor and not favor:
                v = VERDICT_UNFAVORABLE
            else:
                v = VERDICT_NEUTRAL
            da_yun_verdicts[gz] = v

    if da_yun_verdicts:
        reasons.append(
            f"大运倾向（按喜用/忌神五行）："
            + "；".join(f"{gz}{v}" for gz, v in list(da_yun_verdicts.items())[:5])
            + ("…" if len(da_yun_verdicts) > 5 else "")
        )

    uncertainties = [
        "取用神体系（扶抑/调候/通关/病药）属流派规则，本版采用扶抑法",
        "大运吉凶只看干支五行是否属喜忌，未纳入刑冲合会等复杂关系",
        "吉凶为「倾向」而非定论，须结合流年与大运刑冲合会综合判断",
    ]

    return BaziDuan(
        verdict=strength.verdict,
        favorable=favorable,
        unfavorable=unfavorable,
        da_yun_verdicts=da_yun_verdicts,
        reasons=tuple(reasons),
        uncertainties=tuple(uncertainties),
    )


__all__ = [
    "LiuYaoDuan", "BaziDuan", "duan_liuyao", "duan_bazi",
    "VERDICT_FAVORABLE", "VERDICT_NEUTRAL", "VERDICT_UNFAVORABLE",
]
