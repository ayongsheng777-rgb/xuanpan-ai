"""基础常量表 —— 术数领域的**唯一映射来源**。

对应 RULE-005：罗盘/术数规则不得散落在 UI 或 Prompt 中。
本模块只放**固定属性**，不放任何需要流派判断的规则（那些进 `schools.py`）。

可信度标注：
- `[已确认]` 天干/地支的五行与阴阳、六十甲子序、纳音、地支藏干 —— 公认固定属性
- `[待验证]` 卦山之阴阳（采用「四阳卦 / 四阴卦」划分，属流派相关）
"""

from __future__ import annotations

from typing import Final, Literal

# --------------------------------------------------------------------------
# 天干 / 地支
# --------------------------------------------------------------------------

TIANGAN: Final[tuple[str, ...]] = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
DIZHI: Final[tuple[str, ...]] = (
    "子", "丑", "寅", "卯", "辰", "巳",
    "午", "未", "申", "酉", "戌", "亥",
)

# 六十甲子：序号 n -> TIANGAN[n % 10] + DIZHI[n % 12]
JIAZI_60: Final[tuple[str, ...]] = tuple(
    TIANGAN[i % 10] + DIZHI[i % 12] for i in range(60)
)

# --------------------------------------------------------------------------
# 五行
# --------------------------------------------------------------------------

Element = Literal["wood", "fire", "earth", "metal", "water"]
YinYang = Literal["yang", "yin"]

ELEMENT_CN: Final[dict[str, str]] = {
    "wood": "木",
    "fire": "火",
    "earth": "土",
    "metal": "金",
    "water": "水",
}
CN_ELEMENT: Final[dict[str, str]] = {v: k for k, v in ELEMENT_CN.items()}

# 相生：木→火→土→金→水→木
ELEMENT_GENERATES: Final[dict[str, str]] = {
    "wood": "fire",
    "fire": "earth",
    "earth": "metal",
    "metal": "water",
    "water": "wood",
}
# 相克：木→土→水→火→金→木
ELEMENT_CONTROLS: Final[dict[str, str]] = {
    "wood": "earth",
    "earth": "water",
    "water": "fire",
    "fire": "metal",
    "metal": "wood",
}

# 天干 -> 五行（甲乙木 丙丁火 戊己土 庚辛金 壬癸水）
GAN_ELEMENT: Final[dict[str, str]] = {
    gan: element
    for gan, element in zip(
        TIANGAN,
        ("wood", "wood", "fire", "fire", "earth", "earth", "metal", "metal", "water", "water"),
        strict=True,
    )
}

# 天干 -> 阴阳（甲丙戊庚壬为阳，乙丁己辛癸为阴）
GAN_YINYANG: Final[dict[str, str]] = {
    gan: ("yang" if i % 2 == 0 else "yin") for i, gan in enumerate(TIANGAN)
}

# 地支 -> 五行
ZHI_ELEMENT: Final[dict[str, str]] = {
    zhi: element
    for zhi, element in zip(
        DIZHI,
        (
            "water", "earth", "wood", "wood", "earth", "fire",
            "fire", "earth", "metal", "metal", "earth", "water",
        ),
        strict=True,
    )
}

# 地支 -> 阴阳（子寅辰午申戌为阳，丑卯巳未酉亥为阴）
ZHI_YINYANG: Final[dict[str, str]] = {
    zhi: ("yang" if i % 2 == 0 else "yin") for i, zhi in enumerate(DIZHI)
}

# 地支 -> 生肖
ZHI_SHENGXIAO: Final[dict[str, str]] = {
    zhi: animal
    for zhi, animal in zip(
        DIZHI,
        ("鼠", "牛", "虎", "兔", "龙", "蛇", "马", "羊", "猴", "鸡", "狗", "猪"),
        strict=True,
    )
}

# 地支 -> 时辰区间（24 小时制，起始时刻含、结束时刻不含）
# 注意：子时跨日（23:00~01:00），存在早子时/晚子时之争，属流派问题
ZHI_HOUR_RANGE: Final[dict[str, tuple[int, int]]] = {
    zhi: ((23 + i * 2) % 24, (23 + i * 2 + 2) % 24) for i, zhi in enumerate(DIZHI)
}

# 地支藏干（本气在前，余气在后）—— [已确认] 通行版本
ZHI_CANGGAN: Final[dict[str, tuple[str, ...]]] = {
    "子": ("癸",),
    "丑": ("己", "癸", "辛"),
    "寅": ("甲", "丙", "戊"),
    "卯": ("乙",),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "庚", "戊"),
    "午": ("丁", "己"),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛",),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲"),
}

# --------------------------------------------------------------------------
# 纳音（六十甲子两两一组，共 30 组）
# --------------------------------------------------------------------------

NAYIN_30: Final[tuple[str, ...]] = (
    "海中金", "炉中火", "大林木", "路旁土", "剑锋金",
    "山头火", "涧下水", "城头土", "白蜡金", "杨柳木",
    "泉中水", "屋上土", "霹雳火", "松柏木", "长流水",
    "沙中金", "山下火", "平地木", "壁上土", "金箔金",
    "覆灯火", "天河水", "大驿土", "钗钏金", "桑柘木",
    "大溪水", "沙中土", "天上火", "石榴木", "大海水",
)

# --------------------------------------------------------------------------
# 八卦
# --------------------------------------------------------------------------

