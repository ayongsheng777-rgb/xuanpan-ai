"""环形采样与鱼丝线角度测量。

**本项目统一的角度约定**（任何地方都不得出现第二种）：

    0°   = 正北 = 指向画面正上方（图像 -y 方向）
    角度**顺时针**增大：90° = 正东，180° = 正南，270° = 正西

这与 `fortune_core.mountain24` 的约定完全一致，因此从图像角度到二十四山的
映射是一次纯查表，中间不需要任何人工换算 —— 换算就是错误的高发区。

鱼丝线检测原理：
    鱼丝线是一条**贯通整圆**的直线（直径线），因此在任何半径上都表现为暗像素。
    而印刷字符只出现在某个很窄的半径带上。
    故取「跨半径的最小暗度」作为判别量，天然滤掉文字与刻度。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .quality import to_gray_array

#：环形采样默认参数
N_ANGLES = 1440          # 0.25° 分辨率 —— 足以分辨 3° 的分金格
R_MIN_RATIO = 0.30       # 从半径 30% 起采，避开天池区
R_MAX_RATIO = 0.97       # 到 97% 止，避开盘边阴影
N_RADII = 34


def angle_of(x: float, y: float, cx: float, cy: float) -> float:
    """像素坐标 → 项目角度（0=北，顺时针）。

    >>> angle_of(100, 0, 100, 100)   # 正上方 → 北
    0.0
    >>> angle_of(200, 100, 100, 100) # 正右方 → 东
    90.0
    >>> angle_of(100, 200, 100, 100) # 正下方 → 南
    180.0
    """
    dx = x - cx
    dy = y - cy
    return float(np.degrees(np.arctan2(dx, -dy)) % 360.0)


def point_at(center: tuple[float, float], radius: float, angle_deg: float) -> tuple[float, float]:
    """项目角度 → 像素坐标（`angle_of` 的逆）。

    >>> point_at((100.0, 100.0), 50.0, 0.0)
    (100.0, 50.0)
    """
    cx, cy = center
    t = np.radians(angle_deg)
    return (cx + radius * float(np.sin(t)), cy - radius * float(np.cos(t)))


def angular_bins(n_angles: int = N_ANGLES) -> np.ndarray:
    return np.arange(n_angles, dtype=np.float64) * (360.0 / n_angles)


def polar_unwrap(
    gray: np.ndarray,
    center: tuple[float, float],
    radius: float,
    *,
    n_angles: int = N_ANGLES,
    r_min_ratio: float = R_MIN_RATIO,
    r_max_ratio: float = R_MAX_RATIO,
    n_radii: int = N_RADII,
) -> tuple[np.ndarray, np.ndarray]:
    """极坐标展开：返回 (profile, radii_ratios)。

    `profile[a, r]` = 角度 `a` 半径 `r` 处的灰度（0~255，双线性插值）。

    越界采样以 NaN 填充 —— **不补零**，否则盘外区域会被当成"极暗"而污染检测。
    """
    h, w = gray.shape
    angles = angular_bins(n_angles)
    ratios = np.linspace(r_min_ratio, r_max_ratio, n_radii)

    t = np.radians(angles)[:, None]
    r = (radius * ratios)[None, :]

    xs = center[0] + r * np.sin(t)
    ys = center[1] - r * np.cos(t)

    profile = np.full((n_angles, n_radii), np.nan, dtype=np.float64)

    x0 = np.floor(xs).astype(np.int64)
    y0 = np.floor(ys).astype(np.int64)
    fx = xs - x0
    fy = ys - y0

    inside = (x0 >= 0) & (x0 + 1 < w) & (y0 >= 0) & (y0 + 1 < h)
    if not inside.any():
        return profile, ratios

    xi = np.clip(x0, 0, w - 2)
    yi = np.clip(y0, 0, h - 2)

    v00 = gray[yi, xi]
    v01 = gray[yi, xi + 1]
    v10 = gray[yi + 1, xi]
    v11 = gray[yi + 1, xi + 1]
    interp = (
        v00 * (1 - fx) * (1 - fy)
        + v01 * fx * (1 - fy)
        + v10 * (1 - fx) * fy
        + v11 * fx * fy
    )
    profile[inside] = interp[inside]
    return profile, ratios


@dataclass(frozen=True, slots=True)
class LineMeasure:
    """一条直径线（鱼丝线）的测量结果。"""

    angle: float             # 主端角度（0..180，即线的方向，不含朝向）
    confidence: float
    score: float             # 原始判别量（跨半径最小暗度）
    baseline: float          # 中位基线，用于判断显著程度
    ends: tuple[float, float]  # 两个端点角度 (θ, θ+180)

    def to_dict(self) -> dict[str, Any]:
        return {
            "angle": round(self.angle, 2),
            "confidence": round(self.confidence, 4),
            "score": round(self.score, 2),
            "baseline": round(self.baseline, 2),
            "ends": [round(e, 2) for e in self.ends],
        }


def detect_diameter_line(
    profile: np.ndarray,
    *,
    min_prominence: float = 12.0,
    angular_smooth: int = 3,
) -> LineMeasure:
    """从极坐标展开图中检测贯通直径的暗线（鱼丝线）。

    Args:
        profile: `polar_unwrap` 的输出
        min_prominence: 判别量高出中位基线的最小值（灰度级），低于此判为"没找到"
        angular_smooth: 角度方向平滑窗口（奇数），抑制单像素噪点
    """
    n_angles, n_radii = profile.shape
    # 每个角度上：取「跨半径的最小暗度」= 该角度是否整条半径都暗
    dark = 255.0 - profile                        # NaN 会被 nanmin 忽略
    with np.errstate(invalid="ignore"):
        per_angle = np.nanmin(dark, axis=1)
    per_angle = np.nan_to_num(per_angle, nan=0.0)

    if angular_smooth > 1 and n_angles > angular_smooth:
        k = angular_smooth
        pad = np.pad(per_angle, (k // 2, k // 2), mode="wrap")
        kernel = np.ones(k) / k
        per_angle = np.convolve(pad, kernel, mode="valid")

    # 直径线会在 θ 与 θ+180 两处同时出现 → 折叠成 0..180 提升信噪比
    half = n_angles // 2
    if n_angles % 2 == 0:
        folded = per_angle[:half] + per_angle[half:]
    else:  # pragma: no cover - 默认参数下不会走到
        folded = per_angle[:half] + per_angle[half:half * 2]

    idx = int(np.argmax(folded))
    score = float(folded[idx])
    baseline = float(np.median(folded))

    step = 360.0 / n_angles
    angle = idx * step
    # 抛物线亚角插值，把 0.25° 的分辨率再精化一个量级
    if 0 < idx < len(folded) - 1:
        y0, y1, y2 = folded[idx - 1], folded[idx], folded[idx + 1]
        denom = (y0 - 2 * y1 + y2)
        if abs(denom) > 1e-9:
            angle += float(np.clip(0.5 * (y0 - y2) / denom, -1.0, 1.0)) * step

    prominence = score - baseline
    confidence = 0.0 if min_prominence <= 0 else float(np.clip(prominence / (min_prominence * 3.0), 0.0, 1.0))
    if prominence < min_prominence:
        confidence = 0.0

    return LineMeasure(
        angle=angle % 180.0,
        confidence=confidence,
        score=score,
        baseline=baseline,
        ends=(angle % 180.0, (angle % 180.0) + 180.0),
    )


@dataclass(frozen=True, slots=True)
class NeedleMeasure:
    """天池磁针方向测量。"""

    angle: float | None
    confidence: float
    aligned: bool | None      # 是否已对准（贴近 0° 或 180°）
    deviation_deg: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "angle": round(self.angle, 2) if self.angle is not None else None,
            "confidence": round(self.confidence, 4),
            "aligned": self.aligned,
            "deviation_deg": round(self.deviation_deg, 2) if self.deviation_deg is not None else None,
        }


def detect_needle(
    gray: np.ndarray,
    center: tuple[float, float],
    radius: float,
    *,
    r_ratio: float = 0.22,
    aligned_tolerance_deg: float = 4.0,
) -> NeedleMeasure:
    """检测天池磁针方向，用于判断罗盘是否已「对针」。

    磁针位于天池（内圈），故在半径 22% 附近取一圈采样，
    找最暗（针身）与最亮（红头/白底）的方位。
    """
    n = 720
    angles = angular_bins(n)
    t = np.radians(angles)
    xs = center[0] + radius * r_ratio * np.sin(t)
    ys = center[1] - radius * r_ratio * np.cos(t)

    h, w = gray.shape
    x0 = np.clip(np.floor(xs).astype(np.int64), 0, w - 1)
    y0 = np.clip(np.floor(ys).astype(np.int64), 0, h - 1)
    vals = gray[y0, x0]
    if not np.isfinite(vals).any():
        return NeedleMeasure(angle=None, confidence=0.0, aligned=None, deviation_deg=None)

    dark = 255.0 - vals
    half = n // 2
    folded = dark[:half] + dark[half:]
    idx = int(np.argmax(folded))
    score = float(folded[idx])
    base = float(np.median(folded))
    prominence = score - base
    conf = float(np.clip(prominence / 60.0, 0.0, 1.0))
    if conf <= 0.0:
        return NeedleMeasure(angle=None, confidence=0.0, aligned=None, deviation_deg=None)

    angle = (idx * (360.0 / n)) % 180.0
    deviation = min(angle, 180.0 - angle)
    return NeedleMeasure(
        angle=angle,
        confidence=conf,
        aligned=deviation <= aligned_tolerance_deg,
        deviation_deg=deviation,
    )


def ring_profile_from_image(
    image,
    center: tuple[float, float],
    radius: float,
    **kwargs,
) -> tuple[np.ndarray, np.ndarray]:
    """便捷入口：PIL 图 → 极坐标展开。"""
    return polar_unwrap(to_gray_array(image), center, radius, **kwargs)


__all__ = [
    "N_ANGLES", "R_MIN_RATIO", "R_MAX_RATIO", "N_RADII",
    "angle_of", "point_at", "angular_bins", "polar_unwrap",
    "LineMeasure", "NeedleMeasure", "detect_diameter_line", "detect_needle",
    "ring_profile_from_image",
]
