"""MCP 暴露层测试 —— 通过真实 stdio 协议验证（非直接 import 调用）。

为什么走 stdio 而非直接 call_tool：
MCP server 的入口是 `server.py` 的 stdio 进程，客户端通过 JSON-RPC 消息与之通信。
直接 import server 调 call_tool 会绕过「进程启动 + 握手 + 消息编解码」这些真实链路。
本测试用 mcp 的 stdio_client 启动真实子进程，验证：
1. server 能启动并完成 initialize 握手
2. 6 个工具全部注册
3. 每个工具经 stdio 调用返回 structured_content（非自然语言摘要）
4. 结构化输出内含 facts/tradition 两层（RULE-002 分层）

这些是「MCP 暴露层真的能被外部 Agent 用起来」的硬性证明。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "services" / "mcp" / "server.py"
FORTUNE_CORE = REPO / "packages" / "fortune-core"

pytestmark = pytest.mark.mcp


def _python() -> str:
    return sys.executable


def _params() -> StdioServerParameters:
    return StdioServerParameters(
        command=_python(),
        args=[str(SERVER)],
        env={
            **os.environ,
            "PYTHONPATH": str(FORTUNE_CORE),
        },
    )


@asynccontextmanager
async def _connect():
    """建立真实 stdio 连接并完成握手，返回 ClientSession。"""
    async with stdio_client(_params()) as (read, write):
        async with ClientSession(read, write) as sess:
            init = await sess.initialize()
            assert init.server_info.name == "xuanpan"
            yield sess


async def _call(session: ClientSession, name: str, args: dict[str, Any]) -> Any:
    """调用工具并返回 structuredContent（若非 None）。"""
    result = await session.call_tool(name, args)
    if result.is_error:
        raise AssertionError(f"工具 {name} 返回错误: {result.content}")
    sc = result.structured_content
    # 某些客户端实现里 structuredContent 可能为空，回退到文本解析
    if sc is not None:
        return sc
    # 回退：从 text content 里找（不应发生，但兜底以防 SDK 差异）
    for block in result.content:
        if block.type == "text":
            return block.text
    raise AssertionError(f"工具 {name} 无 structuredContent 也无文本输出")


async def test_server_lists_eight_tools() -> None:
    async with _connect() as session:
        tools = await session.list_tools()
        names = {t.name for t in tools.tools}
        assert names == {
            "xuanpan_bazi", "xuanpan_liuyao", "xuanpan_duan_liuyao", "xuanpan_duan_bazi",
            "xuanpan_almanac", "xuanpan_name", "xuanpan_qian", "xuanpan_compass",
        }

async def test_bazi_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_bazi",
                         {"year": 1990, "month": 5, "day": 20, "hour": 10, "gender": "male"})
        assert sc["facts"]["pillar_list"] == ["庚午", "辛巳", "乙酉", "辛巳"]
        # 大运神煞应已接入 FACT 层
        assert "da_yun" in sc["facts"]
        assert "shen_sha" in sc["facts"]
        # TRADITION 层存在（流派标注）
        assert "tradition" in sc

async def test_liuyao_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_liuyao",
                         {"yao_values": [7, 7, 7, 7, 7, 7], "topic": "财运"})
        # 六爻全阳 → 乾为天
        assert sc["facts"]["gua"]["original_gua"] == "乾"
        # 装卦层字段齐备
        assert "yao_details" in sc["facts"]
        assert "palace" in sc["facts"]
        assert len(sc["facts"]["yao_details"]) == 6

async def test_almanac_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_almanac", {"year": 2026, "month": 9, "day": 17})
        assert sc["facts"]["jian_chu"] == "收"
        assert sc["facts"]["chong"]["zhi"] == "子"
        assert sc["facts"]["xiu"]["name"] == "角"

async def test_name_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_name", {"name": "玄盘"})
        # 字库扩充后「玄盘」必须能算（此前连这都报错）
        assert sc["facts"]["wuge"] == {"天格": 6, "人格": 20, "地格": 16, "外格": 2, "总格": 20}

async def test_qian_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_qian", {"seed": 42})
        assert "number" in sc["facts"]
        assert "title" in sc["facts"]

async def test_compass_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_compass", {"sitting": "午"})
        assert sc["facts"]["sitting"] == "午"
        assert sc["facts"]["facing"] == "子"


async def test_duan_liuyao_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_duan_liuyao",
                         {"yao_values": [7, 7, 7, 7, 7, 7], "topic": "财运"})
        # 装卦 + 断卦两层都在
        assert "divination" in sc
        assert "duan" in sc
        # 断卦给出吉凶倾向（非绝对断语）
        assert sc["duan"]["verdict"] in ("偏吉", "中平", "偏凶")
        assert len(sc["duan"]["uncertainties"]) >= 2


async def test_duan_bazi_structured_content() -> None:
    async with _connect() as session:
        sc = await _call(session, "xuanpan_duan_bazi",
                         {"year": 1990, "month": 5, "day": 20, "hour": 10, "gender": "male"})
        assert "chart" in sc
        assert "duan" in sc
        assert sc["duan"]["verdict"] == "身弱"
        assert sc["duan"]["favorable"] == ["木", "水"]
        # 大运倾向存在且为程度词
        assert sc["duan"]["da_yun_verdicts"]

async def test_invalid_input_returns_error_not_crash() -> None:
    """非法输入应返回**清晰的领域错误**，而非笼统报错或让进程崩溃。"""
    async with _connect() as session:
        result = await session.call_tool("xuanpan_bazi", {"year": 1990, "month": 13, "day": 1, "hour": 0})
        # 13 月非法 → 应报错（is_error=True），且错误消息含具体原因
        assert result.is_error
        text = "".join(c.text for c in result.content if c.type == "text")
        assert "非法公历日期" in text and "13" in text
        # server 仍可用：再调一个合法请求
        sc = await _call(session, "xuanpan_qian", {"seed": 1})
        assert "number" in sc["facts"]
