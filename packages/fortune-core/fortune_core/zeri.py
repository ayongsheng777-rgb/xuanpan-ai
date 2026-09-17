"""择日决策 —— 从「查每日宜忌」升级为「给定事件反推吉日」。

`almanac.py` 解决的是「这一天宜什么、忌什么」（正向查询）；
本模块解决的是「我想嫁娶/开业/动土，未来半年哪天合适」（反向筛选）。

设计原则（对齐 RULE-001 / RULE-006 / RULE-008 / RULE-009）：

1. **不造历法** —— 每一日的宜忌、黄黑道、二十八宿、建除、冲煞全部来自
   `calculate_almanac()`（其底层是 `lunar-python`）。本模块只做「把已有的
   确定性事实按规则组合成筛选结果」，不自行推算任何历法值。

2. **事件词表必须来自真实数据** —— 规则表 `data/zeri_events.json` 中每个事件
   的 `yi`/`ji` 词目，都是 `lunar-python` 实际发出过的宜忌词（730 天实测）。
   **不得凭空造词**，否则会产出永不命中的死规则。校验脚本：
   `scripts/verify_zeri_table.py`。

3. **输出「分级」而非「断语」** —— 用「吉 / 次吉 / 平 / 不宜」这类分级词，
   并附 `reasons` 说明每条分数从何而来（宜项命中 +3、黄道 +2 …），
   不输出「大吉日」这种绝对化、无依据的结论。

4. **流派规则模块化 + 显式标注不确定性** —— 建除吉凶分档、各项权重、
   分级阈值全部放在规则表的 `schools` 段内，可整体替换；结果始终带
   `school` 与 `uncertainties`，不冒充唯一结论。

关于「否决（veto）」——本模块采用**忌优先**口径。经 730 天实测：
同一个词**从未同时出现在宜与忌中**（真冲突 0 例），故「忌命中事件词 → 不宜」
是无歧义的安全规则；跨词交叉（如「宜交易 + 忌开市」）按忌优先处理，
并在 `reasons` 中明示，不做静默取舍。
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from .almanac import AlmanacResult, calculate_almanac
from .constants import ZHI_SHENGXIAO
from .exceptions import DomainDataMissingError, InvalidInputError, SchoolNotFoundError

ZERI_TABLE_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "zeri_events.json"

# 单次筛选的日期跨度上限（约 10 年），防止误传超长区间导致长时间计算
MAX_RANGE_DAYS: Final[int] = 3660
DEFAULT_LIMIT: Final[int] = 10

GRADE_JI: Final[str] = "吉"
GRADE_CIJI: Final[str] = "次吉"
GRADE_PING: Final[str] = "平"
GRADE_BUXUAN: Final[str] = "不宜"

# 否决类别码（用于汇总 excluded_reasons，避免把可读文案当 key）
VETO_JI_HIT: Final[str] = "忌项命中"
VETO_ZHU_SHI: Final[str] = "诸事不宜"
VETO_YU_SHI: Final[str] = "馀事勿取"
VETO_PO_DAY: Final[str] = "破日"
VETO_CHONG: Final[str] = "生肖相冲"

WEEKDAY_LABELS: Final[tuple[str, ...]] = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

SHENGXIAO_SET: Final[frozenset[str]] = frozenset(ZHI_SHENGXIAO.values())


# ---------------------------------------------------------------------------
# 规则表加载
# ---------------------------------------------------------------------------


@lru_cache(maxsize=8)
def load_zeri_table(path: str | None = None) -> dict[str, Any]:
    """加载择日规则表。

    规则表缺失 → 抛 `DomainDataMissingError`（**不凭理论推算**，RULE-001）。

    Raises:
        DomainDataMissingError: 规则表文件不存在
        ValueError: 规则表结构非法（启动期校验，快速失败）
    """
    p = Path(path) if path else ZERI_TABLE_PATH
    if not p.exists():
        raise DomainDataMissingError(
            f"择日规则表缺失：{p}。事件宜忌词目属领域规则，必须由规则表提供，"
            f"不得凭理论推算（RULE-001）。"
        )
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, dict) or "events" not in data or "schools" not in data:
        raise ValueError(f"择日规则表结构错误，应含 events 与 schools 两段：{p}")

    events = data["events"]
    if not isinstance(events, dict) or not events:
        raise ValueError(f"择日规则表 events 段为空：{p}")
    for key, ev in events.items():
        if not isinstance(ev, dict):
            raise ValueError(f"[{key}] 事件定义应为 dict：{p}")
        for field_name in ("label", "yi", "ji"):
            if not ev.get(field_name):
                # ji 允许为空列表（该事件无否决词），但必须显式给出
                if field_name == "ji" and isinstance(ev.get("ji"), list):
                    continue
                raise ValueError(f"[{key}] 事件定义缺少非空字段 {field_name}：{p}")
        if not isinstance(ev["yi"], list) or not all(isinstance(w, str) for w in ev["yi"]):
            raise ValueError(f"[{key}] yi 应为字符串列表：{p}")

    schools = data["schools"]
    if "default" not in schools:
        raise ValueError(f"择日规则表 schools 段缺少 default 档案：{p}")
    for sid, prof in schools.items():
        tier = prof.get("jianchu_tier")
        if not isinstance(tier, dict):
            raise ValueError(f"[{sid}] 缺少 jianchu_tier：{p}")
        missing = [z for z in ("建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭")
                   if z not in tier]
        if missing:
            raise ValueError(f"[{sid}] jianchu_tier 未覆盖建除十二神：缺 {missing}：{p}")
        for required in ("weights", "grade_thresholds"):
            if required not in prof:
                raise ValueError(f"[{sid}] 缺少 {required}：{p}")
    return data


def _get_event(table: dict[str, Any], event: str) -> dict[str, Any]:
    """取事件定义。未注册 → 显式报错并列出可用事件（不静默回落）。"""
    events = table["events"]
    if event not in events:
        available = "、".join(sorted(events))
        raise InvalidInputError(f"未注册的择日事件 {event!r}；当前可用：{available}")
    return events[event]


def _get_school_rule(table: dict[str, Any], school: str) -> dict[str, Any]:
    """取择日流派档案。

    注意：择日流派（通行黄历口径等）与 `schools.py` 中的**风水流派**
    （三合派 / 三元派）是两套体系，语义不同，故不共用注册表，
    而是随本规则表一起模块化（RULE-006 要求的「流派规则模块化」同样满足）。
    """
    schools = table["schools"]
    if school not in schools:
        available = "、".join(sorted(schools))
        raise SchoolNotFoundError(f"未注册的择日流派 {school!r}；当前可用：{available}")
    return schools[school]


def list_zeri_events(*, table_path: str | None = None) -> list[dict[str, Any]]:
    """列出全部可择日事件（供 UI / Agent 发现能力）。"""
    table = load_zeri_table(table_path)
    return [
        {"event": key, "label": ev["label"], "yi": list(ev["yi"]), "ji": list(ev["ji"]),
         "note": ev.get("note", "")}
        for key, ev in sorted(table["events"].items())
    ]


def list_zeri_schools(*, table_path: str | None = None) -> list[dict[str, Any]]:
    """列出择日流派档案（含 `unverified` 未覆盖项，供上层生成免责标注）。"""
    table = load_zeri_table(table_path)
    return [{"id": sid, **prof} for sid, prof in sorted(table["schools"].items())]


# ---------------------------------------------------------------------------
# 结果结构
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ZeriDay:
    """单日择日评价。"""

    solar_date: str
    weekday: str
    weekday_index: int
    lunar_label: str
    day_ganzhi: str
    jian_chu: str
    xiu: str
    xiu_luck: str
    tian_shen: str
    tian_shen_type: str
    chong_shengxiao: str
    sha_direction: str
    score: int
    grade: str
    matched_yi: tuple[str, ...]
    matched_ji: tuple[str, ...]
    veto: tuple[str, ...]
    veto_kinds: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        """是否未被否决（即可进入候选列表）。"""
        return self.grade != GRADE_BUXUAN

    def to_dict(self) -> dict[str, Any]:
        return {
            "solar_date": self.solar_date,
            "weekday": self.weekday,
            "lunar": self.lunar_label,
            "day_gan_zhi": self.day_ganzhi,
            "jian_chu": self.jian_chu,
            "xiu": {"name": self.xiu, "luck": self.xiu_luck},
            "tian_shen": {"name": self.tian_shen, "type": self.tian_shen_type},
            "chong_shengxiao": self.chong_shengxiao,
            "sha_direction": self.sha_direction,
            "score": self.score,
            "grade": self.grade,
            "usable": self.is_usable,
            "matched_yi": list(self.matched_yi),
            "matched_ji": list(self.matched_ji),
            "veto": list(self.veto),
            "veto_kinds": list(self.veto_kinds),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ZeriResult:
    """择日筛选结果。"""

    event: str
    event_label: str
    start: str
    end: str
    days_scanned: int
    candidates: tuple[ZeriDay, ...]
    excluded_count: int
    excluded_reasons: dict[str, int]
    school: str
    school_name: str
    limit: int

    @property
    def best(self) -> ZeriDay | None:
        """评分最高的候选日（无候选时为 None）。"""
        return self.candidates[0] if self.candidates else None

    @property
    def has_candidates(self) -> bool:
        return bool(self.candidates)

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：确定性筛选结果。"""
        return {
            "event": self.event,
            "event_label": self.event_label,
            "range": {"start": self.start, "end": self.end, "days_scanned": self.days_scanned},
            "candidate_count": len(self.candidates),
            "excluded_count": self.excluded_count,
            "excluded_reasons": dict(self.excluded_reasons),
            "candidates": [c.to_dict() for c in self.candidates],
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：流派说明与不确定性。"""
        return {
            "school": self.school,
            "school_name": self.school_name,
            "summary": self._summary(),
            "note": (
                "择日结果基于黄历宜忌、黄黑道、二十八宿与建除十二神的通行口径加权分级，"
                "**属流派规则，仅供参考**，不等同于「宜忌断语」。"
            ),
            "uncertainties": list(self._uncertainties()),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}

    def _summary(self) -> str:
        if not self.candidates:
            return (
                f"{self.start} ~ {self.end}（共 {self.days_scanned} 天）内，"
                f"未筛出适合「{self.event_label}」的候选日；"
                f"另有 {self.excluded_count} 天被否（{self._reason_text()}）。"
                f"建议放宽日期区间或另择他事。"
            )
        best = self.candidates[0]
        return (
            f"「{self.event_label}」在 {self.start} ~ {self.end}（共 {self.days_scanned} 天）内，"
            f"筛出 {len(self.candidates)} 个候选吉日（已排除 {self.excluded_count} 天：{self._reason_text()}）。"
            f"评分最高为 {best.solar_date}（{best.weekday}，{best.day_ganzhi}日，"
            f"{best.jian_chu}日、{best.tian_shen}），评级「{best.grade}」。"
        )

    def _reason_text(self) -> str:
        if not self.excluded_reasons:
            return "无"
        # 注意：同一天可能命中多个否决项，故各项计数之和**大于** excluded_count，
        # 这里显式标注「可多项」，避免被误读成互斥分类。
        return "、".join(
            f"{k} {v} 天" for k, v in sorted(self.excluded_reasons.items())
        ) + "（同一日可命中多项，计数不互斥）"

    def _uncertainties(self) -> tuple[str, ...]:
        base = [
            f"择日流派口径：{self.school_name}；不同历书对宜忌与建除吉凶的判定存在差异",
            "评分为「通行口径」的加权汇总，权重与阈值属流派规则，非唯一标准",
            "结果不含当事人八字喜忌、三煞太岁、神煞分级等进阶规则",
            "「不宜」仅表示按本口径被否决，不代表该日对其他事项亦不吉",
        ]
        if not self.candidates:
            base.append("本区间无候选日，属筛选结果而非「绝无吉日」的断言；放宽区间或换事件可再筛")
        return tuple(base)


# ---------------------------------------------------------------------------
# 单日评价
# ---------------------------------------------------------------------------


def _normalize_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise InvalidInputError(f"非法日期字符串 {value!r}，应为 YYYY-MM-DD") from None
    raise InvalidInputError(f"日期应为 date / datetime / 'YYYY-MM-DD'，收到 {type(value).__name__}")


def evaluate_day(
    event: str,
    dt: date | datetime | str,
    *,
    school: str = "default",
    shengxiao: str | None = None,
    table_path: str | None = None,
) -> ZeriDay:
    """评价**某一天**对某事件是否相宜（含被否决原因，便于向用户解释）。

    Args:
        event: 事件 key（见 `list_zeri_events`），如 "jiaqu"。
        dt: 目标日期。
        school: 择日流派 id（默认 default）。
        shengxiao: 可选，当事人属相；提供时该日若冲此属相则否决。
        table_path: 可选，自定义规则表路径（测试用）。

    Returns:
        ZeriDay。`veto` 非空即表示该日被否决（grade="不宜"）。
    """
    table = load_zeri_table(table_path)
    ev = _get_event(table, event)
    prof = _get_school_rule(table, school)
    d = _normalize_date(dt)

    if shengxiao is not None and shengxiao not in SHENGXIAO_SET:
        raise InvalidInputError(
            f"非法属相 {shengxiao!r}；应为十二生肖之一：{'、'.join(sorted(SHENGXIAO_SET))}"
        )

    alm: AlmanacResult = calculate_almanac(d)

    yi_set, ji_set = set(alm.yi), set(alm.ji)
    ev_yi, ev_ji = set(ev["yi"]), set(ev["ji"])

    matched_yi = tuple(w for w in alm.yi if w in ev_yi)
    matched_ji = tuple(w for w in alm.ji if w in ev_ji)

    weights = prof["weights"]
    many = prof.get("many_threshold", 3)
    tier = prof["jianchu_tier"].get(alm.jian_chu, "平")

    # ---- 否决判定（忌优先，全部原因都记录，不做静默取舍）----
    veto: list[str] = []
    veto_kinds: list[str] = []

    if matched_ji:
        veto.append(f"该日忌「{'、'.join(matched_ji)}」，不宜{ev['label']}")
        veto_kinds.append(VETO_JI_HIT)
    for marker in prof.get("veto_yi_markers", []):
        if marker in yi_set:
            veto.append(f"该日「{marker}」")
            veto_kinds.append(VETO_ZHU_SHI)
    # 条件否决：宜含「馀事勿取」表示所列宜项之外皆不宜 —— 仅当事件未被宜项命中时生效
    if not matched_yi:
        for marker in prof.get("conditional_veto_markers", []):
            if marker in yi_set:
                veto.append(f"该日「{marker}」，所列宜项（{'、'.join(alm.yi)}）之外不宜{ev['label']}")
                veto_kinds.append(VETO_YU_SHI)
    if alm.jian_chu in prof.get("veto_jianchu", []):
        veto.append(f"该日值「{alm.jian_chu}」（月破），传统忌行诸事")
        veto_kinds.append(VETO_PO_DAY)
    if shengxiao is not None and alm.chong_shengxiao == shengxiao:
        veto.append(f"该日冲{alm.chong_shengxiao}，与所填属相相冲")
        veto_kinds.append(VETO_CHONG)

    # ---- 评分（仅在未被否决时有意义，但一并算出，便于解释）----
    score = 0
    reasons: list[str] = []

    if matched_yi:
        score += weights["yi_hit"]
        reasons.append(f"宜项命中「{'、'.join(matched_yi)}」（+{weights['yi_hit']}）")

    if alm.tian_shen_type == "黄道":
        score += weights["huang_dao"]
        reasons.append(f"值日天神「{alm.tian_shen}」为黄道（+{weights['huang_dao']}）")
    else:
        score += weights["hei_dao"]
        reasons.append(f"值日天神「{alm.tian_shen}」为黑道（{weights['hei_dao']}）")

    if alm.xiu_luck == "吉":
        score += weights["xiu_ji"]
        reasons.append(f"值「{alm.xiu}」宿（吉，+{weights['xiu_ji']}）")
    else:
        score += weights["xiu_xiong"]
        reasons.append(f"值「{alm.xiu}」宿（凶，{weights['xiu_xiong']}）")

    tier_key = {"吉": "jianchu_ji", "次吉": "jianchu_ciji", "凶": "jianchu_xiong"}.get(tier)
    if tier_key:
        score += weights[tier_key]
        reasons.append(f"建除「{alm.jian_chu}」属{tier}（{weights[tier_key]:+d}）")
    else:
        reasons.append(f"建除「{alm.jian_chu}」属{tier}（0）")

    if len(alm.ji_shen) >= many:
        score += weights["many_ji_shen"]
        reasons.append(f"吉神 {len(alm.ji_shen)} 位（+{weights['many_ji_shen']}）")
    if len(alm.xiong_sha) >= many:
        score += weights["many_xiong_sha"]
        reasons.append(f"凶煞 {len(alm.xiong_sha)} 位（{weights['many_xiong_sha']}）")

    # ---- 分级（被否决者一律「不宜」，不因高分而翻案）----
    thresholds = prof["grade_thresholds"]
    if veto:
        grade = GRADE_BUXUAN
    elif score >= thresholds["吉"]:
        grade = GRADE_JI
    elif score >= thresholds["次吉"]:
        grade = GRADE_CIJI
    else:
        grade = GRADE_PING

    reasons.extend(f"否决：{v}" for v in veto)
    reasons.append(f"综合评分 {score} → 评级「{grade}」")

    return ZeriDay(
        solar_date=d.isoformat(),
        weekday=WEEKDAY_LABELS[d.weekday()],
        weekday_index=d.weekday(),
        lunar_label=alm.lunar_label,
        day_ganzhi=alm.day_ganzhi,
        jian_chu=alm.jian_chu,
        xiu=alm.xiu,
        xiu_luck=alm.xiu_luck,
        tian_shen=alm.tian_shen,
        tian_shen_type=alm.tian_shen_type,
        chong_shengxiao=alm.chong_shengxiao,
        sha_direction=alm.sha_direction,
        score=score,
        grade=grade,
        matched_yi=matched_yi,
        matched_ji=matched_ji,
        veto=tuple(veto),
        veto_kinds=tuple(veto_kinds),
        reasons=tuple(reasons),
    )


# ---------------------------------------------------------------------------
# 区间筛选
# ---------------------------------------------------------------------------


def select_auspicious_days(
    event: str,
    start: date | datetime | str,
    end: date | datetime | str,
    *,
    limit: int = DEFAULT_LIMIT,
    school: str = "default",
    shengxiao: str | None = None,
    include_unfavorable: bool = False,
    table_path: str | None = None,
) -> ZeriResult:
    """在 `[start, end]` 区间内为该事件筛选候选吉日。

    Args:
        event: 事件 key，如 "jiaqu"。
        start / end: 区间起止（含端点）。
        limit: 最多返回候选数（按评分降序，同分按日期升序）；<=0 表示不限。
        school: 择日流派 id。
        shengxiao: 可选，当事人属相；提供时自动排除冲该属相的日子。
        include_unfavorable: True 时把被否决的日子也一并返回（便于解释与调试）。
        table_path: 可选，自定义规则表路径。

    Returns:
        ZeriResult。候选为空是**合法结果**（如「赴任」本就吉日稀少），
        由 `to_tradition()["summary"]` 给出说明，不是错误。

    Raises:
        InvalidInputError: 日期区间非法 / 超长，事件或属相非法
        SchoolNotFoundError: 流派未注册
        DomainDataMissingError: 规则表缺失
    """
    d_start, d_end = _normalize_date(start), _normalize_date(end)
    if d_end < d_start:
        raise InvalidInputError(f"结束日期 {d_end} 早于开始日期 {d_start}")
    span = (d_end - d_start).days + 1
    if span > MAX_RANGE_DAYS:
        raise InvalidInputError(
            f"日期区间 {span} 天超出上限 {MAX_RANGE_DAYS} 天；请缩小范围后重试"
        )

    table = load_zeri_table(table_path)
    ev = _get_event(table, event)
    prof = _get_school_rule(table, school)

    days = [
        evaluate_day(event, d_start + timedelta(days=i), school=school,
                     shengxiao=shengxiao, table_path=table_path)
        for i in range(span)
    ]

    excluded = [d for d in days if not d.is_usable]
    pool = days if include_unfavorable else [d for d in days if d.is_usable]
    pool = sorted(pool, key=lambda x: (-x.score, x.solar_date))
    candidates = tuple(pool[:limit]) if limit and limit > 0 else tuple(pool)

    reason_counter: Counter[str] = Counter()
    for d in excluded:
        for kind in d.veto_kinds:
            reason_counter[kind] += 1

    return ZeriResult(
        event=event,
        event_label=ev["label"],
        start=d_start.isoformat(),
        end=d_end.isoformat(),
        days_scanned=span,
        candidates=candidates,
        excluded_count=len(excluded),
        excluded_reasons=dict(reason_counter),
        school=school,
        school_name=prof["name"],
        limit=limit,
    )


__all__ = [
    "ZeriDay", "ZeriResult",
    "load_zeri_table", "list_zeri_events", "list_zeri_schools",
    "evaluate_day", "select_auspicious_days",
    "GRADE_JI", "GRADE_CIJI", "GRADE_PING", "GRADE_BUXUAN",
    "MAX_RANGE_DAYS", "DEFAULT_LIMIT",
]
