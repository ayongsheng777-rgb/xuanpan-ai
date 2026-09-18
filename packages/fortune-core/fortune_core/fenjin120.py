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
import logging
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

_LOG = logging.getLogger(__name__)


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
    """加载分金干支规则表 —— **严格接口**。

    文件不存在 → 返回空表（**不编造**）；**格式错误 → 抛异常**。

    这里刻意不吞异常，因为它是**校验脚本与测试**的入口：一张写错的表必须
    在补表环节就被拦下，而不是被悄悄当成"没有表"。运行期请走
    `_load_or_error()` —— 那条路径把格式错误降级为「空表 + 一条告警」。
    """
    p = Path(path) if path else DEFAULT_TABLE_PATH
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"分金规则表格式错误，应为 dict：{p}")

    # 启动期校验：干支合法性 + 每山 5 格
    for school, table in data.items():
        if not isinstance(table, dict):
            raise ValueError(f"分金规则表 [{school}] 应为 dict（山名 -> 5 格干支）")
        for mountain_name, cells in table.items():
            get_mountain(mountain_name)  # 山名非法直接抛错
            if not isinstance(cells, list):
                raise ValueError(f"[{school}] {mountain_name}山 应为 list，实为 {type(cells).__name__}")
            if len(cells) != FENJIN_PER_MOUNTAIN:
                raise ValueError(f"[{school}] {mountain_name}山 应有 {FENJIN_PER_MOUNTAIN} 格，实为 {len(cells)}")
            for gz in cells:
                if gz is not None:
                    if not isinstance(gz, str):
                        raise ValueError(
                            f"[{school}] {mountain_name}山 的格值应为 str 或 null，"
                            f"实为 {type(gz).__name__}"
                        )
                    jiazi_index(gz)  # 干支非法直接抛错
    return data


def _cache_key(path: str | None) -> str:
    return str(Path(path)) if path else str(DEFAULT_TABLE_PATH)


@lru_cache(maxsize=8)
def _load_or_error(
    path: str,
) -> tuple[dict[str, dict[str, list[str | None]]] | None, str | None]:
    """**运行期**加载：不可用 → `(None, 原因)`，并只告警一次。

    为什么必须有这一层：`load_fenjin_table()` 的启动期校验会抛
    `KeyError`（山名非法）/`ValueError`（顶层非 dict、格数≠5、干支非法），
    而调用方 `compass.py`、`context.py`、`meta.py` **都没有 try/except** ——
    一张写错的表会让罗盘整个接口 500（实测：某山少写一格即复现；
    只有管理台的 `admin.py` 包了 try/except）。

    降级为「几何格位 + `available=False`」而不是崩溃，与 RULE-003
    「无法确认时返回不确定」一致。**但不是静默**：告警日志 + `table_load_error()`
    都能给出具体原因，管理台据此显示"表坏了"而不是"表没有"。

    告警只打一次是**借 lru_cache 实现的**：函数体只执行一次，日志自然只出现一次
    （否则坏表会在每个请求上刷屏）。
    """
    try:
        return load_fenjin_table(path), None
    except Exception as exc:  # noqa: BLE001 - 规则表是外部数据，任何解析/校验失败都应降级
        reason = f"{type(exc).__name__}: {exc}"
        _LOG.warning(
            "分金规则表加载失败，分金退化为「仅几何格位」：%s（%s）", path, reason
        )
        return None, reason


def table_load_error(table_path: str | None = None) -> str | None:
    """规则表不可用的原因；正常时返回 `None`。供管理台区分「表没提供」与「表写坏了」。"""
    return _load_or_error(_cache_key(table_path))[1]


def clear_fenjin_cache() -> None:
    """清空规则表缓存。

    测试必须调它，否则上一用例的坏表结果会被缓存到下一用例
    （`lru_cache` 不区分测试边界）——那正是"假绿"的经典来源。

    用 `getattr` 取 `cache_clear` 而不是直接调：测试常用 `monkeypatch`
    把 `load_fenjin_table` 换成普通函数来模拟"磁盘上的表写坏了"，
    此时那个名字上没有 `cache_clear`。少清一层不影响正确性 ——
    `_load_or_error` 清掉后就会重新走到被替换的严格加载器。
    """
    for fn in (load_fenjin_table, _load_or_error):
        clear = getattr(fn, "cache_clear", None)
        if clear is not None:
            clear()


def fenjin_cell(index: int, *, school: str = "default", table_path: str | None = None) -> FenjinCell:
    """按全局序号构造分金格（含规则表查得的干支）。"""
    if not 0 <= index < 120:
        raise ValueError(f"分金序号须在 0..119，收到 {index}")

    mountain, sub, start, center, end = _cell_geometry(index)
    ganzhi: str | None = None
    usable: bool | None = None

    # 走 fail-soft 入口：表缺失或**写坏**都只降级为"无干支"，不打断几何层
    table, _ = _load_or_error(_cache_key(table_path))
    school_table = (table or {}).get(school)
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
    """该流派的干支规则表是否已就绪。UI 据此决定是否展示分金干支。

    **表写坏时返回 `False` 而不抛异常** —— 三个运行期调用点
    （`compass.py:122`、`context.py:238`、`meta.py:115`）都是裸调用，
    抛出去就是整个罗盘接口 500。具体原因用 `table_load_error()` 取，
    管理台据此区分「表没提供」与「表写坏了」。
    """
    table, _ = _load_or_error(_cache_key(table_path))
    return bool(table) and school in table


__all__ = [
    "FENJIN_PER_MOUNTAIN", "FENJIN_SPAN", "FENJIN_HALF",
    "DEFAULT_TABLE_PATH", "FenjinCell",
    "load_fenjin_table", "fenjin_cell", "fenjin_at", "fenjin_cells_of",
    "table_available", "table_load_error", "clear_fenjin_cache",
]
