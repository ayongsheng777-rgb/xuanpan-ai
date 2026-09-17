"""黄历查询 —— 单日与区间。

**为什么独立于 `/calc/*`**：黄历是「日历查询」，不是会话的「盘面模块」。
它没有输入上下文、不落库、也不进 `FortuneContext`。若硬塞进 `calc` 的预览体系，
「预览与报告必然一致」这条不变量会变成空话 —— 黄历根本没有报告。

但接口**沿用同样的两层结构**（`facts` / `tradition`），前端渲染逻辑无需分叉。

`facts` 里带着内核的 `rule_consistency` —— 那是建除十二神的交叉校验结果。
交节日因月支口径差会留一条说明，UI 应把它当"已知口径差"展示，而不是当错误。
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from ..schemas import AlmanacDay, AlmanacRange

router = APIRouter(prefix="/almanac", tags=["almanac"])

#：区间查询上限。取一个月，是因为黄历的典型用法是「看这个月哪几天合适」。
#：更长的区间该用择日（`/zeri/select`）—— 那是**反向筛选**，不是逐日列举。
#：这里不复用 `zeri.MAX_RANGE_DAYS`：两者语义不同（一个限制展示量，一个限制筛算量），
#：强行同值会让将来调整任何一方都牵动另一方。
MAX_ALMANAC_DAYS = 31


def _day_of(day: date) -> AlmanacDay:
    """算一整天的黄历，转成接口的两层结构。"""
    from fortune_core import calculate_almanac

    result = calculate_almanac(day)
    return AlmanacDay(facts=result.to_facts(), tradition=result.to_tradition())


@router.get("/day", response_model=AlmanacDay, summary="单日黄历")
def almanac_day(
    day: date | None = Query(
        default=None, alias="date", description="公历日期（YYYY-MM-DD），省略则为今天"
    ),
) -> AlmanacDay:
    """单日黄历。

    `date` 省略即「今天」—— 这是 App 打开黄历页最常见的用法。
    让服务端定"今天"，客户端就不必自己算日期，也就不会引入客户端时区口径差异。
    """
    return _day_of(day or date.today())


@router.get("/range", response_model=AlmanacRange, summary="区间黄历（逐日）")
def almanac_range(
    start: date = Query(description="起始日期（含）"),
    end: date = Query(description="结束日期（含）"),
) -> AlmanacRange:
    """区间黄历，逐日返回两层结果。

    逐日返回而非只给日期列表，是因为前端要按天渲染宜忌；
    服务端既然已经算好，再让前端拼一次纯属重复劳动。
    """
    if end < start:
        raise HTTPException(status_code=400, detail="结束日期早于起始日期")
    span = (end - start).days + 1
    if span > MAX_ALMANAC_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"区间最多 {MAX_ALMANAC_DAYS} 天，收到 {span} 天；更长的区间请用择日筛选",
        )
    return AlmanacRange(
        start=start.isoformat(),
        end=end.isoformat(),
        days=[_day_of(start + timedelta(days=i)) for i in range(span)],
    )


__all__ = ["router", "MAX_ALMANAC_DAYS"]
