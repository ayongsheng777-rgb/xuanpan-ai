"""六爻装卦层测试（RULE-001 / RULE-007）。

验证策略 —— **不复制被测表，用传世规则独立复算**：

1. 纳甲：不用 `NAJIA` 自身做断言，而是验证三条可独立推出的性质
   （内外卦起始地支相差 6 位、阳卦顺行 +2 / 阴卦逆行 −2、天干符合纳甲歌归干）
2. 八宫：用「变爻规则」独立推导 64 卦归属，与硬编码表比对
3. 旬空：用「旬首地支 + 10 / + 11」独立复算
4. 装卦聚合：以手排结果逐位对拍

这样即使实现表被写错，只要写错的位置不自洽，测试就会红。
"""

from __future__ import annotations

import pytest

from fortune_core.constants import DIZHI, TIANGAN
from fortune_core.exceptions import InvalidInputError
from fortune_core.liuyao import (
    GUA_PALACE,
    LIUCHONG_GUA,
    LIUHE_GUA,
    NAJIA,
    NAJIA_GAN,
    PALACE_GUA,
    PALACE_STAGE,
    SHI_YING_YAO,
    cast_liuyao,
    day_relation_of,
    derive_palace_gua,
    is_liuchong_gua,
    is_liuhe_gua,
    liu_qin,
    liu_shen_for_day,
    month_state_of,
    najia_ganzhi_for,
    palace_of,
    palace_stage_of,
    shi_ying_of,
    xun_kong_of,
    yongshen_of,
    zhi_chong,
    zhi_liuhe,
    zhuang_gua,
)

#：四阳卦（地支顺行）/ 四阴卦（地支逆行）
YANG_GUA = ("乾", "震", "坎", "艮")
YIN_GUA = ("巽", "离", "坤", "兑")


# ==========================================================================
# 一、纳甲 —— 传世性质独立复算
# ==========================================================================


class TestNajia:
    def test_covers_all_eight_gua(self):
        assert set(NAJIA) == set(YANG_GUA) | set(YIN_GUA)

    def test_outer_starts_six_branches_after_inner(self):
        """内外卦起始地支恒相差 6 位 —— 纳甲歌的内在规律，独立于具体值。"""
        for gua, (inner, outer) in NAJIA.items():
            delta = (DIZHI.index(outer[0][1]) - DIZHI.index(inner[0][1])) % 12
            assert delta == 6, f"{gua}：内{inner[0]} 外{outer[0]} 相差 {delta} 位"

    @pytest.mark.parametrize("gua", YANG_GUA)
    def test_yang_gua_branches_advance_by_two(self, gua: str):
        """阳卦（乾震坎艮）地支顺行，每爻 +2。"""
        for trio in NAJIA[gua]:
            idx = [DIZHI.index(g[1]) for g in trio]
            assert (idx[1] - idx[0]) % 12 == 2
            assert (idx[2] - idx[1]) % 12 == 2

    @pytest.mark.parametrize("gua", YIN_GUA)
    def test_yin_gua_branches_recede_by_two(self, gua: str):
        """阴卦（巽离坤兑）地支逆行，每爻 −2。"""
        for trio in NAJIA[gua]:
            idx = [DIZHI.index(g[1]) for g in trio]
            assert (idx[0] - idx[1]) % 12 == 2
            assert (idx[1] - idx[2]) % 12 == 2

    def test_gan_matches_najia_song(self):
        """天干符合纳甲歌：乾纳甲壬、坤纳乙癸，余卦内外同干。"""
        for gua, (inner, outer) in NAJIA.items():
            allowed = NAJIA_GAN[gua]
            assert inner[0][0] in allowed and outer[0][0] in allowed
            assert len({g[0] for g in inner}) == 1
            assert len({g[0] for g in outer}) == 1
            if gua in ("乾", "坤"):
                assert inner[0][0] != outer[0][0], "乾坤内外须纳不同天干"
            else:
                assert inner[0][0] == outer[0][0], f"{gua} 内外应同干"

    def test_gan_is_valid_tiangan(self):
        for trio in NAJIA.values():
            for group in trio:
                for gz in group:
                    assert gz[0] in TIANGAN and gz[1] in DIZHI

    def test_najia_ganzhi_for_pure_gua(self):
        assert najia_ganzhi_for("乾", "乾") == [
            "甲子", "甲寅", "甲辰", "壬午", "壬申", "壬戌",
        ]
        # 内坤外乾 = 天地否
        assert najia_ganzhi_for("坤", "乾") == [
            "乙未", "乙巳", "乙卯", "壬午", "壬申", "壬戌",
        ]

    def test_najia_of_rejects_unknown(self):
        from fortune_core.liuyao import najia_of

        with pytest.raises(InvalidInputError, match="未知八卦"):
            najia_of("震震")


