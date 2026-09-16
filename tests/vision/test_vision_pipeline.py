"""罗盘识别管线测试 —— 用**合成图真值**断言几何与算法的正确性。

这一组用例是 Gate 1 的**工程前置**：
先把"几何与角度算得对不对"钉死，再拿真实照片去评"能不能用"。
两者不可互相替代 —— 合成图通过 ≠ Gate 1 通过。
"""

from __future__ import annotations

import math

import pytest
from PIL import Image

from xuanpan_vision.geometry import (
    detect_circle,
    otsu_threshold,
    rectified_size,
    rectify_to_circle,
)
from xuanpan_vision.models import CompassVisionResult, MountainCandidate
from xuanpan_vision.pipeline import CompassAnalyzer, PipelineConfig, analyze_compass
from xuanpan_vision.providers import (
    CAPABILITY_MATRIX,
    ProviderUnavailableError,
    get_provider,
    list_providers,
)
from xuanpan_vision.providers.manual import ManualVisionProvider
from xuanpan_vision.providers.openai_compat import extract_json
from xuanpan_vision.quality import (
    QualityThresholds,
    brightness,
    check_quality,
    glare_ratio,
    laplacian_variance,
    to_gray_array,
)
from xuanpan_vision.ring import angle_of, detect_diameter_line, point_at, polar_unwrap
from xuanpan_vision.testing import angle_error, expected_mountains, render_compass


# ==========================================================================
# 角度约定
# ==========================================================================


class TestAngleConvention:
    """项目角度约定：0=北=画面上方，顺时针。任何偏移都会让整盘结果错位。"""

    def test_cardinal_directions(self) -> None:
        assert angle_of(100, 0, 100, 100) == 0.0      # 上 → 北
        assert angle_of(200, 100, 100, 100) == 90.0   # 右 → 东
        assert angle_of(100, 200, 100, 100) == 180.0  # 下 → 南
        assert angle_of(0, 100, 100, 100) == 270.0    # 左 → 西

    def test_point_at_inverts_angle_of(self) -> None:
        for a in range(0, 360, 7):
            x, y = point_at((100.0, 100.0), 37.0, float(a))
            assert math.isclose(angle_of(x, y, 100.0, 100.0), float(a), abs_tol=1e-6)

    def test_clock_wise(self) -> None:
        """东北方向应为 45°，不是 315° —— 顺时针方向不能反。"""
        assert math.isclose(angle_of(200, 0, 100, 100), 45.0, abs_tol=1e-6)


# ==========================================================================
# 图像质量检测
# ==========================================================================


class TestQuality:
    def test_clean_image_passes(self) -> None:
        q = check_quality(render_compass(size=900, noise=1.0))
        assert q.passed
        assert q.blur_score > 100
        assert not q.blocking

    def test_blurred_fails(self) -> None:
        q = check_quality(render_compass(size=900, blur=12.0))
        assert not q.passed
        assert any(i.code == "blur" and i.severity == "fail" for i in q.issues)

    def test_dark_fails(self) -> None:
        img = Image.new("RGB", (900, 900), (8, 8, 8))
        q = check_quality(img)
        assert not q.passed
        assert any(i.code == "too_dark" for i in q.issues)

    def test_bright_fails(self) -> None:
        img = Image.new("RGB", (900, 900), (252, 252, 252))
        q = check_quality(img)
        assert not q.passed
        assert any(i.code == "too_bright" for i in q.issues)

    def test_small_fails(self) -> None:
        q = check_quality(render_compass(size=300))
        assert not q.passed
        assert any(i.code == "too_small" for i in q.issues)

    def test_glare_fails(self) -> None:
        img = render_compass(size=900, glare_box=(100, 100, 800, 450))
        q = check_quality(img)
        assert q.glare_ratio > 0.18
        assert any(i.code == "glare" and i.severity == "fail" for i in q.issues)

    def test_laplacian_zero_on_flat(self) -> None:
        import numpy as np

        assert laplacian_variance(np.full((32, 32), 128.0)) == 0.0

    def test_laplacian_higher_on_edges(self) -> None:
        import numpy as np

        flat = np.full((32, 32), 128.0)
        edge = flat.copy()
        edge[:, 16:] = 250.0
        assert laplacian_variance(edge) > laplacian_variance(flat)

    def test_glare_ratio_math(self) -> None:
        import numpy as np

        g = np.zeros((10, 10))
        g[0, :] = 255.0
        assert math.isclose(glare_ratio(g), 0.1, abs_tol=1e-9)

    def test_brightness(self) -> None:
        import numpy as np

        assert math.isclose(brightness(np.full((4, 4), 77.0)), 77.0)

    def test_thresholds_are_overridable(self) -> None:
        """阈值必须可覆盖 —— 现场调参不应改代码。"""
        strict = QualityThresholds(blur_fail=1e9)
        q = check_quality(render_compass(size=900), thresholds=strict)
        assert not q.passed

    def test_report_serializable(self) -> None:
        q = check_quality(render_compass(size=900))
        d = q.to_dict()
        assert d["size"] == [900, 900]
        assert isinstance(d["issues"], list)


