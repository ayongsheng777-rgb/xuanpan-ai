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

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from ..config import Settings
from ..deps import get_runtime_config, get_settings, get_store
from ..runtime_config import ConfigError, RuntimeConfig
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
    runtime: RuntimeConfig = Depends(get_runtime_config),
) -> dict[str, Any]:
    """一屏看清"现在有什么、哪些能力可用、数据在哪"。"""
    counts = store.stats()

    # 报告**生效配置**而不是环境基线：概览页与配置页若对同一项给出不同的值，
    # 运维会先怀疑是缓存或部署问题，而实际上只是两处读的不是同一份配置。
    active = runtime.effective_settings(store)

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
            "ai_mode": active.ai_mode,
            "keep_photos": active.keep_photos,
            "max_upload_mb": active.max_upload_mb,
            "cors_origins": list(active.cors_origins),
            "admin_enabled": bool(cfg.admin_token),
            "cloud_ai_ready": runtime.cloud_ready(store),
            #: 提示去哪儿改 —— 概览页只读，改配置在 /admin/config
            "editable_at": "/api/v1/admin/config",
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


# ======================================================================
# 运行时配置
# ======================================================================

def _config_payload(runtime: RuntimeConfig, store: Store) -> dict[str, Any]:
    """配置的完整展示体。GET / PATCH 共用，避免两边字段不一致。"""
    effective = runtime.effective(store)
    return {
        "settings": runtime.entries(store),
        "effective": {
            "ai_mode": effective.get("ai_mode"),
            "keep_photos": effective.get("keep_photos"),
            "max_upload_mb": effective.get("max_upload_mb"),
            #: 云端解释是否齐备（base_url + api_key + model 三件套）
            "cloud_ai_ready": runtime.cloud_ready(store),
        },
        "notes": [
            "来源列写明每项当前值来自哪里：管理台覆盖 > 环境变量 > 代码默认值。",
            "改了环境变量却没变化时，先看这里是不是「管理台覆盖」压着 —— "
            "清除覆盖即可回落到 .env 的值。",
            "标「需重启服务」的项在启动阶段被读取，改完必须重启才生效。",
            "密钥类配置写入后只显示是否已配置，不回显明文。",
        ],
    }


