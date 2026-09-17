"""太乙神数内核测试 —— 三式之三。

## 测试策略

1. **锚点优先**：1972 年阳遁第一局（古籍给了完整数字）、2004 年太乙艮三宫、
   1984 值事生门、2002 壬子元第 31 局、2044 甲子元第 1 局。
   每个锚点都用**独立推导的期望值**，不复述实现。
2. **交叉核对**：太乙宫号与奇门洛书**逐宫错位**，这正是最危险的静默错误源，
   故用奇门的表反查一遍（同一方位在两套体系里必须是同一个卦）。
3. **结构不变量**：周期、满射、单调、覆盖，用于抓「个别年对、整体错」。
4. **语义守卫**：内核不下吉凶断语（RULE-008）。
"""

from __future__ import annotations

import pytest

from fortune_core.exceptions import InvalidInputError, SchoolNotFoundError
from fortune_core.qimen.constants import GONG_GUA, RING_ORDER
from fortune_core.taiyi import (
    BAMEN_BENWEI,
    BAMEN_JIXIONG,
    BAMEN_ORDER,
    JIYAN_BASE,
    PALACE_CLOCKWISE,
    PALACE_DIRECTION,
    PALACE_FENYE,
    PALACE_GUA,
    PALACE_QI,
    PALACE_YINYANG,
    SCHOOLS,
    SHEN_NAME,
    SHEN_PALACE,
    SHISEN_16,
    SHISEN_RING,
    TAIYI_XUN_GONG,
    UNCERTAINTIES,
    WENCHANG_SEQ_YANG,
    bamen_layout,
    canjiang_palace_of,
    cast_taiyi,
    chang_duan_of,
    dingmu_of,
    epoch_of,
    jiang_palace_of,
    jishen_of,
    jiyan_of,
    palace_of_pos,
    san_cai_of,
    shiji_of,
    suan_of,
    taiyi_palace_of,
    wenchang_of,
    year_ganzhi_of,
    zhishi_men_of,
)

ZHI = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")
SIWEI = ("乾", "坤", "艮", "巽")


# ==========================================================================
# 一、静态表
# ==========================================================================


