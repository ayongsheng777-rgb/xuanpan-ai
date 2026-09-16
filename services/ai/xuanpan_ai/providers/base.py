"""LLM Provider 抽象 —— 按**能力**分层，不按品牌（设计规范 §八）。

    reasoning   强推理模型（报告主生成）
    fast        快而省的对话模型（追问）
    local       本地/自建网关（Ollama、vLLM、企业私有 Gateway）
    template    零成本确定性生成（无网络、无 key，默认兜底）

为什么坚持抽象：模型是本项目最大的成本项与最大的可用性风险。
抽象层让"换模型"变成改配置而不是改代码，也让"全部模型都不可用"时
仍有一条**不编造**的诚实路径（template）。

**同步还是异步**：协议定为同步 `interpret`，因为确定性 provider 与
单元测试都天然是同步的。需要异步时由 `BaseLLMProvider.ainterpret`
用 `asyncio.to_thread` 包装 —— 不在每个 provider 里复制一套 async 实现。
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol, runtime_checkable

from ..models import LLMRequest, LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """文本生成 provider 协议。"""

    name: str
    capability: str              # reasoning / fast / local / template
    requires_api_key: bool

    def is_available(self) -> bool:
        """当前环境是否可用（缺 key / 缺依赖时返回 False，不抛异常）。"""
        ...

    def interpret(self, request: LLMRequest) -> LLMResponse:
        """生成解读文本。

        **不得修改 `request.payload`** —— 它是计算层的只读结果（RULE-002）。
        路由层会校验这一点，被改动的 provider 会被记录并丢弃改动。
        """
        ...


class BaseLLMProvider:
    """给 provider 提供的公共实现（异步包装、模型信息）。"""

    name = "base"
    capability = "template"
    requires_api_key = False
    default_model = ""

    #: 供 UI「模型信息展示」用（设计规范 §25）
    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capability": self.capability,
            "requires_api_key": self.requires_api_key,
            "model": self.default_model,
        }

    async def ainterpret(self, request: LLMRequest) -> LLMResponse:
        """异步包装 —— 供 FastAPI 的路由使用。"""
        return await asyncio.to_thread(self.interpret, request)  # type: ignore[attr-defined]


__all__ = ["LLMProvider", "BaseLLMProvider"]
