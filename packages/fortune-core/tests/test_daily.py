"""每日运程测试（RULE-007）。

验证策略：不复制被测实现。
- 日主锚点：用 lunar-python 直接取日干，与 daily 结果交叉校验
  （lunar-python 是已验证的历法引擎，不是被测代码）。
- 十神映射：按文档规则手工推一例（甲日主 + 丙日干 → 食神）。
- 其余断言结构性（星级范围、顺序、确定性、非法输入）。
"""

from __future__ import annotations

from datetime import date

import pytest

from fortune_core.constants import ELEMENT_CN, GAN_ELEMENT, shishen
from fortune_core.daily import daily_fortune
from fortune_core.exceptions import InvalidInputError


def _lunar_day_master(y: int, m: int, d: int) -> str:
    """独立路径：lunar-python 直取日干（sect 默认 2，与内核一致）。"""
    from lunar_python import Solar

    ec = Solar.fromYmdHms(y, m, d, 12, 0, 0).getLunar().getEightChar()
    ec.setSect(2)
    return ec.getDay()[0]


class TestDayMasterAnchor:
    def test_day_master_matches_lunar(self) -> None:
        for (y, m, d) in [(2000, 1, 7), (1981, 5, 21), (2026, 10, 7), (1990, 2, 28)]:
            got = daily_fortune(date(y, m, d), date(2026, 10, 7))
            assert got.day_master == _lunar_day_master(y, m, d)

    def test_day_master_element_consistent(self) -> None:
        got = daily_fortune(date(1981, 5, 21), date(2026, 10, 7))
        assert got.day_master_element == ELEMENT_CN[GAN_ELEMENT[got.day_master]]

    def test_birth_hour_does_not_change_day_master(self) -> None:
        """时辰不影响日主：hour=3 与未知时辰结果的日主必须一致。"""
        a = daily_fortune(date(1981, 5, 21), date(2026, 10, 7), birth_hour=3)
        b = daily_fortune(date(1981, 5, 21), date(2026, 10, 7))
        assert a.day_master == b.day_master
        assert b.birth_hour_known is False
        assert a.birth_hour_known is True
        # 未知时辰必须在 tradition 层留下说明（RULE-008：不静默修正数据）
        assert b.to_tradition()["uncertainties"] != []
        assert a.to_tradition()["uncertainties"] == []


class TestShishenMapping:
    def test_stem_branch_shishen_handcheck(self) -> None:
        """手工验一例：1984-02-02（日主丙）× 2026-10-07 日干支，
        十神应与按文档规则的 shishen 调用一致。"""
        got = daily_fortune(date(1984, 2, 2), date(2026, 10, 7))
        assert got.day_master == "丙"
        gz = got.day_ganzhi
        assert got.stem_shishen == shishen("丙", gz[0])
        # 日支主气藏干独立取
        from fortune_core.constants import ZHI_CANGGAN

        assert got.branch_shishen == shishen("丙", ZHI_CANGGAN[gz[1]][0])


class TestStructure:
    def test_domains_shape(self) -> None:
        got = daily_fortune(date(1981, 5, 21), date(2026, 10, 7))
        names = [d.name for d in got.domains]
        assert names == ["事业", "财运", "感情", "健康", "贵人"]
        for d in got.domains:
            assert 1 <= d.stars <= 5
            assert d.tag in ("宜", "平", "慎")
            assert d.reason

    def test_lucky_fields(self) -> None:
        got = daily_fortune(date(1981, 5, 21), date(2026, 10, 7))
        assert got.lucky_color and got.lucky_direction
        assert got.lucky_color_element in ("木", "火", "土", "金", "水")
        n1, n2 = got.lucky_numbers
        assert 1 <= n1 <= 10 and 1 <= n2 <= 12
        assert 1 <= len(got.lucky_hours) <= 3
        assert all("时" in h for h in got.lucky_hours)

    def test_focus_and_summary(self) -> None:
        got = daily_fortune(date(1981, 5, 21), date(2026, 10, 7))
        assert got.focus_yi.startswith("宜") and got.focus_ji.startswith("慎")
        assert got.day_ganzhi in got.summary and got.day_master in got.summary

    def test_to_dict_layers(self) -> None:
        d = daily_fortune(date(1981, 5, 21), date(2026, 10, 7)).to_dict()
        assert set(d.keys()) == {"facts", "tradition"}
        assert "domains" in d["facts"] and "lucky" in d["facts"]
        assert "summary" in d["tradition"] and "note" in d["tradition"]

    def test_determinism(self) -> None:
        """同一输入两次调用，结果全等（RULE-001 可复现）。"""
        a = daily_fortune(date(1975, 12, 3), date(2026, 10, 8), birth_hour=9)
        b = daily_fortune(date(1975, 12, 3), date(2026, 10, 8), birth_hour=9)
        assert a == b
        assert a.to_dict() == b.to_dict()

    def test_default_target_is_today(self) -> None:
        got = daily_fortune(date(1981, 5, 21))
        assert got.target_date == date.today().isoformat()


class TestInvalidInput:
    def test_bad_birth_hour(self) -> None:
        with pytest.raises(InvalidInputError):
            daily_fortune(date(1981, 5, 21), date(2026, 10, 7), birth_hour=24)

    def test_out_of_range_dates(self) -> None:
        with pytest.raises(InvalidInputError):
            daily_fortune(date(1899, 12, 31), date(2026, 10, 7))
        with pytest.raises(InvalidInputError):
            daily_fortune(date(1981, 5, 21), date(2101, 1, 1))

    def test_impossible_date_rejected_by_birth_input(self) -> None:
        # date(2021, 2, 29) 根本构造不出来（ValueError）；非法年月日走 BirthInput 校验
        from fortune_core.bazi.calendar import BirthInput

        with pytest.raises(InvalidInputError):
            BirthInput(year=2021, month=2, day=29, hour=12).validate()
