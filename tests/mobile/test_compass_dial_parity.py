"""罗盘盘面（`lib/compassDial.ts`）↔ 后端 `fortune_core` 的跨语言一致性校验。

## 为什么需要这道测试

盘面上有三处「同一规则存在两处实现」，且**错了不会报错**：

1. **后天八卦方位** —— 前端画卦符的位置，后端 `constants.GUA_HOUTIAN_DEGREE` 算方位。
   卦位画错 45°，盘面看上去仍然"像个罗盘"，但用户对着实物核对时会发现卦位对不上。
2. **一百二十分金分格** —— 前端画 3° 刻度，后端 `fenjin120` 判分金归属。
   前端若按 2° 或 5° 画，分金格与实物罗盘的格位就永久错位。
3. **二十四山的干支/维分类** —— 前端据此决定朱红/主色/墨，后端 `MOUNTAINS[].kind`
   是同一分类的权威来源。分类错了只会让盘面配色看着"有点怪"，
   但这类"看着有点怪"恰恰是用户判断"这 App 专不专业"的第一直觉。

三者都属于**静默错位**：界面不崩、不报错，只是画的东西不对。这类问题只能靠测试守住。

## 校验方式

真正**执行** `compassDial.ts`（Node ≥ 22.6 类型擦除），把盘式数据取回来与
`fortune_core` 逐项比对 —— 不是正则扫源码。扫源码只能证明"字面量看起来一样"，
证明不了"算出来一样"。

没有 Node 时跳过（而非失败）：本测试保护的是前端一致性约束，
纯后端环境跳过是合理的，不该让 `pytest` 变成"必须装 Node"。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fortune_core.constants import GUA_HOUTIAN_DEGREE, GUA_YAO
from fortune_core.fenjin120 import FENJIN_PER_MOUNTAIN, FENJIN_SPAN
from fortune_core.mountain24 import MOUNTAINS, SPAN_DEGREE, mountain_at

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/compass_dial_probe.ts"

#: 四正（子午卯酉）—— 盘面上的主刻度
_CARDINAL = "子午卯酉"


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过罗盘盘面一致性校验")
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
            "compassDial 探针执行失败（可能是 compassDial.ts 有语法/类型错误）：\n"
            f"{proc.stderr.strip()[:2000]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - 只在探针被改坏时触发
        pytest.fail(f"探针输出不是合法 JSON：{exc}\n原始输出前 500 字：{proc.stdout[:500]}")


# ==========================================================================
# 探针自检（纯前端几何自己就该成立）
# ==========================================================================


def test_probe_self_checks_all_pass(probe: dict) -> None:
    """探针自带的几何自检必须全空。

    这些与后端无关，是"盘面几何自己就该成立"的性质：旋转往返、
    一键对齐、旋转不改变选山、吸附落在格点、指针角、顶部读数、
    归一化范围、层级计数、环半径不重叠。它们失败说明公式本身写错了。
    """
    c = probe["checks"]
    assert c["rotation_roundtrip_errors"] == [], f"旋转往返失败：{c['rotation_roundtrip_errors']}"
    assert c["align_errors"] == [], f"一键对齐失败：{c['align_errors']}"
    assert c["rotation_select_errors"] == [], (
        f"旋转后选山漂移（视角改变不应改事实）：{c['rotation_select_errors']}"
    )
    assert c["azimuth_at_top_errors"] == [], f"顶部读数错误：{c['azimuth_at_top_errors'][:10]}"
    assert c["initial_rotation_errors"] == [], (
        f"初始对准口径错误（顶部应为**坐山**方向）：{c['initial_rotation_errors']}"
    )
    assert c["snap_errors"] == [], f"吸附失败：{c['snap_errors'][:10]}"
    assert c["pointer_errors"] == [], f"指针角失败：{c['pointer_errors'][:10]}"
    assert c["signed_errors"] == [], f"归一化越界：{c['signed_errors'][:10]}"
    assert c["radius_order_errors"] == [], f"环半径排布错误：{c['radius_order_errors']}"


def test_azimuth_at_top_is_minus_rotation_by_geometry() -> None:
    """「顶部读数 = −rotation」这条结论，用**第一性几何**在 Python 侧独立复算一遍。

    为什么不直接信探针：探针里的自检和它自己的实现出自同一双手，
    写错符号时两边会一起错。这里不复用任何 JS 结果 —— 从
    「屏幕 0° 在正上方、顺时针为正」这条定义出发，用旋转矩阵算
    「盘面角 θ 转 rotation 后落在屏幕哪里」，再解出屏幕 0° 处对应哪个 θ。

    这条被上游页面直接依赖：写反了（用 +rotation）界面完全正常，
    只是把盘拖到东边读数显示西边，且在 0°/180° 上"看起来是对的"。
    """
    import math

    def normalize_deg(d: float) -> float:
        r = d % 360.0
        return r + 360.0 if r < 0 else r

    def screen_angle_of_marking(deg: float, rotation: float) -> float:
        """盘面角 deg 处的刻度，盘体顺时针转 rotation 后落在屏幕的哪个角。"""
        # 盘面角 → 屏幕单位向量（x 向右、y 向下；0° 朝上）
        x, y = math.sin(math.radians(deg)), -math.cos(math.radians(deg))
        c, s = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
        # y 轴向下时，该矩阵在视觉上表现为顺时针旋转
        rx, ry = x * c - y * s, x * s + y * c
        return normalize_deg(math.degrees(math.atan2(rx, -ry)))

    for deg in range(0, 360, 15):
        for rotation in (-180.0, -37.5, 0.0, 12.5, 90.0, 181.5, 359.0):
            got = screen_angle_of_marking(deg, rotation)
            want = normalize_deg(deg + rotation)
            delta = abs(((got - want) + 180.0) % 360.0 - 180.0)
            assert delta < 1e-6, f"θ={deg} rotation={rotation} → 屏幕角 {got}，应为 {want}"

    # 正面反解：满足 −rotation 的那个盘面角，必须正好落在屏幕正上方（0°）
    for rotation in (-180.0, -37.5, 0.0, 12.5, 90.0, 181.5, 359.0):
        top_marking = normalize_deg(-rotation)
        on_screen = screen_angle_of_marking(top_marking, rotation)
        assert abs(((on_screen - 0.0) + 180.0) % 360.0 - 180.0) < 1e-6, (
            f"rotation={rotation} 时，盘面角 {top_marking} 并未落在屏幕正上方（落在 {on_screen}）"
        )

    # 语义断言（页面真正依赖的那条）：把 θ 转到顶部后，顶部读数必须就是 θ
    for deg in range(0, 360, 15):
        rotation = normalize_deg(-deg)  # rotationToAlign
        back = normalize_deg(-rotation)
        assert abs(((back - deg) + 180.0) % 360.0 - 180.0) < 1e-9, (
            f"rotationToAlign({deg}) 后顶部读数变成 {back}"
        )
    # 反面对照：证明"+rotation"这个错误写法会被上面抓到，本条测试不是假绿
    rotation = normalize_deg(-90.0)
    wrong = normalize_deg(rotation)
    right = normalize_deg(-rotation)
    assert abs(((wrong - right) + 180.0) % 360.0 - 180.0) > 90.0, (
        "对照失败：+rotation 与 −rotation 在 90° 上竟然接近，本测试无法区分两者"
    )


# ==========================================================================
# 一、后天八卦方位
# ==========================================================================


def test_trigram_directions_match_backend(probe: dict) -> None:
    """八个卦位的**方位角**必须与后端 `GUA_HOUTIAN_DEGREE` 逐一相等。

    卦位错 45° 不会报错，只会让盘面与实物罗盘对不上 —— 静默且致命。
    """
    bad = [
        f"{t['name']}：TS={t['center_degree']}° PY={GUA_HOUTIAN_DEGREE.get(t['name'])}°"
        for t in probe["trigrams"]
        if abs(t["center_degree"] - GUA_HOUTIAN_DEGREE.get(t["name"], -999)) > 1e-9
    ]
    assert not bad, "后天八卦方位不一致：\n" + "\n".join(bad)


def test_trigram_set_complete(probe: dict) -> None:
    assert {t["name"] for t in probe["trigrams"]} == set(GUA_HOUTIAN_DEGREE)
    assert len(probe["trigrams"]) == 8


def test_trigram_yao_match_backend(probe: dict) -> None:
    """卦符爻线（自下而上）必须与后端 `GUA_YAO` 完全相同。

    前端是**自绘**爻线（不依赖字体里的 ☰☱…，避免 Android 缺字渲染成豆腐块）。
    自绘就意味着爻线序列是一份独立实现 —— 一旦与后端画反（自上而下写成自下而上），
    坎会变成离，整圈卦符全错，而视觉上"仍然像八卦"。
    """
    bad = [
        f"{t['name']}：TS={tuple(t['yao'])} PY={GUA_YAO[t['name']]}"
        for t in probe["trigrams"]
        if tuple(t["yao"]) != GUA_YAO[t["name"]]
    ]
    assert not bad, "卦符爻线不一致：\n" + "\n".join(bad)


# ==========================================================================
# 二、二十四山的分类（决定盘面配色）
# ==========================================================================


def test_mountain_roles_match_backend_kind(probe: dict) -> None:
    """前端「盘面角色」必须与后端 `MOUNTAINS[].kind` 同构。

    映射关系（kind → role）：
        gua    → corner （四维：乾坤艮巽）
        stem   → stem   （八天干）
        branch → cardinal（子午卯酉四个主刻度）或 branch（其余八支）
    """
    by_index = {m.index: m for m in MOUNTAINS}
    bad: list[str] = []
    for row in probe["mountain_roles"]:
        m = by_index[row["index"]]
        role = row["role"]
        expected_kind = {
            "corner": "gua",
            "stem": "stem",
            "cardinal": "branch",
            "branch": "branch",
        }[role]
        if m.kind != expected_kind:
            bad.append(f"{row['name']}（第 {row['index']} 位）：role={role} 应为 kind={expected_kind}，后端给 {m.kind}")
        if m.name != row["name"]:
            bad.append(f"第 {row['index']} 位山名：TS={row['name']} PY={m.name}")
    assert not bad, "二十四山分类/顺序不一致：\n" + "\n".join(bad)


def test_cardinal_are_exactly_the_four_principal(probe: dict) -> None:
    """`cardinal` 必须恰好是四正（子午卯酉），不多不少。

    多标一座山会误导用户把它当成主刻度；少标一座则四正不全。
    """
    cardinal = {r["name"] for r in probe["mountain_roles"] if r["role"] == "cardinal"}
    assert cardinal == set(_CARDINAL), f"四正判定不符：{cardinal}"


def test_role_partition_covers_all_twenty_four(probe: dict) -> None:
    """四类角色加起来必须恰好 24 座，且 4 正 / 4 维 / 8 干 / 8 支。"""
    counts: dict[str, int] = {}
    for r in probe["mountain_roles"]:
        counts[r["role"]] = counts.get(r["role"], 0) + 1
    assert counts == {"cardinal": 4, "corner": 4, "stem": 8, "branch": 8}


def test_center_degrees_match_backend(probe: dict) -> None:
    by_index = {m.index: m for m in MOUNTAINS}
    bad = [
        f"第 {r['index']} 位：TS={r['center_degree']}° PY={by_index[r['index']].center_degree}°"
        for r in probe["mountain_roles"]
        if abs(r["center_degree"] - by_index[r["index"]].center_degree) > 1e-9
    ]
    assert not bad, "山心角不一致：\n" + "\n".join(bad)


# ==========================================================================
# 三、一百二十分金分格
# ==========================================================================


def test_fenjin_span_matches_backend(probe: dict) -> None:
    """前端刻度的分格跨度必须等于后端的 `FENJIN_SPAN`，否则分金格与实物错位。"""
    assert probe["fenjin"]["span_degree"] == FENJIN_SPAN
    assert probe["fenjin"]["count"] == int(360 // FENJIN_SPAN)
    assert FENJIN_PER_MOUNTAIN == int(SPAN_DEGREE // FENJIN_SPAN)


def test_tick_total_and_levels(probe: dict) -> None:
    """120 个刻度 = 8 主（45°）+ 16 中（15°）+ 96 细（3°）。"""
    c = probe["checks"]
    assert c["tick_total"] == 120
    assert c["tick_level_counts"] == {"0": 8, "1": 16, "2": 96}

    # 等级与角度的对应关系必须自洽
    for t in probe["ticks"]:
        deg = t["degree"]
        if t["level"] == 0:
            assert deg % 45 == 0, f"{deg}° 标为主刻度，但不是 45° 的倍数"
        elif t["level"] == 1:
            assert deg % 15 == 0 and deg % 45 != 0
        else:
            assert deg % FENJIN_SPAN == 0 and deg % 15 != 0


def test_tick_degrees_are_dense_and_sorted(probe: dict) -> None:
    degrees = [t["degree"] for t in probe["ticks"]]
    assert degrees == sorted(degrees)
    assert len(set(degrees)) == len(degrees), "有重复刻度（叠画会导致视觉变粗）"
    # 刻度必须是 0..359 上每 FENJIN_SPAN 度一个，一个不漏
    assert FENJIN_SPAN == int(FENJIN_SPAN), f"分金跨度应为整数度，实为 {FENJIN_SPAN}"
    assert degrees == list(range(0, 360, int(FENJIN_SPAN)))


# ==========================================================================
# 四、角度归属（旋转相关功能的正确性前提）
# ==========================================================================


def test_degree_to_mountain_matches_backend(probe: dict) -> None:
    """0..359 每个整度，前端盘面与后端 `mountain_at` 必须归到同一座山。"""
    bad: list[str] = []
    for row in probe["degree_to_index"]:
        py = mountain_at(float(row["degree"])).name
        if row["name"] != py:
            bad.append(f"{row['degree']}°：TS={row['name']} PY={py}")
    assert not bad, f"{len(bad)} 个角度归属不一致（前 10 条）：\n" + "\n".join(bad[:10])


def test_mountain_count(probe: dict) -> None:
    assert probe["mountain_count"] == len(MOUNTAINS) == 24


# ==========================================================================
# 五、初始对准口径（档存 / 模板 → 盘面旋转）
# ==========================================================================


def test_initial_rotation_aligns_the_mountain_backend_would_record(probe: dict) -> None:
    """盘面顶部指着的那座山，必须正是内核会记进 `sitting` 的那座山。

    这条守的是一句**跨语言的话**，而不是某个前端公式。口径只在内核里定：

        calculate_orientation(degree=180.24) → sitting='午', facing='子'

    即 `degree` 落在**坐山**那一格上（模板测试的 `(sitting='午', facing='子',
    degree=180.24)` 是同一关系的另一处证据）。所以盘面顶部必须指向坐山。

    🔴 曾经按「取向山山心角」实现过第三档退路，后果是**同一条记录在
       "有实测角"与"没实测角"两种情况下盘面相差 180°** —— 盘面画得完全正常，
       只有把它与记录里的「坐 X 向 Y」对读才会发现读数指向了向而不是坐。
       底部那条反面对照就是为了证明本测试真的能区分这两种口径。
    """
    from fortune_core.compass import calculate_orientation
    from fortune_core.mountain24 import opposite

    # ① 只有坐山（无实测角）→ 顶部就是那座山本身
    bad_sitting = [
        f"{r['sitting_name']}（index {r['sitting_index']}）→ 顶部 {r['top_mountain']}"
        for r in probe["initial_rotation_sweep"]["by_sitting"]
        if r["top_mountain"] != r["sitting_name"]
    ]
    assert not bad_sitting, (
        "只有坐山时，盘面顶部没有对准坐山：\n" + "\n".join(bad_sitting)
    )

    # ② 只有实测角 → 顶部那座山 == 内核由该角度定出的坐山
    bad_degree: list[str] = []
    for row in probe["initial_rotation_sweep"]["by_degree"]:
        sitting = calculate_orientation(degree=float(row["degree"])).sitting.name
        if row["top_mountain"] != sitting:
            bad_degree.append(
                f"{row['degree']}°：TS 顶部={row['top_mountain']} 内核坐山={sitting}"
            )
    assert not bad_degree, (
        f"{len(bad_degree)} 个角度上盘面顶部与内核坐山不符（前 10 条）：\n"
        + "\n".join(bad_degree[:10])
    )

    # ③ 反面对照：证明"按向对齐"的旧写法确实会被上面抓到。
    #    degree=0 时内核给 sitting=子、facing=午，两者不同 —— 若前端按向对齐，
    #    ① 与 ② 都会看到「午」而不是「子」。
    d0 = float(probe["initial_rotation_sweep"]["by_degree"][0]["degree"])
    o = calculate_orientation(degree=d0)
    assert opposite(o.sitting.name) == o.facing.name
    assert o.facing.name != o.sitting.name, (
        f"degree={d0} 时坐山与向山竟然同名，本测试无法区分两种口径"
    )
    ts_top = probe["initial_rotation_sweep"]["by_degree"][0]["top_mountain"]
    assert ts_top == o.sitting.name
    assert ts_top != o.facing.name, (
        f"degree={d0} 时 TS 顶部是 {ts_top}，等于向山 —— 口径反了"
    )
