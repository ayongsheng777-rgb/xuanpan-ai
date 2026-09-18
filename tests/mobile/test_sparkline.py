"""磁场曲线几何（`lib/sparkline.ts`）的锚点测试。

## 为什么需要这道测试

归一化写错**不会报错**，只会让曲线"看起来有点怪"或干脆不出现。
其中有两条错误在真机与模拟器上都极难发现：

1. **恒定读数 → 除零 → NaN** —— 手机静止平放时磁场读数几乎不变，
   `max - min ≈ 0`，直接当分母就得到 `NaN` 路径，**整条曲线静默消失**。
   不崩溃、不警告，只是空白 —— 而"数据明明有、界面却空白"最难定位。
2. **上下颠倒** —— y 轴在 SVG 里向下增长，公式少一个负号会让"磁场强"画成"曲线低"。
   颠倒后的曲线仍然是一条像样的曲线，肉眼完全看不出问题。

## 校验方式

真正**执行** `sparkline_probe.ts`（Node ≥ 22.6 类型擦除）取回结果，
并用正则**解析 `d` 字符串里真实的坐标**再断言 —— 验的是"画出来的点"，
不是"源码里像是对的"。没有 Node 时跳过（而非失败），与 `test_sensor_quality.py` 同口径。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/sparkline_probe.ts"

# 匹配 "M 12.5 34.25" / "L -3 66" 这类指令对
_POINT_RE = re.compile(r"[ML]\s+(-?[\d.]+)\s+(-?[\d.]+)")


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过曲线几何锚点校验")
    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _geo(probe: dict, name: str) -> dict:
    return probe["geometry"][name]


def _points(d: str) -> list[tuple[float, float]]:
    """把 path 字符串解析成坐标列表 —— 断言作用于真实坐标，而非字符串长相。"""
    assert "NaN" not in d and "Infinity" not in d, f"路径里出现了非有限数：{d}"
    return [(float(x), float(y)) for x, y in _POINT_RE.findall(d)]


# ==========================================================================
# 无数据与脏数据
# ==========================================================================


class TestMissingData:
    def test_empty_returns_null(self, probe: dict) -> None:
        """空序列必须返回 null，而不是空路径 —— 调用方要能区分"没数据"。"""
        assert probe["nullCases"]["empty"] is True

    def test_all_non_finite_returns_null(self, probe: dict) -> None:
        """全是 NaN/Infinity 等同于没有数据，不得硬画。"""
        assert probe["nullCases"]["allNonFinite"] is True

    def test_survives_dirty_data(self, probe: dict) -> None:
        """序列里混进一个 NaN，其余点仍应照常画出（一个坏样本不该毁掉整条线）。"""
        assert probe["survivesDirtyData"] is True
        assert probe["dirtyPointCount"] == 2


# ==========================================================================
# 坐标映射
# ==========================================================================


class TestCoordinateMapping:
    def test_constant_series_has_no_nan_and_sits_on_midline(self, probe: dict) -> None:
        """核心锚点：恒定序列（手机静止平放）必须落在中线且不产生 NaN。

        未做跨度保护时这里会得到 NaN，曲线整体消失 —— 这是本文件存在的主要理由。
        """
        geo = _geo(probe, "constant")
        pts = _points(geo["d"])
        assert len(pts) == 5
        height = probe["options"]["height"]
        for _, y in pts:
            assert y == pytest.approx(height / 2, abs=0.01), f"恒定序列应落中线，实得 {y}"

    def test_single_point_sits_at_horizontal_center(self, probe: dict) -> None:
        """单点画成零长度线段（配合 round 线帽显示为点），x 居中。"""
        geo = _geo(probe, "single")
        pts = _points(geo["d"])
        assert len(pts) == 2, f"单点应产出 M+L 两个坐标，实得 {len(pts)}"
        width = probe["options"]["width"]
        ys = {y for _, y in pts}
        assert len(ys) == 1
        assert next(iter(ys)) == pytest.approx(probe["options"]["height"] / 2, abs=0.01)
        for x, _ in pts:
            assert x == pytest.approx(width / 2, abs=0.01)

    def test_x_axis_spans_full_width(self, probe: dict) -> None:
        geo = _geo(probe, "wide")
        pts = _points(geo["d"])
        width = probe["options"]["width"]
        assert pts[0][0] == pytest.approx(0.0)
        assert pts[-1][0] == pytest.approx(float(width))
        # 等距：相邻 x 间隔一致
        steps = {round(pts[i + 1][0] - pts[i][0], 2) for i in range(len(pts) - 1)}
        assert len(steps) == 1, f"x 轴未等距分布：{steps}"

    def test_higher_value_is_drawn_higher(self, probe: dict) -> None:
        """核心锚点：SVG 的 y 向下增长，值大必须 y 小（曲线在上）。

        写反了照样是一条"像样的曲线"，只是把强磁场画成了低谷 —— 真机上看不出来。
        """
        geo = _geo(probe, "rising")
        pts = _points(geo["d"])
        ys = [y for _, y in pts]
        assert ys == sorted(ys, reverse=True), f"单调上升的数据应在图上单调升高，实得 {ys}"
        assert ys[0] > ys[-1]


# ==========================================================================
# 最小跨度保护
# ==========================================================================


class TestMinSpanGuard:
    def test_narrow_wave_is_not_amplified(self, probe: dict) -> None:
        """核心锚点：0.5 μT 的窄波动不得被拉满整屏。

        不设保护时这段噪声会占满绘图区，看起来像"磁场剧烈波动"，
        用户据此判定测量无效 —— 而实际上磁场很稳。这条挂了说明保护被去掉或算错了。
        """
        geo = _geo(probe, "narrow")
        pts = _points(geo["d"])
        ys = [y for _, y in pts]
        amplitude = max(ys) - min(ys)
        height = probe["options"]["height"]
        assert amplitude < height * 0.2, f"窄波动被放大到 {amplitude}px（绘图区高 {height}px）"
        assert amplitude > 0, "数据确实有变化，不应画成完全水平的一根线"

    def test_wide_wave_fills_the_plot(self, probe: dict) -> None:
        """跨度远大于最小跨度时，应铺满绘图区（保护不能反过来压缩真实波动）。"""
        geo = _geo(probe, "wide")
        pts = _points(geo["d"])
        ys = [y for _, y in pts]
        height = probe["options"]["height"]
        assert max(ys) - min(ys) >= height * 0.8, "真实的大波动必须铺满绘图区"

    def test_domain_is_centered_and_at_least_min_span(self, probe: dict) -> None:
        min_span = probe["options"]["minSpan"]
        for name in ("single", "constant", "narrow", "rising", "wide", "twoPoint"):
            geo = _geo(probe, name)
            assert geo["hi"] > geo["lo"], f"{name}: 值域上界不大于下界"
            assert geo["hi"] - geo["lo"] == pytest.approx(max(geo["max"] - geo["min"], min_span), abs=0.02), (
                f"{name}: 跨度不等于 max(实际跨度, 最小跨度)"
            )
            # 中点是数据中点（上下留白对称）
            assert (geo["lo"] + geo["hi"]) / 2 == pytest.approx((geo["min"] + geo["max"]) / 2, abs=0.02)

    def test_domain_covers_all_samples(self, probe: dict) -> None:
        """所有采样点都必须落在标注量程内，否则曲线会画出绘图区。"""
        for name in ("single", "constant", "narrow", "rising", "wide", "twoPoint"):
            geo = _geo(probe, name)
            assert geo["lo"] <= geo["min"] <= geo["max"] <= geo["hi"], f"{name}: 量程未包住数据"
            pts = _points(geo["d"])
            for _, y in pts:
                assert 0 <= y <= probe["options"]["height"], f"{name}: 点 y={y} 超出绘图区"


# ==========================================================================
# 点数一致性
# ==========================================================================


class TestPointCount:
    @pytest.mark.parametrize(
        ("name", "count"),
        [("single", 1), ("constant", 5), ("rising", 5), ("narrow", 5), ("wide", 5), ("twoPoint", 2)],
    )
    def test_point_count_matches_samples(self, probe: dict, name: str, count: int) -> None:
        """采样点只做剔除、不做插值：画出的点数 = 输入点数（单点例外，占两个坐标）。"""
        pts = _points(_geo(probe, name)["d"])
        assert len(pts) == (2 if count == 1 else count)


# ==========================================================================
# 面积填充（折线下方铺渐变用）
# ==========================================================================

#: 围得出面积的用例（单点除外）
_AREA_CASES = ["constant", "rising", "narrow", "wide", "twoPoint"]


class TestAreaPath:
    """`areaD` —— 折线下方那块渐变填充的几何。

    这一组守护的三件事都属于**"错了也画得出来"**：面积照样会渲染，
    只是位置或形状不对，而深底上的色块本来就很淡，肉眼很难判断对错。
    """

    @pytest.mark.parametrize("name", _AREA_CASES)
    def test_area_reuses_the_line_vertices(self, probe: dict, name: str) -> None:
        """面积的前 N 个顶点必须**逐个等于**折线的顶点。

        若为了画面积另算一套坐标，填充就会与曲线错开一点 ——
        表现是"曲线浮在色块上方"或"色块冒出曲线"，很像一种渲染故障，
        却不报任何错。直接比坐标而不是比字符串，才能抓到"数字相同但顺序不同"。
        """
        geo = _geo(probe, name)
        line_pts = _points(geo["d"])
        area_pts = _points(geo["areaD"])
        assert area_pts[: len(line_pts)] == line_pts, f"{name}: 面积顶点与折线不一致"

    @pytest.mark.parametrize("name", _AREA_CASES)
    def test_area_closes_along_the_bottom_edge(self, probe: dict, name: str) -> None:
        """底边必须落在绘图区下缘（y = height），且路径以 Z 闭合。

        写成 `height - paddingY` 是很容易顺手写出的版本：填充底下会露出一条
        底色缝，看着像渲染残影 —— 而曲线本身完全正常，很难归因到这里。
        """
        geo = _geo(probe, name)
        line_pts = _points(geo["d"])
        area_pts = _points(geo["areaD"])
        height = probe["options"]["height"]

        assert len(area_pts) == len(line_pts) + 2, f"{name}: 面积应比折线多出两个底角"
        assert area_pts[-2][1] == pytest.approx(height, abs=0.01), f"{name}: 第一底角未落到下缘"
        assert area_pts[-1][1] == pytest.approx(height, abs=0.01), f"{name}: 第二底角未落到下缘"
        assert geo["areaD"].rstrip().endswith("Z"), f"{name}: 路径没有闭合"

    @pytest.mark.parametrize("name", _AREA_CASES)
    def test_area_corners_align_with_line_endpoints(self, probe: dict, name: str) -> None:
        """两个底角的 x 必须与折线首尾点的 x 相同，否则填充会比曲线多出一截或短一截。"""
        geo = _geo(probe, name)
        line_pts = _points(geo["d"])
        area_pts = _points(geo["areaD"])
        # 闭合顺序：折线末点垂直落到下缘（第一个底角），再横跨到首点正下方（第二个底角）
        assert area_pts[-2][0] == pytest.approx(line_pts[-1][0], abs=0.01), f"{name}: 第一底角 x 未接折线末点"
        assert area_pts[-1][0] == pytest.approx(line_pts[0][0], abs=0.01), f"{name}: 第二底角 x 未接折线首点"

    @pytest.mark.parametrize("name", _AREA_CASES)
    def test_area_has_no_non_finite(self, probe: dict, name: str) -> None:
        """与折线同一条底线：面积里也不许出现 NaN / Infinity。

        恒定序列（手机静止平放）是这里最容易翻车的输入 —— 它同时是
        `test_constant_series_has_no_nan_and_sits_on_midline` 守的那条路。
        """
        area_d = _geo(probe, name)["areaD"]
        assert "NaN" not in area_d and "Infinity" not in area_d, f"{name}: {area_d}"

    def test_single_point_has_no_area(self, probe: dict) -> None:
        """单点围不出面积，必须明确返回 `null`。

        返回**空字符串**比返回 null 更糟：调用方 `curve.areaD ? … : null` 会把空串
        当成"有值"而去渲染一条零宽路径 —— 看不见，却让排查者以为填充已经生效。
        """
        assert probe["areaNullForSingle"] is True, "单点的 areaD 不是 null"
        assert _geo(probe, "single")["areaD"] is None

    def test_no_data_yields_no_geometry_at_all(self, probe: dict) -> None:
        """整条曲线都没有时，连几何对象都不该有（与 `d` 同进同退）。"""
        assert probe["nullCases"]["empty"] is True
        assert probe["nullCases"]["allNonFinite"] is True
