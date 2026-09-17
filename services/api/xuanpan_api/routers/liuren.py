"""大六壬 —— 起课查询（三式之二）。

两条端点：

| 端点 | 用户心里想的是 |
|---|---|
| `GET  /liuren/meta` | 「起课界面需要知道什么？」—— 月将表 + 寄宫 + 天将 + 九宗门 + 未覆盖项 |
| `POST /liuren/cast` | 「给我排这个时刻的课」 |

输入为什么是 **datetime 而非 date**：六壬以「月将加时」起课，
**时**是盘面的直接输入，同一日不同时辰的课完全不同，只给日期排不出课。

**月将表 / 寄宫表 / 天将表由接口返回，前端不得自己算** —— 它们是领域数据（RULE-005）。
前端硬编码一份必然与内核漂移，而漂移的表现是「界面显示的月将与实排不符」，
不报错、只是静默不一致，正是最该避免的失败方式。

未知流派由内核抛 `SchoolNotFoundError`（`FortuneError` 子类），
经 `app.py` 的统一处理器转 400 —— 语义是"你传错了"，不是"服务坏了"。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..schemas import LiurenCastRequest, LiurenMetaResponse

router = APIRouter(prefix="/liuren", tags=["liuren"])


@router.get("/meta", response_model=LiurenMetaResponse, summary="六壬元数据（月将表与流派）")
def liuren_meta() -> LiurenMetaResponse:
    """月将换将表 / 十干寄宫 / 十二天将 / 九宗门 / 流派 / 未覆盖项。

    `uncertainties` 取自内核常量，与起课结果里那份是**同一个来源** ——
    界面应把它展示成"本版不覆盖"，而不是省略：
    用户有权知道"这份课没有考虑什么"。

    天将的吉凶属性也一并返回，但它是**天将自身的属性**（FACT），
    不是对所问之事的结论；界面对它只做展示，不做推断。
    """
    from fortune_core.liuren import (
        DAYTIME_ZHI,
        GUIREN,
        JIGONG,
        JIUZONGMEN,
        JIUZONGMEN_NOTE,
        SCHOOLS,
        TIANJIANG_JIXIONG,
        TIANJIANG_ORDER,
        UNCERTAINTIES,
        YUEJIANG_NAME,
        ZHONGQI_TO_YUEJIANG,
    )

    return LiurenMetaResponse(
        schools=[dict(v) for v in SCHOOLS.values()],
        yuejiang_table=dict(ZHONGQI_TO_YUEJIANG),
        yuejiang_names=dict(YUEJIANG_NAME),
        jigong=dict(JIGONG),
        guiren={k: list(v) for k, v in GUIREN.items()},
        daytime_zhi=list(DAYTIME_ZHI),
        tianjiang_order=list(TIANJIANG_ORDER),
        tianjiang_jixiong=dict(TIANJIANG_JIXIONG),
        jiuzongmen=list(JIUZONGMEN),
        jiuzongmen_note=dict(JIUZONGMEN_NOTE),
        uncertainties=list(UNCERTAINTIES),
    )


@router.post("/cast", summary="大六壬起课")
def liuren_cast(payload: LiurenCastRequest) -> dict[str, Any]:
    """排一张大六壬课。

    返回结构见 `fortune_core.liuren.LiurenChart.to_dict()`：
    `palaces` 是十二宫（地盘支 / 天盘支 / 天将 / 是否贵人临宫），
    `lessons` 是四课（含初传所出那一课的标记），
    `chuan` 是初中末三传（含天将与遁干），
    另有月将、贵人、旬空、驿马。

    前端只需按十二支位置摆放，不需要再做任何推导（RULE-005）。
    """
    from fortune_core.liuren import cast_liuren

    chart = cast_liuren(payload.dt, school=payload.school)
    return chart.to_dict()


__all__ = ["router"]
