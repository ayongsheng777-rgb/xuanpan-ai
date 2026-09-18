"""FastAPI 依赖注入 —— 存储、配置、AI 路由器的唯一装配点。

为什么要有这一层，而不是在路由里直接 `Store(...)`：
1. **测试可替换**：测试用 `app.dependency_overrides` 塞临时库，无需碰真实数据目录
2. **配置只解析一次**：环境变量不该在每次请求里重读
3. **异常翻译集中**：领域异常 → HTTP 状态码的映射只有一处，
   否则每个路由各写一遍 `except`，早晚出现"同一个错误两种状态码"

## 两种配置，别混用

| 依赖 | 是什么 | 用它来 |
|---|---|---|
| `get_settings` | **环境基线**。启动时读一次，不随接口改动变化 | 需要"进程启动时的配置"、或要显示"原本配的是什么" |
| `get_active_settings` | 基线 **+ 管理台覆盖** | 请求期真正干活（上传上限、是否留原件…） |

两个都要留着。只有基线的话，界面回答不了"我清掉覆盖会变回什么"；
只有生效值的话，就分不清"这项是配的还是默认的"。见 `runtime_config` 模块头。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import Depends, Request

from .config import DEFAULT_SETTINGS, Settings
from .runtime_config import RuntimeConfig
from .storage import Store


def get_settings() -> Settings:
    """环境基线配置（进程内单例）。"""
    return DEFAULT_SETTINGS


@lru_cache(maxsize=1)
def _default_store(db_path: str) -> Store:
    store = Store(db_path)
    store.init()
    return store


def get_store(settings: Settings = Depends(get_settings)) -> Store:
    """存储实例。按路径缓存 —— 同一个库不会重复 init 建表。"""
    return _default_store(str(settings.db_path))


def get_runtime_config(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> RuntimeConfig:
    """运行时配置服务（进程内单例）。

    挂在 `app.state` 而不是每次请求新建：它内部缓存着 AI 路由器，
    路由器承载降级轨迹等运行态，每请求重建会让这些信息在响应之间丢失。

    按 `settings` 的**同一性**判断缓存是否可用，而不是"有没有构造过"：
    测试会为每个用例传不同的 `Settings`（各自的临时库），只看"有没有"
    会让第二个用例复用第一个用例的配置 —— 表现为"库里的数据对不上"，
    而根因在配置，排查方向容易跑偏。
    """
    cached = getattr(request.app.state, "runtime_config", None)
    if cached is not None and cached.settings is settings:
        return cached
    runtime = RuntimeConfig(settings)
    request.app.state.runtime_config = runtime
    return runtime


def get_active_settings(
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> Settings:
    """生效配置（环境基线 + 管理台覆盖）。

    请求期读配置**一律用这个**，不要用 `get_settings` —— 否则管理台改了配置
    却在业务路径上不生效，接口返回成功、行为毫无变化。
    """
    return runtime.effective_settings(store)


def get_ai_router(
    request: Request,
    store: Store = Depends(get_store),
) -> Any:
    """AI 路由器，按**生效配置**构造；配置一变即自动重建。

    这是"改了模型即时生效"的落点。之前的实现是启动时构造一次挂在
    `app.state.ai_router` 上，于是管理台里换个模型要重启服务才生效 ——
    改配置的接口看起来成功，实际什么都没发生。
    """
    runtime = getattr(request.app.state, "runtime_config", None)
    if runtime is None:  # pragma: no cover - 兜底：未装配运行时配置时退回旧行为
        return getattr(request.app.state, "ai_router", None)
    return runtime.ai_router(store)


__all__ = [
    "get_active_settings",
    "get_ai_router",
    "get_runtime_config",
    "get_settings",
    "get_store",
]
