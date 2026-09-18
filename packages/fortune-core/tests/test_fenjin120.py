"""一百二十分金 —— 规则表「缺失 / 写坏 / 正常」三种输入下的行为。

为什么单独建这个文件，而不是并进 `test_compass.py`：

那里原有的分金断言写的是 `assert ... is False`，靠的是**仓库里恰好没有这张表**。
于是它描述的是"今天的巧合"，不是"应该发生的行为" —— 真把表补上时，
它会第一个报"回归"，而它想守的东西（缺表时不编造）其实完好。

本文件反过来：**用 `tmp_path` 显式构造三种输入**，断言每种输入下的行为。
这样无论 `data/fenjin120.json` 在不在，结论都成立。

三层职责（改动前只有"严格"一层，运行期会因此 500）：

| 函数 | 定位 | 坏表时 |
|---|---|---|
| `load_fenjin_table` | **严格**——补表环节的裁判 | **抛异常**（必须拦住写错的表） |
| `table_available` / `fenjin_at` | **运行期**——罗盘主链路 | **降级**：`False` / 只给几何格位 |
| `table_load_error` | 诊断——管理台区分"没提供"与"写坏了" | 返回具体原因 |
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from fortune_core.compass import calculate_orientation
from fortune_core.constants import JIAZI_60
from fortune_core.fenjin120 import (
    clear_fenjin_cache,
    fenjin_at,
    load_fenjin_table,
    table_available,
    table_load_error,
)
from fortune_core.mountain24 import MOUNTAIN_ORDER

# 六十甲子中地支为「子」的恰好五个 —— 子山五格（真实排法的形状，仅用于测试装载逻辑）
ZI_CELLS: list[str] = ["甲子", "丙子", "戊子", "庚子", "壬子"]


def _full_default_table() -> dict[str, dict[str, list[str | None]]]:
    """24 山 × 5 格，从六十甲子顺序铺满 120 格（每个干支恰好出现两次）。"""
    return {
        "default": {
            name: [JIAZI_60[(i * 5 + k) % 60] for k in range(5)]
            for i, name in enumerate(MOUNTAIN_ORDER)
        }
    }


def _write(path: Path, data: object) -> str:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return str(path)


@pytest.fixture(autouse=True)
def _fresh_cache():
    """每个用例前后清缓存。

    **不清理就会假绿**：`lru_cache` 不认测试边界，上一用例写坏的表的加载结果
    会被下一用例直接命中，于是"坏表"用例看到的是干净的缓存。
    """
    clear_fenjin_cache()
    yield
    clear_fenjin_cache()


@pytest.fixture
def good_path(tmp_path: Path) -> str:
    return _write(tmp_path / "good.json", _full_default_table())


@pytest.fixture
def short_cells_path(tmp_path: Path) -> str:
    """某山只写了 3 格 —— 补表时最容易犯的错。"""
    return _write(tmp_path / "short.json", {"default": {"子": ["甲子", "丙子", "戊子"]}})


class TestStrictLoader:
    """`load_fenjin_table` 是**严格**接口：写错的表必须当场抛，不能装成"没有表"。"""

    def test_文件不存在返回空表(self, tmp_path: Path) -> None:
        assert load_fenjin_table(str(tmp_path / "nope.json")) == {}

    def test_合法表原样返回(self, good_path: str) -> None:
        table = load_fenjin_table(good_path)
        assert set(table) == {"default"}
        assert len(table["default"]) == len(MOUNTAIN_ORDER)
        assert table["default"]["子"] == [
            JIAZI_60[(MOUNTAIN_ORDER.index("子") * 5 + k) % 60] for k in range(5)
        ]

    @pytest.mark.parametrize(
        ("label", "data", "exc"),
        [
            ("顶层是 list", ["甲子"], ValueError),
            ("山名非法", {"default": {"紫": ZI_CELLS}}, KeyError),
            ("格数不为 5", {"default": {"子": ["甲子", "丙子", "戊子"]}}, ValueError),
            ("干支非法", {"default": {"子": ["甲子", "丙子", "戊子", "庚子", "甲丑"]}}, ValueError),
            ("山值不是 list", {"default": {"子": {"a": 1}}}, ValueError),
            ("格值是数字", {"default": {"子": ["甲子", "丙子", "戊子", "庚子", 1]}}, ValueError),
        ],
    )
    def test_坏表一律抛异常(self, tmp_path: Path, label: str, data: object, exc: type[Exception]) -> None:
        p = _write(tmp_path / "bad.json", data)
        with pytest.raises(exc):
            load_fenjin_table(p)
        assert label  # 参数名进用例 id，便于定位

    def test_空表合法(self, tmp_path: Path) -> None:
        """`{}` 是合法的"没提供"，不是错误 —— 降级与缺表在这里分叉。"""
        assert load_fenjin_table(_write(tmp_path / "empty.json", {})) == {}


class TestRuntimeDegradation:
    """运行期 **不崩**：三个调用点都是裸调用，抛出去就是整个罗盘接口 500。"""

    def test_缺表_available为False且无错误(self, tmp_path: Path) -> None:
        missing = str(tmp_path / "nope.json")
        assert table_available(table_path=missing) is False
        assert table_load_error(table_path=missing) is None, "缺表不是错误，不该报错"

    def test_坏表_available为False但不抛(self, short_cells_path: str) -> None:
        assert table_available(table_path=short_cells_path) is False

    def test_坏表_给出具体原因(self, short_cells_path: str) -> None:
        err = table_load_error(table_path=short_cells_path)
        assert err is not None
        assert err.startswith("ValueError:")
        assert "子山" in err and "5 格" in err, f"原因应可定位到具体山与格数：{err}"

    def test_缺表_几何层完好(self, tmp_path: Path) -> None:
        cell = fenjin_at(0.0, table_path=str(tmp_path / "nope.json"))
        assert cell.index == 2
        assert cell.mountain.name == "子"
        assert cell.sub_index == 2
        assert cell.ganzhi is None and cell.usable is None
        assert "格" in cell.label, "无干支时标签退化为几何描述，不能是空的"

    def test_坏表_几何层完好(self, short_cells_path: str) -> None:
        """★ 本条是加固的核心：坏表下「几何对、干支空」，不是崩溃。"""
        cell = fenjin_at(180.0, table_path=short_cells_path)
        assert cell.index == 62
        assert cell.mountain.name == "午"
        assert cell.ganzhi is None, "坏表不得产出半份干支"
        assert cell.usable is None
        assert cell.label == "午山 3/5 格"

    def test_合法表_干支可用(self, good_path: str) -> None:
        assert table_available(table_path=good_path) is True
        assert table_load_error(table_path=good_path) is None
        cell = fenjin_at(0.0, table_path=good_path)
        assert cell.ganzhi is not None and cell.usable is True
        assert cell.label.endswith("分金")

    def test_表在但缺该流派_按缺表处理(self, tmp_path: Path) -> None:
        """`schools.py` 有 default/sanhe/sanyuan 三个 key，表里可能只给了部分。"""
        p = _write(tmp_path / "only-default.json", _full_default_table())
        assert table_available("default", table_path=p) is True
        assert table_available("sanhe", table_path=p) is False

    def test_罗盘主链路在坏表下不崩(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """**端到端**：让真实调用链撞上"表写坏"。

        改动前的实测行为：`calculate_orientation()` 直接抛
        `ValueError: [default] 子山 应有 5 格，实为 4` —— 因为
        `compass.py` 的 `table_available()` 是裸调用，异常一路冒到接口层。
        """

        def _boom(*_args: object, **_kwargs: object) -> dict:
            raise ValueError("[default] 子山 应有 5 格，实为 4")

        # patch 到 fenjin120 模块上即可：table_available / fenjin_at 都在该模块内
        # 通过模块全局查 load_fenjin_table（compass 持有的是函数对象，不是副本）
        monkeypatch.setattr("fortune_core.fenjin120.load_fenjin_table", _boom)
        clear_fenjin_cache()

        o = calculate_orientation(sitting="午", facing="子", degree=180.0)
        facts = o.to_facts()

        assert facts["fenjin_table_available"] is False
        assert facts["fenjin"]["index"] == 62, "几何层必须仍然完好"
        assert facts["fenjin"]["ganzhi"] is None, "坏表下不得产出半份干支"
        assert any("未提供" in w or "加载失败" in w for w in facts["warnings"]), (
            "必须给出可读警告，不能静默降级"
        )

    def test_坏表时不谎报为未提供(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """表**写坏了**与表**没提供**是两回事：前者是运维事故。

        若一律报"未提供"，运维会去找一张根本不缺的表 —— 方向从第一步就错。
        """

        def _boom(*_args: object, **_kwargs: object) -> dict:
            raise ValueError("[default] 子山 应有 5 格，实为 4")

        monkeypatch.setattr("fortune_core.fenjin120.load_fenjin_table", _boom)
        clear_fenjin_cache()

        facts = calculate_orientation(sitting="午", degree=180.0).to_facts()
        joined = " ".join(facts["warnings"])
        assert "加载失败" in joined, f"应报「加载失败」而非「未提供」：{joined}"
        assert "子山" in joined, "警告里要带得上具体原因，否则运维仍无从下手"


class TestDiagnostics:
    """告警与缓存 —— 两者都是"会不会静默"的关键。"""

    def test_坏表告警只打一次(self, short_cells_path: str, caplog: pytest.LogCaptureFixture) -> None:
        """坏表若每个请求都打日志会刷屏，于是运维反而把日志关掉、彻底静默。

        去重是**借 `lru_cache` 实现**的：函数体只执行一次，日志自然只出现一次。
        """
        with caplog.at_level(logging.WARNING, logger="fortune_core.fenjin120"):
            for _ in range(5):
                table_available(table_path=short_cells_path)

        assert len(caplog.records) == 1, f"应只告警一次，实际 {len(caplog.records)} 次"

    def test_告警带得上路径与原因(self, short_cells_path: str, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.WARNING, logger="fortune_core.fenjin120"):
            table_available(table_path=short_cells_path)
        msg = caplog.records[0].getMessage()
        assert "分金" in msg and "子山" in msg

    def test_清缓存后改表才生效(self, tmp_path: Path) -> None:
        """**明确固化缓存语义**：表是静态领域数据，改写后需重启 / 清缓存。

        这不是 bug，是刻意换来的性能（每个请求都要 `table_available()`）。
        把它写成测试，是为了让"改了表没生效"有据可查，而不是靠猜。
        """
        p = tmp_path / "t.json"
        _write(p, _full_default_table())
        assert table_available(table_path=str(p)) is True

        _write(p, {"default": {"子": ["甲子"]}})  # 改成坏表
        assert table_available(table_path=str(p)) is True, "缓存命中 —— 尚未重读"

        clear_fenjin_cache()
        assert table_available(table_path=str(p)) is False
        assert table_load_error(table_path=str(p)) is not None
