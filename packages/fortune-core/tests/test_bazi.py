"""八字排盘测试 —— 用**外部锚点**与**纯口诀交叉验证**双重锁定历法正确性。

锚点来源：生产路线报告附录 A.3（JDN 偏移 k=49 恒定 + 2000-01-01 戊午日公认锚点）。

这是 RULE-001 的核心防线：历法库若被换掉或升级出错，这里会立刻红。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from fortune_core.bazi import (
    BirthInput,
    assess_strength,
    calculate_bazi,
    count_elements,
    resolve_birth,
    true_solar_time,
)
from fortune_core.bazi.chart import hour_pillar_by_rule, month_pillar_by_rule
from fortune_core.exceptions import InvalidInputError


class TestExternalDayPillarAnchors:
    """日柱外部锚点 —— 全部经 JDN 公式 + k=49 恒定偏移独立验证过。"""

    @pytest.mark.parametrize(
        ("date", "expected_day"),
        [
            ((1981, 9, 14), "乙未"),
            ((2000, 1, 1), "戊午"),     # 公认锚点
            ((2024, 2, 10), "甲辰"),
            ((1990, 5, 20), "乙酉"),
        ],
    )
    def test_day_pillar(self, date: tuple[int, int, int], expected_day: str) -> None:
        y, m, d = date
        chart = calculate_bazi(BirthInput(y, m, d, 12, 0))
        assert chart.pillars["day"] == expected_day

    def test_day_pillar_is_continuous(self) -> None:
        """日柱逐日递进，60 日一循环 —— 验证历法库的连续性。"""
        from fortune_core.constants import jiazi_index

        base = calculate_bazi(BirthInput(2024, 2, 10, 12, 0))
        n0 = jiazi_index(base.pillars["day"])
        for offset in range(1, 31):
            from datetime import timedelta

            dt = datetime(2024, 2, 10) + timedelta(days=offset)
            c = calculate_bazi(BirthInput(dt.year, dt.month, dt.day, 12, 0))
            assert jiazi_index(c.pillars["day"]) == (n0 + offset) % 60


class TestKnownChart:
    """1981-09-14 08:00 —— 本案用于纠正界面演示图错误数据（报告 §2.5）。"""

    @pytest.fixture()
    def chart(self):
        return calculate_bazi(BirthInput(1981, 9, 14, 8, 0, gender="male", location="湖北"))

    def test_four_pillars(self, chart) -> None:
        assert chart.pillars == {
            "year": "辛酉", "month": "丁酉", "day": "乙未", "hour": "庚辰",
        }

    def test_day_master_is_yi_not_xin(self, chart) -> None:
        """演示图标称日主「辛金」，实为「乙木」—— 本用例锁定纠正结果。"""
        assert chart.day_master == "乙"
        assert chart.day_element == "wood"

    def test_hour_pillar_contradicts_demo_image(self, chart) -> None:
        """演示图给「甲辰」，实为「庚辰」。"""
        assert chart.pillars["hour"] == "庚辰"
        assert chart.pillars["hour"] != "甲辰"

    def test_nayin(self, chart) -> None:
        assert chart.nayin == {
            "年柱": "石榴木", "月柱": "山下火", "日柱": "沙中金", "时柱": "白蜡金",
        }

    def test_shishen(self, chart) -> None:
        got = chart.shishen_gan
        assert got["年柱"] == "七杀"
        assert got["月柱"] == "食神"
        assert got["日柱"] == "日主"
        assert got["时柱"] == "正官"

    def test_shengxiao(self, chart) -> None:
        assert chart.shengxiao == "鸡"

    def test_rule_consistency_is_self_consistent(self, chart) -> None:
        """★ 核心自检：四柱必须同时满足五鼠遁与五虎遁口诀。"""
        assert chart.verify_rule_consistency() == []

    def test_five_elements_simple_total(self, chart) -> None:
        """本气口径合计应为 8（4 天干 + 4 地支）。"""
        assert chart.simple_stats.total == 8.0

    def test_five_elements_hidden_has_more_weight(self, chart) -> None:
        assert chart.hidden_stats.total > chart.simple_stats.total


class TestRuleCrossCheck:
    """口诀推导必须与历法库一致 —— 用真实日期批量交叉验证。"""

    @pytest.mark.parametrize("hour", range(24))
    def test_rule_consistency_across_all_hours(self, hour: int) -> None:
        """全天 24 小时逐时校验：时柱必须满足五鼠遁（含晚子时的次日口径）。"""
        chart = calculate_bazi(BirthInput(1981, 9, 14, hour, 0))
        assert chart.verify_rule_consistency() == []

    @pytest.mark.parametrize("hour", [1, 3, 5, 9, 13, 19])
    def test_hour_pillar_directly_derivable_outside_late_zi(self, hour: int) -> None:
        """非晚子时时，时柱应能直接由本日日干推出 —— 排除「碰巧」通过的可能。"""
        chart = calculate_bazi(BirthInput(1981, 9, 14, hour, 0))
        expected = hour_pillar_by_rule(chart.pillars["day"][0], chart.pillars["hour"][1])
        assert chart.pillars["hour"] == expected
        assert chart.hour_rule_convention() == "本日日干起时"

    @pytest.mark.parametrize(
        "date",
        [(1981, 9, 14), (2000, 1, 1), (2024, 2, 10), (1990, 5, 20), (2025, 6, 15), (1976, 3, 3)],
    )
    def test_month_pillar_across_dates(self, date: tuple[int, int, int]) -> None:
        y, m, d = date
        chart = calculate_bazi(BirthInput(y, m, d, 12, 0))
        expected = month_pillar_by_rule(chart.pillars["year"][0], chart.pillars["month"][1])
        assert chart.pillars["month"] == expected

    @pytest.mark.parametrize("day_gan", ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"])
    def test_hour_rule_covers_all_day_stems(self, day_gan: str) -> None:
        """五鼠遁口诀对 10 个日干都应给出合法干支，且子时起点符合口诀。"""
        for i, zhi in enumerate("子丑寅卯辰巳午未申酉戌亥"):
            gz = hour_pillar_by_rule(day_gan, zhi)
            assert len(gz) == 2
            # 时支必须与输入一致
            assert gz[1] == zhi
        # 子时起点校验：甲己→甲子、乙庚→丙子、丙辛→戊子、丁壬→庚子、戊癸→壬子
        expected_start = {"甲": "甲", "己": "甲", "乙": "丙", "庚": "丙",
                          "丙": "戊", "辛": "戊", "丁": "庚", "壬": "庚",
                          "戊": "壬", "癸": "壬"}
        assert hour_pillar_by_rule(day_gan, "子")[0] == expected_start[day_gan]

    def test_rule_functions_validate_input(self) -> None:
        with pytest.raises(InvalidInputError):
            hour_pillar_by_rule("甲", "X")      # 非法地支
        with pytest.raises(InvalidInputError):
            hour_pillar_by_rule("X", "辰")      # 非法天干
        with pytest.raises(InvalidInputError):
            month_pillar_by_rule("X", "寅")


class TestLateZiHour:
    """晚子时流派（sect）—— 实测确认 lunar-python 的语义与直觉相反，故单列锁定。

    实测（2024-06-01 23:00）：
        sect=1 → 日柱 丁酉（次日）+ 时柱 庚子（丁日子时）→ 日柱时柱同源自洽
        sect=2 → 日柱 丙申（当日）+ 时柱 庚子 → 时柱按**次日**日干起
    """

    def test_sect_2_keeps_current_day_pillar(self) -> None:
        """sect=2（默认）：23:00 的日柱仍为当日，与中午一致。"""
        late = calculate_bazi(BirthInput(2024, 6, 1, 23, 0), sect=2)
        noon = calculate_bazi(BirthInput(2024, 6, 1, 12, 0), sect=2)
        assert late.pillars["day"] == noon.pillars["day"] == "丙申"

    def test_sect_2_hour_pillar_comes_from_next_day_stem(self) -> None:
        """sect=2：时柱由**次日**日干起，因此不可由本盘日柱直接推出。"""
        late = calculate_bazi(BirthInput(2024, 6, 1, 23, 0), sect=2)
        assert late.pillars["hour"] == "庚子"                    # 庚 来自次日丁酉
        assert hour_pillar_by_rule("丙", "子") == "戊子"         # 本日丙干推不出庚子
        assert late.hour_rule_convention().startswith("晚子时")

    def test_sect_1_advances_day_pillar(self) -> None:
        """sect=1：23:00 的日柱算次日，与时柱同源。"""
        late = calculate_bazi(BirthInput(2024, 6, 1, 23, 0), sect=1)
        noon = calculate_bazi(BirthInput(2024, 6, 1, 12, 0), sect=1)
        assert late.pillars["day"] != noon.pillars["day"]
        assert late.pillars["hour"] == hour_pillar_by_rule(late.pillars["day"][0], "子")

    def test_sect_2_late_zi_matches_next_day_zao_zi_hour_pillar(self) -> None:
        """sect=2 下，晚子时与次日早子时的时柱应相同（同属子时之气）。"""
        late = calculate_bazi(BirthInput(2024, 6, 1, 23, 0), sect=2)
        early = calculate_bazi(BirthInput(2024, 6, 2, 0, 0), sect=2)
        assert late.pillars["hour"] == early.pillars["hour"]

    def test_rule_consistency_holds_in_both_sects(self) -> None:
        """两种口径都必须通过自检 —— 检查器需感知 sect，不能把惯例当错误。"""
        for sect in (1, 2):
            for hour in (0, 12, 23):
                c = calculate_bazi(BirthInput(1981, 9, 14, hour, 0), sect=sect)
                assert c.verify_rule_consistency() == [], f"sect={sect} hour={hour} 自检失败"

    def test_noon_unaffected_by_sect(self) -> None:
        """午时（非子时）不受 sect 影响 —— 防止检查器过度放宽。"""
        assert (
            calculate_bazi(BirthInput(2024, 6, 1, 12, 0), sect=1).pillars
            == calculate_bazi(BirthInput(2024, 6, 1, 12, 0), sect=2).pillars
        )


class TestTrueSolarTime:
    def test_standard_meridian_no_shift(self) -> None:
        dt = datetime(2000, 1, 1, 12, 0)
        assert true_solar_time(dt, 120.0, 8.0) == dt

    def test_west_of_meridian_goes_back(self) -> None:
        got = true_solar_time(datetime(2000, 1, 1, 12, 0), 116.4, 8.0)
        assert got == datetime(2000, 1, 1, 11, 45, 36)

    def test_east_of_meridian_goes_forward(self) -> None:
        got = true_solar_time(datetime(2000, 1, 1, 12, 0), 125.0, 8.0)
        assert got > datetime(2000, 1, 1, 12, 0)

    def test_applied_in_resolve(self) -> None:
        r = resolve_birth(BirthInput(1981, 9, 14, 8, 0, longitude=114.3))
        assert r.solar_term_shift_minutes < 0
        assert r.solar_dt < r.local_dt
        assert any("真太阳时" in w for w in r.warnings)

    def test_shift_moves_time_backward(self) -> None:
        """新疆经度（87.6°E）相对东八区标准经线 120°E 偏西 32.4°，
        修正约 -130 分钟，足以跨越时辰边界。"""
        r = resolve_birth(BirthInput(1981, 9, 14, 7, 10, longitude=87.6))
        assert r.solar_term_shift_minutes < -100
        assert r.solar_dt < r.local_dt

    def test_shift_can_change_hour_pillar(self) -> None:
        """修正跨过时辰边界时，时柱必须随之改变 —— 证明修正真的进了排盘。"""
        plain = calculate_bazi(BirthInput(1981, 9, 14, 3, 0))
        shifted = calculate_bazi(BirthInput(1981, 9, 14, 3, 0, longitude=87.6))
        assert plain.pillars["hour"] != shifted.pillars["hour"]
        # 两者日柱应一致（未跨日），确保差异确实来自时支
        assert plain.pillars["day"] == shifted.pillars["day"]

    def test_boundary_warning_direct(self) -> None:
        """直接测边界判定函数（确定性，不受经度换算影响）。

        时辰边界在奇数整点，±30 分钟内即告警。
        """
        from fortune_core.bazi.calendar import _hour_branch_boundary_warning as warn

        assert warn(datetime(2024, 6, 1, 3, 10)) is not None   # 距 03:00 仅 10 分钟
        assert warn(datetime(2024, 6, 1, 4, 45)) is not None   # 距 05:00 仅 15 分钟
        assert warn(datetime(2024, 6, 1, 4, 25)) is None       # 距两侧均 > 30 分钟
        assert warn(datetime(2024, 6, 1, 3, 35)) is None

    def test_boundary_warning_integrated(self) -> None:
        """经度修正把时间推到边界附近时，resolve_birth 应给出告警。"""
        r = resolve_birth(BirthInput(2024, 6, 1, 7, 25, longitude=80.0))
        # (80 - 120) * 4 = -160 分钟 → 07:25 - 02:40 = 04:45，距 05:00 仅 15 分钟
        assert r.solar_dt.hour == 4 and r.solar_dt.minute == 45
        assert any("时辰边界" in w for w in r.warnings)


class TestCalendarInput:
    def test_lunar_input_converts(self) -> None:
        """农历输入应先转公历再排盘：1981 年八月十七 == 公历 1981-09-14。"""
        chart = calculate_bazi(BirthInput(1981, 8, 17, 8, 0, calendar="lunar"))
        assert chart.resolved.local_dt.date() == datetime(1981, 9, 14).date()
        assert chart.pillars["day"] == "乙未"

    def test_lunar_and_solar_agree(self) -> None:
        a = calculate_bazi(BirthInput(1981, 8, 17, 8, 0, calendar="lunar"))
        b = calculate_bazi(BirthInput(1981, 9, 14, 8, 0, calendar="solar"))
        assert a.pillars == b.pillars

    def test_invalid_solar_date(self) -> None:
        with pytest.raises(InvalidInputError):
            calculate_bazi(BirthInput(2024, 2, 30, 12, 0))

    def test_invalid_hour(self) -> None:
        with pytest.raises(InvalidInputError):
            calculate_bazi(BirthInput(2024, 2, 10, 24, 0))

    def test_year_range(self) -> None:
        with pytest.raises(InvalidInputError):
            calculate_bazi(BirthInput(1800, 1, 1, 12, 0))

    def test_timezone_unknown_falls_back_with_warning(self) -> None:
        r = resolve_birth(BirthInput(2024, 2, 10, 12, 0, timezone="Mars/Olympus"))
        assert any("未知时区" in w for w in r.warnings)

    def test_timezone_affects_offset_only(self) -> None:
        r = resolve_birth(BirthInput(2024, 2, 10, 12, 0, timezone="Asia/Shanghai"))
        assert r.utc_offset_hours == 8.0

    def test_calendar_validation(self) -> None:
        b = BirthInput(2024, 2, 10, 12, 0, calendar="julian")  # type: ignore[arg-type]
        with pytest.raises(InvalidInputError):
            b.validate()


class TestFiveElementCounting:
    def test_simple_total_is_eight(self) -> None:
        """本气口径 = 4 天干 + 4 地支本气 = 8 个单位。"""
        s = count_elements(["甲子", "丙寅", "戊午", "庚申"], include_hidden=False)
        assert s.total == 8.0

    def test_simple_breakdown(self) -> None:
        s = count_elements(["甲子", "丙寅", "戊午", "庚申"], include_hidden=False)
        # 天干：甲木 丙火 戊土 庚金；地支本气：子水 寅木 午火 申金
        assert s.counts == {
            "wood": 2.0, "fire": 2.0, "earth": 1.0, "metal": 2.0, "water": 1.0,
        }

    def test_hidden_weights_applied(self) -> None:
        s = count_elements(["甲寅"], include_hidden=True)
        # 甲=1.0木；寅藏 甲(1.0) 丙(0.5) 戊(0.3)
        assert s.counts["wood"] == 2.0
        assert s.counts["fire"] == 0.5
        assert s.counts["earth"] == 0.3

    def test_missing_elements_detected(self) -> None:
        s = count_elements(["甲子", "丙寅", "甲午", "丙寅"], include_hidden=False)
        assert "金" in s.missing or "土" in s.missing

    def test_percentage_sums_to_100(self) -> None:
        s = count_elements(["甲子", "丙寅", "戊午", "庚申"])
        assert abs(sum(s.percentage().values()) - 100.0) < 0.05

    def test_invalid_pillar(self) -> None:
        with pytest.raises(InvalidInputError):
            count_elements(["ABCD"])


class TestStrength:
    def test_rule_consistency_with_chart(self) -> None:
        chart = calculate_bazi(BirthInput(1981, 9, 14, 8, 0))
        s = chart.strength
        assert s.day_master == "乙"
        assert s.day_element == "wood"
        assert s.verdict in ("身强", "身弱", "中和")
        assert abs(s.supported + s.opposing - s.stats.total) < 1e-9

    def test_support_ratio_bounds(self) -> None:
        chart = calculate_bazi(BirthInput(1981, 9, 14, 8, 0))
        assert 0.0 <= chart.strength.support_ratio <= 1.0

    def test_strong_verdict_uses_control_side(self) -> None:
        """身强局：喜用应落在非生扶侧。"""
        s = assess_strength(["甲寅", "甲寅", "甲寅", "甲寅"])
        assert s.verdict == "身强"
        assert "wood" in s.unfavorable
        assert "wood" not in s.favorable

    def test_weak_verdict_uses_support_side(self) -> None:
        """身弱局：喜用应落在生扶侧。"""
        s = assess_strength(["庚申", "庚申", "甲申", "庚申"])
        assert s.verdict == "身弱"
        assert "wood" in s.favorable or "water" in s.favorable

    def test_extreme_all_same_element(self) -> None:
        """四柱全火时，日主应正确识别（日柱第 2 字）且判为身强。"""
        s = assess_strength(["丙午", "丙午", "丙午", "丙午"])
        assert s.day_master == "丙"
        assert s.day_element == "fire"
        assert s.verdict == "身强"

    def test_uncertainties_always_present(self) -> None:
        s = assess_strength(["甲寅", "甲寅", "甲寅", "甲寅"])
        assert len(s.uncertainties) >= 2
        assert any("阈值" in u for u in s.uncertainties)

    def test_requires_four_pillars(self) -> None:
        with pytest.raises(InvalidInputError):
            assess_strength(["甲寅", "甲寅", "甲寅"])


class TestLayers:
    def test_facts_and_tradition_are_separate(self) -> None:
        chart = calculate_bazi(BirthInput(1981, 9, 14, 8, 0))
        facts, tradition = chart.to_facts(), chart.to_tradition()
        assert "pillars" in facts
        assert "day_master_strength" in tradition
        assert set(facts) & set(tradition) == set(), "FACT 与 TRADITION 不得有同名字段（防污染）"

    def test_facts_contain_no_interpretation(self) -> None:
        """FACT 层不得出现断语式字段。"""
        chart = calculate_bazi(BirthInput(1981, 9, 14, 8, 0))
        facts = chart.to_facts()
        assert "summary" not in facts
        assert "suggestions" not in facts
        assert facts["rule_consistency"] == []

    def test_tradition_carries_uncertainties(self) -> None:
        chart = calculate_bazi(BirthInput(1981, 9, 14, 8, 0))
        assert chart.to_tradition()["uncertainties"]
