"""几何处理 —— 罗盘圆心/边界检测与透视（椭圆）校正。

只用 `numpy` + `PIL`，不引入 OpenCV：
- 本项目需要的是「一个圆盘的定位与归一」，不是通用 CV 平台
- OpenCV 会显著增大部署体积（原生库），而它的能力在这里只用得上很小一部分
- 纯 numpy 实现可读、可测、可审 —— 与 RULE-001「确定性计算要能被验证」一致

算法路线（针对"罗盘是画面主体"这一拍摄约束）：
1. **阈值搜索 + 形态先验** → 前景掩膜（见下方「为什么不用单一 Otsu」）
2. 前景形心 = 圆心初值；`r = sqrt(area/π)` = 半径初值
3. 圆度校验：掩膜像素落在半径 1.08 倍以内的比例 → 置信度
4. 由掩膜二阶矩估计椭圆长短轴与倾角 → 仿射校正为圆，得到「透视校正图」

为什么不用单一 Otsu 阈值
------------------------

`[已确认]` Otsu 只求**一个**最优二分点，遇到三种以上灰度模式时会切错位置。
真实罗盘照片恰好是这种分布：盘面印刷的墨线极黑、盘体本身较亮、背景最亮。

以本项目合成罗盘（`testing.render_compass`）标定为例，其灰度分布为
`{25 鱼丝线, 60 文字, 70 磁针, 120 刻度, 170 盘边, 195 盘面, 210 背景}`，
Otsu 求得 **120.5** —— 它把"墨线"与"盘体＋背景"分开了，**盘体被归入背景**，
于是 `fill≈0.039`、`detected=False`，整条管线在第一步就断掉。
这不是合成图特有的假象：实拍中"盘面与背景亮度接近、而文字比两者都暗"
是常见构图，同样会踩中。

因此掩膜选择改为**阈值搜索 + 形态先验**：枚举所有可能改变掩膜的阈值
（相邻「出现过的灰度级」的中点），对每个阈值分别取**下侧**与**上侧**作前景，
再用「它像不像一个实心圆盘」给每个候选打分，取最高分。

打分量 `filled = 面积 / (π·a·b)`（a、b 为二阶矩推出的等效椭圆半轴）：

- 实心圆盘（含斜拍产生的椭圆）：`filled ≈ 1.0`，且**与压扁程度无关**
- 圆环（只取到盘边那一圈，例如阈值切在盘面与盘边之间）：`filled ≈ 0.04` → 淘汰
- 零散墨线/刻度/磁针：`filled` 很小 → 淘汰
- "整幅画面减去圆盘"（把背景当前景）：`filled ≈ 0.27` → 淘汰

这仍然只是**几何与亮度的判据**，不含任何猜测：找不到满足形态先验的掩膜时，
返回 `detected=False` 并给出可执行的用户提示，**不猜**（RULE-003）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from .quality import to_gray_array

#：为控制耗时，圆检测前先缩放到该短边尺寸
DETECT_WORK_SIZE = 384

#：掩膜搜索的阈值候选上限（控制最坏耗时；真实照片灰度级远多于此）
MAX_THRESHOLD_CANDIDATES = 64

#：前景占比的合法区间 —— 低于下限说明画面里没有盘体，
#：高于上限说明盘体与背景已无法区分（或盘体占满整幅且贴边）
MIN_FILL = 0.05
MAX_FILL = 0.92

#：前景像素数下限，避免在极小的噪点团上拟合椭圆
MIN_FOREGROUND_PIXELS = 64

#：等效椭圆长宽比超过此值 → 形状先验打折（斜拍极限或掩膜已碎裂）
MAX_ELLIPSE_ASPECT = 2.0

#：长宽比低于此值即视为**正圆**。
#：`[已确认]` 正圆的二阶矩各向同性，`eigh` 返回的特征向量完全由浮点噪声决定，
#：即"长轴方向"在数学上**无定义**。若把噪声方向当旋转角施加到图上，
#：整盘（含二十四山刻度）会被旋转一个任意角度 —— 反而不如不校正。
#：故低于此阈值时不旋转、不形变。
CIRCLE_ASPECT_TOLERANCE = 1.02

#：Otsu 空输入时的兜底阈值
DEFAULT_OTSU = 128.0


@dataclass(frozen=True, slots=True)
class CircleDetection:
    """圆盘检测结果。坐标基于**传入图像**的像素系。"""

    detected: bool
    center: tuple[float, float] | None
    radius: float | None
    confidence: float
    circularity: float          # 前景落在半径内的比例，1.0 = 完美圆
    fill_ratio: float           # 前景占比
    touches_border: bool        # 前景是否贴到画面边缘（罗盘未完整入镜）
    semi_axes: tuple[float, float] | None = None   # 椭圆长短半轴
    tilt_deg: float | None = None                  # 椭圆长轴倾角（度，图像坐标系）
    reason: str | None = None                      # 未检测到时的说明

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "center": {"x": round(self.center[0], 2), "y": round(self.center[1], 2)} if self.center else None,
            "radius": round(self.radius, 2) if self.radius else None,
            "confidence": round(self.confidence, 4),
            "circularity": round(self.circularity, 4),
            "fill_ratio": round(self.fill_ratio, 4),
            "touches_border": self.touches_border,
            "semi_axes": [round(v, 2) for v in self.semi_axes] if self.semi_axes else None,
            "tilt_deg": round(self.tilt_deg, 2) if self.tilt_deg is not None else None,
            "reason": self.reason,
        }


def otsu_threshold(gray: np.ndarray) -> float:
    """Otsu 自动阈值（最大化类间方差）。

    注意：**前景掩膜已不再依赖它**（原因见模块文档「为什么不用单一 Otsu 阈值」）。
    保留此函数是因为它是在**双峰**图像上最快、最稳的二分手段，
    用于"背景与目标各占一大块"的简单场景（如后续的盘面二值化预处理）。

    >>> import numpy as np
    >>> g = np.concatenate([np.full(100, 20.0), np.full(100, 220.0)]).reshape(20, 10)
    >>> 100 < otsu_threshold(g) < 150
    True
    """
    flat = gray.ravel()
    if flat.size == 0:
        return DEFAULT_OTSU

    hist, edges = np.histogram(flat, bins=256, range=(0.0, 256.0))
    hist = hist.astype(np.float64)
    total = hist.sum()
    if total == 0:
        return DEFAULT_OTSU

    centres = (edges[:-1] + edges[1:]) / 2.0
    weight_bg = np.cumsum(hist)
    weight_fg = total - weight_bg
    cum_mean = np.cumsum(hist * centres)
    total_mean = cum_mean[-1]

    with np.errstate(divide="ignore", invalid="ignore"):
        mean_bg = cum_mean / weight_bg
        mean_fg = (total_mean - cum_mean) / weight_fg
        between = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2

    between = np.nan_to_num(between, nan=0.0, posinf=0.0, neginf=0.0)

    # 两类像素**等量**时，`between` 会在两类之间的整段空隙上取同一值（平台）。
    # 若取 `argmax`，得到的是平台**左端**（紧贴暗类），阈值没有余量。
    # 取平台中点，则阈值到两侧类别距离最大，对噪声与光照漂移更稳健。
    best = float(between.max())
    hits = np.flatnonzero(between >= best)
    return float((centres[hits[0]] + centres[hits[-1]]) / 2.0)


def candidate_thresholds(
    gray: np.ndarray,
    *,
    max_candidates: int = MAX_THRESHOLD_CANDIDATES,
) -> list[float]:
    """枚举所有**可能改变掩膜**的阈值。

    只有落在两个「实际出现过的灰度级」之间的阈值才会改变掩膜，因此候选集
    就是这些中点。取中点而非灰度级本身，可让恰好等于某灰度级的像素有确定
    归属（不产生边界歧义）。

    >>> import numpy as np
    >>> candidate_thresholds(np.array([[10.0, 20.0], [200.0, 210.0]]))
    [15.5, 110.5, 205.5]
    """
    flat = gray.ravel()
    if flat.size == 0:
        return [DEFAULT_OTSU]

    hist, edges = np.histogram(flat, bins=256, range=(0.0, 256.0))
    occupied = np.nonzero(hist)[0]
    if occupied.size == 0:
        return [DEFAULT_OTSU]
    if occupied.size == 1:
        lo, hi = edges[occupied[0]], edges[occupied[0] + 1]
        return [float((lo + hi) / 2.0)]

    centres = (edges[:-1] + edges[1:]) / 2.0
    occ_centres = centres[occupied]
    mids = (occ_centres[:-1] + occ_centres[1:]) / 2.0
    if mids.size > max_candidates:
        keep = np.unique(np.linspace(0, mids.size - 1, max_candidates).round().astype(np.int64))
        mids = mids[keep]
    return [float(v) for v in mids]


def central_moments(mask: np.ndarray) -> tuple[float, float, float, float, float]:
    """由行列投影求形心与二阶中心矩 —— 不物化坐标数组，省内存也更快。

    Returns:
        (cx, cy, mxx, myy, mxy)
    """
    h, w = mask.shape
    count = float(mask.sum())
    if count <= 0.0:
        return (0.0, 0.0, 0.0, 0.0, 0.0)

    col = mask.sum(axis=0, dtype=np.float64)
    row = mask.sum(axis=1, dtype=np.float64)
    xs = np.arange(w, dtype=np.float64)
    ys = np.arange(h, dtype=np.float64)

    cx = float(col @ xs) / count
    cy = float(row @ ys) / count
    mxx = float(col @ (xs - cx) ** 2) / count
    myy = float(row @ (ys - cy) ** 2) / count
    mxy = float(((mask * (ys - cy)[:, None]) * (xs - cx)[None, :]).sum()) / count
    return (cx, cy, mxx, myy, mxy)


def ellipse_from_moments(mxx: float, myy: float, mxy: float) -> tuple[float, float, float]:
    """二阶中心矩 → 等效椭圆 `(半长轴 a, 半短轴 b, 长轴倾角°)`，其中 `a >= b`。

    `[已确认]` 均匀实心椭圆关于形心的二阶中心矩为 `mxx = a²/4`、`myy = b²/4`，
    故半轴是该方向标准差的 **2 倍**（不是 1 倍 —— 这是最容易写错的地方）。
    倾角以图像坐标系（x 向右、y 向下）度量，与 `rectify_to_circle` 的旋向一致。
    """
    cov = np.array([[mxx, mxy], [mxy, myy]], dtype=np.float64)
    eigvals, eigvecs = np.linalg.eigh(cov)        # eigh 升序 → [minor, major]
    a = 2.0 * math.sqrt(max(float(eigvals[1]), 1e-9))
    b = 2.0 * math.sqrt(max(float(eigvals[0]), 1e-9))
    tilt = float(np.degrees(np.arctan2(eigvecs[1, 1], eigvecs[0, 1])))
    return a, b, tilt


@dataclass(frozen=True, slots=True)
class MaskSelection:
    """掩膜搜索结果。`found` 为 False 时 `mask` 是全 False 矩阵。"""

    mask: np.ndarray
    threshold: float
    lower_is_foreground: bool
    score: float
    fill_ratio: float
    semi_axes: tuple[float, float] | None
    tilt_deg: float | None
    rejected_because: str | None      # 未选中时的原因："no_object" / "too_large"

    @property
    def found(self) -> bool:
        return self.score > 0.0


def _disk_score(
    mask: np.ndarray, *, min_fill: float, max_fill: float
) -> tuple[float, float, tuple[float, float] | None, float | None]:
    """给「这块前景像不像一个实心圆盘」打分。返回 `score <= 0` 表示不合格。"""
    n = mask.size
    if n == 0:
        return -1.0, 0.0, None, None

    count = int(mask.sum())
    fill = count / n
    if count < MIN_FOREGROUND_PIXELS or fill < min_fill or fill > max_fill:
        return -1.0, fill, None, None

    _cx, _cy, mxx, myy, mxy = central_moments(mask)
    a, b, tilt = ellipse_from_moments(mxx, myy, mxy)
    if a * b <= 0.0:
        return -1.0, fill, None, None

    # 实心椭圆：面积 = π·a·b → 该比值 ≈1；圆环 / 零散墨点远小于 1
    score = count / (math.pi * a * b)
    if a / max(b, 1e-9) > MAX_ELLIPSE_ASPECT:
        score *= 0.5          # 过度狭长 → 不像盘体
    return score, fill, (a, b), tilt


def select_foreground_mask(
    gray: np.ndarray,
    *,
    dark_object: bool | None = None,
    min_fill: float = MIN_FILL,
    max_fill: float = MAX_FILL,
) -> MaskSelection:
    """在候选阈值上搜索「最像实心圆盘」的前景掩膜。

    Args:
        dark_object: True 只考虑「盘体比背景暗」，False 只考虑「盘体比背景亮」，
            None（推荐）= 两侧都试 —— 拍摄场景无法预知，不应让调用方猜。
    """
    lower_options = (True, False) if dark_object is None else (bool(dark_object),)

    best: MaskSelection | None = None
    saw_too_large = False

    for t in candidate_thresholds(gray):
        for lower in lower_options:
            mask = gray < t if lower else gray >= t
            score, fill, axes, tilt = _disk_score(mask, min_fill=min_fill, max_fill=max_fill)
            if score <= 0.0:
                if fill > max_fill:
                    saw_too_large = True
                continue
            # 同分时取面积更大的一侧：更完整的盘体优于被啃掉一块的
            better = (
                best is None
                or score > best.score + 1e-9
                or (abs(score - best.score) <= 1e-9 and fill > best.fill_ratio)
            )
            if better:
                best = MaskSelection(
                    mask=mask, threshold=t, lower_is_foreground=lower,
                    score=score, fill_ratio=fill, semi_axes=axes, tilt_deg=tilt,
                    rejected_because=None,
                )

    if best is not None:
        return best

    return MaskSelection(
        mask=np.zeros(gray.shape, dtype=bool), threshold=0.0, lower_is_foreground=True,
        score=-1.0, fill_ratio=0.0, semi_axes=None, tilt_deg=None,
        rejected_because="too_large" if saw_too_large else "no_object",
    )


def _work_gray(image: Image.Image, work_size: int) -> tuple[np.ndarray, tuple[int, int], float]:
    """缩放 → 灰度。返回 (gray, 缩放后尺寸, scale)。"""
    w, h = image.size
    scale = 1.0
    if max(w, h) > work_size:
        scale = work_size / max(w, h)
        image = image.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.BILINEAR)
    return to_gray_array(image), image.size, scale


def foreground_mask(
    image: Image.Image,
    *,
    dark_object: bool | None = None,
    work_size: int = DETECT_WORK_SIZE,
) -> tuple[np.ndarray, tuple[int, int], float]:
    """生成前景掩膜（罗盘盘体）—— `select_foreground_mask` 的便捷封装。

    未找到合格前景时返回**全 False 掩膜**，调用方据 `mask.any()` 判断，
    并可用 `select_foreground_mask` 直接拿到失败原因。

    Args:
        dark_object: True 表示罗盘比背景暗；False 表示比背景亮；None = 两侧都试

    Returns:
        (mask, work_size_wh, scale) —— mask 是缩放后尺寸的布尔矩阵
    """
    gray, size, scale = _work_gray(image, work_size)
    selection = select_foreground_mask(gray, dark_object=dark_object)
    return selection.mask, size, scale


def detect_circle(
    image: Image.Image,
    *,
    dark_object: bool | None = None,
    min_fill: float = MIN_FILL,
    max_fill: float = MAX_FILL,
) -> CircleDetection:
    """检测罗盘圆盘。

    Raises: 无 —— 所有失败情形都通过返回值表达（不抛异常，便于上层统一处理）。
    """
    gray, _work_wh, scale = _work_gray(image, DETECT_WORK_SIZE)
    selection = select_foreground_mask(
        gray, dark_object=dark_object, min_fill=min_fill, max_fill=max_fill,
    )

    if not selection.found:
        if selection.rejected_because == "too_large":
            return CircleDetection(
                detected=False, center=None, radius=None, confidence=0.0,
                circularity=0.0, fill_ratio=selection.fill_ratio, touches_border=True,
                reason="无法区分罗盘与背景（颜色过于接近），请换用对比更明显的背景",
            )
        return CircleDetection(
            detected=False, center=None, radius=None, confidence=0.0,
            circularity=0.0, fill_ratio=selection.fill_ratio, touches_border=False,
            reason="画面中未找到明显的罗盘盘体，请让罗盘占满识别区域",
        )

    mask = selection.mask
    cx, cy, _mxx, _myy, _mxy = central_moments(mask)
    count = float(mask.sum())
    radius = float(np.sqrt(count / np.pi))

    # ---- 圆形度：落在等效半径 1.08 倍以内的前景占比 ----
    ys, xs = np.nonzero(mask)
    dist = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    circularity = float(np.count_nonzero(dist <= radius * 1.08) / xs.size)

    # ---- 椭圆参数：直接复用打分阶段的二阶矩结果，不重复计算 ----
    semi_major, semi_minor = selection.semi_axes or (radius, radius)
    tilt = selection.tilt_deg if selection.tilt_deg is not None else 0.0

    # ---- 是否贴边 ----
    border = 2
    touches = bool(
        mask[:border, :].any() or mask[-border:, :].any()
        or mask[:, :border].any() or mask[:, -border:].any()
    )

    # ---- 置信度 ----
    confidence = circularity
    if touches:
        confidence *= 0.6
    if not 0.9 <= (semi_major / max(semi_minor, 1e-9)) <= 1.6:
        confidence *= 0.5   # 透视过度，校正后仍可能失真
    confidence = max(0.0, min(1.0, confidence))

    # 还原到原图坐标系
    inv = 1.0 / scale
    return CircleDetection(
        detected=True,
        center=(cx * inv, cy * inv),
        radius=radius * inv,
        confidence=confidence,
        circularity=circularity,
        fill_ratio=selection.fill_ratio,
        touches_border=touches,
        semi_axes=(semi_major * inv, semi_minor * inv),
        tilt_deg=tilt,
        reason=None if not touches else "罗盘未完整进入画面，边缘已被裁切",
    )


def rectified_size(detection: CircleDetection, *, padding: float = 1.08, cap: int = 1024) -> tuple[int, int]:
    """校正后正方形画布的边长。"""
    if not detection.detected or detection.semi_axes is None:
        return (cap, cap)
    diameter = 2.0 * max(detection.semi_axes) * padding
    side = int(round(min(cap, max(64.0, diameter))))
    return (side, side)


def rectify_to_circle(
    image: Image.Image,
    detection: CircleDetection,
    *,
    padding: float = 1.08,
    cap: int = 1024,
) -> Image.Image:
    """透视（椭圆）校正：把罗盘盘体归一为正圆，居中铺满画布。

    为什么必须做这一步
    ------------------
    罗盘文字是**径向排列**的。斜拍产生的椭圆会让"同一圈的字符"落在不同
    半径上，后续按角度取环带时就会取到错误的字。更关键的是：**角度本身
    也被拉偏了** —— 不校正就无法把"鱼丝线角度"读成正确的坐向。

    畸变模型与逆映射（这段是校正正确性的全部依据）
    --------------------------------------------
    把斜拍建模为 `A = Rot(θ_tilt) · diag(k, 1)`（`k <= 1`：先在规范坐标系的
    x 方向压缩，再整体旋转）。观测到的椭圆给出 `k = b/a`（a、b 为半长/半短轴）
    与半长轴方向角 `φ`，于是 `θ_tilt = φ - 90°`。

    要还原角度，必须取 `T = A⁻¹`（相差一个正标量），即：

        T = diag(1/k, 1) · Rot(-(φ - 90°))

    **两个易错点，本实现已踩过：**

    1. `θ_tilt = φ - 90°`（不是 `φ`）。`φ` 是**长轴**方向；而压缩是发生在
       规范坐标系的 **x 轴**上的，长轴对应的是变形**前**的 y 轴。用错会得到
       一个固定的 ±90° 偏差。
    2. 旋转方向取 `+(φ - 90°)`（见下式 `N` 的构造）。反号在纯压扁场景下
       恰好互相抵消、看不出问题，一旦叠加旋转（斜拍）误差就飙到 40°~60°。

    `[已确认]` 以合成罗盘标定（含 10 组「真值 × 压扁 × 旋转」组合，
    压扁 0.75~1.0、旋转 -25°~+33°）实测：校正后鱼丝线角度**最大误差 0.04°**。

    退化处理
    --------
    长宽比低于 `CIRCLE_ASPECT_TOLERANCE` 时按正圆处理：只居中裁剪，
    **不旋转也不形变**（原因见该常量的注释）。

    输出约定
    --------
    罗盘在输出图中的半径恒为 `side / (2·padding)`，与 `rectified_size`
    是否被 `cap` 截断无关 —— 下游（`pipeline`）可按同一公式给出采样半径，
    不必再分情况讨论。
    """
    if not detection.detected or detection.center is None or detection.radius is None:
        raise ValueError("未检测到罗盘，无法校正")

    cx, cy = detection.center
    side, _ = rectified_size(detection, padding=padding, cap=cap)
    half = side / 2.0

    if detection.semi_axes is None:
        a = b = float(detection.radius)
        tilt_deg = 0.0
    else:
        a, b = (max(float(v), 1e-6) for v in detection.semi_axes)
        tilt_deg = detection.tilt_deg if detection.tilt_deg is not None else 0.0

    if a / max(b, 1e-9) < CIRCLE_ASPECT_TOLERANCE:
        # 近似正圆 → 长轴方向不可信，退回等比（只做归一与居中）
        theta = 0.0
        k = 1.0
        a_eff = (a + b) / 2.0
    else:
        theta = math.radians(tilt_deg - 90.0)
        k = b / a
        a_eff = a

    # 正向映射：p_out = s · diag(1/k, 1) · Rot(-θ) · (p_in - c) + out_center
    # 取 s = side/(2·a_eff·padding) ⇒ 罗盘输出半径恒为 side/(2·padding)
    s = side / (2.0 * a_eff * padding)

    # PIL AFFINE 需要**反向**映射：p_in = N · (p_out - out_center) + c
    #   N = T⁻¹ / s = Rot(θ) · diag(k, 1) / s
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    rot = np.array([[cos_t, -sin_t], [sin_t, cos_t]], dtype=np.float64)
    n = rot @ np.array([[k / s, 0.0], [0.0, 1.0 / s]], dtype=np.float64)

    out_center = np.array([half, half], dtype=np.float64)
    offset = np.array([cx, cy], dtype=np.float64) - n @ out_center

    coeffs = (float(n[0, 0]), float(n[0, 1]), float(offset[0]),
              float(n[1, 0]), float(n[1, 1]), float(offset[1]))

    return image.convert("RGB").transform(
        (side, side), Image.AFFINE, coeffs, resample=Image.BICUBIC, fillcolor=(0, 0, 0),
    )


def circle_geometry_ok(detection: CircleDetection, *, min_radius: float = 60.0) -> tuple[bool, str | None]:
    """判定几何是否足以进入识别。"""
    if not detection.detected:
        return False, detection.reason or "未检测到罗盘"
    if detection.radius is not None and detection.radius < min_radius:
        return False, f"罗盘在画面中过小（半径约 {detection.radius:.0f}px），请靠近拍摄"
    if detection.touches_border:
        return False, "罗盘未完整进入画面，请调整距离让整个圆盘入镜"
    if detection.circularity < 0.85:
        return False, "盘体轮廓不完整，可能有遮挡或严重反光，请重新拍摄"
    return True, None


__all__ = [
    "DETECT_WORK_SIZE", "MAX_THRESHOLD_CANDIDATES", "MIN_FILL", "MAX_FILL",
    "CIRCLE_ASPECT_TOLERANCE",
    "CircleDetection", "MaskSelection",
    "otsu_threshold", "candidate_thresholds",
    "central_moments", "ellipse_from_moments",
    "select_foreground_mask", "foreground_mask", "detect_circle",
    "rectified_size", "rectify_to_circle", "circle_geometry_ok",
]
