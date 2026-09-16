"""BaziChart —— 八字排盘的聚合结果。

关键设计：
1. **排盘只走 `lunar-python`，绝不自行推算历法**（RULE-001）
2. 但**同时提供纯口诀推导函数** `hour_pillar_by_rule` / `month_pillar_by_rule`，
   用于**交叉校验**历法库结果 —— 这是本模块最重要的自我验证机制
3. 输出严格分层：`to_facts()` = FACT（只读事实）/ `to_tradition()` = TRADITION（传统规则描述）
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..constants import (
    DIZHI,
    ELEMENT_CN,
    GAN_ELEMENT,
    TIANGAN,
    ZHI_CANGGAN,
    ZHI_SHENGXIAO,
    nayin_of,
    shishen,
)
from ..exceptions import InvalidInputError
from .calendar import BirthInput, ResolvedBirth, resolve_birth
from .strength import DayMasterStrength, assess_strength
from .wuxing import FiveElementStats, count_elements

PILLAR_ORDER = ("year", "month", "day", "hour")
PILLAR_CN = {"year": "年柱", "month": "月柱", "day": "日柱", "hour": "时柱"}


# --------------------------------------------------------------------------
# 纯口诀推导 —— 用于交叉校验历法库（RULE-001 的自证机制）
# --------------------------------------------------------------------------


def hour_pillar_by_rule(day_gan: str, hour_zhi: str) -> str:
    """五鼠遁（日上起时）：由日干 + 时支推时柱干支。

    口诀：甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸何方发，壬子是真途。

    >>> hour_pillar_by_rule("乙", "辰")
    '庚辰'
    >>> hour_pillar_by_rule("辛", "辰")
    '壬辰'
    """
    if day_gan not in GAN_ELEMENT or hour_zhi not in ZHI_SHENGXIAO:
        raise InvalidInputError(f"非法日干/时支：{day_gan!r} / {hour_zhi!r}")
    gan_index = (TIANGAN.index(day_gan) * 2 + DIZHI.index(hour_zhi)) % 10
    return TIANGAN[gan_index] + hour_zhi


def month_pillar_by_rule(year_gan: str, month_zhi: str) -> str:
    """五虎遁（年上起月）：由**节气年干** + 月支推月柱干支。

    口诀：甲己之年丙作首，乙庚之岁戊为头，丙辛必定寻庚起，丁壬壬位顺行流，戊癸之年甲寅求。

    >>> month_pillar_by_rule("辛", "酉")
    '丁酉'
    >>> month_pillar_by_rule("甲", "寅")
    '丙寅'
    """
    if year_gan not in GAN_ELEMENT or month_zhi not in ZHI_SHENGXIAO:
        raise InvalidInputError(f"非法年干/月支：{year_gan!r} / {month_zhi!r}")
    offset = (DIZHI.index(month_zhi) - 2) % 12  # 寅月为岁首
    gan_index = (TIANGAN.index(year_gan) * 2 + 2 + offset) % 10
    return TIANGAN[gan_index] + month_zhi


# --------------------------------------------------------------------------
# 排盘结果
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BaziChart:
    """八字命盘 —— FACT 层的事实载体。"""

    resolved: ResolvedBirth
    pillars: dict[str, str]            # {"year": "辛酉", ...}
    lunar_label: str                   # 农历表述
    shengxiao: str
    solar_term: str | None             # 当前所处节气（前一个节）
    next_solar_term: str | None
    jieqi_month: str | None            # 月柱所依据的节气月
    xun_kong: dict[str, str]           # 各柱空亡
    tai_yuan: str | None               # 胎元
    ming_gong: str | None              # 命宫
    simple_stats: FiveElementStats
    hidden_stats: FiveElementStats
    strength: DayMasterStrength
    sect: int = 2

    # ---------------- 便捷属性 ----------------

    @property
    def day_master(self) -> str:
        return self.pillars["day"][0]

    @property
    def day_element(self) -> str:
        return GAN_ELEMENT[self.day_master]

    @property
    def month_branch(self) -> str:
        return self.pillars["month"][1]

    @property
    def pillar_list(self) -> list[str]:
        return [self.pillars[k] for k in PILLAR_ORDER]

    @property
    def nayin(self) -> dict[str, str]:
        return {PILLAR_CN[k]: nayin_of(v) for k, v in self.pillars.items()}

    @property
    def shishen_gan(self) -> dict[str, str]:
        """各柱天干对日主的十神（日柱本身为「日主」）。"""
        out: dict[str, str] = {}
        for key in PILLAR_ORDER:
            gan = self.pillars[key][0]
            out[PILLAR_CN[key]] = "日主" if key == "day" else shishen(self.day_master, gan)
        return out

    @property
    def shishen_zhi(self) -> dict[str, list[str]]:
        """各柱地支藏干对日主的十神。"""
        return {
            PILLAR_CN[key]: [shishen(self.day_master, g) for g in ZHI_CANGGAN[self.pillars[key][1]]]
            for key in PILLAR_ORDER
        }

    # ---------------- 自检 ----------------

    def verify_rule_consistency(self) -> list[str]:
        """用纯口诀交叉校验历法库结果，返回不一致项（空列表 = 全部自洽）。

        这是 RULE-001 的落地：**确定性结果必须能被独立规则验证**。

        晚子时（23:00~24:00 的子时）存在流派差异，检查器按 `sect` 分别处理：
        - `sect=2`（lunar-python 默认）：日柱算**当天**，但时柱按**次日日干**推
          （子时属次日之气）—— 此时时柱不可由本盘日柱推出，属正常现象
        - `sect=1`：日柱算**次日**，日柱与时柱同源，可直接由本盘日柱推出

        实测依据（2024-06-01 23:00）：sect=1 → 丁酉日/庚子时（同源自洽）；
        sect=2 → 丙申日/庚子时（时柱来自次日丁酉）。两者均为通行口径，不是错误。
        """
        problems: list[str] = []

        day_gan = self.pillars["day"][0]
        hour_zhi = self.pillars["hour"][1]
        expected_hour = hour_pillar_by_rule(day_gan, hour_zhi)
        convention = "本日"

        if expected_hour != self.pillars["hour"] and hour_zhi == "子" and self.sect == 2:
            # 晚子时 + sect=2：时柱按次日日干推
            from ..constants import ganzhi_from_index, jiazi_index

            next_day_gan = ganzhi_from_index(jiazi_index(self.pillars["day"]) + 1)[0]
            expected_hour = hour_pillar_by_rule(next_day_gan, hour_zhi)
            convention = "次日（晚子时惯例）"

        if expected_hour != self.pillars["hour"]:
            problems.append(
                f"时柱不符五鼠遁：历法库给 {self.pillars['hour']}，按{convention}日干推导为 {expected_hour}"
            )

        expected_month = month_pillar_by_rule(self.pillars["year"][0], self.pillars["month"][1])
        if expected_month != self.pillars["month"]:
            problems.append(
                f"月柱不符五虎遁：历法库给 {self.pillars['month']}，口诀推导为 {expected_month}"
            )

        for key, value in self.pillars.items():
            if len(value) != 2 or value[0] not in TIANGAN or value[1] not in DIZHI:
                problems.append(f"{PILLAR_CN[key]}干支非法：{value}")
            elif TIANGAN.index(value[0]) % 2 != DIZHI.index(value[1]) % 2:
                problems.append(f"{PILLAR_CN[key]}阴阳不匹配（不存在此组合）：{value}")

        return problems

    def hour_rule_convention(self) -> str:
        """返回时柱所遵循的口径，供报告层如实标注。"""
        expected_same = hour_pillar_by_rule(self.pillars["day"][0], self.pillars["hour"][1])
        if expected_same == self.pillars["hour"]:
            return "本日日干起时"
        if self.pillars["hour"][1] == "子" and self.sect == 2:
            return "晚子时：时柱按次日日干起（日柱仍算当日）"
        return "不一致（详见 rule_consistency）"

    # ---------------- 分层输出 ----------------

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：确定性计算结果，AI 不可修改。"""
        return {
            "pillars": dict(self.pillars),
            "pillar_list": self.pillar_list,
            "day_master": self.day_master,
            "day_element": ELEMENT_CN[self.day_element],
            "shengxiao": self.shengxiao,
            "lunar": self.lunar_label,
            "solar_datetime_used": self.resolved.solar_dt.strftime("%Y-%m-%d %H:%M"),
            "solar_term": self.solar_term,
            "next_solar_term": self.next_solar_term,
            "nayin": self.nayin,
            "xun_kong": self.xun_kong,
            "tai_yuan": self.tai_yuan,
            "ming_gong": self.ming_gong,
            "five_elements_simple": self.simple_stats.to_dict(),
            "five_elements_hidden": self.hidden_stats.to_dict(),
            "time_correction": {
                "true_solar_applied": self.resolved.solar_term_shift_minutes != 0.0,
                "shift_minutes": round(self.resolved.solar_term_shift_minutes, 2),
                "utc_offset_hours": self.resolved.utc_offset_hours,
                "late_zi_sect": self.sect,
            },
            "rule_consistency": self.verify_rule_consistency(),
            "warnings": list(self.resolved.warnings),
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：传统术数规则的派生描述（非 AI 生成）。"""
        fav = "、".join(ELEMENT_CN[e] for e in self.strength.favorable) or "—"
        unfav = "、".join(ELEMENT_CN[e] for e in self.strength.unfavorable) or "—"
        return {
            "ten_gods": self.shishen_gan,
            "ten_gods_hidden": self.shishen_zhi,
            "day_master_strength": self.strength.to_dict(),
            "summary": (
                f"日主{self.day_master}（{ELEMENT_CN[self.day_element]}），"
                f"生于{self.month_branch}月，判为{self.strength.verdict}；"
                f"喜用 {fav}，忌神 {unfav}。"
            ),
            "uncertainties": list(self.strength.uncertainties),
            "note": "旺衰与用神属流派规则，结论不唯一；此处采用扶抑法，仅供参考。",
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": self.to_facts(),
            "tradition": self.to_tradition(),
            "input": self.resolved.to_dict(),
        }


# --------------------------------------------------------------------------
# 排盘入口
# --------------------------------------------------------------------------


def calculate_bazi(
    birth: BirthInput | None = None,
    *,
    sect: int = 2,
    resolved: ResolvedBirth | None = None,
) -> BaziChart:
    """八字排盘。传入 `birth` 或已归一化的 `resolved`。

    Args:
        birth: 出生信息
        sect: 晚子时流派（透传 `lunar-python`）。
            **2 = 默认**：晚子时**日柱算当天**，时柱按**次日日干**起；
            **1**：晚子时日柱算**次日**，日柱与时柱同源。
            实测见 `verify_rule_consistency` 文档。两者均为通行口径。
        resolved: 已完成归一的结果（避免重复解析时区）
    """
    if resolved is None:
        if birth is None:
            raise InvalidInputError("必须提供 birth 或 resolved 之一")
        resolved = resolve_birth(birth)

    from lunar_python import Solar

    dt = resolved.solar_dt
    lunar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second).getLunar()
    ec = lunar.getEightChar()
    ec.setSect(sect)

    pillars = {
        "year": ec.getYear(),
        "month": ec.getMonth(),
        "day": ec.getDay(),
        "hour": ec.getTime(),
    }

    simple = count_elements(list(pillars.values()), include_hidden=False)
    hidden = count_elements(list(pillars.values()), include_hidden=True)
    strength = assess_strength(list(pillars.values()), stats=hidden)

    prev_jieqi = lunar.getPrevJieQi()
    next_jieqi = lunar.getNextJieQi()

    return BaziChart(
        resolved=resolved,
        pillars=pillars,
        lunar_label=lunar.toString(),
        shengxiao=lunar.getYearShengXiao(),
        solar_term=prev_jieqi.getName() if prev_jieqi else None,
        next_solar_term=next_jieqi.getName() if next_jieqi else None,
        jieqi_month=prev_jieqi.getName() if prev_jieqi else None,
        xun_kong={
            "年柱": ec.getYearXunKong(),
            "月柱": ec.getMonthXunKong(),
            "日柱": ec.getDayXunKong(),
            "时柱": ec.getTimeXunKong(),
        },
        tai_yuan=ec.getTaiYuan(),
        ming_gong=ec.getMingGong(),
        simple_stats=simple,
        hidden_stats=hidden,
        strength=strength,
        sect=sect,
    )


__all__ = [
    "BaziChart", "calculate_bazi", "PILLAR_ORDER", "PILLAR_CN",
    "hour_pillar_by_rule", "month_pillar_by_rule",
]
