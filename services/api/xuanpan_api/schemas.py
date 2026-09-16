"""API 请求 / 响应契约。

设计原则：**字段名与计算层保持一一对应**，不做"友好改名"。
理由：改名会让 API 文档与内核产生第二套词汇表，日后对不上号。
用户看到的"友好文案"由前端与模板层负责，接口层只传输事实。

`Literal` 类型直接取自 fortune-core 的常量（如 `QuestionCategory`），
而不是在本文件重新抄一份枚举 —— 否则内核新增类别后接口会静默拒绝。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#：问题类别与计算层同源（避免两处枚举漂移）
try:  # pragma: no cover - 导入失败时用兜底，保证 API 仍能启动并报错更明确
    from fortune_core.context import QUESTION_CATEGORIES as _CATEGORIES
except Exception:  # noqa: BLE001
    _CATEGORIES = ("事业", "婚姻", "健康", "财运", "学业", "人际", "出行", "其他")


class ApiModel(BaseModel):
    """统一基类：拒绝未知字段。

    为什么设 `extra="forbid"`：客户端打错字段名（如 `sit` 写成 `sitting`）时，
    若静默忽略，用户会得到一份"用默认值算出来的"错误结果且毫无察觉。
    宁可 422 报错，也不产出静默错误的结果。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ======================================================================
# 会话
# ======================================================================


class SessionCreate(ApiModel):
    """新建会话。所有字段可空 —— 会话可以先生成、再逐步录入。"""

    question_category: str | None = None
    question_text: str | None = None
    title: str | None = None

    @field_validator("question_category")
    @classmethod
    def _check_category(cls, v: str | None) -> str | None:
        if v is not None and v not in _CATEGORIES:
            raise ValueError(f"问题类别须为 {list(_CATEGORIES)} 之一")
        return v


# ======================================================================
# 各模块输入
# ======================================================================


class CompassInput(ApiModel):
    """坐向输入。

    `sitting` 与 `facing` 至少给一个，且必须构成对宫（由计算层强校验）。
    只给 `sitting` 时，向山由对宫推导并自动附警告 —— 这是计算层行为，接口不重复判断。
    """

    sitting: str | None = Field(default=None, description="坐山，如「午」")
    facing: str | None = Field(default=None, description="向山，如「子」")
    degree: float | None = Field(default=None, description="实测朝向角度 0..360（正北 0°，顺时针）")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confirmed_by_user: bool = Field(
        default=False,
        description="是否经用户确认。照片识别结果**必须**为 true 才能进入报告（RULE-004）",
    )
    source: Literal["manual", "vision", "import"] = "manual"
    school: str = "default"


