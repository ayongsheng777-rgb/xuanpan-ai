"""pytest 根配置：把 monorepo 各包目录加入 sys.path。

为什么用 sys.path 注入而不是 pip install -e：
- 本项目是 monorepo，四个 Python 包分处不同目录
- 开发期零安装步骤 = 零「忘了装」导致的假失败
- 生产部署时才需要打包（见 deploy/）
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).parent.resolve()

# 顺序即优先级：fortune-core 最底层，api 最上层
PACKAGE_ROOTS = [
    ROOT / "packages" / "fortune-core",
    ROOT / "services" / "vision",
    ROOT / "services" / "ai",
    ROOT / "services" / "api",
    ROOT / "services" / "mcp",
]

for path in reversed(PACKAGE_ROOTS):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)
