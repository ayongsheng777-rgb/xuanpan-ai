"""图像质量检测 —— 对应产品方案 §7。

**相机与相册两条入口共用同一套检测**（基线规范 §4 硬性要求）：
相册里的旧照片同样可能模糊或反光，不得因为"是用户自己选的"就跳过。

检测项：
- 清晰度：拉普拉斯方差（Laplacian Variance），低于阈值判为模糊
- 反光：过曝（>250）像素占比
- 亮度：平均亮度，过暗/过亮都影响识别
- 尺寸：过小则文字不可能看清

阈值取值依据：`[推测]` 基于手机拍摄罗盘的常见分布给出的经验值，
集中定义在 `QualityThresholds`，便于按实测数据回归调整（而非散落在调用处）。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from .models import QualityIssue, QualityReport

#：拉普拉斯算子（四邻）
_LAPLACIAN_KERNEL = np.array(
    [[0.0, 1.0, 0.0],
     [1.0, -4.0, 1.0],
     [0.0, 1.0, 0.0]],
    dtype=np.float64,
)


@dataclass(frozen=True, slots=True)
class QualityThresholds:
    """质量阈值。`[推测]` 经验值，随实测数据回归。"""

    blur_fail: float = 60.0        # 拉普拉斯方差低于此值 → 不通过
    blur_warn: float = 140.0       # 低于此值 → 通过但提示
    glare_fail: float = 0.18       # 过曝像素占比超过 → 不通过
    glare_warn: float = 0.08
    brightness_min: float = 45.0
    brightness_max: float = 215.0
    min_side: int = 480            # 短边最小像素


DEFAULT_THRESHOLDS = QualityThresholds()


def to_gray_array(image: Image.Image) -> np.ndarray:
    """PIL 图像 → float64 灰度矩阵。"""
    return np.asarray(image.convert("L"), dtype=np.float64)


def laplacian_variance(gray: np.ndarray) -> float:
    """拉普拉斯方差 —— 清晰度指标。

    实现为显式 3×3 卷积（仅用 numpy，不引入 OpenCV）。
    方差越大表示边缘越锐利、图像越清晰。

    >>> import numpy as np
    >>> flat = np.full((32, 32), 128.0)
    >>> laplacian_variance(flat)
    0.0
    """
    if gray.ndim != 2 or gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0

    # 用切片拼出 9 个平移视图，比循环快且易读
    h, w = gray.shape
    acc = np.zeros((h - 2, w - 2), dtype=np.float64)
    for dy in range(3):
        for dx in range(3):
            k = _LAPLACIAN_KERNEL[dy, dx]
            if k:
                acc += k * gray[dy:dy + h - 2, dx:dx + w - 2]
    return float(acc.var())


def glare_ratio(gray: np.ndarray, *, highlight: float = 250.0) -> float:
    """过曝（反光）像素占比。

    >>> import numpy as np
    >>> g = np.zeros((10, 10)); g[0, :] = 255.0
    >>> round(glare_ratio(g), 3)
    0.1
    """
    if gray.size == 0:
        return 0.0
    return float(np.count_nonzero(gray >= highlight) / gray.size)


def brightness(gray: np.ndarray) -> float:
    return float(gray.mean()) if gray.size else 0.0


def check_quality(
    image: Image.Image,
    *,
    thresholds: QualityThresholds = DEFAULT_THRESHOLDS,
) -> QualityReport:
    """执行全部质量检测，返回报告。

    只要存在 `severity == "fail"` 的问题，`passed` 即为 False，
    调用方**必须**中止识别并提示用户重拍/重选。
    """
    gray = to_gray_array(image)
    w, h = image.size

    blur = laplacian_variance(gray)
    glare = glare_ratio(gray)
    bright = brightness(gray)

    issues: list[QualityIssue] = []

    if blur < thresholds.blur_fail:
        issues.append(QualityIssue(
            code="blur", severity="fail",
            message="照片过于模糊，请重新拍摄并保持手机稳定",
            metric=blur, threshold=thresholds.blur_fail,
        ))
    elif blur < thresholds.blur_warn:
        issues.append(QualityIssue(
            code="blur", severity="warn",
            message="照片清晰度偏低，识别结果可能不准确",
            metric=blur, threshold=thresholds.blur_warn,
        ))

    if glare > thresholds.glare_fail:
        issues.append(QualityIssue(
            code="glare", severity="fail",
            message="画面反光面积过大，请避开直射光或改变拍摄角度",
            metric=glare, threshold=thresholds.glare_fail,
        ))
    elif glare > thresholds.glare_warn:
        issues.append(QualityIssue(
            code="glare", severity="warn",
            message="画面存在反光，可能遮挡部分文字",
            metric=glare, threshold=thresholds.glare_warn,
        ))

    if bright < thresholds.brightness_min:
        issues.append(QualityIssue(
            code="too_dark", severity="fail",
            message="画面过暗，请在光线充足处重新拍摄",
            metric=bright, threshold=thresholds.brightness_min,
        ))
    elif bright > thresholds.brightness_max:
        issues.append(QualityIssue(
            code="too_bright", severity="fail",
            message="画面过亮（可能过曝），请降低曝光或避开强光",
            metric=bright, threshold=thresholds.brightness_max,
        ))

    if min(w, h) < thresholds.min_side:
        issues.append(QualityIssue(
            code="too_small", severity="fail",
            message=f"图片分辨率过低（{w}×{h}），罗盘文字无法看清，请使用原图",
            metric=float(min(w, h)), threshold=float(thresholds.min_side),
        ))

    has_fail = any(i.severity == "fail" for i in issues)
    return QualityReport(
        passed=not has_fail,
        blur_score=blur,
        glare_ratio=glare,
        brightness=bright,
        width=w,
        height=h,
        issues=tuple(issues),
    )


__all__ = [
    "QualityThresholds", "DEFAULT_THRESHOLDS",
    "to_gray_array", "laplacian_variance", "glare_ratio", "brightness", "check_quality",
]
