"""一百二十分金（Fenjin120）—— V1 交付**几何层**，干支层走规则表。

结构：二十四山 × 每山 5 分金 = 120 格，每格 3°。

分层设计（严格遵守 RULE-001 / RULE-008）：
- **几何层** `[已确认]`：格位序号、所属山、起止角、中心角 —— 纯几何，可完全确定，本模块实现
- **干支层** `[待验证]`：每格的干支与「旺相孤虚」标注 —— **属流派规则，必须由规则表提供**。
  规则表缺失时返回 `None`，**绝不凭理论推算**（见 `DomainDataMissingError` 设计说明）。

规则表文件格式（`data/fenjin120.json`）::

    {
      "default": {
        "子": ["甲子", "丙子", null, "庚子", null],
        ...
      }
    }

值为 `null` 表示该格按此流派为空亡/不用。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

from .constants import jiazi_index
from .mountain24 import HALF_SPAN, MOUNTAINS, Mountain, get_mountain, normalize_degree

FENJIN_PER_MOUNTAIN: Final[int] = 5
FENJIN_SPAN: Final[float] = 360.0 / (24 * FENJIN_PER_MOUNTAIN)  # 3°
FENJIN_HALF: Final[float] = FENJIN_SPAN / 2.0  # 1.5°

DEFAULT_TABLE_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "fenjin120.json"


@dataclass(frozen=True, slots=True)
class FenjinCell:
    """一个分金格。"""

    index: int              # 全局序号 0..119
    mountain: Mountain      # 所属山
    sub_index: int          # 格内序 0..4（从该山起始角起算）
    start_degree: float
    center_degree: float
    end_degree: float
    ganzhi: str | None = None    # 干支，规则表缺失 → None
    usable: bool | None = None   # 旺相可用 / 孤虚不用；未知 → None

    @property
    def label(self) -> str:
        """展示用标签，缺少干支时退化为角度区间。"""
        if self.ganzhi:
            return f"{self.ganzhi}分金"
        return f"{self.mountain.name}山 {self.sub_index + 1}/5 格"


def _cell_geometry(index: int) -> tuple[Mountain, int, float, float, float]:
    mountain_index = index // FENJIN_PER_MOUNTAIN
    sub = index % FENJIN_PER_MOUNTAIN
    mountain = MOUNTAINS[mountain_index]
    start = normalize_degree(mountain.start_degree + sub * FENJIN_SPAN)
    center = normalize_degree(start + FENJIN_HALF)
    end = normalize_degree(start + FENJIN_SPAN)
    return mountain, sub, start, center, end


# --------------------------------------------------------------------------
# 规则表加载（cache：表是静态领域数据）
# --------------------------------------------------------------------------


@lru_cache(maxsize=8)
def load_fenjin_table(path: str | None = None) -> dict[str, dict[str, list[str | None]]]:
    """加载分金干支规则表。文件不存在 → 返回空表（**不编造**）。"""
    p = Path(path) if path else DEFAULT_TABLE_PATH
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"分金规则表格式错误，应为 dict：{p}")

    # 启动期校验：干支合法性 + 每山 5 格
    for school, table in data.items():
        for mountain_name, cells in table.items():
            get_mountain(mountain_name)  # 山名非法直接抛错
            if len(cells) != FENJIN_PER_MOUNTAIN:
                raise ValueError(f"[{school}] {mountain_name}山 应有 {FENJIN_PER_MOUNTAIN} 格，实为 {len(cells)}")
            for gz in cells:
                if gz is not None:
                    jiazi_index(gz)  # 干支非法直接抛错
    return data


def fenjin_cell(index: int, *, school: str = "default", table_path: str | None = None) -> FenjinCell:
    """按全局序号构造分金格（含规则表查得的干支）。"""
    if not 0 <= index < 120:
        raise ValueError(f"分金序号须在 0..119，收到 {index}")

    mountain, sub, start, center, end = _cell_geometry(index)
    ganzhi: str | None = None
    usable: bool | None = None

    table = load_fenjin_table(table_path)
    school_table = table.get(school)
    if school_table and mountain.name in school_table:
        ganzhi = school_table[mountain.name][sub]
        usable = ganzhi is not None

    return FenjinCell(
        index=index,
        mountain=mountain,
        sub_index=sub,
        start_degree=start,
        center_degree=center,
        end_degree=end,
        ganzhi=ganzhi,
        usable=usable,
    )


def fenjin_at(degree: float, *, school: str = "default", table_path: str | None = None) -> FenjinCell:
    """角度 -> 分金格。

    注意：120 格的**格网起点是 352.5°**（子山起始角），不是 0°。
    因为子山中心在 0°，其 5 格对称分布于 352.5°~7.5°，故 0° 落在子山第 3 格（全局序号 2）。

    >>> fenjin_at(0).index
    2
    >>> round(fenjin_at(0).center_degree, 1)
    0.0
    >>> fenjin_at(352.5).index
    0
    >>> fenjin_at(7.5).index
    5
    """
    d = normalize_degree(degree)
    index = int((d + HALF_SPAN) // FENJIN_SPAN) % 120
    return fenjin_cell(index, school=school, table_path=table_path)


def fenjin_cells_of(mountain_name: str) -> list[FenjinCell]:
    """取某山的 5 个分金格（仅几何，不含干支）。"""
    m = get_mountain(mountain_name)
    base = m.index * FENJIN_PER_MOUNTAIN
    return [_geometry_only(i) for i in range(base, base + FENJIN_PER_MOUNTAIN)]


def _geometry_only(index: int) -> FenjinCell:
    mountain, sub, start, center, end = _cell_geometry(index)
    return FenjinCell(
        index=index,
        mountain=mountain,
        sub_index=sub,
        start_degree=start,
        center_degree=center,
        end_degree=end,
    )


def table_available(school: str = "default", table_path: str | None = None) -> bool:
    """该流派的干支规则表是否已就绪。UI 据此决定是否展示分金干支。"""
    return school in load_fenjin_table(table_path)


__all__ = [
    "FENJIN_PER_MOUNTAIN", "FENJIN_SPAN", "FENJIN_HALF",
    "DEFAULT_TABLE_PATH", "FenjinCell",
    "load_fenjin_table", "fenjin_cell", "fenjin_at", "fenjin_cells_of", "table_available",
]
