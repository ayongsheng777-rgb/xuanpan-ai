"""大六壬 —— 三式之二。

分层设计：

1. `constants` —— **固定属性表**：十干寄宫、月将名目、中气换将表、十二天将、
   贵人起法、九宗门优先级。全部为数据，无逻辑。
2. `pan`       —— **排盘**：月将（中气换将）→ 天地盘（月将加时）→ 四课 →
   三传（九宗门）→ 十二天将（贵人起，顺逆布）。

工程铁律：

- RULE-001 全部由确定性代码算出，**不含 LLM 调用**、**不依赖网络**
- RULE-006 流派项集中在 `pan.SCHOOLS`（当前仅通行本）；未实现项在
  `LiurenChart.uncertainties` 中**显式声明**，不假装完备
- RULE-007 每个公开函数都有单元测试（`packages/fortune-core/tests/test_liuren.py`）

**已知未覆盖**：不在此重列 —— 未覆盖项的**唯一真源**是 `constants.UNCERTAINTIES`
（当前 6 项：贵人起法流派、涉害深度量化、课体完整性、真太阳时校正、
昼夜贵口径、晚子时口径）。起课结果与 `/liuren/meta` 都直接取自它。

> 为什么不在本文档重列：初版这里手抄了 4 项，后来补的「昼夜贵口径」「晚子时口径」
> 两项就没跟上 —— 同一份清单两处维护，必然腐化。要看真实清单请看常量。

**本模块刻意不做的事**：不下吉凶断语。天将吉凶、三传五行都作为 FACT 给出，
不合成"吉/凶"结论 —— 那是上层解读（`duangua.py` / AI 层）的职责（RULE-001 / RULE-008）。
"""

from __future__ import annotations

from .constants import (
    CHONG,
    DAYTIME_ZHI,
    DIZHI,
    GAN_ELEMENT,
    GAN_INDEX,
    GUIREN,
    JIGONG,
    JIUZONGMEN,
    JIUZONGMEN_NOTE,
    KE,
    LIUHE,
    SANHE,
    SCHOOLS,
    SELF_XING,
    SHUN_GROUND,
    SIJI,
    SIMENG,
    SIZHONG,
    TIANJIANG_JIXIONG,
    TIANJIANG_ORDER,
    TIANJIANG_SHORT,
    UNCERTAINTIES,
    XING,
    YANG_ZHI,
    YUEJIANG_NAME,
    ZHI_ELEMENT,
    ZHI_INDEX,
    ZHONGQI_ORDER,
    ZHONGQI_TO_YUEJIANG,
)
from .pan import (
    Chuan,
    Lesson,
    LiurenChart,
    Palace,
    cast_liuren,
    dun_gan_of,
    four_lessons,
    generals_of,
    ground_of,
    heaven_plate,
    month_general_of,
    san_chuan,
)

__all__ = [
    # 固定属性表 —— 基础
    "DIZHI", "ZHI_INDEX", "GAN_INDEX", "YANG_ZHI",
    "ZHI_ELEMENT", "GAN_ELEMENT", "KE", "CHONG", "LIUHE", "SANHE",
    "XING", "SELF_XING", "SIMENG", "SIZHONG", "SIJI",
    # 十干寄宫
    "JIGONG",
    # 月将
    "YUEJIANG_NAME", "ZHONGQI_TO_YUEJIANG", "ZHONGQI_ORDER",
    # 十二天将
    "TIANJIANG_ORDER", "TIANJIANG_SHORT", "TIANJIANG_JIXIONG",
    "GUIREN", "DAYTIME_ZHI", "SHUN_GROUND",
    # 九宗门
    "JIUZONGMEN", "JIUZONGMEN_NOTE",
    # 流派与未覆盖项
    "SCHOOLS", "UNCERTAINTIES",
    # 排盘
    "Chuan", "Lesson", "LiurenChart", "Palace",
    "cast_liuren", "dun_gan_of", "four_lessons", "generals_of",
    "ground_of", "heaven_plate", "month_general_of", "san_chuan",
]
