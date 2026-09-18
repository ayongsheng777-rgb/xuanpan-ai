"""传感器质量评估（`lib/sensorQuality.ts`）的锚点测试。

## 为什么需要这道测试

质量评分是纯规则，错了**不会报错**，只会在真机上给出误导性提示：

1. **方位波动必须用圆统计** —— 347° 与 2° 实际只差 15°，
   若误用算术标准差会算出 ~172° 的「剧烈波动」，
   用户在室内稳持手机也会被提示「方向不稳定」。
2. **平放姿态必须是 0°** —— roll 公式若用 `atan2(y, z)`（z 平放时为负），
   平放会被算成 180° 倾斜，质量分永远不及格。
3. **磁干扰必须压分** —— 强度超出地磁区间时 magnetic 被压到 ≤30，
   若漏了这条，「把手机贴在音箱上」也会显示「磁场稳定」。
4. **空样本必须报不可用** —— 「没有数据」和「数据很好」是两回事，
   模拟器上若显示满分，用户会以为测量有效。

## 校验方式

真正**执行** `sensor_quality_probe.ts`（Node ≥ 22.6 类型擦除）取回计算结果，
逐项与期望值比对 —— 不是扫源码。

没有 Node 时跳过（而非失败），与 `test_compass_dial_parity.py` 同口径。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/sensor_quality_probe.ts"


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过传感器质量锚点校验")
    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


# ==========================================================================
# 基础量
# ==========================================================================


class TestMagnitude:
    def test_zero(self, probe: dict) -> None:
        assert probe["magnitude"]["zero"] == 0

    def test_unit(self, probe: dict) -> None:
        assert probe["magnitude"]["unit_x"] == 1

    def test_345_triangle(self, probe: dict) -> None:
        assert probe["magnitude"]["v345"] == pytest.approx(5.0)

    def test_typical_field_in_earth_range(self, probe: dict) -> None:
        """典型地磁读数 (12.3, -45.7, 8.1) 的模必须落在地磁区间内。"""
        mag = probe["magnitude"]["typical"]
        assert 25 <= mag <= 65


class TestAzimuth:
    """平放时设备 y 轴（屏幕上方）与磁北的相对方向。"""

    def test_north_ahead_is_zero(self, probe: dict) -> None:
        assert probe["azimuth"]["north"] == pytest.approx(0.0, abs=1e-9)

    def test_north_behind_is_180(self, probe: dict) -> None:
        assert probe["azimuth"]["south"] == pytest.approx(180.0)

    def test_result_in_0_360(self, probe: dict) -> None:
        for key, val in probe["azimuth"].items():
            assert 0 <= val < 360, f"{key} = {val} 超出 [0, 360)"

    def test_typical_reading(self, probe: dict) -> None:
        """(12.3, -45.7) → atan2(-12.3, -45.7) ≈ 195.06°。"""
        assert probe["azimuth"]["typical"] == pytest.approx(195.064, abs=0.001)


class TestTilt:
    def test_flat_is_zero(self, probe: dict) -> None:
        """平放必须算出 (0, 0) —— roll 公式错一个负号就会得 180°。"""
        flat = probe["tilt"]["flat"]
        assert flat["pitch"] == pytest.approx(0.0, abs=1e-9)
        assert flat["roll"] == pytest.approx(0.0, abs=1e-9)

    def test_nose_down_30(self, probe: dict) -> None:
        assert probe["tilt"]["nose_down_30"]["roll"] == pytest.approx(30.0, abs=0.01)

    def test_right_down_45(self, probe: dict) -> None:
        assert probe["tilt"]["right_down_45"]["pitch"] == pytest.approx(-45.0, abs=0.01)


class TestCircularStdev:
    def test_wrap_around_is_small(self, probe: dict) -> None:
        """核心锚点：347°/2°/355°/359° 的波动必须 < 10°。

        算术标准差会给出 ~150° 的假波动 —— 这条挂了说明圆统计被改坏了。
        """
        assert probe["circularStdev"]["wrap_around"] < 10

    def test_opposite_directions_is_max(self, probe: dict) -> None:
        """0° 与 180° 完全反向 → 最大不确定度，截断到 180，不得发散。"""
        assert probe["circularStdev"]["opposite"] == 180

    def test_tight_cluster(self, probe: dict) -> None:
        assert probe["circularStdev"]["tight"] < 2

    def test_empty_is_max(self, probe: dict) -> None:
        assert probe["circularStdev"]["empty"] == 180


# ==========================================================================
# 综合质量评估
# ==========================================================================


class TestAssessQuality:
    def test_ideal_is_perfect(self, probe: dict) -> None:
        q = probe["quality"]["ideal"]
        assert q["overall"] == 100
        assert q["grade"] == "优"
        assert q["magneticLabel"] == "稳定"
        assert q["levelLabel"] == "水平"
        assert q["hints"] == []

    def test_interference_caps_magnetic(self, probe: dict) -> None:
        """磁场 120μT（贴着音箱）：magnetic 必须 ≤30、overall 被拉低、带可操作提示。"""
        q = probe["quality"]["interference"]
        assert q["magnetic"] <= 30
        assert q["magneticLabel"] == "异常"
        assert q["overall"] < 100
        assert any("移动" in h for h in q["hints"]), q["hints"]

    def test_tilted_lowers_level(self, probe: dict) -> None:
        q = probe["quality"]["tilted"]
        assert q["level"] < 50
        assert q["levelLabel"] == "倾斜"
        assert any("水平" in h for h in q["hints"])

    def test_shaky_lowers_stability(self, probe: dict) -> None:
        q = probe["quality"]["shaky"]
        assert q["stability"] < 30
        assert any("持稳" in h for h in q["hints"])

    def test_empty_reports_unavailable_not_perfect(self, probe: dict) -> None:
        """空样本 = 传感器不可用，必须全 0 + 提示，**不得**假装满分。"""
        q = probe["quality"]["empty"]
        assert q["overall"] == 0
        assert q["grade"] == "差"
        assert any("传感器" in h for h in q["hints"])

    def test_overall_is_weighted(self, probe: dict) -> None:
        """overall = 0.4·magnetic + 0.3·level + 0.3·stability（四舍五入）。

        权重一改，三张指标卡的相对重要性就变了 —— 这是产品口径，不是实现细节。
        """
        for name, q in probe["quality"].items():
            if name == "empty":
                continue
            expect = round(q["magnetic"] * 0.4 + q["level"] * 0.3 + q["stability"] * 0.3)
            assert q["overall"] == expect, f"{name}: {q['overall']} != {expect}"

    def test_scores_bounded(self, probe: dict) -> None:
        for name, q in probe["quality"].items():
            for key in ("magnetic", "level", "stability", "overall"):
                assert 0 <= q[key] <= 100, f"{name}.{key} = {q[key]}"
