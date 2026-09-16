"""xuanpan-api —— 玄盘 AI 后端服务。

职责边界（严格）：
- **只做**：HTTP 语义、输入校验、持久化、把计算层与模型层接起来
- **不做**：任何术数计算（`fortune_core`）、任何图像识别（`xuanpan_vision`）、任何文本生成（`xuanpan_ai`）

启动：

    uvicorn xuanpan_api.app:create_app --factory --port 8352

或：

    python -m xuanpan_api
"""

from __future__ import annotations

from .app import create_app
from .config import Settings
from .context_builder import ContextBuildError
from .deps import get_settings, get_store
from .storage import Store

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "create_app",
    "Settings",
    "Store",
    "ContextBuildError",
    "get_settings",
    "get_store",
]