# ==========================================================================
# 几何：圆检测与透视校正
# ==========================================================================


class TestOtsu:
    def test_separates_two_modes(self) -> None:
        import numpy as np

        g = np.concatenate([np.full(400, 30.0), np.full(400, 220.0)]).reshape(40, 20)
        t = otsu_threshold(g)
        assert 30.0 < t < 220.0

    def test_empty_returns_default(self) -> None:
        import numpy as np

        assert otsu_threshold(np.array([])) == 128.0


class TestCircleDetection:
    def test_centered_circle(self) -> None:
        img = render_compass(size=900, radius_ratio=0.42)
        det = detect_circle(img)
        assert det.detected
        assert det.center is not None
        assert math.isclose(det.center[0], 450.0, abs_tol=12.0)
        assert math.isclose(det.center[1], 450.0, abs_tol=12.0)
        # 半径取前景面积等效半径，深色外圈占比高 → 允许 15% 偏差
        assert math.isclose(det.radius, 900 * 0.42, rel_tol=0.15)
        assert det.circularity > 0.98

    def test_blank_image_not_detected(self) -> None:
        det = detect_circle(Image.new("RGB", (600, 600), (200, 200, 200)))
        assert not det.detected
        assert det.center is None
        assert det.reason

    def test_noise_robustness(self) -> None:
        det = detect_circle(render_compass(size=900, noise=6.0))
        assert det.detected
        assert det.circularity > 0.95

    def test_detects_ellipse_axes(self) -> None:
        img = render_compass(size=900, squash=0.72)
        det = detect_circle(img)
        assert det.detected
        assert det.semi_axes is not None
        major, minor = det.semi_axes
        assert major > minor * 1.15, "应识别出明显的椭圆"


class TestRectification:
    def test_recovers_thread_angle_after_squash(self) -> None:
        """斜拍产生的椭圆，校正后鱼丝线角度必须回到真值 —— 这是校正存在的意义。"""
        for truth in (0.0, 45.0, 90.0, 135.0):
            img = render_compass(size=900, thread_angle=truth, squash=0.75)
            det = detect_circle(img)
            assert det.detected
            rect = rectify_to_circle(img, det, cap=1024)
            side = rect.width
            center = (side / 2.0, side / 2.0)
            radius = side / (2.0 * 1.08)
            profile, _ = polar_unwrap(to_gray_array(rect), center, radius)
            line = detect_diameter_line(profile)
            assert angle_error(line.angle, truth) < 4.0, (
                f"真值 {truth}° 校正后测得 {line.angle:.2f}°"
            )

    def test_rectified_is_square(self) -> None:
        img = render_compass(size=900, squash=0.8)
        det = detect_circle(img)
        rect = rectify_to_circle(img, det, cap=1024)
        assert rect.width == rect.height
        assert rect.width <= 1024

    def test_rectify_size_uses_major_axis(self) -> None:
        img = render_compass(size=900, squash=0.7)
        det = detect_circle(img)
        side, _ = rectified_size(det, padding=1.08, cap=1024)
        assert 64 <= side <= 1024

    def test_rectify_requires_detection(self) -> None:
        det = detect_circle(Image.new("RGB", (600, 600), (200, 200, 200)))
        with pytest.raises(ValueError):
            rectify_to_circle(Image.new("RGB", (600, 600), (200, 200, 200)), det)


# ==========================================================================
# 鱼丝线检测
# ==========================================================================


