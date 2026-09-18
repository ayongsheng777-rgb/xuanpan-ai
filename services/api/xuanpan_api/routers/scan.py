"""罗盘识别路由 —— 照片 → 结构化坐向候选。

**双入口，同一后端**：相机拍照与相册选图在客户端是不同的系统能力，
但产出的都是"一张图"，因此服务端只有一个入口（基线规范裁定 4）。

隐私边界（与用户裁定一致：数据可外流）
原图**默认不落盘**（`Settings.keep_photos=False`），只在内存中过一遍识别链路；
落库的只有结构化识别结果。若运维显式打开 `XUANPAN_KEEP_PHOTOS`，
则原图落盘并在响应中如实告知 —— 隐私说明必须能被架构证实，措辞不得超出实现。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from ..config import Settings
from ..deps import get_active_settings, get_store
from ..schemas import ScanAccepted
from ..storage import Store

router = APIRouter(tags=["scan"])


@router.post("/scan", response_model=ScanAccepted, summary="上传罗盘照片并识别")
async def scan_compass(
    image: UploadFile = File(..., description="罗盘照片（JPEG/PNG/WebP）"),
    provider: str = Query("classical", description="识别 provider：classical / openai_compat"),
    store: Store = Depends(get_store),
    # 取**生效配置**（含管理台覆盖）：上传上限与是否留原件都要能从界面改即时生效。
    settings: Settings = Depends(get_active_settings),
) -> ScanAccepted:
    """识别照片中的罗盘，返回**候选**坐向。

    返回的 `needs_user_confirmation` 恒为 `true`：几何识别无法判断哪一端是坐山
    （这是盘面本身的信息缺失，不是算法能力不足），必须由用户确认。
    """
    raw = await image.read()

    # ---- 尺寸闸门：超大图对识别没有帮助，只会拖慢链路 ----
    if not raw:
        raise HTTPException(status_code=400, detail="未收到图像数据")
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"图片超过 {settings.max_upload_mb}MB 上限，请压缩后重试",
        )

    # ---- 识别（延迟导入：让 API 在未安装 vision 时仍可提供纯计算功能）----
    try:
        from xuanpan_vision import analyze_compass
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=503, detail="识别服务未就绪（xuanpan_vision 不可用）") from exc

    try:
        result, prepared = analyze_compass(raw, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"图像无法解析：{exc}") from exc
    except KeyError as exc:
        # get_provider 未知名字会抛 KeyError
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ---- 会话：识别即建会话，用户确认后原地升级 ----
    session_id = store.create_session(
        origin="scan",
        title=_auto_title(result),
    )
    store.update_session(session_id, recognition=result.to_dict())

    # ---- 隐私：仅当显式开启时才落盘原图 ----
    if settings.keep_photos and raw:
        _persist_photo(settings, session_id, raw, image.content_type or "")

    _ = prepared  # 仅用于确认链路走通；校正图不落库
    return ScanAccepted(
        session_id=session_id,
        compass_detected=result.compass_detected,
        provider=result.provider,
        quality=result.quality.to_dict() if result.quality else None,
        center=result.center,
        radius=result.radius,
        mountain_candidates=[c.to_dict() for c in result.mountain_candidates],
        direction_candidates=[c.to_dict() for c in result.direction_candidates],
        uncertain_regions=list(result.uncertain_regions),
        warnings=list(result.warnings),
    )


def _auto_title(result: Any) -> str:
    """给会话起一个可辨识的标题，避免列表页全是「未命名」。"""
    from datetime import datetime

    stamp = datetime.now().strftime("%m-%d %H:%M")
    if result.compass_detected and result.mountain_candidates:
        names = "／".join(c.name for c in result.mountain_candidates[:3])
        return f"{stamp} 罗盘识别 · {names}"
    if result.uncertain_regions:
        return f"{stamp} 罗盘识别 · 未识别"
    return f"{stamp} 罗盘识别"


def _persist_photo(settings: Settings, session_id: str, raw: bytes, content_type: str) -> None:
    """原图落盘（仅在 `keep_photos=True` 时）。不覆盖同名文件。"""
    ext = {"image/png": ".png", "image/webp": ".webp"}.get(content_type, ".jpg")
    settings.photo_dir.mkdir(parents=True, exist_ok=True)
    target = settings.photo_dir / f"{session_id}{ext}"
    if target.exists():  # 幂等：同会话重复识别不覆盖历史原件
        return
    target.write_bytes(raw)


__all__ = ["router"]
