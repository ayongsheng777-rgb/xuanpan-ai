"""罗盘模板库路由。

模板 = 一套「盘式 + 默认坐向」的命名预设，供下次一键复用。
它解决的是一个具体的重复劳动：风水师手里的盘是**固定的那几面**
（李师傅三元盘、三合综合盘…），每次测盘都要重新选盘式、重设坐向基准。
模板把这套参数存下来，测盘时一键带出。

## 与「会话」的区别

会话是**一次测量的记录**（不可变、有报告、可追溯）；
模板是**可反复套用的预设**（可改可删、不产生任何术数结论）。
两者刻意分表：混在一起会让"删掉一个模板"变成"删掉一次测量记录"。

## 🔴 style 只存 id，不存层数

后端不维护「盘式 → 层数」表 —— 那份表在前端 `lib/dialStyle.ts`，
两边各存一份必然漂移，而漂移的表现是「列表写 18 层、打开画出 6 层」，
数字对不上却不报错。层数由前端按 id 查得。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..deps import get_store
from ..schemas import TemplateCreate, TemplateUpdate
from ..storage import Store

router = APIRouter(tags=["templates"])


@router.get("/templates", summary="模板列表")
def list_templates(store: Store = Depends(get_store)) -> dict[str, Any]:
    """按「常用 → 最近使用 → 新建」排序。

    排序在存储层做（见 `Store.list_templates`），不在这里重排 ——
    两处各排一次必然有一天不一致，而那时前端看到的是另一个顺序。
    """
    items = store.list_templates()
    return {"items": items, "total": len(items)}


@router.post("/templates", summary="新建模板")
def create_template(
    payload: TemplateCreate,
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    return store.create_template(**payload.model_dump())


@router.get("/templates/{template_id}", summary="模板详情")
def get_template(template_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    tpl = store.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")
    return tpl


@router.patch("/templates/{template_id}", summary="更新模板（局部）")
def update_template(
    template_id: str,
    payload: TemplateUpdate,
    store: Store = Depends(get_store),
) -> dict[str, Any]:
    """局部更新，只改传进来的字段。

    `exclude_unset=True` 而不是 `exclude_none=True`：前者只收**客户端显式给了**
    的键，后者会把"显式传 null 表示清空"，也一并当没传 ——
    那样用户就永远清不掉一个填错的备注。
    """
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="没有给出任何要更新的字段")
    tpl = store.update_template(template_id, fields)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")
    return tpl


@router.delete("/templates/{template_id}", summary="删除模板")
def delete_template(template_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    if not store.delete_template(template_id):
        raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")
    return {"deleted": True, "template_id": template_id}


@router.post("/templates/{template_id}/use", summary="记录一次使用")
def touch_template(template_id: str, store: Store = Depends(get_store)) -> dict[str, Any]:
    """`use_count` +1、`last_used_at` 置为现在。

    单独成一个端点而不是塞进 GET：GET 必须是**无副作用**的。
    若"打开列表"就会给每个模板记一次使用，排序会立刻全乱。
    """
    tpl = store.touch_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail=f"模板不存在：{template_id}")
    return tpl
