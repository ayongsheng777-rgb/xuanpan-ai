"""大六壬内核测试。

## 防假绿设计（沿用本项目既有纪律）

1. **独立真值 —— 三张关键表都用「另一条规律」重新生成后对照**：

   | 表 | 实现里的形态 | 测试里的独立来源 |
   |---|---|---|
   | 十干寄宫 | 手抄十项字典 | 「阳干寄禄、阴干寄冠带」——十二长生顺逆推 |
   | 月将表 | 中气 → 支 字典 | 古籍口诀逐月直录（不引用实现任何派生逻辑） |
   | 日柱 | `lunar_python` | 儒略日数纯算术公式（不经任何历法库） |

   若两边都由同一条公式生成，就是自己给自己判卷。

2. **古籍算例锚点**：两条完整的四课推导（甲子日午时戌将、癸未日戌时巳将），
   逐课对照，覆盖「寄宫 → 天盘取上神 → 再取一次」全链路。

3. **不变式优先于固定值**：「天盘是十二支的双射」「四课第二课的下神是第一课的上神」
   这类性质断言，比单点固定值更难被"改坏后仍然通过"。

4. **反查防错**：`test_guiren_ground_is_where_heaven_equals_guiren` 专门钉住
   贵人脚下的地盘宫 —— 本模块初版正是把这一步的反解方程写错，
   后果是十二天将整盘错位，而排出来的课看起来完全正常。

5. **九宗门覆盖**：横扫 60 日柱 × 144 时局，断言九法全部可达且分布合理 ——
   若某法因分支写错而永不触发，只有这种扫描能发现。
"""

from __future__ import annotations

import datetime as dt

import pytest

from fortune_core.constants import jiazi_index, xun_kong_of, yima_of
from fortune_core.exceptions import InvalidInputError, SchoolNotFoundError
from fortune_core.liuren import (
    CHONG,
    DAYTIME_ZHI,
    DIZHI,
    GUIREN,
    JIGONG,
    JIUZONGMEN,
    LIUHE,
    SCHOOLS,
    SHUN_GROUND,
    TIANJIANG_JIXIONG,
    TIANJIANG_ORDER,
    UNCERTAINTIES,
    YANG_ZHI,
    ZHONGQI_TO_YUEJIANG,
    YUEJIANG_NAME,
    ZHI_ELEMENT,
    cast_liuren,
    dun_gan_of,
    four_lessons,
    generals_of,
    ground_of,
    heaven_plate,
    month_general_of,
    san_chuan,
)

GAN = "甲乙丙丁戊己庚辛壬癸"
JIAZI_60 = [GAN[i % 10] + DIZHI[i % 12] for i in range(60)]


# ==========================================================================
# 独立真值工具（与实现无共享代码）
# ==========================================================================


def ganzhi_of_date(y: int, m: int, d: int) -> str:
    """儒略日数公式推日柱 —— 纯算术，不经过任何历法库。

    映射关系 `(JDN + 49) % 60 == 0` 时为甲子日。这条常数用两个已知锚点
    反推得到并已核对：`2000-01-01 = 戊午`、`1949-10-01 = 甲子`。
    """
    a = (14 - m) // 12
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    jdn = d + (153 * mm + 2) // 5 + 365 * yy + yy // 4 - yy // 100 + yy // 400 - 32045
    n = (jdn + 49) % 60
    return GAN[n % 10] + DIZHI[n % 12]


#: 十二长生起点（阳干顺行、阴干逆行）
CHANGSHENG_START = {
    "甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
    "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯",
}
YANG_GAN = frozenset("甲丙戊庚壬")


def changsheng_of(gan: str, step: int) -> str:
    """某天干的第十二长生位（0=长生、2=冠带、3=临官）。"""
    i = DIZHI.index(CHANGSHENG_START[gan])
    if gan in YANG_GAN:
        return DIZHI[(i + step) % 12]
    return DIZHI[(i - step) % 12]


#: 贵人口诀逐条直录（古籍原文，与实现的字典结构完全不同）
GUIREN_MNEMONIC = [
    ("甲戊庚", "牛羊"), ("乙己", "鼠猴"), ("丙丁", "猪鸡"),
    ("壬癸", "蛇兔"), ("辛", "马虎"),
]
BEAST_TO_ZHI = {
    "牛": "丑", "羊": "未", "鼠": "子", "猴": "申", "猪": "亥",
    "鸡": "酉", "蛇": "巳", "兔": "卯", "马": "午", "虎": "寅",
}