class TestStaticTables:
    def test_palace_gua_full_and_center_empty(self) -> None:
        assert set(PALACE_GUA) == set(range(1, 10))
        assert PALACE_GUA[5] == "中"
        assert sorted(v for k, v in PALACE_GUA.items() if k != 5) == sorted(
            ["乾", "离", "艮", "震", "兑", "坤", "坎", "巽"]
        )

    def test_palace_gua_differs_from_luoshu_on_every_palace(self) -> None:
        """太乙宫号与洛书**逐宫错位** —— 这是本包不复用奇门表的全部理由。

        若有哪一宫偶然相同，说明有人把两套表合并了；
        而合并后的表现是「太乙落宫、三算、六将宫位整体偏移」且不报错。
        """
        same = [p for p in range(1, 10) if PALACE_GUA[p] == GONG_GUA[p]]
        assert same == [5], f"除中宫外不应有宫位与洛书相同，实际相同于 {same}"

    def test_direction_matches_gua(self) -> None:
        expect = {
            "乾": "西北", "坎": "正北", "艮": "东北", "震": "正东",
            "巽": "东南", "离": "正南", "坤": "西南", "兑": "正西",
        }
        for pal, gua in PALACE_GUA.items():
            if pal == 5:
                continue
            assert PALACE_DIRECTION[pal].endswith(expect[gua]), f"宫{pal} 方位不符"

    def test_shen_palace_agrees_with_direction(self) -> None:
        """正神位 → 宫号，必须与宫号 → 卦 的方位一致。"""
        gua_of_pal = {p: g for p, g in PALACE_GUA.items()}
        for pos, pal in SHEN_PALACE.items():
            if pos in ZHI:
                continue          # 四维以外：地支与卦不同名，另测
            assert gua_of_pal[pal] == pos, f"{pos} 被指到 {pal} 宫（{gua_of_pal[pal]}）"

    def test_sixteen_shen_ring(self) -> None:
        assert len(SHISEN_16) == 16
        assert len(set(SHISEN_RING)) == 16, "十六神位不可重复"
        assert tuple(p for p, _ in SHISEN_16) == SHISEN_RING

    def test_sixteen_shen_ring_reduces_to_dizhi(self) -> None:
        """去掉四维后，环序必须正好是十二地支序 —— 否则「顺行十六神」会错位。"""
        assert tuple(p for p in SHISEN_RING if p not in SIWEI) == ZHI

    def test_eight_zheng_and_eight_jian(self) -> None:
        zheng = ("子", "午", "卯", "酉", "乾", "坤", "艮", "巽")
        assert set(zheng) == set(SHEN_PALACE), "正神集合与宫号表必须同源"
        jian = tuple(p for p in SHISEN_RING if p not in zheng)
        assert len(jian) == 8
        assert set(jian) | set(zheng) == set(SHISEN_RING)

    def test_wenchang_sequence_shape(self) -> None:
        assert len(WENCHANG_SEQ_YANG) == 18
        assert WENCHANG_SEQ_YANG[0] == "申", "「天目上元起于申」"
        assert set(WENCHANG_SEQ_YANG) == set(SHISEN_RING), "十八步必须覆盖全部十六位"

    def test_wenchang_extra_steps_are_qian_and_kun(self) -> None:
        """重留的只能是阴德(乾)与大武(坤)，且各恰好多一次。"""
        from collections import Counter

        cnt = Counter(WENCHANG_SEQ_YANG)
        assert {p for p, c in cnt.items() if c == 2} == {"乾", "坤"}
        assert all(c == 1 for p, c in cnt.items() if p not in {"乾", "坤"})

    def test_wenchang_extra_steps_are_adjacent(self) -> None:
        """重留必须是**连着两步**，中间不能夹别的位 —— 「重留一算」。"""
        for i in range(1, len(WENCHANG_SEQ_YANG)):
            if WENCHANG_SEQ_YANG[i] == WENCHANG_SEQ_YANG[i - 1]:
                assert WENCHANG_SEQ_YANG[i] in {"乾", "坤"}

    def test_bamen_order_matches_benwei_clockwise(self) -> None:
        """八门轮转序必须与八门本位的方位环同步。

        两者一旦不同步，「布八门」就会把门放到错误宫位 ——
        而门的名与凶吉都对，只有位置错。所以这条是跨表一致性守卫。
        """
        gua_to_pal = {g: p for p, g in PALACE_GUA.items()}
        by_benwei = tuple(gua_to_pal[BAMEN_BENWEI[d]] for d in BAMEN_ORDER)
        pivot = PALACE_CLOCKWISE.index(by_benwei[0])
        rotated = PALACE_CLOCKWISE[pivot:] + PALACE_CLOCKWISE[:pivot]
        assert by_benwei == rotated

    def test_bamen_jixiong_clean_two_valued(self) -> None:
        assert set(BAMEN_JIXIONG) == set(BAMEN_ORDER)
        assert all(v in {"大吉", "吉", "小吉", "小凶", "大凶"} for v in BAMEN_JIXIONG.values())

    def test_wuyuan_liuji_arithmetic(self) -> None:
        from fortune_core.taiyi import CYCLE_JI, CYCLE_WUYUAN_LIUJI, CYCLE_YUAN

        assert CYCLE_YUAN * 5 == CYCLE_WUYUAN_LIUJI
        assert CYCLE_JI * 6 == CYCLE_WUYUAN_LIUJI

    def test_schools_differ_by_one_jiazi(self) -> None:
        """两派积年基数差 60（一甲子）—— 这是太乙唯一的流派分歧点。"""
        assert set(SCHOOLS) == {"default", "taojin"}
        diff = SCHOOLS["taojin"]["jiyan_base"] - SCHOOLS["default"]["jiyan_base"]
        assert diff == 60

    def test_uncertainties_non_empty(self) -> None:
        assert UNCERTAINTIES, "未覆盖项必须随结果返回（RULE-006）"


# ==========================================================================
# 二、积年与年干支
# ==========================================================================