# ==========================================================================
# 二、京房八宫卦序 —— 变爻规则独立推导
# ==========================================================================


class TestPalaceGua:
    @pytest.mark.parametrize("palace", list(PALACE_GUA))
    def test_hardcoded_table_equals_derived(self, palace: str):
        """硬编码表必须等于用变爻规则独立推导的结果（RULE-001 自证）。"""
        assert PALACE_GUA[palace] == derive_palace_gua(palace)

    def test_each_palace_has_eight_gua(self):
        for palace, guas in PALACE_GUA.items():
            assert len(guas) == 8, palace
            assert len(set(guas)) == 8, f"{palace} 宫内有重复"

    def test_sixty_four_gua_all_covered_exactly_once(self):
        """八宫共 64 卦，必须恰好覆盖六十四卦、无重无漏。"""
        all_gua = [g for guas in PALACE_GUA.values() for g in guas]
        assert len(all_gua) == 64
        assert len(set(all_gua)) == 64

        from fortune_core.liuyao import LIUSHISI_GUA

        table_gua = {g for row in LIUSHISI_GUA.values() for g in row.values()}
        assert set(all_gua) == table_gua

    def test_first_gua_of_palace_is_pure_gua(self):
        for palace, guas in PALACE_GUA.items():
            assert guas[0] == palace

    def test_stage_names(self):
        assert PALACE_STAGE[0] == "本宫" and PALACE_STAGE[6] == "游魂"
        assert PALACE_STAGE[7] == "归魂"
        assert palace_stage_of("乾") == "本宫"
        assert palace_stage_of("晋") == "游魂"
        assert palace_stage_of("大有") == "归魂"

    def test_palace_of_samples(self):
        assert palace_of("乾") == ("乾", 0)
        assert palace_of("姤") == ("乾", 1)
        assert palace_of("比") == ("坤", 7)
        assert palace_of("师") == ("坎", 7)
        assert palace_of("未济") == ("离", 3)

    def test_palace_of_rejects_unknown(self):
        with pytest.raises(InvalidInputError, match="未知六十四卦名"):
            palace_of("乾为天")


# ==========================================================================
# 三、世应
# ==========================================================================


class TestShiYing:
    def test_table_shape(self):
        assert len(SHI_YING_YAO) == 8
        for shi, ying in SHI_YING_YAO:
            assert 1 <= shi <= 6 and 1 <= ying <= 6

    def test_shi_ying_opposite_by_three(self):
        """世应恒相隔三位（世+3=应 或 应+3=世）。"""
        for gua, (_palace, idx) in GUA_PALACE.items():
            shi, ying = shi_ying_of(gua)
            assert abs(shi - ying) == 3, f"{gua}: 世{shi} 应{ying}"

    def test_pure_gua_shi_at_top(self):
        for palace in PALACE_GUA:
            assert shi_ying_of(palace) == (6, 3)

    def test_stage_progression(self):
        """一世到五世，世爻随阶段逐位升高。"""
        palace = PALACE_GUA["乾"]
        shi_positions = [shi_ying_of(g)[0] for g in palace[:6]]
        assert shi_positions == [6, 1, 2, 3, 4, 5]

    def test_youhun_guihun_retreat(self):
        palace = PALACE_GUA["乾"]
        assert shi_ying_of(palace[6]) == (4, 1)   # 游魂
        assert shi_ying_of(palace[7]) == (3, 6)   # 归魂


# ==========================================================================
# 四、六神
# ==========================================================================


