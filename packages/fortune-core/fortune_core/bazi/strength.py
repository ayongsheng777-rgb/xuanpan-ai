"""日主旺衰与用神 —— **流派相关模块**（对应 RULE-006）。

⚠️ 本模块的价值不在于"给出唯一正确答案"，而在于：
1. **把流派差异显式化**：阈值、权重、取用法全部可覆盖，不写死为真理
2. **把不确定性带出去**：每个结论都附 `uncertainties`，供 UI 与 AI 层引用
3. **结果可追溯**：输出中间量（得令/得地/得势/力量比），而不是只给一个结论

可信度：
- `[已确认]` 五行生克方向、十神归类
- `[推测]` 旺衰阈值（50% / 40%）与扶抑取用法为通行做法之一，非唯一标准
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ..constants import (
    DIZHI,
    ELEMENT_CN,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATES,
    GAN_ELEMENT,
    TIANGAN,
    ZHI_CANGGAN,
    ZHI_ELEMENT,
)
from ..exceptions import InvalidInputError
from .wuxing import ELEMENTS, FiveElementStats, count_elements

#：身强 / 身弱 判定阈值（同类力量占比）
STRONG_THRESHOLD: float = 0.50
WEAK_THRESHOLD: float = 0.40


@dataclass(frozen=True, slots=True)
class DayMasterStrength:
    """日主旺衰评估结果。"""

    day_master: str                       # 日干，如 "乙"
    day_element: str                      # 日主五行英文键
    month_branch: str                     # 月令地支
    month_element: str
    stats: FiveElementStats

    supported: float                      # 同类力量（比劫 + 印）
    opposing: float                       # 异类力量（食伤 + 财 + 官杀）
    support_ratio: float                  # 同类占比 0..1

    obtains_season: bool                  # 得令
    obtains_ground: bool                  # 得地
    obtains_momentum: bool                # 得势

    verdict: str                          # 身强 / 身弱 / 中和
    favorable: tuple[str, ...]            # 喜用五行（英文键）
    unfavorable: tuple[str, ...]          # 忌神五行
    uncertainties: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "day_master": self.day_master,
            "day_element": ELEMENT_CN[self.day_element],
            "month_branch": self.month_branch,
            "month_element": ELEMENT_CN[self.month_element],
            "supported": round(self.supported, 2),
            "opposing": round(self.opposing, 2),
            "support_ratio": round(self.support_ratio, 4),
            "obtains_season": self.obtains_season,
            "obtains_ground": self.obtains_ground,
            "obtains_momentum": self.obtains_momentum,
            "verdict": self.verdict,
            "favorable": [ELEMENT_CN[e] for e in self.favorable],
            "unfavorable": [ELEMENT_CN[e] for e in self.unfavorable],
            "uncertainties": list(self.uncertainties),
            "notes": list(self.notes),
        }


def _is_supporting(source: str, day_element: str) -> bool:
    """该五行是否对日主起「生扶」作用（同我 或 生我）。"""
    return source == day_element or ELEMENT_GENERATES[source] == day_element


def assess_strength(
    pillars: Sequence[str],
    *,
    strong_threshold: float = STRONG_THRESHOLD,
    weak_threshold: float = WEAK_THRESHOLD,
    stats: FiveElementStats | None = None,
) -> DayMasterStrength:
    """评估日主旺衰并给出扶抑用神。

    Args:
        pillars: 四柱，顺序为 **年、月、日、时**。日柱第 2 字为日主。
        strong_threshold: 同类占比 ≥ 该值判身强
        weak_threshold: 同类占比 ≤ 该值判身弱
        stats: 复用的五行统计（避免重复计算）

    Raises:
        InvalidInputError: 柱数不足 4 或格式非法
    """
    if len(pillars) != 4:
        raise InvalidInputError(f"需要 4 柱（年月日时），收到 {len(pillars)}")

    year, month, day, hour = pillars
    for p in pillars:
        if len(p) != 2 or p[0] not in TIANGAN or p[1] not in DIZHI:
            raise InvalidInputError(f"非法干支柱：{p!r}")

    day_master = day[0]
    day_element = GAN_ELEMENT[day_master]
    month_branch = month[1]
    month_element = ZHI_ELEMENT[month_branch]

    stats = stats or count_elements(pillars, include_hidden=True)

    supported = sum(stats.counts.get(e, 0.0) for e in ELEMENTS if _is_supporting(e, day_element))
    opposing = stats.total - supported
    ratio = supported / stats.total if stats.total else 0.0

    # ---- 得令：月令五行是否生扶日主 ----
    obtains_season = _is_supporting(month_element, day_element)

    # ---- 得地：四地支（含藏干）是否有日主同类 ----
    ground_elements: list[str] = []
    for p in (year, month, hour):
        for gan in ZHI_CANGGAN[p[1]]:
            ground_elements.append(GAN_ELEMENT[gan])
    obtains_ground = any(_is_supporting(e, day_element) for e in ground_elements)

    # ---- 得势：天干（除日干）是否有同类 ----
    obtains_momentum = any(
        _is_supporting(GAN_ELEMENT[p[0]], day_element) for p in (year, month, hour)
    )

    # ---- 判定 ----
    if ratio >= strong_threshold:
        verdict = "身强"
    elif ratio <= weak_threshold:
        verdict = "身弱"
    else:
        verdict = "中和"

    # ---- 扶抑取用 ----
    if verdict == "身弱":
        favorable = tuple(e for e in ELEMENTS if _is_supporting(e, day_element))
        unfavorable = tuple(e for e in ELEMENTS if not _is_supporting(e, day_element))
        principle = "身弱宜生扶：以印（生我）与比劫（同我）为喜，财官食伤为忌"
    elif verdict == "身强":
        favorable = tuple(e for e in ELEMENTS if not _is_supporting(e, day_element))
        unfavorable = tuple(e for e in ELEMENTS if _is_supporting(e, day_element))
        principle = "身强宜克泄耗：以官杀（克我）、财（我克）、食伤（我生）为喜，印比帮身为忌"
    else:
        favorable = ()
        unfavorable = ()
        principle = "中和之局，扶抑法不显；需结合调候、通关等法另行取用"

    notes = (
        f"得令：{'是' if obtains_season else '否'}（月令{month_branch}属{ELEMENT_CN[month_element]}，"
        f"对日主{ELEMENT_CN[day_element]}为{'生扶' if obtains_season else '克泄'}）",
        f"得地：{'是' if obtains_ground else '否'}（年/月/时支藏干中"
        f"{'存在' if obtains_ground else '不存在'}生扶日主之气）",
        f"得势：{'是' if obtains_momentum else '否'}（年/月/时干中"
        f"{'存在' if obtains_momentum else '不存在'}同类天干）",
        principle,
    )

    uncertainties: list[str] = [
        "旺衰阈值（同类占比 ≥50% 判身强、≤40% 判身弱）为通行做法之一，不同流派取值不同",
        "本版采用扶抑法（抑强扶弱）取用神；调候、通关、病药等法未纳入",
    ]
    if verdict == "中和":
        uncertainties.append("此局判为中和，扶抑法无法定出喜用，需其它取用法，结论仅供参考")

    return DayMasterStrength(
        day_master=day_master,
        day_element=day_element,
        month_branch=month_branch,
        month_element=month_element,
        stats=stats,
        supported=supported,
        opposing=opposing,
        support_ratio=ratio,
        obtains_season=obtains_season,
        obtains_ground=obtains_ground,
        obtains_momentum=obtains_momentum,
        verdict=verdict,
        favorable=favorable,
        unfavorable=unfavorable,
        uncertainties=tuple(uncertainties),
        notes=notes,
    )


__all__ = [
    "STRONG_THRESHOLD", "WEAK_THRESHOLD",
    "DayMasterStrength", "assess_strength",
]
