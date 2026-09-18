"""坐向模型 —— 罗盘计算的结果形态与几何校验。

对应材料 §10「坐向模型」：
- 坐山 ≠ 向山
- 坐山与向山应处于**相对方位**（相差 180°）
- 不符时显式报冲突，**不得静默取一个结果**

同时提供三层报告所需的两层数据：
- `to_facts()`  → FACT 层：纯计算结果，AI 不可修改
- `to_tradition()` → TRADITION 层：传统术数规则的解释性字段
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .constants import ELEMENT_CN, ELEMENT_CONTROLS, ELEMENT_GENERATES
from .exceptions import InvalidInputError, OrientationConflictError
from .fenjin120 import FenjinCell, fenjin_at, table_available, table_load_error
from .mountain24 import (
    Mountain,
    angular_distance,
    get_mountain,
    is_opposite,
    mountain_at,
    normalize_degree,
    opposite,
)

Source = Literal["vision", "manual", "hybrid"]


def element_relation(a: str, b: str) -> str:
    """五行关系描述。

    >>> element_relation("water", "wood")
    '水生木'
    >>> element_relation("metal", "wood")
    '金克木'
    >>> element_relation("fire", "fire")
    '比和（同为火）'
    """
    ca, cb = ELEMENT_CN[a], ELEMENT_CN[b]
    if a == b:
        return f"比和（同为{ca}）"
    if ELEMENT_GENERATES[a] == b:
        return f"{ca}生{cb}"
    if ELEMENT_GENERATES[b] == a:
        return f"{cb}生{ca}"
    if ELEMENT_CONTROLS[a] == b:
        return f"{ca}克{cb}"
    if ELEMENT_CONTROLS[b] == a:
        return f"{cb}克{ca}"
    raise ValueError(f"无法判定五行关系：{a} vs {b}")  # pragma: no cover


@dataclass(frozen=True, slots=True)
class CompassOrientation:
    """罗盘坐向 —— 计算后的**唯一事实**。"""

    sitting: Mountain
    facing: Mountain
    exact_degree: float | None = None
    confidence: float = 1.0
    confirmed_by_user: bool = False
    source: Source = "manual"
    fenjin: FenjinCell | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    # ---------------- 基础属性 ----------------

    @property
    def sitting_name(self) -> str:
        return self.sitting.name

    @property
    def facing_name(self) -> str:
        return self.facing.name

    @property
    def pair_label(self) -> str:
        """如「坐午向子」。"""
        return f"坐{self.sitting.name}向{self.facing.name}"

    @property
    def same_yin_yang(self) -> bool:
        """坐山与向山是否同阴阳。四维山（乾坤艮巽）与其对宫相反，其余相同。"""
        return self.sitting.yin_yang == self.facing.yin_yang

    # ---------------- 三层输出 ----------------

    def to_facts(self, *, include_fenjin: bool = True) -> dict[str, Any]:
        """FACT 层：确定性计算结果。AI 不得修改。"""
        facts: dict[str, Any] = {
            "sitting": self.sitting.name,
            "facing": self.facing.name,
            "sitting_degree": self.sitting.center_degree,
            "facing_degree": self.facing.center_degree,
            "pair": self.pair_label,
            "confidence": round(self.confidence, 4),
            "confirmed_by_user": self.confirmed_by_user,
            "source": self.source,
        }
        if self.exact_degree is not None:
            facts["exact_degree"] = round(normalize_degree(self.exact_degree), 2)
            facts["offset_from_center"] = round(
                angular_distance(self.exact_degree, self.sitting.center_degree), 2
            )
        if include_fenjin:
            facts["fenjin"] = (
                {
                    "index": self.fenjin.index,
                    "sub_index": self.fenjin.sub_index,
                    "center_degree": round(self.fenjin.center_degree, 2),
                    "ganzhi": self.fenjin.ganzhi,
                    "usable": self.fenjin.usable,
                }
                if self.fenjin
                else None
            )
            facts["fenjin_table_available"] = table_available()
        if self.warnings:
            facts["warnings"] = list(self.warnings)
        return facts

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：传统术数规则的**派生描述**（非 AI 生成）。"""
        return {
            "sitting": {
                "name": self.sitting.name,
                "kind": self.sitting.kind,
                "element": ELEMENT_CN[self.sitting.element],
                "yin_yang": "阳" if self.sitting.yin_yang == "yang" else "阴",
                "sanyuan": self.sitting.sanyuan,
                "gua": self.sitting.gua,
                "degree": self.sitting.center_degree,
            },
            "facing": {
                "name": self.facing.name,
                "kind": self.facing.kind,
                "element": ELEMENT_CN[self.facing.element],
                "yin_yang": "阳" if self.facing.yin_yang == "yang" else "阴",
                "sanyuan": self.facing.sanyuan,
                "gua": self.facing.gua,
                "degree": self.facing.center_degree,
            },
            "element_relation": element_relation(self.sitting.element, self.facing.element),
            "yin_yang_relation": "同阴阳" if self.same_yin_yang else "异阴阳（阴阳相杂）",
            "note": "以上为二十四山固定属性推导，不含流派吉凶判断；流派规则见 schools/",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}


