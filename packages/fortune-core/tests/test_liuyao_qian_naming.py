"""六爻 / 灵签 / 姓名 测试。"""

from __future__ import annotations

import pytest

from fortune_core.exceptions import (
    DomainDataMissingError,
    InvalidInputError,
)
from fortune_core.liuyao import (
    GUA_ORDER_BY_NUMBER,
    LIUSHISI_GUA,
    cast_liuyao,
    gua_by_number,
    hour_zhi_number,
)
from fortune_core.naming import (
    analyze_name,
    compute_wuge,
    load_strokes,
    split_name,
    stroke_element,
)
from fortune_core.qian import draw_qian, find_sign_by_number, list_qian_sets, load_qian_set


# ==========================================================================
# 六爻
# ==========================================================================


class TestGuaTable:
    def test_table_is_8x8(self) -> None:
        assert len(LIUSHISI_GUA) == 8
        for lower, row in LIUSHISI_GUA.items():
            assert len(row) == 8, f"下卦「{lower}」行的上卦数不为 8"
            assert set(row) == set(LIUSHISI_GUA), f"下卦「{lower}」行的列名不完整"

    def test_64_unique_names(self) -> None:
        """★ 64 卦名必须两两不同 —— 一表错位就会重复，此用例直接抓住。"""
        names = [n for row in LIUSHISI_GUA.values() for n in row.values()]
        assert len(names) == 64
        assert len(set(names)) == 64, f"卦名重复：{[n for n in set(names) if names.count(n) > 1]}"

    def test_diagonal_is_self(self) -> None:
        """上下卦相同者即本卦（乾为天、兑为泽…）。"""
        for gua in GUA_ORDER_BY_NUMBER:
            assert LIUSHISI_GUA[gua][gua] == gua

    def test_known_pairs(self) -> None:
        assert LIUSHISI_GUA["乾"]["坤"] == "泰"   # 地天泰：上坤下乾
        assert LIUSHISI_GUA["坤"]["乾"] == "否"   # 天地否：上乾下坤
        assert LIUSHISI_GUA["离"]["坎"] == "既济"  # 水火既济：上坎下离
        assert LIUSHISI_GUA["坎"]["离"] == "未济"  # 火水未济：上离下坎
        assert LIUSHISI_GUA["震"]["巽"] == "益"   # 风雷益
        assert LIUSHISI_GUA["巽"]["震"] == "恒"   # 雷风恒
        assert LIUSHISI_GUA["艮"]["坤"] == "谦"   # 地山谦
        assert LIUSHISI_GUA["坤"]["艮"] == "剥"   # 山地剥

    def test_gua_by_number(self) -> None:
        assert gua_by_number(1) == "乾"
        assert gua_by_number(8) == "坤"
        with pytest.raises(InvalidInputError):
            gua_by_number(0)
        with pytest.raises(InvalidInputError):
            gua_by_number(9)


