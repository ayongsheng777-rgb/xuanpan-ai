"""奇门遁甲内核测试。

**防假绿设计**（本项目的既有纪律）：

1. **独立真值**：局数表在测试里**硬编码古籍完整表**（24 节气 × 3 元 = 72 个数），
   而实现是「上元表 + 固定偏移」派生 —— 两者的结构不同，
   故对照有效。若两边都用同一条公式生成，就是自己给自己判卷。
2. **不变式优先于固定值**：「天盘是地盘的旋转」「值符随时干」这类性质断言，
   比单点固定值更难被"改坏后仍然通过"。
3. **手工核验过的锚点**：地盘两局、2026-09-17 的完整盘面，均已逐宫手工复核。

锚点来源：古籍通行局数表 + 多个独立开源实现的排盘结果（逐宫对拍）。
"""

from __future__ import annotations

from datetime import datetime

import pytest

from fortune_core.exceptions import InvalidInputError, SchoolNotFoundError
from fortune_core.qimen import (
    BAMEN_BY_GONG,
    BASHEN_ORDER,
    JIUXING_BY_GONG,
    RING_ORDER,
    build_dipan,
    cast_qimen,
    is_yang_dun,
    jushu_of,
    jushu_table,
    xun_kong_of,
    xunshou_of,
    yima_of,
)
from fortune_core.qimen.constants import Qiyi_ORDER

# --------------------------------------------------------------------------
# 独立真值：古籍完整局数表（不引用实现里的任何派生逻辑）
# --------------------------------------------------------------------------

CANONICAL_JUSHU: dict[str, tuple[int, int, int]] = {
    # 阳遁（冬至 → 芒种）
    "冬至": (1, 7, 4), "小寒": (2, 8, 5), "大寒": (3, 9, 6),
    "立春": (8, 5, 2), "雨水": (9, 6, 3), "惊蛰": (1, 7, 4),
    "春分": (3, 9, 6), "清明": (4, 1, 7), "谷雨": (5, 2, 8),
    "立夏": (4, 1, 7), "小满": (5, 2, 8), "芒种": (6, 3, 9),
    # 阴遁（夏至 → 大雪）
    "夏至": (9, 3, 6), "小暑": (8, 2, 5), "大暑": (7, 1, 4),
    "立秋": (2, 5, 8), "处暑": (1, 4, 7), "白露": (9, 3, 6),
    "秋分": (7, 1, 4), "寒露": (6, 9, 3), "霜降": (5, 8, 2),
    "立冬": (6, 9, 3), "小雪": (5, 8, 2), "大雪": (4, 7, 1),
}


class TestJushuTable:
    """局数表 —— 逐节气对拍古籍完整表。"""

    def test_all_24_jieqi_match_canonical(self) -> None:
        """24 节气 × 3 元，共 72 个数逐一对照。"""
        table = jushu_table()
        assert set(table) == set(CANONICAL_JUSHU), "节气集合不一致"
        mismatched = {
            jq: (table[jq], CANONICAL_JUSHU[jq])
            for jq in CANONICAL_JUSHU
            if table[jq] != CANONICAL_JUSHU[jq]
        }
        assert not mismatched, f"局数表与古籍不符：{mismatched}"

    def test_yang_dun_boundary(self) -> None:
        """冬至起阳遁，夏至起阴遁 —— 这是阴阳遁的硬分界。"""
        assert is_yang_dun("冬至") is True
        assert is_yang_dun("芒种") is True
        assert is_yang_dun("夏至") is False
        assert is_yang_dun("大雪") is False

    def test_jushu_all_in_range(self) -> None:
        """局数必须恒在 1~9（洛书九宫）。"""
        for jq, tri in CANONICAL_JUSHU.items():
            assert all(1 <= n <= 9 for n in tri), f"{jq} 局数越界：{tri}"

    def test_unknown_jieqi_raises(self) -> None:
        with pytest.raises(ValueError, match="未知节气"):
            jushu_of("立夏后", 1)
        with pytest.raises(ValueError, match="未知节气"):
            is_yang_dun("不存在的节气")

    def test_bad_yuan_raises(self) -> None:
        with pytest.raises(ValueError, match="元必须是"):
            jushu_of("冬至", 4)
        with pytest.raises(ValueError, match="元必须是"):
            jushu_of("冬至", 0)


