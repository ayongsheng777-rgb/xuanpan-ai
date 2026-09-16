"""AI 解释层的错误类型。

分三类，因为调用方对它们的处置完全不同：

- `ProviderUnavailableError` 环境不满足（缺 key / 缺依赖）→ **路由应跳过并试下一个**
- `ProviderCallError`       调用失败（超时 / 5xx / 返回不可解析）→ **路由应降级**
- `AllProvidersFailedError` 全链路失败 → **必须让用户看到明确失败，不得编造报告**
"""

from __future__ import annotations


class AIError(RuntimeError):
    """AI 解释层错误基类。"""


class ProviderUnavailableError(AIError):
    """provider 在当前环境不可用（缺 API key、缺依赖等）。

    与 `ProviderCallError` 的区别：这是**环境问题**，重试无意义，
    路由应直接跳到下一个候选，且不记为"降级"（因为从未真正调用）。
    """

    def __init__(self, message: str, *, provider: str = "") -> None:
        super().__init__(message)
        self.provider = provider


class ProviderCallError(AIError):
    """provider 调用失败。可重试或降级。"""

    def __init__(self, message: str, *, provider: str = "", retryable: bool = True) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable


class AllProvidersFailedError(AIError):
    """所有候选 provider 都失败。

    这是个**必须让用户看见**的错误：绝不能退化成"随便生成一段文本"，
    否则用户会以为那是基于他数据的解读（RULE-003 的延伸）。
    """

    def __init__(self, attempts: list[str]) -> None:
        self.attempts = list(attempts)
        detail = "；".join(self.attempts) if self.attempts else "无可用候选"
        super().__init__(f"全部 AI 模型均不可用或调用失败：{detail}")


__all__ = [
    "AIError", "ProviderUnavailableError",
    "ProviderCallError", "AllProvidersFailedError",
]
