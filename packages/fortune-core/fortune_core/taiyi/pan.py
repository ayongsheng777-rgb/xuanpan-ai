"""太乙神数排盘 —— 年局（岁计）。

## 排盘链路

```
公元年 ─→ 太乙积年 ─┬─→ 太乙行宫（三年一宫，不入中五）
                     ├─→ 文昌天目（顺行十六神，遇乾坤重留）
                     ├─→ 计神（十二支逆行）──→ 始击客目（计神加艮，文昌随之转）
                     ├─→ 定目（合神加太岁，文昌随之转）
                     ├─→ 主 / 客 / 定 三算 ──→ 大将、参将落宫
                     └─→ 值事八门（30 年一换，240 年一周）
```

## 已验证的锚点

**太乙阳遁第一局 = 1972 年**（甲子年：积年 − 1 同时被 24 与 18 整除）。
古籍对该局给了完整的数字，本实现逐项吻合：

| 项 | 古籍 | 本实现 |
|---|---|---|
| 太乙 | 乾一宫 | 乾 1 宫 |
| 文昌 | 武德（申） | 申 |
| 计神 | 寅 | 寅 |
| 始击 | 大武（坤） | 坤 |
| 主算 | 1 + 6 = 7 | 7 |
| 客算 | 7 + 6 = 13 | 13 |
| 定目 / 定算 | 坤 / 13 | 坤 / 13 |

另有三个独立锚点（不属该局）：
**2004 年太乙在艮三宫、入宫第 3 年**；**1984 年值事八门为生门**；
**2002 年为壬子元第 31 局**。

## 三个最容易写错、且错了不报错的地方

1. **积年从 1 起算**。全部取模都要先减一：`k = 积年 − 1`。
   不减一会让行宫、文昌、局数、值事门**同时**偏一位 —— 而减一之后
   「1984 值事生门」「2002 壬子元第 31 局」「2044 甲子元第 1 局」三个
   互不相干的锚点才会同时成立。用不减一的版本，三个锚点一个都对不上。
2. **「数至太乙前一宫为止」的「前」是顺行方向的终点，不是索引减一。**
   起点含、太乙宫不含、间神不累加。申起一 → 兑六 → 乾即太乙而止，得 1 + 6 = 7。
   按索引减一会把整盘算数系统性算小。
3. **太乙宫号与洛书错位**（见 `constants` 模块头）。表独立，不复用奇门。

## 本模块刻意不做的事

**不下吉凶断语。** 三算的长短 / 和数 / 孤数 / 三才、门的吉凶属性、神将落宫，
一律作为 FACT 返回，不合成「利主 / 利客」「吉 / 凶」这类结论
（RULE-001 / RULE-008）。格局（掩迫囚击关格）与断法属上层解读，内核不碰。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..constants import DIZHI, TIANGAN
from ..exceptions import InvalidInputError, SchoolNotFoundError
from .constants import (
    BAMEN_CYCLE_YEARS,
    BAMEN_JIXIONG,
    BAMEN_ORDER,
    BAMEN_SWITCH_YEARS,
    CHANGDUAN_LONG_MIN,
    CHANGDUAN_SHORT_MAX,
    CYCLE_JI,
    CYCLE_WUYUAN_LIUJI,
    CYCLE_YUAN,
    GUSHU_CLASS,
    HESHU_CLASS,
    JIYAN_BASE,
    LI_SANCAI,
    LIUHE,
    PALACE_CLOCKWISE,
    PALACE_CLOCKWISE_INDEX,
    PALACE_DIRECTION,
    PALACE_GUA,
    PALACE_YINYANG,
    RING_INDEX,
    SANCAI_DIGIT_RULE,
    SANCAI_TENS_LIMIT,
    SCHOOLS,
    SHEN_NAME,
    SHEN_PALACE,
    SHISEN_RING,
    TAIYI_XUN_GONG,
    UNCERTAINTIES,
    WENCHANG_SEQ_YANG,
    WUYUAN_NAMES,
)


# --------------------------------------------------------------------------
# 一、积年与五元六纪
# --------------------------------------------------------------------------


def jiyan_of(year: int, base: int = JIYAN_BASE) -> int:
    """太乙积年 —— 基数 + 公元年。

    `year` 可为 0 与负数（公式本身不设限，只是取模结果会回绕）。
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise InvalidInputError(f"年份必须是整数，得到 {year!r}")
    return base + year