class TestJiyan:
    def test_known_value(self) -> None:
        assert jiyan_of(2004) == 10155921

    def test_tang_dynasty_cross_check(self) -> None:
        """《太乙金镜式经》载开元十二年（724）积 1937281。

        与本基数算出的值相差 8217360 = 360 × 22826（整数个五元六纪），
        故对太乙全部取模运算等价 —— 这正是本基数可用的理由，不是「差不多」。
        """
        ours = jiyan_of(724)
        tang = 1937281
        delta = ours - tang
        assert delta % 360 == 0
        assert delta // 360 == 22826
        for mod in (18, 24, 30, 72, 240, 360):
            assert ours % mod == tang % mod, f"mod {mod} 不等价"

    def test_rejects_non_int(self) -> None:
        for bad in (2004.5, "2004", None, True):
            with pytest.raises(InvalidInputError):
                jiyan_of(bad)  # type: ignore[arg-type]


class TestYearGanzhi:
    @pytest.mark.parametrize(
        "year,expect",
        [(1984, "甲子"), (1972, "壬子"), (2004, "甲申"), (2044, "甲子"), (2026, "丙午")],
    )
    def test_known_years(self, year: int, expect: str) -> None:
        assert year_ganzhi_of(year) == expect

    def test_sixty_year_cycle(self) -> None:
        for y in (1, 1972, 2026):
            assert year_ganzhi_of(y) == year_ganzhi_of(y + 60)


# ==========================================================================
# 三、五元六纪
# ==========================================================================


class TestEpoch:
    def test_2002_is_renzi_yuan_31st_ju(self) -> None:
        e = epoch_of(jiyan_of(2002))
        assert e.wuyuan_name == "壬子元"
        assert e.ju == 31

    def test_2044_is_jiazi_yuan_1st_ju(self) -> None:
        """甲子元第 1 局必须是甲子年 —— 元名与元首之年的干支必须对得上。"""
        e = epoch_of(jiyan_of(2044))
        assert e.wuyuan_name == "甲子元"
        assert e.ju == 1
        assert year_ganzhi_of(2044) == "甲子"

    def test_wuyuan_names_align_with_their_first_year(self) -> None:
        """元名是元首之年的干支：每前进一元（72 年），干支前进 12（丙子…）。"""
        base = 2044                       # 甲子元第 1 局
        for i in range(5):
            y = base + 72 * i
            assert epoch_of(jiyan_of(y)).wuyuan_name == ("甲子元", "丙子元", "戊子元",
                                                         "庚子元", "壬子元")[i]
            assert epoch_of(jiyan_of(y)).ju == 1

    def test_ji_and_yuan_share_one_origin(self) -> None:
        """纪与元是同一条 360 年周期的两种切法，必须同源自洽。

        若分别对 60 与 72 取模，二者会来自不同原点 ——
        表现是「入纪年数」与「入元局数」拼不回去，而各自看起来都合理。
        """
        j = jiyan_of(2026)
        e = epoch_of(j)
        r360 = (j - 1) % 360
        assert e.ji_index == r360 // 60
        assert e.ji_year == r360 % 60 + 1
        assert e.ju == r360 % 72 + 1

    def test_covers_all_yuan_and_ju(self) -> None:
        seen = set()
        for j in range(1, 361):
            e = epoch_of(j)
            seen.add((e.wuyuan_index, e.ju))
        assert len(seen) == 360, "360 年内元与局应两两不同"

    def test_rejects_non_positive(self) -> None:
        with pytest.raises(InvalidInputError):
            epoch_of(0)


# ==========================================================================
# 四、太乙行宫
# ==========================================================================


class TestTaiyiPalace:
    def test_2004_anchor(self) -> None:
        """古籍算例：西元 2004 年，積數 % 24 ÷ 3 = 3 … 0（0 當 3）→ 三宮入宮第 3 年。"""
        pal, ru = taiyi_palace_of(jiyan_of(2004))
        assert pal == 3, "三宫 = 艮"
        assert ru == 3

    def test_1972_first_ju_lands_on_qian(self) -> None:
        assert taiyi_palace_of(jiyan_of(1972)) == (1, 1)

    def test_never_enters_center(self) -> None:
        for j in range(1, 241):
            assert taiyi_palace_of(j)[0] != 5, "太乙不入中五宫"

    def test_ru_gong_year_always_1_to_3(self) -> None:
        assert {taiyi_palace_of(j)[1] for j in range(1, 241)} == {1, 2, 3}

    def test_period_is_24_years(self) -> None:
        for j in range(1, 60):
            assert taiyi_palace_of(j) == taiyi_palace_of(j + 24)

    def test_visits_eight_palaces_each_three_times(self) -> None:
        got = [taiyi_palace_of(j)[0] for j in range(1, 25)]
        assert sorted(got) == sorted([p for p in TAIYI_XUN_GONG for _ in range(3)])

    def test_first_palace_of_each_trip_is_li_tian(self) -> None:
        for j in range(1, 240, 3):
            assert taiyi_palace_of(j)[1] == 1


