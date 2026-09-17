"""六爻装卦的 **固定属性层** —— 纳甲、八宫、世应、六神、六冲六合。

对应 RULE-005：术数规则集中在本模块，**不得散落到 UI / Prompt / 各业务层**。

可信度标注（AGENTS.md 约定）：
- `[已确认]` 八卦纳甲（纳甲歌）、京房八宫卦序、世应定位、六神起例、地支六冲六合
  —— 均为传世固定规则，本模块另附**独立推导校验**（见 `derive_palace_gua`）
- `[待验证]` 无。本模块刻意**不含**任何流派判断（用神取用、旺衰口径在 `zhuang.py`）

⚠️ 本模块只放「不需要判断」的映射表与纯函数。
凡是「看情况」的规则（哪一爻为用神、旺衰怎么算），一律不进这里（RULE-006）。
"""

from __future__ import annotations

from typing import Final

from ..constants import DIZHI, GUA_ELEMENT, GUA_YAO, TIANGAN
from ..exceptions import InvalidInputError

# --------------------------------------------------------------------------
# 一、八卦纳甲
# --------------------------------------------------------------------------
# 纳甲歌（传世固定口诀）：
#   乾金甲子外壬午，坎水戊寅外戊申，艮土丙辰外丙戌，震木庚子外庚午，
#   巽木辛丑外辛未，离火己卯外己酉，坤土乙未外癸丑，兑金丁巳外丁亥。
#
# 结构：卦 → (内卦三爻干支(自下而上), 外卦三爻干支(自下而上))
# 规律：阳卦（乾震坎艮）地支顺行，阴卦（坤巽离兑）地支逆行。
# 「乾纳甲壬、坤纳乙癸」—— 乾坤各纳两干（内外不同），其余六卦内外同干。

NAJIA: Final[dict[str, tuple[tuple[str, str, str], tuple[str, str, str]]]] = {
    "乾": (("甲子", "甲寅", "甲辰"), ("壬午", "壬申", "壬戌")),
    "坎": (("戊寅", "戊辰", "戊午"), ("戊申", "戊戌", "戊子")),
    "艮": (("丙辰", "丙午", "丙申"), ("丙戌", "丙子", "丙寅")),
    "震": (("庚子", "庚寅", "庚辰"), ("庚午", "庚申", "庚戌")),
    "巽": (("辛丑", "辛亥", "辛酉"), ("辛未", "辛巳", "辛卯")),
    "离": (("己卯", "己丑", "己亥"), ("己酉", "己未", "己巳")),
    "坤": (("乙未", "乙巳", "乙卯"), ("癸丑", "癸亥", "癸酉")),
    "兑": (("丁巳", "丁卯", "丁丑"), ("丁亥", "丁酉", "丁未")),
}

# 各卦纳干（供自校验：乾坤纳两干，余卦纳单干）
NAJIA_GAN: Final[dict[str, tuple[str, ...]]] = {
    "乾": ("甲", "壬"),
    "坤": ("乙", "癸"),
    "坎": ("戊",),
    "艮": ("丙",),
    "震": ("庚",),
    "巽": ("辛",),
    "离": ("己",),
    "兑": ("丁",),
}


def najia_of(gua: str) -> tuple[tuple[str, str, str], tuple[str, str, str]]:
    """卦（八卦名）→ (内卦三爻干支, 外卦三爻干支)，均为自下而上。

    >>> najia_of("乾")
    (('甲子', '甲寅', '甲辰'), ('壬午', '壬申', '壬戌'))
    >>> najia_of("坎")[0]
    ('戊寅', '戊辰', '戊午')
    """
    try:
        return NAJIA[gua]
    except KeyError:
        raise InvalidInputError(f"未知八卦：{gua!r}") from None


# --------------------------------------------------------------------------
# 二、京房八宫卦序
# --------------------------------------------------------------------------
# 每宫 8 卦，依「变爻」规则生成：
#   本宫(纯卦) → 一世(变初) → 二世(变初二) → 三世(变初二三)
#   → 四世(再变第四爻) → 五世(再变第五爻)
#   → 游魂(第五世卦的**第四爻再变回**本宫状态)
#   → 归魂(游魂卦的**内卦三爻全部恢复**本宫状态)
#
# ⚠️ 上表由 `derive_palace_gua()` 独立推导而来，两者必须一致（见测试）。