class TestLiuShen:
    @pytest.mark.parametrize(
        "gan,first",
        [("甲", "青龙"), ("乙", "青龙"), ("丙", "朱雀"), ("丁", "朱雀"),
         ("戊", "勾陈"), ("己", "螣蛇"), ("庚", "白虎"), ("辛", "白虎"),
         ("壬", "玄武"), ("癸", "玄武")],
    )
    def test_start_by_day_gan(self, gan: str, first: str):
        assert liu_shen_for_day(gan)[0] == first

    def test_six_shen_all_present_and_ordered(self):
        for gan in TIANGAN:
            shen = liu_shen_for_day(gan)
            assert len(shen) == 6
            assert len(set(shen)) == 6
            # 相邻两爻必是固定顺序中的下一位
            order = ("青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武")
            for i in range(5):
                assert order.index(shen[i + 1]) == (order.index(shen[i]) + 1) % 6

    def test_rejects_bad_gan(self):
        with pytest.raises(InvalidInputError, match="非法日干"):
            liu_shen_for_day("子")


# ==========================================================================
# 五、六亲
# ==========================================================================


class TestLiuQin:
    @pytest.mark.parametrize(
        "yao_element,expected",
        [("metal", "兄弟"), ("water", "子孙"), ("earth", "父母"),
         ("wood", "妻财"), ("fire", "官鬼")],
    )
    def test_qian_palace(self, yao_element: str, expected: str):
        """乾宫属金，五类关系各验一例。"""
        assert liu_qin("乾", yao_element) == expected

    def test_all_five_qin_reachable(self):
        """遍历各宫 × 五行，六亲取值应恰好覆盖五类，无遗漏无越界。"""
        seen = set()
        for palace in PALACE_GUA:
            for element in ("wood", "fire", "earth", "metal", "water"):
                seen.add(liu_qin(palace, element))
        assert seen == {"兄弟", "子孙", "父母", "妻财", "官鬼"}


# ==========================================================================
# 六、六冲 / 六合
# ==========================================================================


class TestChongHe:
    def test_chong_is_involutive_and_offset_six(self):
        for zhi in DIZHI:
            other = zhi_chong(zhi)
            assert zhi_chong(other) == zhi
            assert (DIZHI.index(other) - DIZHI.index(zhi)) % 12 == 6

    def test_liuhe_is_involutive_and_distinct(self):
        for zhi in DIZHI:
            other = zhi_liuhe(zhi)
            assert zhi_liuhe(other) == zhi
            assert other != zhi

    def test_liuhe_pairs_are_traditional(self):
        expected = {("子", "丑"), ("寅", "亥"), ("卯", "戌"),
                    ("辰", "酉"), ("巳", "申"), ("午", "未")}
        actual = {frozenset((z, zhi_liuhe(z))) for z in DIZHI}
        assert actual == {frozenset(p) for p in expected}

    def test_liuchong_gua_set(self):
        """六冲卦 = 八纯卦 + 无妄 + 大壮，共 10 卦。"""
        assert LIUCHONG_GUA == frozenset(
            {"乾", "坎", "艮", "震", "巽", "离", "坤", "兑", "无妄", "大壮"}
        )
        assert is_liuchong_gua("乾") and not is_liuchong_gua("泰")

    def test_liuhe_gua_set(self):
        assert LIUHE_GUA == frozenset({"否", "泰", "豫", "复", "旅", "贲", "节", "困"})
        assert is_liuhe_gua("泰") and not is_liuhe_gua("乾")

    def test_rejects_bad_zhi(self):
        with pytest.raises(InvalidInputError, match="非法地支"):
            zhi_chong("甲")
        with pytest.raises(InvalidInputError, match="非法地支"):
            zhi_liuhe("甲")


# ==========================================================================
# 七、旬空
# ==========================================================================


class TestXunKong:
    @pytest.mark.parametrize(
        "xun_head,expected",
        [("甲子", ("戌", "亥")), ("甲戌", ("申", "酉")), ("甲申", ("午", "未")),
         ("甲午", ("辰", "巳")), ("甲辰", ("寅", "卯")), ("甲寅", ("子", "丑"))],
    )
    def test_six_xun(self, xun_head: str, expected: tuple[str, str]):
        assert xun_kong_of(xun_head) == expected
        # 旬首自身的地支不该是空亡
        assert xun_head[1] not in expected

    def test_same_xun_shares_kong(self):
        """同旬十日，空亡相同。"""
        from fortune_core.constants import JIAZI_60

        for start in range(0, 60, 10):
            base = xun_kong_of(JIAZI_60[start])
            for i in range(10):
                assert xun_kong_of(JIAZI_60[start + i]) == base

    def test_kong_fills_the_gap(self):
        """旬空必是该旬十日地支之外的两支。"""
        from fortune_core.constants import JIAZI_60

        for start in range(0, 60, 10):
            used = {JIAZI_60[start + i][1] for i in range(10)}
            kong = set(xun_kong_of(JIAZI_60[start]))
            assert used | kong == set(DIZHI)
            assert not (used & kong)

    def test_rejects_bad_pillar(self):
        with pytest.raises(ValueError):
            xun_kong_of("甲丑")