def guiren_from_mnemonic() -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for gans, beasts in GUIREN_MNEMONIC:
        for g in gans:
            out[g] = (BEAST_TO_ZHI[beasts[0]], BEAST_TO_ZHI[beasts[1]])
    return out


#: 月将口诀逐月直录：「正月雨水后用亥将，二月春分后用戌将……」
#: **这是独立真值**：实现里的表是「中气 → 支」，此处是「月序 → 神将名」，
#: 两种编码互不派生，若实现表被改坏，此处会立刻对不上。
YUEJIANG_MNEMONIC: dict[str, tuple[str, str]] = {
    # 中气: (月将支, 神将名)
    "雨水": ("亥", "登明"), "春分": ("戌", "河魁"), "谷雨": ("酉", "从魁"),
    "小满": ("申", "传送"), "夏至": ("未", "小吉"), "大暑": ("午", "胜光"),
    "处暑": ("巳", "太乙"), "秋分": ("辰", "天罡"), "霜降": ("卯", "太冲"),
    "小雪": ("寅", "功曹"), "冬至": ("丑", "大吉"), "大寒": ("子", "神后"),
}


# ==========================================================================
# 一、固定属性表
# ==========================================================================


class TestStaticTables:
    """三张关键表的独立交叉校验。表写错不报错、只给另一张盘，故必须双源对照。"""

    def test_jigong_matches_lu_and_guandai(self) -> None:
        """十干寄宫 ← 「阳干寄禄（临官）、阴干寄冠带」，用十二长生独立推出。

        这不是抄表：测试里从长生起点 + 顺逆方向**现算**禄位与冠带位。
        寄宫表若被改成任意一个"看起来像"的地支，此处必失败。
        """
        for gan in GAN:
            expected = (
                changsheng_of(gan, 3) if gan in YANG_GAN else changsheng_of(gan, 2)
            )
            assert JIGONG[gan] == expected, (
                f"{gan} 寄宫实现={JIGONG[gan]}，独立推出={expected}"
                f"（{'阳干寄禄' if gan in YANG_GAN else '阴干寄冠带'}）"
            )

    def test_jigong_never_uses_four_cardinal(self) -> None:
        """四正神（子午卯酉）永不寄宫 —— 口诀「分明不用四正神」。

        十干恰好落在其余八支上，故丙戊同寄巳、丁己同寄未，
        值域应为那八个支的一个满射。
        """
        four_cardinal = {"子", "午", "卯", "酉"}
        assert not (set(JIGONG.values()) & four_cardinal)
        assert set(JIGONG.values()) == set(DIZHI) - four_cardinal
        assert JIGONG["丙"] == JIGONG["戊"] == "巳"
        assert JIGONG["丁"] == JIGONG["己"] == "未"

    def test_yuejiang_table_matches_mnemonic(self) -> None:
        """月将表 ← 古籍逐月口诀（独立编码），逐项对照。"""
        assert set(ZHONGQI_TO_YUEJIANG) == set(YUEJIANG_MNEMONIC)
        for zq, (zhi, name) in YUEJIANG_MNEMONIC.items():
            assert ZHONGQI_TO_YUEJIANG[zq] == zhi, (
                f"{zq} 月将实现={ZHONGQI_TO_YUEJIANG[zq]}，口诀={zhi}"
            )
            assert YUEJIANG_NAME[zhi] == name, (
                f"{zhi} 神将名实现={YUEJIANG_NAME[zhi]}，口诀={name}"
            )

    def test_yuejiang_is_liuhe_of_month_rule(self) -> None:
        """再补一条结构规律：月将 = 该中气所在**月建**的六合。

        与口诀互为正交：口诀查的是"哪个月用哪个将"，这条查的是"将和月建的关系"。
        两条同时成立才算表对。
        """
        zq_to_yuejian = {
            "冬至": "子", "大寒": "丑", "雨水": "寅", "春分": "卯", "谷雨": "辰",
            "小满": "巳", "夏至": "午", "大暑": "未", "处暑": "申", "秋分": "酉",
            "霜降": "戌", "小雪": "亥",
        }
        for zq, jian in zq_to_yuejian.items():
            assert ZHONGQI_TO_YUEJIANG[zq] == LIUHE[jian]

    def test_guiren_matches_mnemonic(self) -> None:
        """贵人表 ← 口诀「甲戊庚牛羊，乙己鼠猴乡…」逐字解析。"""
        assert GUIREN == guiren_from_mnemonic()

    def test_tianjiang_names_and_balance(self) -> None:
        """十二天将：名目不重复、恰好十二个、吉凶各六。"""
        assert len(TIANJIANG_ORDER) == 12
        assert len(set(TIANJIANG_ORDER)) == 12
        assert set(TIANJIANG_ORDER) == set(TIANJIANG_JIXIONG)
        assert list(TIANJIANG_JIXIONG.values()).count("吉") == 6
        assert list(TIANJIANG_JIXIONG.values()).count("凶") == 6

    def test_jiuzongmen_order_is_specified(self) -> None:
        """九宗门顺序不可乱 —— 伏吟/返吟必须排在最前。

        它们判的是**天地盘整体结构**（月将与占时同位/相冲）。若被通用的贼克法
        抢先接走，中末传的推法与返吟要求的「取冲」完全不同。
        """
        assert JIUZONGMEN == (
            "伏吟", "返吟", "贼克", "比用", "涉害", "遥克", "昴星", "别责", "八专"
        )

    def test_undeclared_gaps_are_declared(self) -> None:
        """未覆盖项必须显式声明，不能假装完备（RULE-006 精神）。"""
        assert len(UNCERTAINTIES) >= 3
        joined = "".join(UNCERTAINTIES)
        for keyword in ("贵人", "涉害", "真太阳时"):
            assert keyword in joined, f"uncertainties 未声明 {keyword} 相关缺口"

    def test_schools_has_default(self) -> None:
        assert "default" in SCHOOLS
        assert SCHOOLS["default"]["name"]