@router.get("/config", summary="读取全部可调配置（含来源与生效值）")
def admin_get_config(
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """列出每一项配置：当前值、来源、是否可改、改动何时生效。"""
    return _config_payload(runtime, store)


@router.patch("/config", summary="修改配置（即时生效，写库持久化）")
def admin_patch_config(
    changes: dict[str, Any] = Body(..., description="要改的键值；值传 null 表示清除该项覆盖"),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """写入管理台覆盖。

    **值传 `null` 表示清除该项覆盖**（回落到环境变量/默认值）。
    用 null 而不是空字符串表达"清除"，是因为 `llm.api_key` 置空本身是个
    有意义的取值（"我不再用云端了"），与"我没动过这一项"不是一回事。
    混在一起，用户就失去了显式关掉云端的能力。

    响应里带 `restart_required`：不回报的话，改完没生效的人会以为是程序坏了。
    """
    try:
        result = runtime.update(store, changes)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "config": _config_payload(runtime, store)}


@router.post("/config/reset", summary="清除配置覆盖（回落环境变量/默认值）")
def admin_reset_config(
    keys: list[str] | None = Body(default=None, description="要清除的键；省略则清全部"),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    try:
        result = runtime.reset(store, keys)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "config": _config_payload(runtime, store)}


# ======================================================================
# AI 模型
# ======================================================================

def _probe_models(base_url: str, api_key: str, timeout: float = 10.0) -> dict[str, Any]:
    """向配置的接入地址探一次 `/models`，返回**真实**可用模型列表。

    为什么每次都去探、而不是内置一份模型名清单：模型名会随供应商更新而失效，
    写死一份等于给用户一个迟早会撒谎的下拉框 —— 他选中一个早就下线的模型，
    点保存成功、生成报告失败，而错误发生在别处。宁可列表是空的 + 说明原因。

    失败一律返回 `available: false` 并附**可分辨的原因**（没配 / 网络不通 /
    网关没实现这个端点 / 返回体不是预期结构）。这四种的处理方式完全不同，
    笼统给一句"获取失败"等于让人从头查起。

    ⚠️ 密钥不进入任何返回值与异常文本（异常里可能回显 URL，但 URL 里没有 key；
    key 只进请求头）。
    """
    if not base_url:
        return {
            "available": False,
            "reason": "未配置模型接入地址（llm.base_url）",
            "hint": "在配置页填入 OpenAI 兼容的 /v1 地址，例如 https://api.deepseek.com/v1",
        }
    if not api_key:
        return {
            "available": False,
            "reason": "未配置模型密钥（llm.api_key）",
            "hint": "在配置页填入密钥；保存后只显示是否已配置，不再回显明文",
        }

    import httpx

    url = base_url.rstrip("/") + "/models"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            # 本机有系统代理时，连内网模型服务会被代理劫持成"连不上"。
            # 显式禁掉环境代理，避免把"本机代理"误报成"模型服务不可达"。
            trust_env=False,
        )
    except httpx.HTTPError as exc:
        return {
            "available": False,
            "reason": f"无法连接：{type(exc).__name__}",
            "hint": f"确认地址可达且容器能出网：{url}",
            "url": url,
        }

    if resp.status_code == 404:
        return {
            "available": False,
            "reason": "该地址未实现 /models 端点（404）",
            "hint": "可以手动填写模型名 —— 能正常生成报告即可，不必依赖这个列表",
            "url": url,
        }
    if resp.status_code in (401, 403):
        return {
            "available": False,
            "reason": f"鉴权被拒（{resp.status_code}）",
            "hint": "检查 llm.api_key 是否有效、是否有该模型的权限",
            "url": url,
        }
    if resp.status_code >= 400:
        return {
            "available": False,
            "reason": f"服务返回 {resp.status_code}",
            "hint": resp.text[:200],
            "url": url,
        }

    try:
        body = resp.json()
        items = body.get("data") if isinstance(body, dict) else None
        if not isinstance(items, list):
            raise ValueError("返回体里没有 data 数组")
        models = sorted(
            str(m.get("id")) for m in items
            if isinstance(m, dict) and m.get("id")
        )
    except (ValueError, TypeError) as exc:
        return {
            "available": False,
            "reason": f"返回体不是预期的模型列表结构：{exc}",
            "hint": "该网关可能兼容 /chat/completions 但不兼容 /models，手填模型名即可",
            "url": url,
        }

    return {"available": True, "models": models, "count": len(models), "url": url}


@router.get("/ai/models", summary="探取云端模型列表（真实请求，不内置清单）")
def admin_ai_models(
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """向当前配置的接入地址问一次有哪些模型。"""
    llm = runtime.llm(store)
    result = _probe_models(llm["XUANPAN_LLM_BASE_URL"], llm["XUANPAN_LLM_API_KEY"])
    current = llm["XUANPAN_LLM_MODEL"]
    if result.get("available"):
        # 当前模型不在列表里不是错误 —— 有些网关不把私有部署的模型列出来。
        # 但要显式说出来，否则用户会以为"列表里没有 = 配错了"。
        result["current"] = current
        result["current_in_list"] = current in result["models"]
        if current and current not in result["models"]:
            result["note"] = (
                f"当前使用的模型 {current!r} 不在该列表内，"
                "但这不代表它不可用（部分网关不列出私有模型）"
            )
    return result


@router.get("/ai/status", summary="AI 候选链与可用性")
def admin_ai_status(
    request: Request,
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """当前候选链的顺序与可用性 —— 解释"这次报告为什么走了本地模板"。"""
    router_obj = runtime.ai_router(store)
    if router_obj is None:
        return {"available": False, "reason": "xuanpan_ai 未安装，报告功能不可用"}
    llm = runtime.llm(store)
    return {
        "available": True,
        "mode": router_obj.config.mode,
        "cloud_ready": runtime.cloud_ready(store),
        "configured_model": llm["XUANPAN_LLM_MODEL"],
        "configured_base_url": llm["XUANPAN_LLM_BASE_URL"],
        "providers": router_obj.available_providers(),
        "note": (
            "template 是零成本兜底，永远排在最后。云端三项（base_url/api_key/model）"
            "缺任一即不参与选路 —— 这时报告会走本地模板，属于设计内行为，不是故障。"
        ),
    }


__all__ = ["router", "require_admin", "ADMIN_DISABLED_HINT"]
