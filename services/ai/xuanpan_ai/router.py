"""AI 路由 —— 按能力选路 + 故障自动降级（设计规范 §十一、§二十一）。

    payload(FortuneContext)
            ↓
      候选排序（按模式）
            ↓
      逐个尝试 ──失败──► 记录 Attempt ──► 下一个
            ↓ 成功
        返回文本（同时带回"是否降级"与尝试轨迹，供 UI 显示）

**降级绝不改变计算结果**（§二十一末）：router 只返回文本，
新增的 `facts` / `tradition` 永远来自调用方的 `FortuneContext`，
模型连写入它们的通道都没有。

**只读载荷守卫**：每次调用前后对 `payload` 取指纹。若 provider 改动了它，
改动会被丢弃、载荷被还原，并记一条 warning。这不是假想的威胁 ——
"顺手在 payload 上补个字段"是很自然的写法，而它正好会破坏
"AI 不参与计算"这一条底线。
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Literal, Mapping, Sequence

from .errors import AllProvidersFailedError, ProviderCallError, ProviderUnavailableError
from .models import Attempt, LLMRequest, LLMResponse, Turn
from .prompt import build_system_prompt, build_user_message
from .providers import get_provider

Mode = Literal["auto", "cost", "quality"]
Task = Literal["report", "followup"]

_TEMPLATE_CAPABILITY = "template"


def _fingerprint(payload: dict[str, Any]) -> str:
    """载荷指纹 —— 用于检测 provider 是否改动了只读数据。"""
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _capability_rank(provider: Any) -> int:
    """能力强弱：reasoning 最强，fast 次之，local 再次，template 最弱。"""
    return {
        "reasoning": 3,
        "fast": 2,
        "local": 1,
        _TEMPLATE_CAPABILITY: 0,
    }.get(getattr(provider, "capability", ""), 1)


def _cost_rank(provider: Any) -> int:
    """成本：越小越省。未声明者按"可能是付费云"处理（保守）。"""
    return int(getattr(provider, "cost_rank", 2))


@dataclass(frozen=True, slots=True)
class RouterConfig:
    mode: Mode = "auto"
    max_tokens: int = 2048
    temperature: float = 0.7
    history_limit: int = 12

    def __post_init__(self) -> None:
        if self.mode not in ("auto", "cost", "quality"):
            raise ValueError(f"mode 须为 auto/cost/quality，收到 {self.mode!r}")


class AIRouter:
    """模型路由器。**无状态**，可复用。"""

    def __init__(
        self,
        providers: Sequence[Any] | None = None,
        config: RouterConfig | None = None,
        llm: Mapping[str, str] | None = None,
    ) -> None:
        self.config = config or RouterConfig()
        # 未显式传入时：本地模板兜底 + 从配置构造的云端 provider（若已配置）。
        # `llm` 是**已解析**的云端配置；不传则回落到读环境变量（见 _default_chain）。
        self._providers: list[Any] = (
            list(providers) if providers is not None else _default_chain(llm)
        )

    # ------------------------------------------------------------------

    def _ordered(self, task: Task) -> list[Any]:
        """按模式排序候选。**template 永远排在最后**（它是兜底，不是首选）。"""
        cfg = self.config
        available = [p for p in self._providers if _safe_available(p)]
        unavailable = [p for p in self._providers if not _safe_available(p)]

        real = [p for p in available if getattr(p, "capability", "") != _TEMPLATE_CAPABILITY]
        fallback = [p for p in available if getattr(p, "capability", "") == _TEMPLATE_CAPABILITY]

        mode = cfg.mode
        if mode == "cost" or (mode == "auto" and task == "followup"):
            # 省钱优先：先便宜的，同价位再挑能力强的
            real.sort(key=lambda p: (_cost_rank(p), -_capability_rank(p)))
        else:
            # quality 或 auto+report：能力强优先，同档再挑便宜的
            real.sort(key=lambda p: (-_capability_rank(p), _cost_rank(p)))

        # 不可用的一律排除，避免把"缺 key"当成"调用失败"混进降级轨迹
        _ = unavailable
        return real + fallback

    # ------------------------------------------------------------------

    def generate(
        self,
        payload: dict[str, Any],
        *,
        question: str = "",
        history: Iterable[Turn] = (),
        task: Task = "report",
    ) -> LLMResponse:
        """生成解读文本。全部候选失败时抛 `AllProvidersFailedError`。

        Args:
            payload: `FortuneContext.to_ai_payload()` 的结果 —— **只读**
            task: report（报告主生成）/ followup（追问，倾向省钱快速）
        """
        candidates = self._ordered(task)
        if not candidates:
            raise AllProvidersFailedError(["没有任何可用候选（未配置 key 且模板 provider 缺失）"])

        session_id = str(payload.get("session_id") or "")
        system_prompt = build_system_prompt(payload)
        user_message = build_user_message(payload, question=question)
        turns = tuple(history)[-self.config.history_limit:]

        pristine = copy.deepcopy(payload)
        before = _fingerprint(payload)

        attempts: list[Attempt] = []
        problems: list[str] = []

        for index, provider in enumerate(candidates):
            name = getattr(provider, "name", type(provider).__name__)
            model = getattr(provider, "default_model", "") or ""
            request = LLMRequest(
                session_id=session_id,
                payload=payload,
                system_prompt=system_prompt,
                user_message=user_message,
                history=turns,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            try:
                response = provider.interpret(request)
            except ProviderUnavailableError as exc:
                attempts.append(Attempt(name, model, False, f"环境不可用：{exc}"))
                continue
            except ProviderCallError as exc:
                attempts.append(Attempt(name, model, False, str(exc)))
                continue
            except Exception as exc:  # noqa: BLE001 - 任何 provider 缺陷都不应中断降级链
                attempts.append(Attempt(name, model, False, f"{type(exc).__name__}: {exc}"))
                continue
            finally:
                # ---- 只读载荷守卫：无论成败，都检查并还原 ----
                if _fingerprint(payload) != before:
                    payload.clear()
                    payload.update(pristine)
                    problems.append(
                        f"provider「{name}」改动了只读的计算结果，改动已被丢弃并还原"
                    )

            # 成功
            merged_attempts = (*attempts, *response.attempts)
            degraded = index > 0
            if degraded:
                problems.append(
                    f"主候选不可用或失败，已自动切换到「{response.provider}」"
                )
            return LLMResponse(
                text=response.text,
                provider=response.provider,
                model=response.model,
                attempts=merged_attempts,
                usage=response.usage,
                degraded=degraded,
                warnings=response.warnings + tuple(problems),
            )

        raise AllProvidersFailedError([f"{a.provider}：{a.detail}" for a in attempts])

    # ------------------------------------------------------------------

    def available_providers(self) -> list[dict[str, Any]]:
        """供 UI「AI 连接状态」（§二十）展示。"""
        out: list[dict[str, Any]] = []
        for p in self._providers:
            entry = {"name": getattr(p, "name", "?"), "capability": getattr(p, "capability", "")}
            if hasattr(p, "describe"):
                entry.update(p.describe())
            entry["available"] = _safe_available(p)
            out.append(entry)
        return out


def _safe_available(provider: Any) -> bool:
    """`is_available` 自身抛异常时按不可用处理（探测不应让整个路由崩掉）。"""
    try:
        return bool(provider.is_available())
    except Exception:  # noqa: BLE001
        return False


def _default_chain(llm: Mapping[str, str] | None = None) -> list[Any]:
    """默认候选链：配置了云端就用云端，模板永远兜底。

    环境变量（与设计规范 §十 的配置项对应）：
        XUANPAN_LLM_BASE_URL / XUANPAN_LLM_API_KEY / XUANPAN_LLM_MODEL
        XUANPAN_LLM_CAPABILITY（reasoning / fast / local）

    Args:
        llm: **已解析**的云端配置，键名与环境变量同名。为 None 时读 `os.environ`
            —— 保留原行为，让不需要配置层的调用方（内核测试）不必先造一份配置。

    为什么 `llm` 非 None 时**不再回落** `os.environ`：解析层已经把「环境变量 +
    管理台覆盖」合并好了。这里再回落一次等于引入第二个真源，会出现最难查的
    一类问题 —— 界面上显示用的是 A 模型、实际调的是 B，而且两边各自看都对。
    """
    import os

    if llm is None:
        def read(name: str) -> str:
            return os.environ.get(name, "").strip()
    else:
        def read(name: str) -> str:
            return str(llm.get(name) or "").strip()

    chain: list[Any] = []
    base_url = read("XUANPAN_LLM_BASE_URL")
    api_key = read("XUANPAN_LLM_API_KEY")
    model = read("XUANPAN_LLM_MODEL")
    if base_url and api_key and model:
        capability = read("XUANPAN_LLM_CAPABILITY") or "reasoning"
        chain.append(
            get_provider(
                "openai_compat", api_key=api_key, base_url=base_url,
                model=model, capability=capability,
            )
        )
    chain.append(get_provider("template"))
    return chain


__all__ = ["Mode", "Task", "RouterConfig", "AIRouter"]
