"""大六壬排盘 —— 天地盘、四课、三传、十二天将。

## 排盘链路

```
占时 ─┐
      ├─→ 月将（以中气换将）─→ 天地盘（月将加时）─→ 四课 ─→ 三传（九宗门）
日干支 ┘
                                        └─→ 十二天将（贵人起，顺逆布）
```

## 已验证的锚点

以下两条算例来自古籍排盘法（非本项目自造），本实现逐课吻合：

| 算例 | 四课 |
|---|---|
| 甲子日、午时、戌将 | `午甲 / 戌午 / 辰子 / 申辰` |
| 癸未日、戌时、巳将 | `申癸 / 卯申 / 寅未 / 酉寅` |

两条都覆盖了「日干寄宫 → 天盘取上神 → 再取一次」的完整四课推导，
所以天地盘公式 `天盘[地盘支] = 月将 + 地盘支 − 占时` 不是自证的。

## 本模块刻意不做的事

**不下吉凶断语。** 十二天将的吉凶属性、三传的五行生克都作为 FACT 返回，
但不合成"吉/凶"结论 —— 那是上层解读（`duangua.py` / AI 层）的职责，
内核只给事实（RULE-001 / RULE-008）。

## 九宗门的判定顺序

`伏吟 → 返吟 → 贼克 → 比用 → 涉害 → 遥克 → 昴星 → 别责 → 八专`

前两个必须最先判：它们是**天地盘整体结构**上的特例（月将与占时同位或相冲）。
若让通用的贼克法先把返吟接走，中传/末传会按「初传之上神」推，
而返吟要的是「初传之冲」—— 两种推法给出的三传完全不同，且都像模像样。
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from lunar_python import Solar

from ..constants import jiazi_index, xun_kong_of, yima_of
from ..exceptions import InvalidInputError
from .constants import (
    CHONG,
    DAYTIME_ZHI,
    DIZHI,
    GAN_ELEMENT,
    GUIREN,
    JIGONG,
    JIUZONGMEN,
    JIUZONGMEN_NOTE,
    KE,
    LIUHE,
    SANHE,
    SCHOOLS,
    SELF_XING,
    SHUN_GROUND,
    SIMENG,
    SIZHONG,
    TIANJIANG_JIXIONG,
    TIANJIANG_ORDER,
    UNCERTAINTIES,
    XING,
    YANG_ZHI,
    YUEJIANG_NAME,
    ZHI_ELEMENT,
    ZHI_INDEX,
    ZHONGQI_TO_YUEJIANG,
)


# --------------------------------------------------------------------------
# 数据结构
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Lesson:
    """一课。上神在天盘、下神在地盘；第一课的下神写作日干本身。"""

    index: int
    name: str
    upper: str
    lower: str
    lower_label: str
    is_ke: bool = False       # 是否为初传所出的一课
    ke_kind: str | None = None  # 下贼上 / 上克下

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "upper": self.upper,
            "lower": self.lower,
            "lower_label": self.lower_label,
            "upper_element": ZHI_ELEMENT[self.upper],
            "lower_element": _lower_element(self.lower, self.lower_label),
            "is_ke": self.is_ke,
            "ke_kind": self.ke_kind,
        }


@dataclass(frozen=True)
class Palace:
    """一宫：地盘支、其上的天盘支、以及该天盘支所带的天将。"""

    ground: str
    heaven: str
    general: str | None = None
    is_guiren_ground: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ground": self.ground,
            "heaven": self.heaven,
            "general": self.general,
            "general_jixiong": TIANJIANG_JIXIONG.get(self.general or ""),
            "is_guiren_ground": self.is_guiren_ground,
        }


@dataclass(frozen=True)
class Chuan:
    """三传中的一传。"""

    position: str     # 初传 / 中传 / 末传
    zhi: str
    general: str | None = None
    dun_gan: str | None = None   # 遁干（由日柱旬推出）

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "zhi": self.zhi,
            "general": self.general,
            "dun_gan": self.dun_gan,
            "element": ZHI_ELEMENT[self.zhi],
        }


@dataclass(frozen=True)
class LiurenChart:
    """一张六壬课。"""

    solar_datetime: _dt.datetime
    day_ganzhi: str
    hour_zhi: str
    month_general: str          # 月将支
    month_general_name: str     # 月将神将名
    zhongqi: str                # 换将所依的中气
    zhongqi_time: str           # 该中气的交气时刻
    guiren_zhi: str             # 所用贵人支
    guiren_is_day: bool         # 昼贵还是夜贵
    guiren_ground: str          # 贵人所在地盘宫
    shun: bool                  # 天将顺布还是逆布
    lessons: tuple[Lesson, ...]
    palaces: tuple[Palace, ...]
    chuan: tuple[Chuan, ...]
    chuanke: str                # 所用宗门
    chuanke_note: str
    xun_kong: tuple[str, ...]
    school: str = "default"
    uncertainties: tuple[str, ...] = field(default_factory=tuple)

    def palace(self, ground: str) -> Palace:
        for p in self.palaces:
            if p.ground == ground:
                return p
        raise InvalidInputError(f"地支必须在十二支之内，得到 {ground!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "solar_datetime": self.solar_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "day_ganzhi": self.day_ganzhi,
            "day_gan": self.day_ganzhi[0],
            "day_zhi": self.day_ganzhi[1],
            "hour_zhi": self.hour_zhi,
            "month_general": self.month_general,
            "month_general_name": self.month_general_name,
            "month_general_label": f"{self.month_general}将（{self.month_general_name}）",
            "zhongqi": self.zhongqi,
            "zhongqi_time": self.zhongqi_time,
            "guiren": {
                "zhi": self.guiren_zhi,
                "is_day": self.guiren_is_day,
                "kind": "昼贵" if self.guiren_is_day else "夜贵",
                "ground": self.guiren_ground,
                "shun": self.shun,
                "direction": "顺布" if self.shun else "逆布",
            },
            "lessons": [x.to_dict() for x in self.lessons],
            "palaces": [x.to_dict() for x in self.palaces],
            "chuan": [x.to_dict() for x in self.chuan],
            "chuanke": self.chuanke,
            "chuanke_note": self.chuanke_note,
            "xun_kong": list(self.xun_kong),
            "yima": yima_of(self.day_ganzhi[1]),
            "school": self.school,
            "school_name": SCHOOLS[self.school]["name"],
            "uncertainties": list(self.uncertainties),
        }


def _lower_element(lower: str, lower_label: str) -> str:
    """下神的五行 —— 第一课的下神是**日干**，要看干五行而不是寄宫支五行。

    这两者在这一课上恰好同五行（寄宫即禄位/冠带位，与日干同气），
    但**不能因此就用支五行糊过去**：一旦有人把寄宫表改错，
    用支五行会把错误一并吞掉，于是贼克判定静默偏移。
    """
    if lower_label in GAN_ELEMENT:
        return GAN_ELEMENT[lower_label]
    return ZHI_ELEMENT[lower]


# --------------------------------------------------------------------------
# 一、月将（以中气换将）
# --------------------------------------------------------------------------


def month_general_of(solar: Solar) -> tuple[str, str, _dt.datetime]:
    """求月将 —— 返回 `(月将支, 所依中气, 交气时刻)`。

    🔴 **换将以中气为界，不是节气。** 正月立春即建寅，但月将要到**雨水**
    才由子（神后）换成亥（登明）。用节气换将，会在每个月「节已到、气未到」
    的上半月系统性地取错月将，而排出来的盘看起来完全正常。

    🔴 **不能用 `getJieQiTable()` 的键名筛中气。** 该表的键名随基准日期滚动：
    表里只有 24 个中文名键，窗口外的相邻中气被存成 ASCII 别名
    （`DONG_ZHI` / `XIAO_HAN` / `YU_SHUI` …）。按中文名筛，会把这些别名整批跳过，
    于是「最近的中气」退回到窗口内更早的那一个 ——
    **实测 2025-12-22 查到的是小雪而不是冬至，月将整整错一个月**，
    而那张盘上一切正常。连带的错是全年各月的窗口边缘各错一次，不是孤立个案。

    改用 `getPrevQi()`：它就是「逆推第一个气令」，且内部会把别名归一成中文名，
    窗口滚动再也不会影响结果。
    """
    lunar = solar.getLunar()
    jq = lunar.getPrevQi()
    if jq is None:
        raise InvalidInputError(
            "无法确定最近的中气 —— 时刻可能超出了节气数据覆盖范围"
        )
    name = jq.getName()
    if name not in ZHONGQI_TO_YUEJIANG:  # pragma: no cover - 库保证是十二气令之一
        raise InvalidInputError(f"{name!r} 不是十二中气之一，无法换将")

    s = jq.getSolar()
    moment = _dt.datetime(
        s.getYear(), s.getMonth(), s.getDay(),
        s.getHour(), s.getMinute(), s.getSecond(),
    )
    return ZHONGQI_TO_YUEJIANG[name], name, moment


# --------------------------------------------------------------------------
# 二、天地盘
# --------------------------------------------------------------------------


def heaven_plate(month_general: str, hour_zhi: str) -> dict[str, str]:
    """天盘 —— 「月将加时」。

    把月将放在占时之上，其余十一支按序跟随。等价于

        天盘[地盘支] = 月将 + (地盘支 − 占时)   （对 12 取模）

    返回 `{地盘支: 天盘支}`，十二项齐全。

    >>> heaven_plate("戌", "午")["寅"]
    '午'
    >>> heaven_plate("戌", "午")["子"]
    '辰'
    """
    if month_general not in ZHI_INDEX or hour_zhi not in ZHI_INDEX:
        raise InvalidInputError(f"月将与占时都必须是地支，得到 {month_general!r} / {hour_zhi!r}")
    shift = ZHI_INDEX[month_general] - ZHI_INDEX[hour_zhi]
    return {g: DIZHI[(ZHI_INDEX[g] + shift) % 12] for g in DIZHI}


def ground_of(tian: dict[str, str], heaven: str) -> str:
    """天盘支 -> 它**脚下的地盘宫**（`heaven_plate` 的反函数）。

    凡是需要「某个天盘支落在哪个地盘宫」的地方都走这里，不要在别处重解一遍方程。
    天盘是十二支的双射，反查不可能认错相位；而手写反解一旦把
    「月将加时」的符号写反，得到的是**另一个合法地支** ——
    布将顺逆会跟着翻转、整盘天将错位，盘面却毫无异常。
    （本模块的 `generals_of` 初版就是这样错了一天将。）

    >>> ground_of(heaven_plate("戌", "午"), "丑")
    '酉'
    >>> ground_of(heaven_plate("戌", "午"), "午")
    '寅'
    """
    if heaven not in ZHI_INDEX:
        raise InvalidInputError(f"地支必须是十二支之一，得到 {heaven!r}")
    for g in DIZHI:
        if tian[g] == heaven:
            return g
    raise InvalidInputError("天盘不是十二支的完整映射，无法反查地盘")  # pragma: no cover


# --------------------------------------------------------------------------
# 三、四课
# --------------------------------------------------------------------------


def four_lessons(day_gan: str, day_zhi: str, tian: dict[str, str]) -> tuple[Lesson, ...]:
    """四课。

    - 第一课：以日干**寄宫**为下神，取天盘上神（下神写作日干本身）
    - 第二课：以第一课上神为下神，再取天盘上神
    - 第三课：以**日支**为下神，取天盘上神
    - 第四课：以第三课上神为下神，再取天盘上神

    第二、四课为什么是「再取一次」：它们表示的是同一处阴阳两面 ——
    第一、三课取的是「显现」的一面，第二、四课取的是它**之上**再叠一层，
    传统称「干阴」「支阴」。这一步抄漏了，四课会少一半，而三传照样能取出来。

    >>> lessons = four_lessons("甲", "子", heaven_plate("戌", "午"))
    >>> [(x.upper, x.lower_label) for x in lessons]
    [('午', '甲'), ('戌', '午'), ('辰', '子'), ('申', '辰')]
    """
    if day_gan not in JIGONG:
        raise InvalidInputError(f"日干必须是十天干之一，得到 {day_gan!r}")
    if day_zhi not in ZHI_INDEX:
        raise InvalidInputError(f"日支必须是十二支之一，得到 {day_zhi!r}")

    ji = JIGONG[day_gan]
    up1 = tian[ji]
    up2 = tian[up1]
    up3 = tian[day_zhi]
    up4 = tian[up3]

    rows = [
        (1, "第一课", up1, ji, day_gan),
        (2, "第二课", up2, up1, up1),
        (3, "第三课", up3, day_zhi, day_zhi),
        (4, "第四课", up4, up3, up3),
    ]
    return tuple(
        Lesson(index=i, name=n, upper=u, lower=lo, lower_label=lb)
        for i, n, u, lo, lb in rows
    )


# --------------------------------------------------------------------------
# 四、三传（九宗门）
# --------------------------------------------------------------------------


def _ke_relation(upper: str, lower_element: str) -> str | None:
    """上神与下神的关系：`下贼上` / `上克下` / 无克。"""
    up_el = ZHI_ELEMENT[upper]
    if KE[lower_element] == up_el:
        return "下贼上"
    if KE[up_el] == lower_element:
        return "上克下"
    return None


def _candidate_lessons(lessons: tuple[Lesson, ...], kind: str) -> list[Lesson]:
    """筛出满足某类克关系的课。

    克关系按**下神的五行**判：第一课的下神是日干（看干五行），
    其余课的下神是地支（看支五行）。
    """
    out: list[Lesson] = []
    for le in lessons:
        lower_el = _lower_element(le.lower, le.lower_label)
        if _ke_relation(le.upper, lower_el) == kind:
            out.append(le)
    return out


def _bi_yong(cands: list[Lesson], day_gan: str) -> list[Lesson]:
    """比用：取与日干**同阴阳**者。返回筛选后的候选（可能仍多于一个）。"""
    day_is_yang = day_gan in {"甲", "丙", "戊", "庚", "壬"}
    keep = [c for c in cands if (c.upper in YANG_ZHI) == day_is_yang]
    return keep or cands


def _she_hai(cands: list[Lesson], day_gan: str, day_zhi: str, tian: dict[str, str]) -> Lesson:
    """涉害（简化判读）：孟深仲浅季当休，复等则柔辰刚日宜。

    ⚠️ **本版是简化判读，已在 `uncertainties` 中声明。**
    完整涉害法要「由地盘涉归本家、数路逢受克之多寡」，
    各家对「深浅」的量化口径不一；本版取其**分档结论**：
    先看候选人所在地盘宫是否四孟（寅申巳亥），再退到四仲（子午卯酉），
    仍平则柔日取支上神、刚日取干上神。

    之所以仍要实现而不是直接报"未支持"：绝大多数课在比用一步就定下来了，
    走到涉害的是少数；给出一个**口径明确、可被替换**的结果，
    比抛异常让整个盘排不出来更可用（RULE-006 的同一精神）。
    """
    meng = [c for c in cands if c.lower in SIMENG]
    if len(meng) == 1:
        return meng[0]
    zhong = [c for c in cands if c.lower in SIZHONG]
    if not meng and len(zhong) == 1:
        return zhong[0]
    # 「复等」：柔日（阴日）取支上神，刚日（阳日）取干上神
    day_is_yang = day_gan in {"甲", "丙", "戊", "庚", "壬"}
    target_lower = day_gan if day_is_yang else day_zhi
    for c in cands:
        if c.lower_label == day_gan or c.lower == target_lower:
            return c
    return cands[0]


def _yao_ke(lessons: tuple[Lesson, ...], day_gan: str) -> list[Lesson]:
    """遥克候选：上神克日干（遥克）优先，其次日干克上神（蒿矢）。"""
    day_el = GAN_ELEMENT[day_gan]
    shen_ke_ri = [c for c in lessons if KE[ZHI_ELEMENT[c.upper]] == day_el]
    if shen_ke_ri:
        return shen_ke_ri
    return [c for c in lessons if KE[day_el] == ZHI_ELEMENT[c.upper]]


def _propagate(chu: str, tian: dict[str, str]) -> tuple[str, str]:
    """常法：初传之上神为中传，中传之上神为末传。"""
    zhong = tian[chu]
    mo = tian[zhong]
    return zhong, mo


def _he_gan(day_gan: str) -> str:
    """日干的六合之干（甲己合、乙庚合、丙辛合、丁壬合、戊癸合）。"""
    pairs = {"甲": "己", "己": "甲", "乙": "庚", "庚": "乙", "丙": "辛",
             "辛": "丙", "丁": "壬", "壬": "丁", "戊": "癸", "癸": "戊"}
    return pairs[day_gan]


def _sanhe_next(zhi: str) -> str:
    """三合局中紧接在 `zhi` 之后的那一支（别责「支前三合取」）。

    三合局为环状：巳→酉→丑→巳，亥→卯→未→亥，申→子→辰→申，寅→午→戌→寅。
    「支前」指**环上的下一位**，不是序数 +1 —— 序数 +1 在酉、丑、亥、未
    这四支上恰好也会得到同一结果，但在其余支上会错，所以必须按三合环走。
    """
    a, b, c = SANHE[zhi]
    if zhi == a:
        return b
    if zhi == b:
        return c
    return a


def san_chuan(
    lessons: tuple[Lesson, ...],
    day_gan: str,
    day_zhi: str,
    month_general: str,
    hour_zhi: str,
    tian: dict[str, str],
) -> tuple[tuple[str, str, str], str, str]:
    """九宗门取三传 —— 返回 `((初, 中, 末), 宗门名, 说明)`。"""
    ji = JIGONG[day_gan]

    # ---- 伏吟：月将与占时同支，天地盘重叠 ----
    if month_general == hour_zhi:
        return _chuan_fuyin(lessons, day_gan, day_zhi, tian, ji)

    # ---- 返吟：月将与占时相冲 ----
    if CHONG[month_general] == hour_zhi:
        return _chuan_fanyin(lessons, day_gan, day_zhi, tian, ji)

    # ---- 贼克 ----
    for kind in ("下贼上", "上克下"):
        cands = _candidate_lessons(lessons, kind)
        if not cands:
            continue
        if len(cands) == 1:
            chu = cands[0].upper
            zhong, mo = _propagate(chu, tian)
            return (chu, zhong, mo), "贼克", JIUZONGMEN_NOTE["贼克"]

        # ---- 比用 ----
        bi = _bi_yong(cands, day_gan)
        if len(bi) == 1:
            chu = bi[0].upper
            zhong, mo = _propagate(chu, tian)
            return (chu, zhong, mo), "比用", JIUZONGMEN_NOTE["比用"]

        # ---- 涉害 ----
        pick = _she_hai(bi, day_gan, day_zhi, tian)
        chu = pick.upper
        zhong, mo = _propagate(chu, tian)
        return (chu, zhong, mo), "涉害", JIUZONGMEN_NOTE["涉害"]

    # ---- 遥克 ----
    yao = _yao_ke(lessons, day_gan)
    if yao:
        if len(yao) > 1:
            yao = _bi_yong(yao, day_gan)
        chu = yao[0].upper
        zhong, mo = _propagate(chu, tian)
        return (chu, zhong, mo), "遥克", JIUZONGMEN_NOTE["遥克"]

    # ---- 八专：日干寄宫与日支同支（四课只有两课）----
    if ji == day_zhi:
        up1 = tian[ji]
        if day_gan in {"甲", "丙", "戊", "庚", "壬"}:
            # 刚日：干上神在天盘顺数三位
            chu = DIZHI[(ZHI_INDEX[up1] + 2) % 12]
        else:
            # 柔日：第四课上神在天盘逆数三位
            up4 = lessons[3].upper
            chu = DIZHI[(ZHI_INDEX[up4] - 2) % 12]
        return (chu, up1, up1), "八专", JIUZONGMEN_NOTE["八专"]

    # ---- 别责：四课不全（只有三课），无贼克无遥克 ----
    if len({(le.upper, le.lower) for le in lessons}) == 3:
        up1 = tian[ji]
        if day_gan in {"甲", "丙", "戊", "庚", "壬"}:
            # 刚日：日干六合之干，取其寄宫之上的天盘支
            chu = tian[JIGONG[_he_gan(day_gan)]]
        else:
            # 柔日：日支三合局中紧接日支之后的那一支，取其之上的天盘支
            chu = tian[_sanhe_next(day_zhi)]
        return (chu, up1, up1), "别责", JIUZONGMEN_NOTE["别责"]

    # ---- 昴星：四课全备、无上下克、无遥克 ----
    up1 = tian[ji]
    up3 = tian[day_zhi]
    if day_gan in {"甲", "丙", "戊", "庚", "壬"}:
        # 刚日（阳仰）：地盘酉之上神发用，中取支上神，末取干上神
        chu, zhong, mo = tian["酉"], up3, up1
    else:
        # 柔日（阴俯）：天盘酉之**下神**发用，中取干上神，末取支上神
        chu = ground_of(tian, "酉")
        zhong, mo = up1, up3
    return (chu, zhong, mo), "昴星", JIUZONGMEN_NOTE["昴星"]


def _xing_chain(first: str, day_gan: str, day_zhi: str, tian: dict[str, str]) -> tuple[str, str, str]:
    """伏吟的中末：迤逦刑之，遇自刑则改道。

    规则（口诀「若也自刑为发用，次传颠倒日辰并；次传更复自刑者，冲取末传不论刑」）：
    - 初传自刑（辰午酉亥）→ 中传取**支上神**，末传取中传所刑
    - 中传又自刑 → 末传取中传之**冲**
    - 否则常规：中传 = 刑(初传)，末传 = 刑(中传)
    """
    if first in SELF_XING:
        zhong = tian[JIGONG[day_gan]]  # 干上神
        mo = XING[zhong]
        if zhong in SELF_XING:
            mo = CHONG[zhong]
        return first, zhong, mo
    zhong = XING[first]
    mo = XING[zhong]
    if zhong in SELF_XING:
        mo = CHONG[zhong]
    return first, zhong, mo


def _chuan_fuyin(
    lessons: tuple[Lesson, ...],
    day_gan: str,
    day_zhi: str,
    tian: dict[str, str],
    ji: str,
) -> tuple[tuple[str, str, str], str, str]:
    """伏吟。有克依常法取用，无克则刚日取干上神、柔日取支上神，中末递刑。"""
    for kind in ("下贼上", "上克下"):
        cands = _candidate_lessons(lessons, kind)
        if cands:
            first = _bi_yong(cands, day_gan)[0].upper
            return _xing_chain(first, day_gan, day_zhi, tian), "伏吟", JIUZONGMEN_NOTE["伏吟"]

    day_is_yang = day_gan in {"甲", "丙", "戊", "庚", "壬"}
    first = tian[ji] if day_is_yang else tian[day_zhi]
    return _xing_chain(first, day_gan, day_zhi, tian), "伏吟", JIUZONGMEN_NOTE["伏吟"]


def _chuan_fanyin(
    lessons: tuple[Lesson, ...],
    day_gan: str,
    day_zhi: str,
    tian: dict[str, str],
    ji: str,
) -> tuple[tuple[str, str, str], str, str]:
    """返吟。有克依常法取用、中末递冲；无克取日支驿马发用。

    返吟只有六日无克：丁丑、己丑、辛丑、丁未、己未、辛未 ——
    这六日的干支自身与四课都构不成克，所以另走驿马一路。
    本实现不硬编码这六日，而是**先试贼克、试不出来再取驿马**：
    硬编码一张六日表，改天寄宫表动了它不会跟着动。
    """
    for kind in ("下贼上", "上克下"):
        cands = _candidate_lessons(lessons, kind)
        if cands:
            first = _bi_yong(cands, day_gan)[0].upper
            zhong = CHONG[first]
            mo = CHONG[zhong]
            return (first, zhong, mo), "返吟", JIUZONGMEN_NOTE["返吟"]

    chu = yima_of(day_zhi)
    zhong = tian[day_zhi]
    mo = tian[ji]
    return (chu, zhong, mo), "返吟", JIUZONGMEN_NOTE["返吟"]


# --------------------------------------------------------------------------
# 五、十二天将
# --------------------------------------------------------------------------


def generals_of(
    day_gan: str,
    hour_zhi: str,
    tian: dict[str, str],
) -> tuple[dict[str, str], str, str, bool]:
    """布十二天将 —— 返回 `({天盘支: 天将}, 贵人支, 贵人所在地盘宫, 是否顺布)`。

    1. 由日干取昼/夜贵人（占时卯~申为昼，官方的昼夜分界取"日出前/后"的常用口径）
    2. 贵人先落在**天盘**上，再由它**脚下的地盘宫**定顺逆
    3. 顺布时天将按支序递增依次配到天盘支上；逆布则递减

    🔴 第 2 步用**反查**，不用解方程。天盘是十二支的一个双射，反查不可能认错相位；
    而解方程一旦把「月将加时」的符号写反（或像本模块初版那样多减了一项时辰），
    得到的仍是另一个**合法地支** —— 顺逆随之翻转，十二天将整盘错位，
    而排出来的课看起来毫无异常。这一步没有"看起来差不多"可言。

    >>> mapping, gz, ground, shun = generals_of("甲", "午", heaven_plate("戌", "午"))
    >>> gz, ground, shun
    ('丑', '酉', False)
    >>> mapping["丑"], mapping["午"]
    ('贵人', '白虎')
    """
    if day_gan not in GUIREN:
        raise InvalidInputError(f"日干必须是十天干之一，得到 {day_gan!r}")
    is_day = hour_zhi in DAYTIME_ZHI
    guiren_zhi = GUIREN[day_gan][0 if is_day else 1]

    ground = ground_of(tian, guiren_zhi)
    shun = ground in SHUN_GROUND

    mapping: dict[str, str] = {}
    for i, general in enumerate(TIANJIANG_ORDER):
        step = i if shun else -i
        heaven = DIZHI[(ZHI_INDEX[guiren_zhi] + step) % 12]
        mapping[heaven] = general
    return mapping, guiren_zhi, ground, shun


# --------------------------------------------------------------------------
# 六、遁干
# --------------------------------------------------------------------------


def dun_gan_of(day_ganzhi: str, zhi: str) -> str | None:
    """三传遁干 —— 由日柱所在旬推出该支所配的天干，落旬空者返回 None。

    旬遁的原理：一旬十日，天干正好用满甲~癸一遍，地支则从旬首支起依序前进。
    所以某支的遁干 = 它在**本旬内**的偏移量（0~9 → 甲~癸）。

    偏移量 ≥ 10 的，正是这一旬的两个空亡之支 —— 它们在本旬里没有配到天干，
    所以返回 None 而不是硬凑一个。**这个 None 是有意义的领域信号**（旬空），
    上层拿它来标"空"，不是数据缺失。

    >>> dun_gan_of("甲子", "寅")   # 甲子旬：甲子乙丑丙寅…
    '丙'
    >>> dun_gan_of("甲子", "戌")   # 甲子旬空戌亥
    >>> dun_gan_of("甲戌", "子")   # 甲戌旬：甲戌乙亥丙子…
    '丙'
    """
    if zhi not in ZHI_INDEX:
        raise InvalidInputError(f"地支必须是十二支之一，得到 {zhi!r}")
    start = (jiazi_index(day_ganzhi) // 10) * 10
    offset = (DIZHI.index(zhi) - start % 12) % 12
    if offset >= 10:
        return None  # 旬空之支不配干
    return "甲乙丙丁戊己庚辛壬癸"[offset]


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------


def cast_liuren(when: _dt.datetime, school: str = "default") -> LiurenChart:
    """排一张大六壬课。

    `when` 必须含**时分**：六壬以时辰起课，只给日期排不出课
    （与奇门同理，「月将加时」里的「时」就是它）。

    返回结构见 `LiurenChart.to_dict()`。全部为确定性结果：
    不含随机数、不调用语言模型（RULE-001）。
    """
    if school not in SCHOOLS:
        from ..exceptions import SchoolNotFoundError

        raise SchoolNotFoundError(
            f"未知的六壬流派 {school!r}；可选：{sorted(SCHOOLS)}"
        )

    solar = Solar.fromYmdHms(
        when.year, when.month, when.day, when.hour, when.minute, when.second
    )
    lunar = solar.getLunar()
    day_ganzhi = lunar.getDayInGanZhi()
    day_gan, day_zhi = day_ganzhi[0], day_ganzhi[1]
    hour_zhi = lunar.getTimeZhi()

    month_general, zhongqi, zhongqi_dt = month_general_of(solar)
    tian = heaven_plate(month_general, hour_zhi)
    lessons = four_lessons(day_gan, day_zhi, tian)

    # 贵人支由 generals_of 唯一产出 —— 不在调用方再算一遍，
    # 否则昼夜判据一旦调整（比如改分界时刻），两处会给出不同的贵人
    zhijiang, guiren_zhi, guiren_ground, shun = generals_of(day_gan, hour_zhi, tian)

    (chu, zhong, mo), chuanke, note = san_chuan(
        lessons, day_gan, day_zhi, month_general, hour_zhi, tian
    )

    # 标出初传所出的一课（供界面高亮"三传从哪来"）
    marked: list[Lesson] = []
    for le in lessons:
        hit = le.upper == chu
        marked.append(
            Lesson(
                index=le.index, name=le.name, upper=le.upper, lower=le.lower,
                lower_label=le.lower_label, is_ke=hit,
                ke_kind=_ke_relation(le.upper, _lower_element(le.lower, le.lower_label)) if hit else None,
            )
        )

    palaces = tuple(
        Palace(
            ground=g,
            heaven=tian[g],
            general=zhijiang.get(tian[g]),
            is_guiren_ground=(g == guiren_ground),
        )
        for g in DIZHI
    )

    chuan = tuple(
        Chuan(position=pos, zhi=z, general=zhijiang.get(z), dun_gan=dun_gan_of(day_ganzhi, z))
        for pos, z in (("初传", chu), ("中传", zhong), ("末传", mo))
    )

    return LiurenChart(
        solar_datetime=when,
        day_ganzhi=day_ganzhi,
        hour_zhi=hour_zhi,
        month_general=month_general,
        month_general_name=YUEJIANG_NAME[month_general],
        zhongqi=zhongqi,
        zhongqi_time=zhongqi_dt.strftime("%Y-%m-%d %H:%M:%S"),
        guiren_zhi=guiren_zhi,
        guiren_is_day=hour_zhi in DAYTIME_ZHI,
        guiren_ground=guiren_ground,
        shun=shun,
        lessons=tuple(marked),
        palaces=palaces,
        chuan=chuan,
        chuanke=chuanke,
        chuanke_note=note,
        xun_kong=tuple(xun_kong_of(day_ganzhi)),
        school=school,
        uncertainties=UNCERTAINTIES,
    )


__all__ = [
    "Chuan",
    "Lesson",
    "LiurenChart",
    "Palace",
    "cast_liuren",
    "dun_gan_of",
    "four_lessons",
    "generals_of",
    "ground_of",
    "heaven_plate",
    "month_general_of",
    "san_chuan",
]
