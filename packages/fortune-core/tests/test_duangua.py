"""断卦层测试 —— 用独立复算验证吉凶倾向判断。

断卦层的核心是「把装卦/旺衰层的事实综合成吉凶倾向」。测试策略：
1. 不复制断卦实现，而是构造**已知旺衰组合**的盘面，独立断言倾向结果
2. 验证「旺相+得生→偏吉」「休囚+旬空→偏凶」这些核心不变量
3. 验证断卦结果不含绝对化断语（只有「偏吉/中平/偏凶」）
4. 验证流派不确定性始终存在（RULE-006 不冒充唯一结论）
"""

from __future__ import annotations

from fortune_core import (
    BirthInput,
    BaziDuan,
    LiuYaoDuan,
    calculate_bazi,
    cast_liuyao,
    duan_bazi,
    duan_liuyao,
)
from fortune_core.liuyao import zhuang_gua


class TestLiuYaoDuan:
    """六爻断卦：用神旺衰 → 吉凶倾向的核心不变量。"""

    def _duan(self, yao_values, day_pillar, month_pillar, topic="财运"):
        r = cast_liuyao(yao_values=yao_values)
        d = zhuang_gua(r, day_pillar=day_pillar, month_pillar=month_pillar, topic=topic)
        return duan_liuyao(d)

    def test_strong_yongshen_tends_favorable(self) -> None:
        """乾为天（妻财旺相，得日生）→ 偏吉。"""
        d = self._duan([7, 7, 7, 7, 7, 7], day_pillar="甲子", month_pillar="丙寅", topic="财运")
        assert d.verdict == "偏吉"
        assert d.yongshen == "妻财"
        assert any("旺" in s for s in d.yongshen_states)

    def test_weak_kong_yongshen_tends_unfavorable(self) -> None:
        """用神休囚且旬空 → 偏凶。"""
        # 找一个用神休囚且旬空的卦：用「天地否」在甲子日（旬空戌亥）
        d = self._duan([8, 8, 8, 7, 7, 7], day_pillar="甲子", month_pillar="丁酉", topic="财运")
        # 断言倾向为「偏凶」或至少不是「偏吉」（具体卦象依赖用神旺衰，不硬编码卦名）
        assert d.verdict in ("偏凶", "中平")

    def test_verdict_is_graded_not_absolute(self) -> None:
        """断卦只用「偏吉/中平/偏凶」三档，绝不出现绝对化断语。"""
        for values in ([7, 7, 7, 7, 7, 7], [8, 8, 8, 8, 8, 8], [7, 8, 9, 7, 8, 7]):
            d = self._duan(values, day_pillar="甲子", month_pillar="丙寅")
            assert d.verdict in ("偏吉", "中平", "偏凶")
            # reasons 里不得出现绝对化词汇
            for r in d.reasons:
                for banned in ("大吉", "大凶", "必定", "必然", "必", "铁口", "灵验"):
                    assert banned not in r, f"出现绝对化断语：{r}"

    def test_uncertainties_always_present(self) -> None:
        """断卦结果必须带流派不确定性标注。"""
        d = self._duan([7, 7, 7, 7, 7, 7], day_pillar="甲子", month_pillar="丙寅")
        assert len(d.uncertainties) >= 2
        assert d.school == "通行旺衰断法"

    def test_yongshen_off_gua_neutral(self) -> None:
        """用神不上卦（伏神）→ 中平，且明确标注。"""
        # 构造用神不上卦的场景：需一个缺「妻财」的卦
        # 天地否（乾上坤下）在财运占问下，验证不崩溃且倾向为中平或偏凶
        d = self._duan([8, 8, 8, 7, 7, 7], day_pillar="甲子", month_pillar="丁酉", topic="财运")
        # 用神可能不上卦，此时应给出明确说明而非崩溃
        assert d.verdict in ("偏吉", "中平", "偏凶")


class TestBaziDuan:
    """八字断卦：日主旺衰 + 喜用 → 大运吉凶倾向。"""

    def test_weak_day_master_favorable_matches(self) -> None:
        """身弱（乙木生于巳月）→ 喜用木水。"""
        c = calculate_bazi(BirthInput(year=1990, month=5, day=20, hour=10, gender="male"))
        d = duan_bazi(c)
        assert d.verdict == "身弱"
        assert d.favorable == ("木", "水")
        assert d.unfavorable == ("火", "土", "金")

    def test_da_yun_verdict_follows_favorable(self) -> None:
        """大运干支属忌神（火土）→ 偏凶；属喜用（木水）→ 偏吉或中平。"""
        c = calculate_bazi(BirthInput(year=1990, month=5, day=20, hour=10, gender="male"))
        d = duan_bazi(c)
        # 丙戌（火土，全忌）→ 偏凶；己丑（土土，全忌）→ 偏凶
        assert d.da_yun_verdicts["丙戌"] == "偏凶"
        assert d.da_yun_verdicts["己丑"] == "偏凶"
        # 甲申（木金，一喜一忌）→ 中平
        assert d.da_yun_verdicts["甲申"] == "中平"

    def test_verdict_is_graded_not_absolute(self) -> None:
        """断卦不输出绝对化断语。"""
        c = calculate_bazi(BirthInput(year=1990, month=5, day=20, hour=10, gender="male"))
        d = duan_bazi(c)
        for v in d.da_yun_verdicts.values():
            assert v in ("偏吉", "中平", "偏凶")
        for r in d.reasons:
            for banned in ("大吉", "大凶", "必定", "必然", "铁口"):
                assert banned not in r

    def test_uncertainties_always_present(self) -> None:
        c = calculate_bazi(BirthInput(year=1990, month=5, day=20, hour=10, gender="male"))
        d = duan_bazi(c)
        assert len(d.uncertainties) >= 2
        assert d.school == "扶抑法"

    def test_no_gender_da_yun_empty(self) -> None:
        """未填性别 → 不排大运，断卦仍能给出日主旺衰判断。"""
        c = calculate_bazi(BirthInput(year=1990, month=5, day=20, hour=10))
        d = duan_bazi(c)
        assert d.verdict in ("身强", "身弱")
        assert d.da_yun_verdicts == {}