PALACE_GUA: Final[dict[str, tuple[str, ...]]] = {
    "乾": ("乾", "姤", "遁", "否", "观", "剥", "晋", "大有"),
    "坎": ("坎", "节", "屯", "既济", "革", "丰", "明夷", "师"),
    "艮": ("艮", "贲", "大畜", "损", "睽", "履", "中孚", "渐"),
    "震": ("震", "豫", "解", "恒", "升", "井", "大过", "随"),
    "巽": ("巽", "小畜", "家人", "益", "无妄", "噬嗑", "颐", "蛊"),
    "离": ("离", "旅", "鼎", "未济", "蒙", "涣", "讼", "同人"),
    "坤": ("坤", "复", "临", "泰", "大壮", "夬", "需", "比"),
    "兑": ("兑", "困", "萃", "咸", "蹇", "谦", "小过", "归妹"),
}

# 卦名 → (所属宫, 宫内序号 0..7)
GUA_PALACE: Final[dict[str, tuple[str, int]]] = {
    gua: (palace, idx)
    for palace, guas in PALACE_GUA.items()
    for idx, gua in enumerate(guas)
}

# 宫内序号的语义名（供报告层如实表述）
PALACE_STAGE: Final[tuple[str, ...]] = (
    "本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂",
)

# --------------------------------------------------------------------------
# 三、世应定位
# --------------------------------------------------------------------------
# 世爻 = 「这一卦代表谁」的爻位；应爻 = 与世相对的那一爻（隔三位）。
# 按宫内序号（0..7）查表，值为 (世爻位, 应爻位)，爻位 1..6 自下而上。
# 规律：一世到五世，世爻随之升高；游魂退到四爻；归魂退到三爻。

SHI_YING_YAO: Final[tuple[tuple[int, int], ...]] = (
    (6, 3),  # 本宫（八纯卦）：世上应三
    (1, 4),  # 一世
    (2, 5),  # 二世
    (3, 6),  # 三世
    (4, 1),  # 四世
    (5, 2),  # 五世
    (4, 1),  # 游魂：世退四爻
    (3, 6),  # 归魂：世退三爻
)

# --------------------------------------------------------------------------
# 四、六神（六兽）
# --------------------------------------------------------------------------
# 起例歌：甲乙起青龙，丙丁起朱雀，戊起勾陈，己起螣蛇，庚辛起白虎，壬癸起玄武。
# 定起始六神后，按固定顺序自初爻向上排。

LIUSHEN_ORDER: Final[tuple[str, ...]] = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")

# 日干 → 初爻所起六神在 LIUSHEN_ORDER 中的下标
LIUSHEN_START_INDEX: Final[dict[str, int]] = {
    "甲": 0, "乙": 0,   # 青龙
    "丙": 1, "丁": 1,   # 朱雀
    "戊": 2,            # 勾陈
    "己": 3,            # 螣蛇
    "庚": 4, "辛": 4,   # 白虎
    "壬": 5, "癸": 5,   # 玄武
}

# --------------------------------------------------------------------------
# 五、地支六冲 / 六合
# --------------------------------------------------------------------------
# 六冲：子午、丑未、寅申、卯酉、辰戌、巳亥（相隔六位）
# 六合：子丑、寅亥、卯戌、辰酉、巳申、午未

ZHI_CHONG: Final[dict[str, str]] = {
    "子": "午", "午": "子", "丑": "未", "未": "丑",
    "寅": "申", "申": "寅", "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰", "巳": "亥", "亥": "巳",
}
ZHI_LIUHE: Final[dict[str, str]] = {
    "子": "丑", "丑": "子", "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯", "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳", "午": "未", "未": "午",
}

# 卦的六冲 / 六合
# 六冲卦：八纯卦（本宫卦）＋ 天雷无妄、雷天大壮，共 10 卦
LIUCHONG_GUA: Final[frozenset[str]] = frozenset(
    {"乾", "坎", "艮", "震", "巽", "离", "坤", "兑", "无妄", "大壮"}
)
# 六合卦：天地否、地天泰、雷地豫、地雷复、火山旅、山火贲、水泽节、泽水困，共 8 卦
LIUHE_GUA: Final[frozenset[str]] = frozenset(
    {"否", "泰", "豫", "复", "旅", "贲", "节", "困"}
)

# --------------------------------------------------------------------------
# 六、纯函数
# --------------------------------------------------------------------------


def palace_of(gua: str) -> tuple[str, int]:
    """卦名 → (所属宫, 宫内序号 0..7)。

    >>> palace_of("乾")
    ('乾', 0)
    >>> palace_of("比")
    ('坤', 7)
    >>> palace_of("师")
    ('坎', 7)
    """
    try:
        return GUA_PALACE[gua]
    except KeyError:
        raise InvalidInputError(f"未知六十四卦名：{gua!r}") from None


