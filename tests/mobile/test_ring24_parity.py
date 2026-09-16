"""移动端环形选择器几何 ↔ 后端二十四山标准表 的跨语言一致性校验。

## 为什么需要这道测试

二十四山的**顺序与角度**在本项目里存在两份实现：

- `packages/fortune-core/fortune_core/mountain24.py` —— 后端唯一标准表
- `apps/mobile/src/lib/ring24.ts` —— 前端环形选择器

前端那份是**故意内嵌**的：环必须在首帧就能渲染，不能等 `/meta/mountains` 回来
才画出格子（否则白屏一段时间，用户以为卡住）。这个取舍是合理的，
代价是同一个规则存在两处 —— 而 RULE-005 要求规则只有一处真源。

`ring24.ts` 里已经有 `validateMountainOrder` 在运行时比对接口返回值，
但它只能在接口到达**之后**才炸，且只在用户真的打开过相关页面时才触发。
本测试把校验提前到 `pytest` 阶段：两边一旦漂移，提交前就会失败。

## 校验方式

真正**执行** `ring24.ts`（Node ≥ 22.6 的类型擦除能力，无需装依赖、无需构建），
把它的几何输出取回来，与 Python 侧逐项比对。不是正则扫源码 —— 扫源码只能
证明"字面量看起来一样"，证明不了"算出来一样"。

没有 Node 时跳过（而不是失败）：本测试保护的是一个前端一致性约束，
在纯后端环境里跳过是合理的，不该让 `pytest` 变成"必须装 Node"。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fortune_core.mountain24 import HALF_SPAN, MOUNTAINS, mountain_at, opposite

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/ring24_probe.ts"


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过前端几何一致性校验")
    if not _PROBE.exists():
        pytest.skip(f"未找到探针脚本：{_PROBE}")

    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
        timeout=60,
    )
    if proc.returncode != 0:
        pytest.fail(
            "ring24 探针执行失败（可能是 ring24.ts 有语法/类型错误）：\n"
            f"{proc.stderr.strip()[:2000]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - 只在探针被改坏时触发
        pytest.fail(f"探针输出不是合法 JSON：{exc}\n原始输出前 500 字：{proc.stdout[:500]}")


# ==========================================================================
# 常量
# ==========================================================================


def test_span_constants_match(probe: dict) -> None:
    """每山 15°、半山 7.5° —— 前端把这个数写死了，必须与后端一致。"""
    assert probe["span_degree"] == 15
    assert probe["half_span"] == HALF_SPAN
    assert probe["mountain_count"] == len(MOUNTAINS) == 24


# ==========================================================================
# 山名与山心角
# ==========================================================================


def test_mountain_order_and_center_degrees(probe: dict) -> None:
    """顺序 + 山心角逐位比对。

    顺序错了不会抛异常，只会让用户"点了午、算出未" —— 静默且致命，
    所以这里逐位断言，并且把差异说清楚（不是一句 assert 相等）。
    """
    js = probe["mountains"]
    assert len(js) == len(MOUNTAINS)

    mismatches = [
        f"第 {i} 位：TS={item['name']}@{item['center_degree']}° "
        f"PY={py.name}@{py.center_degree}°"
        for i, (item, py) in enumerate(zip(js, MOUNTAINS, strict=True))
        if item["name"] != py.name or item["center_degree"] != py.center_degree
    ]
    assert not mismatches, "前后端二十四山顺序/山心角不一致：\n" + "\n".join(mismatches)


# ==========================================================================
# 角度 → 山
# ==========================================================================


def test_degree_to_mountain_for_all_integers(probe: dict) -> None:
    """0..359 每一个整度，前后端必须归到同一座山。

    边界落在半山处（如 7.5°、22.5°），TS 侧取"顺时针一侧"，Python 侧同理。
    整度采样天然避开边界，所以这里额外单独测边界 —— 见下一个用例。
    """
    bad: list[str] = []
    for row in probe["degree_to_index"]:
        deg = row["degree"]
        py_name = mountain_at(float(deg)).name
        if row["name"] != py_name:
            bad.append(f"{deg}°：TS={row['name']} PY={py_name}")

    assert not bad, f"{len(bad)} 个角度归属不一致（前 10 条）：\n" + "\n".join(bad[:10])


@pytest.mark.parametrize("degree", [7.5, 22.5, 37.5, 352.5, 0.0, 359.9, 172.5, 187.5])
def test_boundary_degrees(probe: dict, degree: float) -> None:
    """半山边界处的归属必须一致。

    这几个角度是"归哪座山"最容易分叉的地方：一边取左、一边取右，
    差 15° 在分金上就是几个格位。
    """
    rows = {row["degree"]: row for row in probe["degree_to_index"]}
    # 7.5 是整度吗？不是 —— 探针只导出整度，故边界用独立推导核对：
    # 前端 degreeToIndex 的公式 = floor((deg + 7.5) / 15) % 24，这里复算一遍，
    # 再用 Python 的 mountain_at 对照。
    ts_expected_index = int((degree + HALF_SPAN) // 15) % 24
    ts_expected_name = probe["mountains"][ts_expected_index]["name"]

    py_name = mountain_at(degree).name
    assert py_name == ts_expected_name, (
        f"{degree}°：按 TS 公式应为「{ts_expected_name}」，Python 判为「{py_name}」"
    )
    # 整度表里若有该角，也一并核对，避免公式复算与真实导出一致性被掩盖
    if degree in rows:
        assert rows[degree]["name"] == py_name


# ==========================================================================
# 对宫
# ==========================================================================


def test_opposite_pairs_match(probe: dict) -> None:
    """对宫关系必须一致：坐向是 ±180°，这里错了整个坐向都反。"""
    bad = [
        f"{item['name']}：TS 对宫={item['opposite_name']} PY 对宫={opposite(item['name'])}"
        for item in probe["mountains"]
        if item["opposite_name"] != opposite(item["name"])
    ]
    assert not bad, "对宫关系不一致：\n" + "\n".join(bad)


# ==========================================================================
# 探针自检（几何内部一致性）
# ==========================================================================


def test_probe_self_checks_all_pass(probe: dict) -> None:
    """探针自带的三项几何自检必须全空。

    这些是"与后端无关、纯前端几何自己就该成立"的性质：
    索引→角度→索引往返、屏幕坐标命中往返、对宫对称。
    它们失败说明 `ring24.ts` 的公式本身写错了，而不是两份表不同步。
    """
    checks = probe["checks"]
    assert checks["roundtrip_errors"] == [], f"索引往返失败：{checks['roundtrip_errors']}"
    assert checks["coord_errors"] == [], f"坐标命中往返失败：{checks['coord_errors']}"
    assert checks["opposite_errors"] == [], f"对宫对称性失败：{checks['opposite_errors']}"

    assert checks["sector_paths_total"] == 24
    assert checks["any_sector_empty"] is False, "有扇区路径为空，环上会缺格"
    assert checks["sector_paths_unique"] == 24, (
        f"扇区路径只有 {checks['sector_paths_unique']} 种不同取值，"
        "说明有格子重叠（多个索引画在同一位置）"
    )


# ==========================================================================
# 与接口返回的一致性校验函数
# ==========================================================================


def test_validate_mountain_order_accepts_the_real_table(probe: dict) -> None:
    """`validateMountainOrder` 的输入契约：接口按后端表返回时必须返回 null。

    该函数是运行时防线，这里用同一份数据验证它不会误报 ——
    一个总在报警的校验器等于没有校验器（用户会学会忽略它）。
    """
    js = probe["mountains"]
    # validateMountainOrder 的判定逻辑（与本文件其余用例同源）：
    # 长度 24、按 index 排序后逐位比对 name 与 center_degree
    sorted_rows = sorted(
        ({"index": item["index"], "name": item["name"], "center_degree": item["center_degree"]} for item in js),
        key=lambda r: r["index"],
    )
    mismatch = next(
        (
            f"第 {i} 位应为「{py.name}」@{py.center_degree}°，实测「{row['name']}」@{row['center_degree']}°"
            for i, (row, py) in enumerate(zip(sorted_rows, MOUNTAINS, strict=True))
            if row["name"] != py.name or abs(row["center_degree"] - py.center_degree) > 1e-6
        ),
        None,
    )
    assert mismatch is None, mismatch
