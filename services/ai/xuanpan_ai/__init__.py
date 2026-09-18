"""xuanpan-ai —— AI 解释层。

职责边界（严格）：
- **只做**：把 `FortuneContext` 里的结构化结果组织成可读解读
- **不做**：任何术数计算（那是 fortune-core 的事）
- **不做**：修改 facts / tradition（三层物理分离，见 `report`）

对应 RULE-002：AI 的唯一输入是 `FortuneContext.to_ai_payload()`，
它看不到原始照片，也没有任何写入计算结果的通道。

快速上手：

    from fortune_core.context import build_context
    from xuanpan_ai import build_report

    ctx = build_context("session-1", compass=ori, question=QuestionContext("事业", "今年适合换工作吗"))
    report = build_report(ctx)          # 默认走本地模板，零成本、离线
    print(report.interpretation.text)
    print(report.uncertainties)         # 系统保证存在，与模型写不写无关
"""

from __future__ import annotations

from .errors import (
    AIError,
    AllProvidersFailedError,
    ProviderCallError,
    ProviderUnavailableError,
)
from .models import (
    DISCLAIMER,
    REGISTER_EXPERT,
    REGISTER_PLAIN,
    REGISTER_TITLES,
    REQUIRED_SECTIONS,
    Attempt,
    Interpretation,
    LLMRequest,
    LLMResponse,
    Report,
    ReportSection,
    TokenUsage,
    Turn,
)
from .prompt import (
    SYSTEM_ROLE,
    build_system_prompt,
    build_user_message,
    missing_sections,
    parse_sections,
    required_sections_of,
    split_registers,
    unmentioned_uncertainties,
)
from .providers import (
    CAPABILITY_MATRIX,
    ENDPOINT_PRESETS,
    get_provider,
    list_endpoint_presets,
    list_providers,
)
from .report import UNCERTAINTY_SECTION_TITLE, build_report
from .router import AIRouter, RouterConfig

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # 报告装配
    "build_report", "UNCERTAINTY_SECTION_TITLE", "Report",
    "Interpretation", "ReportSection", "DISCLAIMER", "REQUIRED_SECTIONS",
    # 文体（专业分析 / 白话讲解）
    "REGISTER_EXPERT", "REGISTER_PLAIN", "REGISTER_TITLES",
    # 路由
    "AIRouter", "RouterConfig",
    # 调用模型
    "LLMRequest", "LLMResponse", "Attempt", "TokenUsage", "Turn",
    # 提示词
    "SYSTEM_ROLE", "required_sections_of",
    "build_system_prompt", "build_user_message",
    "parse_sections", "missing_sections", "unmentioned_uncertainties",
    "split_registers",
    # provider 元信息（供 API / UI）
    "CAPABILITY_MATRIX", "ENDPOINT_PRESETS", "get_provider",
    "list_providers", "list_endpoint_presets",
    # 错误
    "AIError", "ProviderUnavailableError", "ProviderCallError", "AllProvidersFailedError",
]