def year_ganzhi_of(year: int) -> str:
    """公元年的干支（年柱口径）。

    按整数年直接换算，等价于「该年**立春之后**」的干支。
    立春之前仍属上一年的干支 —— 本函数不处理这一段，
    已登记在 `UNCERTAINTIES`（年局输入是裸年份，没有日期可供分界）。
    """
    idx = (year - 4) % 60
    return TIANGAN[idx % 10] + DIZHI[idx % 12]


@dataclass(frozen=True)
class Epoch:
    """五元六纪的定位。"""

    wuyuan_index: int   # 0..4
    ju: int             # 元内第几局（1..72）
    ji_index: int       # 0..5
    ji_year: int        # 纪内第几年（1..60）

    @property
    def wuyuan_name(self) -> str:
        return WUYUAN_NAMES[self.wuyuan_index]

    def to_dict(self) -> dict[str, Any]:
        return {
            "wuyuan_index": self.wuyuan_index,
            "wuyuan": self.wuyuan_name,
            "ju": self.ju,
            "ju_label": f"{self.wuyuan_name}第 {self.ju} 局",
            "ji_number": self.ji_index + 1,   # 第几纪（1..6）
            "ji_year": self.ji_year,
        }


def epoch_of(jiyan: int) -> Epoch:
    """五元六纪 —— 定位「第几元 / 元内第几局 / 第几纪 / 纪内第几年」。

    古籍三步除法：积年 ÷ 360 取余 → 余数 ÷ 60 得纪 → 余数 ÷ 72 得元与局。
    本实现先取 360 的余再分别除，而不是直接对 72 取模：
    元（5 × 72）与纪（6 × 60）是同一 360 年周期的两种切法，
    分开取模会让「元内之局」与「纪内之年」来自两个不同原点而互不自洽。

    🔴 取模前先减一（积年从 1 起算），否则元、局全体偏一位。
    """
    if jiyan < 1:
        raise InvalidInputError(f"积年必须为正，得到 {jiyan}")
    k = jiyan - 1
    r360 = k % CYCLE_WUYUAN_LIUJI
    ji_index, ji_year = divmod(r360, CYCLE_JI)
    wuyuan_index, ju = divmod(r360, CYCLE_YUAN)
    return Epoch(
        wuyuan_index=wuyuan_index,
        ju=ju + 1,
        ji_index=ji_index,
        ji_year=ji_year + 1,
    )


# --------------------------------------------------------------------------
# 二、太乙行宫
# --------------------------------------------------------------------------