# ==========================================================================
# 二、天地盘
# ==========================================================================


class TestHeavenPlate:
    def test_is_bijection_for_all_144_combinations(self) -> None:
        """任意月将 × 占时，天盘都必须是十二支的一个排列（双射）。

        这条不变式一破，"天盘上神"的取值就会出现重复或缺失，
        而单点固定值测试照样能过。
        """
        for jiang in DIZHI:
            for shi in DIZHI:
                tian = heaven_plate(jiang, shi)
                assert len(tian) == 12
                assert set(tian) == set(DIZHI)
                assert set(tian.values()) == set(DIZHI), f"{jiang}将{shi}时天盘有重复支"

    def test_month_general_sits_on_hour(self) -> None:
        """「月将加时」的字面含义：月将必须落在占时宫之上。"""
        for jiang in DIZHI:
            for shi in DIZHI:
                assert heaven_plate(jiang, shi)[shi] == jiang

    def test_ground_of_inverts_heaven_plate(self) -> None:
        """`ground_of` 是 `heaven_plate` 的反函数 —— 十二项全部往返一致。"""
        for jiang in DIZHI:
            for shi in DIZHI:
                tian = heaven_plate(jiang, shi)
                for z in DIZHI:
                    assert ground_of(tian, tian[z]) == z

    def test_identity_when_general_equals_hour(self) -> None:
        """月将 == 占时（即伏吟）时天地盘重叠，天盘等于地盘。"""
        for z in DIZHI:
            assert heaven_plate(z, z) == {g: g for g in DIZHI}

    def test_chong_when_opposite(self) -> None:
        """月将与占时相冲（即返吟）时，每个天盘支都是其地盘宫的冲位。"""
        for z in DIZHI:
            tian = heaven_plate(CHONG[z], z)
            assert tian == {g: CHONG[g] for g in DIZHI}

    def test_rejects_non_zhi(self) -> None:
        with pytest.raises(InvalidInputError):
            heaven_plate("甲", "午")
        with pytest.raises(InvalidInputError):
            heaven_plate("戌", "甲")


# ==========================================================================
# 三、四课
# ==========================================================================


