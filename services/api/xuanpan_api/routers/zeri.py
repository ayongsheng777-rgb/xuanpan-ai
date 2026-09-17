"""择日 —— 由「查每日宜忌」反过来「为某事件筛吉日」。

三条端点对应三种真实用法：

| 端点 | 用户心里想的是 |
|---|---|
| `GET /zeri/events`   | 「有哪些事可以择日？」—— UI 渲染选择器 |
| `GET /zeri/evaluate` | 「我选定了某天，这天行不行？」 |
| `POST /zeri/select`  | 「下个月哪几天行？」—— 择日的主用法 |

**事件与流派全部从规则表读取**，接口层不写死任何事件名：
写死一处，将来规则表加事件时必然漏改，而漏改的表现是「新事件在 App 里看不见」
—— 不报错、只是静默消失，正是最该避免的失败方式。

未知事件 / 未知流派由内核抛 `InvalidInputError` / `SchoolNotFoundError`
（都是 `FortuneError` 子类），经 `app.py` 的统一处理器转 400。
**注意 `FortuneError` 不继承 `ValueError`** —— 若忘了注册那个处理器，这些
本该是"你传错了"的错误会变成 500，让用户以为服务坏了。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from ..schemas import (
    ZeriDayResponse,
    ZeriEvent,
    ZeriEventsResponse,
    ZeriResultResponse,
    ZeriSelect,
)

router = APIRouter(prefix="/zeri", tags=["zeri"])


@router.get("/events", response_model=ZeriEventsResponse, summary="可择日事件与流派")
def zeri_events() -> ZeriEventsResponse:
    """列出全部可择日事件与流派档案。

    `schools[].unverified` 是**显式未覆盖项**（如三煞、太岁、五黄），
    UI 应把它展示成"本版不覆盖"，而不是省略 ——
    用户有权知道"这份吉日建议没有考虑什么"。
    """
    from fortune_core.zeri import list_zeri_events, list_zeri_schools

    return ZeriEventsResponse(
        events=[ZeriEvent(**ev) for ev in list_zeri_events()],
        schools=list_zeri_schools(),
    )


@router.get("/evaluate", response_model=ZeriDayResponse, summary="单日择日评价")
def zeri_evaluate(
    event: str = Query(description="事件 key，见 /zeri/events"),
    day: date = Query(alias="date", description="公历日期（YYYY-MM-DD）"),
    school: str = Query(default="default", description="择日流派 id"),
    shengxiao: str | None = Query(
        default=None, description="当事人属相；提供时该日若冲此属相即被否决"
    ),
) -> ZeriDayResponse:
    """评价某一天对某事件是否相宜。

    返回 `day.veto` 为空即表示未被否决。`day.reasons` 给出**逐条依据**
    （哪条宜项命中、哪条否决生效），供 UI 向用户解释"为什么不宜"。
    """
    from fortune_core.zeri import evaluate_day, list_zeri_events, list_zeri_schools

    result = evaluate_day(event, day, school=school, shengxiao=shengxiao)

    # 标签与备注取自规则表本身，不在这里另写一份文案 —— 两处文案必然漂移。
    event_meta = next((e for e in list_zeri_events() if e["event"] == event), None)
    school_meta = next((s for s in list_zeri_schools() if s["id"] == school), None)

    return ZeriDayResponse(
        day=result.to_dict(),
        event_label=event_meta["label"] if event_meta else event,
        school=school,
        school_name=(school_meta or {}).get("name", school),
        event_note=(event_meta or {}).get("note", ""),
    )


@router.post("/select", response_model=ZeriResultResponse, summary="区间择日筛选")
def zeri_select(payload: ZeriSelect) -> ZeriResultResponse:
    """在区间内为该事件筛选候选吉日（按评分降序）。

    **候选为空是合法结果**，不是错误：像「赴任」这类事件本就吉日稀少。
    此时 `tradition.summary` 会给出说明与建议，UI 应如实展示"本区间无候选"
    并提示放宽区间，而不是渲染成错误页。
    """
    from fortune_core.zeri import select_auspicious_days

    result = select_auspicious_days(
        payload.event,
        payload.start,
        payload.end,
        limit=payload.limit,
        school=payload.school,
        shengxiao=payload.shengxiao,
        include_unfavorable=payload.include_unfavorable,
    )
    return ZeriResultResponse(**result.to_dict())


__all__ = ["router"]
