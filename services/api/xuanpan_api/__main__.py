"""`python -m xuanpan_api` 入口 —— 起一个开发用服务。

生产建议用 `uvicorn xuanpan_api.app:create_app --factory` 并交给进程管理器，
本模块只负责"本地能一条命令跑起来"。
"""

from __future__ import annotations

import os

from .app import create_app


def main() -> None:  # pragma: no cover - 需真实起服务
    import uvicorn

    host = os.environ.get("XUANPAN_HOST", "127.0.0.1")
    port = int(os.environ.get("XUANPAN_PORT", "8352"))
    reload_enabled = os.environ.get("XUANPAN_RELOAD", "").strip().lower() in ("1", "true", "yes")

    uvicorn.run(create_app(), host=host, port=port, reload=reload_enabled)


if __name__ == "__main__":  # pragma: no cover
    main()
