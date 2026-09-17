"""太乙神数 —— 三式之三。

太乙与奇门、六壬并称三式，**主天时与国运**（奇门主地理方位，六壬主日常人事）。
三式里太乙的算法最繁，也最容易在「错了不报错」的地方翻车，故几处关键口径在此点明：

## 一、太乙宫号与洛书错位

太乙把宫位逆时针转了 45°，`乾 = 1 宫`、`巽 = 9 宫`，与奇门的后天洛书**逐宫错位**。
因此本包**不复用** `qimen` 的任何宫位表。把奇门的宫号搬来算，
太乙落宫、三算、六将宫位会整体偏移，而盘面照常输出。

## 二、积年从 1 起算

所有取模运算都要先减一（`k = 积年 − 1`）。不减一会让行宫、文昌、局数、
值事门**同时**偏一位；减一之后，「1984 值事生门」「2002 壬子元第 31 局」
「2044 甲子元第 1 局」三个互不相干的锚点才同时成立。

## 三、本版范围

**只做年局（岁计）。** 太乙另有月局、日局、时局，本版未实现。
年局按公元年份定位，不需要月日 —— 与六壬「必须给到时辰」恰好相反。

## 四、不下断语

三算的长短 / 和数 / 孤数 / 三才、八门吉凶、神将落宫，一律作为 FACT 返回。
格局（掩迫囚击关格）与「利主利客」的结论属上层解读，内核不产出（RULE-008）。

**已知未覆盖项**（详见 `constants.UNCERTAINTIES`，是唯一真源，此处不重列）。
"""

from .constants import (
    BAMEN_BENWEI,
    BAMEN_JIXIONG,
    BAMEN_ORDER,
    CYCLE_JI,
    CYCLE_WUYUAN_LIUJI,
    CYCLE_YUAN,
    GUSHU_CLASS,
    HESHU_CLASS,
    JIAN_SHEN,
    JIYAN_BASE,
    LIUHE,
    PALACE_CLOCKWISE,
    PALACE_DIRECTION,
    PALACE_FENYE,
    PALACE_GUA,
    PALACE_QI,
    PALACE_YINYANG,
    RING_INDEX,
    SANCAI_DIGIT_RULE,
    SANCAI_TENS_LIMIT,
    SCHOOLS,
    SHEN_NAME,
    SHEN_PALACE,
    SHISEN_16,
    SHISEN_RING,
    TAIYI_XUN_GONG,
    UNCERTAINTIES,
    WENCHANG_SEQ_YANG,
)
from .pan import (
    Epoch,
    SanSuan,
    TaiyiChart,
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

__all__ = [
    # 主入口
    "cast_taiyi",
    "TaiyiChart",
    # 环节函数
    "jiyan_of",
    "year_ganzhi_of",
    "epoch_of",
    "taiyi_palace_of",
    "wenchang_of",
    "jishen_of",
    "shiji_of",
    "dingmu_of",
    "palace_of_pos",
    "suan_of",
    "jiang_palace_of",
    "canjiang_palace_of",
    "chang_duan_of",
    "san_cai_of",
    "zhishi_men_of",
    "bamen_layout",
    # 数据结构
    "Epoch",
    "SanSuan",
    # 领域表
    "JIYAN_BASE",
    "SCHOOLS",
    "PALACE_GUA",
    "PALACE_DIRECTION",
    "PALACE_FENYE",
    "PALACE_QI",
    "PALACE_YINYANG",
    "PALACE_CLOCKWISE",
    "SHEN_NAME",
    "SHEN_PALACE",
    "SHISEN_16",
    "SHISEN_RING",
    "JIAN_SHEN",
    "RING_INDEX",
    "LIUHE",
    "TAIYI_XUN_GONG",
    "WENCHANG_SEQ_YANG",
    "BAMEN_ORDER",
    "BAMEN_BENWEI",
    "BAMEN_JIXIONG",
    "CYCLE_JI",
    "CYCLE_YUAN",
    "CYCLE_WUYUAN_LIUJI",
    "HESHU_CLASS",
    "GUSHU_CLASS",
    "SANCAI_TENS_LIMIT",
    "SANCAI_DIGIT_RULE",
    "UNCERTAINTIES",
]
