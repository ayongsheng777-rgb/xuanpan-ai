"""基础常量与映射的测试。

这些是整个内核的地基：**一张表错一位，整盘结果全错，而且不会报错**。
"""

from __future__ import annotations

import pytest

from fortune_core.constants import (
    DIZHI,
    GAN_ELEMENT,
    GAN_YINYANG,
    GUA_ELEMENT,
    GUA_YAO,
    JIAZI_60,
    NAYIN_30,
    TIANGAN,
    ZHI_CANGGAN,
    ZHI_ELEMENT,
    ZHI_YINYANG,
    ganzhi_from_index,
    jiazi_index,
    nayin_of,
    shishen,
)


class TestGanZhiBasics:
    def test_lengths(self) -> None:
        assert len(TIANGAN) == 10
        assert len(DIZHI) == 12
        assert len(JIAZI_60) == 60
        assert len(NAYIN_30) == 30

    def test_jiazi_uniqueness(self) -> None:
        assert len(set(JIAZI_60)) == 60, "六十甲子不可重复"

    def test_jiazi_first_last(self) -> None:
        assert JIAZI_60[0] == "甲子"
        assert JIAZI_60[59] == "癸亥"

    @pytest.mark.parametrize("index", range(60))
    def test_index_roundtrip(self, index: int) -> None:
        gz = ganzhi_from_index(index)
        assert jiazi_index(gz) == index

    def test_invalid_ganzhi_rejected(self) -> None:
        for bad in ("甲丑", "乙子", "甲", "甲子子", "", "XM"):
            with pytest.raises(ValueError):
                jiazi_index(bad)

    def test_ganzhi_parity_invariant(self) -> None:
        """六十甲子中天干地支阴阳必同 —— 这是干支体系的结构性约束。"""
        for gz in JIAZI_60:
            assert GAN_YINYANG[gz[0]] == ZHI_YINYANG[gz[1]], f"{gz} 阴阳不匹配"


class TestElements:
    def test_gan_element(self) -> None:
        assert GAN_ELEMENT["甲"] == GAN_ELEMENT["乙"] == "wood"
        assert GAN_ELEMENT["丙"] == GAN_ELEMENT["丁"] == "fire"
        assert GAN_ELEMENT["戊"] == GAN_ELEMENT["己"] == "earth"
        assert GAN_ELEMENT["庚"] == GAN_ELEMENT["辛"] == "metal"
        assert GAN_ELEMENT["壬"] == GAN_ELEMENT["癸"] == "water"

    def test_zhi_element(self) -> None:
        assert ZHI_ELEMENT["子"] == "water"
        assert ZHI_ELEMENT["午"] == "fire"
        assert ZHI_ELEMENT["卯"] == "wood"
        assert ZHI_ELEMENT["酉"] == "metal"
        assert ZHI_ELEMENT["辰"] == "earth"

    def test_alternating_yinyang(self) -> None:
        """天干地支阴阳均按序交替，这是干支序的基础性质。"""
        for i, gan in enumerate(TIANGAN):
            assert GAN_YINYANG[gan] == ("yang" if i % 2 == 0 else "yin")
        for i, zhi in enumerate(DIZHI):
            assert ZHI_YINYANG[zhi] == ("yang" if i % 2 == 0 else "yin")

    def test_canggan_covers_12_zhi(self) -> None:
        assert set(ZHI_CANGGAN) == set(DIZHI)
        for zhi, gans in ZHI_CANGGAN.items():
            assert 1 <= len(gans) <= 3, f"{zhi} 藏干数量异常：{gans}"
            for g in gans:
                assert g in TIANGAN, f"{zhi} 藏干含非法天干：{g}"

    def test_canggan_standard_samples(self) -> None:
        assert ZHI_CANGGAN["子"] == ("癸",)
        assert ZHI_CANGGAN["卯"] == ("乙",)
        assert ZHI_CANGGAN["寅"] == ("甲", "丙", "戊")
        assert ZHI_CANGGAN["亥"] == ("壬", "甲")


class TestNayin:
    @pytest.mark.parametrize(
        ("ganzhi", "expected"),
        [
            ("甲子", "海中金"),
            ("乙丑", "海中金"),   # 与甲子同组
            ("丙寅", "炉中火"),
            ("庚申", "石榴木"),
            ("辛酉", "石榴木"),   # 与庚申同组
            ("庚辰", "白蜡金"),
            ("乙未", "沙中金"),
            ("丁酉", "山下火"),
            ("壬戌", "大海水"),
            ("癸亥", "大海水"),
        ],
    )
    def test_nayin(self, ganzhi: str, expected: str) -> None:
        assert nayin_of(ganzhi) == expected

    def test_nayin_pairing(self) -> None:
        """纳音每两干支配同一纳音（60/2 = 30 组）。"""
        pairs = [nayin_of(ganzhi_from_index(i)) for i in range(60)]
        for i in range(0, 60, 2):
            assert pairs[i] == pairs[i + 1]


class TestShishen:
    @pytest.mark.parametrize(
        ("day_gan", "other", "expected"),
        [
            ("甲", "甲", "比肩"), ("甲", "乙", "劫财"),
            ("甲", "丙", "食神"), ("甲", "丁", "伤官"),
            ("甲", "戊", "偏财"), ("甲", "己", "正财"),
            ("甲", "庚", "七杀"), ("甲", "辛", "正官"),
            ("甲", "壬", "偏印"), ("甲", "癸", "正印"),
            # 换日主再验一组，防止只对甲日干成立
            ("乙", "乙", "比肩"), ("乙", "丙", "伤官"), ("乙", "庚", "正官"), ("乙", "壬", "正印"),
        ],
    )
    def test_shishen(self, day_gan: str, other: str, expected: str) -> None:
        assert shishen(day_gan, other) == expected

    def test_ten_gods_complete(self) -> None:
        """任一日干对其他 10 天干应恰好覆盖十神各一次（除自身为比肩）。"""
        for day_gan in TIANGAN:
            got = [shishen(day_gan, g) for g in TIANGAN]
            assert len(set(got)) == 10, f"{day_gan}日的十神覆盖不全：{got}"


class TestGua:
    def test_eight_gua_yao(self) -> None:
        """八卦三爻编码自检：乾三连、坤六断、离中虚、坎中满、兑上缺、巽下断、震仰盂、艮覆碗。"""
        assert GUA_YAO["乾"] == (1, 1, 1)
        assert GUA_YAO["坤"] == (0, 0, 0)
        assert GUA_YAO["离"] == (1, 0, 1)   # 中虚
        assert GUA_YAO["坎"] == (0, 1, 0)   # 中满
        assert GUA_YAO["兑"] == (1, 1, 0)   # 上缺
        assert GUA_YAO["巽"] == (0, 1, 1)   # 下断
        assert GUA_YAO["震"] == (1, 0, 0)   # 仰盂（下实）
        assert GUA_YAO["艮"] == (0, 0, 1)   # 覆碗（上实）

    def test_yao_codes_unique(self) -> None:
        assert len(set(GUA_YAO.values())) == 8

    def test_gua_element(self) -> None:
        assert GUA_ELEMENT["乾"] == GUA_ELEMENT["兑"] == "metal"
        assert GUA_ELEMENT["震"] == GUA_ELEMENT["巽"] == "wood"
        assert GUA_ELEMENT["艮"] == GUA_ELEMENT["坤"] == "earth"
        assert GUA_ELEMENT["坎"] == "water"
        assert GUA_ELEMENT["离"] == "fire"
