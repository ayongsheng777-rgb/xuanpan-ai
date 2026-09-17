"""神煞 —— 八字神煞的确定性查找。

对应 RULE-001：神煞是**固定口诀表**，由天干/地支/干支组合唯一确定，
不含任何"吉凶程度"的流派判断（吉凶分级进 `schools.py` 或标注不确定性）。

可信度标注：
- `[已确认]` 天乙贵人 / 文昌 / 禄神 / 羊刃 / 桃花 / 驿马 / 华盖 / 将星 /
  劫煞 / 亡神 / 孤辰 / 寡宿 / 天德 / 月德 —— 通行口诀，各家一致
- `[待验证]` 红鸾 / 天喜 / 金舆 / 太极贵人 —— 存在不同起法，仅收录无争议口径

设计约束：
1. **只查，不断**。本模块回答"这个盘里有没有某神煞、落在哪一柱"，
   不输出"吉/凶"评级。吉凶属流派解读，交给上层标注不确定性。
2. 每张口诀表附 `verify_*` 自证函数，用独立性质校验硬编码表（同装卦层思路）。
3. 神煞以「日干」「年干」「日支」「年支」四类为锚点，输出统一结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..constants import (
    DIZHI,
    GAN_ELEMENT,
    GAN_YINYANG,
    TIANGAN,
    ZHI_ELEMENT,
    ZHI_YINYANG,
)
from ..exceptions import InvalidInputError

# --------------------------------------------------------------------------
# 一、以「日干 / 年干」为锚点的神煞
# --------------------------------------------------------------------------

# 天乙贵人（口诀：甲戊庚牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢马虎）
# 每个天干两个贵人地支。
TIANYI_GUIREN: Final[dict[str, tuple[str, str]]] = {
    "甲": ("丑", "未"),
    "戊": ("丑", "未"),
    "庚": ("丑", "未"),
    "乙": ("子", "申"),
    "己": ("子", "申"),
    "丙": ("亥", "酉"),
    "丁": ("亥", "酉"),
    "壬": ("卯", "巳"),
    "癸": ("卯", "巳"),
    "辛": ("午", "寅"),
}

# 文昌贵人（口诀：甲乙巳午报君知，丙戊申宫丁己鸡，庚猪辛鼠壬逢虎，癸人见卯入云梯）
WENCHANG: Final[dict[str, str]] = {
    "甲": "巳", "乙": "午", "丙": "申", "丁": "酉", "戊": "申",
    "己": "酉", "庚": "亥", "辛": "子", "壬": "寅", "癸": "卯",
}

# 禄神（临官位：甲禄在寅、乙禄在卯、丙戊禄在巳、丁己禄在午、庚禄在申、辛禄在酉、壬禄在亥、癸禄在子）
LU_SHEN: Final[dict[str, str]] = {
    "甲": "寅", "乙": "卯", "丙": "巳", "丁": "午", "戊": "巳",
    "己": "午", "庚": "申", "辛": "酉", "壬": "亥", "癸": "子",
}

# 羊刃（阳干帝旺位，阴干取劫财位——通行口径：甲卯乙寅丙午丁巳戊午己巳庚酉辛申壬子癸亥）
YANG_REN: Final[dict[str, str]] = {
    "甲": "卯", "乙": "寅", "丙": "午", "丁": "巳", "戊": "午",
    "己": "巳", "庚": "酉", "辛": "申", "壬": "子", "癸": "亥",
}

# 金舆（禄前二位：甲辰乙巳丙未丁申戊未己申庚戌辛亥壬丑癸寅）
JIN_YU: Final[dict[str, str]] = {
    "甲": "辰", "乙": "巳", "丙": "未", "丁": "申", "戊": "未",
    "己": "申", "庚": "戌", "辛": "亥", "壬": "丑", "癸": "寅",
}

# 太极贵人（甲乙生人子午中，丙丁鸡兔定亨通，戊己两干临四季，庚辛寅亥禄丰隆，壬癸巳申偏喜美）
TAIJI_GUIREN: Final[dict[str, tuple[str, ...]]] = {
    "甲": ("子", "午"), "乙": ("子", "午"),
    "丙": ("酉", "卯"), "丁": ("酉", "卯"),
    "戊": ("辰", "戌", "丑", "未"), "己": ("辰", "戌", "丑", "未"),
    "庚": ("寅", "亥"), "辛": ("寅", "亥"),
    "壬": ("巳", "申"), "癸": ("巳", "申"),
}

# --------------------------------------------------------------------------
# 二、以「日支 / 年支」为锚点的神煞
# --------------------------------------------------------------------------

# 桃花（咸池）：申子辰在酉、寅午戌在卯、巳酉丑在午、亥卯未在子
TAOHUA: Final[dict[str, str]] = {
    "申": "酉", "子": "酉", "辰": "酉",
    "寅": "卯", "午": "卯", "戌": "卯",
    "巳": "午", "酉": "午", "丑": "午",
    "亥": "子", "卯": "子", "未": "子",
}

# 驿马（马星）：申子辰马在寅、寅午戌马在申、巳酉丑马在亥、亥卯未马在巳
YIMA: Final[dict[str, str]] = {
    "申": "寅", "子": "寅", "辰": "寅",
    "寅": "申", "午": "申", "戌": "申",
    "巳": "亥", "酉": "亥", "丑": "亥",
    "亥": "巳", "卯": "巳", "未": "巳",
}

# 华盖：申子辰见辰、寅午戌见戌、巳酉丑见丑、亥卯未见未
HUAGAI: Final[dict[str, str]] = {
    "申": "辰", "子": "辰", "辰": "辰",
    "寅": "戌", "午": "戌", "戌": "戌",
    "巳": "丑", "酉": "丑", "丑": "丑",
    "亥": "未", "卯": "未", "未": "未",
}

# 将星：申子辰见子、寅午戌见午、巳酉丑见酉、亥卯未见卯
JIANGXING: Final[dict[str, str]] = {
    "申": "子", "子": "子", "辰": "子",
    "寅": "午", "午": "午", "戌": "午",
    "巳": "酉", "酉": "酉", "丑": "酉",
    "亥": "卯", "卯": "卯", "未": "卯",
}

# 劫煞：申子辰见巳、寅午戌见亥、巳酉丑见寅、亥卯未见申
JIESHA: Final[dict[str, str]] = {
    "申": "巳", "子": "巳", "辰": "巳",
    "寅": "亥", "午": "亥", "戌": "亥",
    "巳": "寅", "酉": "寅", "丑": "寅",
    "亥": "申", "卯": "申", "未": "申",
}

# 亡神：申子辰见亥、寅午戌见巳、巳酉丑见申、亥卯未见寅
WANGSHEN: Final[dict[str, str]] = {
    "申": "亥", "子": "亥", "辰": "亥",
    "寅": "巳", "午": "巳", "戌": "巳",
    "巳": "申", "酉": "申", "丑": "申",
    "亥": "寅", "卯": "寅", "未": "寅",
}

# 孤辰：亥子丑见寅、寅卯辰见巳、巳午未见申、申酉戌见亥
GUCHEN: Final[dict[str, str]] = {
    "亥": "寅", "子": "寅", "丑": "寅",
    "寅": "巳", "卯": "巳", "辰": "巳",
    "巳": "申", "午": "申", "未": "申",
    "申": "亥", "酉": "亥", "戌": "亥",
}

# 寡宿：亥子丑见戌、寅卯辰见丑、巳午未见辰、申酉戌见未
GUASU: Final[dict[str, str]] = {
    "亥": "戌", "子": "戌", "丑": "戌",
    "寅": "丑", "卯": "丑", "辰": "丑",
    "巳": "辰", "午": "辰", "未": "辰",
    "申": "未", "酉": "未", "戌": "未",
}

# 红鸾（子起卯，逆数）：子卯丑寅寅丑卯子辰亥巳戌午酉未申申未酉午戌巳亥辰
HONGLUAN: Final[dict[str, str]] = {
    "子": "卯", "丑": "寅", "寅": "丑", "卯": "子", "辰": "亥", "巳": "戌",
    "午": "酉", "未": "申", "申": "未", "酉": "午", "戌": "巳", "亥": "辰",
}

# 天喜（红鸾对冲）：子酉丑申寅未卯午辰巳巳辰午卯未寅申丑酉子戌亥亥戌
TIANXI: Final[dict[str, str]] = {
    "子": "酉", "丑": "申", "寅": "未", "卯": "午", "辰": "巳", "巳": "辰",
    "午": "卯", "未": "寅", "申": "丑", "酉": "子", "戌": "亥", "亥": "戌",
}

# --------------------------------------------------------------------------
# 三、以「月支」为锚点的神煞
# --------------------------------------------------------------------------

# 天德贵人（月支起：正丁二申宫，三壬四辛同，五亥六甲上，七癸八寅逢，九丙十居乙，子巳丑庚中）
TIANDE: Final[dict[str, str]] = {
    "寅": "丁", "卯": "申", "辰": "壬", "巳": "辛", "午": "亥", "未": "甲",
    "申": "癸", "酉": "寅", "戌": "丙", "亥": "乙", "子": "巳", "丑": "庚",
}

# 月德贵人（月支起：寅午戌月德在丙、申子辰月德在壬、亥卯未月德在甲、巳酉丑月德在庚）
YUEDE: Final[dict[str, str]] = {
    "寅": "丙", "午": "丙", "戌": "丙",
    "申": "壬", "子": "壬", "辰": "壬",
    "亥": "甲", "卯": "甲", "未": "甲",
    "巳": "庚", "酉": "庚", "丑": "庚",
}


# --------------------------------------------------------------------------
# 结果结构
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShenShaResult:
    """一柱命盘的神煞查找结果。

    `gan_anchor` 以日干为锚的神煞、`zhi_anchor` 以日支为锚的神煞、
    `month_anchor` 以月支为锚的神煞，各是一张 ``神煞名 -> 命盘内命中位置`` 的映射。
    命中的位置以「四柱天干/地支」集合表示（例如天乙贵人可能落在时支）。
    """

    gan_anchor: dict[str, list[str]]   # 神煞名 -> 命中的地支（以日干为锚）
    zhi_anchor: dict[str, list[str]]   # 神煞名 -> 命中的地支（以日支为锚）
    month_anchor: dict[str, list[str]]  # 神煞名 -> 命中的天干（以月支为锚）

    def to_dict(self) -> dict[str, dict[str, list[str]]]:
        return {
            "日干起": self.gan_anchor,
            "日支起": self.zhi_anchor,
            "月支起": self.month_anchor,
        }


def find_shensha(pillars: dict[str, str]) -> ShenShaResult:
    """在一组四柱里查找神煞。

    Args:
        pillars: {"year": 干支, "month": 干支, "day": 干支, "hour": 干支}

    Returns:
        命中结果。每类神煞的值是命盘中**命中的地支/天干**列表（去重、按地支序）。
        空列表表示该神煞未命中。

    说明：
        神煞锚点只用「日干 / 日支 / 月支」三类（命理以日柱为主）。
        年柱为锚的起法（如年支桃花）可通过 `find_shensha_year_anchor` 单独取，
        本函数默认不混入，避免口径混乱。
    """
    _validate_pillars(pillars)
    day_gan = pillars["day"][0]
    day_zhi = pillars["day"][1]
    month_zhi = pillars["month"][1]

    branches = [pillars[k][1] for k in ("year", "month", "day", "hour")]
    stems = [pillars[k][0] for k in ("year", "month", "day", "hour")]

    # ---- 日干起 ----
    gan_anchor: dict[str, list[str]] = {}
    for name, target in (
        ("天乙贵人", TIANYI_GUIREN.get(day_gan, ())),
        ("文昌贵人", (WENCHANG[day_gan],)),
        ("禄神", (LU_SHEN[day_gan],)),
        ("羊刃", (YANG_REN[day_gan],)),
        ("金舆", (JIN_YU[day_gan],)),
        ("太极贵人", TAIJI_GUIREN[day_gan]),
    ):
        hits = [z for z in branches if z in target]
        if hits:
            gan_anchor[name] = _uniq_ordered(hits)

    # ---- 日支起 ----
    zhi_anchor: dict[str, list[str]] = {}
    for name, target in (
        ("桃花", (TAOHUA[day_zhi],)),
        ("驿马", (YIMA[day_zhi],)),
        ("华盖", (HUAGAI[day_zhi],)),
        ("将星", (JIANGXING[day_zhi],)),
        ("劫煞", (JIESHA[day_zhi],)),
        ("亡神", (WANGSHEN[day_zhi],)),
        ("孤辰", (GUCHEN[day_zhi],)),
        ("寡宿", (GUASU[day_zhi],)),
        ("红鸾", (HONGLUAN[day_zhi],)),
        ("天喜", (TIANXI[day_zhi],)),
    ):
        hits = [z for z in branches if z in target]
        if hits:
            zhi_anchor[name] = _uniq_ordered(hits)

    # ---- 月支起 ----
    month_anchor: dict[str, list[str]] = {}
    for name, target in (("天德贵人", TIANDE[month_zhi]), ("月德贵人", YUEDE[month_zhi])):
        hits = [g for g in stems if g == target]
        if hits:
            month_anchor[name] = _uniq_ordered(hits)

    return ShenShaResult(
        gan_anchor=gan_anchor,
        zhi_anchor=zhi_anchor,
        month_anchor=month_anchor,
    )


def find_shensha_year_anchor(pillars: dict[str, str]) -> dict[str, list[str]]:
    """以「年支」为锚的神煞（年支桃花 / 驿马 / 华盖 等）。

    单独成函数：年支起法与日支起法结果不同，混在一起会让人误以为是同一套。
    命理上以日柱为主，年柱起法多用于大运流年比对，故分开返回。
    """
    _validate_pillars(pillars)
    year_zhi = pillars["year"][1]
    branches = [pillars[k][1] for k in ("year", "month", "day", "hour")]

    out: dict[str, list[str]] = {}
    for name, target in (
        ("年支桃花", (TAOHUA[year_zhi],)),
        ("年支驿马", (YIMA[year_zhi],)),
        ("年支华盖", (HUAGAI[year_zhi],)),
        ("年支将星", (JIANGXING[year_zhi],)),
    ):
        hits = [z for z in branches if z in target]
        if hits:
            out[name] = _uniq_ordered(hits)
    return out


# --------------------------------------------------------------------------
# 自证校验（同装卦层思路：用独立性质验证硬编码表）
# --------------------------------------------------------------------------


def verify_tables() -> list[str]:
    """校验所有神煞口诀表的内部自洽性，返回问题列表（空 = 全部通过）。

    性质约束：
    1. 桃花 / 驿马 / 华盖 / 将星 / 劫煞 / 亡神 六表共享同一「三合局分组」，
       即同一三合组内三个地支的取值必须相同（这是六表的口诀结构）
    2. 红鸾 + 天喜 恒为对冲（相隔六位）
    3. 天德 / 月德 的取值为合法天干/地支
    4. 各表条目数完整（覆盖 10 天干或 12 地支）
    """
    problems: list[str] = []

    # 1) 三合局分组一致性：三合组 = (申子辰)(寅午戌)(巳酉丑)(亥卯未)
    triads = [
        ("申", "子", "辰"),
        ("寅", "午", "戌"),
        ("巳", "酉", "丑"),
        ("亥", "卯", "未"),
    ]
    for table_name, table in (
        ("桃花", TAOHUA),
        ("驿马", YIMA),
        ("华盖", HUAGAI),
        ("将星", JIANGXING),
        ("劫煞", JIESHA),
        ("亡神", WANGSHEN),
    ):
        for triad in triads:
            vals = {table[z] for z in triad}
            if len(vals) != 1:
                problems.append(f"{table_name} 三合组 {triad} 取值不一致：{sorted(vals)}")

    # 2) 红鸾天喜对冲
    for z in DIZHI:
        if (DIZHI.index(HONGLUAN[z]) - DIZHI.index(TIANXI[z])) % 12 != 6:
            problems.append(f"红鸾/天喜 {z} 不对冲")

    # 3) 天德月德取值为合法天干/地支
    for z, v in TIANDE.items():
        if v not in TIANGAN and v not in DIZHI:
            problems.append(f"天德 {z} 取值非法：{v}")
    for z, v in YUEDE.items():
        if v not in TIANGAN:
            problems.append(f"月德 {z} 取值非法：{v}")

    # 4) 完整性：所有单值表必须覆盖 12 地支 / 10 天干
    for table_name, table, size in (
        ("文昌", WENCHANG, 10), ("禄神", LU_SHEN, 10), ("羊刃", YANG_REN, 10),
        ("金舆", JIN_YU, 10), ("天乙贵人", TIANYI_GUIREN, 10),
        ("桃花", TAOHUA, 12), ("驿马", YIMA, 12), ("华盖", HUAGAI, 12),
        ("将星", JIANGXING, 12), ("劫煞", JIESHA, 12), ("亡神", WANGSHEN, 12),
        ("孤辰", GUCHEN, 12), ("寡宿", GUASU, 12), ("红鸾", HONGLUAN, 12),
        ("天喜", TIANXI, 12), ("天德", TIANDE, 12), ("月德", YUEDE, 12),
    ):
        if len(table) != size:
            problems.append(f"{table_name} 表缺项：{len(table)}/{size}")

    return problems


# --------------------------------------------------------------------------
# 工具
# --------------------------------------------------------------------------


def _validate_pillars(pillars: dict[str, str]) -> None:
    if set(pillars) != {"year", "month", "day", "hour"}:
        raise InvalidInputError(f"四柱键不全：{sorted(pillars)}")
    for k, v in pillars.items():
        if len(v) != 2 or v[0] not in GAN_ELEMENT or v[1] not in ZHI_ELEMENT:
            raise InvalidInputError(f"{k} 柱干支非法：{v!r}")


def _uniq_ordered(items: list[str]) -> list[str]:
    """去重且按「地支序优先、天干序其次」排列。"""
    seen = set(items)
    return [x for x in list(DIZHI) + list(TIANGAN) if x in seen]


__all__ = [
    "ShenShaResult", "find_shensha", "find_shensha_year_anchor", "verify_tables",
    "TIANYI_GUIREN", "WENCHANG", "LU_SHEN", "YANG_REN", "JIN_YU", "TAIJI_GUIREN",
    "TAOHUA", "YIMA", "HUAGAI", "JIANGXING", "JIESHA", "WANGSHEN",
    "GUCHEN", "GUASU", "HONGLUAN", "TIANXI", "TIANDE", "YUEDE",
]