class TestCast:
    def test_all_yang_is_qian(self) -> None:
        r = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        assert r.original_gua == "乾"
        assert r.upper_gua == "乾" and r.lower_gua == "乾"
        assert r.moving_positions == ()
        assert r.changed_gua is None

    def test_all_yin_is_kun(self) -> None:
        r = cast_liuyao(yao_values=[8, 8, 8, 8, 8, 8])
        assert r.original_gua == "坤"
        assert r.has_moving is False

    def test_moving_line_creates_changed_gua(self) -> None:
        """初爻老阳动 → 乾之姤（天风姤）。"""
        r = cast_liuyao(yao_values=[9, 7, 7, 7, 7, 7])
        assert r.original_gua == "乾"
        assert r.moving_positions == (1,)
        assert r.changed_gua == "姤"
        assert r.changed_lower_gua == "巽"
        assert r.changed_upper_gua == "乾"

    def test_laoyin_moving(self) -> None:
        """上爻老阴动 → 变卦上卦改变。"""
        r = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 6])
        assert r.moving_positions == (6,)
        assert r.changed_upper_gua is not None
        assert r.changed_gua is not None

    def test_multiple_moving_lines(self) -> None:
        r = cast_liuyao(yao_values=[9, 6, 7, 8, 7, 8])
        assert r.moving_positions == (1, 2)

    def test_yao_names(self) -> None:
        r = cast_liuyao(yao_values=[6, 7, 8, 9, 7, 8])
        assert r.to_facts()["yao_names"] == ["老阴", "少阳", "少阴", "老阳", "少阳", "少阴"]

    def test_coins_all_back_is_qian(self) -> None:
        """三枚全背 = 9 分 = 老阳 → 六爻皆老阳 = 乾（有动爻）。"""
        r = cast_liuyao(coins=[[True, True, True]] * 6)
        assert r.original_gua == "乾"
        assert r.moving_positions == (1, 2, 3, 4, 5, 6)

    def test_coins_all_front_is_kun(self) -> None:
        r = cast_liuyao(coins=[[False, False, False]] * 6)
        assert r.original_gua == "坤"
        assert r.moving_positions == (1, 2, 3, 4, 5, 6)

    def test_coins_two_back_is_shaoyin(self) -> None:
        """两背一字 = 3+3+2 = 8 = 少阴（**偶数 8 为少阴，易与直觉相悖，故单列**）。"""
        r = cast_liuyao(coins=[[True, True, False]] * 6)
        assert r.yao_values == (8,) * 6
        assert r.original_gua == "坤"
        assert r.moving_positions == ()

    def test_coins_one_back_is_shaoyang(self) -> None:
        """一背两字 = 3+2+2 = 7 = 少阳。"""
        r = cast_liuyao(coins=[[True, False, False]] * 6)
        assert r.yao_values == (7,) * 6
        assert r.original_gua == "乾"
        assert r.moving_positions == ()

    @pytest.mark.parametrize(
        ("backs", "expected_value", "expected_name"),
        [
            (3, 9, "老阳"),   # 三背
            (2, 8, "少阴"),   # 两背
            (1, 7, "少阳"),   # 一背
            (0, 6, "老阴"),   # 三字
        ],
    )
    def test_coin_convention_table(self, backs: int, expected_value: int, expected_name: str) -> None:
        """铜钱换算表（背=阳=3 分，字=阴=2 分）逐项锁定。"""
        toss = [True] * backs + [False] * (3 - backs)
        r = cast_liuyao(coins=[toss] * 6)
        assert set(r.yao_values) == {expected_value}
        assert set(r.to_facts()["yao_names"]) == {expected_name}

    def test_numbers_method(self) -> None:
        r = cast_liuyao(numbers=(1, 1))
        assert r.method == "numbers"
        assert len(r.yao_values) == 6
        assert r.moving_positions == (2,)  # (1+1) % 6 = 2

    def test_time_method(self) -> None:
        r = cast_liuyao(time_info={"year_zhi": 1, "month": 1, "day": 1, "hour_zhi": 1})
        assert r.method == "time"
        assert len(r.yao_values) == 6

    def test_deterministic(self) -> None:
        """同样输入必得同样卦 —— 本模块不含随机（RULE-007）。"""
        a = cast_liuyao(yao_values=[9, 8, 7, 6, 7, 8])
        b = cast_liuyao(yao_values=[9, 8, 7, 6, 7, 8])
        assert a == b

    def test_validation(self) -> None:
        with pytest.raises(InvalidInputError):
            cast_liuyao(yao_values=[7, 7, 7])
        with pytest.raises(InvalidInputError):
            cast_liuyao(yao_values=[7, 7, 7, 7, 7, 5])
        with pytest.raises(InvalidInputError):
            cast_liuyao(coins=[[True, True, True]] * 5)
        with pytest.raises(InvalidInputError):
            cast_liuyao(coins=[[True, True]] * 6)
        with pytest.raises(InvalidInputError):
            cast_liuyao(numbers=(0, 5))
        with pytest.raises(InvalidInputError):
            cast_liuyao(time_info={"year_zhi": 1})
        with pytest.raises(InvalidInputError):
            cast_liuyao()

    def test_layers(self) -> None:
        r = cast_liuyao(yao_values=[9, 8, 7, 6, 7, 8])
        facts, tradition = r.to_facts(), r.to_tradition()
        assert "original_gua" in facts
        assert "note" in tradition
        assert set(facts) & set(tradition) == set()

    def test_hour_zhi_number(self) -> None:
        assert hour_zhi_number(23) == 1   # 子
        assert hour_zhi_number(0) == 1    # 子
        assert hour_zhi_number(1) == 2    # 丑
        assert hour_zhi_number(3) == 3    # 寅
        assert hour_zhi_number(12) == 7   # 午
        with pytest.raises(InvalidInputError):
            hour_zhi_number(24)


