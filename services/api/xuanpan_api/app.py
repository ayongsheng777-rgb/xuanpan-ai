"""FastAPI 应用装配。

分层：
    app.py（装配 + 异常翻译）
      └── routers/（HTTP 语义）
            └── context_builder（唯一与计算层耦合处）
                  └── fortune_core（确定性内核）

异常处理集中在这里，是为了保证**同一个领域错误在任何接口上都返回同一个状态码**。
分散到各路由写 `except`，迟早出现"这里 400、那里 422"的不一致。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .config import Settings
from .deps import get_settings

logger = logging.getLogger("xuanpan.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    """构造应用。测试可传入自定义 `settings`（如临时库路径）。"""
    cfg = settings or get_settings()

    app = FastAPI(
        title="玄盘 AI · 后端服务",
        version="0.1.0",
        description=(
            "确定性术数计算 + AI 解释的接口层。\n\n"
            "**硬性边界**：所有数值由 fortune-core 计算，AI 不参与计算，也不得修改结果。"
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _register_error_handlers(app)
    _mount_routers(app)

    # AI 路由器：进程内单例（挂在 state 上，供 deps.get_ai_router 取用）
    app.state.settings = cfg
    app.state.ai_router = _build_ai_router(cfg)

    @app.get("/healthz", tags=["ops"], summary="健康检查")
    def healthz() -> dict[str, Any]:
        """健康检查：只报告"进程活着 + 依赖是否齐备"，不触发任何计算。"""
        return {
            "status": "ok",
            "db": str(cfg.db_path),
            "ai_mode": cfg.ai_mode,
            "keep_photos": cfg.keep_photos,
        }

    return app


def _mount_routers(app: FastAPI) -> None:
    from .routers import API_V1

    app.include_router(API_V1)

    @app.get("/", include_in_schema=False)
    def index() -> dict[str, str]:
        return {
            "service": "玄盘 AI",
            "docs": "/docs",
            "api": "/api/v1",
            "admin": "/admin",
        }

    @app.get("/admin", include_in_schema=False, response_class=HTMLResponse)
    def admin_page() -> HTMLResponse:
        """管理台页面。

        **页面本身不含任何数据、也不需要令牌** —— 它只是一张空壳，
        真正的数据一律经 `/api/v1/admin/*` 取，鉴权在那里。
        这样拆的理由：若连页面都要令牌，用户会陷进一个死循环 ——
        「打不开页面 → 不知道要配什么 → 更打不开」。空壳页面正是那个入口。

        文件缺失时返回 503 并说明原因（而不是 500）：这种情况几乎总是
        镜像构建漏了 `COPY services/`，属于部署问题，说清楚比给个堆栈有用。
        """
        page = Path(__file__).resolve().parent / "static" / "admin.html"
        if not page.exists():
            return HTMLResponse(
                content=(
                    "<h1>管理台资源缺失</h1>"
                    f"<p>找不到 {page}。</p>"
                    "<p>若运行在容器中，请确认镜像构建时 <code>COPY services/</code> 覆盖了 "
                    "<code>services/api/xuanpan_api/static/</code>。</p>"
                ),
                status_code=503,
            )
        return HTMLResponse(content=page.read_text(encoding="utf-8"))


def _build_ai_router(cfg: Settings):  # type: ignore[no-untyped-def]
    """按配置构造 AI 路由器。导入失败时返回 None，让纯计算功能仍可用。"""
    try:
        from xuanpan_ai import AIRouter, RouterConfig
    except ImportError:  # pragma: no cover
        logger.warning("xuanpan_ai 不可用：报告功能将不可用，计算功能不受影响")
        return None
    try:
        return AIRouter(config=RouterConfig(mode=cfg.ai_mode))
    except ValueError:
        logger.warning("XUANPAN_AI_MODE=%r 非法，回退 auto", cfg.ai_mode)
        return AIRouter(config=RouterConfig(mode="auto"))


def _register_error_handlers(app: FastAPI) -> None:
    """领域异常 → HTTP 状态码的唯一映射点。"""
    from fortune_core import FortuneError

    from .context_builder import ContextBuildError

    @app.exception_handler(FortuneError)
    async def _domain_error(request: Request, exc: FortuneError) -> JSONResponse:
        """内核抛出的领域错误 → 400。

        为什么必须单独注册：`FortuneError` 继承 `Exception`，**不是 `ValueError`**。
        下面那个 `ValueError` 处理器抓不到它 —— 若不注册，
        「未注册的择日事件」「未注册的流派」这类明显的调用方错误会变成 500，
        而 500 的语义是「服务坏了」，会把用户引向完全错误的排查方向。

        注册顺序不影响匹配：Starlette 按异常的 MRO 找**最具体**的处理器，
        所以 `ContextBuildError`（`FortuneError` 的子类）仍走它自己的分支。
        """
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc), "error": type(exc).__name__},
        )

    @app.exception_handler(ContextBuildError)
    async def _build_error(request: Request, exc: ContextBuildError) -> JSONResponse:
        """用户输入无法构成有效上下文 → 400。

        **不返回 500**：这类错误的原因是"用户给的东西不成立"（山名写错、坐向冲突、
        生辰不全），前端需要把可执行的原因展示给用户；500 只会让人以为是服务坏了。
        """
        return JSONResponse(status_code=400, content={"detail": str(exc), "error": "ContextBuildError"})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:  # pragma: no cover
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务内部错误", "error": type(exc).__name__},
        )

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        """值错误按"输入不合法"处理（400）。

        计算层用 `ValueError` 表达参数非法（如问题类别不在枚举内），
        它属于调用方的问题，不是服务故障。
        """
        return JSONResponse(status_code=400, content={"detail": str(exc), "error": "ValueError"})


__all__ = ["create_app"]
