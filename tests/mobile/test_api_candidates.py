"""`apps/mobile/src/lib/apiCandidates.ts` 的候选地址回归 —— 钉住「连不上后端」这件事。

## 为什么需要这道测试

真机装包后最常见、也最难查的故障是**连不上后端**：界面只是转圈或报一句
"无法连接后端服务"，看不出是地址错了、网段不对，还是后端没起。

而 APK 只能内联**一个**地址，构建机却常有多块网卡分属不同网段
（实测本机同时存在 `192.168.57.10` / `192.168.59.56` / `192.168.68.80`）。
所以本次改成了「内联一张候选表 + 启动时并发探活」。这段逻辑一旦写错，
表现与"网络不通"完全一样 —— 没有任何异常会指到代码上。

| 环节 | 写错的后果 | 谁来兜 |
|---|---|---|
| 候选表规范化/合并 | 候选少了或顺序乱了，换网段静默不生效 | **本文件** |
| 并发探活 | 卡住不返回、或全失败时抛异常导致红屏 | **本文件** |
| 构建期注入 | bundle 里根本没有候选表，退回 127.0.0.1 | `build-apk.sh` 自检 + 交付时解包核验 |

## 为什么必须真跑

扫源码只能证明"文件里写了 `Set` 去重"，证明不了"`a,b` 与 `b,c` 合出来还是
`a,b,c`"、也证明不了"全失败的探活会在有限时间内返回 null"。所以用探针真跑
`apiCandidates.ts`，把结果交给 pytest。

## 两份实现的漂移（本文件覆盖的重点之一）

规范化规则在运行期（TS）与构建期（`app.config.js`，CommonJS）各有一份 ——
它们无法共享模块。于是"改了一边忘了另一边"成了结构性风险：构建期注入了
4 个地址、运行期只认 1 个，**不报错**，只是换网段不生效。

所以探针把 `app.config.js` 也真 `require` 进来跑，本文件逐项比对两边结果。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/api_candidates_probe.ts"

#: 探针里用的兜底地址（构建期在候选表为空时补的那一项），比对时需剥离
_CROSS_FALLBACK = "http://fallback:8360"


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    """真跑 `api_candidates_probe.ts`，取回它对 `apiCandidates.ts` 的实际调用结果。"""
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过候选地址回归校验")
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
    if proc.returncode != 0:
        pytest.fail(
            "候选地址探针执行失败（可能是 apiCandidates.ts 有语法错误，"
            "或 app.config.js 无法被 require）：\n"
            f"{proc.stderr.strip()[:2000]}"
        )

    # node 会把 MODULE_TYPELESS_PACKAGE_JSON 之类的告警写到 stderr，
    # 但**也可能混进 stdout**（取决于 node 版本），所以只取最后一个 JSON 对象。
    raw = proc.stdout.strip()
    start = raw.find("{")
    if start < 0:
        pytest.fail(f"探针没有输出 JSON。原始输出前 500 字：{raw[:500]}")
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError as exc:  # pragma: no cover
        pytest.fail(f"探针输出不是合法 JSON：{exc}\n原始输出前 500 字：{raw[:500]}")


# ==========================================================================
# 假绿自检
# ==========================================================================


def test_probe_is_not_vacuous(probe: dict) -> None:
    """探针必须真的覆盖到四条通道，否则下面的断言只是自说自话。

    少任何一条，本文件都会"全绿"，但被漏掉的那条通道其实是零覆盖 ——
    这正是探针类测试最常见的假绿方式。
    """
    assert len(probe["normalize_cases"]) >= 10, "规范化用例太少，不足以覆盖边界"
    assert len(probe["merge_cases"]) >= 6, "合并用例太少"
    assert len(probe["pick_cases"]) >= 5, "探活用例太少"
    assert len(probe["app_config_cases"]) >= 6, "构建期用例太少"
    assert len(probe["cross_consistency"]) >= 3, "交叉比对用例太少"


# ==========================================================================
# 1. 规范化：一串文本 → 规范地址表
# ==========================================================================

#: 期望值**独立写在这里**，不复用探针输出 —— 否则就是拿实现验证实现。
_NORMALIZE_EXPECTED: dict[str, list[str]] = {
    "plain": ["http://a:8360"],
    "comma": ["http://a:8360", "http://b:8360"],
    "spaces": ["http://a:8360", "http://b:8360"],
    "trailing_slash": ["http://a:8360"],
    "dedupe": ["http://a:8360", "http://b:8360"],
    # 去斜杠之后才相同的两项，也必须合并成一个
    "dedupe_after_normalize": ["http://a:8360"],
    "drop_non_http": ["http://a:8360"],
    "drop_empty": ["http://a:8360", "http://b:8360"],
    "https_kept": ["https://a.example.com:8360"],
    "all_invalid": [],
    "empty": [],
    "undefined": [],
    "null": [],
}


def test_normalize_cases_match_expectations(probe: dict) -> None:
    """逐项核对规范化结果（期望表见 `_NORMALIZE_EXPECTED`）。"""
    by_name = {c["name"]: c for c in probe["normalize_cases"]}

    assert set(by_name) == set(_NORMALIZE_EXPECTED), (
        "用例集合与期望表不一致 —— 探针加了用例而这里没补期望，"
        f"或反之。\n探针有：{sorted(by_name)}\n期望表有：{sorted(_NORMALIZE_EXPECTED)}"
    )

    for name, expected in _NORMALIZE_EXPECTED.items():
        got = by_name[name]["output"]
        assert got == expected, f"用例 {name!r}：期望 {expected}，实际 {got}"


def test_empty_and_none_are_indistinguishable(probe: dict) -> None:
    """`undefined` 与 `null` 都应得到空表。

    它们对应两种真实情形：构建期变量**没设**（undefined）与显式传了 null。
    两者都必须安全退化为空表，而不是抛异常 —— 抛了会让整个 APP 起不来。
    """
    by_name = {c["name"]: c for c in probe["normalize_cases"]}
    assert by_name["undefined"]["output"] == []
    assert by_name["null"]["output"] == []


# ==========================================================================
# 2. 合并：多来源按优先级
# ==========================================================================

_MERGE_EXPECTED: dict[str, list[str]] = {
    "priority_order": ["http://first:8360", "http://second:8360"],
    # b 在第二个来源里又出现一次：必须留在**先出现**的位置，不得后移
    "cross_source_dedupe": ["http://a:8360", "http://b:8360", "http://c:8360"],
    "array_source": ["http://arr1:8360", "http://arr2:8360"],
    "array_and_string_mixed": ["http://arr:8360", "http://str:8360"],
    "skips_falsy": ["http://only:8360"],
    "array_with_invalid_items": ["http://ok:8360"],
    "empty_sources": [],
}


def test_merge_cases_match_expectations(probe: dict) -> None:
    """逐项核对多来源合并（期望表见 `_MERGE_EXPECTED`）。"""
    by_name = {c["name"]: c for c in probe["merge_cases"]}

    assert set(by_name) == set(_MERGE_EXPECTED), (
        f"用例集合不一致。\n探针有：{sorted(by_name)}\n期望表有：{sorted(_MERGE_EXPECTED)}"
    )

    for name, expected in _MERGE_EXPECTED.items():
        got = by_name[name]["output"]
        assert got == expected, f"用例 {name!r}：期望 {expected}，实际 {got}"


def test_merge_preserves_first_occurrence_position(probe: dict) -> None:
    """顺序即优先级 —— 后来源里的重复项**不得**插到前面去。

    这是"优先级"能否成立的关键：如果合并时按来源分组而不是按首次出现排序，
    后一个来源的地址会整体排到前一个之后，看起来也对；但一旦两边有交叉
    （如 a,b + b,c），顺序错乱会让首选地址变成非预期的那个。
    """
    by_name = {c["name"]: c for c in probe["merge_cases"]}
    got = by_name["cross_source_dedupe"]["output"]
    assert got.index("http://a:8360") < got.index("http://b:8360") < got.index("http://c:8360")


# ==========================================================================
# 3. 探活：并发、取第一个回应、全失败不卡死
# ==========================================================================

_PICK_EXPECTED: dict[str, str | None] = {
    # 首个即可用：直接返回它
    "first_ok": "http://a",
    # 靠前的很慢、靠后的立刻回应：应返回**先回应的**，而不是死等靠前的
    "fast_later_wins": "http://fast",
    # 只有中间那个可用
    "middle_ok": "http://b",
    # 全部失败 → null（而不是抛异常）
    "all_fail": None,
    # 空表 → null，且必须立刻返回
    "empty": None,
    "concurrent_not_serial": None,
}


def test_pick_cases_match_expectations(probe: dict) -> None:
    """逐项核对探活结果（期望表见 `_PICK_EXPECTED`）。"""
    by_name = {c["name"]: c for c in probe["pick_cases"]}

    assert set(by_name) == set(_PICK_EXPECTED), (
        f"用例集合不一致。\n探针有：{sorted(by_name)}\n期望表有：{sorted(_PICK_EXPECTED)}"
    )

    for name, expected in _PICK_EXPECTED.items():
        got = by_name[name]["got"]
        assert got == expected, f"用例 {name!r}：期望 {expected}，实际 {got}"


def test_pick_never_raises_on_total_failure(probe: dict) -> None:
    """全失败必须返回 null，**不得抛异常**。

    调用点在 App 启动路径上。抛出去就是一次红屏 —— 而启动期连不上是常态
    （后端没起、手机不在同一网段），红屏会让用户连「我的 → 网络线路」
    这个手改入口都进不去。
    """
    by_name = {c["name"]: c for c in probe["pick_cases"]}
    assert by_name["all_fail"]["got"] is None


def test_pick_probes_all_candidates_concurrently(probe: dict) -> None:
    """并发而非串行 —— 用耗时与"是否全都试过"共同判定。

    `concurrent_not_serial` 里三个候选分别延迟 30/60/90 ms 且全部失败：
    - 串行耗时 ≈ 180ms
    - 并发耗时 ≈ 90ms（最慢的那个）
    判据取 150ms，留出余量。

    再断言"三个都被试过"：否则"快"可能只是因为**根本没试**另外两个 ——
    那会让本该被发现的可用后端被跳过。
    """
    case = {c["name"]: c for c in probe["pick_cases"]}["concurrent_not_serial"]

    assert len(case["tried"]) == 3, (
        f"只尝试了 {len(case['tried'])} 个候选（应为 3 个）：{case['tried']}\n"
        "→ 被跳过的候选即使真的可用也不会被发现。"
    )
    assert case["elapsed_ms"] < 150, (
        f"耗时 {case['elapsed_ms']}ms，接近串行的 180ms —— 探活没有并发执行。\n"
        "→ 3 个候选各等一次超时，启动时会白屏数秒。"
    )


def test_pick_does_not_wait_for_slow_candidate(probe: dict) -> None:
    """靠前的候选很慢时，不得阻塞靠后的可用候选。

    这条是"用户体验"的核心：若实现是"按顺序串行、前一个失败才试下一个"，
    那么首选地址所在网段不通时，用户要等满一个超时才切到正确的地址。
    """
    case = {c["name"]: c for c in probe["pick_cases"]}["fast_later_wins"]
    assert case["got"] == "http://fast"
    # 慢的那个延迟 80ms；真做到了"先回应先用"，总耗时应远小于它
    assert case["elapsed_ms"] < 60, (
        f"耗时 {case['elapsed_ms']}ms —— 疑似在等靠前的慢候选（其延迟为 80ms）"
    )


# ==========================================================================
# 4. 构建期实现（app.config.js）—— 独立校验
# ==========================================================================

_APP_CONFIG_EXPECTED: dict[str, list[str]] = {
    "list_only": ["http://a:8360", "http://b:8360"],
    "single_only": ["http://solo:8360"],
    # 两者都设时以 list 为准（single 只是"首选"语义）
    "both_list_wins": ["http://a:8360", "http://b:8360"],
    "neither_falls_back": ["http://fallback:8360"],
    "dedupe_and_trim": ["http://a:8360", "http://b:8360"],
    # 全非法时**不能**得到空表：空表会让"首选地址"与"候选表"指向两个后端
    "all_invalid_falls_back": ["http://fallback:8360"],
}


def test_app_config_cases_match_expectations(probe: dict) -> None:
    """逐项核对构建期（CommonJS 那份实现）的结果。"""
    by_name = {c["name"]: c for c in probe["app_config_cases"]}

    assert set(by_name) == set(_APP_CONFIG_EXPECTED), (
        f"用例集合不一致。\n探针有：{sorted(by_name)}\n期望表有：{sorted(_APP_CONFIG_EXPECTED)}"
    )

    for name, expected in _APP_CONFIG_EXPECTED.items():
        got = by_name[name]["output"]
        assert got == expected, f"用例 {name!r}：期望 {expected}，实际 {got}"


def test_app_config_never_returns_empty(probe: dict) -> None:
    """构建期的候选表**必须非空**，且首项等于首选地址。

    空表会让构建期写进 `extra.apiBaseUrls` 的东西与 `extra.apiBaseUrl`
    （首选）不一致 —— APP 用一个地址连、却按另一张表探活，
    这种分裂在真机上表现为"偶发连不上"，几乎无法复现定位。
    """
    for case in probe["app_config_cases"]:
        assert case["output"], f"用例 {case['name']!r} 得到了空表"


# ==========================================================================
# 5. 两份实现的交叉一致性 —— 本文件最重要的一组
# ==========================================================================


def test_runtime_and_build_agree_on_normalization(probe: dict) -> None:
    """运行期与构建期的规范化结果必须逐项一致。

    ⚠️ 比对方式是「构建期结果剥离兜底项」后与运行期结果相等，而不是直接相等：
    两者职责不同 —— `normalizeCandidateUrls` 是纯规范化（全非法 → 空表），
    而 `app.config.js` 还要保证表非空。直接比会把"职责差异"误报成"实现漂移"。
    """
    for case in probe["cross_consistency"]:
        assert case["build_is_runtime_plus_fallback"], (
            f"输入 {case['raw']!r} 两边结果不一致：\n"
            f"  运行期（apiCandidates.ts）: {case['runtime']}\n"
            f"  构建期（app.config.js）  : {case['build']}\n"
            "→ 两份实现漂移了。构建期注入的地址运行期认不出来，"
            "表现是「换网段不生效」而**不报任何错**。"
        )


def test_all_invalid_inputs_still_yield_fallback(probe: dict) -> None:
    """全非法输入时必须恰好得到「一项兜底」。

    这条单列出来，是因为它最容易在"精简代码"时被删掉：
    `if (apiBaseUrls.length === 0) apiBaseUrls.push(apiBaseUrl);` 看起来像
    一句多余的兜底，但没有它就会写出空表（见上一条测试的说明）。
    """
    case = {c["raw"]: c for c in probe["cross_consistency"]}["ftp://x,garbage"]
    assert case["runtime"] == [], "纯规范化对全非法输入应得到空表"
    assert case["build"] == [_CROSS_FALLBACK], (
        f"构建期对全非法输入应得到仅含兜底项的表，实际 {case['build']}"
    )
