"""bazi —— 八字排盘模块。

子模块职责：
- `calendar`  输入归一（公历/农历、时区、夏令时、真太阳时）
- `wuxing`    五行统计（本气 / 藏干两种口径）
- `strength`  日主旺衰与用神（**流派相关，标注不确定性**）
- `chart`     聚合为 `BaziChart`，输出 FACT / TRADITION 两层
"""

from .calendar import BirthInput, ResolvedBirth, resolve_birth, true_solar_time
from .chart import BaziChart, calculate_bazi
from .strength import DayMasterStrength, assess_strength
from .wuxing import FiveElementStats, count_elements

__all__ = [
    "BirthInput",
    "ResolvedBirth",
    "resolve_birth",
    "true_solar_time",
    "BaziChart",
    "calculate_bazi",
    "FiveElementStats",
    "count_elements",
    "DayMasterStrength",
    "assess_strength",
]
