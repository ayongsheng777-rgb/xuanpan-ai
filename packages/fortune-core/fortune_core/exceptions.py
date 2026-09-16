"""fortune-core 异常体系。

设计原则：**可判定的失败必须显式抛出，不得静默返回兜底值**。
对应 RULE-008：不得为了「看起来合理」而修正用户数据。

因此本模块区分两类失败：

- `FortuneError` 及其子类：**调用方输入或状态不合法**，必须让调用方知道
- 返回 `None`：**信息不足，无法判定**（对应 RULE-003），不是错误
"""

from __future__ import annotations


class FortuneError(Exception):
    """fortune-core 所有异常的基类。"""


class InvalidInputError(FortuneError):
    """输入不合法（缺字段、越界、类型错误）。"""


class OrientationConflictError(FortuneError):
    """坐山与向山不满足几何关系（应互为 180°）。

    对应材料 §10：识别结果不符合基本几何关系时必须报冲突，而非静默取一个。
    """

    def __init__(self, sitting: str, facing: str, detail: str = "") -> None:
        self.sitting = sitting
        self.facing = facing
        msg = f"坐山「{sitting}」与向山「{facing}」不构成相对关系（应相差 180°）"
        if detail:
            msg = f"{msg}；{detail}"
        super().__init__(msg)


class DomainDataMissingError(FortuneError):
    """领域规则表缺失。

    对应 RULE-001 的反面：**规则表没有时不得凭理论推算**，
    必须显式失败，让上层标注 `[待验证]` 或返回 null。
    """


class SchoolNotFoundError(FortuneError):
    """请求的流派不存在。"""


__all__ = [
    "FortuneError",
    "InvalidInputError",
    "OrientationConflictError",
    "DomainDataMissingError",
    "SchoolNotFoundError",
]