class TestDiameterLine:
    @pytest.mark.parametrize("truth", [0.0, 15.0, 60.0, 90.0, 123.0, 165.0])
    def test_angle_accuracy(self, truth: float) -> None:
        img = render_compass(size=900, thread_angle=truth)
        det = detect_circle(img)
        rect = rectify_to_circle(img, det, cap=1024)
        side = rect.width
        profile, _ = polar_unwrap(to_gray_array(rect), (side / 2, side / 2), side / (2 * 1.08))
        line = detect_diameter_line(profile)
        assert line.confidence > 0.5, f"真值 {truth}° 未测出线"
        assert angle_error(line.angle, truth) < 1.5

    def test_printed_blobs_are_not_mistaken_for_thread(self) -> None:
        """印刷文字/刻度只覆盖窄半径带，不得被误判为贯通直径的鱼丝线。"""
        img = render_compass(size=900, thread_angle=90.0, label_blobs=True, ticks=True)
        det = detect_circle(img)
        rect = rectify_to_circle(img, det, cap=1024)
        side = rect.width
        profile, _ = polar_unwrap(to_gray_array(rect), (side / 2, side / 2), side / (2 * 1.08))
        line = detect_diameter_line(profile)
        assert angle_error(line.angle, 90.0) < 2.0

    def test_no_thread_returns_zero_confidence(self) -> None:
        """没有鱼丝线时置信度必须为 0 —— RULE-003，不猜。

        `thread_value=195` = 渲染器默认的**盘面内圈色** (`inner`)。鱼丝线绝大部分
        长度横跨内圈，取内圈色才是真正"看不见的线"。
        （早先此处用 170 —— 那是**盘边**色，线在内圈上仍比底色暗，属夹具取值错误。）
        """
        img = render_compass(size=900, thread_value=195)  # 与盘面内圈同色 → 无可见线
        det = detect_circle(img)
        rect = rectify_to_circle(img, det, cap=1024)
        side = rect.width
        profile, _ = polar_unwrap(to_gray_array(rect), (side / 2, side / 2), side / (2 * 1.08))
        line = detect_diameter_line(profile)
        assert line.confidence == 0.0


# ==========================================================================
# 端到端管线
# ==========================================================================


class TestPipelineEndToEnd:
    @pytest.mark.parametrize("truth", [0.0, 90.0, 135.0, 270.0])
    def test_mountains_match_truth(self, truth: float) -> None:
        img = render_compass(size=900, thread_angle=truth)
        result, prepared = analyze_compass(img)
        assert prepared is not None
        assert result.compass_detected
        got = {c.name for c in result.mountain_candidates}
        assert got == expected_mountains(truth), f"真值 {truth}° → 期望 {expected_mountains(truth)}，实得 {got}"

    def test_mountains_match_truth_under_perspective(self) -> None:
        """斜拍 + 旋转后仍应给出正确的对宫候选。"""
        for truth, squash, tilt in ((0.0, 0.78, 18.0), (90.0, 0.8, -25.0), (45.0, 0.85, 33.0)):
            img = render_compass(size=900, thread_angle=truth, squash=squash, tilt=tilt)
            result, prepared = analyze_compass(img)
            assert result.compass_detected, f"真值 {truth}° 斜拍未被检出"
            got = {c.name for c in result.mountain_candidates}
            assert got == expected_mountains(truth), f"真值 {truth}° → 期望 {expected_mountains(truth)}，实得 {got}"

    def test_sitting_and_facing_are_opposite(self) -> None:
        from fortune_core.mountain24 import is_opposite

        img = render_compass(size=900, thread_angle=30.0)
        result, _ = analyze_compass(img)
        for s in result.mountain_candidates:
            for f in result.direction_candidates:
                if s.name != f.name:
                    pass
        assert result.best_sitting is not None
        assert result.best_facing is not None
        assert is_opposite(result.best_sitting.name, result.best_facing.name)

    def test_needs_user_confirmation_always_true(self) -> None:
        """RULE-004：识别结果必须允许用户修正，任何情况下都不得自动放行。"""
        for truth in (0.0, 90.0, 200.0):
            img = render_compass(size=900, thread_angle=truth)
            result, _ = analyze_compass(img)
            assert result.needs_user_confirmation is True

    def test_quality_failure_rejected_before_recognition(self) -> None:
        result, prepared = analyze_compass(render_compass(size=900, blur=14.0))
        assert prepared is None
        assert not result.compass_detected
        assert result.mountain_candidates == ()
        assert result.quality is not None and not result.quality.passed

    def test_no_compass_rejected(self) -> None:
        result, prepared = analyze_compass(Image.new("RGB", (900, 900), (205, 205, 205)))
        assert prepared is None
        assert not result.compass_detected
        assert result.uncertain_regions

    def test_result_serializable(self) -> None:
        img = render_compass(size=900, thread_angle=15.0)
        result, _ = analyze_compass(img)
        d = result.to_dict()
        assert isinstance(d["mountain_candidates"], list)
        assert d["needs_user_confirmation"] is True
        assert d["quality"]["passed"] is True

    def test_invalid_bytes_rejected(self) -> None:
        with pytest.raises(ValueError):
            analyze_compass(b"not an image at all")

    def test_analyzer_holds_no_state(self) -> None:
        """同一实例重复分析不同图，结果不得互相污染。"""
        analyzer = CompassAnalyzer()
        a, _ = analyzer.analyze(render_compass(size=900, thread_angle=0.0))
        b, _ = analyzer.analyze(render_compass(size=900, thread_angle=90.0))
        assert {c.name for c in a.mountain_candidates} == expected_mountains(0.0)
        assert {c.name for c in b.mountain_candidates} == expected_mountains(90.0)