class BaziInput(ApiModel):
    """出生信息。公历为默认口径；农历需显式声明 `calendar="lunar"`。"""

    year: int = Field(ge=1900, le=2100)
    month: int = Field(ge=1, le=12)
    day: int = Field(ge=1, le=31)
    hour: int = Field(ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    calendar: Literal["solar", "lunar"] = "solar"
    gender: Literal["male", "female"] | None = None
    timezone: str = "Asia/Shanghai"
    longitude: float | None = Field(default=None, description="出生地经度（用于真太阳时修正）")
    latitude: float | None = None
    sect: Literal[1, 2] = Field(default=2, description="晚子时日柱口径：1=日柱算次日，2=日柱算当天")


class LiuyaoInput(ApiModel):
    """起卦输入。三种方式三选一，**不接受随机**（RULE-001）。"""

    method: Literal["coins", "yao", "numbers"] = "coins"
    coins: list[list[bool]] | None = Field(
        default=None, description="六爻铜钱结果，每爻 3 枚；true=正面(背)"
    )
    yao_values: list[int] | None = Field(default=None, description="六爻数值 6/7/8/9，自下而上")
    numbers: list[int] | None = Field(default=None, description="梅花易数式起卦数字")
    time_info: dict[str, Any] | None = None

    @field_validator("coins")
    @classmethod
    def _check_coins(cls, v: list[list[bool]] | None) -> list[list[bool]] | None:
        if v is None:
            return v
        if len(v) != 6:
            raise ValueError("摇卦须为 6 爻")
        for i, group in enumerate(v):
            if len(group) != 3:
                raise ValueError(f"第 {i + 1} 爻必须是 3 枚铜钱的结果")
        return v

    @field_validator("yao_values")
    @classmethod
    def _check_yao(cls, v: list[int] | None) -> list[int] | None:
        if v is None:
            return v
        if len(v) != 6:
            raise ValueError("爻值须为 6 个")
        bad = [x for x in v if x not in (6, 7, 8, 9)]
        if bad:
            raise ValueError(f"爻值只能是 6/7/8/9，收到 {bad}")
        return v


class QianInput(ApiModel):
    """抽签。seed 为整数，同一 seed 永远得到同一签（可复现）。"""

    seed: int
    set_id: str = "demo_guanyin"


class NamingInput(ApiModel):
    name: str = Field(min_length=1, max_length=16)


class InputPatch(ApiModel):
    """增量录入：只传本次要设置的模块，其余保持原值。"""

    compass: CompassInput | None = None
    bazi: BaziInput | None = None
    liuyao: LiuyaoInput | None = None
    qian: QianInput | None = None
    naming: NamingInput | None = None
    question_category: str | None = None
    question_text: str | None = None
    title: str | None = None


class CompassConfirm(ApiModel):
    """确认照片识别的坐向（RULE-004 的落点）。

    这是识别链路唯一的"放行闸门"：识别结果**永远**不自动生效，
    必须由用户在此提交。提交即视为用户本人给出的结果。
    """

    sitting: str | None = None
    facing: str | None = None
    degree: float | None = None
    school: str = "default"
    note: str | None = Field(default=None, description="用户修正说明，仅存档")


# ======================================================================
# 报告与追问
# ======================================================================


class ReportRequest(ApiModel):
    question_category: str | None = None
    question_text: str | None = None
    mode: Literal["auto", "cost", "quality"] | None = Field(
        default=None, description="AI 路由模式；留空用服务端默认"
    )
    force_template: bool = Field(
        default=False, description="强制走本地模板（零成本、离线、可复现）"
    )


class AskRequest(ApiModel):
    """多轮追问：只带新问题，上下文由服务端从会话重建。"""

    question_text: str = Field(min_length=1, max_length=2000)
    question_category: str | None = None
    mode: Literal["auto", "cost", "quality"] | None = None
    force_template: bool = False


# ======================================================================
# 响应
# ======================================================================


class SessionCreated(ApiModel):
    session_id: str
    created_at: str
    title: str = ""


class ScanAccepted(ApiModel):
    """照片识别结果。

    刻意不在顶层返回 `facts`：识别只是"候选"，还不是盘面事实。
    用户确认后由 `/sessions/{id}/compass/confirm` 产出真正的坐向。
    """

    session_id: str
    compass_detected: bool
    needs_user_confirmation: Literal[True] = True
    provider: str
    quality: dict[str, Any] | None = None
    center: tuple[float, float] | None = None
    radius: float | None = None
    mountain_candidates: list[dict[str, Any]] = Field(default_factory=list)
    direction_candidates: list[dict[str, Any]] = Field(default_factory=list)
    uncertain_regions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LayerPreview(ApiModel):
    """某模块的两层只读结果（供 UI 预览，不落库）。"""

    facts: dict[str, Any]
    tradition: dict[str, Any]
    uncertainties: list[str] = Field(default_factory=list)


class DeletedResponse(ApiModel):
    deleted: bool
    session_id: str


__all__ = [
    "ApiModel", "SessionCreate", "CompassInput", "BaziInput", "LiuyaoInput",
    "QianInput", "NamingInput", "InputPatch", "CompassConfirm",
    "ReportRequest", "AskRequest",
    "SessionCreated", "ScanAccepted", "LayerPreview", "DeletedResponse",
]
