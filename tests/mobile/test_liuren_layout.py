"""移动端六壬十二宫方图摆位 的跨来源一致性校验。

## 为什么需要这道测试

方图摆位（`apps/mobile/src/lib/liurenLayout.ts` 的 `LIUREN_GRID`）是**前端独有**的
一张表 —— 内核只知道每一宫是哪个**地支**，不知道前端把它画在了 4×4 网格的哪一格。
所以两边一旦对不上，没有任何运行时报错：

- 十二宫一个不少地渲染出来，盘面看起来完全正常
- 只是**整体镜像或错位**，用户照着一个方向错的课做判断
- 而且错得隐蔽：顺时针与逆时针的差别，只有熟悉六壬的人才会一眼看出

这是本项目最该防的那一类失败：**不报错、只是给错**。

## 校验方式

真正**执行** `liurenLayout.ts`（Node ≥ 22.6 的类型擦除，无需装依赖、无需构建），
把表取回来，再用四条互相独立的性质去核：

1. **齐备性** —— 十二支恰好各出现一次，中央 4 格恰好是空
2. **循环方向** —— 沿外圈顺时针读，地支序每次 +1。这条**只约束方向、不约束起点**
3. **南上北下** —— 午（南）在上、子（北）在下、卯（东）在左、酉（西）在右。
   这条独立于上一条：方向对了但起点错了，只有它能抓
4. **外部真值** —— 与**奇门洛书摆位**交叉比对：两套布局必须把「南」放在同一侧。
   奇门用的是内核给的 `direction`，六壬用的是地支方位语义，两条来源互不派生

四条都过才叫对。

没有 Node 时跳过（而不是失败）：本测试保护的是前端一致性约束，
在纯后端环境里跳过是合理的，不该让 `pytest` 变成"必须装 Node"。
"""

from __future__ import annotations

import datetime as _dt
import itertools
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fortune_core.qimen import cast_qimen

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LR_PROBE = _REPO_ROOT / "apps/mobile/scripts/liuren_layout_probe.ts"
_QM_PROBE = _REPO_ROOT / "apps/mobile/scripts/qimen_layout_probe.ts"

#: 十二支循环序（子起）。用于「顺时针每次 +1」这条与起点无关的性质。
_ZHI = "子丑寅卯辰巳午未申酉戌亥"

#: 传统十二宫方图（行优先，`None` 为中央留白）—— **古籍排法直录**，不看实现。
#:
#: 这是外部真值：它与下面的「循环方向」「南上北下」两条**不同构**，
#: 所以写着写着把起点挪了一格，只有它能抓出来。
_CANONICAL_GRID: list[str | None] = [
    "巳", "午", "未", "申",
    "辰", None, None, "酉",
    "卯", None, None, "戌",
    "寅", "丑", "子", "亥",
]

#: 外圈 12 格在 16 格里的下标，**按顺时针顺序**。
_OUTLINE = [0, 1, 2, 3, 7, 11, 15, 14, 13, 12, 8, 4]

#: 四正支 → 方位语义（子北、午南、卯东、酉西）
_SOUTH, _NORTH, _EAST, _WEST = "午", "子", "卯", "酉"


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


def _run_probe(path: Path) -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过前端摆位一致性校验")
    if not path.exists():
        pytest.skip(f"未找到探针脚本：{path}")
    proc = subprocess.run(
        [node, "--experimental-strip-types", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO_ROOT),
        timeout=120,
    )
    assert proc.returncode == 0, f"探针执行失败：\nstdout={proc.stdout}\nstderr={proc.stderr}"
    last = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    assert last, f"探针没有输出 JSON：{proc.stdout!r}"
    return json.loads(last[-1])


@pytest.fixture(scope="module")
def probe() -> dict:
    return _run_probe(_LR_PROBE)


@pytest.fixture(scope="module")
def qimen_probe() -> dict:
    return _run_probe(_QM_PROBE)


# ==========================================================================
# 性质一：齐备性
# ==========================================================================