# --------------------------------------------------------------------------
# 构造与校验
# --------------------------------------------------------------------------


def calculate_orientation(
    sitting: str | None = None,
    facing: str | None = None,
    degree: float | None = None,
    *,
    confidence: float = 1.0,
    confirmed_by_user: bool = False,
    source: Source = "manual",
    school: str = "default",
) -> CompassOrientation:
    """计算坐向，并执行几何校验。

    三种输入方式（至少给其一）：
    1. 只给 `degree` → 自动定坐山，向山取对宫
    2. 只给 `sitting` → 向山取对宫
    3. 给 `sitting` + `facing` → **必须互为对宫**，否则抛 `OrientationConflictError`

    当 `degree` 与 `sitting` 同时给出且矛盾时，**抛错而不是修正用户数据**（RULE-008）。

    Raises:
        InvalidInputError: 三者均未提供，或置信度越界
        OrientationConflictError: 坐向不构成相对关系，或 degree 与 sitting 矛盾
    """
    if not 0.0 <= confidence <= 1.0:
        raise InvalidInputError(f"置信度须在 0..1，收到 {confidence}")

    warnings: list[str] = []

    if sitting is None and facing is None and degree is None:
        raise InvalidInputError("必须提供 sitting / facing / degree 中的至少一项")

    # ---- 由角度定坐山 ----
    if degree is not None:
        from_degree = mountain_at(degree)
        if sitting is not None and sitting != from_degree.name:
            raise OrientationConflictError(
                sitting,
                facing or "?",
                detail=f"给定角度 {normalize_degree(degree):.1f}° 落在「{from_degree.name}」山，与坐山「{sitting}」不符",
            )
        sitting = from_degree.name

    sitting_m = get_mountain(sitting) if sitting else None  # type: ignore[arg-type]
    facing_m = get_mountain(facing) if facing else None

    # ---- 校验：坐山 ≠ 向山 ----
    if sitting_m and facing_m and sitting_m.name == facing_m.name:
        raise OrientationConflictError(sitting_m.name, facing_m.name, detail="坐山与向山不可相同")

    # ---- 校验：必须互为对宫 ----
    if sitting_m and facing_m and not is_opposite(sitting_m.name, facing_m.name):
        raise OrientationConflictError(
            sitting_m.name,
            facing_m.name,
            detail="二十四山中互为对宫的仅 12 组（如 子↔午、艮↔坤）",
        )

    # ---- 补全缺失一侧 ----
    # 无论是「只给坐山」还是「只给角度」，只要有一侧是推导出来的，就必须留痕：
    # 用户看到的结果里应能区分「我给的」与「系统推的」。
    if sitting_m and facing_m is None:
        facing_m = get_mountain(opposite(sitting_m.name))
        warnings.append("向山由坐山对宫推导")
    if facing_m and sitting_m is None:
        sitting_m = get_mountain(opposite(facing_m.name))
        warnings.append("坐山由向山对宫推导")

    assert sitting_m is not None and facing_m is not None  # 上方已保证

    # ---- 分金：仅当有精确角度时才有意义 ----
    fenjin = fenjin_at(degree, school=school) if degree is not None else None
    if fenjin and fenjin.ganzhi is None:
        # 「表没提供」与「表写坏了」必须分开报：后者是运维事故，
        # 一律说"未提供"会让人去找一张根本不缺的表 —— 方向从第一步就错。
        _fenjin_err = table_load_error()
        if _fenjin_err:
            warnings.append(
                f"一百二十分金规则表加载失败，仅输出几何格位：{_fenjin_err}"
            )
        else:
            warnings.append("一百二十分金干支规则表未提供，仅输出几何格位（见 fenjin120.py）")

    # ---- 置信度低 → 显式提示 ----
    if confidence < 0.75:
        warnings.append("识别置信度偏低，建议用户确认或手动修正")

    return CompassOrientation(
        sitting=sitting_m,
        facing=facing_m,
        exact_degree=degree,
        confidence=confidence,
        confirmed_by_user=confirmed_by_user,
        source=source,
        fenjin=fenjin,
        warnings=tuple(warnings),
    )


def neighbors(mountain_name: str, span: int = 1) -> list[str]:
    """取某山左右相邻山（用于环形选择器与「接近边界」提示）。

    >>> neighbors("子")
    ['壬', '癸']
    >>> neighbors("午", 2)
    ['巳', '丙', '丁', '未']
    """
    from .mountain24 import MOUNTAINS

    idx = get_mountain(mountain_name).index
    return [MOUNTAINS[(idx + k) % 24].name for k in range(-span, span + 1) if k != 0]


__all__ = [
    "CompassOrientation",
    "element_relation",
    "calculate_orientation",
    "neighbors",
]
