"""Vision Provider 注册表 —— 按**能力**取用，不按品牌。

    classical       本地经典 CV，零成本、离线、可复现（默认）
    openai_compat   云端视觉大模型，需自备 key（按量计费）
    manual          用户直接指定，RULE-004 兜底

新增 provider 只需在此注册，业务层不改。
"""

from __future__ import annotations

from typing import Any, Callable

from .base import PreparedCompass, ProviderUnavailableError, VisionProvider
from .classical import ClassicalVisionProvider
from .manual import ManualVisionProvider
from .openai_compat import OpenAICompatVisionProvider

Type = Callable[..., VisionProvider]

REGISTRY: dict[str, Type] = {
    "classical": ClassicalVisionProvider,
    "openai_compat": OpenAICompatVisionProvider,
    "manual": ManualVisionProvider,
}

DEFAULT_PROVIDER = "classical"

#：**输出即用户输入**的 provider —— 由注册表声明，不由 provider 自称。
#：
#：为什么需要这个概念：`manual` 路径下坐向本来就是用户自己在环形选择器上
#：指定的，再要求"请确认识别结果"是自欺欺人。但**不能**把这个权力交给
#：provider 自己声明 —— 否则任何第三方 provider 都能把 RULE-004 的确认
#：闸门关掉。故：只有注册表里登记过的 id 才被认可（见 `is_user_authoritative`）。
USER_AUTHORITATIVE_PROVIDERS: frozenset[str] = frozenset({"manual"})

#：能力矩阵（供 UI「我的 → AI 模型」页展示，用户据此选择）
CAPABILITY_MATRIX: tuple[dict[str, Any], ...] = (
    {
        "id": "classical",
        "name": "本地几何识别",
        "capability": "local",
        "requires_api_key": False,
        "cost": "免费（本地计算）",
        "reads_printed_text": False,
        "description": "测量鱼丝线与磁针角度，输出对宫候选，需用户确认哪端为坐山",
    },
    {
        "id": "openai_compat",
        "name": "云端视觉模型",
        "capability": "cloud",
        "requires_api_key": True,
        "cost": "按量计费（自备 key）",
        "reads_printed_text": True,
        "description": "可直接读出盘面印刷文字，适用于任意盘式；调用成本为项目最大支出项",
    },
    {
        "id": "manual",
        "name": "手动选择",
        "capability": "manual",
        "requires_api_key": False,
        "cost": "免费",
        "reads_printed_text": False,
        "description": "完全由用户指定坐向，不经过任何模型；识别失败时的兜底路径",
    },
)


def get_provider(name: str | None = None, **kwargs: Any) -> VisionProvider:
    """取 provider 实例。未知名字抛 KeyError 并列出可用项。

    返回的实例会被**盖上** `registry_id` 印记（构造之后覆盖写入），
    使 `is_user_authoritative` 无法被 provider 自身伪造。
    """
    key = name or DEFAULT_PROVIDER
    try:
        cls = REGISTRY[key]
    except KeyError:
        raise KeyError(f"未注册的 vision provider：{key!r}；可用：{sorted(REGISTRY)}") from None
    instance = cls(**kwargs)
    try:
        instance.registry_id = key          # type: ignore[attr-defined]
    except AttributeError:                  # pragma: no cover - 只读实例
        pass
    return instance


def is_user_authoritative(provider: Any) -> bool:
    """该 provider 的输出是否**等同于用户本人的输入**。

    只有注册表登记过的 id 才算；直接构造的第三方实例一律不算，
    从而保持 RULE-004「识别结果必须经用户确认」的有效性。
    """
    return getattr(provider, "registry_id", None) in USER_AUTHORITATIVE_PROVIDERS


def list_providers() -> list[dict[str, Any]]:
    """列出 provider 及其在当前环境的可用性。"""
    out = []
    for entry in CAPABILITY_MATRIX:
        try:
            instance = get_provider(entry["id"])
            available = instance.is_available()
        except Exception:  # noqa: BLE001 - 环境探测失败按不可用处理
            available = False
        out.append({**entry, "available": available})
    return out


__all__ = [
    "REGISTRY", "DEFAULT_PROVIDER", "CAPABILITY_MATRIX",
    "USER_AUTHORITATIVE_PROVIDERS", "is_user_authoritative",
    "get_provider", "list_providers",
    "VisionProvider", "PreparedCompass", "ProviderUnavailableError",
    "ClassicalVisionProvider", "OpenAICompatVisionProvider", "ManualVisionProvider",
]
