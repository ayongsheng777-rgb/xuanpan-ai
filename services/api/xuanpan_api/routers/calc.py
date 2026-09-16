"""纯计算预览路由 —— 无状态，不落库。

用途：UI 在用户还没"保存"之前就要显示结果（如八字一排出来立刻想看到四柱），
若必须先建会话再算，链路会变长且产生大量半成品会话。

这些接口与 `/sessions/{id}/inputs` 走**完全相同**的底层函数
（`context_builder.build_*` → `preview_of`），因此预览与最终报告必然一致。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..context_builder import ContextBuildError, build_bazi, build_compass, build_liuyao, build_naming, build_qian, preview_of
from ..schemas import BaziInput, CompassInput, LayerPreview, LiuyaoInput, NamingInput, QianInput

router = APIRouter(prefix="/calc", tags=["calc"])


def _preview(module: str, builder, payload) -> LayerPreview:  # type: ignore[no-untyped-def]
    """统一处理：构造 → 预览。领域异常翻译成 400（输入问题，不是服务故障）。"""
    try:
        result = builder(payload.model_dump(exclude_none=True))
    except ContextBuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return preview_of(module, result)
    except ContextBuildError as exc:  # pragma: no cover - 防御
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/compass", response_model=LayerPreview, summary="坐向计算预览")
def calc_compass(payload: CompassInput) -> LayerPreview:
    return _preview("compass", build_compass, payload)


@router.post("/bazi", response_model=LayerPreview, summary="八字排盘预览")
def calc_bazi(payload: BaziInput) -> LayerPreview:
    return _preview("bazi", build_bazi, payload)


@router.post("/liuyao", response_model=LayerPreview, summary="六爻起卦预览")
def calc_liuyao(payload: LiuyaoInput) -> LayerPreview:
    return _preview("liuyao", build_liuyao, payload)


@router.post("/qian", response_model=LayerPreview, summary="抽签预览")
def calc_qian(payload: QianInput) -> LayerPreview:
    return _preview("qian", build_qian, payload)


@router.post("/naming", response_model=LayerPreview, summary="姓名分析预览")
def calc_naming(payload: NamingInput) -> LayerPreview:
    return _preview("naming", build_naming, payload)


__all__ = ["router"]
