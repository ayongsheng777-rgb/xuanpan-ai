"""八字神煞与大运测试。

验证策略（对齐 RULE-001 / RULE-007，不复制被测实现）：
1. 神煞表：用 `verify_tables` 的独立性质（三合局分组一致性、红鸾天喜对冲、完整度）
   约束硬编码表；再用**手工核过的已知锚点**验证查找结果。
2. 大运：用「阳年男顺排 / 阴年女顺排 / 阳年女逆排 / 阴年男逆排」四条规则
   独立断言方向，不依赖被测的 `yun_direction`。
"""

from __future__ import annotations

import pytest

from fortune_core.bazi import BirthInput, calculate_bazi
from fortune_core.bazi.dynamics import yun_direction
from fortune_core.bazi.shensha import (
    HUAGAI,
    JIANGXING,
    TIANDE,
    TIANYI_GUIREN,
    WENCHANG,
    YIMA,
    YUEDE,
    find_shensha,
    verify_tables,
)


# --------------------------------------------------------------------------
# 神煞表自证
# --------------------------------------------------------------------------


class TestShenShaTables:
    def test_verify_tables_clean(self) -> None:
        """所有口诀表应通过独立性质校验（三合局分组 / 红鸾天喜对冲 / 完整度）。"""
        assert verify_tables() == []

    def test_tianyi_guiren_known(self) -> None:
        """天乙贵人锚点：甲戊庚 → 丑未，乙己 → 子申（手工核对口诀）。"""
        assert TIANYI_GUIREN["甲"] == ("丑", "未")
        assert TIANYI_GUIREN["庚"] == ("丑", "未")
        assert TIANYI_GUIREN["乙"] == ("子", "申")
        assert TIANYI_GUIREN["辛"] == ("午", "寅")

    def test_wenchang_known(self) -> None:
        """文昌锚点：甲乙巳午（甲巳乙午）。"""
        assert WENCHANG["甲"] == "巳"
        assert WENCHANG["乙"] == "午"

    def test_sanzai_triad_consistency(self) -> None:
        """三合局内桃花/驿马/华盖/将星必须同值（口诀结构，非偶然）。"""
        # 申子辰水局 → 桃花在酉、驿马在寅、华盖在辰、将星在子
        for z in ("申", "子", "辰"):
            from fortune_core.bazi.shensha import TAOHUA

            assert HUAGAI[z] == "辰"
            assert JIANGXING[z] == "子"
            assert YIMA[z] == "寅"

    def test_tiande_yuede_known(self) -> None:
        """天德月德锚点：寅月天德丁、月德丙（手工核对）。"""
        assert TIANDE["寅"] == "丁"
        assert YUEDE["寅"] == "丙"
        assert YUEDE["午"] == "丙"  # 寅午戌月德同丙


# --------------------------------------------------------------------------
# 神煞查找
# --------------------------------------------------------------------------


class TestFindShenSha:
    def test_known_chart_shensha(self) -> None:
        """1990-05-20 乙酉日：文昌在午、将星在酉（日支酉 → 将星酉，手工核）。"""
        r = find_shensha({"year": "庚午", "month": "辛巳", "day": "乙酉", "hour": "辛巳"})
        assert r.gan_anchor["文昌贵人"] == ["午"]
        assert r.zhi_anchor["将星"] == ["酉"]

    def test_absent_shensha_omitted(self) -> None:
        """未命中的神煞不应出现在结果里。"""
        r = find_shensha({"year": "甲子", "month": "甲子", "day": "甲子", "hour": "甲子"})
        # 甲子日：无天乙贵人落在四支（丑未不在盘内）
        assert "天乙贵人" not in r.gan_anchor

    def test_invalid_pillar_raises(self) -> None:
        from fortune_core.exceptions import InvalidInputError

        with pytest.raises(InvalidInputError):
            find_shensha({"year": "庚午", "month": "辛巳", "day": "乙酉"})  # 缺时柱


# --------------------------------------------------------------------------
# 大运顺逆
# --------------------------------------------------------------------------


class TestYunDirection:
    """大运顺逆规则独立断言：阳年男/阴年女顺，阴年男/阳年女逆。"""

    def test_yang_year_male_forward(self) -> None:
        # 庚午（阳）男 → 顺排
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0, gender="male"))
        assert c.to_facts()["da_yun"]["forward"] is True
        assert c.yun.start_age_text is not None

    def test_yang_year_female_reverse(self) -> None:
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0, gender="female"))
        assert c.to_facts()["da_yun"]["forward"] is False

    def test_yin_year_female_forward(self) -> None:
        # 辛未（阴）女 → 顺排
        c = calculate_bazi(BirthInput(1991, 5, 20, 10, 0, gender="female"))
        assert c.to_facts()["da_yun"]["forward"] is True

    def test_yin_year_male_reverse(self) -> None:
        c = calculate_bazi(BirthInput(1991, 5, 20, 10, 0, gender="male"))
        assert c.to_facts()["da_yun"]["forward"] is False

    def test_yun_direction_helper(self) -> None:
        assert yun_direction("yang", "male") == "顺排"
        assert yun_direction("yang", "female") == "逆排"
        assert yun_direction("yin", "female") == "顺排"
        assert yun_direction("yin", "male") == "逆排"
        assert yun_direction("yang", None) is None
        assert yun_direction("yin", "other") is None


class TestDaYunStructure:
    def test_first_step_is_before_start(self) -> None:
        """第 0 步大运是「起运前」空档，干支为空。"""
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0, gender="male"))
        dy = c.to_facts()["da_yun"]
        assert dy["da_yun"][0]["gan_zhi"] == ""
        assert dy["da_yun"][1]["gan_zhi"] != ""

    def test_liu_nian_skips_before_start(self) -> None:
        """流年应从第一步大运（index 1）开始，不含起运前。"""
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0, gender="male"))
        dy = c.to_facts()["da_yun"]
        assert "0" not in dy["liu_nian"]
        assert "1" in dy["liu_nian"]

    def test_no_gender_unavailable(self) -> None:
        """未填性别：不排大运，明确说明原因（RULE-008 不静默猜测）。"""
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0))
        dy = c.to_facts()["da_yun"]
        assert dy["available"] is False
        assert "性别" in dy["reason"]


# --------------------------------------------------------------------------
# 长生十二宫 / 身宫 / 胎息
# --------------------------------------------------------------------------


class TestDiShiAndPalaces:
    def test_di_shi_present(self) -> None:
        """长生十二宫（地势）四柱齐全。"""
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0, gender="male"))
        di_shi = c.to_facts()["di_shi"]
        assert set(di_shi) == {"年柱", "月柱", "日柱", "时柱"}
        # 乙酉日 → 酉为乙木的「绝」位（手工核：木长生在亥，酉为绝）
        assert di_shi["日柱"] == "绝"

    def test_shen_gong_tai_xi_present(self) -> None:
        """身宫、胎息非空（库提供）。"""
        c = calculate_bazi(BirthInput(1990, 5, 20, 10, 0, gender="male"))
        assert c.to_facts()["shen_gong"]
        assert c.to_facts()["tai_xi"]