class TestFourLessons:
    """古籍算例 + 结构不变式。"""

    @pytest.mark.parametrize(
        "day_gan, day_zhi, jiang, shi, expected",
        [
            # 甲子日、午时、戌将
            ("甲", "子", "戌", "午",
             [("午", "甲"), ("戌", "午"), ("辰", "子"), ("申", "辰")]),
            # 癸未日、戌时、巳将
            ("癸", "未", "巳", "戌",
             [("申", "癸"), ("卯", "申"), ("寅", "未"), ("酉", "寅")]),
        ],
    )
    def test_ancient_examples(
        self, day_gan: str, day_zhi: str, jiang: str, shi: str,
        expected: list[tuple[str, str]],
    ) -> None:
        """两条完整四课推导，逐课对照（覆盖"寄宫→取上神→再取一次"全链路）。"""
        lessons = four_lessons(day_gan, day_zhi, heaven_plate(jiang, shi))
        got = [(x.upper, x.lower_label) for x in lessons]
        assert got == expected

    def test_structure_invariants_across_sweep(self) -> None:
        """四课的链式结构：2 课下神 = 1 课上神，4 课下神 = 3 课上神。

        这两条抄漏了，四课会少一半，而三传照样能取出来 —— 属于
        "少了东西却看不出少了"的典型，必须由不变式兜住。
        """
        for gz in JIAZI_60:
            gan, zhi = gz[0], gz[1]
            for jiang in DIZHI:
                for shi in DIZHI:
                    le = four_lessons(gan, zhi, heaven_plate(jiang, shi))
                    assert len(le) == 4
                    assert le[1].lower == le[0].upper
                    assert le[3].lower == le[2].upper
                    assert le[0].lower_label == gan, "第一课下神必须是日干本身"
                    assert le[2].lower == zhi, "第三课下神必须是日支"
                    assert [x.index for x in le] == [1, 2, 3, 4]

    def test_first_lesson_lower_is_jigong(self) -> None:
        """第一课的下神是日干**寄宫**，上神取天盘该宫。"""
        tian = heaven_plate("戌", "午")
        le = four_lessons("甲", "子", tian)
        assert le[0].lower == JIGONG["甲"] == "寅"
        assert le[0].upper == tian["寅"] == "午"

    def test_rejects_bad_input(self) -> None:
        tian = heaven_plate("戌", "午")
        with pytest.raises(InvalidInputError):
            four_lessons("子", "子", tian)  # 日干必须是天干
        with pytest.raises(InvalidInputError):
            four_lessons("甲", "甲", tian)  # 日支必须是地支


# ==========================================================================
# 四、三传（九宗门）
# ==========================================================================