class TestDipan:
    """地盘三奇六仪 —— 对拍两个局的完整宫位（手工核验过的锚点）。"""

    def test_yang_dun_1_ju(self) -> None:
        """阳遁 1 局：戊从坎 1 起顺行。"""
        assert build_dipan(1, True) == {
            1: "戊", 2: "己", 3: "庚", 4: "辛", 5: "壬",
            6: "癸", 7: "丁", 8: "丙", 9: "乙",
        }

    def test_yin_dun_9_ju(self) -> None:
        """阴遁 9 局：戊从离 9 起逆行。"""
        assert build_dipan(9, False) == {
            9: "戊", 8: "己", 7: "庚", 6: "辛", 5: "壬",
            4: "癸", 3: "丁", 2: "丙", 1: "乙",
        }

    def test_all_18_ju_are_permutations(self) -> None:
        """18 种局（阳 9 + 阴 9）都必须恰好铺满九个干，无重复无遗漏。"""
        for jushu in range(1, 10):
            for yang in (True, False):
                pan = build_dipan(jushu, yang)
                assert len(pan) == 9, f"{yang=} {jushu=} 宫数不为 9"
                assert set(pan.values()) == set(Qiyi_ORDER), (
                    f"{yang=} {jushu=} 干集合不符：{sorted(pan.values())}"
                )

    def test_start_palace_is_jushu(self) -> None:
        """戊必起于局数宫 —— 这是定局的直接体现。"""
        for jushu in range(1, 10):
            assert build_dipan(jushu, True)[jushu] == "戊"
            assert build_dipan(jushu, False)[jushu] == "戊"

    def test_no_jia_on_dipan(self) -> None:
        """甲隐于六仪之下，地盘上永远看不到「甲」（RULE-001 的领域常识）。"""
        for jushu in range(1, 10):
            for yang in (True, False):
                assert "甲" not in build_dipan(jushu, yang).values()

    def test_invalid_jushu_raises(self) -> None:
        with pytest.raises(InvalidInputError, match="局数必须在"):
            build_dipan(0, True)
        with pytest.raises(InvalidInputError, match="局数必须在"):
            build_dipan(10, True)


class TestXunshouAndKong:
    """旬首与旬空。"""

    def test_six_xunshou(self) -> None:
        """六个旬首必须逐一正确（曾因用 `旬序*2` 而把甲戌算成甲寅）。"""
        cases = {
            "甲子": "甲子", "乙丑": "甲子", "癸酉": "甲子",
            "甲戌": "甲戌", "丁丑": "甲戌",
            "甲申": "甲申", "己丑": "甲申",
            "甲午": "甲午",
            "甲辰": "甲辰",
            "甲寅": "甲寅", "癸亥": "甲寅",
        }
        for ganzhi, expect in cases.items():
            assert xunshou_of(ganzhi) == expect, f"{ganzhi} 旬首错"

    def test_all_60_ganzhi_xunshou_is_jia(self) -> None:
        """全体六十甲子的旬首必为「甲X」。"""
        from fortune_core.constants import JIAZI_60

        for gz in JIAZI_60:
            xs = xunshou_of(gz)
            assert xs.startswith("甲"), f"{gz} -> {xs} 不是甲日"
            assert len(xs) == 2

    def test_xun_kong(self) -> None:
        assert xun_kong_of("甲子") == ("戌", "亥")
        assert xun_kong_of("庚午") == ("戌", "亥")
        assert xun_kong_of("甲戌") == ("申", "酉")
        assert xun_kong_of("甲申") == ("午", "未")
        assert xun_kong_of("甲午") == ("辰", "巳")
        assert xun_kong_of("甲辰") == ("寅", "卯")
        assert xun_kong_of("甲寅") == ("子", "丑")

    def test_xun_kong_is_two_branches(self) -> None:
        from fortune_core.constants import JIAZI_60

        for gz in JIAZI_60:
            assert len(xun_kong_of(gz)) == 2


class TestYima:
    """驿马 —— 三合局取冲。"""

    def test_four_groups(self) -> None:
        assert yima_of("申") == yima_of("子") == yima_of("辰") == "寅"
        assert yima_of("寅") == yima_of("午") == yima_of("戌") == "申"
        assert yima_of("巳") == yima_of("酉") == yima_of("丑") == "亥"
        assert yima_of("亥") == yima_of("卯") == yima_of("未") == "巳"

    def test_all_branches_covered(self) -> None:
        from fortune_core.constants import DIZHI

        for zhi in DIZHI:
            assert yima_of(zhi) in DIZHI


