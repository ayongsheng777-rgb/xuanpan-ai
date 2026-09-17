"""黄历 / 择日测试。

验证策略（RULE-001 / RULE-007，不复制被测实现）：
1. 建除十二神：用「月支 + 日支」独立推导公式，与库结果交叉校验（非交节日）
2. 日冲：日支的对冲位（相隔六位），独立断言
3. 交节日：口径差被正确标注，而不是误报为错误
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from fortune_core import calculate_almanac
from fortune_core.almanac import JIANCHU_12, derive_zhi_xing
from fortune_core.constants import DIZHI


class TestDeriveZhiXing:
    """建除十二神独立推导公式。"""

    def test_derive_basic(self) -> None:
        # 月支酉 + 日支午 → 收（2026-09-17 实际值）
        assert derive_zhi_xing("酉", "午") == "收"
        # 月支寅 + 日支寅 → 建（正月建寅）
        assert derive_zhi_xing("寅", "寅") == "建"

    def test_derive_cycles(self) -> None:
        """建除随日支顺行：月支寅（序2）为建，日支每进一位值星进一位。"""
        month_idx = DIZHI.index("寅")
        for i in range(12):
            day = DIZHI[i]
            assert derive_zhi_xing("寅", day) == JIANCHU_12[(i - month_idx) % 12]

    def test_invalid_zhi_raises(self) -> None:
        from fortune_core.exceptions import InvalidInputError

        with pytest.raises(InvalidInputError):
            derive_zhi_xing("x", "午")


class TestAlmanacFacts:
    def test_known_day(self) -> None:
        """2026-09-17 锚点：甲午日、收日、角宿、金匮（黄道）、冲鼠。"""
        r = calculate_almanac(date(2026, 9, 17))
        f = r.to_facts()
        assert f["gan_zhi"]["day"] == "甲午"
        assert f["jian_chu"] == "收"
        assert f["xiu"]["name"] == "角"
        assert f["tian_shen"]["name"] == "金匮"
        assert f["tian_shen"]["type"] == "黄道"
        assert f["chong"]["shengxiao"] == "鼠"
        assert f["chong"]["zhi"] == "子"

    def test_rule_consistency_clean_on_normal_day(self) -> None:
        """非交节日：建除推导应与库一致，rule_consistency 为空。"""
        r = calculate_almanac(date(2026, 9, 17))
        assert r.rule_consistency == []

    def test_day_chong_is_opposite_zhi(self) -> None:
        """日冲 = 日支对冲位（相隔六位），独立断言。"""
        r = calculate_almanac(date(2026, 9, 17))
        day_zhi = r.day_ganzhi[1]  # 甲午 → 午
        assert r.chong == DIZHI[(DIZHI.index(day_zhi) + 6) % 12]

    def test_yi_ji_not_empty(self) -> None:
        """宜忌、吉神凶煞、彭祖百忌均有内容。"""
        r = calculate_almanac(date(2026, 9, 17))
        assert r.yi
        assert r.ji
        assert r.ji_shen
        assert r.xiong_sha
        assert r.pengzu_gan and r.pengzu_zhi

    def test_huang_dao_flag(self) -> None:
        """is_huang_dao 与 type 一致。"""
        r = calculate_almanac(date(2026, 9, 17))
        assert r.is_huang_dao is (r.tian_shen_type == "黄道")


class TestJieQiBoundary:
    def test_jieqi_day_marked_not_error(self) -> None:
        """交节日若口径差，标注为「交节」而非普通错误。"""
        # 2025-02-03 立春，已知建除口径差
        r = calculate_almanac(date(2025, 2, 3))
        # 该日可能有口径差；若有，必须带「交节」字样
        for p in r.rule_consistency:
            assert "交节" in p, f"交节日的口径差未正确标注：{p}"

    def test_accepts_datetime(self) -> None:
        """传入 datetime 与 date 等价（取年月日）。"""
        r1 = calculate_almanac(datetime(2026, 9, 17, 8, 30))
        r2 = calculate_almanac(date(2026, 9, 17))
        assert r1.day_ganzhi == r2.day_ganzhi
        assert r1.jian_chu == r2.jian_chu


class TestToDict:
    def test_layered_output(self) -> None:
        """FACT / TRADITION 两层分离。"""
        r = calculate_almanac(date(2026, 9, 17))
        d = r.to_dict()
        assert set(d) == {"facts", "tradition"}
        assert "yi" in d["facts"]
        assert "summary" in d["tradition"]
