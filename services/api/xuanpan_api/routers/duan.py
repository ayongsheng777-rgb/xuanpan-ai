"""断卦 —— 把确定性排盘组合成吉凶倾向。

**这里仍然没有 LLM**。`duangua.py` 的规则全部建立在装卦层 / 旺衰层的确定性
FACT 之上，只做组合（用神旺衰、世应、旬空、动爻 → 倾向分级）。
LLM 的职责在 `/sessions/{id}/report` 的解释层，不在本文件 —— 这是 RULE-001/002。

## 为什么必须三步齐全

六爻的链路是 `cast_liuyao`（起卦）→ `zhuang_gua`（纳甲装卦）→ `duan_liuyao`（断）。
少一步就不是六爻：

- 只起卦 → 只有本卦/变卦名，没有六亲世应，**无从断起**
- 缺日辰 → 六神、旬空、旺衰全部无从定。日辰是"卦之主宰"，缺了整盘失效

所以本文件与 MCP 暴露层走**完全相同**的三步。`build_liuyao` 与 `/calc/liuyao`
共用，保证「预览里看到的卦」与「断卦所依据的卦」是同一份数据。

## 起卦日的口径

`cast_date` 默认今天。**补录隔夜的卦必须显式传** —— 否则会拿今天的日辰去算
昨天摇的卦，旺衰结论看似正常、依据却全错，用户无从察觉。
实际使用的日辰月令随 `detail.basis` 一并返回，任何一条倾向都能回溯到它。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException

from ..context_builder import build_bazi, build_liuyao
from ..schemas import BaziInput, DuanLiuyaoRequest, DuanResponse

router = APIRouter(prefix="/duan", tags=["duan"])

#：`DuanResponse` 顶层已有的字段。detail 承载其余差异化部分。
_TOP_LEVEL = ("verdict", "reasons", "school", "uncertainties")


def _pillars_of(day: date) -> tuple[str, str]:
    """取某日的日柱与月柱干支（装卦用）。

    口径与 MCP 暴露层一致（`getMonthInGanZhi`，按交节日、不细分时刻）。
    为什么刻意保持一致：同一个卦若从 HTTP 与 MCP 两个入口算出**不同的月建**，
    用户会拿到两套结论而无从判断谁对。交节当天的时刻级差异不在这里私自改口径，
    而是归入 `uncertainties` 让使用者知情。
    """
    from lunar_python import Solar

    lunar = Solar.fromYmd(day.year, day.month, day.day).getLunar()
    return lunar.getDayInGanZhi(), lunar.getMonthInGanZhi()


def _split(raw: dict[str, Any], **extra: Any) -> DuanResponse:
    """把内核 `to_dict()` 拆成「稳定契约 + 差异化细节」。"""
    detail = {k: v for k, v in raw.items() if k not in _TOP_LEVEL}
    detail.update(extra)
    return DuanResponse(
        verdict=raw["verdict"],
        reasons=list(raw["reasons"]),
        school=raw["school"],
        uncertainties=list(raw["uncertainties"]),
        detail=detail,
    )


@router.post("/liuyao", response_model=DuanResponse, summary="六爻断卦（吉凶倾向）")
def duan_liuyao_endpoint(payload: DuanLiuyaoRequest) -> DuanResponse:
    """六爻吉凶倾向。

    `detail.divination` 是完整装卦结果（纳甲、六亲、世应、六神、伏神、旬空、旺衰），
    `detail.basis` 是本盘实际采用的日柱月令。两者都要展示 ——
    只给一个「偏吉」而不给依据，等于让用户无条件相信一个黑盒。

    `topic`（占问类别）决定**取哪个六亲为用神**，这是断卦的第一步。
    传了未注册的类别会直接 400 而不是静默沿用「无主题」：后者会让用神取空，
    结论退化成与所问之事无关的「中平」，而那看起来完全像一个正常结果。
    """
    from fortune_core import duan_liuyao
    from fortune_core.context import QUESTION_CATEGORIES
    from fortune_core.liuyao.zhuang import YONGSHEN_BY_TOPIC, yongshen_of, zhuang_gua

    if payload.topic is not None:
        allowed = set(QUESTION_CATEGORIES) | set(YONGSHEN_BY_TOPIC)
        if payload.topic not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"未注册的占问类别 {payload.topic!r}；"
                    f"可用：{'、'.join(sorted(allowed))}"
                ),
            )

    cast_date = payload.cast_date or date.today()
    day_pillar, month_pillar = _pillars_of(cast_date)

    result = build_liuyao(payload.model_dump(exclude_none=True))
    divination = zhuang_gua(
        result,
        day_pillar=day_pillar,
        month_pillar=month_pillar,
        topic=payload.topic,
        gender=payload.gender,
    )

    extra_uncertainties: list[str] = []
    yongshen = yongshen_of(payload.topic, payload.gender) if payload.topic else None
    if payload.topic is None:
        # 内核此时给出的理由是「用神不上卦（伏神）」。那句措辞在本场景是**错的**：
        # 不是用神藏起来了，而是用户根本没说要问什么事。照搬会让用户
        # 以为卦里有什么玄机，实际只是信息缺失。故在此显式纠正。
        extra_uncertainties.append(
            "未指定占问类别，本次未取用神；倾向为整体卦象参照，不等于针对该事的结论"
        )
    elif yongshen is None:
        # 「其他」这类类别本就无对应用神，是合法输入而非错误。
        # 但必须讲清楚"本次没取用神"，否则用户会以为中平是算出来的。
        extra_uncertainties.append(
            f"占问类别「{payload.topic}」未定义用神，本次未取用神，倾向仅供参照"
        )

    response = _split(
        duan_liuyao(divination).to_dict(),
        divination=divination.to_dict(),
        basis={
            "cast_date": cast_date.isoformat(),
            "day_pillar": day_pillar,
            "month_pillar": month_pillar,
            "topic": payload.topic,
            "gender": payload.gender,
            "yongshen": yongshen,
        },
    )
    if extra_uncertainties:
        response = response.model_copy(
            update={"uncertainties": response.uncertainties + extra_uncertainties}
        )
    return response


@router.post("/bazi", response_model=DuanResponse, summary="八字断卦（旺衰与运程倾向）")
def duan_bazi_endpoint(payload: BaziInput) -> DuanResponse:
    """八字旺衰与喜用倾向。

    `verdict` 是身强 / 身弱（复用旺衰层），`detail.da_yun_verdicts` 是每一步大运的
    吉凶倾向。注意**大运倾向是相对日主喜忌而言的**，不等于"这十年一定如何" ——
    对应 `uncertainties` 里的流派标注。

    这里不重复回传整份命盘：App 的命盘页已经展示四柱与大运，
    断卦接口再传一份只会让同一份数据出现两个来源，迟早不一致。
    """
    from fortune_core import duan_bazi

    chart = build_bazi(payload.model_dump(exclude_none=True))
    return _split(duan_bazi(chart).to_dict())


__all__ = ["router"]
