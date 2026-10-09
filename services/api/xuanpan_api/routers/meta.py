"""元信息路由 —— 静态参考数据与能力清单。

这些接口**不产生任何计算**，只把计算层与模型层已有的元信息透出给 UI，
避免前端各自硬编码一份（那必然与内核漂移）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request

from ..deps import get_runtime_config, get_store
from ..runtime_config import ConfigError, RuntimeConfig
from ..storage import Store

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
def ai_providers(
    request: Request,
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """按**能力**而非品牌列出，并标注当前环境是否可用。

    `requires_api_key=True` 的条目若 `available=False`，说明未配置 key；
    UI 应展示为"未配置"而不是"不可用"，两者对用户的含义不同。

    2026-10-08 修复：之前直接调模块级的 `list_providers()`，拿到的是
    进程启动时的 provider 实例，管理台改了密钥后这里显示的还是旧状态。
    现在走运行时配置重建的 router，与真实 AI 调用看到的一致。

    **字段基准仍是 `CAPABILITY_MATRIX`，运行时只决定 `available`**：
    UI 契约（`ProviderInfo`）要 `id` / `cost` / `description`，这三项只有
    静态矩阵里有 —— provider 实例的 `describe()` 不提供。若整条响应改用
    `describe()`，前端类型契约会缺字段、且 `id` 缺失会让前端按 id 取用直接崩。
    """
    from xuanpan_ai import CAPABILITY_MATRIX, list_endpoint_presets

    from ..deps import get_ai_router

    router_obj = get_ai_router(request, store)
    if router_obj is None:
        # 兜底：未装配运行时配置时退回静态探测（与旧行为一致）
        from xuanpan_ai import list_providers

        providers = list_providers()
    else:
        # 运行时可用集合。provider 实例的 `registry_id` 与矩阵 id 同源
        # （`get_provider` 按注册表键写入），故可据此对齐。
        available_ids: set[str] = set()
        for p in getattr(router_obj, "_providers", None) or []:
            registry_id = getattr(p, "registry_id", None)
            if not registry_id:
                continue
            try:
                if p.is_available():
                    available_ids.add(registry_id)
            except Exception:  # noqa: BLE001 - 环境探测失败按不可用处理
                pass

        providers = [
            {**dict(entry), "available": entry["id"] in available_ids}
            for entry in CAPABILITY_MATRIX
        ]

    return {
        "matrix": [dict(x) for x in CAPABILITY_MATRIX],
        "providers": providers,
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


@router.post("/ai-model-selection", summary="App 选择 AI 模型（不碰密钥）")
def set_ai_model_selection(
    selection: dict[str, Any] = Body(..., description="要选的模型：{model: 模型名, capability: 能力}"),
    runtime: RuntimeConfig = Depends(get_runtime_config),
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """App 端切换 AI 模型选择。

    安全边界（2026-10-08 用户要求 App 内可配模型）：
    - 只允许改 `llm.model` 与 `llm.capability`（选"用哪个模型"）。
    - **不接受** `llm.api_key`、`llm.base_url` —— 密钥与接入地址只能
      经管理台（/admin，需令牌）或环境变量配置，永不经过 App。
    - capability 必须在配置层规格允许的档位内，否则 `runtime.update` 会拒。

    为什么单开一个接口而不复用 admin 的 PATCH /config：
    admin 接口要令牌（防隐私数据泄露），而选模型不涉及隐私；
    把选模型做成免令牌接口，用户在 App 里点两下就能换，不用记令牌。

    2026-10-08 修复：capability 的合法域原先在本函数里另写了一份
    `{vision, reasoning, fast, fallback, embedding}`，与配置层
    `llm.capability` 的 choices `(reasoning, fast, local)` **不一致**：
    App 按 `(p.id, p.capability)` 调用，`template` provider 自报
    `capability="template"` → 必然 400；而 `vision`/`fallback`/`embedding`
    虽过了本函数，又会被下游 `runtime.update` 以 ConfigError 拒掉。
    现改为**以配置层规格为单一真源**，并把 provider 自报档位归一化。
    """
    from ..runtime_config import SPEC_BY_KEY

    model = selection.get("model")
    capability = selection.get("capability")
    if not model or not isinstance(model, str):
        raise HTTPException(status_code=400, detail="缺少 model（模型名）")
    if not capability or not isinstance(capability, str):
        raise HTTPException(status_code=400, detail="缺少 capability（能力档位）")

    #: 合法档位取自配置层规格 —— 不要再在这里手抄一份，两份必然会漂移。
    valid_caps: tuple[str, ...] = SPEC_BY_KEY["llm.capability"].choices

    #: provider 自报档位 → 配置层档位。`template` 是「本地零成本」档，
    #: 配置层用 `local` 表达同一含义（见 providers/template.py 的 capability）。
    _CAPABILITY_ALIASES = {"template": "local"}

    normalized = _CAPABILITY_ALIASES.get(capability, capability)
    if normalized not in valid_caps:
        raise HTTPException(
            status_code=400,
            detail=(
                f"capability 非法，应为 {sorted(valid_caps)} 之一"
                f"（provider 自报的 {sorted(_CAPABILITY_ALIASES)} 会自动归一化）"
            ),
        )

    changes = {"llm.model": model.strip(), "llm.capability": normalized}
    try:
        result = runtime.update(store, changes)
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {**result, "model": model.strip(), "capability": normalized}