# 八卦：名称 -> (自下而上的三爻, 1=阳 0=阴)
# 口诀：乾三连、坤六断、震仰盂、艮覆碗、离中虚、坎中满、兑上缺、巽下断
GUA_YAO: Final[dict[str, tuple[int, int, int]]] = {
    "乾": (1, 1, 1),
    "兑": (1, 1, 0),
    "离": (1, 0, 1),
    "震": (1, 0, 0),
    "巽": (0, 1, 1),
    "坎": (0, 1, 0),
    "艮": (0, 0, 1),
    "坤": (0, 0, 0),
}

# 八卦 -> 五行
GUA_ELEMENT: Final[dict[str, str]] = {
    "乾": "metal", "兑": "metal",
    "离": "fire",
    "震": "wood", "巽": "wood",
    "坎": "water",
    "艮": "earth", "坤": "earth",
}

# 八卦 -> 阴阳（四阳卦：乾坎艮震；四阴卦：巽离坤兑）—— [待验证] 流派相关
GUA_YINYANG: Final[dict[str, str]] = {
    "乾": "yang", "坎": "yang", "艮": "yang", "震": "yang",
    "巽": "yin", "离": "yin", "坤": "yin", "兑": "yin",
}

# 后天八卦方位（度，正北 0°，顺时针）
GUA_HOUTIAN_DEGREE: Final[dict[str, float]] = {
    "坎": 0.0, "艮": 45.0, "震": 90.0, "巽": 135.0,
    "离": 180.0, "坤": 225.0, "兑": 270.0, "乾": 315.0,
}

# 先天八卦序（用于六爻/梅花易数取数）
GUA_XIANTIAN_NUMBER: Final[dict[str, int]] = {
    "乾": 1, "兑": 2, "离": 3, "震": 4, "巽": 5, "坎": 6, "艮": 7, "坤": 8,
}

# --------------------------------------------------------------------------
# 十神
# --------------------------------------------------------------------------

SHISHEN: Final[tuple[str, ...]] = (
    "比肩", "劫财", "食神", "伤官", "偏财",
    "正财", "七杀", "正官", "偏印", "正印",
)

# --------------------------------------------------------------------------
# 派生函数
# --------------------------------------------------------------------------


def jiazi_index(ganzhi: str) -> int:
    """干支字符串 -> 六十甲子序号（0~59）。非法干支抛 ValueError。

    >>> jiazi_index("甲子")
    0
    >>> jiazi_index("癸亥")
    59
    """
    if len(ganzhi) != 2 or ganzhi[0] not in GAN_ELEMENT or ganzhi[1] not in ZHI_ELEMENT:
        raise ValueError(f"非法干支：{ganzhi!r}")
    gi, zi = TIANGAN.index(ganzhi[0]), DIZHI.index(ganzhi[1])
    if gi % 2 != zi % 2:
        raise ValueError(f"干支阴阳不匹配（不存在此组合）：{ganzhi!r}")
    # 解同余方程组 n ≡ gi (mod 10), n ≡ zi (mod 12)
    for n in range(60):
        if n % 10 == gi and n % 12 == zi:
            return n
    raise ValueError(f"无法解出干支序号：{ganzhi!r}")  # pragma: no cover


def ganzhi_from_index(index: int) -> str:
    """六十甲子序号 -> 干支字符串（自动对 60 取模）。"""
    return JIAZI_60[index % 60]


def nayin_of(ganzhi: str) -> str:
    """干支 -> 纳音五行。"""
    return NAYIN_30[jiazi_index(ganzhi) // 2]


def shishen(day_gan: str, other_gan: str) -> str:
    """以日干为参照，判定另一天干的十神。

    规则（同性为偏、异性为正）：
        同我 → 比肩 / 劫财      我生 → 食神 / 伤官
        我克 → 偏财 / 正财      克我 → 七杀 / 正官
        生我 → 偏印 / 正印
    """
    me = GAN_ELEMENT[day_gan]
    other = GAN_ELEMENT[other_gan]
    same_polarity = GAN_YINYANG[day_gan] == GAN_YINYANG[other_gan]

    if other == me:
        return "比肩" if same_polarity else "劫财"
    if ELEMENT_GENERATES[me] == other:
        return "食神" if same_polarity else "伤官"
    if ELEMENT_CONTROLS[me] == other:
        return "偏财" if same_polarity else "正财"
    if ELEMENT_CONTROLS[other] == me:
        return "七杀" if same_polarity else "正官"
    if ELEMENT_GENERATES[other] == me:
        return "偏印" if same_polarity else "正印"
    raise ValueError(f"无法判定十神：{day_gan} vs {other_gan}")  # pragma: no cover


__all__ = [
    "TIANGAN", "DIZHI", "JIAZI_60",
    "Element", "YinYang", "ELEMENT_CN", "CN_ELEMENT",
    "ELEMENT_GENERATES", "ELEMENT_CONTROLS",
    "GAN_ELEMENT", "GAN_YINYANG", "ZHI_ELEMENT", "ZHI_YINYANG",
    "ZHI_SHENGXIAO", "ZHI_HOUR_RANGE", "ZHI_CANGGAN", "NAYIN_30",
    "GUA_YAO", "GUA_ELEMENT", "GUA_YINYANG", "GUA_HOUTIAN_DEGREE", "GUA_XIANTIAN_NUMBER",
    "SHISHEN",
    "jiazi_index", "ganzhi_from_index", "nayin_of", "shishen",
]
