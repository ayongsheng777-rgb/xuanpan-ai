"""管理界面后端 —— 运维入口。

## 安全默认：未配置令牌即关闭

管理界面会列出**全部会话记录**，其中含用户生辰、坐向等隐私数据。
容器部署时宿主端口通常对外映射，所以「默认可访问」等于把用户数据放到公网上。
因此 `XUANPAN_ADMIN_TOKEN` 未配置时，本模块所有接口一律拒绝并给出配置指引。

刻意**不做**两种折中：

- 「未配置就只读」—— 只读同样泄露隐私，那只是把风险描述得小一点；
- 「仅允许 127.0.0.1」—— 容器内的 127.0.0.1 是容器自己，宿主访问一律来自
  网关地址，白名单既拦不住远程、又会拦住正常使用。

## 为什么另立一组接口，而不是复用 /api/v1/sessions

现有的 sessions / report 接口是给 App 用的，**没有鉴权**。
管理界面若直接调它们，鉴权就只剩前端画的一道门 —— 知道 URL 就能绕过。
所以 admin 组自带鉴权，而**内部复用同一个 `Store`**，不重复实现任何查询逻辑。
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from ..config import Settings
from ..deps import get_settings, get_store
from ..storage import Store

#：未配置令牌时的提示。会同时出现在接口 403 的 detail 与页面提示里 ——
#：一处措辞、两处展示，避免两边说法不一致。
ADMIN_DISABLED_HINT = (
    "管理界面未启用：环境变量 XUANPAN_ADMIN_TOKEN 未设置。\n"
    "该界面会列出全部会话记录（含生辰等隐私信息），因此默认关闭。\n"
    "启用步骤：\n"
    "  1) 生成令牌：python -c \"import secrets;print(secrets.token_urlsafe(32))\"\n"
    "  2) 写入 .env：XUANPAN_ADMIN_TOKEN=<上一步生成的值>\n"
    "  3) 重启服务，然后访问 /admin?token=<令牌>"
)


def require_admin(request: Request, cfg: Settings = Depends(get_settings)) -> None:
    """管理接口的统一鉴权闸门。

    令牌可经三种途径提供，按「越显式越优先」排序：
    请求头（脚本调用）、查询参数（首次点链接）、Cookie（页面登录后）。

    `compare_digest` 而非 `==`：字符串比较在第一个不同字节处就短路，
    理论上可被计时侧信道逐字节猜出令牌。内网场景风险很低，
    但改用一个常数时间比较没有任何代价。

    ⚠️ `cfg` 必须经 `Depends` 注入，**不能写成裸的 `get_settings()` 调用**。
    那样会绕开 `app.dependency_overrides`，直接拿到进程启动时的 `DEFAULT_SETTINGS`：
    测试里换不掉配置只是表象，真正的问题是同一模块内出现两种取配置的方式 ——
    一旦 `admin_overview` 走注入、这里走单例，就会出现
    「鉴权按 A 配置、展示按 B 配置」的分裂，而这种分裂极难察觉。
    """
    if not cfg.admin_token:
        raise HTTPException(status_code=403, detail=ADMIN_DISABLED_HINT)

    supplied = (
        request.headers.get("X-Xuanpan-Admin-Token")
        or request.query_params.get("token")
        or request.cookies.get("xuanpan_admin")
    )
    if not supplied or not secrets.compare_digest(supplied, cfg.admin_token):
        raise HTTPException(status_code=401, detail="管理令牌无效或未提供")


router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _rule_tables() -> dict[str, Any]:
    """各领域规则表的就绪状态。

    为什么管理界面要专门显示这个：规则表缺失时计算层返回 `None`（不猜），
    UI 上表现为"某个格子空着"。运维看到"怎么不显示"时要能立刻分辨
    是**表没进镜像**还是**程序坏了** —— 这两者的处理方式完全不同。
    """
    out: dict[str, Any] = {}

    try:
        from fortune_core.fenjin120 import table_available

        out["fenjin120"] = {"available": table_available()}
    except Exception as exc:  # noqa: BLE001 - 管理界面要报告"为什么没有"，不能让异常逃逸
        out["fenjin120"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        from fortune_core.zeri import list_zeri_events, list_zeri_schools

        out["zeri_events"] = {
            "available": True,
            "events": len(list_zeri_events()),
            "schools": [s["id"] for s in list_zeri_schools()],
        }
    except Exception as exc:  # noqa: BLE001
        out["zeri_events"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        from fortune_core.naming import DEFAULT_STROKES_PATH, load_strokes

        raw = json.loads(Path(DEFAULT_STROKES_PATH).read_text(encoding="utf-8"))
        out["kangxi_strokes"] = {
            "available": bool(load_strokes()),
            "chars": len(load_strokes()),
            # `verified=False` 意味着表是拼凑来源，笔画可能不可信 —— 必须显式可见
            "verified": bool(raw.get("verified", False)),
        }
    except Exception as exc:  # noqa: BLE001
        out["kangxi_strokes"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"}

    return out


@router.get("/overview", summary="概览：体量、能力与规则表状态")
def admin_overview(
    store: Store = Depends(get_store),
    cfg: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """一屏看清"现在有什么、哪些能力可用、数据在哪"。"""
    counts = store.stats()

    db_path = Path(cfg.db_path)
    try:
        db_size = db_path.stat().st_size if db_path.exists() else 0
    except OSError:  # pragma: no cover - 权限异常时不该让整页挂掉
        db_size = -1

    capabilities: dict[str, Any] = {}
    try:
        from xuanpan_ai import list_providers as list_ai

        capabilities["ai_provider_available"] = any(p.get("available") for p in list_ai())
    except Exception:  # noqa: BLE001
        capabilities["ai_provider_available"] = False
    try:
        from xuanpan_vision import list_providers as list_vision

        capabilities["vision_provider_available"] = any(p.get("available") for p in list_vision())
    except Exception:  # noqa: BLE001
        capabilities["vision_provider_available"] = False

    return {
        "counts": counts,
        "storage": {"db_path": str(db_path), "size_bytes": db_size},
        "rule_tables": _rule_tables(),
        "capabilities": capabilities,
        "config": {
            "ai_mode": cfg.ai_mode,
            "keep_photos": cfg.keep_photos,
            "max_upload_mb": cfg.max_upload_mb,
            "cors_origins": list(cfg.cors_origins),
            "admin_enabled": bool(cfg.admin_token),
        },
        "note": (
            "会话记录含用户生辰等隐私数据。本页仅在配置了 XUANPAN_ADMIN_TOKEN 时可访问；"
            "对外暴露前请确认服务本身没有直接映射到公网。"
        ),
    }


@router.get("/sessions", summary="会话列表（管理视图）")
def admin_sessions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """与会话列表接口同一数据源，只是走 admin 鉴权。"""
    return {
        "total": store.count_sessions(),
        "limit": limit,
        "offset": offset,
        "items": store.list_sessions(limit=limit, offset=offset),
    }


@router.get("/sessions/{session_id}", summary="会话详情（含报告与多轮对话）")
def admin_session_detail(session_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    """一次把运维要看的东西取全：输入、识别快照、报告、对话。

    分多次请求会让人在下拉列表里反复点，而管理界面的使用场景是"排查这一个会话"。
    """
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"会话不存在：{session_id}")
    return {
        "session": session,
        "reports": store.list_reports(session_id),
        "turns": store.list_turns(session_id),
    }


@router.delete("/sessions/{session_id}", summary="删除会话（含报告与对话）")
def admin_delete_session(session_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    """删除是不可逆操作 —— 界面上必须二次确认后才调用这里。"""
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"会话不存在：{session_id}")
    return {"deleted": True, "session_id": session_id}


@router.get("/reports/{report_id}", summary="查看单份报告")
def admin_report(report_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    report = store.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"报告不存在：{report_id}")
    return report


__all__ = ["router", "require_admin", "ADMIN_DISABLED_HINT"]