# ==========================================================================
# 五、文昌
# ==========================================================================


class TestWenchang:
    def test_1972_starts_at_wude(self) -> None:
        assert wenchang_of(jiyan_of(1972)) == "申"

    def test_period_is_18(self) -> None:
        for j in range(1, 40):
            assert wenchang_of(j) == wenchang_of(j + 18)

    def test_walks_the_sequence(self) -> None:
        got = tuple(wenchang_of(jiyan_of(1972) + i) for i in range(18))
        assert got == WENCHANG_SEQ_YANG

    def test_holds_two_years_at_qian_and_kun(self) -> None:
        """重留的实际效果：同一个位连续两年是文昌。"""
        seq = [wenchang_of(jiyan_of(1972) + i) for i in range(18)]
        repeats = [seq[i] for i in range(1, 18) if seq[i] == seq[i - 1]]
        assert repeats == ["乾", "坤"]

    def test_rejects_non_positive(self) -> None:
        with pytest.raises(InvalidInputError):
            wenchang_of(0)


# ==========================================================================
# 六、计神
# ==========================================================================


class TestJishen:
    @pytest.mark.parametrize(
        "year_zhi,expect",
        list(zip(ZHI, ("寅", "丑", "子", "亥", "戌", "酉", "申", "未", "午", "巳", "辰", "卯"))),
    )
    def test_koujue_all_twelve(self, year_zhi: str, expect: str) -> None:
        """口诀逐条锚定：「子岁计神寅上起，丑牛寅鼠逆周流」。"""
        assert jishen_of(year_zhi) == expect

    def test_never_uses_siwei(self) -> None:
        assert set(jishen_of(z) for z in ZHI).isdisjoint(SIWEI)

    def test_is_a_bijection(self) -> None:
        assert len(set(jishen_of(z) for z in ZHI)) == 12

    def test_rejects_bad_zhi(self) -> None:
        for bad in ("乾", "甲", ""):
            with pytest.raises(InvalidInputError):
                jishen_of(bad)


# ==========================================================================
# 七、始击与定目
# ==========================================================================


class TestShiji:
    def test_1972_anchor(self) -> None:
        """古籍：甲子年计神在寅、文昌在申 → 计神移至艮 → 文昌转至坤，故始击在坤。"""
        assert shiji_of("申", "寅") == "坤"

    def test_rotation_amount_matches_hand_calc(self) -> None:
        """计神寅(环序3) → 艮(环序2)，顺行需 15 步。"""
        from fortune_core.taiyi import RING_INDEX

        steps = (RING_INDEX["艮"] - RING_INDEX["寅"]) % 16
        assert steps == 15
        assert RING_INDEX["坤"] == (RING_INDEX["申"] + steps) % 16

    def test_identity_when_jishen_already_at_gen(self) -> None:
        assert shiji_of("午", "艮") == "午"

    def test_result_is_always_a_valid_pos(self) -> None:
        for pos in SHISEN_RING:
            for z in ZHI:
                assert shiji_of(pos, jishen_of(z)) in SHISEN_RING


class TestDingmu:
    def test_1972_anchor(self) -> None:
        """古籍：甲子年太岁在子、合神为丑、文昌在申 → 合神加太岁 → 文昌临坤。"""
        assert dingmu_of("申", "子") == "坤"

    def test_uses_liuhe_as_anchor(self) -> None:
        from fortune_core.taiyi import LIUHE, RING_INDEX

        steps = (RING_INDEX["子"] - RING_INDEX[LIUHE["子"]]) % 16
        assert steps == 15
        assert RING_INDEX["坤"] == (RING_INDEX["申"] + steps) % 16

    def test_rejects_bad_tai_sui(self) -> None:
        with pytest.raises(InvalidInputError):
            dingmu_of("申", "乾")


