"""fortune-core —— 玄盘 AI 的**唯一计算内核**。

定位（材料 §46 第六原则）：
    APP、Web、MCP、未来 Agent 全部共享同一套 Fortune Core。

铁律（AGENTS.md §2.3）：
    RULE-001 确定性计算必须由代码完成
    RULE-002 LLM 不得修改计算层输出
    RULE-005 罗盘规则不得散落在 UI
    RULE-006 流派规则必须模块化
    RULE-007 所有核心算法必须有单元测试

本包**不含任何 LLM 调用**，也不依赖网络。纯函数 + 领域数据。
"""

from __future__ import annotations

__version__ = "0.1.0"

from .bazi import BaziChart, BirthInput, calculate_bazi
from .almanac import AlmanacResult, calculate_almanac
from .compass import CompassOrientation, calculate_orientation, element_relation
from .context import FortuneContext, build_context
from .duangua import BaziDuan, LiuYaoDuan, duan_bazi, duan_liuyao
from .exceptions import (
    DomainDataMissingError,
    FortuneError,
    InvalidInputError,
    OrientationConflictError,
    SchoolNotFoundError,
)
from .fenjin120 import FenjinCell, fenjin_at, fenjin_cells_of, table_available
from .liuyao import LiuYaoResult, cast_liuyao
from .mountain24 import (
    MOUNTAIN_ORDER,
    MOUNTAINS,
    Mountain,
    angular_distance,
    degree_of,
    get_mountain,
    is_opposite,
    mountain_at,
    mountains_in_span,
    normalize_degree,
    opposite,
)
from .naming import NameAnalysis, analyze_name
from .qian import QianResult, draw_qian
from .schools import DEFAULT_SCHOOL, get_school, list_schools

__all__ = [
    "__version__",
    # 二十四山 / 坐向
    "MOUNTAIN_ORDER", "MOUNTAINS", "Mountain",
    "mountain_at", "degree_of", "get_mountain", "opposite", "is_opposite",
    "angular_distance", "mountains_in_span", "normalize_degree",
    "CompassOrientation", "calculate_orientation", "element_relation",
    # 分金
    "FenjinCell", "fenjin_at", "fenjin_cells_of", "table_available",
    # 八字
    "BirthInput", "BaziChart", "calculate_bazi",
    # 黄历 / 择日
    "AlmanacResult", "calculate_almanac",
    # 六爻 / 灵签 / 姓名
    "LiuYaoResult", "cast_liuyao",
    "QianResult", "draw_qian",
    "NameAnalysis", "analyze_name",
    # 断卦
    "LiuYaoDuan", "BaziDuan", "duan_liuyao", "duan_bazi",
    # 上下文 / 流派
    "FortuneContext", "build_context",
    "DEFAULT_SCHOOL", "get_school", "list_schools",
    # 异常
    "FortuneError", "InvalidInputError", "OrientationConflictError",
    "DomainDataMissingError", "SchoolNotFoundError",
]