# ==========================================================================
# 灵签
# ==========================================================================


class TestQian:
    def test_demo_set_loads(self) -> None:
        data = load_qian_set()
        assert data["demo"] is True
        assert len(data["signs"]) == data["total"]

    def test_list_sets(self) -> None:
        sets = list_qian_sets()
        assert any(s["set_id"] == "demo_guanyin" for s in sets)
        assert all(s["demo"] for s in sets)

    def test_draw_is_deterministic(self) -> None:
        a = draw_qian(3)
        b = draw_qian(3)
        assert a == b

    def test_seed_wraps(self) -> None:
        assert draw_qian(0).number == draw_qian(6).number

    def test_seed_sequence_covers_all(self) -> None:
        numbers = {draw_qian(i).number for i in range(6)}
        assert len(numbers) == 6, "0..5 应覆盖全部 6 签"

    def test_sign_fields_populated(self) -> None:
        q = draw_qian(0)
        assert q.level and q.title and q.poem
        assert q.interpretation and q.advice

    def test_demo_flag_in_tradition(self) -> None:
        q = draw_qian(0)
        assert q.to_facts()["is_demo_data"] is True
        assert any("演示" in u for u in q.to_tradition()["uncertainties"])

    def test_missing_set_raises(self) -> None:
        with pytest.raises(DomainDataMissingError):
            draw_qian(0, set_id="does_not_exist")

    def test_find_by_number(self) -> None:
        q = find_sign_by_number(3)
        assert q.number == 3
        with pytest.raises(InvalidInputError):
            find_sign_by_number(999)

    def test_layers_separate(self) -> None:
        facts = draw_qian(0).to_facts()
        tradition = draw_qian(0).to_tradition()
        assert set(facts) & set(tradition) == set()


# ==========================================================================
# 姓名
# ==========================================================================


class TestNameSplitting:
    def test_single_surname(self) -> None:
        assert split_name("李白") == ("李", "白")
        assert split_name("王小明") == ("王", "小明")

    def test_compound_surname(self) -> None:
        assert split_name("欧阳修") == ("欧阳", "修")
        assert split_name("司马光") == ("司马", "光")
        assert split_name("诸葛孔明") == ("诸葛", "孔明")

    def test_too_short(self) -> None:
        with pytest.raises(InvalidInputError):
            split_name("李")


class TestWugeFormula:
    """五格公式测试 —— 用**显式笔画**驱动，与笔画数据来源解耦。"""

    STROKES = {"王": 4, "明": 8, "华": 6, "欧": 15, "阳": 17, "李": 7, "白": 5}

    def test_single_surname_single_given(self) -> None:
        got = compute_wuge("王", "明", self.STROKES)
        assert got == {"天格": 5, "人格": 12, "地格": 9, "外格": 2, "总格": 12}

    def test_single_surname_double_given(self) -> None:
        got = compute_wuge("王", "明华", self.STROKES)
        assert got == {"天格": 5, "人格": 12, "地格": 14, "外格": 7, "总格": 18}

    def test_compound_surname_single_given(self) -> None:
        got = compute_wuge("欧阳", "明", self.STROKES)
        assert got == {"天格": 32, "人格": 25, "地格": 9, "外格": 16, "总格": 40}

    def test_compound_surname_double_given(self) -> None:
        got = compute_wuge("欧阳", "明华", self.STROKES)
        assert got == {"天格": 32, "人格": 25, "地格": 14, "外格": 21, "总格": 46}

    def test_zongge_is_sum_of_all(self) -> None:
        got = compute_wuge("王", "明华", self.STROKES)
        assert got["总格"] == 4 + 8 + 6

    def test_renge_is_last_surname_char_plus_first_given(self) -> None:
        got = compute_wuge("欧阳", "明", self.STROKES)
        assert got["人格"] == 17 + 8


