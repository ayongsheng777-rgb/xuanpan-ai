"""由「用户输入」重建 `FortuneContext` —— 计算层永远从原始输入出发。

为什么不让数据库直接存计算结果：那会出现"库里一份、内核另一份"的双真源，
内核升级后历史数据就变成了旧口径的僵尸。只存输入、按需重算，
则同一会话在任何时候重放都得到一致的、符合当前内核版本的结果。

本模块是 API 层与计算层之间**唯一**的装配点，
所有 `fortune_core` 的调用都收在这里，便于审计"API 到底改了内核什么"。
"""

from __future__ import annotations

from typing import Any

from fortune_core.bazi import BirthInput, calculate_bazi
from fortune_core.compass import calculate_orientation
from fortune_core.context import FortuneContext, QuestionContext, build_context
from fortune_core.exceptions import FortuneError
from fortune_core.liuyao import cast_liuyao
from fortune_core.mountain24 import MOUNTAIN_ORDER
from fortune_core.naming import analyze_name
from fortune_core.qian import draw_qian

from .schemas import LayerPreview

#：合法山名集合（启动时固定，避免每次校验都重建）
_MOUNTAIN_NAMES: frozenset[str] = frozenset(MOUNTAIN_ORDER)

#：会话里可能出现的输入列 → 该列对应的解读模块名（供列表页展示用）
ORIGIN_OF_COLUMN: dict[str, str] = {
    "compass_input": "compass",
    "bazi_input": "bazi",
    "liuyao_input": "liuyao",
    "qian_input": "qian",
    "naming_input": "naming",
}


class ContextBuildError(FortuneError):
    """存储的输入无法重建上下文（数据损坏或内核不再接受该输入）。"""


def build_compass(data: dict[str, Any]):  # type: ignore[no-untyped-def]
    """由已确认的坐向输入构造 `CompassOrientation`。"""
    sitting = data.get("sitting")
    facing = data.get("facing")
    # 山名先自查一遍。为什么不依赖下层抛错：`get_mountain` 对未知山名抛 `KeyError`，
    # 而 KeyError 在 API 层会被当作"服务内部错误"(500)。用户写错山名是**输入问题**，
    # 必须返回 400 并说明可用值，否则前端只能显示"服务器错误"，用户无从修正。
    for label, value in (("坐山", sitting), ("向山", facing)):
        if value is not None and value not in _MOUNTAIN_NAMES:
            raise ContextBuildError(
                f"{label}「{value}」不是二十四山之一；可用值：{'、'.join(MOUNTAIN_ORDER)}"
            )
    try:
        return calculate_orientation(
            sitting=sitting,
            facing=facing,
            degree=data.get("degree"),
            confidence=float(data.get("confidence", 1.0)),
            confirmed_by_user=bool(data.get("confirmed_by_user", False)),
            source=str(data.get("source", "manual")),
            school=str(data.get("school", "default")),
        )
    except FortuneError as exc:
        raise ContextBuildError(f"坐向输入无法成立：{exc}") from exc