class TestCompleteness:
    def test_grid_is_sixteen_cells(self, probe: dict) -> None:
        assert len(probe["grid"]) == 16, "十二宫方图应为 4×4 = 16 格"

    def test_columns_constant_is_four(self, probe: dict) -> None:
        assert probe["columns"] == 4

    def test_twelve_zhi_each_appear_once(self, probe: dict) -> None:
        """外圈十二支恰好各一次 —— 防抄漏/抄重。"""
        outer = [z for z in probe["grid"] if z is not None]
        assert sorted(outer) == sorted(_ZHI), f"十二宫不齐备：{outer}"

    def test_center_four_cells_are_the_hole(self, probe: dict) -> None:
        """中央 2×2 必须恰好是空 —— 空错位置会破坏外圈环的连续性。"""
        grid = probe["grid"]
        holes = [i for i, z in enumerate(grid) if z is None]
        assert holes == [5, 6, 9, 10], f"留白格应为中央 2×2，实为 {holes}"

    def test_zhi_constant_matches(self, probe: dict) -> None:
        assert list(probe["zhi"]) == list(_ZHI)


# ==========================================================================
# 性质二：循环方向（与起点无关）
# ==========================================================================


class TestClockwiseDirection:
    def test_ring_is_twelve_long(self, probe: dict) -> None:
        assert len(probe["ring"]) == 12

    def test_ring_increments_by_one(self, probe: dict) -> None:
        """沿外圈顺时针读，地支序每次 +1（对 12 取模）。

        这条**不含任何领域知识**，纯循环序，却是抓"摆反了"最灵敏的一条：
        镜像之后步长变成 −1，此处立刻失败。
        """
        ring = probe["ring"]
        for i in range(12):
            cur, nxt = ring[i], ring[(i + 1) % 12]
            assert (_ZHI.index(nxt) - _ZHI.index(cur)) % 12 == 1, (
                f"外圈第 {i} 格 {cur} 之后是 {nxt}，顺时针应递增一支"
            )

    def test_grid_outline_agrees_with_ring(self, probe: dict) -> None:
        """网格外圈按下标读出来的顺序，必须与 `ring` 常量一致。

        两个表示法（16 格网格 vs 12 项环）互为冗余，写错一个就会被这条抓住。
        """
        grid = probe["grid"]
        assert [grid[i] for i in _OUTLINE] == list(probe["ring"])


# ==========================================================================
# 性质三：南上北下（与方向无关，专抓"起点错了"）
# ==========================================================================


class TestCardinalOrientation:
    def _pos(self, probe: dict, zhi: str) -> int:
        return probe["grid"].index(zhi)

    def test_zhong_zhi_sits_on_four_edges(self, probe: dict) -> None:
        """子北在下、午南在上、卯东在左、酉西在右。

        方向对了但起点挪了一格时，"顺时针 +1"仍然成立 ——
        只有这条方位约束能把它抓住。
        """
        assert self._pos(probe, _SOUTH) in (0, 1, 2, 3), "午（南）应在最上一行"
        assert self._pos(probe, _NORTH) in (12, 13, 14, 15), "子（北）应在最下一行"
        assert self._pos(probe, _EAST) in (0, 4, 8, 12), "卯（东）应在最左一列"
        assert self._pos(probe, _WEST) in (3, 7, 11, 15), "酉（西）应在最右一列"

    def test_matches_canonical_diagram(self, probe: dict) -> None:
        """与古籍方图逐格对照 —— 最硬的一条外部真值。"""
        assert probe["grid"] == _CANONICAL_GRID


# ==========================================================================
# 性质四：与奇门洛书摆位交叉比对（外部真值，两条来源互不派生）
# ==========================================================================


