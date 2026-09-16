"""LLM Provider 注册表 —— 按能力取用，不按品牌（设计规范 §八）。

    template       本地规则模板，零成本、离线、确定性（默认兜底）
    openai_compat  OpenAI 兼容协议的云端/本地模型

`ENDPOINT_PRESETS` 只提供 **base_url**，不预置模型名：
模型名随各家账户与版本变化，预置一个写死的名字迟早变成错误信息。
用户在「模型配置中心」按自己账户的可用列表填写即可。
"""

from __future__ import annotations

from typing import Any, Callable

from .base import BaseLLMProvider, LLMProvider
from .openai_compat import OpenAICompatProvider
from .template import TemplateProvider

Type = Callable[..., LLMProvider]

REGISTRY: dict[str, Type] = {
    "template": TemplateProvider,
    "openai_compat": OpenAICompatProvider,
}

DEFAULT_PROVIDER = "template"

#：能力矩阵（供 UI「AI 模型中心」展示，用户据此选择）
CAPABILITY_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "id": "template",
        "name": "本地规则模板",
        "capability": "template",
        "requires_api_key": False,
        "cost": "免费（无网络调用）",
        "description": "确定性句式生成，永不失败、永不编造；措辞机械，不含个性化推演",
    },
    {
        "id": "openai_compat",
        "name": "云端 / 自建模型（OpenAI 兼容）",
        "capability": "reasoning",
        "requires_api_key": True,
        "cost": "按量计费（自备 key）或本地零成本",
        "description": "覆盖 OpenAI / DeepSeek / 通义 / 智谱 / Moonshot 及自建 vLLM、Ollama；换模型只改配置",
    },
)

#：常见端点。**不含模型名** —— 模型名请按自己账户可用列表填写。
ENDPOINT_PRESETS: tuple[dict[str, str], ...] = (
    {"id": "openai", "name": "OpenAI", "base_url": "https://api.openai.com/v1",
     "requires_api_key": "yes", "note": "国内直连通常不可达，需自备线路"},
    {"id": "deepseek", "name": "DeepSeek", "base_url": "https://api.deepseek.com/v1",
     "requires_api_key": "yes", "note": "国内可直连"},
    {"id": "dashscope", "name": "通义千问（DashScope）",
     "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
     "requires_api_key": "yes", "note": "国内可直连"},
    {"id": "zhipu", "name": "智谱 GLM", "base_url": "https://open.bigmodel.cn/api/paas/v4",
     "requires_api_key": "yes", "note": "国内可直连"},
    {"id": "moonshot", "name": "Moonshot Kimi", "base_url": "https://api.moonshot.cn/v1",
     "requires_api_key": "yes", "note": "国内可直连"},
    {"id": "ollama", "name": "本地 Ollama", "base_url": "http://127.0.0.1:11434/v1",
     "requires_api_key": "no", "note": "本地零成本；key 随便填非空值"},
    {"id": "vllm", "name": "自建 vLLM", "base_url": "http://127.0.0.1:8000/v1",
     "requires_api_key": "no", "note": "自建服务；key 随便填非空值"},
)


def get_provider(name: str | None = None, **kwargs: Any) -> LLMProvider:
    """取 provider 实例。未知名字抛 KeyError 并列出可用项。"""
    key = name or DEFAULT_PROVIDER
    try:
        cls = REGISTRY[key]
    except KeyError:
        raise KeyError(
            f"未注册的 LLM provider：{key!r}；可用：{sorted(REGISTRY)}"
        ) from None
    instance = cls(**kwargs)
    try:
        instance.registry_id = key          # type: ignore[attr-defined]
    except AttributeError:                  # pragma: no cover
        pass
    return instance


def list_providers() -> list[dict[str, Any]]:
    """列出 provider 及当前环境可用性（供 UI 展示）。"""
    out: list[dict[str, Any]] = []
    for entry in CAPABILITY_MATRIX:
        try:
            available = get_provider(entry["id"]).is_available()
        except Exception:  # noqa: BLE001 - 环境探测失败按不可用处理
            available = False
        out.append({**entry, "available": available})
    return out


def list_endpoint_presets() -> list[dict[str, str]]:
    """常见端点预设（UI「模型配置中心」用）。"""
    return [dict(p) for p in ENDPOINT_PRESETS]


__all__ = [
    "REGISTRY", "DEFAULT_PROVIDER", "CAPABILITY_MATRIX", "ENDPOINT_PRESETS",
    "get_provider", "list_providers", "list_endpoint_presets",
    "LLMProvider", "BaseLLMProvider",
    "TemplateProvider", "OpenAICompatProvider",
]