# ==========================================================================
# 八、月建旺衰 / 日辰关系
# ==========================================================================


class TestMonthState:
    def test_five_states_under_metal_month(self):
        zhi = "酉"  # 金月
        assert month_state_of("metal", zhi) == "旺"
        assert month_state_of("water", zhi) == "相"   # 金生水
        assert month_state_of("earth", zhi) == "休"   # 土生金
        assert month_state_of("wood", zhi) == "死"    # 金克木
        assert month_state_of("fire", zhi) == "囚"    # 火克金

    def test_every_month_yields_one_of_five(self):
        for zhi in DIZHI:
            for el in ("wood", "fire", "earth", "metal", "water"):
                assert month_state_of(el, zhi) in {"旺", "相", "休", "囚", "死"}

    def test_rejects_bad_month(self):
        with pytest.raises(InvalidInputError, match="非法月支"):
            month_state_of("metal", "甲")


class TestDayRelation:
    def test_same_branch(self):
        assert day_relation_of("子", "子")[0] == "临日"

    def test_chong(self):
        assert day_relation_of("子", "午")[0] == "日冲"

    def test_he(self):
        assert day_relation_of("子", "丑")[0] == "日合"

    def test_chong_beats_generation_priority(self):
        """冲合优先于生克判定（子午虽水火相克，仍判日冲）。"""
        assert day_relation_of("午", "子")[0] == "日冲"

    def test_generation_and_control(self):
        assert day_relation_of("寅", "子")[0] == "日生"    # 水生木
        assert day_relation_of("辰", "子")[0] == "爻克日"  # 土克水
        assert day_relation_of("申", "子")[0] == "爻生日"  # 金生水

    def test_every_pair_returns_relation(self):
        valid = {"临日", "日冲", "日合", "日生", "日克", "爻生日", "爻克日", "比和"}
        for yao in DIZHI:
            for day in DIZHI:
                rel, note = day_relation_of(yao, day)
                assert rel in valid and note

    def test_rejects_bad_zhi(self):
        with pytest.raises(InvalidInputError, match="非法地支"):
            day_relation_of("甲", "子")


# ==========================================================================
# 九、装卦聚合 —— 与手排结果逐位对拍
# ==========================================================================


