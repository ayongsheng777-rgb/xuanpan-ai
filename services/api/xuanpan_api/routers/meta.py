"""元信息路由 —— 静态参考数据与能力清单。

这些接口**不产生任何计算**，只把计算层与模型层已有的元信息透出给 UI，
避免前端各自硬编码一份（那必然与内核漂移）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/mountains", summary="二十四山标准表")
def mountains() -> dict[str, Any]:
    """二十四山及其属性。

    UI 的"手动选山"转盘、识别结果显示都以此为准 —— 前端不得自建一份山表，
    否则角度约定（0°=正北、顺时针）一旦不一致，识别与计算就会错位 90°/180°。
    """
    from fortune_core.mountain24 import MOUNTAINS

    return {
        "convention": "0°=正北（子），顺时针递增，每山 15°",
        "mountains": [
            {
                "index": m.index,
                "name": m.name,
                "center_degree": m.center_degree,
                "start_degree": m.start_degree,
                "end_degree": m.end_degree,
                "kind": m.kind,
                "element": m.element,
                "yin_yang": m.yin_yang,
                "sanyuan": m.sanyuan,
                "gua": m.gua,
                "full_name": m.full_name,
            }
            for m in MOUNTAINS
        ],
    }


@router.get("/schools", summary="流派清单与可用性")
def schools() -> dict[str, Any]:
    from fortune_core.schools import DEFAULT_SCHOOL, list_schools

    return {"default": DEFAULT_SCHOOL, "schools": list_schools()}


@router.get("/question-categories", summary="问题类别与敏感类别")
def question_categories() -> dict[str, Any]:
    """敏感类别会触发额外免责声明（RULE-010）。"""
    from fortune_core.context import QUESTION_CATEGORIES, SENSITIVE_CATEGORIES

    return {
        "categories": list(QUESTION_CATEGORIES),
        "sensitive": dict(SENSITIVE_CATEGORIES),
    }


@router.get("/disclaimer", summary="统一免责声明")
def disclaimer() -> dict[str, str]:
    from xuanpan_ai import DISCLAIMER

    return {"disclaimer": DISCLAIMER}


@router.get("/ai-providers", summary="AI 解释模型能力清单")
def ai_providers() -> dict[str, Any]:
    """按**能力**而非品牌列出，并标注当前环境是否可用。

    `requires_api_key=True` 的条目若 `available=False`，说明未配置 key；
    UI 应展示为"未配置"而不是"不可用"，两者对用户的含义不同。
    """
    from xuanpan_ai import CAPABILITY_MATRIX, list_endpoint_presets, list_providers

    return {
        "matrix": [dict(x) for x in CAPABILITY_MATRIX],
        "providers": list_providers(),
        "endpoint_presets": list_endpoint_presets(),
    }


@router.get("/vision-providers", summary="罗盘识别 provider 能力清单")
def vision_providers() -> dict[str, Any]:
    from xuanpan_vision import CAPABILITY_MATRIX, list_providers
    from xuanpan_vision.providers import USER_AUTHORITATIVE_PROVIDERS

    return {
        "matrix": [dict(x) for x in CAPABILITY_MATRIX],
        "providers": list_providers(),
        "user_authoritative": sorted(USER_AUTHORITATIVE_PROVIDERS),
    }


@router.get("/qian-sets", summary="可用签库")
def qian_sets() -> dict[str, Any]:
    """签库清单。`demo=true` 的签库是演示用，报告会据此附警告。"""
    from fortune_core.qian import list_qian_sets

    return {"sets": list_qian_sets()}


@router.get("/capabilities", summary="系统能力与规则表就绪状态")
def capabilities() -> dict[str, Any]:
    """把"哪些结论现在可用"如实透出。

    为什么单列这个接口：一百二十分金的干支层依赖规则表，规则表缺失时
    计算层会返回 `None`（不猜）。UI 需要能解释"为什么这里显示未定"，
    而不是把它渲染成一个空值让用户以为程序坏了。
    """
    from fortune_core.fenjin120 import table_available
    from xuanpan_ai import list_providers as list_ai_providers
    from xuanpan_vision import list_providers as list_vision_providers

    return {
        "fenjin_table_available": table_available(),
        "ai_provider_available": any(p.get("available") for p in list_ai_providers()),
        "vision_provider_available": any(p.get("available") for p in list_vision_providers()),
        "note": "fenjin_table_available=False 时，分金只输出几何格位，干支显示为「未定」",
    }


__all__ = ["router"]
