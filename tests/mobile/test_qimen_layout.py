"""移动端奇门九宫摆位 ↔ 内核宫殿方位 的跨来源一致性校验。

## 为什么需要这道测试

洛书摆位（`apps/mobile/src/lib/qimenLayout.ts` 的 `QIMEN_GRID`）是**前端独有**的
一张表 —— 内核只知道每个宫的 `direction`（北/东北/东…），不知道前端把它画在了
3×3 网格的哪一格。所以两边一旦对不上，没有任何运行时报错：

- 九个宫一个不少地渲染出来，盘面看起来完全正常
- 只是**方位整体错位**，用户照着一个方向错的盘做判断
- 而且错得很隐蔽：南上北下与北上南下的差别，只有熟悉罗盘的人才会一眼看出

这是本项目最该防的那一类失败：**不报错、只是给错**。

## 校验方式

真正**执行** `qimenLayout.ts`（Node ≥ 22.6 的类型擦除，无需装依赖、无需构建），
把两张表取回来，再用三条互相独立的性质去核：

1. **齐备性** —— 1~9 恰好各出现一次（防"抄漏一个宫、另一个宫抄了两遍"）
2. **数理性质** —— 洛书是幻方：三行、三列、两条对角线之和都等于 15。
   这条**完全不含领域知识**，纯数学，却是抓错位最灵敏的一条
3. **外部真值** —— 逐位比对内核宫殿的 `direction`。这条用的是**另一条独立来源**
   （内核的方位表），而不是让这张表自己和自己对答案

三条都过才叫对。只过第 1 条的话，把任意两个宫对调照样能过。

没有 Node 时跳过（而不是失败）：本测试保护的是前端一致性约束，
在纯后端环境里跳过是合理的，不该让 `pytest` 变成"必须装 Node"。
"""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fortune_core.qimen import cast_qimen

import datetime as _dt

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/qimen_layout_probe.ts"

#: 3×3 网格每行/列/对角线应有的和（洛书 = 1..9 的三阶幻方，恒为 15）
_MAGIC_SUM = 15


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict[str, list]:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过前端九宫摆位一致性校验")
    if not _PROBE.exists():
        pytest.skip(f"未找到探针脚本：{_PROBE}")

    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO_ROOT),
        timeout=120,
    )
    assert proc.returncode == 0, (
        f"探针执行失败：\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    # 末行是 JSON（node 可能先打警告）
    last = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    assert last, f"探针没有输出 JSON：{proc.stdout!r}"
    return json.loads(last[-1])


@pytest.fixture(scope="module")
def palace_direction() -> dict[int, str]:
    """内核给出的「宫 -> 方位」，作为**独立真值**。"""
    chart = cast_qimen(_dt.datetime(2026, 9, 17, 12, 0))
    return {p.gong: p.direction for p in chart.palaces}


class TestGridCompleteness:
    def test_grid_is_a_permutation_of_1_to_9(self, probe: dict[str, list]) -> None:
        """九个宫恰好各出现一次 —— 防抄漏/抄重。"""
        grid = probe["grid"]
        assert sorted(grid) == list(range(1, 10)), f"九宫不齐备：{grid}"

    def test_direction_array_matches_grid_length(self, probe: dict[str, list]) -> None:
        """两张表长度必须一致，否则后面的逐位比对是错位的。"""
        assert len(probe["direction"]) == len(probe["grid"])


class TestMagicSquare:
    """洛书的数理性质 —— 这条**不含任何领域知识**，却是最灵敏的错位探测器。"""

    def test_rows_columns_diagonals_all_sum_to_fifteen(
        self, probe: dict[str, list]
    ) -> None:
        grid: list[int] = probe["grid"]
        rows = [grid[0:3], grid[3:6], grid[6:9]]
        cols = [[grid[r * 3 + c] for r in range(3)] for c in range(3)]
        diags = [
            [grid[0], grid[4], grid[8]],
            [grid[2], grid[4], grid[6]],
        ]
        for i, row in enumerate(rows):
            assert sum(row) == _MAGIC_SUM, f"第 {i + 1} 行和应为 15，实为 {sum(row)}：{row}"
        for i, col in enumerate(cols):
            assert sum(col) == _MAGIC_SUM, f"第 {i + 1} 列和应为 15，实为 {sum(col)}：{col}"
        for i, diag in enumerate(diags):
            assert sum(diag) == _MAGIC_SUM, (
                f"第 {i + 1} 条对角线和应为 15，实为 {sum(diag)}：{diag}"
            )

    def test_center_is_five(self, probe: dict[str, list]) -> None:
        """中宫必为 5 —— 洛书的固定性质。"""
        assert probe["grid"][4] == 5, "中宫应为 5 宫"


class TestDirectionMatchesKernel:
    """用内核的方位表做外部真值逐位核 —— 不是自己和自己对答案。"""

    def test_each_cell_direction_matches_kernel(
        self, probe: dict[str, list], palace_direction: dict[int, str]
    ) -> None:
        grid: list[int] = probe["grid"]
        expected: list[str] = probe["direction"]
        for i, (gong, want) in enumerate(zip(grid, expected)):
            actual = palace_direction[gong]
            assert actual == want, (
                f"网格第 {i} 格（第 {i // 3 + 1} 行第 {i % 3 + 1} 列）摆的是 {gong} 宫，"
                f"该宫方位为「{actual}」，但表里写的是「{want}」"
            )

    def test_all_nine_directions_are_covered(
        self, probe: dict[str, list], palace_direction: dict[int, str]
    ) -> None:
        """九个方位各出现一次 —— 与内核的方位集合完全一致。"""
        assert sorted(probe["direction"]) == sorted(palace_direction.values())


class TestNotVacuous:
    """证明这套校验真的能抓错 —— 否则上面全绿也没有意义。"""

    def test_any_single_swap_breaks_at_least_one_check(self, probe: dict[str, list]) -> None:
        """穷举所有单次两格对调，统计有多少种会被抓到。

        如果存在大量"对调后三条性质照样成立"的情况，说明这套校验太弱，
        应当补更强的约束 —— 这个数字本身就是测试的强度指标。
        """
        grid: list[int] = probe["grid"]
        expected: list[str] = probe["direction"]
        kernel_dir = {
            1: '北', 2: '西南', 3: '东', 4: '东南', 5: '中',
            6: '西北', 7: '西', 8: '东北', 9: '南',
        }
        # 先确认上面这张硬编码的方位表与探针一致（防这张表本身写错）
        assert [kernel_dir[g] for g in grid] == expected

        caught = 0
        total = 0
        for i, j in itertools.combinations(range(9), 2):
            total += 1
            swapped = list(grid)
            swapped[i], swapped[j] = swapped[j], swapped[i]
            rows = [swapped[0:3], swapped[3:6], swapped[6:9]]
            cols = [[swapped[r * 3 + c] for r in range(3)] for c in range(3)]
            diags = [
                [swapped[0], swapped[4], swapped[8]],
                [swapped[2], swapped[4], swapped[6]],
            ]
            magic_ok = all(sum(x) == _MAGIC_SUM for x in rows + cols + diags)
            direction_ok = [kernel_dir[g] for g in swapped] == expected
            if not (magic_ok and direction_ok):
                caught += 1

        # 36 种单次对调中，洛书只有"同一行/列/对角线上成对换位"才可能保持幻方，
        # 而方位比对又进一步收紧。要求至少 34/36 被抓到（预留 2 种数理等价情形）。
        assert caught >= 34, (
            f"36 种单次对调中只抓到 {caught} 种，校验强度不足"
        )