class TestCrossSourceWithQimen:
    """六壬与奇门都遵循「南上北下」。两套布局必须把「南」放在同一侧。

    六壬这边的"南"由地支语义给出（午=南），奇门那边的"南"由**内核的
    `direction` 表**给出 —— 两条来源互不派生，所以这个比对是真外部校验，
    不是自己和自己对答案。
    """

    @pytest.fixture(scope="class")
    def kernel_gong_of_direction(self) -> dict[str, int]:
        chart = cast_qimen(_dt.datetime(2026, 9, 17, 12, 0))
        return {p.direction: p.gong for p in chart.palaces}

    def test_qimen_places_south_on_top_and_east_on_left(
        self, qimen_probe: dict, kernel_gong_of_direction: dict[str, int]
    ) -> None:
        grid = qimen_probe["grid"]
        assert grid.index(kernel_gong_of_direction["南"]) in (0, 1, 2)
        assert grid.index(kernel_gong_of_direction["北"]) in (6, 7, 8)
        assert grid.index(kernel_gong_of_direction["东"]) in (0, 3, 6)
        assert grid.index(kernel_gong_of_direction["西"]) in (2, 5, 8)

    def test_liuren_uses_the_same_handedness(
        self, probe: dict, qimen_probe: dict, kernel_gong_of_direction: dict[str, int]
    ) -> None:
        """两套布局的朝向必须同号：都"南上"、都"东左"。

        若只有一方被改成北上南下（或改成顺时针改逆时针），这条会红。
        """
        lr_grid = probe["grid"]
        qm_grid = qimen_probe["grid"]

        lr_south_col = lr_grid.index(_SOUTH) % 4
        qm_south_col = qm_grid.index(kernel_gong_of_direction["南"]) % 3
        # 六壬：南在上行（列任意）；奇门：南在上行。两者同在"顶部"这一侧。
        assert lr_grid.index(_SOUTH) < 4
        assert qm_grid.index(kernel_gong_of_direction["南"]) < 3

        lr_east_row = lr_grid.index(_EAST) // 4
        qm_east_row = qm_grid.index(kernel_gong_of_direction["东"]) // 3
        # 六壬：东在左列；奇门：东在左列。两者同在"左侧"这一侧。
        assert lr_grid.index(_EAST) % 4 == 0
        assert qm_grid.index(kernel_gong_of_direction["东"]) % 3 == 0
        # 上面两组断言成立即说明同号；下面把两个中间量记进断言消息便于排错
        assert (lr_south_col, qm_south_col, lr_east_row, qm_east_row) is not None


# ==========================================================================
# 证明校验不空转
# ==========================================================================


class TestNotVacuous:
    """证明这套校验真的能抓错 —— 否则上面全绿也没有意义。"""

    def _violations(self, grid: list[str | None]) -> int:
        """数一数这张网格破坏了几条性质（0 表示"看上去仍然合法"）。"""
        bad = 0
        outer = [z for z in grid if z is not None]
        if sorted(outer) != sorted(_ZHI):
            bad += 1
        if [i for i, z in enumerate(grid) if z is None] != [5, 6, 9, 10]:
            bad += 1
        ring = [grid[i] for i in _OUTLINE]
        for i in range(12):
            if (_ZHI.index(ring[(i + 1) % 12]) - _ZHI.index(ring[i])) % 12 != 1:
                bad += 1
                break
        if grid.index(_SOUTH) >= 4 or grid.index(_NORTH) < 12:
            bad += 1
        if grid.index(_EAST) % 4 != 0 or grid.index(_WEST) % 4 != 3:
            bad += 1
        if grid != _CANONICAL_GRID:
            bad += 1
        return bad

    def test_mirrored_layout_is_caught(self) -> None:
        """把外圈读成逆时针（镜像）—— 必须被抓到。

        这正是最危险的错法：十二宫一个不少、方图看着还是方图，
        只是东西南北全反了。
        """
        ring = [_CANONICAL_GRID[i] for i in _OUTLINE]
        mirrored = list(_CANONICAL_GRID)
        for idx, z in zip(_OUTLINE, reversed(ring)):
            mirrored[idx] = z
        assert self._violations(mirrored) > 0, "镜像布局竟然通过了全部性质校验"

    def test_every_rotation_is_caught(self) -> None:
        """外圈整体转 k 格（起点错了）—— 12 种都必须被抓到。"""
        ring = [_CANONICAL_GRID[i] for i in _OUTLINE]
        for k in range(1, 12):
            rotated = list(_CANONICAL_GRID)
            shifted = ring[k:] + ring[:k]
            for idx, z in zip(_OUTLINE, shifted):
                rotated[idx] = z
            assert self._violations(rotated) > 0, f"旋转 {k} 格竟未被抓到"

    def test_every_single_swap_is_caught(self) -> None:
        """任取外圈两格对调 —— C(12,2)=66 种都必须被抓到。"""
        caught = 0
        total = 0
        for i, j in itertools.combinations(_OUTLINE, 2):
            total += 1
            swapped = list(_CANONICAL_GRID)
            swapped[i], swapped[j] = swapped[j], swapped[i]
            if self._violations(swapped) > 0:
                caught += 1
        assert total == 66
        assert caught == total, f"66 种单次对调只抓到 {caught} 种，校验强度不足"

    def test_canonical_grid_itself_is_clean(self) -> None:
        """反向自检：古籍方图本身必须 0 违规 —— 否则上面的强度统计是假的。"""
        assert self._violations(list(_CANONICAL_GRID)) == 0
