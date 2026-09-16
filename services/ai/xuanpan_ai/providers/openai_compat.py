"""OpenAI 兼容协议的 LLM provider。

**为什么只做这一个云端实现**：OpenAI 的 `/chat/completions` 协议事实上已是
业界通用接口，OpenAI、DeepSeek、通义千问、智谱、Moonshot、以及自建的
vLLM / Ollama / 企业私有 Gateway 都能直接对接。按品牌各写一个 provider
会得到一堆 90% 相同的复制代码，且每换一个模型都要改代码。

换供应商 = 改配置（`base_url` + `model` + `api_key`），不改业务代码。

设计要点：
- 只用 `httpx`，不引入各家 SDK（SDK 版本冲突是长期维护负担）
- 错误一律转成 `ProviderCallError`，让路由层统一决定"重试还是降级"
- **API key 绝不出现在任何错误消息或日志里**（统一走 `_redact`）
- 不修改 `request.payload`（RULE-002），只读
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ..errors import ProviderCallError
from ..models import Attempt, LLMRequest, LLMResponse, TokenUsage, Turn
from .base import BaseLLMProvider


def _redact(text: str, secret: str) -> str:
    """把 API key 从任意文本中抹掉 —— 错误消息与日志都不得带出密钥。"""
    if not secret:
        return text
    out = text.replace(secret, "***")
    if len(secret) > 8:
        # 有些实现会回显 key 的前后若干位
        out = out.replace(secret[:8], "***")
    return out


class OpenAICompatProvider(BaseLLMProvider):
    """OpenAI 兼容的云端 provider。"""

    name = "openai_compat"
    capability = "reasoning"
    requires_api_key = True

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "",
        capability: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 1,
        extra_headers: dict[str, str] | None = None,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").rstrip("/")
        self.default_model = (model or "").strip()
        self.capability = capability or type(self).capability
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.extra_headers = dict(extra_headers or {})
        self.extra_body = dict(extra_body or {})

    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """缺 key 或 base_url 即不可用 —— **不抛异常**，让路由安静跳过。"""
        return bool(self.api_key and self.base_url and self.default_model)

    def describe(self) -> dict[str, Any]:
        info = super().describe()
        info.update({"base_url": self.base_url, "timeout": self.timeout})
        return info

    # ------------------------------------------------------------------

    def _messages(self, request: LLMRequest) -> list[dict[str, str]]:
        msgs = [{"role": "system", "content": request.system_prompt}]
        for turn in request.history[-12:]:          # 只回带最近若干轮，控制成本
            if isinstance(turn, Turn) and turn.content.strip():
                msgs.append({"role": turn.role, "content": turn.content})
        msgs.append({"role": "user", "content": request.user_message})
        return msgs

    def _payload(self, request: LLMRequest, model: str) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": self._messages(request),
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        body.update(self.extra_body)
        return body

    def interpret(self, request: LLMRequest) -> LLMResponse:
        if not self.is_available():
            # 这个分支正常不会走到（路由会先查 is_available），留作防御
            raise ProviderCallError(
                "provider 未配置完整（需要 api_key / base_url / model）",
                provider=self.name, retryable=False,
            )

        model = request.payload.get("_model_override") or self.default_model
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json", **self.extra_headers}
        headers.setdefault("Authorization", f"Bearer {self.api_key}")

        last_error = ""
        for attempt_no in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=self._payload(request, model))
            except httpx.HTTPError as exc:
                last_error = _redact(f"网络错误：{type(exc).__name__}: {exc}", self.api_key)
                continue

            elapsed = int((time.monotonic() - started) * 1000)

            if resp.status_code >= 400:
                detail = _redact(resp.text[:400], self.api_key)
                last_error = f"HTTP {resp.status_code}：{detail}"
                # 4xx 多为配置/额度问题，重试无意义
                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    break
                continue

            try:
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                last_error = f"返回格式不符合 OpenAI 协议：{type(exc).__name__}: {exc}"
                continue

            if not isinstance(text, str) or not text.strip():
                last_error = "模型返回了空内容"
                continue

            usage_raw = data.get("usage") or {}
            usage = TokenUsage(
                prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
                completion_tokens=int(usage_raw.get("completion_tokens") or 0),
            )
            return LLMResponse(
                text=text.strip(),
                provider=self.name,
                model=str(data.get("model") or model),
                attempts=(Attempt(self.name, model, True, "调用成功", elapsed),),
                usage=usage,
                degraded=False,
            )

        raise ProviderCallError(last_error or "调用失败", provider=self.name)

    # ------------------------------------------------------------------

    @staticmethod
    def extract_json(text: str) -> dict[str, Any]:
        """从模型输出里取出 JSON 对象（有些模型会包 ```json 或加前言）。

        与 vision 层的同名工具用途不同（那边取识别结果），故各自持有、
        互不依赖 —— 两个服务的部署边界是分开的。
        """
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[-1]
            stripped = stripped.rsplit("```", 1)[0]
        try:
            return json.loads(stripped)
        except ValueError:
            start, end = stripped.find("{"), stripped.rfind("}")
            if start >= 0 and end > start:
                return json.loads(stripped[start:end + 1])
            raise


__all__ = ["OpenAICompatProvider", "_redact"]
