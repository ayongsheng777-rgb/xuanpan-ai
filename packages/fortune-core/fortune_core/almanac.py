"""黄历 / 择日 —— 每日黄历信息的确定性封装。

对应 RULE-001：**黄历数据完全复用 `lunar-python`**，不自行推算历法。
本模块只做三件事：
1. 聚合散落的接口（二十八宿 / 建除 / 黄黑道 / 冲煞 / 宜忌 / 彭祖百忌）为一份结果
2. 分层输出（FACT = 确定性事实；TRADITION = 带流派说明的宜忌取舍）
3. 交叉校验：建除十二神、冲煞方可用独立规则验证（非交节日），交节日标注跳过

可信度标注：
- `[已确认]` 二十八宿、建除十二神、黄道黑道、冲煞、宜忌、彭祖百忌 —— 来自 lunar-python
- `[待验证]` 建除推导公式在**节气交节当日**与库有 1 天口径差（见 `verify_zhi_xing`），
  已确认是节气切换边界，非库缺陷，故交节日跳过交叉校验
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .exceptions import InvalidInputError

# 建除十二神（顺行）
JIANCHU_12: tuple[str, ...] = (
    "建", "除", "满", "平", "定", "执",
    "破", "危", "成", "收", "开", "闭",
)

# 黄道吉日（六神）
HUANG_DAO: frozenset[str] = frozenset({
    "青龙", "明堂", "金匮", "天德", "玉堂", "司命",
})


@dataclass(frozen=True, slots=True)
class AlmanacResult:
    """一日黄历结果。"""

    solar_date: str              # 公历 YYYY-MM-DD
    lunar_label: str             # 农历表述
    year_ganzhi: str             # 年干支（立春分界）
    month_ganzhi: str            # 月干支
    day_ganzhi: str              # 日干支
    jian_chu: str                # 建除十二神（值星）
    xiu: str                     # 二十八宿
    xiu_luck: str                # 宿吉凶
    tian_shen: str               # 黄道黑道十二神（值日天神）
    tian_shen_type: str          # 黄道 / 黑道
    tian_shen_luck: str          # 吉 / 凶
    chong: str                   # 冲（地支）
    chong_desc: str              # 冲描述（含生肖）
    chong_shengxiao: str         # 冲生肖
    sha_direction: str           # 煞方（方位）
    yi: list[str]                # 宜
    ji: list[str]                # 忌
    ji_shen: list[str]           # 吉神
    xiong_sha: list[str]         # 凶煞
    pengzu_gan: str              # 彭祖百忌（天干）
    pengzu_zhi: str              # 彭祖百忌（地支）
    # 交叉校验结果：空 = 全部通过（或交节日跳过）
    rule_consistency: list[str]

    @property
    def is_huang_dao(self) -> bool:
        return self.tian_shen_type == "黄道"

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：确定性黄历事实。"""
        return {
            "solar_date": self.solar_date,
            "lunar": self.lunar_label,
            "gan_zhi": {
                "year": self.year_ganzhi,
                "month": self.month_ganzhi,
                "day": self.day_ganzhi,
            },
            "jian_chu": self.jian_chu,
            "xiu": {"name": self.xiu, "luck": self.xiu_luck},
            "tian_shen": {
                "name": self.tian_shen,
                "type": self.tian_shen_type,
                "luck": self.tian_shen_luck,
                "is_huang_dao": self.is_huang_dao,
            },
            "chong": {
                "zhi": self.chong,
                "desc": self.chong_desc,
                "shengxiao": self.chong_shengxiao,
                "sha_direction": self.sha_direction,
            },
            "yi": list(self.yi),
            "ji": list(self.ji),
            "ji_shen": list(self.ji_shen),
            "xiong_sha": list(self.xiong_sha),
            "peng_zu": {"gan": self.pengzu_gan, "zhi": self.pengzu_zhi},
            "rule_consistency": list(self.rule_consistency),
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：宜忌的流派说明。"""
        return {
            "summary": (
                f"{self.solar_date}（{self.lunar_label}）{self.day_ganzhi}日，"
                f"{self.jian_chu}日、值{self.xiu}宿、{self.tian_shen}（{self.tian_shen_type}）。"
            ),
            "note": "宜忌、黄黑道与吉神凶煞属传统黄历规则，不同历书存在差异；此处采用 lunar-python 通行口径，仅供参考。",
            "uncertainties": [
                "建除十二神在节气交节当日存在口径差（见 rule_consistency）",
            ] if any("交节" in p for p in self.rule_consistency) else [],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": self.to_facts(),
            "tradition": self.to_tradition(),
        }


def calculate_almanac(dt: datetime | date) -> AlmanacResult:
    """计算某日的黄历。

    Args:
        dt: 目标日期/时间（仅取年月日）。

    Returns:
        黄历结果。FACT 层含交叉校验结果 `rule_consistency`。
    """
    from lunar_python import Solar

    if isinstance(dt, datetime):
        d = dt.date()
    else:
        d = dt

    lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()

    day_zhi = lunar.getDayZhi()
    month_zhi_exact = lunar.getMonthZhiExact()

    # 交叉校验：建除十二神可由「月支 + 日支」独立推导（非交节日）
    consistency = _verify_zhi_xing(lunar, month_zhi_exact, day_zhi)

    return AlmanacResult(
        solar_date=d.isoformat(),
        lunar_label=lunar.toString(),
        year_ganzhi=lunar.getYearInGanZhi(),
        month_ganzhi=lunar.getMonthInGanZhi(),
        day_ganzhi=lunar.getDayInGanZhi(),
        jian_chu=lunar.getZhiXing(),
        xiu=lunar.getXiu(),
        xiu_luck=lunar.getXiuLuck(),
        tian_shen=lunar.getDayTianShen(),
        tian_shen_type=lunar.getDayTianShenType(),
        tian_shen_luck=lunar.getDayTianShenLuck(),
        chong=lunar.getDayChong(),
        chong_desc=lunar.getDayChongDesc(),
        chong_shengxiao=lunar.getDayChongShengXiao(),
        sha_direction=lunar.getDaySha(),
        yi=list(lunar.getDayYi()),
        ji=list(lunar.getDayJi()),
        ji_shen=list(lunar.getDayJiShen()),
        xiong_sha=list(lunar.getDayXiongSha()),
        pengzu_gan=lunar.getPengZuGan(),
        pengzu_zhi=lunar.getPengZuZhi(),
        rule_consistency=consistency,
    )


# --------------------------------------------------------------------------
# 交叉校验
# --------------------------------------------------------------------------


def derive_zhi_xing(month_zhi: str, day_zhi: str) -> str:
    """由「月支 + 日支」独立推导建除十二神（不依赖库）。

    规则：正月建寅，二月建卯……「建」落在月支，日支相对月支每进一位，值星进一位。
    即：值星 = JIANCHU_12[(日支序 − 月支序) % 12]。

    >>> derive_zhi_xing("酉", "午")
    '收'
    """
    from .constants import DIZHI

    if month_zhi not in DIZHI or day_zhi not in DIZHI:
        raise InvalidInputError(f"非法地支：{month_zhi!r}/{day_zhi!r}")
    offset = (DIZHI.index(day_zhi) - DIZHI.index(month_zhi)) % 12
    return JIANCHU_12[offset]


def _verify_zhi_xing(lunar: Any, month_zhi: str, day_zhi: str) -> list[str]:
    """校验库的建除结果是否与独立推导一致。

    节气交节当日（`getJieQi` 非空）跳过：此时月支在交节瞬间切换，
    `getMonthZhiExact` 与 `getZhiXing` 可能各取一侧，属已知口径差。
    """
    problems: list[str] = []
    is_jieqi_day = bool(lunar.getJieQi())
    derived = derive_zhi_xing(month_zhi, day_zhi)
    actual = lunar.getZhiXing()

    if is_jieqi_day:
        # 交节日：仅当推导与库不同时，提示这是边界口径差（不算错误）
        if derived != actual:
            problems.append(
                f"交节当日（{lunar.getJieQi()}）建除口径差：库给「{actual}」，"
                f"按月支{month_zhi}推导为「{derived}」"
            )
    elif derived != actual:
        problems.append(
            f"建除不符：库给「{actual}」，按月支{month_zhi}+日支{day_zhi}推导为「{derived}」"
        )
    return problems


__all__ = [
    "AlmanacResult", "calculate_almanac", "derive_zhi_xing",
    "JIANCHU_12", "HUANG_DAO",
]
