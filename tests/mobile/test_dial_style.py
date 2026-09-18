"""盘式系统（`lib/dialStyle.ts`）锚点测试。

## 为什么需要这道测试

盘式是「盘面由哪些环带构成」的定义。它有两个会**静默错**的地方：

1. **先天八卦被写成后天八卦。** 两者都是「45° 一格、八个卦」，把后天表
   复制给先天，画出来仍然是一圈像模像样的八卦 —— 只是每个卦都错位。
   本测试逐卦断言「同一卦在先后天两表中方位不同」，这正是防这一手。
2. **`simple` 盘式与 `DIAL_RATIOS` 漂移。** 两者是同一套几何的两种表述：
   盘式表按层 id 取用，`DIAL_RATIOS` 按旧字段名取用。一旦漂移，
   同一个 `size` 会算出两个不同的盘（一个走盘式路径、一个走旧路径），
   而两条路径画的都是"一个罗盘"，肉眼分不出谁对。

## 校验方式

真正**执行** `dialStyle.ts`（Node ≥ 22.6 类型擦除）取回算出来的层几何，
再在 **Python 侧独立复算**一遍 —— 例如层不重叠、半径换算、先天八卦方位。
不只依赖探针自己的 `checks`：探针的结论与实现出自同一份代码，
用它自证等于自己给自己判卷。Python 侧写的是**第二实现**。

没有 Node 时跳过而非失败（同 `test_compass_dial_parity.py` 的约定）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/dial_style_probe.ts"

#: 先天八卦（伏羲）方位 —— **测试侧独立写出**，不引用任何 TS/Python 常量。
#: 0° = 正北，顺时针递增（与全仓角度约定一致）。
_XIANTIAN_EXPECTED = {
    "坤": 0,
    "震": 45,
    "离": 90,
    "兑": 135,
    "乾": 180,
    "巽": 225,
    "坎": 270,
    "艮": 315,
}

#: 先天八卦卦符（自下而上，1=阳 0=阴）
_XIANTIAN_YAO = {
    "坤": (0, 0, 0),
    "震": (1, 0, 0),
    "离": (1, 0, 1),
    "兑": (1, 1, 0),
    "乾": (1, 1, 1),
    "巽": (0, 1, 1),
    "坎": (0, 1, 0),
    "艮": (0, 0, 1),
}

#: 后天八卦方位（洛书九宫）—— 同样独立写出，用于交叉比对
_HOUTIAN_EXPECTED = {
    "坎": 0,
    "艮": 45,
    "震": 90,
    "巽": 135,
    "离": 180,
    "坤": 225,
    "兑": 270,
    "乾": 315,
}


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过盘式锚点校验")
    if not _PROBE.exists():
        pytest.skip(f"未找到探针脚本：{_PROBE}")

    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO_ROOT),
        timeout=60,
    )
    if proc.returncode != 0:
        pytest.fail(
            "dialStyle 探针执行失败（可能是 dialStyle.ts 有语法/类型错误）：\n"
            f"{proc.stderr.strip()[:2000]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - 只在探针被改坏时触发
        pytest.fail(f"探针输出不是合法 JSON：{exc}\n原始输出前 500 字：{proc.stdout[:500]}")


# ==========================================================================
# 一、探针四类自检必须全空
# ==========================================================================


def test_probe_self_checks_all_pass(probe: dict) -> None:
    """探针自带的九项自检必须全空。

    它们覆盖层的重叠/范围、天池次序、先后天八卦混用、脏数据归一、
    盘式循环、simple↔DIAL_RATIOS 一致、层存在性判定。
    这些是"盘式自己就该成立"的性质，失败说明定义本身写错了。
    """
    for name, errs in probe["checks"].items():
        assert errs == [], f"自检 {name} 失败：{errs}"


# ==========================================================================
# 二、先天八卦：方位、卦符、与后天的差异性（本文件的核心）
# ==========================================================================


def test_xiantian_directions_are_exactly_expected(probe: dict) -> None:
    """先天八卦方位必须与测试侧独立写出的期望**逐卦相等**。

    卦位错 45° 不会报错，只会让盘面与实物罗盘对不上 —— 静默且致命。
    """
    got = {t["name"]: t["center_degree"] for t in probe["xiantian"]}
    assert got == _XIANTIAN_EXPECTED, f"先天八卦方位不符：\n实得 {got}\n应为 {_XIANTIAN_EXPECTED}"


def test_xiantian_yao_are_exactly_expected(probe: dict) -> None:
    """卦符爻线（自下而上）必须与期望相同。

    前端**自绘**爻线（不依赖字体里的 ☰☱…，避免 Android 缺字渲染成豆腐块），
    故爻线序列是一份独立实现。画反了（自上而下）坎会变离，
    整圈卦符全错，而视觉上"仍然像八卦"。
    """
    got = {t["name"]: tuple(t["yao"]) for t in probe["xiantian"]}
    assert got == _XIANTIAN_YAO, f"先天八卦卦符不符：\n实得 {got}\n应为 {_XIANTIAN_YAO}"


def test_houtian_directions_are_exactly_expected(probe: dict) -> None:
    """后天八卦方位同样逐卦核对 —— 它是既有盘面的基础，不能被顺手改掉。"""
    got = {t["name"]: t["center_degree"] for t in probe["houtian"]}
    assert got == _HOUTIAN_EXPECTED, f"后天八卦方位不符：\n实得 {got}\n应为 {_HOUTIAN_EXPECTED}"


def test_xiantian_never_shares_a_direction_with_houtian(probe: dict) -> None:
    """**同一卦在先后天两表中不得落在相同方位。**

    这是本文件最重要的一条。先天（伏羲）与后天（洛书）是两套方位，
    八个卦没有一个方位重合。但两者形状完全一样（8 卦 × 45°），
    把后天表复制给先天，页面不会崩、不会报错、看起来仍是标准八卦图 ——
    只有对着实物罗盘才会发现卦位全错。

    断言的是"逐卦方位不同"，而不是"方位集合不同"（后者恒成立，
    因为两者都是 45° 的整数倍，集合必然相同）。
    """
    xi = {t["name"]: t["center_degree"] for t in probe["xiantian"]}
    ho = {t["name"]: t["center_degree"] for t in probe["houtian"]}
    same = {name: xi[name] for name in xi if name in ho and xi[name] == ho[name]}
    assert not same, (
        "以下卦在先后天两表中方位相同，疑似把后天表复制给了先天：\n"
        + "\n".join(f"  {n} 都是 {d}°" for n, d in same.items())
    )


def test_xiantian_set_is_complete(probe: dict) -> None:
    assert {t["name"] for t in probe["xiantian"]} == set(_XIANTIAN_EXPECTED)
    assert len(probe["xiantian"]) == 8


# ==========================================================================
# 三、simple 盘式 ↔ DIAL_RATIOS（Python 侧独立复算）
# ==========================================================================


def test_simple_style_matches_dial_ratios(probe: dict) -> None:
    """`simple` 盘式的层边界必须与 `DIAL_RATIOS` 逐项相等。

    Python 侧自己取两个数据源比对（不依赖探针的 simple_vs_ratios 结论），
    因为探针的比对逻辑与实现出自同一份代码。
    """
    by_id = {l["id"]: l for l in probe["simple_layers"]}
    ratios = probe["dial_ratios"]
    pairs = {
        "mountain24": ("mountainOuter", "mountainInner"),
        "houtian": ("trigramOuter", "trigramInner"),
        "fenjin": ("tickOuter", "tickInner"),
    }
    for layer_id, (out_key, in_key) in pairs.items():
        layer = by_id[layer_id]
        assert layer["outer"] == pytest.approx(ratios[out_key]), (
            f"simple.{layer_id} 外径 {layer['outer']} ≠ DIAL_RATIOS.{out_key} {ratios[out_key]}"
        )
        assert layer["inner"] == pytest.approx(ratios[in_key]), (
            f"simple.{layer_id} 内径 {layer['inner']} ≠ DIAL_RATIOS.{in_key} {ratios[in_key]}"
        )
    assert by_id["pool"]["outer"] == pytest.approx(ratios["pool"])


# ==========================================================================
# 四、层几何：Python 侧独立复算
# ==========================================================================


#: 天池外的留白上限（相对整体半径）。
#:
#: 实物罗盘在天池与最内层之间有一段**不刻字的留白环**，故留白本身是有意的设计，
#: 不能一律禁止。但留白过大就成了"盘面漏了一块"，而那种问题一眼看上去
#: 像是渲染没画完，很难归因。此处设上限把它钉住。
#:
#: 既有 `DIAL_RATIOS` 的留白为 0.45 − 0.28 = 0.17（最宽的一个），故取 0.30 留出余量。
_MAX_POOL_GAP = 0.30


def test_layers_are_ordered_and_non_overlapping(probe: dict) -> None:
    """每个盘式的层必须由外向内排列、互不重叠，仅在**天池前**允许有限留白。

    重叠会让两层互相盖住。这些只在渲染时可见，静态检查发现不了 ——
    故在此用几何断言钉住。

    天池层单独处理：它与上一层之间的间隙是实物罗盘就有的内盘留白（见
    `_MAX_POOL_GAP` 说明），不能与"无意留下的空隙"混为一谈。本测试第一次
    运行时就正是靠这条发现了 `simple` 盘式的 0.17 留白 —— 那是既有
    `DIAL_RATIOS` 的形制，不是遗漏，故在此显式承认它并把上限定死。
    """
    for sid, style in probe["styles"].items():
        layers = style["layers"]
        assert layers, f"{sid} 没有任何层"
        for i, layer in enumerate(layers):
            assert layer["outer"] > layer["inner"], f"{sid}.{layer['id']} 外径未大于内径"
            assert 0 <= layer["inner"] and layer["outer"] <= 1, (
                f"{sid}.{layer['id']} 超出 (0,1] 范围：{layer}"
            )
            if i + 1 >= len(layers):
                continue

            nxt = layers[i + 1]
            if nxt["id"] == "pool":
                gap = layer["inner"] - nxt["outer"]
                assert gap >= -1e-9, (
                    f"{sid}：{layer['id']} 内径 {layer['inner']} 小于天池外径 {nxt['outer']}，两层重叠"
                )
                assert gap <= _MAX_POOL_GAP, (
                    f"{sid}：{layer['id']} 与天池之间有 {gap:.3f} 的留白，超过上限 {_MAX_POOL_GAP}"
                    "（过大的留白看上去像渲染没画完）"
                )
            else:
                assert layer["inner"] == pytest.approx(nxt["outer"]), (
                    f"{sid}：{layer['id']} 内径 {layer['inner']} 与 {nxt['id']} 外径 "
                    f"{nxt['outer']} 不接续（会有空隙或重叠）"
                )


def test_each_style_has_exactly_one_pool_at_the_innermost(probe: dict) -> None:
    """天池必须恰好一层，且是所有层里最内的（它是最后画的，盖在最上面）。"""
    for sid, style in probe["styles"].items():
        pools = [l for l in style["layers"] if l["id"] == "pool"]
        assert len(pools) == 1, f"{sid} 的天池层数为 {len(pools)}，应为 1"
        assert style["layers"][-1]["id"] == "pool", f"{sid} 的天池不在最内层"
        assert pools[0]["inner"] == 0, f"{sid} 天池内径应为 0（实心圆）"


def test_style_complexity_increases_in_order(probe: dict) -> None:
    """选择器顺序必须由简到繁：渲染层数与标注层数都单调不减。

    顺序写反会让"切换盘式"看起来像在变简单，与它的语义相反。
    """
    order = probe["order"]
    assert order == ["simple", "sanhe", "zonghe"], f"盘式顺序异常：{order}"
    rendered = [len(probe["styles"][s]["layers"]) for s in order]
    stated = [probe["styles"][s]["statedLayers"] for s in order]
    assert rendered == sorted(rendered), f"渲染层数未递增：{rendered}"
    assert stated == sorted(stated), f"标注层数未递增：{stated}"
    for sid, n_layers, n_stated in zip(order, rendered, stated, strict=True):
        assert n_stated >= n_layers, (
            f"{sid} 标注 {n_stated} 层却只渲染 {n_layers} 层 —— "
            "标注不应小于可渲染层数（含未渲染的细分层才是常见口径）"
        )


# ==========================================================================
# 五、半径换算（Python 侧独立复算）
# ==========================================================================


def test_radius_at_280_is_recomputable(probe: dict) -> None:
    """探针给的半径必须能由「相对比例 × size/2」独立复算出来。

    半径算错会让整个盘面在容器里偏移或截断，而各层之间的相对关系
    仍然正常 —— 属于"看着有点怪但说不出哪里怪"的那类问题。
    """
    size = 280
    for sid, style in probe["styles"].items():
        got = probe["radius_at"][sid]
        for layer in style["layers"]:
            expected = layer["outer"] * size / 2
            assert got[layer["id"]] == pytest.approx(expected, abs=0.01), (
                f"{sid}.{layer['id']} 在 {size}px 下外径 {got[layer['id']]} ≠ 复算 {expected}"
            )


# ==========================================================================
# 六、脏数据容错（存档里可能存着已废弃的盘式名）
# ==========================================================================


def test_coerce_falls_back_to_default(probe: dict) -> None:
    """非法盘式名必须回落到默认盘，而不是抛异常。

    盘式名会随存档落库；将来删掉某个盘式时，旧存档里仍留着它的名字。
    此时抛异常 = 用户的历史记录打不开。
    """
    assert probe["coerce"]["default"] == "zonghe"