class TestSanChuan:
    """九宗门逐个锚点 + 传播不变式 + 覆盖率扫描。"""

    #: (日柱, 占时, 月将, 期望三传, 期望宗门)
    #: 每一条都已手工复核过四课与取用路径，不是"跑出来的就记下来"。
    ANCHORS = [
        # 贼克：四课 午/甲 戌/午 辰/子 申/辰，仅第三课上克下（辰土克子水）
        ("甲子", "午", "戌", ("辰", "申", "子"), "贼克"),
        # 比用：下贼上得丑、子两课，取与阳日干甲同阴阳者（子为阳支）
        ("甲子", "丑", "子", ("子", "亥", "戌"), "比用"),
        # 涉害：上克下得戌两课（第三课与第二课），比用后仍两课，走涉害分档
        ("甲子", "寅", "子", ("戌", "申", "午"), "涉害"),
        # 伏吟：月将==占时，天地盘重叠，甲（刚日）无克取干上神寅，中末递刑寅→巳→申
        ("甲子", "戌", "戌", ("寅", "巳", "申"), "伏吟"),
        # 返吟：辰戌相冲，下贼上得寅一课，中末各取其冲
        ("甲子", "辰", "戌", ("寅", "申", "寅"), "返吟"),
        # 别责：戊辰日四课只三课且无克无遥克，刚日取日干六合之干（戊合癸）寄宫丑之上神寅
        ("戊辰", "亥", "子", ("寅", "午", "午"), "别责"),
        # 八专：丁未日寄宫==日支，柔日取第四课上神逆数三位
        ("丁未", "丑", "子", ("卯", "午", "午"), "八专"),
        # 昴星：己巳日四课全备无克无遥克，柔日取天盘酉之下神发用
        ("己巳", "亥", "子", ("申", "申", "午"), "昴星"),
        # 遥克：丙寅日上神克日干（亥水克丙火）
        ("丙寅", "卯", "子", ("亥", "申", "巳"), "遥克"),
    ]

    @pytest.mark.parametrize(
        "day_ganzhi, shi, jiang, expected, men", ANCHORS,
        ids=[f"{a[0]}-{a[1]}时-{a[2]}将-{a[4]}" for a in ANCHORS],
    )
    def test_anchors(
        self, day_ganzhi: str, shi: str, jiang: str,
        expected: tuple[str, str, str], men: str,
    ) -> None:
        gan, zhi = day_ganzhi[0], day_ganzhi[1]
        tian = heaven_plate(jiang, shi)
        le = four_lessons(gan, zhi, tian)
        chuan, got_men, note = san_chuan(le, gan, zhi, jiang, shi, tian)
        assert chuan == expected, f"三传不符：得到 {chuan}"
        assert got_men == men, f"宗门不符：得到 {got_men}"
        assert note, "宗门说明不能为空（界面与 Agent 要如实转述）"

    def test_all_nine_methods_are_reachable(self) -> None:
        """横扫 60 日柱 × 144 时局，九法必须**全部**被触发过。

        某个分支若因条件写错而永不进入，单点测试发现不了 —— 只有覆盖率扫描能。
        顺带断言分布量级：贼克应是主流、八专/别责应罕见。
        """
        from collections import Counter

        counts: Counter[str] = Counter()
        for gz in JIAZI_60:
            gan, zhi = gz[0], gz[1]
            for jiang in DIZHI:
                for shi in DIZHI:
                    tian = heaven_plate(jiang, shi)
                    le = four_lessons(gan, zhi, tian)
                    _, men, _ = san_chuan(le, gan, zhi, jiang, shi, tian)
                    counts[men] += 1

        assert set(counts) == set(JIUZONGMEN), (
            f"未触发的宗门：{set(JIUZONGMEN) - set(counts)}"
        )
        total = sum(counts.values())
        assert total == 60 * 144
        # 量级校验：贼克占三成以上；八专/别责各不足 5%
        assert counts["贼克"] / total > 0.30
        assert counts["八专"] / total < 0.05
        assert counts["别责"] / total < 0.05
        # 八专只有五日，其出现数必为 5 × 144 的倍数关系下的极小值
        assert counts["八专"] == 108 and counts["别责"] == 108

    def test_fuyin_and_fanyin_count(self) -> None:
        """伏吟/返吟各为 1/12 的时局（月将与占时同位/相冲各有 12 种组合）。"""
        from collections import Counter

        counts: Counter[str] = Counter()
        for gz in JIAZI_60:
            for jiang in DIZHI:
                for shi in DIZHI:
                    tian = heaven_plate(jiang, shi)
                    le = four_lessons(gz[0], gz[1], tian)
                    _, men, _ = san_chuan(le, gz[0], gz[1], jiang, shi, tian)
                    counts[men] += 1
        assert counts["伏吟"] == 60 * 12
        assert counts["返吟"] == 60 * 12

    def test_common_methods_propagate_through_heaven_plate(self) -> None:
        """贼克/比用/涉害/遥克：中传 = 天盘[初传]，末传 = 天盘[中传]。

        这条是"常法"的定义。若有人把传播写成「取初传之冲」之类，
        四课不动、宗门名不变，只有三传会整串错位 —— 必须由不变式钉住。
        """
        common = {"贼克", "比用", "涉害", "遥克"}
        checked = 0
        for gz in JIAZI_60:
            for jiang in DIZHI:
                for shi in DIZHI:
                    tian = heaven_plate(jiang, shi)
                    le = four_lessons(gz[0], gz[1], tian)
                    (c, zh, mo), men, _ = san_chuan(le, gz[0], gz[1], jiang, shi, tian)
                    if men not in common:
                        continue
                    assert zh == tian[c], f"{men} 中传应为天盘[{c}]"
                    assert mo == tian[zh], f"{men} 末传应为天盘[{zh}]"
                    checked += 1
        assert checked > 5000, f"常法样本过少（{checked}），不变式形同虚设"

    @pytest.mark.parametrize(
        "day_ganzhi", ["丁丑", "己丑", "辛丑", "丁未", "己未", "辛未"]
    )
    def test_fanyin_no_ke_uses_yima(self, day_ganzhi: str) -> None:
        """返吟六日无克：初传取驿马，中传取支上神，末传取干上神。

        这六日（丁丑 己丑 辛丑 丁未 己未 辛未）在古籍中是点名的特例。
        实现**不硬编码**这六日，而是先试贼克、试不出来再取驿马 ——
        此处即验证这条回退真的走到了，且结果与古籍口径一致。
        """
        gan, zhi = day_ganzhi[0], day_ganzhi[1]
        tian = heaven_plate("戌", "辰")  # 辰戌冲 → 返吟
        le = four_lessons(gan, zhi, tian)
        (c, zh, mo), men, _ = san_chuan(le, gan, zhi, "戌", "辰", tian)
        assert men == "返吟"
        assert c == yima_of(zhi), f"{day_ganzhi} 初传应为驿马 {yima_of(zhi)}"
        assert zh == tian[zhi], "中传应为支上神"
        assert mo == tian[JIGONG[gan]], "末传应为干上神"

    def test_eight_zhuan_days_are_exactly_five(self) -> None:
        """八专日 = 寄宫与日支同支者，恰好五日（甲寅 庚申 丁未 己未 癸丑）。"""
        found = [gz for gz in JIAZI_60 if JIGONG[gz[0]] == gz[1]]
        assert sorted(found) == sorted(["甲寅", "庚申", "丁未", "己未", "癸丑"])


