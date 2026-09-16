"""流派模块化 —— 对应 RULE-006「流派规则必须模块化」。

V1 只开放 `default`，但**扩展接口从第一天就存在**，避免以后把流派判断硬编码进业务。
每个流派把散落各处的可调参数（分金规则表 key、晚子时口径、旺衰阈值、真太阳时开关）
集中成一份 profile，业务层只依赖 profile，不依赖具体数值。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .exceptions import SchoolNotFoundError


@dataclass(frozen=True, slots=True)
class SchoolProfile:
    """流派档案。"""

    id: str
    name: str
    description: str

    # 分金：指向 data/fenjin120.json 中的规则表 key
    fenjin_table: str = "default"

    # 八字：晚子时口径。透传 lunar-python：
    #   2 = 默认：晚子时日柱算当天，时柱按次日日干起
    #   1 = 晚子时日柱算次日，日柱与时柱同源
    bazi_late_zi_sect: int = 2

    # 旺衰阈值
    strong_threshold: float = 0.50
    weak_threshold: float = 0.40

    # 真太阳时：默认仅在用户提供经度时启用
    true_solar_time_required: bool = False

    # 显式声明该流派当前**未覆盖**的规则，供 UI 与 AI 层生成不确定性标注
    unverified: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SCHOOLS: dict[str, SchoolProfile] = {
    "default": SchoolProfile(
        id="default",
        name="默认（通行做法）",
        description="二十四山固定属性 + 通行八字口径 + 扶抑法取用神。V1 唯一开放流派。",
        fenjin_table="default",
        bazi_late_zi_sect=2,
        unverified=(
            "一百二十分金的干支与旺相孤虚标注需规则表，当前未提供",
            "旺衰阈值与用神取法为通行做法之一，非唯一标准",
            "净阴净阳的完整判定属流派规则，当前仅输出坐向阴阳异同",
        ),
    ),
    # ---- 以下为预留档案，V2 实现规则表后开放 ----
    "sanhe": SchoolProfile(
        id="sanhe",
        name="三合派",
        description="以三合五行、净阴净阳、水法为主。规则表待补。",
        fenjin_table="sanhe",
        unverified=("规则表未实现，暂不可用",),
    ),
    "sanyuan": SchoolProfile(
        id="sanyuan",
        name="三元派（玄空）",
        description="以三元九运、飞星、替卦为主。规则表待补。",
        fenjin_table="sanyuan",
        unverified=("规则表未实现，暂不可用",),
    ),
}

DEFAULT_SCHOOL: str = "default"


def get_school(school_id: str | None = None) -> SchoolProfile:
    """取流派档案。未注册的 id **显式报错**，不静默回落默认值。

    Raises:
        SchoolNotFoundError: 流派未注册
    """
    key = school_id or DEFAULT_SCHOOL
    try:
        return SCHOOLS[key]
    except KeyError:
        available = "、".join(SCHOOLS)
        raise SchoolNotFoundError(f"未注册的流派 {key!r}；当前可用：{available}") from None


def list_schools() -> list[dict[str, Any]]:
    """列出全部流派（含未开放者，`available` 字段标明）。"""
    return [{**p.to_dict(), "available": p.id == DEFAULT_SCHOOL} for p in SCHOOLS.values()]


__all__ = ["SchoolProfile", "SCHOOLS", "DEFAULT_SCHOOL", "get_school", "list_schools"]
