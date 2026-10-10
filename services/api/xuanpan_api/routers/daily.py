"""每日运程 —— 基于用户出生日期的当日运程查询。

**为什么独立于 `/calc/*`**：与黄历同理 —— 它是「无状态查询」，
不落库、不进 `FortuneContext`、没有报告。硬塞进 `calc` 的预览体系，
「预览与报告必然一致」这条不变量会变成空话。

接口沿用同样的两层结构（`facts` / `tradition`），前端渲染逻辑无需分叉。

用 POST 而不用 GET：请求体里装着出生日期这类个人信息，
放 query 参数会进日志与浏览器历史；POST + JSON 更干净。
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from ..schemas import DailyFortune, DailyFortuneInput

router = APIRouter(prefix="/daily", tags=["daily"])


@router.post("/fortune", response_model=DailyFortune, summary="每日运程")
def daily_fortune(payload: DailyFortuneInput) -> DailyFortune:
    """按出生日期算目标日的运程。

    - `birth_date` 只用于定日主（八字日柱），时辰不影响结果；
    - `birth_hour` 未知可省略，服务端按午时排盘，tradition 层会留痕说明；
    - `target_date` 省略即「今天」—— 由服务端定，客户端不必自己算日期，
      也就不会引入客户端时区口径差异。
    """
    from fortune_core import daily_fortune as calc

    result = calc(
        payload.birth_date,
        payload.target_date or date.today(),
        birth_hour=payload.birth_hour,
    )
    return DailyFortune(facts=result.to_facts(), tradition=result.to_tradition())


__all__ = ["router"]
