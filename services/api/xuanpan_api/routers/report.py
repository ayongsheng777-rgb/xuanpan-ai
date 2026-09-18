"""报告与多轮追问路由。

关键约束（RULE-002 / 基线规范 §3）：
- AI 的唯一输入是 `FortuneContext.to_ai_payload()`，本层不得往提示里塞原始输入
- 三层报告**原样落库**：AI 输出是非确定性的，不可重算，丢了就没了
- 多轮追问只带新问题，上下文由服务端从会话重建 —— 不让客户端持有历史，
  既避免客户端篡改历史，也避免历史随客户端版本漂移
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from ..context_builder import ContextBuildError, rebuild_context
from ..deps import get_ai_router, get_store
from ..schemas import AskRequest, ReportRequest
from ..storage import Store

router = APIRouter(tags=["report"])


def _require(store: Store, session_id: str) -> dict[str, Any]:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话不存在：{session_id}")
    return session


def _resolve_router(
    request: Request,
    mode: str | None,
    force_template: bool,
    store: Store,
):
    """取 AI 路由器。

    `force_template` 用于两类场景：
    1. 用户显式要求"离线、零成本、可复现"
    2. 自动化测试与端到端校验（结果必须可复现）

    非 force_template 时走 `deps.get_ai_router`，它读的是**生效配置**
    （含管理台覆盖）并在配置变化时重建路由器。此前这里直接读
    `request.app.state.ai_router`（启动时构造一次的旧对象），
    结果是管理台改了模型名、报告仍然按老模型生成 —— 接口返回成功，
    行为毫无变化，比报错更难发现。
    """
    if force_template:
        from xuanpan_ai import AIRouter, RouterConfig, get_provider

        return AIRouter(
            providers=[get_provider("template")],
            config=RouterConfig(mode="cost"),
        )

    base = get_ai_router(request, store)
    if base is None:
        from xuanpan_ai import AIRouter

        return AIRouter()
    if mode is None or mode == base.config.mode:
        return base

    from xuanpan_ai import AIRouter, RouterConfig

    return AIRouter(providers=list(base._providers), config=RouterConfig(mode=mode))  # noqa: SLF001


@router.post("/sessions/{session_id}/report", summary="生成报告")
def generate_report(
    session_id: str,
    payload: ReportRequest,
    request: Request,
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """由会话输入重算并生成报告，落库后返回三层全量。"""
    session = _require(store, session_id)

    try:
        ctx = rebuild_context(
            session,
            question_category=payload.question_category,
            question_text=payload.question_text,
        )
    except ContextBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not ctx.to_facts():
        raise HTTPException(
            status_code=422,
            detail="该会话还没有任何可用输入（请先录入坐向 / 生辰 / 卦象等），无法生成报告",
        )

    from xuanpan_ai import AllProvidersFailedError, build_report

    ai_router = _resolve_router(request, payload.mode, payload.force_template, store)
    question = (payload.question_text if payload.question_text is not None else session.get("question_text")) or ""

    try:
        report = build_report(ctx, router=ai_router, question=str(question), task="report")
    except AllProvidersFailedError as exc:
        # 不允许退化成"随便生成一段"，如实报错
        raise HTTPException(status_code=503, detail=f"所有可用模型均调用失败：{exc}") from exc

    body = report.to_dict()
    report_id = store.save_report(session_id, body, question=str(question) or None)

    # 多轮对话留痕：用户问题与报告结论都进 turns
    if str(question).strip():
        store.add_turn(session_id, role="user", content=str(question))
    store.add_turn(
        session_id,
        role="assistant",
        content=report.interpretation.text,
        report_id=report_id,
    )

    return {"report_id": report_id, "report": body}


@router.post("/sessions/{session_id}/ask", summary="多轮追问")
def ask(
    session_id: str,
    payload: AskRequest,
    request: Request,
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """在既有盘面事实之上追问。

    注意：追问**不会**改变 facts / tradition —— 计算层结果与问题无关，
    问题只影响 AI 解读的"针对问题"区块。这正是三层分离的直接好处。
    """
    session = _require(store, session_id)

    try:
        ctx = rebuild_context(
            session,
            question_category=payload.question_category,
            question_text=payload.question_text,
        )
    except ContextBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not ctx.to_facts():
        raise HTTPException(status_code=422, detail="该会话还没有任何可用输入，无法追问")

    from xuanpan_ai import AllProvidersFailedError, Turn, build_report

    history = tuple(
        Turn(role=t["role"], content=t["content"])
        for t in store.list_turns(session_id)
        if t["role"] in ("user", "assistant")
    )

    ai_router = _resolve_router(request, payload.mode, payload.force_template, store)
    try:
        report = build_report(
            ctx,
            router=ai_router,
            question=payload.question_text,
            history=history,
            task="followup",
        )
    except AllProvidersFailedError as exc:
        raise HTTPException(status_code=503, detail=f"所有可用模型均调用失败：{exc}") from exc

    body = report.to_dict()
    report_id = store.save_report(session_id, body, question=payload.question_text)
    store.add_turn(session_id, role="user", content=payload.question_text)
    store.add_turn(
        session_id,
        role="assistant",
        content=report.interpretation.text,
        report_id=report_id,
    )

    return {"report_id": report_id, "report": body}


@router.get("/sessions/{session_id}/reports", summary="会话的报告列表")
def list_reports(session_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    _require(store, session_id)
    return {"items": store.list_reports(session_id)}


@router.get("/sessions/{session_id}/turns", summary="会话的多轮对话记录")
def list_turns(session_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    _require(store, session_id)
    return {"items": store.list_turns(session_id)}


@router.get("/reports/{report_id}", summary="读取单份报告")
def get_report(report_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    report = store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在：{report_id}")
    return report


__all__ = ["router"]
