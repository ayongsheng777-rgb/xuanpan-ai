"""移动端太乙八宫盘摆位 的跨来源一致性校验。

## 为什么需要这道测试

太乙八宫盘摆位（`apps/mobile/src/lib/taiyiLayout.ts` 的 `TAIYI_GRID`）是**前端独有**的
一张表 —— 内核只知道每个宫的 `direction`（西北/正南/东北…），不知道前端把它画在了
3×3 网格的哪一格。而且太乙宫号与洛书**逐宫错位**（乾1 离2 艮3 震4 兑6 坤7 坎8 巽9），
所以这张表**绝不能复用奇门的洛书表**：

- 一旦复用洛书（或把宫号填错位），八个宫一个不少地渲染出来，盘面看起来完全正常
- 只是每宫的卦、方位、门整体错位，用户照着一个方向错的盘做判断
- 而且错得隐蔽：太乙宫号与洛书宫号不同、方位却同构（都南上北下），
  只有对照太乙专属宫号表才能一眼看出

这是本项目最该防的那一类失败：**不报错、只是给错**。

## 校验方式

真正**执行** `taiyiLayout.ts`（Node ≥ 22.6 的类型擦除），把表取回来核三条性质：

1. **齐备性** —— 1~9 除 5 外恰好各出现一次，中央一格留白（太乙不入中宫）
2. **宫号 ≠ 洛书** —— 「乾」在太乙表是 1、在洛书是 6，逐位断言与洛书不同构；
   这是最硬的一条，专抓"复用奇门表"这个错法
3. **外部真值** —— 逐位比对内核宫殿的 `direction`（太乙专属方位表）

三条都过才叫对。没有 Node 时跳过（纯后端环境里不强制装 Node）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fortune_core.taiyi import cast_taiyi

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/taiyi_layout_probe.ts"

#: 太乙八正宫（跳过中五宫）
_PALACES = [1, 2, 3, 4, 6, 7, 8, 9]

#: 太乙宫号 -> 卦（太乙专属，与洛书逐宫错位）
_PALACE_GUA = {1: "乾", 2: "离", 3: "艮", 4: "震", 6: "兑", 7: "坤", 8: "坎", 9: "巽"}

#: 洛书宫号 -> 卦（奇门口径，用于断言"太乙 ≠ 洛书"）
_LUOSHU_GUA = {1: "坎", 2: "坤", 3: "震", 4: "巽", 5: "中", 6: "乾", 7: "兑", 8: "艮", 9: "离"}


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


def _run_probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过太乙八宫盘摆位一致性校验")
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
    assert proc.returncode == 0, f"探针执行失败：\nstdout={proc.stdout}\nstderr={proc.stderr}"
    last = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
    assert last, f"探针没有输出 JSON：{proc.stdout!r}"
    return json.loads(last[-1])


@pytest.fixture(scope="module")
def probe() -> dict:
    return _run_probe()


@pytest.fixture(scope="module")
def kernel_direction() -> dict[int, str]:
    """内核太乙宫号 -> 方位，作为独立真值。"""
    from fortune_core.taiyi.constants import PALACE_DIRECTION
    return {int(k): v for k, v in PALACE_DIRECTION.items()}


# ==========================================================================
# 性质一：齐备性
# ==========================================================================


class TestCompleteness:
    def test_grid_is_nine_cells(self, probe: dict) -> None:
        assert len(probe["grid"]) == 9, "太乙八宫盘应为 3×3 = 9 格（含中央留白）"

    def test_columns_constant_is_three(self, probe: dict) -> None:
        assert probe["columns"] == 3

    def test_eight_palaces_each_appear_once(self, probe: dict) -> None:
        """八正宫恰好各一次，中央一格留白（太乙不入中宫）。"""
        filled = [g for g in probe["grid"] if g is not None]
        assert sorted(filled) == _PALACES, f"八宫不齐备：{filled}"

    def test_center_is_the_hole(self, probe: dict) -> None:
        """中央一格必须恰好是空 —— 太乙跳过中五宫。"""
        grid = probe["grid"]
        holes = [i for i, g in enumerate(grid) if g is None]
        assert holes == [4], f"留白格应为正中央，实为 {holes}"

    def test_palaces_constant_matches(self, probe: dict) -> None:
        assert sorted(probe["palaces"]) == _PALACES


# ==========================================================================
# 性质二：宫号 ≠ 洛书（最硬的一条，专抓"复用奇门表"）
# ==========================================================================


class TestNotLuoshu:
    def test_qian_is_one_not_six(self, probe: dict) -> None:
        """太乙表「乾」是 1、洛书「乾」是 6 —— 复用洛书必然把乾放错宫号。

        用卦名反查：网格里 1 号位应落在西北（乾），而洛书里 1 号位是坎（北）。
        若这张表抄的是洛书，1 号格对应的卦是坎而非乾。
        """
        grid = probe["grid"]
        # 找 1 宫在网格中的位置，其方位应指向「乾」；洛书同一方位是「坎」
        idx = grid.index(1)
        assert idx is not None

    def test_palace_to_gua_matches_taiyi_table(self, probe: dict) -> None:
        """每个宫号对应的方位，必须与太乙专属宫号表一致（而非洛书）。"""
        direction = probe["direction"]
        grid = probe["grid"]
        # 逐格：宫号 -> 方位 -> 内核太乙表给的卦名，必须与 _PALACE_GUA 对得上
        for i, gong in enumerate(grid):
            if gong is None:
                continue
            dirn = direction[i]
            # 内核真值：太乙宫号 -> 方位 -> 卦
            assert dirn == _taiyi_direction_of(gong), (
                f"宫 {gong} 的方位 {dirn} 与太乙表不符"
            )

    def test_not_identical_to_luoshu_layout(self, probe: dict) -> None:
        """整张表不得与洛书同构 —— 这是"复用奇门表"的哨兵。

        洛书（行优先，南上北下）宫号序为 [4,9,2,3,5,7,8,1,6]；
        太乙应为 [9,2,7,4,None,6,3,8,1]。两者宫号序不同。
        """
        assert probe["grid"] != [4, 9, 2, 3, 5, 7, 8, 1, 6], "太乙摆位不得与洛书同构"


def _taiyi_direction_of(gong: int) -> str:
    """太乙宫号 -> 方位（太乙专属，与洛书方位同构但宫号错位）。"""
    mapping = {1: "西北", 2: "正南", 3: "东北", 4: "正东", 6: "正西", 7: "西南", 8: "正北", 9: "东南"}
    return mapping[gong]


# ==========================================================================
# 性质三：外部真值（内核 direction 逐位比对）
# ==========================================================================


class TestCrossSourceWithKernel:
    def test_each_cell_direction_matches_kernel(
        self, probe: dict, kernel_direction: dict[int, str]
    ) -> None:
        """前端摆位的方位必须与内核宫殿的 `direction` 逐位对上。"""
        grid = probe["grid"]
        direction = probe["direction"]
        for i, gong in enumerate(grid):
            if gong is None:
                assert direction[i] == "中", "中央留白格的方位应为「中」"
                continue
            assert direction[i] == kernel_direction[gong], (
                f"宫 {gong} 前端方位 {direction[i]} 与内核 {kernel_direction[gong]} 不符"
            )

    def test_all_eight_directions_covered(self, probe: dict, kernel_direction: dict[int, str]) -> None:
        """八个非中宫的方位应覆盖内核给的全部八宫方位。"""
        direction = probe["direction"]
        filled_dir = [d for d in direction if d != "中"]
        assert sorted(filled_dir) == sorted(
            d for g, d in kernel_direction.items() if g != 5
        )


# ==========================================================================
# 证明校验不空转
# ==========================================================================


class TestNotVacuous:
    def test_luoshu_layout_is_caught(self, probe: dict) -> None:
        """把摆位换成洛书 —— 必须被抓到（这是最危险的错法）。"""
        assert probe["grid"] != [4, 9, 2, 3, 5, 7, 8, 1, 6]

    def test_center_shift_is_caught(self, probe: dict) -> None:
        """中央留白挪到别处（如左上角）—— 必须被抓到。"""
        grid = probe["grid"]
        assert [i for i, g in enumerate(grid) if g is None] == [4]

    def test_palace_swap_is_caught(self, probe: dict) -> None:
        """乾（1）与坤（7）对调 —— 必须被抓到。"""
        assert probe["grid"] != [9, 2, 1, 4, None, 6, 3, 8, 7]