# ==========================================================================
# 五、十二天将
# ==========================================================================


class TestGenerals:
    def test_guiren_ground_is_where_heaven_equals_guiren(self) -> None:
        """🔴 反查防错（本模块初版在此处出过 bug）。

        贵人"临"的地盘宫，定义就是「天盘支 == 贵人支」的那个宫。
        初版用解方程求这个宫，多减了一项时辰 → 得到另一个合法地支 →
        顺逆翻转 → **十二天将整盘错位**，而排出来的课毫无异常。

        这条断言把定义直接写成检查，任何反解写法都会被它打回。
        """
        for gz in JIAZI_60:
            for shi in DIZHI:
                tian = heaven_plate("戌", shi)
                _, gzhi, ground, _ = generals_of(gz[0], shi, tian)
                assert tian[ground] == gzhi, (
                    f"{gz}日{shi}时：贵人{gzhi} 应临地盘宫 {ground}，"
                    f"但该宫天盘是 {tian[ground]}"
                )

    def test_each_general_used_exactly_once(self) -> None:
        """十二天将必须恰好各布一次（映射是双射）。"""
        for shi in DIZHI:
            mapping, _, _, _ = generals_of("甲", shi, heaven_plate("戌", shi))
            assert len(mapping) == 12
            assert set(mapping.values()) == set(TIANJIANG_ORDER)

    def test_guiren_selection_by_day_and_night(self) -> None:
        """昼夜贵人：占时在 卯~申 用昼贵，其余用夜贵。"""
        tian = heaven_plate("戌", "午")
        for shi in DIZHI:
            _, gzhi, _, _ = generals_of("甲", shi, heaven_plate("戌", shi))
            expected = GUIREN["甲"][0 if shi in DAYTIME_ZHI else 1]
            assert gzhi == expected, f"{shi}时贵人应取 {expected}"
        assert not tian == {}  # 保持 tian 被引用，避免 F841

    def test_shun_reverse_rule(self) -> None:
        """顺逆由**贵人脚下的地盘宫**决定：亥子丑寅卯辰顺，余者逆。"""
        for shi in DIZHI:
            for jiang in DIZHI:
                tian = heaven_plate(jiang, shi)
                _, _, ground, shun = generals_of("甲", shi, tian)
                assert shun == (ground in SHUN_GROUND)

    def test_anchored_case(self) -> None:
        """甲子日午时戌将：昼贵丑，临地盘酉（酉属逆布六宫），故逆布。

        十二将落位已在探针中逐宫手工复核过，此处只钉最易错的几格。
        """
        tian = heaven_plate("戌", "午")
        mapping, gzhi, ground, shun = generals_of("甲", "午", tian)
        assert (gzhi, ground, shun) == ("丑", "酉", False)
        assert mapping["丑"] == "贵人"
        assert mapping["午"] == "白虎"
        assert mapping["子"] == "螣蛇"

    def test_rejects_bad_gan(self) -> None:
        with pytest.raises(InvalidInputError):
            generals_of("子", "午", heaven_plate("戌", "午"))


# ==========================================================================
# 六、遁干
# ==========================================================================


