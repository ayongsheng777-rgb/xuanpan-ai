"""五行统计 —— 八字的事实层数据。

两种口径**必须显式区分**，否则不同实现给出的"五行分布"会互相打架：

1. `simple`（本气口径）：只数 4 天干 + 4 地支本气，共 8 个单位
2. `hidden`（藏干口径）：天干各 1.0，地支按藏干权重 `(1.0, 0.5, 0.3)` 分摊

> `[推测]` 藏干权重 `(1.0, 0.5, 0.3)` 为通行做法之一，不同流派取值略有差异。
> 因此本模块**不把权重写死为"真理"**，而是作为可覆盖参数暴露，
> 并在 `to_dict()` 中回写实际使用的权重，保证结果可追溯（材料 §46 第三原则）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Iterable, Sequence

from ..constants import (
    CN_ELEMENT,
    DIZHI,
    ELEMENT_CN,
    GAN_ELEMENT,
    TIANGAN,
    ZHI_CANGGAN,
    ZHI_ELEMENT,
)
from ..exceptions import InvalidInputError

ELEMENTS: Final[tuple[str, ...]] = ("wood", "fire", "earth", "metal", "water")

#：地支藏干默认权重（本气 / 中气 / 余气）
DEFAULT_HIDDEN_WEIGHTS: Final[tuple[float, ...]] = (1.0, 0.5, 0.3)


@dataclass(frozen=True, slots=True)
class FiveElementStats:
    """五行分布统计结果。"""

    counts: dict[str, float]           # 五行 -> 力量（本气口径下为整数）
    weights: tuple[float, ...]         # 实际使用的藏干权重
    include_hidden: bool               # 是否含藏干口径

    @property
    def total(self) -> float:
        return sum(self.counts.values())

    def percentage(self) -> dict[str, float]:
        t = self.total
        if t == 0:
            return {e: 0.0 for e in ELEMENTS}
        return {e: round(self.counts.get(e, 0.0) / t * 100, 2) for e in ELEMENTS}

    @property
    def missing(self) -> list[str]:
        """完全缺失的五行（中文名）。本气口径下才有"缺"的概念。"""
        return [ELEMENT_CN[e] for e in ELEMENTS if self.counts.get(e, 0.0) == 0]

    @property
    def strongest(self) -> str:
        return max(ELEMENTS, key=lambda e: self.counts.get(e, 0.0))

    @property
    def weakest(self) -> str:
        return min(ELEMENTS, key=lambda e: self.counts.get(e, 0.0))

    def cn(self) -> dict[str, float]:
        """中文键版本，便于直接展示。"""
        return {ELEMENT_CN[e]: self.counts.get(e, 0.0) for e in ELEMENTS}

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": "hidden" if self.include_hidden else "simple",
            "counts": self.cn(),
            "counts_en": self.counts,
            "percentage": {ELEMENT_CN[e]: v for e, v in self.percentage().items()},
            "missing": self.missing,
            "strongest": ELEMENT_CN[self.strongest],
            "weakest": ELEMENT_CN[self.weakest],
            "hidden_weights": list(self.weights) if self.include_hidden else None,
        }


def _explode_pillars(pillars: Sequence[str]) -> tuple[list[str], list[str]]:
    gans, zhis = [], []
    for p in pillars:
        if len(p) != 2 or p[0] not in TIANGAN or p[1] not in DIZHI:
            raise InvalidInputError(f"非法干支柱：{p!r}")
        gans.append(p[0])
        zhis.append(p[1])
    return gans, zhis


def count_elements(
    pillars: Sequence[str],
    *,
    include_hidden: bool = True,
    hidden_weights: Sequence[float] = DEFAULT_HIDDEN_WEIGHTS,
) -> FiveElementStats:
    """统计五行分布。

    Args:
        pillars: 四柱干支，如 ``["辛酉", "丁酉", "乙未", "庚辰"]``（年/月/日/时）
        include_hidden: False 时只计本气（天干 + 地支本气）
        hidden_weights: 地支藏干权重，按本气→余气顺序取用

    >>> s = count_elements(["甲子", "丙寅", "戊午", "庚申"], include_hidden=False)
    >>> [s.counts[k] for k in ("wood", "fire", "earth", "metal", "water")]
    [2.0, 2.0, 1.0, 2.0, 1.0]

    明现木为 2（天干「甲」＋ 地支「寅」本气），不是 3 —— 逐字可数：

    >>> s = count_elements(["甲子", "丙寅", "戊午", "庚申"])   # 含藏干：本气1.0 / 余气0.5 / 0.3
    >>> [round(s.counts[k], 2) for k in ("wood", "fire", "earth", "metal", "water")]
    [2.0, 2.5, 2.1, 2.0, 1.5]
    """
    if not pillars:
        raise InvalidInputError("pillars 不能为空")
    if include_hidden and len(hidden_weights) < 3:
        raise InvalidInputError("hidden_weights 至少需 3 个元素")

    gans, zhis = _explode_pillars(pillars)
    counts: dict[str, float] = {e: 0.0 for e in ELEMENTS}

    for gan in gans:
        counts[GAN_ELEMENT[gan]] += 1.0

    for zhi in zhis:
        if not include_hidden:
            counts[ZHI_ELEMENT[zhi]] += 1.0
            continue
        for idx, gan in enumerate(ZHI_CANGGAN[zhi]):
            weight = hidden_weights[min(idx, len(hidden_weights) - 1)]
            counts[GAN_ELEMENT[gan]] += weight

    return FiveElementStats(
        counts=counts,
        weights=tuple(hidden_weights),
        include_hidden=include_hidden,
    )


def element_of(character: str) -> str:
    """单字（天干或地支）→ 五行英文键。

    >>> element_of("甲")
    'wood'
    >>> element_of("酉")
    'metal'
    """
    if character in GAN_ELEMENT:
        return GAN_ELEMENT[character]
    if character in ZHI_ELEMENT:
        return ZHI_ELEMENT[character]
    raise InvalidInputError(f"既非天干也非地支：{character!r}")


def cn_to_key(cn: str) -> str:
    """中文五行 → 英文键。

    >>> cn_to_key("金")
    'metal'
    """
    try:
        return CN_ELEMENT[cn]
    except KeyError:
        raise InvalidInputError(f"未知五行：{cn!r}") from None


def keys_to_cn(keys: Iterable[str]) -> list[str]:
    return [ELEMENT_CN[k] for k in keys]


__all__ = [
    "ELEMENTS", "DEFAULT_HIDDEN_WEIGHTS", "FiveElementStats",
    "count_elements", "element_of", "cn_to_key", "keys_to_cn",
]