# ==========================================================================
# 交叉校验（RULE-002 在识别层的落地）
# ==========================================================================


class _BogusProvider:
    """故意返回错误角度与非法山名的 provider —— 用来验证校验层是否真的拦得住。"""

    name = "bogus"
    capability = "test"
    requires_api_key = False

    def is_available(self) -> bool:
        return True

    def analyze(self, prepared):  # noqa: ANN001
        return CompassVisionResult(
            compass_detected=True,
            center=prepared.center,
            radius=prepared.radius,
            mountain_candidates=(
                MountainCandidate("子", 123.0, 0.99, "sitting"),   # 角度被篡改
                MountainCandidate("戊", 0.0, 0.99, "sitting"),      # 非法山名
            ),
            direction_candidates=(MountainCandidate("酉", 66.0, 0.99, "facing"),),  # 非对宫
            needs_user_confirmation=False,
            provider=self.name,
        )


class TestCrossValidation:
    def test_provider_cannot_inject_angle(self) -> None:
        """识别层没有权力定义角度 —— 一律以 fortune_core 的规范值为准。"""
        result, _ = analyze_compass(render_compass(size=900), provider=_BogusProvider())
        by_name = {c.name: c for c in result.mountain_candidates}
        assert by_name["子"].angle == 0.0, "被篡改的角度必须被纠正"
        assert any("角度被改写" in w for w in result.warnings)

    def test_illegal_mountain_dropped(self) -> None:
        result, _ = analyze_compass(render_compass(size=900), provider=_BogusProvider())
        assert all(c.name != "戊" for c in result.mountain_candidates)
        assert any("非法山名" in w for w in result.warnings)

    def test_facing_forced_to_opposite(self) -> None:
        from fortune_core.mountain24 import is_opposite

        result, _ = analyze_compass(render_compass(size=900), provider=_BogusProvider())
        assert result.best_facing is not None
        assert is_opposite(result.best_sitting.name, result.best_facing.name)
        assert any("对宫" in w for w in result.warnings)

    def test_confirmation_forced_true(self) -> None:
        result, _ = analyze_compass(render_compass(size=900), provider=_BogusProvider())
        assert result.needs_user_confirmation is True, "provider 无权关闭用户确认"

    def test_illegal_angle_replaced_by_center(self) -> None:
        """与山名矛盾的角度 → 用山心角覆盖（provider 不得把角度塞进别的山）。"""
        from fortune_core.mountain24 import get_mountain

        result, _ = analyze_compass(render_compass(size=900), provider=_BogusProvider())
        for c in result.mountain_candidates + result.direction_candidates:
            assert c.angle == get_mountain(c.name).center_degree

    def test_measurement_inside_mountain_is_preserved(self) -> None:
        """落在所属山范围内的实测角**必须保留** —— 否则分金永远落在正中格。

        一百二十分金是 3° 级精度：把实测角一律替换成山心角，等于把整个分金
        功能废掉（永远返回同一个格位）。这条测试锁住"精度不被校验顺手抹掉"。
        """
        from fortune_core.mountain24 import HALF_SPAN, angular_distance, get_mountain

        # 3.0° 落在「子」山范围内（子山 352.5°~7.5°），但明显偏离山心 0°
        result, _ = analyze_compass(render_compass(size=900, thread_angle=3.0))
        by_name = {c.name: c for c in result.mountain_candidates}
        assert "子" in by_name
        best = by_name["子"]
        assert angular_distance(best.angle, 3.0) < 0.5, (
            f"实测角应被保留（约 3.0°），实得 {best.angle:.2f}°"
        )
        assert best.angle != get_mountain("子").center_degree, "不得被压回山心角"
        assert angular_distance(best.angle, get_mountain("子").center_degree) <= HALF_SPAN

        # 对宫端同样应保留实测角（坐向轴是一条直线，两端测量同源）
        face = {c.name: c for c in result.direction_candidates}["午"]
        assert angular_distance(face.angle, 183.0) < 0.5, (
            f"向山实测角应约 183.0°，实得 {face.angle:.2f}°"
        )


