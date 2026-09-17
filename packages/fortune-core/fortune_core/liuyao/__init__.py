"""六爻 —— **起卦**（`gua`）+ **装卦**（`najia` / `zhuang`）。

分层设计：
1. `gua`     —— 起卦与卦象：爻值 → 本卦 / 变卦 / 上下卦 / 动爻。**不含随机数**（RULE-007）
2. `najia`   —— 装卦的**固定属性表**：八卦纳甲、京房八宫卦序、世应、六神、地支六冲六合
3. `zhuang`  —— 装卦聚合：把起卦结果 + 日辰/月建**装配**成完整卦盘（六亲/世应/六神/伏神/用神）

工程铁律：
- RULE-001 全部由确定性代码算出，**不含 LLM 调用**，**不依赖网络**
- RULE-006 流派相关项（用神取用法、旺衰口径）集中在 `zhuang.py` 显式声明
- RULE-007 每个公开函数都有单元测试
"""

from __future__ import annotations

from .gua import (
    GUA_ORDER_BY_NUMBER,
    LIUSHISI_GUA,
    YAO_NAMES,
    LiuYaoResult,
    cast_liuyao,
    gua_by_number,
    hour_zhi_number,
)
from .najia import (
    GUA_PALACE,
    LIUCHONG_GUA,
    LIUHE_GUA,
    LIUSHEN_ORDER,
    NAJIA,
    NAJIA_GAN,
    PALACE_GUA,
    PALACE_STAGE,
    SHI_YING_YAO,
    ZHI_CHONG,
    ZHI_LIUHE,
    derive_palace_gua,
    is_liuchong_gua,
    is_liuhe_gua,
    liu_qin,
    liu_shen_for_day,
    najia_of,
    palace_of,
    palace_stage_of,
    shi_ying_of,
    yao_of_lower_upper,
    zhi_chong,
    zhi_liuhe,
)
from .zhuang import (
    ALL_QIN,
    MARRIAGE_YONGSHEN,
    YONGSHEN_BY_TOPIC,
    LiuYaoDivination,
    YaoDetail,
    day_relation_of,
    month_state_of,
    najia_ganzhi_for,
    xun_kong_of,
    yongshen_of,
    zhuang_gua,
)

__all__ = [
    # 起卦
    "LIUSHISI_GUA", "GUA_ORDER_BY_NUMBER", "YAO_NAMES",
    "LiuYaoResult", "cast_liuyao", "gua_by_number", "hour_zhi_number",
    # 装卦 · 固定属性（najia）
    "NAJIA", "NAJIA_GAN", "najia_of",
    "PALACE_GUA", "GUA_PALACE", "PALACE_STAGE", "derive_palace_gua",
    "SHI_YING_YAO", "palace_of", "palace_stage_of", "shi_ying_of",
    "LIUSHEN_ORDER", "liu_shen_for_day",
    "ZHI_CHONG", "ZHI_LIUHE", "zhi_chong", "zhi_liuhe",
    "LIUCHONG_GUA", "LIUHE_GUA", "is_liuchong_gua", "is_liuhe_gua",
    "liu_qin", "yao_of_lower_upper",
    # 装卦 · 聚合（zhuang）
    "YaoDetail", "LiuYaoDivination", "zhuang_gua", "najia_ganzhi_for", "ALL_QIN",
    "YONGSHEN_BY_TOPIC", "MARRIAGE_YONGSHEN", "yongshen_of",
    "xun_kong_of", "month_state_of", "day_relation_of",
]