class TestStrokeElement:
    @pytest.mark.parametrize(
        ("count", "expected"),
        [(1, "木"), (2, "木"), (3, "火"), (4, "火"), (5, "土"),
         (6, "土"), (7, "金"), (8, "金"), (9, "水"), (10, "水"),
         (11, "木"), (12, "木"), (20, "水")],
    )
    def test_element(self, count: int, expected: str) -> None:
        assert stroke_element(count) == expected

    def test_invalid(self) -> None:
        with pytest.raises(InvalidInputError):
            stroke_element(0)


class TestAnalyzeName:
    def test_with_builtin_table(self) -> None:
        """王 + 明 两字均在内置表内，应可直接分析。"""
        a = analyze_name("王明")
        assert a.surname == "王" and a.given == "明"
        assert a.tiange == 5 and a.renge == 12 and a.dige == 9
        assert a.waige == 2 and a.zongge == 12
        assert a.sancai_label == "土" + "木" + "水"

    def test_missing_strokes_raise_with_char_list(self) -> None:
        """缺笔画时必须报出**具体缺哪些字**，不得静默取错值。"""
        with pytest.raises(DomainDataMissingError) as exc:
            analyze_name("王𠮷")
        assert "𠮷" in str(exc.value)

    def test_explicit_strokes_override(self) -> None:
        a = analyze_name("王明", strokes={"王": 4, "明": 8})
        assert a.strokes == {"王": 4, "明": 8}

    def test_provided_wuge_bypass(self) -> None:
        a = analyze_name("王明", strokes={"王": 4, "明": 8},
                         provided_wuge={"天格": 5, "人格": 12, "地格": 9, "外格": 2, "总格": 12})
        assert a.zongge == 12

    def test_compound_surname(self) -> None:
        a = analyze_name("欧阳修", strokes={"欧": 15, "阳": 17, "修": 10})
        assert a.surname == "欧阳"
        assert a.tiange == 32
        assert a.renge == 17 + 10

    def test_number_luck_is_none_without_table(self) -> None:
        """81 数理表未提供时，吉凶必须为 None —— 不编造。"""
        a = analyze_name("王明")
        assert a.number_luck is None
        assert a.to_facts()["number_luck_available"] is False

    def test_uncertainties_present(self) -> None:
        a = analyze_name("王明")
        assert len(a.uncertainties) >= 2

    def test_layers_separate(self) -> None:
        a = analyze_name("王明")
        assert set(a.to_facts()) & set(a.to_tradition()) == set()


class TestStrokesTableIntegrity:
    """笔画表的结构性校验 + 锚点回归。"""

    def test_table_loads(self) -> None:
        table = load_strokes()
        assert len(table) > 300, f"内置笔画表过小：{len(table)}"

    def test_all_values_in_range(self) -> None:
        for ch, v in load_strokes().items():
            assert 1 <= v <= 64, f"{ch} 笔画越界：{v}"

    def test_keys_are_single_chars(self) -> None:
        for ch in load_strokes():
            assert len(ch) == 1, f"笔画表的键须为单字：{ch!r}"

    @pytest.mark.parametrize(
        ("char", "expected"),
        [
            ("王", 4), ("张", 11), ("刘", 15), ("陈", 16), ("罗", 20),
            ("苏", 22), ("谭", 19), ("薛", 19), ("钱", 16), ("赵", 14),
            ("李", 7), ("孙", 10), ("郑", 19), ("韩", 17), ("杨", 13),
        ],
    )
    def test_anchor_values(self, char: str, expected: int) -> None:
        """★ 锚点回归：这 15 个字的康熙笔画是姓名学硬常识，
        换用任何新笔画表都必须保留这些值，否则整张表不可信。"""
        assert load_strokes().get(char) == expected
