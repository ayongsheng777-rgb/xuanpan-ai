"""六爻起卦 —— 确定性推卦，不用随机数冒充「天意」。

三种起卦方式（对应材料 §17.2）：
1. `yao_values`  直接给 6 个爻值（6=老阴 7=少阳 8=少阴 9=老阳）—— **最可测、最推荐**
2. `coins`       给 6 次掷币结果，每次 3 枚铜钱的阴阳（True=背=阳 3 分，False=字=阴 2 分）
3. `numbers` / `time`  梅花易数数字/时间起卦

设计原则（RULE-007）：**同样的输入必得同样的卦**，故本模块**不含 `random`**。
需要"随机摇卦"时，随机源在调用方（客户端），结果作为 `yao_values` 传入并留痕。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ..constants import (
    DIZHI,
    ELEMENT_CN,
    GUA_XIANTIAN_NUMBER,
    GUA_ELEMENT,
    GUA_YAO,
)
from ..exceptions import InvalidInputError

# 先天八卦序（1..8），用于取余定卦：余 0 归 8（坤）
GUA_ORDER_BY_NUMBER: tuple[str, ...] = ("乾", "兑", "离", "震", "巽", "坎", "艮", "坤")
_YAO_TO_GUA: dict[tuple[int, int, int], str] = {v: k for k, v in GUA_YAO.items()}

# 六十四卦表：{下卦(内) : {上卦(外) : 卦名}} —— 双向已按上下卦结构逐条核对
LIUSHISI_GUA: dict[str, dict[str, str]] = {
    "乾": {"乾": "乾", "兑": "夬", "离": "大有", "震": "大壮", "巽": "小畜", "坎": "需", "艮": "大畜", "坤": "泰"},
    "兑": {"乾": "履", "兑": "兑", "离": "睽", "震": "归妹", "巽": "中孚", "坎": "节", "艮": "损", "坤": "临"},
    "离": {"乾": "同人", "兑": "革", "离": "离", "震": "丰", "巽": "家人", "坎": "既济", "艮": "贲", "坤": "明夷"},
    "震": {"乾": "无妄", "兑": "随", "离": "噬嗑", "震": "震", "巽": "益", "坎": "屯", "艮": "颐", "坤": "复"},
    "巽": {"乾": "姤", "兑": "大过", "离": "鼎", "震": "恒", "巽": "巽", "坎": "井", "艮": "蛊", "坤": "升"},
    "坎": {"乾": "讼", "兑": "困", "离": "未济", "震": "解", "巽": "涣", "坎": "坎", "艮": "蒙", "坤": "师"},
    "艮": {"乾": "遁", "兑": "咸", "离": "旅", "震": "小过", "巽": "渐", "坎": "蹇", "艮": "艮", "坤": "谦"},
    "坤": {"乾": "否", "兑": "萃", "离": "晋", "震": "豫", "巽": "观", "坎": "比", "艮": "剥", "坤": "坤"},
}

# 爻值语义：六/七/八/九
YAO_NAMES: dict[int, str] = {6: "老阴", 7: "少阳", 8: "少阴", 9: "老阳"}
YAO_IS_YANG: dict[int, bool] = {6: False, 7: True, 8: False, 9: True}
YAO_IS_MOVING: dict[int, bool] = {6: True, 7: False, 8: False, 9: True}


@dataclass(frozen=True, slots=True)
class LiuYaoResult:
    """六爻起卦结果。"""

    yao_values: tuple[int, ...]        # 6 爻，自下而上（初爻 → 上爻）
    original_gua: str                  # 本卦名
    changed_gua: str | None            # 变卦名（无动爻时为 None）
    upper_gua: str                     # 上卦（外卦）
    lower_gua: str                     # 下卦（内卦）
    changed_upper_gua: str | None
    changed_lower_gua: str | None
    moving_positions: tuple[int, ...]  # 动爻位置（1..6）
    method: str

    @property
    def upper_element(self) -> str:
        return GUA_ELEMENT[self.upper_gua]

    @property
    def lower_element(self) -> str:
        return GUA_ELEMENT[self.lower_gua]

    @property
    def has_moving(self) -> bool:
        return bool(self.moving_positions)

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：起卦的确定性结果。"""
        return {
            "method": self.method,
            "yao_values": list(self.yao_values),
            "yao_names": [YAO_NAMES[v] for v in self.yao_values],
            "original_gua": self.original_gua,
            "upper_gua": self.upper_gua,
            "lower_gua": self.lower_gua,
            "changed_gua": self.changed_gua,
            "changed_upper_gua": self.changed_upper_gua,
            "changed_lower_gua": self.changed_lower_gua,
            "moving_positions": list(self.moving_positions),
            "has_moving": self.has_moving,
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：卦象五行与体用关系（不含吉凶断语）。"""
        body = self.lower_gua  # 体卦（默认内卦为体）
        use = self.upper_gua   # 用卦
        return {
            "upper_gua_element": ELEMENT_CN[self.upper_element],
            "lower_gua_element": ELEMENT_CN[self.lower_element],
            "body_gua": body,
            "use_gua": use,
            "note": "体用与吉凶断法属流派规则，此处只输出卦象与五行，不含断语",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}


# --------------------------------------------------------------------------
# 内部工具
# --------------------------------------------------------------------------


def _gua_from_yao(yao: Sequence[int]) -> str:
    """三爻（自下而上）→ 八卦名。"""
    key = (int(yao[0]), int(yao[1]), int(yao[2]))
    try:
        return _YAO_TO_GUA[key]
    except KeyError:
        raise InvalidInputError(f"非法三爻组合：{key}（每爻须为 0 或 1）") from None


def _split_gua(yao_values: Sequence[int]) -> tuple[str, str]:
    """六爻 → (下卦, 上卦)。"""
    lower = _gua_from_yao(yao_values[:3])
    upper = _gua_from_yao(yao_values[3:6])
    return lower, upper


def _gua_name(lower: str, upper: str) -> str:
    try:
        return LIUSHISI_GUA[lower][upper]
    except KeyError:  # pragma: no cover - 表已完整覆盖 8×8
        raise InvalidInputError(f"六十四卦表缺失组合：上{upper} 下{lower}") from None


def _validate_yao_values(values: Sequence[int]) -> tuple[int, ...]:
    if len(values) != 6:
        raise InvalidInputError(f"六爻起卦需恰好 6 爻，收到 {len(values)}")
    out = []
    for v in values:
        if v not in YAO_NAMES:
            raise InvalidInputError(f"爻值须为 6/7/8/9，收到 {v!r}")
        out.append(int(v))
    return tuple(out)


def _build(values: tuple[int, ...], method: str) -> LiuYaoResult:
    yang_flags = [YAO_IS_YANG[v] for v in values]
    lower, upper = _split_gua(yang_flags)
    moving = tuple(i + 1 for i, v in enumerate(values) if YAO_IS_MOVING[v])

    changed_gua = changed_upper = changed_lower = None
    if moving:
        flipped = list(yang_flags)
        for pos in moving:
            flipped[pos - 1] = not flipped[pos - 1]
        changed_lower, changed_upper = _split_gua(flipped)
        changed_gua = _gua_name(changed_lower, changed_upper)

    return LiuYaoResult(
        yao_values=values,
        original_gua=_gua_name(lower, upper),
        changed_gua=changed_gua,
        upper_gua=upper,
        lower_gua=lower,
        changed_upper_gua=changed_upper,
        changed_lower_gua=changed_lower,
        moving_positions=moving,
        method=method,
    )


# --------------------------------------------------------------------------
# 起卦入口
# --------------------------------------------------------------------------


def cast_liuyao(
    *,
    yao_values: Sequence[int] | None = None,
    coins: Sequence[Sequence[bool]] | None = None,
    numbers: tuple[int, int] | None = None,
    time_info: dict[str, int] | None = None,
) -> LiuYaoResult:
    """起卦。四种方式择一，优先级：yao_values > coins > numbers > time_info。

    Args:
        yao_values: 6 个爻值（6/7/8/9），自下而上
        coins: 6 次掷币，每次 3 枚，``True`` = 背（阳，3 分），``False`` = 字（阴，2 分）
        numbers: 梅花易数报数起卦 ``(数1, 数2)``
        time_info: 时间起卦，需 ``{"year_zhi": 1..12, "month": 1..12, "day": 1..30, "hour_zhi": 1..12}``

    >>> cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7]).original_gua
    '乾'
    >>> cast_liuyao(coins=[[True, True, True]] * 6).original_gua
    '乾'
    >>> cast_liuyao(yao_values=[9, 7, 7, 7, 7, 7]).changed_gua
    '姤'
    """
    if yao_values is not None:
        return _build(_validate_yao_values(yao_values), "yao_values")

    if coins is not None:
        if len(coins) != 6:
            raise InvalidInputError(f"掷币需恰好 6 次，收到 {len(coins)}")
        values = []
        for toss in coins:
            if len(toss) != 3:
                raise InvalidInputError(f"每次须掷 3 枚，收到 {len(toss)} 枚")
            total = sum(3 if c else 2 for c in toss)
            values.append(total)
        return _build(_validate_yao_values(values), "coins")

    if numbers is not None:
        a, b = numbers
        if a <= 0 or b <= 0:
            raise InvalidInputError(f"报数须为正整数，收到 {numbers!r}")
        upper = GUA_ORDER_BY_NUMBER[a % 8 - 1]
        lower = GUA_ORDER_BY_NUMBER[b % 8 - 1]
        moving = (a + b) % 6 or 6
        yang = list(GUA_YAO[lower]) + list(GUA_YAO[upper])
        values = [9 if (yang[i] and i + 1 == moving) else
                  (6 if (not yang[i] and i + 1 == moving) else
                   (7 if yang[i] else 8))
                  for i in range(6)]
        return _build(_validate_yao_values(values), "numbers")

    if time_info is not None:
        required = ("year_zhi", "month", "day", "hour_zhi")
        missing = [k for k in required if k not in time_info]
        if missing:
            raise InvalidInputError(f"时间起卦缺少字段：{missing}")
        y, m, d, h = (time_info[k] for k in required)
        if not all(1 <= v <= 12 for v in (y, h)) or not 1 <= m <= 12 or not 1 <= d <= 30:
            raise InvalidInputError("时间起卦字段越界（年支/时支 1..12，月 1..12，日 1..30）")
        upper = GUA_ORDER_BY_NUMBER[(y + m + d) % 8 - 1]
        lower = GUA_ORDER_BY_NUMBER[(y + m + d + h) % 8 - 1]
        moving = (y + m + d + h) % 6 or 6
        yang = list(GUA_YAO[lower]) + list(GUA_YAO[upper])
        values = [9 if (yang[i] and i + 1 == moving) else
                  (6 if (not yang[i] and i + 1 == moving) else
                   (7 if yang[i] else 8))
                  for i in range(6)]
        return _build(_validate_yao_values(values), "time")

    raise InvalidInputError("必须提供 yao_values / coins / numbers / time_info 之一")


def gua_by_number(number: int) -> str:
    """先天卦数（1..8）→ 卦名。

    >>> gua_by_number(1)
    '乾'
    >>> gua_by_number(8)
    '坤'
    """
    if not 1 <= number <= 8:
        raise InvalidInputError(f"卦数须在 1..8，收到 {number}")
    return GUA_ORDER_BY_NUMBER[number - 1]


def hour_zhi_number(hour: int) -> int:
    """小时（0..23）→ 时辰序号（子=1 … 亥=12）。"""
    if not 0 <= hour <= 23:
        raise InvalidInputError(f"hour 须在 0..23，收到 {hour}")
    idx = ((hour + 1) // 2) % 12
    return idx + 1


__all__ = [
    "LIUSHISI_GUA", "GUA_ORDER_BY_NUMBER", "YAO_NAMES",
    "LiuYaoResult", "cast_liuyao", "gua_by_number", "hour_zhi_number",
]