# ==========================================================================
# 八、三算
# ==========================================================================


class TestSuan:
    def test_1972_main_count(self) -> None:
        """文昌在申（间辰，起一）→ 兑六 → 乾即太乙而止 ⇒ 1 + 6 = 7。"""
        value, warn = suan_of("申", 1)
        assert value == 7
        assert warn == ()

    def test_1972_guest_count(self) -> None:
        """始击在坤（正神，以本宫七起）→ 兑六 → 乾止 ⇒ 7 + 6 = 13。"""
        assert suan_of("坤", 1)[0] == 13

    def test_zheng_shen_starts_with_its_own_palace_number(self) -> None:
        """正神起本宫数：坎(8) 起 8，下一个顺行正宫是艮(3) → 8 + 3 = 11。"""
        assert suan_of("子", 1)[0] == 8 + 3 + 4 + 9 + 2 + 7 + 6

    def test_jian_shen_starts_with_one(self) -> None:
        """间辰起一：丑(间) 与子(正,8) 的差别只有起算值，其余路径相同。"""
        assert suan_of("丑", 1)[0] == 1 + 3 + 4 + 9 + 2 + 7 + 6

    def test_difference_between_zheng_and_jian_on_same_edge(self) -> None:
        """子与丑走同一段路，差恰为 8 − 1 = 7 —— 起算口径一旦写反会立刻暴露。"""
        assert suan_of("子", 1)[0] - suan_of("丑", 1)[0] == 7

    def test_interval_shen_is_not_accumulated(self) -> None:
        """间神不参与累加：从申走与从酉(兑)走，累加段完全相同。"""
        assert suan_of("申", 1)[0] == 1 + 6
        assert suan_of("酉", 1)[0] == 6

    def test_same_palace_same_shen_takes_palace_number(self) -> None:
        value, warn = suan_of("乾", 1)
        assert value == 1
        assert warn and "同宫同神" in warn[0]

    def test_same_palace_different_shen_takes_one_and_warns(self) -> None:
        """间神与太乙同宫 → 算数取 1，且必须给提示（各家表述不一）。"""
        value, warn = suan_of("亥", 8)      # 亥的顺行下一正宫是子(坎 8)
        assert value == 1
        assert warn and "不同神" in warn[0]

    def test_always_positive(self) -> None:
        for pos in SHISEN_RING:
            for pal in TAIYI_XUN_GONG:
                value, _ = suan_of(pos, pal)
                assert value >= 1, f"{pos} 在太乙{pal}宫算出 {value}"

    def test_rejects_bad_input(self) -> None:
        with pytest.raises(InvalidInputError):
            suan_of("甲", 1)

    def test_center_palace_rejected(self) -> None:
        with pytest.raises(InvalidInputError):
            suan_of("申", 5), "太乙不居五宫"


class TestPalaceOfPos:
    def test_zheng_shen_has_own_palace(self) -> None:
        for pos, pal in SHEN_PALACE.items():
            assert palace_of_pos(pos) == pal

    def test_shen_belongs_to_next_zheng_palace(self) -> None:
        """古籍算例说「申在 6 宫位」，而申顺行下一正宫是酉（兑 6）。"""
        assert palace_of_pos("申") == 6

    def test_every_jian_shen_maps_to_some_palace(self) -> None:
        from fortune_core.taiyi import JIAN_SHEN

        assert {palace_of_pos(p) for p in JIAN_SHEN} <= set(TAIYI_XUN_GONG)

    def test_rejects_bad_pos(self) -> None:
        with pytest.raises(InvalidInputError):
            palace_of_pos("甲")


# ==========================================================================
# 九、大将与参将
# ==========================================================================


