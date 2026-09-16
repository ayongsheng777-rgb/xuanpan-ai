"""合成罗盘图生成器 —— 让识别管线**可以被真实测试**。

为什么需要它：
Gate 1 的判据是"能否稳定识别真实罗盘照片"，但真实照片不可控、不可复现、
无法放进 CI。合成图提供**已知真值**（鱼丝线角度、磁针角度、透视形变），
因此可以自动断言"管线输出的角度是否等于真值"。

它同时是 Gate 1 现场评测的工具：可以用它生成不同难度梯度
（清晰/模糊/反光/斜拍/小尺寸），对齐到真实拍摄条件。

注意：**合成图只验证几何与算法，不能替代真实照片的 Gate 1 测试**。
真实照片的评测结果必须单独记录，不得用合成图结果冒充。
"""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter

from .ring import point_at


def render_compass(
    *,
    size: int = 900,
    radius_ratio: float = 0.42,
    thread_angle: float = 0.0,
    thread_width: int = 4,
    needle_angle: float = 0.0,
    ticks: bool = True,
    label_blobs: bool = True,
    squash: float = 1.0,
    tilt: float = 0.0,
    background: int = 210,
    body: int = 170,
    inner: int = 195,
    tick_value: int = 120,
    blob_value: int = 60,
    thread_value: int = 25,
    needle_dark: int = 70,
    noise: float = 0.0,
    blur: float = 0.0,
    glare_box: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """渲染一张合成罗盘图。

    Args:
        thread_angle: 鱼丝线角度（项目约定：0=北，顺时针）
        squash: 水平压缩比例，<1 模拟斜拍产生的椭圆
        tilt: 压缩后再旋转的角度（度），模拟任意方向的斜拍
        glare_box: 过曝矩形区域 (x0, y0, x1, y1)，模拟反光
    """
    W = size
    canvas = Image.new("L", (W, W), background)
    draw = ImageDraw.Draw(canvas)
    cx = cy = W / 2.0
    R = W * radius_ratio

    # ---- 盘体与内圈 ----
    draw.ellipse([cx - R, cy - R, cx + R, cy + R], fill=body)
    draw.ellipse([cx - R * 0.93, cy - R * 0.93, cx + R * 0.93, cy + R * 0.93], fill=inner)
    draw.ellipse([cx - R * 0.90, cy - R * 0.90, cx + R * 0.90, cy + R * 0.90],
                 outline=tick_value, width=max(2, int(R * 0.012)))

    # ---- 二十四山刻度 ----
    if ticks:
        for i in range(24):
            a = i * 15.0
            p0 = point_at((cx, cy), R * 0.86, a)
            p1 = point_at((cx, cy), R * 0.92, a)
            draw.line([p0, p1], fill=tick_value, width=max(2, int(R * 0.010)))
        # 四正加粗
        for a in (0.0, 90.0, 180.0, 270.0):
            p0 = point_at((cx, cy), R * 0.80, a)
            p1 = point_at((cx, cy), R * 0.93, a)
            draw.line([p0, p1], fill=tick_value, width=max(3, int(R * 0.020)))

    # ---- 模拟印刷文字（用于验证"文字不会被误判为鱼丝线"）----
    if label_blobs:
        for i in range(24):
            a = i * 15.0 + 7.5
            for rr in (0.72, 0.62):
                p = point_at((cx, cy), R * rr, a)
                s = max(2.0, R * 0.028)
                draw.ellipse([p[0] - s, p[1] - s, p[0] + s, p[1] + s], fill=blob_value)

    # ---- 天池磁针（半径 ~22%，在鱼丝线采样范围之外）----
    draw.ellipse([cx - R * 0.26, cy - R * 0.26, cx + R * 0.26, cy + R * 0.26],
                 outline=tick_value, width=max(2, int(R * 0.010)))
    n0 = point_at((cx, cy), R * 0.24, needle_angle)
    n1 = point_at((cx, cy), R * 0.24, needle_angle + 180.0)
    draw.line([n0, n1], fill=needle_dark, width=max(3, int(R * 0.022)))

    # ---- 鱼丝线：贯通整圆的直径线（识别目标）----
    t0 = point_at((cx, cy), R * 0.995, thread_angle)
    t1 = point_at((cx, cy), R * 0.995, thread_angle + 180.0)
    draw.line([t0, t1], fill=thread_value, width=thread_width)

    # ---- 退化处理：模糊 / 噪点 / 反光 ----
    if blur > 0:
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    if noise > 0:
        import numpy as np

        arr = np.asarray(canvas, dtype=np.float64)
        rng = np.random.default_rng(20260916)   # 固定种子 → 可复现
        arr = arr + rng.normal(0.0, noise, arr.shape)
        canvas = Image.fromarray(arr.clip(0, 255).astype("uint8"))
    if glare_box is not None:
        d2 = ImageDraw.Draw(canvas)
        d2.rectangle(glare_box, fill=255)

    # ---- 透视形变：先横向压缩，再整体旋转 ----
    if squash != 1.0:
        canvas = canvas.resize((max(1, int(W * squash)), W), Image.BICUBIC)
    if tilt:
        canvas = canvas.rotate(tilt, resample=Image.BICUBIC, fillcolor=background,
                               expand=True)

    # 贴回统一画布，保证输出尺寸稳定
    out = Image.new("RGB", (W, W), (background, background, background))
    out.paste(canvas.convert("RGB"),
              ((W - canvas.width) // 2, (W - canvas.height) // 2))
    return out


def expected_mountains(thread_angle: float) -> set[str]:
    """给定鱼丝线角度，返回应有的两个对宫山名（合成图的"真值"）。"""
    from fortune_core.mountain24 import mountain_at, opposite

    m = mountain_at(thread_angle)
    return {m.name, opposite(m.name)}


def angle_error(measured: float, truth: float) -> float:
    """线的角度误差（0~90°），考虑直径线只有 0~180 的方向性。"""
    m = measured % 180.0
    t = truth % 180.0
    d = abs(m - t) % 180.0
    return min(d, 180.0 - d)


__all__ = ["render_compass", "expected_mountains", "angle_error"]
