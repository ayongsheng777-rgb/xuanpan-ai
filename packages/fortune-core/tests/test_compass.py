"""二十四山 · 一百二十分金 · 坐向 —— 罗盘计算的核心测试。"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from fortune_core.compass import (
    calculate_orientation,
    element_relation,
    neighbors,
)
from fortune_core.constants import DIZHI, TIANGAN
from fortune_core.exceptions import InvalidInputError, OrientationConflictError
from fortune_core.fenjin120 import (
    FENJIN_PER_MOUNTAIN,
    FENJIN_SPAN,
    fenjin_at,
    fenjin_cell,
    fenjin_cells_of,
    table_available,
)
from fortune_core.mountain24 import (
    GUA_OF_MOUNTAIN,
    HALF_SPAN,
    MOUNTAIN_ORDER,
    MOUNTAINS,
    SPAN_DEGREE,
    angular_distance,
    degree_of,
    get_mountain,
    is_opposite,
    mountain_at,
    mountains_in_span,
    normalize_degree,
    opposite,
)


class TestMountainTable:
    def test_count_and_order(self) -> None:
        assert len(MOUNTAINS) == 24
        assert len(MOUNTAIN_ORDER) == 24
        assert tuple(m.name for m in MOUNTAINS) == MOUNTAIN_ORDER
        assert MOUNTAIN_ORDER[0] == "子", "标准表须从正北「子」起"
        assert MOUNTAIN_ORDER[12] == "午", "第 13 位应为「午」（正南）"

    def test_each_mountain_15_degrees(self) -> None:
        assert SPAN_DEGREE == 15.0
        assert HALF_SPAN == 7.5
        for i, m in enumerate(MOUNTAINS):
            assert m.index == i
            assert m.center_degree == i * 15.0

    def test_center_degrees_unique_and_cover_360(self) -> None:
        centres = sorted(m.center_degree for m in MOUNTAINS)
        assert centres == [i * 15.0 for i in range(24)]

    def test_four_cardinal_points(self) -> None:
        assert get_mountain("子").center_degree == 0.0     # 正北
        assert get_mountain("卯").center_degree == 90.0    # 正东
        assert get_mountain("午").center_degree == 180.0   # 正南
        assert get_mountain("酉").center_degree == 270.0   # 正西

    def test_span_left_closed_right_open(self) -> None:
        zi = get_mountain("子")
        assert zi.start_degree == 352.5
        assert zi.end_degree == 7.5

    def test_kind_partition(self) -> None:
        """24 山 = 12 地支山 + 8 天干山 + 4 卦山，且戊己不入山。"""
        kinds = [m.kind for m in MOUNTAINS]
        assert kinds.count("branch") == 12
        assert kinds.count("stem") == 8
        assert kinds.count("gua") == 4
        stems = {m.stem for m in MOUNTAINS if m.kind == "stem"}
        assert stems == set(TIANGAN) - {"戊", "己"}
        branches = {m.branch for m in MOUNTAINS if m.kind == "branch"}
        assert branches == set(DIZHI)

    def test_gua_covers_three_consecutive_mountains(self) -> None:
        """每卦辖连续三山，合计 8×3 = 24，无遗漏无重复（须处理跨 0° 的环绕）。"""
        all_m = [m for group in GUA_OF_MOUNTAIN.values() for m in group]
        assert len(all_m) == 24
        assert len(set(all_m)) == 24
        # 坎卦居正北，辖 壬(345°) 子(0°) 癸(15°) —— 跨越 0° 的关键案例
        assert set(GUA_OF_MOUNTAIN["坎"]) == {"壬", "子", "癸"}

        for name, group in GUA_OF_MOUNTAIN.items():
            idxs = [MOUNTAIN_ORDER.index(m) for m in group]
            assert idxs == [(idxs[0] + k) % 24 for k in range(3)], f"{name}卦辖山不连续：{group}"
            assert get_mountain(group[1]).gua == name, f"{name}卦中位山归属错误"
            assert get_mountain(group[0]).gua == name
            assert get_mountain(group[2]).gua == name

    def test_sanyuan_partition(self) -> None:
        """三元龙 8+8+8 完整划分。"""
        got = [m.sanyuan for m in MOUNTAINS]
        assert got.count("天元") == 8
        assert got.count("地元") == 8
        assert got.count("人元") == 8

    def test_element_assignment(self) -> None:
        assert get_mountain("子").element == "water"
        assert get_mountain("午").element == "fire"
        assert get_mountain("卯").element == "wood"
        assert get_mountain("酉").element == "metal"
        assert get_mountain("辰").element == "earth"
        assert get_mountain("艮").element == "earth"   # 卦山按卦五行
        assert get_mountain("乾").element == "metal"
        assert get_mountain("巽").element == "wood"


class TestDegreeToMountain:
    @pytest.mark.parametrize(
        ("degree", "expected"),
        [
            (0, "子"), (15, "癸"), (30, "丑"), (45, "艮"), (60, "寅"), (75, "甲"),
            (90, "卯"), (105, "乙"), (120, "辰"), (135, "巽"), (150, "巳"), (165, "丙"),
            (180, "午"), (195, "丁"), (210, "未"), (225, "坤"), (240, "申"), (255, "庚"),
            (270, "酉"), (285, "辛"), (300, "戌"), (315, "乾"), (330, "亥"), (345, "壬"),
        ],
    )
    def test_all_24_centres(self, degree: float, expected: str) -> None:
        assert mountain_at(degree).name == expected

    @pytest.mark.parametrize(
        ("degree", "expected"),
        [
            (7.5, "癸"),      # 右边界归下一山
            (352.5, "子"),    # 左边界归本山
            (22.4, "癸"),
            (22.6, "丑"),
            (720.0, "子"),    # 超过 360 应回绕（720 % 360 = 0）
            (367.5, "癸"),    # 367.5 % 360 = 7.5 → 右边界归癸
            (-7.5, "子"),     # 负角度应回绕
            (-10.0, "壬"),
        ],
    )
    def test_boundaries_and_wrap(self, degree: float, expected: str) -> None:
        assert mountain_at(degree).name == expected

    def test_exhaustive_coverage(self) -> None:
        """以 0.5° 步长扫全圆，24 山每山应恰好被命中 30 次（15/0.5）。"""
        counts: dict[str, int] = {}
        d = 0.0
        while d < 360.0:
            m = mountain_at(d).name
            counts[m] = counts.get(m, 0) + 1
            d += 0.5
        assert len(counts) == 24
        assert set(counts.values()) == {30}, f"覆盖不均匀：{counts}"

    def test_normalize(self) -> None:
        assert normalize_degree(360) == 0.0
        assert normalize_degree(-1) == 359.0
        assert normalize_degree(725) == 5.0

    def test_invalid_name_raises(self) -> None:
        with pytest.raises(KeyError):
            get_mountain("戊")  # 戊不入二十四山
        with pytest.raises(KeyError):
            get_mountain("中")


class TestOpposite:
    def test_opposite_pairs(self) -> None:
        assert opposite("子") == "午"
        assert opposite("午") == "子"
        assert opposite("卯") == "酉"
        assert opposite("艮") == "坤"
        assert opposite("乾") == "巽"

    def test_self_inverse(self) -> None:
        for m in MOUNTAIN_ORDER:
            assert opposite(opposite(m)) == m, f"{m} 对宫非自反"

    def test_exactly_180_degrees(self) -> None:
        for m in MOUNTAIN_ORDER:
            assert abs(angular_distance(degree_of(m), degree_of(opposite(m))) - 180.0) < 1e-9

    def test_opposite_table_has_12_pairs(self) -> None:
        pairs = {frozenset({m, opposite(m)}) for m in MOUNTAIN_ORDER}
        assert len(pairs) == 12, "对宫关系应恰有 12 组"

    def test_is_opposite(self) -> None:
        assert is_opposite("子", "午")
        assert not is_opposite("子", "癸")
        assert not is_opposite("子", "子")


class TestAngularDistance:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [(0, 90, 90), (350, 10, 20), (0, 180, 180), (10, 350, 20), (90, 270, 180)],
    )
    def test_distance(self, a: float, b: float, expected: float) -> None:
        assert math.isclose(angular_distance(a, b), expected, abs_tol=1e-9)


class TestMountainsInSpan:
    def test_span_crossing_zero(self) -> None:
        got = [m.name for m in mountains_in_span(350, 20)]
        assert "子" in got and "壬" in got and "癸" in got

    def test_empty_span(self) -> None:
        assert mountains_in_span(10, 10) == []


class TestNeighbors:
    def test_neighbors(self) -> None:
        assert neighbors("子") == ["壬", "癸"]
        assert neighbors("午", 2) == ["巳", "丙", "丁", "未"]

    def test_neighbors_wrap(self) -> None:
        assert neighbors("壬") == ["亥", "子"]


class TestFenjinGeometry:
    def test_grid_size(self) -> None:
        assert FENJIN_SPAN == 3.0
        assert FENJIN_PER_MOUNTAIN == 5

    def test_120_cells_no_overlap_no_gap(self) -> None:
        """120 格应以 3° 等分整圆，首尾相接、无重叠、无空隙（跨 0° 处须模 360 计算跨度）。"""
        starts = []
        for i in range(120):
            c = fenjin_cell(i)
            starts.append(c.start_degree)
            span = (c.end_degree - c.start_degree) % 360.0
            assert math.isclose(span, 3.0, abs_tol=1e-9), f"第 {i} 格跨度异常：{span}"
            assert math.isclose((c.center_degree - c.start_degree) % 360.0, 1.5, abs_tol=1e-9)

        assert len(set(starts)) == 120, "格起始角重复"
        # 起始角集合应恰为 {352.5 + 3k mod 360 | k = 0..119}
        assert set(starts) == {round((352.5 + 3 * k) % 360.0, 6) for k in range(120)}

        # 相邻格必须首尾相接
        ordered = sorted(starts)
        for a, b in zip(ordered, ordered[1:]):
            assert math.isclose(b - a, 3.0, abs_tol=1e-9), f"{a} 与 {b} 之间存在空隙或重叠"

    def test_cell_belongs_to_correct_mountain(self) -> None:
        for i in range(120):
            c = fenjin_cell(i)
            assert c.mountain is MOUNTAINS[i // 5]
            assert c.sub_index == i % 5
            assert mountain_at(c.center_degree).name == c.mountain.name

    def test_each_mountain_has_5_cells(self) -> None:
        for m in MOUNTAIN_ORDER:
            cells = fenjin_cells_of(m)
            assert len(cells) == 5
            assert all(c.mountain.name == m for c in cells)
            assert [c.sub_index for c in cells] == [0, 1, 2, 3, 4]

    def test_grid_origin_is_352_5(self) -> None:
        """格网起点是 352.5°（子山起始角），不是 0° —— 这是易错点。"""
        assert fenjin_cell(0).start_degree == 352.5
        assert fenjin_at(352.5).index == 0
        assert fenjin_at(0.0).index == 2
        assert fenjin_cell(2).center_degree == 0.0

    @pytest.mark.parametrize(
        ("degree", "expected_index"),
        [(352.5, 0), (355.5, 1), (0.0, 2), (1.5, 3), (4.5, 4), (7.5, 5), (180.0, 62)],
    )
    def test_fenjin_at(self, degree: float, expected_index: int) -> None:
        assert fenjin_at(degree).index == expected_index

    def test_out_of_range_index(self) -> None:
        with pytest.raises(ValueError):
            fenjin_cell(120)
        with pytest.raises(ValueError):
            fenjin_cell(-1)

    def test_ganzhi_absent_without_rule_table(self, tmp_path: Path) -> None:
        """规则表未提供时，干支必须为 None —— 不得凭理论推算（RULE-001/008）。

        **显式指向一个不存在的路径**，而不是靠「仓库里恰好没有这张表」：
        后者描述的是今天的巧合 —— 真把表补上时它会报「回归」，
        而它想守的东西（缺表不编造）其实完好。
        """
        missing = str(tmp_path / "no-such-fenjin120.json")
        assert table_available(table_path=missing) is False
        cell = fenjin_at(180.0, table_path=missing)
        assert cell.ganzhi is None
        assert cell.usable is None
        assert "分金" in cell.label or "格" in cell.label


class TestElementRelation:
    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [
            ("water", "wood", "水生木"),
            ("wood", "water", "水生木"),
            ("metal", "wood", "金克木"),
            ("wood", "metal", "金克木"),
        ],
    )
    def test_relation(self, a: str, b: str, expected: str) -> None:
        assert element_relation(a, b) == expected

    def test_same_element(self) -> None:
        assert "比和" in element_relation("fire", "fire")

    def test_all_pairs_defined(self) -> None:
        elements = ("wood", "fire", "earth", "metal", "water")
        for a in elements:
            for b in elements:
                assert element_relation(a, b)


class TestCalculateOrientation:
    def test_from_sitting_only(self) -> None:
        o = calculate_orientation(sitting="午")
        assert o.sitting.name == "午"
        assert o.facing.name == "子"
        assert o.pair_label == "坐午向子"
        assert "向山由坐山对宫推导" in o.warnings

    def test_from_facing_only(self) -> None:
        o = calculate_orientation(facing="子")
        assert o.sitting.name == "午"
        assert "坐山由向山对宫推导" in o.warnings

    def test_from_degree(self) -> None:
        o = calculate_orientation(degree=182.0)
        assert o.sitting.name == "午"
        assert o.facing.name == "子"
        assert o.exact_degree == 182.0
        assert o.to_facts()["offset_from_center"] == 2.0

    def test_valid_pair(self) -> None:
        o = calculate_orientation(sitting="艮", facing="坤")
        assert o.sitting.name == "艮" and o.facing.name == "坤"

    def test_facing_not_opposite_raises(self) -> None:
        """坐向不构成相对关系必须报冲突，不得静默取一个。"""
        with pytest.raises(OrientationConflictError):
            calculate_orientation(sitting="子", facing="癸")

    def test_sitting_equals_facing_raises(self) -> None:
        with pytest.raises(OrientationConflictError):
            calculate_orientation(sitting="子", facing="子")

    def test_degree_conflicts_with_sitting_raises(self) -> None:
        """角度与坐山矛盾时必须报错，而不是悄悄改掉用户给的值（RULE-008）。"""
        with pytest.raises(OrientationConflictError) as exc:
            calculate_orientation(sitting="子", degree=180.0)
        assert "不符" in str(exc.value)

    def test_no_input_raises(self) -> None:
        with pytest.raises(InvalidInputError):
            calculate_orientation()

    def test_bad_confidence_raises(self) -> None:
        with pytest.raises(InvalidInputError):
            calculate_orientation(sitting="午", confidence=1.5)

    def test_low_confidence_warns(self) -> None:
        o = calculate_orientation(sitting="午", confidence=0.5)
        assert any("置信度偏低" in w for w in o.warnings)

    def test_yinyang_relation(self) -> None:
        """四维山（乾坤艮巽）与其对宫阴阳相反，其余对宫阴阳相同。"""
        assert calculate_orientation(sitting="子").same_yin_yang is True
        assert calculate_orientation(sitting="艮").same_yin_yang is False

    def test_facts_layer_shape(self) -> None:
        o = calculate_orientation(sitting="午", facing="子", degree=180.0, confidence=0.92,
                                  confirmed_by_user=True, source="vision")
        f = o.to_facts()
        assert f["sitting"] == "午" and f["facing"] == "子"
        assert f["pair"] == "坐午向子"
        assert f["confirmed_by_user"] is True
        assert f["source"] == "vision"
        assert f["fenjin"]["index"] == 62
        # 只锁**形状**（字段在、类型对）不锁值：本用例的主题是 facts 层结构，
        # 而这一位的值取决于分金规则表在不在 —— 见过它写成 `is False` 的版本，
        # 那等于把"今天的巧合"写进了测试，补表时会报出一个毫无道理的回归。
        assert isinstance(f["fenjin_table_available"], bool)

    def test_tradition_layer_shape(self) -> None:
        o = calculate_orientation(sitting="午", facing="子")
        t = o.to_tradition()
        assert t["sitting"]["element"] == "火"
        assert t["facing"]["element"] == "水"
        assert t["element_relation"] == "水克火"
        assert t["sitting"]["gua"] == "离"
        assert t["facing"]["gua"] == "坎"