class TestDingju:
    """定局 —— 节气 / 三元 / 局数。"""

    def test_known_case_2026_09_17(self) -> None:
        """2026-09-17 12:00：白露后第 11 天 → 下元 → 阴遁 6 局。"""
        chart = cast_qimen(datetime(2026, 9, 17, 12, 0))
        d = chart.dingju
        assert d.jieqi == "白露"
        assert d.days_after_jieqi == 11
        assert d.yuan == 3 and d.yuan_label == "下元"
        assert d.yang_dun is False
        assert d.jushu == 6
        assert d.jushu_label == "阴遁六局"

    def test_yuan_boundaries_are_1_5_6_10_11(self) -> None:
        """三元分界：1-5 上元、6-10 中元、11-15 下元。

        白露交节于 2026-09-07 **22:41**，故 09-07 当天 12:00 尚属处暑；
        真正属于白露的第 1 天是 09-07 22:41 之后。这里从 09-08 起测，
        把 5/6、10/11 两处边界都撞一遍。
        """
        days = {
            "2026-09-08": (2, 1),    # 上元
            "2026-09-11": (5, 1),    # 上元末
            "2026-09-12": (6, 2),    # 中元首 ← 边界
            "2026-09-16": (10, 2),   # 中元末
            "2026-09-17": (11, 3),   # 下元首 ← 边界
        }
        for day, (expect_days, expect_yuan) in days.items():
            y, m, dd = (int(x) for x in day.split("-"))
            d = cast_qimen(datetime(y, m, dd, 12, 0)).dingju
            assert d.jieqi == "白露", f"{day} 节气应为白露"
            assert d.days_after_jieqi == expect_days, f"{day} 节后天数错"
            assert d.yuan == expect_yuan, f"{day} 三元错"

    def test_before_jieqi_moment_still_previous_jieqi(self) -> None:
        """交节时刻之前仍属上一节气 —— 防「按日期粗暴切节气」的典型错误。

        白露交节 2026-09-07 22:41：同一天的 12:00 与 23:00 分属两个节气，
        若只比日期就会把 12:00 也算成白露。
        """
        before = cast_qimen(datetime(2026, 9, 7, 12, 0)).dingju
        after = cast_qimen(datetime(2026, 9, 7, 23, 0)).dingju
        assert before.jieqi == "处暑", "交节前应仍属处暑"
        assert after.jieqi == "白露", "交节后应属白露"
        assert after.days_after_jieqi == 1, "交节当日算第 1 天"
        # 两天同属阴遁（夏至后皆为阴遁），但局数不同：
        # 处暑已是第 16 天（下元）→ 7 局；白露刚交节为第 1 天（上元）→ 9 局
        assert before.yang_dun is False, "处暑属阴遁"
        assert after.yang_dun is False, "白露亦属阴遁"
        assert before.yuan == 3 and after.yuan == 1, "处暑下元、白露上元"
        assert (before.jushu, after.jushu) == (7, 9), "两节气局数应不同"

    def test_unknown_school_raises(self) -> None:
        with pytest.raises(SchoolNotFoundError, match="未知奇门定局流派"):
            cast_qimen(datetime(2026, 9, 17, 12, 0), school="zhirun")


