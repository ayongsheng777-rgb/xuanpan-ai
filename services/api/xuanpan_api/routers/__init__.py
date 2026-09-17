"""API 路由集合。每个模块只负责一条链路，共享的装配逻辑在 `deps` 与 `context_builder`。

分两组：

- **会话域**（`sessions` / `scan` / `calc` / `report`）：围绕「一个盘面」展开，
  输入落库、可生成报告。`calc` 是无状态预览，语义上仍属这一组。
- **查询域**（`almanac` / `zeri` / `duan` / `qimen` / `liuren` / `taiyi`）：
  无状态查询，不落库、不进 `FortuneContext`、也没有报告。`duan` 虽是「解读」，
  但它解读的是**本次请求里传进来的排盘结果**，不依赖会话。
  `qimen` / `liuren` / `taiyi` 即三式（奇门遁甲 / 大六壬 / 太乙神数）——
  三者至此全部接入。
- **运维域**（`admin`）：自带令牌鉴权。它与会话域**读同一份数据**，
  但**不共用端点** —— 会话域是给 App 用的、没有鉴权，
  管理界面若直接调它就等于没有保护（知道 URL 即可绕过）。

`meta` 为各组共用。
"""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    admin,
    almanac,
    calc,
    duan,
    liuren,
    meta,
    qimen,
    report,
    scan,
    sessions,
    taiyi,
    zeri,
)

#：所有业务路由的统一挂载点（前缀 /api/v1 在 app 层加）
API_V1 = APIRouter(prefix="/api/v1")
API_V1.include_router(meta.router)
API_V1.include_router(scan.router)
API_V1.include_router(calc.router)
API_V1.include_router(almanac.router)
API_V1.include_router(zeri.router)
API_V1.include_router(duan.router)
API_V1.include_router(qimen.router)
API_V1.include_router(liuren.router)
API_V1.include_router(taiyi.router)
API_V1.include_router(sessions.router)
API_V1.include_router(report.router)
API_V1.include_router(admin.router)

__all__ = ["API_V1"]
