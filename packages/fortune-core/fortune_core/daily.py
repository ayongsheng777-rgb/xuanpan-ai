"""每日运程 —— 出生日期定日主 × 目标日期干支的确定性推演。

定位：**传统文化娱乐参考**，不是命理定论。全部规则写死在代码里，
给定（出生日期，目标日期）必得同一结果：可复现、可测试、不调用 LLM
（RULE-001：确定性计算必须由代码完成）。

算法（前端可在「怎么算的」里原文展示）：
1. 出生日期 → 八字日柱 → 取**日主**。只用到日柱：
   出生时辰不影响日主；时辰未知时按午时（12 点）排盘，结果不变，
   这一点在接口文档里写清楚，避免 RULE-008（不得为合理而修正数据）争议。
2. 目标日期 → 日干支：**复用** `calculate_almanac`，不自算（RULE-001 复用而非自算）。
3. 日干、日支主气藏干分别对日主取十神（`shishen`）。
4. 五宫映射（十神取象，口径固定）：
     事业 ← 官杀印（官杀为事业星，印为靠山）
     财运 ← 财食伤（财星，食伤生财）
     感情 ← 官杀财食伤（互动与表达之星，不分男女）
     健康 ← 印比劫（生我、同我为底气）
     贵人 ← 比劫食伤印（同类与生助）
   星级 = 3 ＋ 天干命中(1) ＋ 地支命中(1) － 天干受制(1)，钳制到 1..5。
   受制集（每宫固定）：事业←伤官（伤官见官），财运←比劫（劫财），
   感情←比劫（争合），健康←官杀食伤（克泄），贵人←官杀（压力）。
5. 开运物（全确定性）：
   生日主之五行 → 幸运色 / 吉方；日干支序号 → 幸运数；
   生/同日主五行之地支 → 吉时（取前三，顺地支序）。

输出分 `facts` / `tradition` 两层，与黄历接口保持同一渲染约定。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from .almanac import calculate_almanac
from .bazi.calendar import BirthInput
from .bazi.chart import calculate_bazi
from .constants import (
    DIZHI,
    ELEMENT_CN,
    ELEMENT_GENERATES,
    GAN_ELEMENT,
    TIANGAN,
    ZHI_CANGGAN,
    ZHI_ELEMENT,
    shishen,
)
from .exceptions import InvalidInputError

# 未知时辰时的默认排盘时辰。只影响时柱，不影响日主（每日运程唯一用到的字段）。
DEFAULT_HOUR_WHEN_UNKNOWN: Final[int] = 12

# 五宫：名称 → （本宫星集， 受制集， 宜动作， 忌动作）
_DOMAINS: Final[tuple[tuple[str, frozenset[str], frozenset[str], str, str], ...]] = (
    ("事业", frozenset({"正官", "七杀", "正印", "偏印"}), frozenset({"伤官"}), "推进重要工作", "重大决策"),
    ("财运", frozenset({"正财", "偏财", "食神", "伤官"}), frozenset({"比肩", "劫财"}), "处理财务事宜", "大额支出"),
    ("感情", frozenset({"正官", "七杀", "正财", "偏财", "食神", "伤官"}), frozenset({"比肩", "劫财"}), "主动联络亲友", "意气用事"),
    ("健康", frozenset({"正印", "偏印", "比肩", "劫财"}), frozenset({"七杀", "正官", "食神", "伤官"}), "早睡早起", "熬夜透支"),
    ("贵人", frozenset({"比肩", "劫财", "食神", "伤官", "正印", "偏印"}), frozenset({"七杀", "正官"}), "多与人交流", "独断专行"),
)

_ELEMENT_COLOR: Final[dict[str, str]] = {
    "wood": "青绿",
    "fire": "朱红",
    "earth": "明黄",
    "metal": "银白",
    "water": "玄青",
}

_ELEMENT_DIRECTION: Final[dict[str, str]] = {
    "wood": "东方",
    "fire": "南方",
    "earth": "中央",
    "metal": "西方",
    "water": "北方",
}

# 地支 → 时辰起止（24 小时制），顺序即地支序
_ZHI_HOURS: Final[tuple[tuple[str, str], ...]] = (
    ("子", "23:00–01:00"),
    ("丑", "01:00–03:00"),
    ("寅", "03:00–05:00"),
    ("卯", "05–07:00"),
    ("辰", "07:00–09:00"),
    ("巳", "09:00–11:00"),
    ("午", "11:00–13:00"),
    ("未", "13:00–15:00"),
    ("申", "15:00–17:00"),
    ("酉", "17:00–19:00"),
    ("戌", "19:00–21:00"),
    ("亥", "21:00–23:00"),
)


@dataclass(frozen=True, slots=True)
class DomainScore:
    """一宫的评分。"""

    name: str
    stars: int          # 1..5
    tag: str            # 宜 / 平 / 慎
    reason: str         # 哪颗星起了作用（可展示）

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "stars": self.stars, "tag": self.tag, "reason": self.reason}


@dataclass(frozen=True, slots=True)
class DailyFortune:
    """一日运程结果。"""

    target_date: str
    day_ganzhi: str
    day_master: str
    day_master_element: str   # 中文：木/火/土/金/水
    stem_shishen: str         # 日干对日主的十神
    branch_shishen: str       # 日支主气藏干对日主的十神
    domains: tuple[DomainScore, ...]
    lucky_color: str
    lucky_color_element: str  # 中文五行
    lucky_numbers: tuple[int, int]
    lucky_direction: str
    lucky_hours: tuple[str, ...]
    focus_yi: str
    focus_ji: str
    summary: str
    birth_hour_known: bool

    def to_facts(self) -> dict[str, Any]:
        return {
            "date": self.target_date,
            "day_ganzhi": self.day_ganzhi,
            "day_master": self.day_master,
            "day_master_element": self.day_master_element,
            "stem_shishen": self.stem_shishen,
            "branch_shishen": self.branch_shishen,
            "domains": [d.to_dict() for d in self.domains],
            "lucky": {
                "color": self.lucky_color,
                "color_element": self.lucky_color_element,
                "numbers": list(self.lucky_numbers),
                "direction": self.lucky_direction,
                "hours": list(self.lucky_hours),
            },
            "focus_yi": self.focus_yi,
            "focus_ji": self.focus_ji,
        }

    def to_tradition(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "note": (
                "规则口径：五宫映射与星级公式见 fortune_core.daily 模块文档；"
                "十神取象为传统常用口径之一，不同流派有差异。"
                "内容属传统文化娱乐参考，不构成决策建议。"
            ),
            "uncertainties": (
                [] if self.birth_hour_known else
                ["出生时辰未知，按午时排盘；每日运程只用到日柱（日主），时辰不影响结果"]
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}


def _validate_day(d: date, field: str) -> None:
    if not isinstance(d, date):
        raise InvalidInputError(f"{field} 须为日期，收到 {d!r}")
    if not date(1900, 1, 1) <= d <= date(2100, 12, 31):
        raise InvalidInputError(f"{field} 须在 1900-01-01..2100-12-31，收到 {d.isoformat()}")


def daily_fortune(
    birth_date: date,
    target: date | None = None,
    *,
    birth_hour: int | None = None,
) -> DailyFortune:
    """算一日运程。

    Args:
        birth_date: 出生公历日期（只用到日柱）。
        target: 目标日期，省略即今天。
        birth_hour: 出生小时（0..23），未知传 None（默认按午时，不影响日主）。
    """
    _validate_day(birth_date, "birth_date")
    target = target or date.today()
    _validate_day(target, "target")
    if birth_hour is not None and not 0 <= birth_hour <= 23:
        raise InvalidInputError(f"birth_hour 须在 0..23，收到 {birth_hour!r}")

    # 1. 日主（只取日柱；时辰不影响）
    birth = BirthInput(
        year=birth_date.year,
        month=birth_date.month,
        day=birth_date.day,
        hour=birth_hour if birth_hour is not None else DEFAULT_HOUR_WHEN_UNKNOWN,
    )
    birth.validate()
    chart = calculate_bazi(birth)
    day_master = chart.day_master
    me_element = GAN_ELEMENT[day_master]

    # 2. 目标日干支（复用黄历，不自算）
    alm = calculate_almanac(target)
    day_ganzhi = alm.day_ganzhi
    day_gan, day_zhi = day_ganzhi[0], day_ganzhi[1]

    # 3. 十神
    stem_ss = shishen(day_master, day_gan)
    branch_main_gan = ZHI_CANGGAN[day_zhi][0]
    branch_ss = shishen(day_master, branch_main_gan)

    # 4. 五宫评分
    domains: list[DomainScore] = []
    for name, fav, drain, yi_act, ji_act in _DOMAINS:
        hits: list[str] = []
        stars = 3
        if stem_ss in fav:
            stars += 1
            hits.append(f"日干透「{stem_ss}」")
        if branch_ss in fav:
            stars += 1
            hits.append(f"日支藏「{branch_ss}」")
        drained = False
        if stem_ss in drain:
            stars -= 1
            drained = True
            hits.append(f"日干「{stem_ss}」受制")
        stars = max(1, min(5, stars))
        tag = "宜" if stars >= 4 else ("慎" if stars <= 2 else "平")
        reason = "，".join(hits) if hits else "日干支无本宫星透出"
        if drained and stars <= 2:
            reason += "，宜收敛"
        domains.append(DomainScore(name=name, stars=stars, tag=tag, reason=reason))

    # 5. 开运物：生日主之五行
    helper_element = next(k for k, v in ELEMENT_GENERATES.items() if v == me_element)
    lucky_color = _ELEMENT_COLOR[helper_element]
    lucky_direction = _ELEMENT_DIRECTION[helper_element]
    lucky_numbers = (TIANGAN.index(day_gan) + 1, DIZHI.index(day_zhi) + 1)
    lucky_hours = tuple(
        f"{zhi}时（{span}）"
        for zhi, span in _ZHI_HOURS
        if ZHI_ELEMENT[zhi] in (helper_element, me_element)
    )[:3]

    # 宜/忌焦点：星级最高/最低宫（并列按五宫固定顺序取首个，确定性）
    order = list(range(len(domains)))
    best_i = max(order, key=lambda i: (domains[i].stars, -i))
    worst_i = min(order, key=lambda i: (domains[i].stars, i))
    best, worst = domains[best_i], domains[worst_i]
    focus_yi = f"宜{_DOMAINS[best_i][3]}（{best.name}{best.stars}星）"
    focus_ji = f"慎{_DOMAINS[worst_i][4]}（{worst.name}{worst.stars}星）"

    summary = (
        f"{target.isoformat()}（{day_ganzhi}日），日主{day_master}"
        f"（{ELEMENT_CN[me_element]}）：{best.name}运最佳，{worst.name}宜谨慎。"
        f"幸运色{lucky_color}，吉位{lucky_direction}。"
    )

    return DailyFortune(
        target_date=target.isoformat(),
        day_ganzhi=day_ganzhi,
        day_master=day_master,
        day_master_element=ELEMENT_CN[me_element],
        stem_shishen=stem_ss,
        branch_shishen=branch_ss,
        domains=tuple(domains),
        lucky_color=lucky_color,
        lucky_color_element=ELEMENT_CN[helper_element],
        lucky_numbers=lucky_numbers,
        lucky_direction=lucky_direction,
        lucky_hours=lucky_hours,
        focus_yi=focus_yi,
        focus_ji=focus_ji,
        summary=summary,
        birth_hour_known=birth_hour is not None,
    )


__all__ = [
    "DEFAULT_HOUR_WHEN_UNKNOWN",
    "DailyFortune",
    "DomainScore",
    "daily_fortune",
]