class TestPan:
    """排盘整体 —— 以不变式为主，固定值为辅。"""

    @pytest.fixture
    def chart(self):  # type: ignore[no-untyped-def]
        return cast_qimen(datetime(2026, 9, 17, 12, 0))

    def test_nine_palaces_complete(self, chart) -> None:  # type: ignore[no-untyped-def]
        assert [p.gong for p in chart.palaces] == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    def test_tianpan_is_rotation_of_dipan(self, chart) -> None:  # type: ignore[no-untyped-def]
        """不变式：**外八宫**的天盘干集合恒等于其地盘干集合（转动不增不减）。

        中五宫不参与转动（其天盘干寄坤二宫），必须排除 ——
        把中宫也算进来会误以为"丢了一个干"，而其实是寄宫规则。
        """
        di = {p.di_gan for p in chart.palaces if p.gong != 5}
        tian = {p.tian_gan for p in chart.palaces if p.gong != 5}
        assert di == tian, (
            f"外八宫天盘非地盘之转动：地盘={sorted(di)} 天盘={sorted(tian)}"
        )
        assert len(di) == 8, "外八宫应有 8 个不同的干"

    def test_zhifu_yi_lands_on_shigan_palace(self, chart) -> None:  # type: ignore[no-untyped-def]
        """不变式：值符（旬首之仪）必落在时干的地盘宫位 —— 「值符随时干」。"""
        hour_gan = chart.pillars["hour"][0]
        # 时干在地盘上的宫
        target = next(p.gong for p in chart.palaces if p.di_gan == hour_gan)
        # 天盘上值符仪所在的宫
        assert chart.zhifu_gong_now == target, "值符未随时干"
        assert chart.palace(target).tian_gan == chart.zhifu_yi

    @pytest.mark.parametrize(
        "when",
        [
            datetime(2026, 1, 5, 9, 0),
            datetime(2026, 3, 20, 14, 30),
            datetime(2026, 7, 8, 20, 0),
            datetime(2026, 9, 17, 12, 0),
            datetime(2026, 11, 3, 6, 15),
        ],
    )
    def test_zhifu_follows_shigan_across_times(self, when: datetime) -> None:
        """多时刻验证「值符随时干」，且**从天盘数据独立反查**。

        为什么需要这个：上面的单点测试用了 `zhifu_gong_now`，而该字段本身就是
        `shigan_gong`（等于自证）。且当值符宫与时干宫在环上恰好相距 4 宫时，
        步数取反后模 8 与原值相同（**等价变异**），单点测试必然漏过。
        故此处用多时刻，并从 `palaces` 里反查值符仪真实落宫。
        """
        chart = cast_qimen(when)
        hour_gan = chart.pillars["hour"][0]
        if hour_gan == "甲":
            target = chart.zhifu_gong
        else:
            target = next(
                (p.gong for p in chart.palaces if p.di_gan == hour_gan), None
            )
        if target is None or target == 5:
            pytest.skip("时干落中宫，本测试只覆盖外八宫")

        land = next(
            p.gong for p in chart.palaces
            if p.gong != 5 and p.tian_gan == chart.zhifu_yi
        )
        assert land == target, (
            f"{when} 值符仪（{chart.zhifu_yi}）应落 {target} 宫"
            f"（时干 {hour_gan} 之地盘宫），实落 {land} 宫"
        )

    def test_zhishi_door_lands_on_zhishi_gong(self, chart) -> None:  # type: ignore[no-untyped-def]
        """值使门必落在其计算出的落宫。"""
        assert chart.palace(chart.zhishi_gong).door == chart.zhishi_door

    def test_zhifu_star_matches_palace_origin(self, chart) -> None:  # type: ignore[no-untyped-def]
        """值符星 = 值符宫的原始九星。"""
        assert chart.zhifu_star == JIUXING_BY_GONG[chart.zhifu_gong]

    def test_stars_follow_tianpan(self, chart) -> None:  # type: ignore[no-untyped-def]
        """不变式：九星与天盘同步 —— 天盘某干所在宫，其星必为**该干原位宫**的原始星。

        真值取自 `JIUXING_BY_GONG`（固定属性表），**不能取自排盘结果** ——
        拿排盘后的星去比排盘后的星，等于自己跟自己判卷，改坏了也测不出。
        """
        di = {p.gong: p.di_gan for p in chart.palaces}
        for p in chart.palaces:
            if p.gong == 5 or p.tian_gan is None:
                continue
            src = next(g for g, gan in di.items() if gan == p.tian_gan)
            assert p.star == JIUXING_BY_GONG[src], (
                f"{p.gong}宫天盘{p.tian_gan}来自{src}宫，"
                f"星应为{JIUXING_BY_GONG[src]}，实为{p.star}"
            )

    def test_gods_order_yang_forward_yin_backward(self) -> None:
        """八神阳遁顺布、阴遁逆布 —— 用两个盘对比验证方向。"""
        yang_chart = cast_qimen(datetime(2026, 1, 5, 12, 0))   # 小寒前后，阳遁
        yin_chart = cast_qimen(datetime(2026, 9, 17, 12, 0))   # 白露后，阴遁
        assert yang_chart.dingju.yang_dun is True
        assert yin_chart.dingju.yang_dun is False

        def god_ring(chart) -> list[str]:  # type: ignore[no-untyped-def]
            gods = {p.gong: p.god for p in chart.palaces if p.god}
            return [gods[g] for g in RING_ORDER]

        # 阳遁：沿环序即 BASHEN_ORDER 的循环移位
        y = god_ring(yang_chart)
        idx = y.index("值符")
        assert [y[(idx + k) % 8] for k in range(8)] == list(BASHEN_ORDER)

        # 阴遁：沿环序为逆序
        n = god_ring(yin_chart)
        idx = n.index("值符")
        assert [n[(idx - k) % 8] for k in range(8)] == list(BASHEN_ORDER)

    def test_xun_kong_and_yima_match_palace_flags(self, chart) -> None:  # type: ignore[no-untyped-def]
        """旬空/驿马必须真实落到对应宫位的标记上。"""
        from fortune_core.qimen.pan import ZHI_TO_GONG

        kong_gongs = {ZHI_TO_GONG[z] for z in chart.xun_kong}
        for p in chart.palaces:
            assert p.is_xun_kong == (p.gong in kong_gongs), f"{p.gong}宫空亡标记错"
            assert p.is_yima == (p.gong == ZHI_TO_GONG[chart.yima]), f"{p.gong}宫驿马标记错"

    def test_center_palace_has_no_door_or_god(self, chart) -> None:  # type: ignore[no-untyped-def]
        """中五宫无门无神（寄坤），但有地盘干与天禽星。"""
        c = chart.palace(5)
        assert c.door is None and c.god is None
        assert c.di_gan is not None and c.star == "天禽"

    def test_all_outer_palaces_have_full_set(self, chart) -> None:  # type: ignore[no-untyped-def]
        """外八宫必须齐备：地盘干 / 天盘干 / 星 / 门 / 神。"""
        for p in chart.palaces:
            if p.gong == 5:
                continue
            assert p.di_gan and p.tian_gan and p.star and p.door and p.god, (
                f"{p.gong}宫信息不全：{p}"
            )

    def test_doors_are_permutation(self, chart) -> None:  # type: ignore[no-untyped-def]
        """八门必须恰好铺满外八宫，无重复。"""
        doors = [p.door for p in chart.palaces if p.door]
        assert len(doors) == 8
        assert set(doors) == set(BAMEN_BY_GONG.values())

    def test_pillars_are_four(self, chart) -> None:  # type: ignore[no-untyped-def]
        assert set(chart.pillars) == {"year", "month", "day", "hour"}
        for v in chart.pillars.values():
            assert len(v) == 2