def palace_stage_of(gua: str) -> str:
    """卦名 → 宫内阶段名（本宫/一世/…/游魂/归魂）。"""
    _, idx = palace_of(gua)
    return PALACE_STAGE[idx]


def shi_ying_of(gua: str) -> tuple[int, int]:
    """卦名 → (世爻位, 应爻位)，爻位 1..6 自下而上。

    >>> shi_ying_of("乾")   # 八纯卦：世上应三
    (6, 3)
    >>> shi_ying_of("姤")   # 一世卦：世初应四
    (1, 4)
    >>> shi_ying_of("晋")   # 游魂卦：世四应初
    (4, 1)
    """
    _, idx = palace_of(gua)
    return SHI_YING_YAO[idx]


def liu_shen_for_day(day_gan: str) -> tuple[str, ...]:
    """日干 → 六神序列（自初爻至上爻，长度 6）。

    >>> liu_shen_for_day("甲")[0]
    '青龙'
    >>> liu_shen_for_day("戊")[0]
    '勾陈'
    >>> liu_shen_for_day("癸")[0]
    '玄武'
    """
    if day_gan not in LIUSHEN_START_INDEX:
        raise InvalidInputError(f"非法日干：{day_gan!r}")
    start = LIUSHEN_START_INDEX[day_gan]
    return tuple(LIUSHEN_ORDER[(start + i) % 6] for i in range(6))


def liu_qin(palace_gua_name: str, yao_element: str) -> str:
    """六亲判定：以**本卦所属宫**的五行为「我」，比对某爻地支五行。

    规则（传世通行，与八字十神同源）：
        同我 → 兄弟    我生 → 子孙    生我 → 父母    我克 → 妻财    克我 → 官鬼

    >>> liu_qin("乾", "metal")    # 乾宫属金，金见金为兄弟
    '兄弟'
    >>> liu_qin("乾", "water")    # 金生水 → 子孙
    '子孙'
    >>> liu_qin("乾", "earth")    # 土生金 → 父母
    '父母'
    >>> liu_qin("乾", "wood")     # 金克木 → 妻财
    '妻财'
    >>> liu_qin("乾", "fire")     # 火克金 → 官鬼
    '官鬼'
    """
    from ..constants import ELEMENT_CONTROLS, ELEMENT_GENERATES

    me = GUA_ELEMENT[palace_gua_name]
    other = yao_element
    if other == me:
        return "兄弟"
    if ELEMENT_GENERATES[me] == other:
        return "子孙"
    if ELEMENT_GENERATES[other] == me:
        return "父母"
    if ELEMENT_CONTROLS[me] == other:
        return "妻财"
    if ELEMENT_CONTROLS[other] == me:
        return "官鬼"
    raise InvalidInputError(  # pragma: no cover - 五行五行关系全覆盖，不可达
        f"无法判定六亲：宫{GUA_ELEMENT[palace_gua_name]} vs 爻{yao_element}"
    )


def zhi_chong(zhi: str) -> str:
    """地支六冲对象。

    >>> zhi_chong("子")
    '午'
    """
    if zhi not in ZHI_CHONG:
        raise InvalidInputError(f"非法地支：{zhi!r}")
    return ZHI_CHONG[zhi]


def zhi_liuhe(zhi: str) -> str:
    """地支六合对象。

    >>> zhi_liuhe("子")
    '丑'
    """
    if zhi not in ZHI_LIUHE:
        raise InvalidInputError(f"非法地支：{zhi!r}")
    return ZHI_LIUHE[zhi]


def is_liuchong_gua(gua: str) -> bool:
    """是否六冲卦。"""
    return gua in LIUCHONG_GUA


def is_liuhe_gua(gua: str) -> bool:
    """是否六合卦。"""
    return gua in LIUHE_GUA


# --------------------------------------------------------------------------
# 七、八宫卦序的独立推导 —— RULE-001 的自证机制
# --------------------------------------------------------------------------


def _flip(gua: str, positions: tuple[int, ...]) -> str:
    """把八卦的指定爻位（1..3 自下而上）取反，返回新卦名。"""
    yao = list(GUA_YAO[gua])
    for p in positions:
        yao[p - 1] = 1 - yao[p - 1]
    flipped = tuple(yao)
    for name, pattern in GUA_YAO.items():
        if pattern == flipped:
            return name
    raise InvalidInputError(f"取反后无对应卦：{gua} {positions}")  # pragma: no cover


