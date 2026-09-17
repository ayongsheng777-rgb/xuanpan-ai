"""奇门遁甲 —— 定局与排盘。

排盘链路（每一步都是确定性计算，禁 LLM 介入 —— RULE-001）：

    时柱 ──┬─→ 旬首（六甲）──→ 值符仪 ──→ 值符宫 ──┬─→ 值符星
           │                                        └─→ 值使门
    节气 ──→ 三元 → 局数 ──→ 地盘（三奇六仪）
                              └─→ 天盘（沿环转动 steps）──→ 九星（同步）
           └─→ 八门（按旬首至时支步数转动）
           └─→ 八神（自值符落宫起，阳顺阴逆）

**流派处理（RULE-006）**：定局取「拆补法」为主流默认。
置闰法（超神接气）未实现，属**显式未覆盖项**，在 `uncertainties` 中声明 ——
宁可告诉用户「本版没考虑什么」，也不装作已经完备（RULE-008）。

**与古籍的可对照锚点**（见 `tests/test_qimen.py`）：
- 地盘布局：阳遁 1 局 = 坎1戊 / 坤2己 / 震3庚 / 巽4辛 / 中5壬 / 乾6癸 / 兑7丁 / 艮8丙 / 离9乙
- 地盘布局：阴遁 9 局 = 离9戊 / 艮8己 / 兑7庚 / 乾6辛 / 中5壬 / 巽4癸 / 震3丁 / 坤2丙 / 坎1乙
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ..constants import DIZHI, TIANGAN, jiazi_index
from ..constants import xun_kong_of as _shared_xun_kong
from ..constants import yima_of as _shared_yima
from ..exceptions import InvalidInputError
from .constants import (
    BAMEN_BY_GONG,
    BAMEN_JIXIONG,
    BASHEN_ORDER,
    CENTER_HOST,
    CENTER_PALACE,
    GONG_DIRECTION,
    GONG_ELEMENT,
    GONG_GUA,
    JIUXING_BY_GONG,
    JIUXING_JIXIONG,
    Qiyi_ORDER,
    RING_ORDER,
    is_yang_dun,
    jushu_of,
)

#: 支持的定局流派
SCHOOLS: dict[str, dict[str, str]] = {
    "chaibu": {
        "id": "chaibu",
        "name": "拆补法",
        "note": "以节气交节时刻为严格分界，节后 1-5 天为上元、6-10 中元、11-15 下元",
    },
}

YUAN_LABEL: tuple[str, str, str] = ("上元", "中元", "下元")

#: 内核**显式未覆盖项**。提为模块常量而不是写在 `cast_qimen` 里，
#: 是为了让 HTTP 的 `/qimen/meta` 与排盘结果**共用同一份文案** ——
#: 两处各写一份的话，改了内核忘了接口，界面就会少报一项未覆盖项。
UNCERTAINTIES: tuple[str, ...] = (
    "定局取拆补法；置闰法（超神接气）本版未实现，节气交界附近局数可能与置闰派不同",
    "三元起算取「交节当日算第 1 天」（自然日），与按满 24 小时计的口径略有差异",
    "八神名目取「白虎 / 玄武」，另有「勾陈 / 朱雀」一派",
    "未做真太阳时校正：传入时刻按本地区时直接使用",
)


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Dingju:
    """定局结果 —— 排盘的第一块地基。"""

    solar_dt: datetime
    jieqi: str                 # 当前所处节气（前一个节气）
    jieqi_time: datetime       # 该节气交节时刻
    days_after_jieqi: int      # 节后天数（交节当日算第 1 天）
    yuan: int                  # 1=上元 2=中元 3=下元
    yuan_label: str
    yang_dun: bool
    jushu: int                 # 1~9

    @property
    def dun_name(self) -> str:
        return "阳遁" if self.yang_dun else "阴遁"

    @property
    def jushu_label(self) -> str:
        """如「阴遁六局」—— 给界面直接展示的完整定局标签。"""
        cn = "一二三四五六七八九"
        return f"{self.dun_name}{cn[self.jushu - 1]}局"

    def to_dict(self) -> dict[str, Any]:
        return {
            "solar_datetime": self.solar_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "jieqi": self.jieqi,
            "jieqi_time": self.jieqi_time.strftime("%Y-%m-%d %H:%M:%S"),
            "days_after_jieqi": self.days_after_jieqi,
            "yuan": self.yuan,
            "yuan_label": self.yuan_label,
            "yang_dun": self.yang_dun,
            "dun_name": self.dun_name,
            "jushu": self.jushu,
            "jushu_label": self.jushu_label,
        }


@dataclass(frozen=True)
class QimenPalace:
    """一个宫位的完整盘面信息。"""

    gong: int
    gua: str
    direction: str
    element: str
    di_gan: str | None = None          # 地盘干（三奇六仪）
    tian_gan: str | None = None        # 天盘干
    star: str | None = None            # 九星
    door: str | None = None            # 八门
    god: str | None = None             # 八神
    is_xun_kong: bool = False          # 是否落旬空
    is_yima: bool = False              # 是否落驿马

    def to_dict(self) -> dict[str, Any]:
        return {
            "gong": self.gong,
            "gua": self.gua,
            "direction": self.direction,
            "element": self.element,
            "di_gan": self.di_gan,
            "tian_gan": self.tian_gan,
            "star": self.star,
            "star_jixiong": JIUXING_JIXIONG.get(self.star or "", None),
            "door": self.door,
            "door_jixiong": BAMEN_JIXIONG.get(self.door or "", None),
            "god": self.god,
            "is_xun_kong": self.is_xun_kong,
            "is_yima": self.is_yima,
        }


@dataclass(frozen=True)
class QimenChart:
    """奇门盘 —— 聚合结果。"""

    dingju: Dingju
    pillars: dict[str, str]
    xunshou: str                # 旬首（六甲），如「甲子」
    zhifu_yi: str               # 值符所依之仪（甲子→戊）
    zhifu_gong: int             # 值符宫
    zhifu_star: str             # 值符星
    zhishi_door: str            # 值使门
    zhishi_gong: int            # 值使落宫
    zhifu_gong_now: int         # 天盘值符当前落宫（= 时干落宫）
    palaces: tuple[QimenPalace, ...]
    xun_kong: tuple[str, ...]
    yima: str
    school: str
    uncertainties: tuple[str, ...] = field(default_factory=tuple)

    def palace(self, gong: int) -> QimenPalace:
        """按宫序取宫位。"""
        for p in self.palaces:
            if p.gong == gong:
                return p
        raise InvalidInputError(f"宫序必须在 1~9，得到 {gong!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "dingju": self.dingju.to_dict(),
            "pillars": dict(self.pillars),
            "xunshou": self.xunshou,
            "zhifu_yi": self.zhifu_yi,
            "zhifu_gong": self.zhifu_gong,
            "zhifu_star": self.zhifu_star,
            "zhishi_door": self.zhishi_door,
            "zhishi_gong": self.zhishi_gong,
            "zhifu_gong_now": self.zhifu_gong_now,
            "xun_kong": list(self.xun_kong),
            "yima": self.yima,
            "palaces": [p.to_dict() for p in self.palaces],
            "school": self.school,
            "school_name": SCHOOLS[self.school]["name"],
            "uncertainties": list(self.uncertainties),
        }


# --------------------------------------------------------------------------
# 定局
# --------------------------------------------------------------------------


def resolve_dingju(dt: datetime, school: str = "chaibu") -> Dingju:
    """定局：由公历时刻定出节气、三元、阴阳遁与局数。

    **拆补法**：以交节时刻为严格分界，从交节日算起
    第 1-5 天为上元、第 6-10 天为中元、第 11-15 天为下元。

    注意这里用**自然日**（交节当日算第 1 天）而非「满 24 小时」，
    属流派口径，已记入 `uncertainties`。
    """
    from lunar_python import Solar

    if school not in SCHOOLS:
        from ..exceptions import SchoolNotFoundError

        raise SchoolNotFoundError(f"未知奇门定局流派：{school!r}")

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()

    prev = lunar.getPrevJieQi()
    if prev is None:  # pragma: no cover - 库在极端年份才可能返回 None
        raise InvalidInputError("无法确定当前所处节气")

    jieqi = prev.getName()
    jieqi_time = datetime(
        prev.getSolar().getYear(),
        prev.getSolar().getMonth(),
        prev.getSolar().getDay(),
        prev.getSolar().getHour(),
        prev.getSolar().getMinute(),
        prev.getSolar().getSecond(),
    )

    days = (dt.date() - jieqi_time.date()).days + 1
    if days <= 5:
        yuan = 1
    elif days <= 10:
        yuan = 2
    else:
        yuan = 3

    yang = is_yang_dun(jieqi)

    return Dingju(
        solar_dt=dt,
        jieqi=jieqi,
        jieqi_time=jieqi_time,
        days_after_jieqi=days,
        yuan=yuan,
        yuan_label=YUAN_LABEL[yuan - 1],
        yang_dun=yang,
        jushu=jushu_of(jieqi, yuan),
    )


# --------------------------------------------------------------------------
# 地盘 / 天盘
# --------------------------------------------------------------------------


def build_dipan(jushu: int, yang_dun: bool) -> dict[int, str]:
    """地盘三奇六仪。

    戊从**局数宫**起，按九宫**数字顺序**布六仪三奇（戊己庚辛壬癸丁丙乙），
    阳遁顺行、阴遁逆行。甲隐于六仪之下，故盘面无「甲」。

    >>> build_dipan(1, True)[1], build_dipan(1, True)[9]
    ('戊', '乙')
    >>> build_dipan(9, False)[9], build_dipan(9, False)[1]
    ('戊', '乙')
    """
    if jushu not in range(1, 10):
        raise InvalidInputError(f"局数必须在 1~9，得到 {jushu!r}")

    step = 1 if yang_dun else -1
    pan: dict[int, str] = {}
    gong = jushu
    for gan in Qiyi_ORDER:
        pan[gong] = gan
        gong = (gong - 1 + step) % 9 + 1
    return pan


def _ring_index(gong: int) -> int:
    """宫序 -> 外环下标。中五宫寄坤二宫。"""
    if gong == CENTER_PALACE:
        gong = CENTER_HOST
    return RING_ORDER.index(gong)


def _gong_of_gan(dipan: dict[int, str], gan: str, xunshou_yi: str) -> int:
    """找某天干在地盘上的宫位。

    **甲不出现在地盘上**（隐于六仪之下），故时干为甲时，
    其落宫即旬首之仪所在宫 —— 这也是「甲时天盘伏吟」的由来。
    """
    if gan == "甲":
        for gong, g in dipan.items():
            if g == xunshou_yi:
                return gong
        raise InvalidInputError("地盘缺少旬首之仪，无法定位甲")  # pragma: no cover
    for gong, g in dipan.items():
        if g == gan:
            return gong
    raise InvalidInputError(f"地盘上没有天干 {gan!r}")


def xunshou_of(ganzhi: str) -> str:
    """干支 -> 所属旬首（六甲）。

    每旬 10 个干支，旬首即该旬的第一个甲日。地支步长 10 在 12 支上循环，
    故旬首地支索引 = `(旬序 * 10) % 12`（不能用 `旬序 * 2` —— 甲申、甲午
    这两个旬会算错）。

    >>> xunshou_of("甲子"), xunshou_of("庚午"), xunshou_of("癸酉")
    ('甲子', '甲子', '甲子')
    >>> xunshou_of("乙丑"), xunshou_of("甲戌"), xunshou_of("甲申")
    ('甲子', '甲戌', '甲申')
    >>> xunshou_of("癸亥")
    '甲寅'
    """
    idx = jiazi_index(ganzhi)
    return f"甲{DIZHI[(idx // 10) * 10 % 12]}"


def xun_kong_of(ganzhi: str) -> tuple[str, ...]:
    """干支 -> 旬空二支。

    实现在 `fortune_core.constants.xun_kong_of` —— 六爻、奇门、六壬都要用它，
    三处各写一份就会出现「同一个日柱、三个术式算出三个旬空」。
    本函数只作为本包的稳定入口保留。

    >>> xun_kong_of("甲子")
    ('戌', '亥')
    >>> xun_kong_of("庚午")
    ('戌', '亥')
    """
    return _shared_xun_kong(ganzhi)


def yima_of(zhi: str) -> str:
    """地支 -> 驿马地支（三合局长生的对冲）。

    实现在 `fortune_core.constants.yima_of`（按规律算，不查表）——
    六爻、奇门、六壬都要用它。本包保留 `YIMA_BY_SANHE` 只是作为**可读的对照数据**，
    取值与共享实现的一致性由 `tests/test_qimen.py` 钉住。

    >>> yima_of("子"), yima_of("午"), yima_of("酉"), yima_of("卯")
    ('寅', '申', '亥', '巳')
    """
    try:
        return _shared_yima(zhi)
    except ValueError as exc:  # 保持本包原有的异常类型
        raise InvalidInputError(f"未知地支：{zhi!r}") from exc


def _rotate(steps: int) -> list[int]:
    """沿外环前进 steps 步后的「源宫 -> 目标宫」映射。

    返回长度 8 的列表：`result[i]` = 外环第 i 宫的**地盘内容**将落到哪个宫。
    """
    return [RING_ORDER[(i + steps) % 8] for i in range(8)]


# --------------------------------------------------------------------------
# 聚合排盘
# --------------------------------------------------------------------------


def cast_qimen(
    dt: datetime,
    *,
    school: str = "chaibu",
    day_boundary: str = "zi",
) -> QimenChart:
    """排一个奇门盘。

    Args:
        dt: 公历时刻（**必须是本地时间**，区时换算由调用方负责）
        school: 定局流派，目前仅 `chaibu`（拆补法）
        day_boundary: 日界口径，`zi` 为晚子时算次日（通行），`early_zi` 为早子时算当日
    """
    from lunar_python import Solar

    dingju = resolve_dingju(dt, school=school)

    solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    lunar = solar.getLunar()

    exact = day_boundary == "zi"
    pillars = {
        "year": lunar.getYearInGanZhiExact() if exact else lunar.getYearInGanZhi(),
        "month": lunar.getMonthInGanZhiExact() if exact else lunar.getMonthInGanZhi(),
        "day": lunar.getDayInGanZhiExact() if exact else lunar.getDayInGanZhi(),
        "hour": lunar.getTimeInGanZhi(),
    }

    hour_ganzhi = pillars["hour"]
    day_ganzhi = pillars["day"]

    # ---- 旬首 / 值符 ----
    xunshou = xunshou_of(hour_ganzhi)
    from .constants import XUNSHOU_TO_YI

    zhifu_yi = XUNSHOU_TO_YI[xunshou]

    dipan = build_dipan(dingju.jushu, dingju.yang_dun)
    zhifu_gong = _gong_of_gan(dipan, "甲", zhifu_yi)  # 甲 -> 旬首之仪所在宫
    zhifu_star = JIUXING_BY_GONG[zhifu_gong]
    zhishi_door = BAMEN_BY_GONG.get(zhifu_gong) or BAMEN_BY_GONG[CENTER_HOST]

    # ---- 天盘：值符（旬首之仪）随时干 ----
    # 时干为甲时，甲隐于旬首仪 → 落宫 = 值符宫 → steps = 0（天盘伏吟）
    hg = hour_ganzhi[0]
    shigan_gong = _gong_of_gan(dipan, hg, zhifu_yi)
    steps = (_ring_index(shigan_gong) - _ring_index(zhifu_gong)) % 8
    mapping = _rotate(steps)

    tianpan: dict[int, str] = {}
    for i, src_gong in enumerate(RING_ORDER):
        tianpan[mapping[i]] = dipan[src_gong]
    # 中五宫天盘干寄坤二宫
    tianpan[CENTER_PALACE] = tianpan[CENTER_HOST]

    # ---- 值使门：从值符宫起，阳顺阴逆数至时支 ----
    xun_zhi = xunshou[1]
    hour_zhi = hour_ganzhi[1]
    delta = (DIZHI.index(hour_zhi) - DIZHI.index(xun_zhi)) % 12
    if not dingju.yang_dun:
        # 阴遁逆数：等价于从旬首支到时辰支的逆时针步数
        delta = (-delta) % 12
    zhishi_ri = _ring_index(zhifu_gong)
    zhishi_idx = (zhishi_ri + delta) % 8
    zhishi_gong = RING_ORDER[zhishi_idx]

    # 八门整体转动：值使门落于 zhishi_gong
    door_steps = (zhishi_idx - zhishi_ri) % 8
    door_map = _rotate(door_steps)
    doors: dict[int, str] = {}
    for i, src_gong in enumerate(RING_ORDER):
        if src_gong in BAMEN_BY_GONG:
            doors[door_map[i]] = BAMEN_BY_GONG[src_gong]

    # ---- 九星：与天盘同步转动（同 steps）----
    stars: dict[int, str] = {}
    for i, src_gong in enumerate(RING_ORDER):
        stars[mapping[i]] = JIUXING_BY_GONG[src_gong]

    # ---- 八神：值符神起于天盘值符落宫，阳顺阴逆 ----
    zhifu_gong_now = shigan_gong
    gods: dict[int, str] = {}
    base = _ring_index(zhifu_gong_now)
    for k, god in enumerate(BASHEN_ORDER):
        offset = k if dingju.yang_dun else -k
        gods[RING_ORDER[(base + offset) % 8]] = god

    # ---- 旬空 / 驿马 ----
    xun_kong = xun_kong_of(day_ganzhi)
    yima = yima_of(hour_zhi)

    palaces = []
    for gong in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        palaces.append(
            QimenPalace(
                gong=gong,
                gua=GONG_GUA[gong],
                direction=GONG_DIRECTION[gong],
                element=GONG_ELEMENT[gong],
                di_gan=dipan.get(gong),
                tian_gan=tianpan.get(gong),
                star="天禽" if gong == CENTER_PALACE else stars.get(gong),
                door=None if gong == CENTER_PALACE else doors.get(gong),
                god=None if gong == CENTER_PALACE else gods.get(gong),
                is_xun_kong=gong in {_gong_of_zhi(z) for z in xun_kong if _has_gong(z)},
                is_yima=_gong_of_zhi(yima) == gong if _has_gong(yima) else False,
            )
        )

    return QimenChart(
        dingju=dingju,
        pillars=pillars,
        xunshou=xunshou,
        zhifu_yi=zhifu_yi,
        zhifu_gong=zhifu_gong,
        zhifu_star=zhifu_star,
        zhishi_door=zhishi_door,
        zhishi_gong=zhishi_gong,
        zhifu_gong_now=zhifu_gong_now,
        palaces=tuple(palaces),
        xun_kong=xun_kong,
        yima=yima,
        school=school,
        uncertainties=UNCERTAINTIES,
    )


#: 地支 -> 后天八卦宫位（用于把旬空/驿马的地支映射到宫）
ZHI_TO_GONG: dict[str, int] = {
    "子": 1, "丑": 8, "寅": 8, "卯": 3, "辰": 4, "巳": 4,
    "午": 9, "未": 2, "申": 2, "酉": 7, "戌": 6, "亥": 6,
}


def _has_gong(zhi: str) -> bool:
    return zhi in ZHI_TO_GONG


def _gong_of_zhi(zhi: str) -> int:
    return ZHI_TO_GONG[zhi]


__all__ = [
    "SCHOOLS",
    "UNCERTAINTIES",
    "YUAN_LABEL",
    "ZHI_TO_GONG",
    "Dingju",
    "QimenPalace",
    "QimenChart",
    "build_dipan",
    "cast_qimen",
    "resolve_dingju",
    "xun_kong_of",
    "xunshou_of",
    "yima_of",
]
