"""六爻装卦 —— 把「起卦结果 + 日辰月建」装配成完整卦盘。

装卦（又称「装卦」/「排盘」）是六爻预测的核心工序：
拿到一个卦，还需要补上 **纳甲、六亲、世应、六神、伏神、旬空、月建日辰旺衰**，
才具备断卦的条件。本模块负责这一层。

⚠️ 分层原则（RULE-002 / RULE-006）：
- **FACT 层**：纳甲、六亲、世应、六神、旬空、旺衰 —— 确定性推导，AI 不可改
- **TRADITION 层**：用神取用、卦身、六冲六合吉凶倾向 —— 流派相关，全部显式标注

本模块**不输出吉凶断语**。断语由调用方（AI 层）依据 FACT/TRADITION 生成，
且必须受 RULE-010 约束（不得伪装成确定性结论）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..constants import (
    ELEMENT_CN,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GAN_ELEMENT,
    ZHI_ELEMENT,
    jiazi_index,
)
from ..exceptions import InvalidInputError
from .gua import YAO_IS_MOVING, YAO_IS_YANG, LiuYaoResult
from .najia import (
    GUA_PALACE,
    PALACE_STAGE,
    liu_qin,
    liu_shen_for_day,
    najia_of,
    palace_of,
    shi_ying_of,
    zhi_chong,
    zhi_liuhe,
)

# --------------------------------------------------------------------------
# 用神取用表 —— 流派相关（RULE-006），显式集中
# --------------------------------------------------------------------------
# 六爻占断第一件事是「取用神」：问什么事，就看代表那件事的六亲。
# 通行取用：
#   妻财 = 钱财、货物、妻子（男占）、失物
#   官鬼 = 官职、功名、丈夫（女占）、疾病、盗贼、官司对方
#   父母 = 长辈、房产、车船、文书、学业、考试
#   子孙 = 子女、下属、福神、解忧之神、医生
#   兄弟 = 兄弟、朋友、合伙人、竞争者、劫财

YONGSHEN_BY_TOPIC: dict[str, str] = {
    "财运": "妻财", "求财": "妻财", "生意": "妻财", "货物": "妻财", "失物": "妻财",
    "事业": "官鬼", "官运": "官鬼", "功名": "官鬼", "工作": "官鬼", "升迁": "官鬼",
    "疾病": "官鬼", "官司": "官鬼", "诉讼": "官鬼", "盗贼": "官鬼",
    "父母": "父母", "长辈": "父母", "房产": "父母", "车船": "父母",
    "学业": "父母", "考试": "父母", "文书": "父母", "出行": "父母",
    "子女": "子孙", "子嗣": "子孙", "下属": "子孙", "生育": "子孙",
    "兄弟": "兄弟", "朋友": "兄弟", "合伙": "兄弟", "竞争": "兄弟",
    # ---- 接缝：全项目问题类别 ↔ 用神表 ----
    # `context.QUESTION_CATEGORIES`（App 里用户能选的 8 个类别）用的是
    # 「健康」「人际」，而上面的通行措辞是「疾病」「朋友」。两者若不接上，
    # 用户在 App 选「健康」时 `yongshen_of` 返回 None，断卦会走
    # 「用神不上卦」分支给出「中平」—— 看起来是个正常结论，实际是**根本没取用神**。
    # 这类静默降级比报错危险得多，所以在此显式补两条映射（依据同属通行取用法）。
    "健康": "官鬼", "人际": "兄弟",
}

# 婚姻取用看性别：男占妻看妻财，女占夫看官鬼
MARRIAGE_YONGSHEN: dict[str, str] = {"male": "妻财", "female": "官鬼"}

YONGSHEN_NOTE = (
    "用神取用属流派规则：本表采用通行取用法，不同流派对同一占问可能取不同六亲；"
    "此外尚有「用神多现取谁」「用神不上卦取伏神」等细则，本版未纳入"
)


def yongshen_of(topic: str, gender: str | None = None) -> str | None:
    """按占问类别取用神六亲。婚姻需传 gender。

    >>> yongshen_of("财运")
    '妻财'
    >>> yongshen_of("婚姻", "male")
    '妻财'
    >>> yongshen_of("婚姻", "female")
    '官鬼'
    >>> yongshen_of("未知事项") is None
    True
    """
    if topic in ("婚姻", "感情", "婚恋"):
        if gender in MARRIAGE_YONGSHEN:
            return MARRIAGE_YONGSHEN[gender]
        return None
    return YONGSHEN_BY_TOPIC.get(topic)


# --------------------------------------------------------------------------
# 旬空
# --------------------------------------------------------------------------


def xun_kong_of(day_ganzhi: str) -> tuple[str, ...]:
    """由日柱干支推出旬空（空亡）地支，两枚。

    六十甲子分六旬，每旬十日、配十二支，故每旬必缺两支，即为「旬空」。
    甲子旬空戌亥、甲戌旬空申酉、甲申旬空午未、甲午旬空辰巳、甲辰旬空寅卯、甲寅旬空子丑。

    >>> xun_kong_of("甲子")
    ('戌', '亥')
    >>> xun_kong_of("庚午")
    ('戌', '亥')
    >>> xun_kong_of("甲寅")
    ('子', '丑')
    """
    from ..constants import DIZHI

    idx = jiazi_index(day_ganzhi)
    xun_head = (idx // 10) * 10
    zhi_start = xun_head % 12
    return (DIZHI[(zhi_start + 10) % 12], DIZHI[(zhi_start + 11) % 12])


# --------------------------------------------------------------------------
# 月建旺衰（旺相休囚死）
# --------------------------------------------------------------------------

_MONTH_STATE_NOTE = (
    "旺相休囚死为通行月令旺衰法：同令者旺、令生者相、我生令者休、我克令者囚、令克我者死"
)


def month_state_of(yao_element: str, month_zhi: str) -> str:
    """某爻五行在月建下的旺衰（旺/相/休/囚/死）。

    >>> month_state_of("metal", "酉")   # 金爻逢金月 → 旺
    '旺'
    >>> month_state_of("water", "酉")   # 金生水 → 相
    '相'
    >>> month_state_of("fire", "酉")    # 火克金 → 囚
    '囚'
    >>> month_state_of("wood", "酉")    # 金克木 → 死
    '死'
    """
    if month_zhi not in ZHI_ELEMENT:
        raise InvalidInputError(f"非法月支：{month_zhi!r}")
    month_el = ZHI_ELEMENT[month_zhi]
    if yao_element == month_el:
        return "旺"
    if ELEMENT_GENERATES[month_el] == yao_element:
        return "相"
    if ELEMENT_GENERATES[yao_element] == month_el:
        return "休"
    if ELEMENT_CONTROLS[yao_element] == month_el:
        return "囚"
    return "死"


def day_relation_of(yao_zhi: str, day_zhi: str) -> tuple[str, str]:
    """某爻地支与日辰的关系 → (关系名, 说明)。

    日辰为一卦之主宰，能生、能克、能冲、能合。日冲旺相之爻为**暗动**，
    日冲休囚之爻为**日破**（此处只如实给出关系，不替断卦下结论）。

    >>> day_relation_of("子", "午")   # 日冲
    ('日冲', '日辰冲爻：旺相为暗动，休囚为日破')
    >>> day_relation_of("子", "丑")   # 日合
    ('日合', '日辰六合此爻')
    >>> day_relation_of("子", "子")
    ('临日', '爻与日辰同支，得日辰之力')
    """
    if yao_zhi not in ZHI_ELEMENT or day_zhi not in ZHI_ELEMENT:
        raise InvalidInputError(f"非法地支：{yao_zhi!r} / {day_zhi!r}")
    if yao_zhi == day_zhi:
        return "临日", "爻与日辰同支，得日辰之力"
    if zhi_chong(yao_zhi) == day_zhi:
        return "日冲", "日辰冲爻：旺相为暗动，休囚为日破"
    if zhi_liuhe(yao_zhi) == day_zhi:
        return "日合", "日辰六合此爻"

    y_el, d_el = ZHI_ELEMENT[yao_zhi], ZHI_ELEMENT[day_zhi]
    if ELEMENT_GENERATES[d_el] == y_el:
        return "日生", "日辰生此爻"
    if ELEMENT_CONTROLS[d_el] == y_el:
        return "日克", "日辰克此爻"
    if ELEMENT_GENERATES[y_el] == d_el:
        return "爻生日", "此爻生日辰（泄气）"
    if ELEMENT_CONTROLS[y_el] == d_el:
        return "爻克日", "此爻克日辰（耗力）"
    return "比和", "爻与日辰五行相同"  # pragma: no cover - 五行关系全覆盖


# --------------------------------------------------------------------------
# 爻与卦盘
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class YaoDetail:
    """一爻的完整装卦信息。"""

    position: int              # 爻位 1..6，自下而上
    yin_yang: int              # 1=阳爻(—)  0=阴爻(--)
    gan: str
    zhi: str
    gan_element: str           # 天干五行英文键
    zhi_element: str           # 地支五行英文键
    liu_qin: str               # 六亲
    liu_shen: str              # 六神
    is_shi: bool               # 是否世爻
    is_ying: bool              # 是否应爻
    is_moving: bool            # 是否动爻
    is_kong: bool              # 是否旬空
    month_state: str           # 月建旺衰
    day_relation: str          # 日辰关系
    day_relation_note: str
    fushen_qin: str | None = None   # 伏神六亲（本卦缺此六亲时有值）
    fushen_ganzhi: str | None = None
    fushen_note: str | None = None

    @property
    def ganzhi(self) -> str:
        return self.gan + self.zhi

    @property
    def yao_symbol(self) -> str:
        return "▅▅▅▅▅" if self.yin_yang else "▅▅　▅▅"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "position": self.position,
            "yin_yang": "阳" if self.yin_yang else "阴",
            "ganzhi": self.ganzhi,
            "gan_element": ELEMENT_CN[self.gan_element],
            "zhi_element": ELEMENT_CN[self.zhi_element],
            "liu_qin": self.liu_qin,
            "liu_shen": self.liu_shen,
            "is_shi": self.is_shi,
            "is_ying": self.is_ying,
            "is_moving": self.is_moving,
            "is_kong": self.is_kong,
            "month_state": self.month_state,
            "day_relation": self.day_relation,
            "day_relation_note": self.day_relation_note,
        }
        if self.fushen_qin:
            d["fushen"] = {
                "liu_qin": self.fushen_qin,
                "ganzhi": self.fushen_ganzhi,
                "note": self.fushen_note,
            }
        return d


@dataclass(frozen=True, slots=True)
class LiuYaoDivination:
    """完整卦盘 —— 起卦 + 装卦的聚合结果。"""

    result: LiuYaoResult
    day_pillar: str                       # 日柱干支
    month_pillar: str | None              # 月柱干支
    day_gan: str
    day_zhi: str
    month_zhi: str | None
    palace: str                           # 本卦所属宫
    palace_element: str
    palace_stage: str                     # 本宫/一世/…/游魂/归魂
    shi_position: int
    ying_position: int
    yao_details: tuple[YaoDetail, ...]    # 6 爻，自下而上
    changed_yao_details: tuple[YaoDetail, ...] | None
    xun_kong: tuple[str, ...]             # 旬空地支
    gua_features: tuple[str, ...]         # 六冲/六合 等卦性
    topic: str | None = None
    yongshen: str | None = None

    # ---------------- 便捷属性 ----------------

    @property
    def yongshen_yao(self) -> tuple[YaoDetail, ...]:
        """用神所临之爻（可能多现）。"""
        if not self.yongshen:
            return ()
        return tuple(y for y in self.yao_details if y.liu_qin == self.yongshen)

    @property
    def shi_yao(self) -> YaoDetail:
        return self.yao_details[self.shi_position - 1]

    @property
    def ying_yao(self) -> YaoDetail:
        return self.yao_details[self.ying_position - 1]

    @property
    def missing_qin(self) -> tuple[str, ...]:
        """本卦未上卦的六亲（需借伏神）。"""
        present = {y.liu_qin for y in self.yao_details}
        return tuple(q for q in ("父母", "兄弟", "子孙", "妻财", "官鬼") if q not in present)

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：装卦的确定性结果。"""
        return {
            "gua": self.result.to_facts(),
            "day_pillar": self.day_pillar,
            "month_pillar": self.month_pillar,
            "palace": self.palace,
            "palace_element": ELEMENT_CN[self.palace_element],
            "palace_stage": self.palace_stage,
            "shi_position": self.shi_position,
            "ying_position": self.ying_position,
            "xun_kong": list(self.xun_kong),
            "yao_details": [y.to_dict() for y in self.yao_details],
            "changed_yao_details": (
                [y.to_dict() for y in self.changed_yao_details]
                if self.changed_yao_details else None
            ),
            "gua_features": list(self.gua_features),
            "missing_qin": list(self.missing_qin),
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：流派相关的取用与卦性倾向（不含具体吉凶断语）。"""
        return {
            "topic": self.topic,
            "yongshen": self.yongshen,
            "yongshen_positions": [y.position for y in self.yongshen_yao],
            "yongshen_note": YONGSHEN_NOTE,
            "month_state_note": _MONTH_STATE_NOTE,
            "gua_features": list(self.gua_features),
            "note": "本层不含吉凶断语；断卦须结合用神旺衰、生克冲合综合判断，属流派规则",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}


# --------------------------------------------------------------------------
# 装卦主流程
# --------------------------------------------------------------------------


def najia_ganzhi_for(lower: str, upper: str) -> list[str]:
    """按内外卦取 6 爻纳甲干支（自下而上）。

    >>> najia_ganzhi_for("乾", "乾")
    ['甲子', '甲寅', '甲辰', '壬午', '壬申', '壬戌']
    >>> najia_ganzhi_for("坤", "乾")
    ['乙未', '乙巳', '乙卯', '壬午', '壬申', '壬戌']
    """
    inner = najia_of(lower)[0]
    outer = najia_of(upper)[1]
    return list(inner) + list(outer)


def _build_yao_details(
    *,
    yang: tuple[int, ...],
    lower: str,
    upper: str,
    palace: str,
    day_gan: str,
    day_zhi: str,
    month_zhi: str | None,
    shi_pos: int,
    ying_pos: int,
    moving: tuple[int, ...],
    kong: tuple[str, ...],
    fushen_map: dict[int, tuple[str, str]],
) -> tuple[YaoDetail, ...]:
    ganzhi_list = najia_ganzhi_for(lower, upper)
    liu_shen = liu_shen_for_day(day_gan)

    out: list[YaoDetail] = []
    for i in range(6):
        gz = ganzhi_list[i]
        gan, zhi = gz[0], gz[1]
        zhi_el = ZHI_ELEMENT[zhi]
        rel, rel_note = day_relation_of(zhi, day_zhi)

        fx = fushen_map.get(i + 1)
        out.append(YaoDetail(
            position=i + 1,
            yin_yang=yang[i],
            gan=gan,
            zhi=zhi,
            gan_element=GAN_ELEMENT[gan],
            zhi_element=zhi_el,
            liu_qin=liu_qin(palace, zhi_el),
            liu_shen=liu_shen[i],
            is_shi=(i + 1 == shi_pos),
            is_ying=(i + 1 == ying_pos),
            is_moving=(i + 1) in moving,
            is_kong=zhi in kong,
            month_state=month_state_of(zhi_el, month_zhi) if month_zhi else "—",
            day_relation=rel,
            day_relation_note=rel_note,
            fushen_qin=fx[0] if fx else None,
            fushen_ganzhi=fx[1] if fx else None,
            fushen_note=(
                "本卦此六亲未上卦，自本宫首卦同位借入伏神" if fx else None
            ),
        ))
    return tuple(out)


# 六亲全集（用于判定某卦是否「六亲不全」，需借伏神）
ALL_QIN: tuple[str, ...] = ("父母", "兄弟", "子孙", "妻财", "官鬼")


def _fushen_map(lower: str, upper: str, palace: str) -> dict[int, tuple[str, str]]:
    """伏神表：本卦若缺某六亲，从**本宫首卦（八纯卦）**同位借入。

    六爻通则：一卦六爻若六亲不全，则缺者以本宫首卦同爻位之干支为「伏神」。
    例：乾宫「姤」卦无「妻财」，即借乾为天同位之爻。
    """
    present = {liu_qin(palace, ZHI_ELEMENT[gz[1]]) for gz in najia_ganzhi_for(lower, upper)}
    missing = set(ALL_QIN) - present
    if not missing:
        return {}

    fushen: dict[int, tuple[str, str]] = {}
    for pos, gz in enumerate(najia_ganzhi_for(palace, palace), start=1):
        qin = liu_qin(palace, ZHI_ELEMENT[gz[1]])
        if qin in missing:
            fushen[pos] = (qin, gz)
    return fushen


def zhuang_gua(
    result: LiuYaoResult,
    *,
    day_pillar: str,
    month_pillar: str | None = None,
    topic: str | None = None,
    gender: str | None = None,
) -> LiuYaoDivination:
    """装卦：把起卦结果装配成完整卦盘。

    Args:
        result: `cast_liuyao()` 的返回值
        day_pillar: **必填**。日柱干支（如 ``"庚午"``）。六爻以日辰为卦之主宰，
            六神、旬空、旺衰皆由此定，故不可缺省。
        month_pillar: 月柱干支（如 ``"辛巳"``），提供后额外标注月建旺衰
        topic: 占问类别（如 ``"财运"`` ``"事业"``），用于取用神
        gender: ``"male"`` / ``"female"``，婚姻类占问需传（男占妻看妻财、女占夫看官鬼）

    Returns:
        `LiuYaoDivination`：含纳甲、六亲、世应、六神、伏神、旬空、旺衰

    Raises:
        InvalidInputError: 日柱干支非法

    >>> from fortune_core.liuyao import cast_liuyao
    >>> r = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])          # 乾为天
    >>> d = zhuang_gua(r, day_pillar="甲子", month_pillar="丙寅")
    >>> d.palace, d.palace_stage, d.shi_position, d.ying_position
    ('乾', '本宫', 6, 3)
    >>> [y.liu_qin for y in d.yao_details]
    ['子孙', '妻财', '父母', '官鬼', '兄弟', '父母']
    >>> [y.liu_shen for y in d.yao_details]
    ['青龙', '朱雀', '勾陈', '螣蛇', '白虎', '玄武']
    """
    try:
        jiazi_index(day_pillar)
    except ValueError as exc:
        raise InvalidInputError(f"日柱干支非法：{day_pillar!r}（{exc}）") from None

    day_gan, day_zhi = day_pillar[0], day_pillar[1]
    month_zhi = month_pillar[1] if month_pillar else None
    if month_pillar:
        try:
            jiazi_index(month_pillar)
        except ValueError as exc:
            raise InvalidInputError(f"月柱干支非法：{month_pillar!r}（{exc}）") from None

    yang = tuple(YAO_IS_YANG[v] for v in result.yao_values)
    palace = palace_of(result.original_gua)[0]
    stage_idx = GUA_PALACE[result.original_gua][1]
    shi_pos, ying_pos = shi_ying_of(result.original_gua)
    kong = xun_kong_of(day_pillar)

    fushen = _fushen_map(result.lower_gua, result.upper_gua, palace)

    yao_details = _build_yao_details(
        yang=yang,
        lower=result.lower_gua,
        upper=result.upper_gua,
        palace=palace,
        day_gan=day_gan,
        day_zhi=day_zhi,
        month_zhi=month_zhi,
        shi_pos=shi_pos,
        ying_pos=ying_pos,
        moving=result.moving_positions,
        kong=kong,
        fushen_map=fushen,
    )

    changed_details: tuple[YaoDetail, ...] | None = None
    if result.changed_gua and result.changed_lower_gua and result.changed_upper_gua:
        changed_yang = list(yang)
        for pos in result.moving_positions:
            changed_yang[pos - 1] = 1 - changed_yang[pos - 1]
        # 变卦沿用本卦宫（六爻惯例：以本卦宫定六亲，变卦只作动变参考）
        changed_details = _build_yao_details(
            yang=tuple(changed_yang),
            lower=result.changed_lower_gua,
            upper=result.changed_upper_gua,
            palace=palace,
            day_gan=day_gan,
            day_zhi=day_zhi,
            month_zhi=month_zhi,
            shi_pos=shi_pos,
            ying_pos=ying_pos,
            moving=(),
            kong=kong,
            fushen_map={},
        )

    from .najia import is_liuhe_gua, is_liuchong_gua

    features: list[str] = []
    if is_liuchong_gua(result.original_gua):
        features.append("六冲卦")
    if is_liuhe_gua(result.original_gua):
        features.append("六合卦")
    if result.changed_gua:
        if is_liuchong_gua(result.changed_gua):
            features.append("变卦六冲")
        if is_liuhe_gua(result.changed_gua):
            features.append("变卦六合")

    return LiuYaoDivination(
        result=result,
        day_pillar=day_pillar,
        month_pillar=month_pillar,
        day_gan=day_gan,
        day_zhi=day_zhi,
        month_zhi=month_zhi,
        palace=palace,
        palace_element=_palace_element(palace),
        palace_stage=PALACE_STAGE[stage_idx],
        shi_position=shi_pos,
        ying_position=ying_pos,
        yao_details=yao_details,
        changed_yao_details=changed_details,
        xun_kong=kong,
        gua_features=tuple(features),
        topic=topic,
        yongshen=yongshen_of(topic, gender) if topic else None,
    )


def _palace_element(palace: str) -> str:
    from ..constants import GUA_ELEMENT

    return GUA_ELEMENT[palace]


__all__ = [
    "ALL_QIN", "YaoDetail", "LiuYaoDivination", "zhuang_gua", "najia_ganzhi_for",
    "YONGSHEN_BY_TOPIC", "MARRIAGE_YONGSHEN", "yongshen_of",
    "xun_kong_of", "month_state_of", "day_relation_of",
]
