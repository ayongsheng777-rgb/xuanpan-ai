"""xuanpan-vision —— 罗盘视觉识别层。

职责边界（严格）：
- 只做「图像 → 结构化候选」
- **不含任何风水推理**，不含吉凶判断
- 角度 → 二十四山的映射一律调用 `fortune_core`，本层不复制一份表

对应 RULE-005：罗盘规则不得散落 —— 因此本层唯一的领域依赖就是 fortune_core。
"""

from __future__ import annotations

from .geometry import (
    CircleDetection,
    MaskSelection,
    candidate_thresholds,
    central_moments,
    circle_geometry_ok,
    detect_circle,
    ellipse_from_moments,
    foreground_mask,
    otsu_threshold,
    rectify_to_circle,
    rectified_size,
    select_foreground_mask,
)
from .models import (
    CompassVisionResult,
    MountainCandidate,
    QualityIssue,
    QualityReport,
)
from .pipeline import (
    CompassAnalyzer,
    PipelineConfig,
    analyze_compass,
)
from .providers import (
    CAPABILITY_MATRIX,
    ProviderUnavailableError,
    VisionProvider,
    get_provider,
    list_providers,
)
from .quality import (
    DEFAULT_THRESHOLDS,
    QualityThresholds,
    check_quality,
    glare_ratio,
    laplacian_variance,
)
from .ring import (
    LineMeasure,
    NeedleMeasure,
    angle_of,
    detect_diameter_line,
    detect_needle,
    polar_unwrap,
    point_at,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # 质检
    "QualityThresholds", "DEFAULT_THRESHOLDS", "check_quality",
    "laplacian_variance", "glare_ratio",
    # 几何
    "CircleDetection", "MaskSelection", "detect_circle", "otsu_threshold",
    "candidate_thresholds", "central_moments", "ellipse_from_moments",
    "select_foreground_mask", "foreground_mask",
    "rectify_to_circle", "rectified_size", "circle_geometry_ok",
    # 极坐标
    "angle_of", "point_at", "polar_unwrap",
    "LineMeasure", "NeedleMeasure", "detect_diameter_line", "detect_needle",
    # 模型
    "QualityIssue", "QualityReport", "MountainCandidate", "CompassVisionResult",
    # 管线
    "CompassAnalyzer", "PipelineConfig", "analyze_compass",
    # provider
    "VisionProvider", "ProviderUnavailableError", "get_provider",
    "list_providers", "CAPABILITY_MATRIX",
]
