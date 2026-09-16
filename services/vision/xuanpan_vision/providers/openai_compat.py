"""云端视觉 provider（OpenAI 兼容协议）。

⚠️ **成本声明（AGENTS.md §5.4）**
- 需要**自备 API key**（环境变量 `XUANPAN_VISION_API_KEY`）
- **按量计费**，是本项目最大成本项
- 默认**不启用**；未配置 key 时 `is_available()` 返回 False，不会静默失败

关键设计 —— 即使调用大模型，**角度也由代码算，不由模型给**：
模型只需回答"鱼丝线两端对应哪两个山"（读出盘面印刷的字），
返回山名后由 `fortune_core` 查表得到规范角度。
这样模型**无法注入一个错误的角度值**，是 RULE-002 在识别层的落地。
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from ..models import CompassVisionResult, MountainCandidate
from .base import PreparedCompass

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

#：Vision Prompt —— 与产品方案 §8 保持一致，逐条禁止项都保留
VISION_PROMPT = """你是罗盘图像信息提取器。

你的任务不是进行风水推理。

只识别图片中实际印刷/显示的文字和鱼丝线指向位置。

禁止：
1. 根据风水理论猜测
2. 根据八字补全文字
3. 根据上下文纠正图片中的文字
4. 将"可能是"输出成确定值

如果无法确认，对应字段返回 null。

图片说明：这是一张已经过透视校正、罗盘盘体归一为正圆并居中铺满的图。
0° 方向为画面正上方（正北），角度顺时针增大。

重点识别：
- 鱼丝线（贯通盘面的那条直线）两端所在的二十四山
- 若天池磁针可见，其指向

输出严格 JSON，不要输出任何解释文字：
{
  "compass_detected": true,
  "line_ends": [
    {"name": "午", "confidence": 0.9},
    {"name": "子", "confidence": 0.9}
  ],
  "sitting": {"name": "午", "confidence": 0.9},
  "facing": {"name": "子", "confidence": 0.9},
  "printed_text": [],
  "uncertain_regions": [],
  "needs_user_confirmation": true
}

`line_ends` / `sitting` / `facing` 中的 `name` 必须是以下 24 个字之一：
子 癸 丑 艮 寅 甲 卯 乙 辰 巽 巳 丙 午 丁 未 坤 申 庚 酉 辛 戌 乾 亥 壬
若无法确认，返回 null。
"""

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict[str, Any]:
    """从模型回复中提取 JSON 对象。容忍 ```json 代码围栏与前后解释文字。"""
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text
    match = _JSON_BLOCK.search(candidate)
    if not match:
        raise ValueError("模型回复中未找到 JSON 对象")
    return json.loads(match.group(0))


class OpenAICompatVisionProvider:
    """OpenAI 兼容的视觉模型 provider。"""

    name = "openai_compat"
    capability = "cloud"
    requires_api_key = True

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("XUANPAN_VISION_API_KEY", "")
        self.base_url = (base_url or os.environ.get("XUANPAN_VISION_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("XUANPAN_VISION_MODEL") or DEFAULT_MODEL
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------

    def _build_payload(self, prepared: PreparedCompass) -> dict[str, Any]:
        import base64
        import io

        buf = io.BytesIO()
        prepared.rectified.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                    ],
                }
            ],
        }

    def _call(self, payload: dict[str, Any]) -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------

    def analyze(self, prepared: PreparedCompass) -> CompassVisionResult:
        from fortune_core.mountain24 import MOUNTAIN_BY_NAME, get_mountain, mountain_at

        if not self.is_available():
            return CompassVisionResult.rejected(
                "云端视觉 provider 未配置 API key，请改用本地识别或手动选择",
                provider=self.name,
                quality=prepared.quality,
            )

        try:
            raw = self._call(self._build_payload(prepared))
            data = extract_json(raw)
        except Exception as exc:  # noqa: BLE001 - 网络/解析失败统一降级
            return CompassVisionResult.rejected(
                f"云端识别调用失败：{type(exc).__name__}",
                provider=self.name,
                quality=prepared.quality,
                warnings=("可稍后重试，或改用本地识别 / 手动选择",),
            )

        if not data.get("compass_detected"):
            return CompassVisionResult.rejected(
                "云端模型未能确认图中罗盘，请重新拍摄或手动选择坐向",
                provider=self.name,
                quality=prepared.quality,
            )

        warnings: list[str] = []

        # ---- 山名 → 规范角度：**角度一律由 fortune_core 查表得到** ----
        def to_candidate(item: Any, end: str) -> MountainCandidate | None:
            if not isinstance(item, dict):
                return None
            name = item.get("name")
            if not isinstance(name, str) or name not in MOUNTAIN_BY_NAME:
                if name is not None:
                    warnings.append(f"模型返回了非法山名「{name}」，已丢弃")
                return None
            conf = item.get("confidence")
            conf = float(conf) if isinstance(conf, (int, float)) else 0.5
            conf = max(0.0, min(1.0, conf))
            return MountainCandidate(name, get_mountain(name).center_degree, conf, end)  # type: ignore[arg-type]

        sitting = to_candidate(data.get("sitting"), "sitting")
        facing = to_candidate(data.get("facing"), "facing")

        # 若模型没给 sitting/facing，退回用 line_ends 推导对宫
        if sitting is None or facing is None:
            ends = [to_candidate(e, "unknown") for e in (data.get("line_ends") or [])]
            ends = [e for e in ends if e is not None]
            if ends:
                base = ends[0]
                sitting = MountainCandidate(base.name, base.angle, base.confidence, "sitting")
                opp = mountain_at(base.angle + 180.0)
                facing = MountainCandidate(opp.name, opp.center_degree, base.confidence, "facing")
                warnings.append("模型未直接给出坐/向，已按鱼丝线端点推导对宫")

        if sitting is None or facing is None:
            return CompassVisionResult.rejected(
                "云端模型未给出可用的坐向结果（RULE-003：不确定即返回空）",
                provider=self.name,
                quality=prepared.quality,
                warnings=tuple(warnings),
            )

        # ---- 几何校验：坐向必须互为对宫（由代码判定，不听模型的） ----
        from fortune_core.mountain24 import is_opposite

        if sitting.name == facing.name or not is_opposite(sitting.name, facing.name):
            warnings.append(
                f"模型给出的坐「{sitting.name}」与向「{facing.name}」不构成对宫关系，"
                "已按坐山重新推导向山"
            )
            opp = mountain_at(sitting.angle + 180.0)
            facing = MountainCandidate(opp.name, opp.center_degree, facing.confidence, "facing")

        printed = data.get("printed_text") or []
        printed_tuple = tuple(str(t) for t in printed if isinstance(t, (str, int, float)))
        uncertain = data.get("uncertain_regions") or []

        return CompassVisionResult(
            compass_detected=True,
            center=prepared.center,
            radius=prepared.radius,
            rotation_deg=None,
            mountain_candidates=(sitting,),
            direction_candidates=(facing,),
            printed_text=printed_tuple,
            uncertain_regions=tuple(str(u) for u in uncertain),
            needs_user_confirmation=True,
            provider=self.name,
            quality=prepared.quality,
            warnings=tuple(warnings),
        )


__all__ = [
    "OpenAICompatVisionProvider", "VISION_PROMPT", "extract_json",
    "DEFAULT_BASE_URL", "DEFAULT_MODEL",
]
