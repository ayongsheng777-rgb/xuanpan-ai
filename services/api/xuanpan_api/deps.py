"""FastAPI 依赖注入 —— 存储、配置、AI 路由器的唯一装配点。

为什么要有这一层，而不是在路由里直接 `Store(...)`：
1. **测试可替换**：测试用 `app.dependency_overrides` 塞临时库，无需碰真实数据目录
2. **配置只解析一次**：`Settings` 读环境变量，不该在每次请求里重读
3. **异常翻译集中**：领域异常 → HTTP 状态码的映射只有一处，
   否则每个路由各写一遍 `except`，早晚出现"同一个错误两种状态码"
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import Depends, Request

from .config import DEFAULT_SETTINGS, Settings
from .storage import Store


def get_settings() -> Settings:
    """运行时配置（进程内单例）。"""
    return DEFAULT_SETTINGS


@lru_cache(maxsize=1)
def _default_store(db_path: str) -> Store:
    store = Store(db_path)
    store.init()
    return store


def get_store(settings: Settings = Depends(get_settings)) -> Store:
    """存储实例。按路径缓存 —— 同一个库不会重复 init 建表。"""
    return _default_store(str(settings.db_path))


def get_ai_router(request: Request) -> Any:
    """AI 路由器（进程内单例，挂在 app.state 上）。

    为什么挂在 app.state：路由器持有 provider 配置与降级策略，
    每次请求重建会丢失"上次调用是否处于降级状态"这类运行态信息。
    """
    return getattr(request.app.state, "ai_router", None)


__all__ = ["get_settings", "get_store", "get_ai_router"]