class TestJiang:
    @pytest.mark.parametrize("suan,expect", [(7, 7), (13, 3), (21, 1), (9, 9), (34, 4)])
    def test_last_digit(self, suan: int, expect: int) -> None:
        assert jiang_palace_of(suan) == expect

    @pytest.mark.parametrize("suan,expect", [(10, 1), (20, 2), (30, 3), (40, 4), (90, 9)])
    def test_multiples_of_ten_divide_by_nine(self, suan: int, expect: int) -> None:
        """「十算仍将九去之」—— 个位为 0 时不能取 0，必须除九取余。"""
        assert jiang_palace_of(suan) == expect

    def test_never_zero_or_center_out_of_range(self) -> None:
        for suan in range(1, 200):
            assert 1 <= jiang_palace_of(suan) <= 9, f"算数 {suan} 得到非法宫号"

    def test_canjiang_is_triple_last_digit(self) -> None:
        assert canjiang_palace_of(7) == 1     # 7×3 = 21
        assert canjiang_palace_of(3) == 9     # 3×3 = 9
        assert canjiang_palace_of(4) == 2     # 12
        assert canjiang_palace_of(9) == 7     # 27

    def test_rejects_bad_input(self) -> None:
        with pytest.raises(InvalidInputError):
            jiang_palace_of(0)
        with pytest.raises(InvalidInputError):
            canjiang_palace_of(0)


# ==========================================================================
# 十、长短、三才、和孤
# ==========================================================================


class TestChangDuanSanCai:
    @pytest.mark.parametrize("suan,expect", [(1, "短"), (9, "短"), (10, "中"), (11, "长"), (40, "长")])
    def test_length_boundaries(self, suan: int, expect: str) -> None:
        assert chang_duan_of(suan) == expect

    def test_san_cai_missing_tian_below_ten(self) -> None:
        assert "无天" in san_cai_of(9)
        assert "无天" not in san_cai_of(10)

    def test_san_cai_digit_rule(self) -> None:
        assert "无地" not in san_cai_of(15), "15 里有 5，不该判无地"
        assert "无地" in san_cai_of(13)
        assert "无人" not in san_cai_of(51), "51 里有 1，不该判无人"
        assert "无人" in san_cai_of(23)

    def test_san_cai_all_present_is_empty(self) -> None:
        """15 有天(有十位)、有地(含5)、有人(含1) —— 三者皆备。"""
        assert san_cai_of(15) == ()

    def test_san_cai_at_most_three(self) -> None:
        for suan in range(1, 100):
            assert len(san_cai_of(suan)) <= 3


# ==========================================================================
# 十一、值事八门
# ==========================================================================


class TestBamen:
    def test_1984_is_shengmen(self) -> None:
        """锚点：1984 年积年 % 240 = 60，60 ÷ 30 = 2 → 第三门 = 生门。"""
        assert zhishi_men_of(jiyan_of(1984)) == "生门"

    def test_period_is_240(self) -> None:
        for j in range(1, 300):
            assert zhishi_men_of(j) == zhishi_men_of(j + 240)

    def test_switches_every_30_years(self) -> None:
        seq = [zhishi_men_of(j) for j in range(1, 241)]
        for i in range(0, 240, 30):
            assert len(set(seq[i:i + 30])) == 1, f"第 {i} 段内值事门应恒定"
        assert seq[0] == "开门", "开门为始"

    def test_layout_places_zhishi_on_taiyi_palace(self) -> None:
        for pal in TAIYI_XUN_GONG:
            for door in BAMEN_ORDER:
                layout = dict((p, d) for p, d in bamen_layout(pal, door))
                assert layout[pal] == door, "值事门必须落太乙宫"

    def test_layout_is_a_bijection_over_eight_palaces(self) -> None:
        layout = bamen_layout(6, "生门")
        assert len(layout) == 8
        assert {p for p, _ in layout} == set(TAIYI_XUN_GONG)
        assert {d for _, d in layout} == set(BAMEN_ORDER)

    def test_layout_follows_clockwise_ring(self) -> None:
        """落宫必须沿九宫顺时针环依次推进，不能按宫号递增。"""
        layout = bamen_layout(1, "开门")
        order = [p for p, _ in layout]
        pivot = PALACE_CLOCKWISE.index(1)
        assert order == list(PALACE_CLOCKWISE[pivot:] + PALACE_CLOCKWISE[:pivot])

    def test_rejects_center_and_bad_door(self) -> None:
        with pytest.raises(InvalidInputError):
            bamen_layout(5, "开门")
        with pytest.raises(InvalidInputError):
            bamen_layout(1, "中门")


# ==========================================================================
# 十二、主入口
# ==========================================================================


