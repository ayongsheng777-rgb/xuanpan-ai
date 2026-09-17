"""大运 / 流年 / 小运 —— 八字运程排布。

对应 RULE-001：**起运与大运排布完全走 `lunar-python` 的 `getYun`**，不自行推算历法。
本模块只做封装与分层输出，不做任何历法/节气计算。

可信度标注：
- `[已确认]` 起运岁数、大运干支、每步流年/小运 —— 来自 `lunar-python`（权威历法库）
- `[待验证]` 大运排法流派（阳男阴女顺排 / 阴男阳女逆排）依赖 `lunar-python` 的 `getYun(gender)`，
  其中 gender 参数语义：**1 = 男，0 = 女**（已实测确认）

边界约定：
- 未填性别（`gender=None` 或 `other`）时，大运无法确定顺逆，**不排大运**，
  返回 `dyun_available=False` 并说明原因（RULE-008 不静默猜测）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..exceptions import InvalidInputError
from .calendar import Gender


@dataclass(frozen=True, slots=True)
class DaYunStep:
    """一步大运。index=0 是「起运前」的空档（干支为空串）。"""
    index: int            # 从 0 起；0 表示起运前
    gan_zhi: str          # 起运前为空串
    start_year: int
    end_year: int
    start_age: int
    end_age: int
    xun_kong: str         # 该步大运的旬空

    @property
    def is_before_start(self) -> bool:
        return self.gan_zhi == ""


@dataclass(frozen=True, slots=True)
class LiuNianStep:
    """一个流年。"""
    year: int
    age: int
    gan_zhi: str
    xun_kong: str


@dataclass(frozen=True, slots=True)
class YunResult:
    """大运排布结果。"""

    gender: Gender | None
    available: bool                # 是否成功排出（未填性别为 False）
    reason: str | None             # available=False 时的说明
    forward: bool | None           # 顺排 / 逆排
    start_age_text: str | None     # 起运表述（如「5 年 7 个月 10 天」）
    start_solar: str | None        # 起运公历
    da_yun: list[DaYunStep]
    liu_nian: dict[int, list[LiuNianStep]]    # 大运 index -> 该步流年
    xiao_yun: dict[int, list[LiuNianStep]]    # 大运 index -> 该步小运

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "forward": self.forward,
            "start_age_text": self.start_age_text,
            "start_solar": self.start_solar,
            "da_yun": [
                {
                    "index": d.index,
                    "gan_zhi": d.gan_zhi,
                    "start_year": d.start_year,
                    "end_year": d.end_year,
                    "start_age": d.start_age,
                    "end_age": d.end_age,
                    "xun_kong": d.xun_kong,
                }
                for d in self.da_yun
            ],
            "liu_nian": {
                str(k): [
                    {"year": x.year, "age": x.age, "gan_zhi": x.gan_zhi, "xun_kong": x.xun_kong}
                    for x in v
                ]
                for k, v in self.liu_nian.items()
            },
            "xiao_yun": {
                str(k): [
                    {"year": x.year, "age": x.age, "gan_zhi": x.gan_zhi, "xun_kong": x.xun_kong}
                    for x in v
                ]
                for k, v in self.xiao_yun.items()
            },
        }


def calculate_yun(
    solar_dt: Any,
    gender: Gender | None,
    *,
    sect: int = 2,
) -> YunResult:
    """排大运 / 流年 / 小运。

    Args:
        solar_dt: 已归一（含真太阳时修正）的出生 `datetime`。
        gender: 出生性别，`male` 传 1、`female` 传 0；`None`/`other` 无法排大运。
        sect: 晚子时流派，透传 `lunar-python`。

    Returns:
        YunResult。性别缺失时 `available=False`，其余字段为空。
    """
    from lunar_python import Solar

    if gender not in ("male", "female"):
        return YunResult(
            gender=gender,
            available=False,
            reason="未填写性别，无法确定大运顺逆排法（阳男阴女顺排、阴男阳女逆排）",
            forward=None,
            start_age_text=None,
            start_solar=None,
            da_yun=[],
            liu_nian={},
            xiao_yun={},
        )

    lunar = Solar.fromYmdHms(
        solar_dt.year, solar_dt.month, solar_dt.day,
        solar_dt.hour, solar_dt.minute, solar_dt.second,
    ).getLunar()
    ec = lunar.getEightChar()
    ec.setSect(sect)

    yun = ec.getYun(1 if gender == "male" else 0)

    da_yun: list[DaYunStep] = []
    liu_nian: dict[int, list[LiuNianStep]] = {}
    xiao_yun: dict[int, list[LiuNianStep]] = {}

    for step in yun.getDaYun():
        idx = step.getIndex()
        da_yun.append(DaYunStep(
            index=idx,
            gan_zhi=step.getGanZhi(),
            start_year=step.getStartYear(),
            end_year=step.getEndYear(),
            start_age=step.getStartAge(),
            end_age=step.getEndAge(),
            xun_kong=step.getXunKong(),
        ))
        # 起运前（第 0 步）无干支，流年/小运也跳过
        if step.getGanZhi() == "":
            continue
        liu_nian[idx] = [
            LiuNianStep(
                year=x.getYear(),
                age=x.getAge(),
                gan_zhi=x.getGanZhi(),
                xun_kong=x.getXunKong(),
            )
            for x in step.getLiuNian()
        ]
        xiao_yun[idx] = [
            LiuNianStep(
                year=x.getYear(),
                age=x.getAge(),
                gan_zhi=x.getGanZhi(),
                xun_kong=x.getXunKong(),
            )
            for x in step.getXiaoYun()
        ]

    return YunResult(
        gender=gender,
        available=True,
        reason=None,
        forward=yun.isForward(),
        start_age_text=(
            f"{yun.getStartYear()} 年 {yun.getStartMonth()} 个月 {yun.getStartDay()} 天"
        ),
        start_solar=yun.getStartSolar().toYmd(),
        da_yun=da_yun,
        liu_nian=liu_nian,
        xiao_yun=xiao_yun,
    )


def yun_direction(year_gan_yinyang: str, gender: Gender | None) -> str | None:
    """返回大运顺逆方向（供报告层说明），性别缺失返回 None。

    规则：阳年男 / 阴年女顺排，阴年男 / 阳年女逆排。
    注意：这里的「年」是**年柱天干**的阴阳（不是日干）。
    """
    if gender not in ("male", "female"):
        return None
    yang = year_gan_yinyang == "yang"
    male = gender == "male"
    return "顺排" if yang == male else "逆排"


__all__ = [
    "DaYunStep", "LiuNianStep", "YunResult",
    "calculate_yun", "yun_direction",
]
