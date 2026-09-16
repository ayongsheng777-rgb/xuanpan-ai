"""会话路由 —— 录入、确认、历史、删除。

数据策略（与 `storage` 一致）：**只存用户输入**，派生结果一律按需重算。
因此这里的每个写接口都只做"把用户给的东西存下来"，不缓存任何计算结果。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..context_builder import (
    ORIGIN_OF_COLUMN,
    ContextBuildError,
    available_modules,
    build_compass,
    preview_of,
    rebuild_context,
)
from ..deps import get_store
from ..schemas import (
    CompassConfirm,
    DeletedResponse,
    InputPatch,
    LayerPreview,
    SessionCreate,
    SessionCreated,
)
from ..storage import Store

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _require(store: Store, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话不存在：{session_id}")
    return session


@router.post("", response_model=SessionCreated, summary="新建会话")
def create_session(payload: SessionCreate, store: Store = Depends(get_store)) -> SessionCreated:
    session_id = store.create_session(
        origin="manual",
        title=payload.title or _default_title(payload.question_text),
        question_category=payload.question_category,
        question_text=payload.question_text,
    )
    session = _require(store, session_id)
    return SessionCreated(
        session_id=session_id,
        created_at=session["created_at"],
        title=session["title"],
    )


@router.get("", summary="会话列表")
def list_sessions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    return {
        "total": store.count_sessions(),
        "items": store.list_sessions(limit=limit, offset=offset),
    }


@router.get("/{session_id}", summary="会话详情（含已录入模块的两层结果）")
def get_session(session_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    """详情页数据。

    返回值里的 `facts` / `tradition` 是**按需重算**的，与数据库里存的东西无关 ——
    数据库只存输入。这样内核升级后，同一个会话重放得到的是新口径的结果，
    不会留下"库里一份、内核一份"的双真源。
    """
    session = _require(store, session_id)
    modules = available_modules(session)

    facts: dict[str, Any] = {}
    tradition: dict[str, Any] = {}
    uncertainties: list[str] = []
    build_error: str | None = None

    if modules:
        try:
            ctx = rebuild_context(session)
            facts = ctx.to_facts()
            tradition = ctx.to_tradition()
            uncertainties = ctx.uncertainties()
        except ContextBuildError as exc:
            # 输入损坏时**不隐藏**：告诉调用方"这份会话现在算不出来"，而不是返回空三层
            build_error = str(exc)

    return {
        "session_id": session_id,
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
        "title": session["title"],
        "origin": session["origin"],
        "question": {
            "category": session.get("question_category"),
            "text": session.get("question_text"),
        },
        "modules": modules,
        "inputs": {column: session.get(column) for column in ORIGIN_OF_COLUMN},
        "recognition": session.get("recognition"),
        "confirm_state": session.get("confirm_state"),
        "facts": facts,
        "tradition": tradition,
        "uncertainties": uncertainties,
        "build_error": build_error,
        "report_count": len(store.list_reports(session_id)),
    }


@router.patch("/{session_id}/inputs", summary="录入 / 更新某个模块的输入")
def patch_inputs(
    session_id: str, payload: InputPatch, store: Store = Depends(get_store)
) -> dict[str, Any]:
    """增量录入。只更新本次传了的模块，其余保持原值。

    **顺序很关键**：先全部构造成功，再落库。
    早先的写法是"先落库、再逐个预览"，结果是：用户传了非法山名时，
    数据已经被写进库、接口还返回 200（错误藏在 previews 里）——
    下次打开会话直接 500。非法输入必须在落库前就被拒绝。
    """
    _require(store, session_id)

    column_of = {value: key for key, value in ORIGIN_OF_COLUMN.items()}

    # ---- 1. 全部构造（任一失败 → 整体拒绝，不落库）----
    built: dict[str, Any] = {}
    for module, value in (
        ("compass", payload.compass),
        ("bazi", payload.bazi),
        ("liuyao", payload.liuyao),
        ("qian", payload.qian),
        ("naming", payload.naming),
    ):
        if value is None:
            continue
        built[module] = _build(module, value.model_dump(exclude_none=True))

    inputs = {column_of[m]: _input_of(payload, m) for m in built}

    # ---- 2. 落库 ----
    try:
        store.update_session(
            session_id,
            inputs=inputs,
            question_category=payload.question_category,
            question_text=payload.question_text,
            title=payload.title,
        )
    except ValueError as exc:  # 未知列
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ---- 3. 预览 ----
    previews = {m: preview_of(m, r).model_dump() for m, r in built.items()}
    return {"session_id": session_id, "updated": list(built), "previews": previews}


def _input_of(payload: InputPatch, module: str) -> dict[str, Any]:
    """取该模块的原始输入字典（落库用）。"""
    value = {
        "compass": payload.compass,
        "bazi": payload.bazi,
        "liuyao": payload.liuyao,
        "qian": payload.qian,
        "naming": payload.naming,
    }[module]
    assert value is not None
    return value.model_dump(exclude_none=True)


@router.post("/{session_id}/compass/confirm", response_model=LayerPreview, summary="确认坐向（RULE-004 闸门）")
def confirm_compass(
    session_id: str, payload: CompassConfirm, store: Store = Depends(get_store)
) -> LayerPreview:
    """用户确认照片识别的坐向。

    这是识别链路进入计算链路的**唯一**放行点。设计要点：

    - 识别结果（`recognition` 列）**原样保留**，不被确认结果覆盖 ——
      这样"用户改了什么"永远可追溯（RULE-008：不篡改用户数据）
    - `confirmed_by_user` 由本接口强制置 `True`：用户主动提交就是确认本身，
      不允许客户端传 `False` 来绕过闸门
    - 提交的角度若与坐山矛盾，由计算层抛错（`OrientationConflictError`）→ 400，
      **不静默修正**用户的输入
    """
    session = _require(store, session_id)

    if payload.sitting is None and payload.facing is None:
        raise HTTPException(status_code=400, detail="至少需要指定坐山或向山")

    data: dict[str, Any] = {
        "sitting": payload.sitting,
        "facing": payload.facing,
        "degree": payload.degree,
        "confidence": _recognition_confidence(session),
        "confirmed_by_user": True,          # 强制：用户提交即确认
        "source": "vision" if session.get("recognition") else "manual",
        "school": payload.school,
    }
    data = {k: v for k, v in data.items() if v is not None or k == "confirmed_by_user"}

    try:
        orientation = build_compass(data)
        preview = preview_of("compass", orientation)
    except ContextBuildError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store.update_session(
        session_id,
        inputs={"compass_input": data},
        confirm_state={
            "confirmed": True,
            "sitting": orientation.sitting.name,
            "facing": orientation.facing.name,
            "degree": data.get("degree"),
            "user_note": payload.note,
        },
    )
    return preview


@router.delete("/{session_id}", response_model=DeletedResponse, summary="删除会话（含报告与对话）")
def delete_session(session_id: str, store: Store = Depends(get_store)) -> DeletedResponse:
    """用户主动删除（RULE-008 的删除权）。级联删掉报告与对话轮次。"""
    _require(store, session_id)
    deleted = store.delete_session(session_id)
    return DeletedResponse(deleted=deleted, session_id=session_id)


# ----------------------------------------------------------------------


def _build(module: str, data: dict[str, Any]):  # type: ignore[no-untyped-def]
    """模块名 → 构造器。延迟导入避免循环依赖。"""
    from ..context_builder import build_bazi, build_liuyao, build_naming, build_qian

    return {
        "compass": build_compass,
        "bazi": build_bazi,
        "liuyao": build_liuyao,
        "qian": build_qian,
        "naming": build_naming,
    }[module](data)


def _recognition_confidence(session: dict[str, Any]) -> float:
    """把识别置信度带进坐向记录；无识别则视为用户手输（1.0）。

    注意：置信度**只影响提示强度**，不影响任何计算 —— 计算层不因置信度低而改变结论。
    """
    rec = session.get("recognition")
    if isinstance(rec, dict):
        conf = rec.get("confidence")
        if isinstance(conf, (int, float)) and conf > 0:
            return float(min(1.0, max(0.0, conf)))
    return 1.0


def _default_title(question_text: str | None) -> str:
    from datetime import datetime

    stamp = datetime.now().strftime("%m-%d %H:%M")
    text = (question_text or "").strip()
    if text:
        return f"{stamp} {text[:12]}"
    return f"{stamp} 未命名"


__all__ = ["router"]