class TestCastTaiyi:
    def test_first_ju_all_anchors_at_once(self) -> None:
        """阳遁第一局 = 1972 年，古籍给的七项数字必须同时成立。"""
        c = cast_taiyi(1972)
        assert c.year_ganzhi == "壬子"
        assert c.taiyi_palace == 1
        assert c.wenchang_pos == "申"
        assert c.jishen_zhi == "寅"
        assert c.shiji_pos == "坤"
        assert c.dingmu_pos == "坤"
        assert c.suan("主算").value == 7
        assert c.suan("客算").value == 13
        assert c.suan("定算").value == 13

    def test_2044_reproduces_1972(self) -> None:
        """七十二年为元周期：太乙(24)、文昌(18)、局(72) 的最小公倍数是 72，
        故 2044 与 1972 除值事门外应完全同盘。"""
        a, b = cast_taiyi(1972), cast_taiyi(2044)
        assert a.taiyi_palace == b.taiyi_palace
        assert a.wenchang_pos == b.wenchang_pos
        assert a.shiji_pos == b.shiji_pos
        assert a.suan("主算").value == b.suan("主算").value

    def test_three_counts_always_present(self) -> None:
        c = cast_taiyi(2026)
        assert [s.name for s in c.sansuan] == ["主算", "客算", "定算"]

    def test_da_can_jiang_present_and_legal(self) -> None:
        for year in (1972, 1984, 2002, 2004, 2026, 2044):
            for s in cast_taiyi(year).sansuan:
                assert 1 <= s.da_jiang <= 9
                assert 1 <= s.can_jiang <= 9

    def test_li_sancai_matches_ru_gong_year(self) -> None:
        c = cast_taiyi(2004)
        assert (c.ru_gong_year, c.taiyi_li) == (3, "理人")

    def test_he_shen_is_liuhe_of_tai_sui(self) -> None:
        from fortune_core.taiyi import LIUHE

        for year in (1972, 1984, 2002, 2026):
            c = cast_taiyi(year)
            assert c.he_shen == LIUHE[c.tai_sui]

    def test_deterministic(self) -> None:
        assert cast_taiyi(2026).to_dict() == cast_taiyi(2026).to_dict()

    def test_no_fortune_verdict(self) -> None:
        """内核只给 FACT，不合成吉凶结论（RULE-008）。"""
        d = cast_taiyi(2026).to_dict()
        banned = {"verdict", "conclusion", "is_auspicious", "lucky", "fortune", "advice"}
        assert banned.isdisjoint(d)
        for s in d["sansuan"]:
            assert banned.isdisjoint(s)
        assert banned.isdisjoint(d["taiyi"])
        assert banned.isdisjoint(d["bamen"])

    def test_uncertainties_same_source_as_constants(self) -> None:
        d = cast_taiyi(2026).to_dict()
        assert tuple(d["uncertainties"]) == UNCERTAINTIES

    def test_all_years_in_a_cycle_are_renderable(self) -> None:
        for year in range(1976, 2100):
            d = cast_taiyi(year).to_dict()
            assert d["sansuan"] and d["bamen"]["layout"]

    def test_unknown_school_raises(self) -> None:
        with pytest.raises(SchoolNotFoundError):
            cast_taiyi(2026, school="nope")

    def test_takes_no_month_or_day(self) -> None:
        """年局只按年定位 —— 与六壬「必须给到时辰」相反，是本模块的有意设计。"""
        import inspect

        sig = inspect.signature(cast_taiyi)
        assert list(sig.parameters)[:2] == ["year", "school"]


class TestSchool:
    def test_taojin_differs_from_default(self) -> None:
        a, b = cast_taiyi(2002), cast_taiyi(2002, school="taojin")
        assert a.jiyan != b.jiyan
        assert (a.epoch.ju, a.taiyi_palace) != (b.epoch.ju, b.taiyi_palace)

    def test_school_reported_in_output(self) -> None:
        d = cast_taiyi(2002, school="taojin").to_dict()
        assert d["school"] == "taojin"
        assert d["school_name"] == SCHOOLS["taojin"]["name"]
        assert d["jiyan_base"] == SCHOOLS["taojin"]["jiyan_base"]

    def test_default_base_is_the_jingjing_one(self) -> None:
        d = cast_taiyi(2002).to_dict()
        assert d["jiyan_base"] == JIYAN_BASE