class TestUncertainties:
    """未覆盖项必须显式声明 —— 不假装完备（RULE-008）。"""

    def test_uncertainties_declared(self) -> None:
        chart = cast_qimen(datetime(2026, 9, 17, 12, 0))
        assert len(chart.uncertainties) >= 3
        joined = " ".join(chart.uncertainties)
        assert "置闰" in joined, "必须声明置闰法未实现"
        assert "真太阳时" in joined, "必须声明未做真太阳时校正"

    def test_to_dict_is_json_serializable(self) -> None:
        import json

        chart = cast_qimen(datetime(2026, 9, 17, 12, 0))
        payload = json.dumps(chart.to_dict(), ensure_ascii=False)
        assert len(payload) > 200
        assert "palaces" in payload

    def test_school_registry(self) -> None:
        from fortune_core.qimen import SCHOOLS

        assert "chaibu" in SCHOOLS
        assert SCHOOLS["chaibu"]["name"] == "拆补法"


class TestDeterminism:
    """确定性 —— 同一输入必得同一输出（RULE-001）。"""

    def test_same_input_same_output(self) -> None:
        dt = datetime(2026, 9, 17, 12, 0)
        a, b = cast_qimen(dt), cast_qimen(dt)
        assert a.to_dict() == b.to_dict()

    def test_no_network_dependency(self) -> None:
        """内核不得联网 —— 断言源码未引入任何网络库。"""
        from pathlib import Path

        import fortune_core.qimen.constants as const_mod
        import fortune_core.qimen.pan as pan_mod

        for mod in (pan_mod, const_mod):
            src = Path(mod.__file__).read_text(encoding="utf-8")
            for forbidden in ("requests", "httpx", "urllib.request", "socket"):
                assert forbidden not in src, (
                    f"{mod.__name__} 引入了网络依赖：{forbidden}"
                )