def taiyi_palace_of(jiyan: int) -> tuple[int, int]:
    """太乙落宫 —— 返回 `(宫号, 入宫第几年 1..3)`。

    「三年一宫，二十四年一周，不入中五」。二十四年的余数除以三，
    商即行宫序（0..7，对应宫号序 乾→离→艮→震→兑→坤→坎→巽），余数即入宫年。

    注意 `r == 0` 的去向：它表示二十四年周期刚刚走满，
    应落在**第八宫（巽九）**的第三年，而不是第一宫的零年 ——
    直接 `r // 3` 会把这一年的太乙扔回乾宫。
    """
    if jiyan < 1:
        raise InvalidInputError(f"积年必须为正，得到 {jiyan}")
    r = (jiyan - 1) % (len(TAIYI_XUN_GONG) * 3)
    return TAIYI_XUN_GONG[r // 3], r % 3 + 1


# --------------------------------------------------------------------------
# 三、文昌（天目）与计神
# --------------------------------------------------------------------------


def wenchang_of(jiyan: int) -> str:
    """文昌（天目）所在十六神位 —— 「天目上元起于申，依数顺行十六神」。

    阳遁自武德（申）起，遇阴德（乾）、大武（坤）各重留一步，十八年一周。
    `k = 积年 − 1` 为 0 时正落在申，即**阳遁第一局**（1972 年）。
    """
    if jiyan < 1:
        raise InvalidInputError(f"积年必须为正，得到 {jiyan}")
    return WENCHANG_SEQ_YANG[(jiyan - 1) % len(WENCHANG_SEQ_YANG)]


def jishen_of(year_zhi: str) -> str:
    """计神 —— 「子岁计神寅上起，丑牛寅鼠逆周流」，逆行十二支、不用四维。

    即 `(寅序 − 年支序) mod 12`；等价于把「子年加寅」这一条口诀
    写成公式，而不是抄一张十二项的表 —— 表抄错一项，只有那一年错。
    """
    if year_zhi not in DIZHI:
        raise InvalidInputError(f"年支必须是十二支之一，得到 {year_zhi!r}")
    return DIZHI[(DIZHI.index("寅") - DIZHI.index(year_zhi)) % 12]


def _rotate_pos(pos: str, steps: int) -> str:
    """把十六神环上的一个位旋转 `steps` 步（顺行为正）。"""
    if pos not in RING_INDEX:
        raise InvalidInputError(f"必须是十六神之一，得到 {pos!r}")
    return SHISEN_RING[(RING_INDEX[pos] + steps) % len(SHISEN_RING)]


def shiji_of(wenchang_pos: str, jishen_zhi: str) -> str:
    """始击（客目）—— 「计神用加和德上，下看天目所临辰」。

    把计神移到和德（艮）位，文昌随同一转动，文昌转到哪一位、始击就在哪一位。
    所以转动量 = 艮位 − 计神位（在十六神环上、顺行方向计），
    再把这个量加到文昌上。**不是在九宫上转** —— 十六神环含八间神，
    与八宫环的步长不同，用九宫转会得到另一个看起来合法的位。
    """
    steps = RING_INDEX["艮"] - RING_INDEX[jishen_zhi]
    return _rotate_pos(wenchang_pos, steps)


def dingmu_of(wenchang_pos: str, tai_sui: str) -> str:
    """定目 —— 「以合神加太岁上，看文昌所临」。

    与始击同一机制，只是锚点从「艮」换成「太岁位」，
    转动量为「太岁位 − 合神位」。合神取太岁的六合支。
    """
    if tai_sui not in LIUHE:
        raise InvalidInputError(f"太岁必须是十二支之一，得到 {tai_sui!r}")
    he_shen = LIUHE[tai_sui]
    steps = RING_INDEX[tai_sui] - RING_INDEX[he_shen]
    return _rotate_pos(wenchang_pos, steps)


# --------------------------------------------------------------------------
# 四、三算（主 / 客 / 定）
# --------------------------------------------------------------------------


def palace_of_pos(pos: str) -> int:
    """十六神位 → 太乙宫号。

    八正神自有宫号；八间神归入**顺行方向最近**的那个正宫 ——
    古籍算例里说「申在 6 宫位」，而申顺行的下一个正宫正是酉（兑 6），
    与此约定吻合。间神归宫各家表述不一，是已知分歧点。
    """
    if pos not in RING_INDEX:
        raise InvalidInputError(f"必须是十六神之一，得到 {pos!r}")
    own = SHEN_PALACE.get(pos)
    if own is not None:
        return own
    for step in range(1, len(SHISEN_RING)):
        got = SHEN_PALACE.get(SHISEN_RING[(RING_INDEX[pos] + step) % len(SHISEN_RING)])
        if got is not None:
            return got
    raise InvalidInputError("十六神环不完整")  # pragma: no cover


def suan_of(start_pos: str, taiyi_palace: int) -> tuple[int, tuple[str, ...]]:
    """三算的计数 —— 返回 `(算数, 提示)`。

    「八宫起八七宫七，间神起一数不过；顺行数至太乙前，得算之数是其源。」

    - 起点在**正神**：以该宫宫号起算
    - 起点在**间辰**：以 1 起算
    - 此后沿十六神环顺行，**只累加八正宫的宫号**，间神跳过，
      遇到太乙所在宫即止（该宫不计）
    - 起点与太乙**同宫**：同神者算数取本宫数，不同神者取 1

    最后一条是各家表述最不一致的地方，命中时会额外给出一条提示，
    请人工核对而不是直接采信（见 `UNCERTAINTIES`）。
    """
    if start_pos not in RING_INDEX:
        raise InvalidInputError(f"起点必须是十六神之一，得到 {start_pos!r}")
    if taiyi_palace not in PALACE_GUA or taiyi_palace == 5:
        raise InvalidInputError(f"太乙宫号必须是八宫之一（不居五），得到 {taiyi_palace!r}")

    warn: list[str] = []
    if palace_of_pos(start_pos) == taiyi_palace:
        if start_pos in SHEN_PALACE:
            warn.append(
                f"起点「{start_pos}」与太乙同宫同神，算数取本宫数 {taiyi_palace}"
            )
            return taiyi_palace, tuple(warn)
        warn.append(
            f"起点「{start_pos}」与太乙同宫而不同神，算数取 1 —— "
            "间神归宫与「同宫不同神」的取值各家表述不一，请人工核对"
        )
        return 1, tuple(warn)

    total = SHEN_PALACE[start_pos] if start_pos in SHEN_PALACE else 1
    for step in range(1, len(SHISEN_RING)):
        pos = SHISEN_RING[(RING_INDEX[start_pos] + step) % len(SHISEN_RING)]
        pal = SHEN_PALACE.get(pos)
        if pal is None:
            continue
        if pal == taiyi_palace:
            break
        total += pal
    return total, tuple(warn)


def jiang_palace_of(suan: int) -> int:
    """大将落宫 —— 「若也自一至于九，随得便为诸将首；十算仍将九去之」。

    即取算数的个位数；算数为 10 的整数倍（个位为 0）时改取「除以 9 的余数」。
    余数也为 0（算数 = 90）时取 9。

    🔴 个位为 0 时**不能直接取 0**，也不能取 10 / 20 / 30 / 40 本身 ——
    它们都不是九宫里的宫号，会得到一张「大将没有落宫」的盘。
    """
    if suan <= 0:
        raise InvalidInputError(f"算数必须为正，得到 {suan}")
    last = suan % 10
    if last != 0:
        return last
    return suan % 9 or 9


def canjiang_palace_of(jiang_palace: int) -> int:
    """参将落宫 —— 「三因大将满十去」：大将宫数 × 3，取个位数。

    大将 7 宫 → 21 → 参将 1 宫；大将 3 宫 → 9 → 参将 9 宫。
    """
    if not 1 <= jiang_palace <= 9:
        raise InvalidInputError(f"大将宫号必须在 1..9，得到 {jiang_palace!r}")
    return jiang_palace_of(jiang_palace * 3)


def chang_duan_of(suan: int) -> str:
    """数之长短 —— 11 以上为「长」，9 以下为「短」，10 归「中」。"""
    if suan >= CHANGDUAN_LONG_MIN:
        return "长"
    if suan <= CHANGDUAN_SHORT_MAX:
        return "短"
    return "中"


def san_cai_of(suan: int) -> tuple[str, ...]:
    """天地人三才之缺 —— 返回缺失项，三者皆备则为空元组。

    「算中无十」→ 无天（算数不足 10，没有十位）；「算中无五」→ 无地；
    「算中无一」→ 无人。后两条看的是**数里有没有这个字**，
    不是十位或个位是不是它 —— 15 与 51 在两种读法下结论不同。
    """
    missing: list[str] = []
    if suan < SANCAI_TENS_LIMIT:
        missing.append("无天")
    text = str(suan)
    for digit, label in SANCAI_DIGIT_RULE.items():
        if digit not in text:
            missing.append(label)
    return tuple(missing)


@dataclass(frozen=True)
class SanSuan:
    """一个算（主 / 客 / 定）及其派生。"""

    name: str
    source_label: str
    source_pos: str
    source_palace: int
    value: int
    da_jiang: int
    can_jiang: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_label": self.source_label,
            "source_pos": self.source_pos,
            "source_name": SHEN_NAME[self.source_pos],
            "source_palace": self.source_palace,
            "source_palace_gua": PALACE_GUA[self.source_palace],
            "value": self.value,
            "length": chang_duan_of(self.value),
            "san_cai": list(san_cai_of(self.value)),
            "he_class": HESHU_CLASS.get(self.value),
            "gu_class": GUSHU_CLASS.get(self.value),
            "da_jiang": self.da_jiang,
            "da_jiang_gua": PALACE_GUA[self.da_jiang],
            "can_jiang": self.can_jiang,
            "can_jiang_gua": PALACE_GUA[self.can_jiang],
        }


