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

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from .config import Settings
from .deps import get_settings, get_store
from .runtime_config import RuntimeConfig
from .storage import Store

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

    # 运行时配置：环境基线 + 管理台覆盖的合成点。
    # AI 路由器**不在这里构造** —— 它由 RuntimeConfig 按需构建并在配置变化时
    # 自动重建（见 runtime_config.ai_router）。在这里构造一次的话，管理台里
    # 改模型要重启服务才生效，等于"改配置"这个功能只是看起来能用。
    app.state.settings = cfg
    app.state.runtime_config = RuntimeConfig(cfg)

    @app.get("/healthz", tags=["ops"], summary="健康检查")
    def healthz(store: Store = Depends(get_store)) -> dict[str, Any]:
        """健康检查：只报告"进程活着 + 依赖是否齐备"，不触发任何计算。

        报告的是**生效配置**（含管理台覆盖），不是启动时的环境值 ——
        否则改完配置后健康检查还在报告旧值，会让人以为改动没生效。

        取值失败时退回环境基线而不是报错：健康检查本身挂了，容器会被判成
        unhealthy 并重启，而真正的问题可能只是设置表读不出来 —— 用"重启"
        去应对一个配置读取问题，只会把现场冲掉。
        """
        try:
            active = app.state.runtime_config.effective_settings(store)
            cloud_ready = app.state.runtime_config.cloud_ready(store)
            db_ok = True
        except Exception:  # noqa: BLE001
            active, cloud_ready, db_ok = cfg, False, False
        return {
            "status": "ok",
            "db": str(cfg.db_path),
            "settings_db": db_ok,
            "ai_mode": active.ai_mode,
            "cloud_ai_ready": cloud_ready,
            "keep_photos": active.keep_photos,
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
    """（已弃用）启动时构造 AI 路由器。

    保留这个薄壳只为兼容外部引用；应用内部一律走
    `RuntimeConfig.ai_router`，它会在配置变化时自动重建。
    """
    from .runtime_config import build_ai_router

    return build_ai_router(mode=cfg.ai_mode)


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
