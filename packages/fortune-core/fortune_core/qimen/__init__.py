"""奇门遁甲 —— 三式之一。

分层设计：

1. `constants` —— **固定属性表**：洛书九宫配卦、九星/八门配宫、三奇六仪顺序、
   二十四节气上元局数表、外环环序、驿马表。全部为数据，无逻辑。
2. `pan`       —— **定局与排盘**：节气 → 三元 → 局数 → 地盘 →
   天盘（沿环转动）→ 九星（同步）→ 八门（按时支步数）→ 八神（阳顺阴逆）。

工程铁律：

- RULE-001 全部由确定性代码算出，**不含 LLM 调用**、**不依赖网络**
- RULE-006 流派项集中在 `pan.SCHOOLS`（当前仅拆补法）；未实现项在
  `QimenChart.uncertainties` 中**显式声明**，不假装完备
- RULE-007 每个公开函数都有单元测试（`tests/test_qimen.py`）

**已知未覆盖**（详见 `uncertainties`）：置闰法、真太阳时校正、
十干克应/格局判断（属解读层，不在内核）。
"""

from __future__ import annotations

from .constants import (
    BAMEN_BY_GONG,
    BAMEN_JIXIONG,
    BASHEN_ALIAS,
    BASHEN_ORDER,
    CENTER_HOST,
    CENTER_PALACE,
    GONG_DIRECTION,
    GONG_ELEMENT,
    GONG_GRID_POS,
    GONG_GUA,
    JIUXING_BY_GONG,
    JIUXING_JIXIONG,
    LIUYI,
    Qiyi_ORDER,
    RING_ORDER,
    SANQI,
    SHANGYUAN_JUSHU,
    XUNSHOU_TO_YI,
    YANG_DUN_JIEQI,
    YIMA_BY_SANHE,
    YIN_DUN_JIEQI,
    is_yang_dun,
    jushu_of,
    jushu_table,
)
from .pan import (
    SCHOOLS,
    UNCERTAINTIES,
    YUAN_LABEL,
    ZHI_TO_GONG,
    Dingju,
    QimenChart,
    QimenPalace,
    build_dipan,
    cast_qimen,
    resolve_dingju,
    xun_kong_of,
    xunshou_of,
    yima_of,
)

__all__ = [
    # 固定属性表
    "GONG_GUA", "GONG_DIRECTION", "GONG_ELEMENT", "GONG_GRID_POS", "RING_ORDER",
    "CENTER_PALACE", "CENTER_HOST",
    "LIUYI", "SANQI", "Qiyi_ORDER", "XUNSHOU_TO_YI",
    "JIUXING_BY_GONG", "BAMEN_BY_GONG", "BAMEN_JIXIONG", "JIUXING_JIXIONG",
    "BASHEN_ORDER", "BASHEN_ALIAS", "YIMA_BY_SANHE",
    "YANG_DUN_JIEQI", "YIN_DUN_JIEQI", "SHANGYUAN_JUSHU",
    "is_yang_dun", "jushu_of", "jushu_table",
    # 定局与排盘
    "SCHOOLS", "UNCERTAINTIES", "YUAN_LABEL", "ZHI_TO_GONG",
    "Dingju", "QimenPalace", "QimenChart",
    "build_dipan", "cast_qimen", "resolve_dingju",
    "xun_kong_of", "xunshou_of", "yima_of",
]