def _sansuan(name: str, label: str, pos: str, taiyi_palace: int) -> tuple[SanSuan, tuple[str, ...]]:
    value, warn = suan_of(pos, taiyi_palace)
    da = jiang_palace_of(value)
    return (
        SanSuan(
            name=name,
            source_label=label,
            source_pos=pos,
            source_palace=palace_of_pos(pos),
            value=value,
            da_jiang=da,
            can_jiang=canjiang_palace_of(da),
        ),
        warn,
    )


# --------------------------------------------------------------------------
# 五、值事八门
# --------------------------------------------------------------------------


def zhishi_men_of(jiyan: int) -> str:
    """值事八门 —— 开门为始，三十年一换，二百四十年一周。

    `k = 积年 − 1` 为 0 时是开门值事；1984 年落在生门（已作锚点）。
    """
    if jiyan < 1:
        raise InvalidInputError(f"积年必须为正，得到 {jiyan}")
    idx = ((jiyan - 1) % BAMEN_CYCLE_YEARS) // BAMEN_SWITCH_YEARS
    return BAMEN_ORDER[idx]


def bamen_layout(taiyi_palace: int, zhishi: str) -> tuple[tuple[int, str], ...]:
    """布八门 —— 「常以开门加太乙，各门临处有凶吉」。

    自值事门起，沿九宫**顺时针环**依次落宫（乾→坎→艮→震→巽→离→坤→兑）。
    八门的轮转次序与其本位方位次序一致（开门本位居乾、休门居坎……），
    所以两张表可以共用同一个环 —— 若哪天有人只改了其中一张，
    测试会因「门序与宫序不再同步」而失败。

    ⚠️ 另一读法是把「常以开门加太乙」解为**开门永远落太乙宫**，
    与值事门无关。两种读法只在值事门非开门时不同，已登记分歧。
    """
    if taiyi_palace not in PALACE_CLOCKWISE_INDEX:
        raise InvalidInputError(f"太乙宫号必须在八宫之内，得到 {taiyi_palace!r}")
    if zhishi not in BAMEN_ORDER:
        raise InvalidInputError(f"值事门必须是八门之一，得到 {zhishi!r}")
    start = PALACE_CLOCKWISE_INDEX[taiyi_palace]
    z0 = BAMEN_ORDER.index(zhishi)
    return tuple(
        (
            PALACE_CLOCKWISE[(start + i) % 8],
            BAMEN_ORDER[(z0 + i) % 8],
        )
        for i in range(8)
    )