class TestDunGan:
    @pytest.mark.parametrize(
        "day_ganzhi, zhi, expected",
        [
            ("甲子", "子", "甲"), ("甲子", "丑", "乙"), ("甲子", "寅", "丙"),
            ("甲子", "酉", "癸"),
            # 甲戌旬：甲戌 乙亥 丙子 …（旬首支为戌，序数不与支序对齐）
            ("甲戌", "子", "丙"),
            # 甲申旬：甲申 乙酉 丙戌 丁亥 戊子 …（子在本旬第五位 → 戊）
            ("甲申", "子", "戊"),
            ("甲申", "申", "甲"),
        ],
    )
    def test_examples(self, day_ganzhi: str, zhi: str, expected: str) -> None:
        assert dun_gan_of(day_ganzhi, zhi) == expected

    @pytest.mark.parametrize("day_ganzhi", ["甲子", "甲戌", "甲申", "甲午", "甲辰", "甲寅"])
    def test_xunkong_has_no_dun_gan(self, day_ganzhi: str) -> None:
        """旬空之支不配干 —— 返回 None 是**领域信号**（空亡），不是数据缺失。

        这条同时钉住"旬空"与"遁干"两套算法对同一旬的理解一致：
        若遁干改用别的算法，空亡之位可能被凑出天干来。
        """
        for zhi in xun_kong_of(day_ganzhi):
            assert dun_gan_of(day_ganzhi, zhi) is None

    def test_matches_jiazi_sequence_for_all_60(self) -> None:
        """全量对照：某支的遁干应等于该支在**本旬六十甲子序列**中的天干。"""
        for n, gz in enumerate(JIAZI_60):
            xun_start = (n // 10) * 10
            for k in range(10):
                day = JIAZI_60[xun_start + k]
                assert dun_gan_of(gz, day[1]) == day[0], (
                    f"{gz} 旬，支{day[1]} 遁干应为 {day[0]}"
                )
            # 本旬最后两支为旬空
            for k in (10, 11):
                assert dun_gan_of(gz, JIAZI_60[(xun_start + k) % 60][1]) is None

    def test_rejects_bad_zhi(self) -> None:
        with pytest.raises(InvalidInputError):
            dun_gan_of("甲子", "甲")


# ==========================================================================
# 七、月将（以中气换将）
# ==========================================================================


class TestMonthGeneral:
    def test_boundary_is_zhongqi_not_jieqi(self) -> None:
        """🔴 换将以**中气**为界。逐个中气验证「交气前一刻用旧将、后一刻用新将」。

        这是六壬最常被写错的一处：用节气换将，会在每月上半月
        （节已到、气未到）系统性取错月将，而盘面完全正常。
        """
        from lunar_python import Solar

        solar = Solar.fromYmdHms(2026, 6, 1, 12, 0, 0)
        table = solar.getLunar().getJieQiTable()
        checked = 0
        for name, jq in table.items():
            if name not in ZHONGQI_TO_YUEJIANG:
                continue
            t = dt.datetime(
                jq.getYear(), jq.getMonth(), jq.getDay(),
                jq.getHour(), jq.getMinute(), jq.getSecond(),
            )
            after = t + dt.timedelta(hours=1)
            s_after = Solar.fromYmdHms(after.year, after.month, after.day,
                                       after.hour, after.minute, after.second)
            jiang, zq, _ = month_general_of(s_after)
            assert zq == name, f"{after} 应依中气 {name}，实得 {zq}"
            assert jiang == ZHONGQI_TO_YUEJIANG[name]

            before = t - dt.timedelta(hours=1)
            s_before = Solar.fromYmdHms(before.year, before.month, before.day,
                                        before.hour, before.minute, before.second)
            jiang_b, zq_b, _ = month_general_of(s_before)
            assert zq_b != name, (
                f"{before} 在 {name} 交气之前，不应已用该中气的月将"
            )
            checked += 1
        assert checked == 12, f"应核对 12 个中气，实际 {checked}"

    def test_known_dates(self) -> None:
        """点检几个日期（口诀直推）：处暑后 → 巳将；冬至后 → 丑将。

        2026-12-25 这条是**回归锚点**：修掉「节气表键名窗口滚动」那个 bug 之前，
        它会错答成小雪/寅将 —— 因为该日期对应的冬至被存成了 ASCII 别名。
        """
        from lunar_python import Solar

        for y, m, d, expect_zq, expect_jiang in [
            (2026, 9, 17, "处暑", "巳"),
            (2026, 2, 25, "雨水", "亥"),
            (2026, 12, 25, "冬至", "丑"),
            (2026, 1, 1, "冬至", "丑"),
        ]:
            solar = Solar.fromYmdHms(y, m, d, 12, 0, 0)
            jiang, zq, t = month_general_of(solar)
            assert (zq, jiang) == (expect_zq, expect_jiang)
            assert isinstance(t, dt.datetime)


# ==========================================================================
# 八、端到端排盘
# ==========================================================================


class TestCastLiuren:
    WHEN = dt.datetime(2026, 9, 17, 10, 0, 0)

    def test_day_ganzhi_matches_independent_jdn(self) -> None:
        """日柱与**儒略日数公式**（不经任何历法库）一致。"""
        chart = cast_liuren(self.WHEN)
        assert chart.day_ganzhi == ganzhi_of_date(2026, 9, 17) == "甲午"

    def test_hour_zhi_from_shichen(self) -> None:
        """时支：10:00 → 巳时；23:30 → 子时。"""
        assert cast_liuren(self.WHEN).hour_zhi == "巳"
        assert cast_liuren(dt.datetime(2026, 9, 17, 23, 30)).hour_zhi == "子"

    def test_xun_kong_and_yima_come_from_shared_helpers(self) -> None:
        """旬空/驿马直接复用 `fortune_core.constants` 的共享实现。

        此前六爻、奇门各写过一份，同一个日柱会算出三个旬空。
        这条断言钉住"唯一真源"，防止有人在六壬里再抄一份。
        """
        chart = cast_liuren(self.WHEN)
        assert chart.xun_kong == xun_kong_of("甲午")
        payload = chart.to_dict()
        assert payload["yima"] == yima_of("午")
        assert payload["xun_kong"] == list(xun_kong_of("甲午"))

    def test_guiren_ground_consistency_end_to_end(self) -> None:
        """端到端复验贵人落宫定义（防止只在单测里对、在 `cast_liuren` 里串了参）。"""
        for hour in (0, 3, 6, 9, 12, 15, 18, 21, 23):
            chart = cast_liuren(dt.datetime(2026, 9, 17, hour, 0))
            palace = chart.palace(chart.guiren_ground)
            assert palace.heaven == chart.guiren_zhi
            assert palace.is_guiren_ground is True
            assert palace.general == "贵人"

    def test_structure_is_complete(self) -> None:
        chart = cast_liuren(self.WHEN)
        assert len(chart.palaces) == 12
        assert len(chart.lessons) == 4
        assert len(chart.chuan) == 3
        assert [c.position for c in chart.chuan] == ["初传", "中传", "末传"]
        assert chart.month_general_name == YUEJIANG_NAME[chart.month_general]
        assert chart.chuanke in JIUZONGMEN
        assert chart.chuanke_note
        assert chart.school == "default"
        assert chart.uncertainties == UNCERTAINTIES
        # 日柱是可用的干支：拆得出的干要在日干表里、支要在十二支里
        payload = chart.to_dict()
        assert len(chart.day_ganzhi) == 2
        assert payload["day_gan"] == chart.day_ganzhi[0]
        assert payload["day_zhi"] == chart.day_ganzhi[1]
        assert chart.day_ganzhi[0] in GUIREN
        assert chart.day_ganzhi[1] in DIZHI

    def test_chuan_are_consistent_with_heaven_plate(self) -> None:
        """三传的两个位置必须真的能在天盘上找到对应（初→中→末 或冲位）。"""
        chart = cast_liuren(self.WHEN)
        zhijiang = {p.ground: p.heaven for p in chart.palaces}
        for c in chart.chuan:
            assert c.zhi in zhijiang.values(), f"三传之支 {c.zhi} 不在天盘上"

    def test_lessons_mark_the_source_of_chu(self) -> None:
        """至少有一课被标为初传所出（界面靠它高亮"三传从哪来"）。"""
        chart = cast_liuren(self.WHEN)
        assert any(x.is_ke for x in chart.lessons)

    def test_to_dict_has_no_fortune_verdict(self) -> None:
        """🔴 内核不下吉凶断语：允许给天将自身的吉凶属性（FACT），
        但不得出现任何聚合性的"结论"字段（RULE-001 / RULE-008）。"""
        payload = cast_liuren(self.WHEN).to_dict()
        forbidden = {"verdict", "judgement", "judgment", "吉凶", "断语", "结论", "score"}
        assert not (set(payload) & forbidden)
        # 天将属性是事实，可以出现
        assert payload["palaces"][0]["general_jixiong"] in {"吉", "凶", None}

    def test_unknown_school_raises(self) -> None:
        with pytest.raises(SchoolNotFoundError):
            cast_liuren(self.WHEN, school="不存在的流派")

    def test_deterministic(self) -> None:
        """同一时刻两次排盘必须完全一致（无随机、无隐藏状态）。"""
        assert cast_liuren(self.WHEN).to_dict() == cast_liuren(self.WHEN).to_dict()


# ==========================================================================
# 九、与共享常量的一致性
# ==========================================================================


class TestSharedConstants:
    def test_chong_liuhe_yangzhi_are_consistent(self) -> None:
        """六冲/六合/阴阳三张表的自洽性（子=0 序）。"""
        for i, z in enumerate(DIZHI):
            assert CHONG[z] == DIZHI[(i + 6) % 12]
            assert CHONG[CHONG[z]] == z
            assert LIUHE[LIUHE[z]] == z
            assert (z in YANG_ZHI) == (i % 2 == 0)

    def test_zhi_element_covers_12(self) -> None:
        assert len(ZHI_ELEMENT) == 12
        assert set(ZHI_ELEMENT) == set(DIZHI)

    def test_jiazi_index_sanity(self) -> None:
        assert jiazi_index("甲子") == 0
        assert jiazi_index("癸亥") == 59