class TestZhuangGua:
    def test_qian_wei_tian_full_layout(self):
        """乾为天 · 甲子日 · 丙寅月 —— 逐位对照手排结果。

        乾为天（乾宫本宫，六冲卦）：
            位1 甲子(水) 子孙 青龙  位2 甲寅(木) 妻财 朱雀
            位3 甲辰(土) 父母 勾陈  位4 壬午(火) 官鬼 螣蛇
            位5 壬申(金) 兄弟 白虎  位6 壬戌(土) 父母 玄武
            世上应三；甲子旬空戌亥。
        """
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子", month_pillar="丙寅", topic="财运")

        assert d.palace == "乾" and d.palace_stage == "本宫"
        assert (d.shi_position, d.ying_position) == (6, 3)
        assert d.xun_kong == ("戌", "亥")
        assert d.gua_features == ("六冲卦",)

        assert [y.ganzhi for y in d.yao_details] == [
            "甲子", "甲寅", "甲辰", "壬午", "壬申", "壬戌",
        ]
        assert [y.liu_qin for y in d.yao_details] == [
            "子孙", "妻财", "父母", "官鬼", "兄弟", "父母",
        ]
        assert [y.liu_shen for y in d.yao_details] == [
            "青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武",
        ]
        assert [y.yin_yang for y in d.yao_details] == [1] * 6

        # 世应标记
        assert d.shi_yao.position == 6 and d.ying_yao.position == 3
        assert sum(y.is_shi for y in d.yao_details) == 1
        assert sum(y.is_ying for y in d.yao_details) == 1

        # 旬空：仅位6（戌）落空
        assert [y.position for y in d.yao_details if y.is_kong] == [6]

        # 月建旺衰：寅月木，寅爻旺、子爻休、辰戌土死、午火相、申金囚
        states = {y.position: y.month_state for y in d.yao_details}
        assert states == {1: "休", 2: "旺", 3: "死", 4: "相", 5: "囚", 6: "死"}

        # 日辰关系：子日
        relations = {y.position: y.day_relation for y in d.yao_details}
        assert relations[1] == "临日" and relations[4] == "日冲"

        # 六亲齐全 → 无伏神
        assert d.missing_qin == ()
        assert all(y.fushen_qin is None for y in d.yao_details)

    def test_fushen_when_qin_missing(self):
        """天风姤（乾宫一世）缺妻财 → 借本宫首卦同位为伏神。

        姤：巽下乾上 → 辛丑/辛亥/辛酉/壬午/壬申/壬戌
        六亲（乾宫金）：父母/子孙/兄弟/官鬼/兄弟/父母 —— 无妻财。
        本宫首卦乾为天位2 为甲寅(木)妻财，故位2 伏神 = 妻财 甲寅。
        """
        result = cast_liuyao(yao_values=[8, 7, 7, 7, 7, 7])
        assert result.original_gua == "姤"

        d = zhuang_gua(result, day_pillar="甲子")
        assert d.palace == "乾" and d.palace_stage == "一世"
        assert (d.shi_position, d.ying_position) == (1, 4)
        assert d.missing_qin == ("妻财",)

        yao2 = d.yao_details[1]
        assert yao2.liu_qin == "子孙"          # 本爻辛亥(水)
        assert yao2.fushen_qin == "妻财"
        assert yao2.fushen_ganzhi == "甲寅"
        assert "伏神" in (yao2.fushen_note or "")

    def test_changed_gua_lays_out_own_najia(self):
        """乾为天初爻动 → 变卦天风姤，变卦按自身上下卦纳甲。"""
        result = cast_liuyao(yao_values=[9, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子")

        assert result.changed_gua == "姤"
        assert d.changed_yao_details is not None
        assert [y.ganzhi for y in d.changed_yao_details] == [
            "辛丑", "辛亥", "辛酉", "壬午", "壬申", "壬戌",
        ]
        # 六亲以本卦宫（乾）为准，不随变卦换宫
        assert [y.liu_qin for y in d.changed_yao_details] == [
            "父母", "子孙", "兄弟", "官鬼", "兄弟", "父母",
        ]

    def test_no_changed_gua_without_moving(self):
        result = cast_liuyao(yao_values=[7, 8, 7, 8, 7, 8])
        d = zhuang_gua(result, day_pillar="甲子")
        assert d.changed_yao_details is None
        assert d.result.moving_positions == ()

    def test_month_pillar_optional(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子")
        assert d.month_zhi is None
        assert all(y.month_state == "—" for y in d.yao_details)

    def test_liuhe_gua_detected(self):
        """地天泰：坤上乾下 → 六合卦。"""
        result = cast_liuyao(yao_values=[7, 7, 7, 8, 8, 8])
        assert result.original_gua == "泰"
        d = zhuang_gua(result, day_pillar="甲子")
        assert "六合卦" in d.gua_features
        assert d.palace == "坤" and d.palace_stage == "三世"
        assert (d.shi_position, d.ying_position) == (3, 6)

    def test_rejects_bad_day_pillar(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        with pytest.raises(InvalidInputError, match="日柱干支非法"):
            zhuang_gua(result, day_pillar="甲丑")
        with pytest.raises(InvalidInputError, match="月柱干支非法"):
            zhuang_gua(result, day_pillar="甲子", month_pillar="乙子")

    def test_facts_tradition_layering(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子", month_pillar="丙寅", topic="财运")
        facts, trad = d.to_facts(), d.to_tradition()

        # FACT 层承载确定性推导
        assert facts["palace"] == "乾"
        assert len(facts["yao_details"]) == 6
        assert facts["yao_details"][0]["ganzhi"] == "甲子"
        assert facts["yao_details"][0]["yin_yang"] == "阳"
        assert facts["yao_details"][0]["gan_element"] == "木"   # 位1 天干「甲」属木
        assert facts["yao_details"][0]["zhi_element"] == "水"   # 位1 地支「子」属水

        # TRADITION 层承载流派取用，且必须自带不确定性标注
        assert trad["yongshen"] == "妻财"
        assert trad["yongshen_positions"] == [2]
        assert trad["yongshen_note"] and trad["month_state_note"]

    def test_to_dict_roundtrip(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子")
        payload = d.to_dict()
        assert set(payload) == {"facts", "tradition"}

    def test_yao_symbol(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子")
        assert d.yao_details[0].yao_symbol == "▅▅▅▅▅"
        result2 = cast_liuyao(yao_values=[8, 8, 8, 8, 8, 8])
        d2 = zhuang_gua(result2, day_pillar="甲子")
        assert d2.yao_details[0].yao_symbol == "▅▅　▅▅"


# ==========================================================================
# 十、用神取用
# ==========================================================================


class TestYongShen:
    @pytest.mark.parametrize(
        "topic,expected",
        [("财运", "妻财"), ("事业", "官鬼"), ("父母", "父母"),
         ("子女", "子孙"), ("兄弟", "兄弟"), ("考试", "父母")],
    )
    def test_topic_mapping(self, topic: str, expected: str):
        assert yongshen_of(topic) == expected

    def test_marriage_depends_on_gender(self):
        assert yongshen_of("婚姻", "male") == "妻财"
        assert yongshen_of("婚姻", "female") == "官鬼"
        assert yongshen_of("婚姻") is None  # 缺性别不猜

    def test_unknown_topic_returns_none(self):
        assert yongshen_of("明天天气") is None

    def test_yongshen_yao_lookup(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子", topic="财运")
        assert [y.ganzhi for y in d.yongshen_yao] == ["甲寅"]

    def test_no_topic_no_yongshen(self):
        result = cast_liuyao(yao_values=[7, 7, 7, 7, 7, 7])
        d = zhuang_gua(result, day_pillar="甲子")
        assert d.yongshen is None and d.yongshen_yao == ()

    def test_all_question_categories_map_to_yongshen(self):
        """App 里用户可选的每个类别都必须能取到用神（「其他」除外）。

        为什么值得单测：`QUESTION_CATEGORIES`（用户在 App 里选的 8 个类别）与
        `YONGSHEN_BY_TOPIC`（取用神用的词表）是**两套词表**，只靠命名来对齐。
        一旦有人往前者加了类别而忘了补后者，用户在 App 里选它 →
        `yongshen_of` 返回 None → 断卦走「用神不上卦」分支给出「中平」。
        那个结果**看起来完全正常**，实际与所问之事毫无关系 ——
        这正是本项目最该防的静默降级。这条断言把它变成红灯。
        """
        from fortune_core.context import QUESTION_CATEGORIES

        unmapped = [
            c for c in QUESTION_CATEGORIES
            if c not in ("其他", "婚姻") and yongshen_of(c) is None
        ]
        assert unmapped == [], f"这些全项目问题类别取不到用神：{unmapped}"

        # 婚姻类按性别取用，两个方向都必须取得（缺性别则返回 None 是**设计**，不在此断言）
        assert yongshen_of("婚姻", "male") is not None
        assert yongshen_of("婚姻", "female") is not None


# ==========================================================================
# 十一、全卦遍历 —— 装卦不得对任何一卦报错
# ==========================================================================


class TestAllGuaLayOut:
    def test_all_sixty_four_gua_lay_out(self):
        """64 卦逐一装卦，必须全部成功且结构完整。"""
        from fortune_core.constants import GUA_YAO

        seen: set[str] = set()
        for lower, l_yao in GUA_YAO.items():
            for upper, u_yao in GUA_YAO.items():
                yao = list(l_yao) + list(u_yao)
                # 组装爻值：阳→7(少阳)、阴→8(少阴)，全静爻
                values = [7 if v else 8 for v in yao]
                result = cast_liuyao(yao_values=values)
                d = zhuang_gua(result, day_pillar="甲子", month_pillar="丙寅")

                seen.add(result.original_gua)
                assert len(d.yao_details) == 6
                assert 1 <= d.shi_position <= 6
                assert 1 <= d.ying_position <= 6
                # 世爻与应爻的六亲必须存在于爻中
                assert d.shi_yao.liu_qin in {"父母", "兄弟", "子孙", "妻财", "官鬼"}
                # 每爻六亲合法
                for y in d.yao_details:
                    assert y.liu_qin in {"父母", "兄弟", "子孙", "妻财", "官鬼"}
                    assert y.liu_shen in {"青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"}
                # 缺六亲必有伏神补齐
                missing = set(d.missing_qin)
                covered = {y.fushen_qin for y in d.yao_details if y.fushen_qin}
                assert missing <= covered, f"{result.original_gua} 伏神未补全"

        assert len(seen) == 64