# --------------------------------------------------------------------------
# 六、主入口
# --------------------------------------------------------------------------


def _pos_info(pos: str) -> dict[str, Any]:
    """把一个十六神位展开成可展示的结构（两个目共用）。"""
    pal = palace_of_pos(pos)
    return {
        "pos": pos,
        "name": SHEN_NAME[pos],
        "palace": pal,
        "gua": PALACE_GUA[pal],
        "direction": PALACE_DIRECTION[pal],
        "is_zheng": pos in SHEN_PALACE,
    }


@dataclass(frozen=True)
class TaiyiChart:
    """一张太乙年局（岁计）。"""

    year: int
    year_ganzhi: str
    jiyan: int
    epoch: Epoch
    tai_sui: str
    he_shen: str
    taiyi_palace: int
    ru_gong_year: int
    taiyi_li: str
    wenchang_pos: str
    jishen_zhi: str
    shiji_pos: str
    dingmu_pos: str
    sansuan: tuple[SanSuan, ...]
    zhishi_men: str
    bamen: tuple[tuple[int, str], ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    school: str = "default"
    uncertainties: tuple[str, ...] = field(default_factory=tuple)

    def suan(self, name: str) -> SanSuan:
        for s in self.sansuan:
            if s.name == name:
                return s
        raise InvalidInputError(f"算名必须是 主算 / 客算 / 定算 之一，得到 {name!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "year_ganzhi": self.year_ganzhi,
            "jiyan": self.jiyan,
            "school": self.school,
            "school_name": SCHOOLS[self.school]["name"],
            "jiyan_base": SCHOOLS[self.school]["jiyan_base"],
            "epoch": self.epoch.to_dict(),
            "tai_sui": self.tai_sui,
            "he_shen": self.he_shen,
            "taiyi": {
                "palace": self.taiyi_palace,
                "gua": PALACE_GUA[self.taiyi_palace],
                "direction": PALACE_DIRECTION[self.taiyi_palace],
                "yinyang": PALACE_YINYANG[self.taiyi_palace],
                "ru_gong_year": self.ru_gong_year,
                "li": self.taiyi_li,
            },
            "wenchang": _pos_info(self.wenchang_pos),
            "jishen": {"zhi": self.jishen_zhi},
            "shiji": _pos_info(self.shiji_pos),
            "dingmu": _pos_info(self.dingmu_pos),
            "sansuan": [s.to_dict() for s in self.sansuan],
            "bamen": {
                "zhishi": self.zhishi_men,
                "zhishi_jixiong": BAMEN_JIXIONG[self.zhishi_men],
                "layout": [
                    {
                        "palace": p,
                        "gua": PALACE_GUA[p],
                        "door": d,
                        "jixiong": BAMEN_JIXIONG[d],
                    }
                    for p, d in self.bamen
                ],
            },
            "warnings": list(self.warnings),
            "uncertainties": list(self.uncertainties),
        }


def cast_taiyi(year: int, school: str = "default") -> TaiyiChart:
    """排一张太乙年局（岁计）。

    `year` 是公元年份（整数）。年局**只按年**定位，不需要月日 ——
    与六壬「必须给到时辰」刚好相反，因为太乙年局的最小单位就是年。
    （太乙另有月局、日局、时局，本版未实现。）

    返回结构见 `TaiyiChart.to_dict()`。全部为确定性结果：
    不含随机数、不调用语言模型（RULE-001）。
    """
    if school not in SCHOOLS:
        raise SchoolNotFoundError(
            f"未知的太乙流派 {school!r}；可选：{sorted(SCHOOLS)}"
        )

    jiyan = jiyan_of(year, SCHOOLS[school]["jiyan_base"])
    epoch = epoch_of(jiyan)
    year_gz = year_ganzhi_of(year)
    tai_sui = year_gz[1]

    taiyi_palace, ru_gong_year = taiyi_palace_of(jiyan)
    wenchang = wenchang_of(jiyan)
    jishen = jishen_of(tai_sui)
    shiji = shiji_of(wenchang, jishen)
    dingmu = dingmu_of(wenchang, tai_sui)

    warn: list[str] = []
    san_list: list[SanSuan] = []
    for name, label, pos in (
        ("主算", "文昌天目", wenchang),
        ("客算", "始击客目", shiji),
        ("定算", "定目", dingmu),
    ):
        s, w = _sansuan(name, label, pos, taiyi_palace)
        san_list.append(s)
        warn.extend(w)

    zhishi = zhishi_men_of(jiyan)

    return TaiyiChart(
        year=year,
        year_ganzhi=year_gz,
        jiyan=jiyan,
        epoch=epoch,
        tai_sui=tai_sui,
        he_shen=LIUHE[tai_sui],
        taiyi_palace=taiyi_palace,
        ru_gong_year=ru_gong_year,
        taiyi_li=LI_SANCAI[ru_gong_year],
        wenchang_pos=wenchang,
        jishen_zhi=jishen,
        shiji_pos=shiji,
        dingmu_pos=dingmu,
        sansuan=tuple(san_list),
        zhishi_men=zhishi,
        bamen=bamen_layout(taiyi_palace, zhishi),
        warnings=tuple(warn),
        school=school,
        uncertainties=UNCERTAINTIES,
    )


__all__ = [
    "Epoch",
    "SanSuan",
    "TaiyiChart",
    "bamen_layout",
    "canjiang_palace_of",
    "cast_taiyi",
    "chang_duan_of",
    "dingmu_of",
    "epoch_of",
    "jiang_palace_of",
    "jishen_of",
    "jiyan_of",
    "palace_of_pos",
    "san_cai_of",
    "shiji_of",
    "suan_of",
    "taiyi_palace_of",
    "wenchang_of",
    "year_ganzhi_of",
    "zhishi_men_of",
]