# ==========================================================================
# Provider 注册表与手动路径
# ==========================================================================


class TestProviders:
    def test_registry_lists_three(self) -> None:
        ids = {p["id"] for p in list_providers()}
        assert ids == {"classical", "openai_compat", "manual"}

    def test_classical_always_available(self) -> None:
        assert get_provider("classical").is_available()

    def test_cloud_unavailable_without_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XUANPAN_VISION_API_KEY", raising=False)
        assert get_provider("openai_compat", api_key="").is_available() is False

    def test_cloud_marked_as_paid(self) -> None:
        entry = next(p for p in CAPABILITY_MATRIX if p["id"] == "openai_compat")
        assert entry["requires_api_key"] is True
        assert "计费" in entry["cost"]

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(KeyError):
            get_provider("no_such_provider")

    def test_analyzer_refuses_unavailable_provider(self) -> None:
        with pytest.raises(ProviderUnavailableError):
            CompassAnalyzer(provider=get_provider("openai_compat", api_key=""))

    def test_manual_provider_sitting(self) -> None:
        img = render_compass(size=900)
        result, _ = analyze_compass(img, provider="manual", sitting="午", facing="子")
        assert result.compass_detected
        assert result.best_sitting.name == "午"
        assert result.best_facing.name == "子"
        assert result.needs_user_confirmation is False
        assert result.confidence == 1.0

    def test_manual_provider_invalid_pair_rejected(self) -> None:
        """用户给的值不合法时如实报错，不替用户"修正"（RULE-008）。"""
        img = render_compass(size=900)
        result, _ = analyze_compass(img, provider="manual", sitting="子", facing="癸")
        assert not result.compass_detected
        assert "不成立" in result.uncertain_regions[0]

    def test_manual_provider_requires_input(self) -> None:
        img = render_compass(size=900)
        result, _ = analyze_compass(img, provider="manual")
        assert not result.compass_detected


class TestVisionResultModel:
    def test_rejected_has_no_candidates(self) -> None:
        r = CompassVisionResult.rejected("未检测到罗盘", provider="test")
        assert not r.compass_detected
        assert r.mountain_candidates == ()
        assert r.direction_candidates == ()
        assert r.confidence == 0.0
        assert not r.auto_acceptable

    def test_confidence_takes_weaker_side(self) -> None:
        r = CompassVisionResult(
            compass_detected=True,
            mountain_candidates=(MountainCandidate("子", 0.0, 0.9),),
            direction_candidates=(MountainCandidate("午", 180.0, 0.4),),
        )
        assert r.confidence == 0.4

    def test_auto_acceptable_requires_both(self) -> None:
        r = CompassVisionResult(
            compass_detected=True,
            mountain_candidates=(MountainCandidate("子", 0.0, 0.9),),
            direction_candidates=(MountainCandidate("午", 180.0, 0.9),),
        )
        assert r.auto_acceptable


class TestVisionPromptContract:
    """Vision Prompt 是产品方案 §8 的核心资产，其禁止项不得被删改。"""

    def test_prompt_keeps_all_prohibitions(self) -> None:
        from xuanpan_vision.providers.openai_compat import VISION_PROMPT

        for phrase in ("不是进行风水推理", "根据风水理论猜测", "八字补全文字",
                       "输出成确定值", "返回 null"):
            assert phrase in VISION_PROMPT, f"Prompt 丢失关键约束：{phrase}"

    def test_prompt_lists_24_mountains(self) -> None:
        from xuanpan_vision.providers.openai_compat import VISION_PROMPT

        for m in "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬":
            assert m in VISION_PROMPT

    def test_extract_json_plain(self) -> None:
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_extract_json_fenced(self) -> None:
        text = "这是结果：\n```json\n{\"compass_detected\": true}\n```\n完成"
        assert extract_json(text)["compass_detected"] is True

    def test_extract_json_with_prose(self) -> None:
        assert extract_json('好的，分析如下 {"x": [1, 2]} 以上')["x"] == [1, 2]

    def test_extract_json_failure(self) -> None:
        with pytest.raises(ValueError):
            extract_json("完全没有 JSON")