def yao_of_lower_upper(lower: str, upper: str) -> tuple[int, ...]:
    """(内卦, 外卦) → 六爻阴阳（自下而上，1=阳 0=阴）。"""
    if lower not in GUA_YAO or upper not in GUA_YAO:
        raise InvalidInputError(f"非法八卦：{lower!r} / {upper!r}")
    return tuple(GUA_YAO[lower]) + tuple(GUA_YAO[upper])


def _gua_from_yao6(yao: tuple[int, ...]) -> tuple[str, str]:
    """六爻阴阳 → (内卦, 外卦)。"""
    for name, pattern in GUA_YAO.items():
        if pattern == tuple(yao[:3]):
            lower = name
            break
    else:
        raise InvalidInputError(f"内卦无对应：{yao[:3]}")  # pragma: no cover
    for name, pattern in GUA_YAO.items():
        if pattern == tuple(yao[3:]):
            upper = name
            break
    else:
        raise InvalidInputError(f"外卦无对应：{yao[3:]}")  # pragma: no cover
    return lower, upper


def derive_palace_gua(palace: str) -> tuple[str, ...]:
    """**独立推导**八宫卦序 —— 不查表，只用「变爻规则」算。

    这是本模块的 RULE-001 自证机制：把 `PALACE_GUA` 的结果与本法推导结果
    逐宫比对，若不一致说明硬编码表有误（见 `tests/test_liuyao_zhuang.py`）。

    推导规则：
        本宫 = 八纯卦
        一世/二世/三世 = 下卦依次变初爻、初二爻、初二三爻
        四世/五世     = 在上一步基础上，上卦再变初爻、初二爻
        游魂          = 五世卦的**第四爻再变回**本宫状态（即上卦初爻复原）
        归魂          = 游魂卦的**内卦三爻全部恢复**本宫

    >>> derive_palace_gua("乾")
    ('乾', '姤', '遁', '否', '观', '剥', '晋', '大有')
    """
    from .gua import _gua_name  # 本包内复用六十四卦表

    if palace not in GUA_YAO:
        raise InvalidInputError(f"非法宫名：{palace!r}")

    pure = yao_of_lower_upper(palace, palace)  # 八纯卦六爻
    out: list[str] = [palace]

    # 一世 ~ 三世：内卦逐步全变
    for n in (1, 2, 3):
        yao = list(pure)
        for i in range(n):
            yao[i] = 1 - yao[i]
        lower, upper = _gua_from_yao6(tuple(yao))
        out.append(_gua_name(lower, upper))

    # 四世 ~ 五世：内卦全变 + 外卦变初爻 / 初二爻
    for n in (1, 2):
        yao = list(pure)
        for i in range(3):
            yao[i] = 1 - yao[i]
        for i in range(n):
            yao[3 + i] = 1 - yao[3 + i]
        lower, upper = _gua_from_yao6(tuple(yao))
        out.append(_gua_name(lower, upper))

    # 游魂：五世卦的第 4 爻再变回本宫（= 上卦初爻复原）
    wushi = list(pure)
    for i in range(3):
        wushi[i] = 1 - wushi[i]
    for i in range(2):
        wushi[3 + i] = 1 - wushi[3 + i]
    wushi[3] = pure[3]  # 第四爻恢复本宫
    lower, upper = _gua_from_yao6(tuple(wushi))
    out.append(_gua_name(lower, upper))

    # 归魂：游魂卦内卦三爻全部恢复本宫
    guihun = list(wushi)
    for i in range(3):
        guihun[i] = pure[i]
    lower, upper = _gua_from_yao6(tuple(guihun))
    out.append(_gua_name(lower, upper))

    return tuple(out)


__all__ = [
    "NAJIA", "NAJIA_GAN", "najia_of",
    "PALACE_GUA", "GUA_PALACE", "PALACE_STAGE",
    "SHI_YING_YAO", "palace_of", "palace_stage_of", "shi_ying_of",
    "LIUSHEN_ORDER", "LIUSHEN_START_INDEX", "liu_shen_for_day",
    "ZHI_CHONG", "ZHI_LIUHE", "zhi_chong", "zhi_liuhe",
    "LIUCHONG_GUA", "LIUHE_GUA", "is_liuchong_gua", "is_liuhe_gua",
    "liu_qin", "yao_of_lower_upper", "derive_palace_gua",
]
