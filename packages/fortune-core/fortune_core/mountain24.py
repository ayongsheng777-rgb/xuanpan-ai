"""二十四山 —— 罗盘计算的地基。

设计要点（对应 RULE-005）：**二十四山的排列、角度、属性是领域配置，不是散落的字面量。**

- 唯一标准顺序：从正北「子」起，顺时针每山 15°
- 每山属性：五行、阴阳、三元龙、所属层（地支 / 天干 / 卦）
- 一切角度运算都以「山心角」为基准，边界处理显式定义（左闭右开）

角度约定（全项目统一，不得再有第二种）：
    0° = 正北 = 子山中心，角度顺时针增大，90° = 正东 = 卯山中心
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from .constants import (
    DIZHI,
    GAN_ELEMENT,
    GAN_YINYANG,
    GUA_ELEMENT,
    GUA_YINYANG,
    TIANGAN,
    ZHI_ELEMENT,
    ZHI_YINYANG,
)

# --------------------------------------------------------------------------
# 唯一标准表
# --------------------------------------------------------------------------

MOUNTAIN_ORDER: Final[tuple[str, ...]] = (
    "子", "癸", "丑", "艮", "寅", "甲", "卯", "乙",
    "辰", "巽", "巳", "丙", "午", "丁", "未", "坤",
    "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬",
)

SPAN_DEGREE: Final[float] = 360.0 / 24.0  # 15°
HALF_SPAN: Final[float] = SPAN_DEGREE / 2.0  # 7.5°

# 一元 = 三山 = 45°，共八卦八方。每卦辖**连续三山**，起于该卦方位角前 15°。
# 例：坎卦居正北（0°），辖 壬(345°) 子(0°) 癸(15°)。
GUA_OF_MOUNTAIN: Final[dict[str, str]] = {
    "坎": "壬子癸", "艮": "丑艮寅", "震": "甲卯乙", "巽": "辰巽巳",
    "离": "丙午丁", "坤": "未坤申", "兑": "庚酉辛", "乾": "戌乾亥",
}
MOUNTAIN_OF_GUA: Final[dict[str, str]] = {
    m: gua for gua, group in GUA_OF_MOUNTAIN.items() for m in group
}

# 三元龙：天元（四正 + 四维）/ 地元（四库 + 四阳干）/ 人元（四生 + 四阴干）
SANYUAN: Final[dict[str, str]] = {
    **{m: "天元" for m in ("子", "午", "卯", "酉", "乾", "坤", "艮", "巽")},
    **{m: "地元" for m in ("辰", "戌", "丑", "未", "甲", "庚", "壬", "丙")},
    **{m: "人元" for m in ("寅", "申", "巳", "亥", "乙", "辛", "丁", "癸")},
}

Kind = Literal["branch", "stem", "gua"]


@dataclass(frozen=True, slots=True)
class Mountain:
    """二十四山之一。不可变值对象。"""

    index: int              # 0..23，从子起顺时针
    name: str
    kind: Kind              # branch=地支山 / stem=天干山 / gua=卦山
    center_degree: float    # 山心角（0..345，步长 15）
    element: str            # 五行（英文键，见 constants.ELEMENT_CN）
    yin_yang: str           # "yang" | "yin"
    sanyuan: str            # 天元 / 地元 / 人元
    gua: str                # 所属后天八卦（坎/艮/震/巽/离/坤/兑/乾）
    branch: str | None = None   # 该山是否为地支山 → 地支字
    stem: str | None = None     # 该山是否为天干山 → 天干字

    @property
    def start_degree(self) -> float:
        """山的起始角（含）。"""
        return (self.center_degree - HALF_SPAN) % 360.0

    @property
    def end_degree(self) -> float:
        """山的结束角（不含）。"""
        return (self.center_degree + HALF_SPAN) % 360.0

    @property
    def full_name(self) -> str:
        """完整称谓，如「午山」「艮山」。"""
        return f"{self.name}山"


def _build() -> tuple[Mountain, ...]:
    mountains = []
    for index, name in enumerate(MOUNTAIN_ORDER):
        kind: Kind
        if name in ZHI_ELEMENT and name in DIZHI:
            kind, element, yinyang = "branch", ZHI_ELEMENT[name], ZHI_YINYANG[name]
            branch, stem = name, None
        elif name in GAN_ELEMENT and name in TIANGAN:
            kind, element, yinyang = "stem", GAN_ELEMENT[name], GAN_YINYANG[name]
            branch, stem = None, name
        else:
            # 只剩卦山：艮 巽 坤 乾
            kind, element, yinyang = "gua", GUA_ELEMENT[name], GUA_YINYANG[name]
            branch, stem = None, None

        mountains.append(
            Mountain(
                index=index,
                name=name,
                kind=kind,
                center_degree=index * SPAN_DEGREE,
                element=element,
                yin_yang=yinyang,
                sanyuan=SANYUAN[name],
                gua=MOUNTAIN_OF_GUA[name],
                branch=branch,
                stem=stem,
            )
        )
    return tuple(mountains)


MOUNTAINS: Final[tuple[Mountain, ...]] = _build()
MOUNTAIN_BY_NAME: Final[dict[str, Mountain]] = {m.name: m for m in MOUNTAINS}

# ---- 启动期不变量（领域数据必须自洽，否则整盘计算作废）----
if set(MOUNTAIN_OF_GUA) != set(MOUNTAIN_ORDER):  # pragma: no cover - 配置错误才会触发
    _missing = set(MOUNTAIN_ORDER) - set(MOUNTAIN_OF_GUA)
    raise RuntimeError(f"八卦辖山未完整覆盖二十四山，缺失：{''.join(sorted(_missing))}")
if {m.name for m in MOUNTAINS} != set(MOUNTAIN_ORDER):  # pragma: no cover
    raise RuntimeError("二十四山构造结果与标准表不一致")
if len({m.center_degree for m in MOUNTAINS}) != 24:  # pragma: no cover
    raise RuntimeError("二十四山山心角存在重复")


# --------------------------------------------------------------------------
# 查询接口
# --------------------------------------------------------------------------


def normalize_degree(degree: float) -> float:
    """把任意角度规范到 [0, 360)。"""
    return float(degree) % 360.0


def mountain_at(degree: float) -> Mountain:
    """角度 -> 二十四山。

    边界约定：山的区间为 [center-7.5, center+7.5)，即左闭右开。
    因此 7.5° 归「癸」，352.5° 归「子」。

    >>> mountain_at(0).name
    '子'
    >>> mountain_at(180).name
    '午'
    >>> mountain_at(7.5).name
    '癸'
    >>> mountain_at(352.5).name
    '子'
    """
    d = normalize_degree(degree)
    index = int((d + HALF_SPAN) // SPAN_DEGREE) % 24
    return MOUNTAINS[index]


def degree_of(name: str) -> float:
    """山名 -> 山心角。非法名抛 KeyError（不静默兜底）。"""
    return get_mountain(name).center_degree


def get_mountain(name: str) -> Mountain:
    """按名取山，带友好报错。"""
    try:
        return MOUNTAIN_BY_NAME[name]
    except KeyError:
        raise KeyError(f"未知二十四山：{name!r}（合法值：{''.join(MOUNTAIN_ORDER)}）") from None


def index_of(name: str) -> int:
    return get_mountain(name).index


def opposite(name: str) -> str:
    """取对宫山（相差 180° = 12 位）。

    >>> opposite("子")
    '午'
    >>> opposite("午")
    '子'
    """
    return MOUNTAINS[(index_of(name) + 12) % 24].name


def is_opposite(a: str, b: str) -> bool:
    """判定两山是否互为对宫（相差 180°）。"""
    return (index_of(a) - index_of(b)) % 24 == 12


def angular_distance(a: float, b: float) -> float:
    """两角的最小夹角（0~180）。"""
    diff = abs(normalize_degree(a) - normalize_degree(b)) % 360.0
    return min(diff, 360.0 - diff)


def mountains_in_span(start: float, end: float) -> list[Mountain]:
    """返回 [start, end) 角度区间覆盖到的山（按角度升序）。

    用于罗盘扫描：从「鱼丝线起点」到「终点」扫过哪些山。
    """
    s, e = normalize_degree(start), normalize_degree(end)
    if s == e:
        return []

    step = SPAN_DEGREE / 4.0  # 3.75°，细于半山宽，避免漏采
    out: list[Mountain] = []
    seen: set[str] = set()
    cursor = s
    while True:
        m = mountain_at(cursor)
        if m.name not in seen:
            seen.add(m.name)
            out.append(m)
        cursor += step
        if len(out) >= 24 or (cursor - s) >= ((e - s) % 360.0 or 360.0):
            break
    return out


__all__ = [
    "MOUNTAIN_ORDER", "MOUNTAINS", "MOUNTAIN_BY_NAME", "Mountain", "Kind",
    "SPAN_DEGREE", "HALF_SPAN", "GUA_OF_MOUNTAIN", "MOUNTAIN_OF_GUA", "SANYUAN",
    "normalize_degree", "mountain_at", "degree_of", "get_mountain", "index_of",
    "opposite", "is_opposite", "angular_distance", "mountains_in_span",
]
