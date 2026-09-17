"""奇门遁甲 —— 排盘查询（三式之一）。

两条端点：

| 端点 | 用户心里想的是 |
|---|---|
| `GET  /qimen/meta` | 「排盘界面需要知道什么？」—— 局数表 + 流派 + 未覆盖项 |
| `POST /qimen/pan`  | 「给我排这个时刻的盘」 |

输入为什么是 **datetime 而非 date**：奇门以**时辰**起局，同一日不同时辰
局可能不同，只给日期排不出盘。

**局数表由接口返回，前端不得自己算** —— 它是领域数据（RULE-005）。
前端硬编码一份必然与内核漂移，而漂移的表现是「界面显示的局数与实排不符」，
不报错、只是静默不一致，正是最该避免的失败方式。

未知流派由内核抛 `SchoolNotFoundError`（`FortuneError` 子类），
经 `app.py` 的统一处理器转 400 —— 语义是"你传错了"，不是"服务坏了"。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..schemas import QimenCastRequest, QimenMetaResponse

router = APIRouter(prefix="/qimen", tags=["qimen"])


@router.get("/meta", response_model=QimenMetaResponse, summary="奇门元数据（局数表与流派）")
def qimen_meta() -> QimenMetaResponse:
    """局数表 / 阴阳遁节气划分 / 流派 / 未覆盖项。

    `uncertainties` 取自内核常量，与排盘结果里那份是**同一个来源** ——
    界面应把它展示成"本版不覆盖"，而不是省略：
    用户有权知道"这份盘没有考虑什么"。
    """
    from fortune_core.qimen import (
        SCHOOLS,
        UNCERTAINTIES,
        YANG_DUN_JIEQI,
        YIN_DUN_JIEQI,
        jushu_table,
    )

    return QimenMetaResponse(
        schools=[dict(v) for v in SCHOOLS.values()],
        jushu_table={jq: list(triple) for jq, triple in jushu_table().items()},
        yang_dun_jieqi=list(YANG_DUN_JIEQI),
        yin_dun_jieqi=list(YIN_DUN_JIEQI),
        uncertainties=list(UNCERTAINTIES),
    )


@router.post("/pan", summary="奇门排盘")
def qimen_pan(payload: QimenCastRequest) -> dict[str, Any]:
    """排一个奇门盘。

    返回结构见 `fortune_core.qimen.QimenChart.to_dict()`。
    `palaces` 是按宫序 1~9 排好的九宫，每宫含
    地盘干 / 天盘干 / 九星 / 八门 / 八神 / 空亡 / 驿马标记，
    前端只需按洛书位置摆放，不需要再做任何推导。
    """
    from fortune_core.qimen import cast_qimen

    chart = cast_qimen(
        payload.dt,
        school=payload.school,
        day_boundary=payload.day_boundary,
    )
    return chart.to_dict()


__all__ = ["router"]
