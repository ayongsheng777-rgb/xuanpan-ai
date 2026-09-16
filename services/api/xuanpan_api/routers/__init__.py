"""API 路由集合。每个模块只负责一条链路，共享的装配逻辑在 `deps` 与 `context_builder`。"""

from __future__ import annotations

from fastapi import APIRouter

from . import calc, meta, report, scan, sessions

#：所有业务路由的统一挂载点（前缀 /api/v1 在 app 层加）
API_V1 = APIRouter(prefix="/api/v1")
API_V1.include_router(meta.router)
API_V1.include_router(scan.router)
API_V1.include_router(calc.router)
API_V1.include_router(sessions.router)
API_V1.include_router(report.router)

__all__ = ["API_V1"]