def build_bazi(data: dict[str, Any]):  # type: ignore[no-untyped-def]
    try:
        birth = BirthInput(
            year=int(data["year"]),
            month=int(data["month"]),
            day=int(data["day"]),
            hour=int(data["hour"]),
            minute=int(data.get("minute", 0)),
            calendar=str(data.get("calendar", "solar")),
            gender=data.get("gender"),
            timezone=str(data.get("timezone", "Asia/Shanghai")),
            longitude=data.get("longitude"),
            latitude=data.get("latitude"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ContextBuildError(f"出生信息不完整或不合法：{exc}") from exc

    try:
        return calculate_bazi(birth, sect=int(data.get("sect", 2)))
    except FortuneError as exc:
        raise ContextBuildError(f"排盘失败：{exc}") from exc


def build_liuyao(data: dict[str, Any]):  # type: ignore[no-untyped-def]
    try:
        return cast_liuyao(
            yao_values=data.get("yao_values"),
            coins=_to_coins(data.get("coins")),
            numbers=tuple(data["numbers"]) if data.get("numbers") else None,
            time_info=data.get("time_info"),
        )
    except (FortuneError, TypeError, ValueError) as exc:
        raise ContextBuildError(f"起卦失败：{exc}") from exc


def _to_coins(raw: Any) -> list[tuple[bool, bool, bool]] | None:
    """JSON 里没有 tuple，且布尔可能被写成 0/1 —— 这里统一归一。"""
    if not raw:
        return None
    out: list[tuple[bool, bool, bool]] = []
    for group in raw:
        if len(group) != 3:
            raise ContextBuildError("每爻必须是 3 枚铜钱的结果")
        out.append(tuple(bool(x) for x in group))  # type: ignore[arg-type]
    return out


def build_qian(data: dict[str, Any]):  # type: ignore[no-untyped-def]
    try:
        return draw_qian(int(data["seed"]), set_id=str(data.get("set_id") or "demo_guanyin"))
    except (KeyError, TypeError, ValueError, FortuneError) as exc:
        raise ContextBuildError(f"抽签失败：{exc}") from exc


def build_naming(data: dict[str, Any]):  # type: ignore[no-untyped-def]
    name = str(data.get("name") or "").strip()
    if not name:
        raise ContextBuildError("姓名为空")
    try:
        return analyze_name(name)
    except FortuneError as exc:
        raise ContextBuildError(f"姓名分析失败：{exc}") from exc


_BUILDERS = {
    "compass_input": build_compass,
    "bazi_input": build_bazi,
    "liuyao_input": build_liuyao,
    "qian_input": build_qian,
    "naming_input": build_naming,
}


def rebuild_context(
    session: dict[str, Any],
    *,
    question_category: str | None = None,
    question_text: str | None = None,
) -> FortuneContext:
    """把一条会话记录重建成 `FortuneContext`。

    任何一层输入损坏都会抛 `ContextBuildError`（由 API 层转 422），
    **不会静默跳过** —— 少一层数据却报"生成成功"是最危险的失败方式。
    """
    parts: dict[str, Any] = {}
    for column, builder in _BUILDERS.items():
        raw = session.get(column)
        if isinstance(raw, dict) and raw:
            # 用 CONTEXT_ARG 而不是 ORIGIN_OF_COLUMN：后者是"模块名"（naming），
            # 而 build_context 的参数名是 name_analysis。两者不同名，混用会 TypeError。
            parts[CONTEXT_ARG[ORIGIN_OF_COLUMN[column]]] = builder(raw)

    category = question_category or session.get("question_category") or "其他"
    text = question_text if question_text is not None else (session.get("question_text") or "")
    question = QuestionContext(category=str(category), text=str(text))

    return build_context(str(session["session_id"]), question=question, **parts)


def available_modules(session: dict[str, Any]) -> list[str]:
    """该会话已有哪些模块的结果（供 UI 决定显示哪些标签页）。"""
    return [
        ORIGIN_OF_COLUMN[column]
        for column in _BUILDERS
        if isinstance(session.get(column), dict) and session.get(column)
    ]


#：模块名 → `build_context` 的参数名（命名模块的参数是 `name_analysis`）
CONTEXT_ARG: dict[str, str] = {
    "compass": "compass",
    "bazi": "bazi",
    "liuyao": "liuyao",
    "qian": "qian",
    "naming": "name_analysis",
}

#：模块名 → `FortuneContext.to_facts()` 里的键名（命名模块的键是 `name` 而非 `naming`）
FACT_KEY: dict[str, str] = {
    "compass": "compass",
    "bazi": "bazi",
    "liuyao": "liuyao",
    "qian": "qian",
    "naming": "name",
}


def preview_of(module: str, result: Any) -> LayerPreview:
    """把单个模块结果转成两层只读预览。

    实现上**真的去组装一次 FortuneContext**，而不是直接调 `result.to_facts()`。
    为什么绕这一下：组装过程会补上流派元信息、规则表就绪状态等上下文，
    若这里走捷径，UI 预览与最终报告就可能出现"预览有、报告没有"的差异。
    宁可多算一次（纯内存、微秒级），也不让两条路径分叉。
    """
    arg = CONTEXT_ARG.get(module)
    key = FACT_KEY.get(module)
    if arg is None or key is None:
        raise ContextBuildError(f"未知模块：{module!r}")

    ctx = build_context("preview", **{arg: result})
    return LayerPreview(
        facts={key: ctx.to_facts()[key]},
        tradition={key: ctx.to_tradition()[key]},
        uncertainties=ctx.uncertainties(),
    )


__all__ = [
    "ContextBuildError", "CONTEXT_ARG", "FACT_KEY", "ORIGIN_OF_COLUMN",
    "available_modules", "rebuild_context", "preview_of",
    "build_compass", "build_bazi", "build_liuyao", "build_qian", "build_naming",
]
