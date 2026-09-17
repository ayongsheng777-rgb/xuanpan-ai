"""`apps/mobile/src/lib/date.ts` 的本地日期回归 —— 钉住「凌晨不倒退一天」。

## 为什么需要这道测试

东八区的凌晨 0:00–8:00 之间，`new Date(...)` 的 UTC 表示仍在**前一天**。
用 `toISOString().slice(0, 10)` 取日期串会**静默退一天** ——
用户点「今天」，查到的是昨天的黄历，而页面没有任何异常迹象。

本机实测（探针输出）：

| 本地时刻 | `toISODate()`（正确） | `toISOString().slice(0,10)`（错误） |
|---|---|---|
| 2026-09-17 00:00 | `2026-09-17` | `2026-09-16` |
| 2026-09-17 00:30 | `2026-09-17` | `2026-09-16` |
| 2026-09-17 07:59 | `2026-09-17` | `2026-09-16` |
| 2026-09-17 08:00 | `2026-09-17` | `2026-09-17`（8 点后 UTC 才落到当天） |

这个错误只在**一天中的前 1/3** 出现，靠人工点页面几乎不可能发现。
所以用探针真跑 `date.ts`，把它钉死在 `pytest` 里。

## 为什么不是"扫源码看有没有 toISOString"

扫源码只能证明"文件里没出现那个词"，证明不了"凌晨 0:30 算出来还是今天"。
而这个模块存在的**全部理由**就是后者。

## 假绿自检（这道测试最容易失效的方式）

陷阱能否复现**取决于运行时区**。在 UTC 或西半球，`toISOString` 并不会退一天，
于是所有断言都会轻松通过 —— 而测试已经变成一句空话。

三重防线让它无法悄悄失效：
1. 探针固定以 `TZ=Asia/Shanghai` 运行；
2. 断言时区偏移确实是 +480 分钟（固定失败，不静默跳过）；
3. 断言「错误写法确实算错了」至少一例 —— 前提不成立就报错，而不是放过。

三者任一不成立，说明这道测试已经失去意义，此时**必须失败**。
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _REPO_ROOT / "apps/mobile/scripts/date_probe.ts"

#: 固定时区 —— 该陷阱只在 UTC 以东复现。不固定就取决于跑测试的机器，
#: 在 CI 或另一台机器上可能变成永远通过的空测试。
_TZ = "Asia/Shanghai"
_EXPECTED_OFFSET_MINUTES = 480  # UTC+8

#: Python `date.weekday()` 的取值：周一 = 0 … 周日 = 6
_WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


@pytest.fixture(scope="module")
def probe() -> dict:
    """真跑 `date_probe.ts`，取回它对 `src/lib/date.ts` 的实际调用结果。"""
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过本地日期回归校验")
    if not _PROBE.exists():
        pytest.skip(f"未找到探针脚本：{_PROBE}")

    env = {**os.environ, "TZ": _TZ}
    proc = subprocess.run(
        [node, "--experimental-strip-types", str(_PROBE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO_ROOT),
        timeout=60,
        env=env,
    )
    if proc.returncode != 0:
        pytest.fail(
            "date 探针执行失败（可能是 date.ts 有语法/类型错误，或守卫抛到了用例之外）：\n"
            f"{proc.stderr.strip()[:2000]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - 只在探针被改坏时触发
        pytest.fail(f"探针输出不是合法 JSON：{exc}\n原始输出前 500 字：{proc.stdout[:500]}")


# ==========================================================================
# 假绿自检：先证明"这道测试有能力失败"
# ==========================================================================


def test_probe_runs_in_utc_plus_8(probe: dict) -> None:
    """探针必须真的跑在 UTC+8。

    跑不到就说明 `TZ` 没生效（Windows 上尤其容易），那么下面所有关于
    「凌晨不倒退」的断言都失去了意义 —— 在 UTC 机器上那个 bug 根本不存在。
    此时**报错**而不是跳过：一个静默跳过的守卫等于没有守卫。
    """
    assert probe["tz_offset_minutes"] == _EXPECTED_OFFSET_MINUTES, (
        f"探针时区偏移为 {probe['tz_offset_minutes']} 分钟（期望 {_EXPECTED_OFFSET_MINUTES}），"
        f"解析到的时区名是 {probe['tz_name']!r}。\n"
        "→ `TZ=Asia/Shanghai` 未生效，本测试无法验证「凌晨倒退一天」这个陷阱。"
    )


def test_the_hazard_actually_exists_here(probe: dict) -> None:
    """`toISOString()` 的错误写法在本环境必须**真的会**算错。

    这是本文件最重要的一条：如果错误写法也算对（比如跑在 UTC），
    那下面的断言就只是在复述一个恒等式，测试沦为假绿。
    """
    wrong = [
        c for c in probe["midnight_cases"]
        if c["via_toisostring"] != c["expected"]
    ]
    assert wrong, (
        "在本环境下 `toISOString()` 并未算错，说明时区不是 UTC 以东，"
        "这道测试已失去验证能力。\n"
        f"（时区：{probe['tz_name']}，偏移 {probe['tz_offset_minutes']} 分钟）"
    )
    # 至少要有"凌晨"那一批，否则说明采样点被改到了 8 点之后
    labels = [c["label"] for c in wrong]
    assert any(" 00:" in lb or " 07:" in lb for lb in labels), (
        f"失败的样本里没有凌晨时刻，采样点可能被改错了：{labels}"
    )


# ==========================================================================
# 核心断言：本地日期永不倒退
# ==========================================================================


def test_local_date_never_off_by_one(probe: dict) -> None:
    """所有凌晨/边界样本，`toISODate` 都必须给出「用户表盘上的那一天」。"""
    bad = [
        f"{c['label']}：期望 {c['expected']}，实得 {c['via_lib']}"
        for c in probe["midnight_cases"]
        if c["via_lib"] != c["expected"]
    ]
    assert not bad, "本地日期取值错误（凌晨会退一天）：\n" + "\n".join(bad)


def test_parse_roundtrip(probe: dict) -> None:
    """`YYYY-MM-DD` → Date → `YYYY-MM-DD` 必须回到自身。

    这条同时挡住 `new Date(iso)` 的陷阱（ISO 日期串按 UTC 解析，
    `getDate()` 在 UTC+8 会得到前一天）。
    """
    bad = [f"{r['iso']} → {r['back']}" for r in probe["roundtrip"] if not r["ok"]]
    assert not bad, "日期串解析往返不一致：\n" + "\n".join(bad)


def test_roundtrip_does_not_use_naive_parse(probe: dict) -> None:
    """往返过程中不得用到 `new Date(iso)` 的按 UTC 解析。

    直接证据：若按 UTC 解析，`new Date('2026-09-01').getDate()` 在东八区会得到
    8 月 31 日的 31 —— 探针把 `naive_getdate` 一并导出了，这里确认它确实与
    日期串里的"日"不同（说明两种取值法真的会分叉，我们的往返没有依赖它）。
    """
    # 只取月初几天：这是两种解析法必然分叉的位置
    for r in probe["roundtrip"]:
        if r["iso"].endswith("-01"):
            assert r["back"] == r["iso"], (
                f"{r['iso']} 往返得到 {r['back']} —— 月初最容易暴露按 UTC 解析的问题"
            )


# ==========================================================================
# 位移
# ==========================================================================


@pytest.mark.parametrize(
    "case",
    [
        {"iso": "2026-09-17", "days": 1},
        {"iso": "2026-09-17", "days": -1},
        {"iso": "2026-09-30", "days": 1},
        {"iso": "2026-01-01", "days": -1},
        {"iso": "2026-12-31", "days": 1},
        {"iso": "2024-02-28", "days": 1},
        {"iso": "2026-02-28", "days": 1},
        {"iso": "2024-02-29", "days": 1},
        {"iso": "2026-09-17", "days": 0},
        {"iso": "2026-09-17", "days": 60},
    ],
    ids=lambda c: f"{c['iso']}{c['days']:+d}",
)
def test_shift_days(probe: dict, case: dict) -> None:
    """跨月 / 跨年 / 闰年 / 平年的位移。

    闰年那两条是关键：`2024-02-28 +1 = 2024-02-29`（有 29 日），
    `2026-02-28 +1 = 2026-03-01`（没有）。用固定天数硬加会在这里出错。
    """
    row = next(
        (s for s in probe["shifts"] if s["iso"] == case["iso"] and s["days"] == case["days"]),
        None,
    )
    assert row is not None, f"探针未覆盖 {case}"
    assert row["got"] == row["expected"], (
        f"{case['iso']} {case['days']:+d} 天：期望 {row['expected']}，实得 {row['got']}"
    )


# ==========================================================================
# 星期（与 Python 日历交叉核对，而不是复述 JS 的常量表）
# ==========================================================================


def test_weekday_matches_python_calendar(probe: dict) -> None:
    """`weekdayLabel` 的结果必须与 Python 自己的日历一致。

    刻意用 Python 的 `datetime.date.weekday()` 作为**独立真值**，
    而不是复述前端那份常量数组 —— 后者等于把常量抄一遍，抄错也检不出来。
    """
    bad = []
    for row in probe["weekdays"]:
        y, m, d = (int(x) for x in row["iso"].split("-"))
        expected = _WEEKDAY_LABELS[datetime.date(y, m, d).weekday()]
        if row["label"] != expected:
            bad.append(f"{row['iso']}：JS={row['label']} PY={expected}")
    assert not bad, "星期换算与 Python 日历不一致：\n" + "\n".join(bad)


def test_weekday_covers_all_seven(probe: dict) -> None:
    """样本必须覆盖完整一周，否则上面那条可能在"只有工作日"时假绿。"""
    labels = {row["label"] for row in probe["weekdays"]}
    assert labels == set(_WEEKDAY_LABELS), f"样本未覆盖完整一周：{sorted(labels)}"


# ==========================================================================
# 区间与"今天"
# ==========================================================================


def test_range_from_shares_one_anchor(probe: dict) -> None:
    """`rangeFrom` 的两端必须同源（同一次锚点取值）。

    若两端各取一次"今天"，午夜前后会得到跨天的一对日期
    （起始属旧日、结束属新日），而界面上完全看不出来。
    """
    r30 = probe["range_30"]
    r0 = probe["range_0"]
    assert r30[0] == "2026-09-17" and r30[1] == "2026-10-17", f"30 天区间不对：{r30}"
    assert r0[0] == r0[1] == "2026-09-17", f"0 天区间应首尾同一天：{r0}"


def test_is_today(probe: dict) -> None:
    """`isToday` 与 `todayISODate` 同源 —— 否则会出现"按钮高亮着、查的却是昨天"。"""
    assert probe["is_today_self"] is True
    assert probe["is_today_other"] is False
    # 今天必须是合法形状，且能被自己解析回来
    assert len(probe["today"]) == 10
    assert probe["today"].count("-") == 2


# ==========================================================================
# 守卫：非法输入必须抛，不得静默产出"看着像日期"的东西
# ==========================================================================


@pytest.mark.parametrize(
    "key",
    ["bad_shape", "short_shape", "empty", "nonexistent", "nonexistent_31", "invalid_date"],
    ids=["斜杠分隔", "月份未补零", "空串", "2月30日", "4月31日", "Invalid Date"],
)
def test_guards_reject_bad_input(probe: dict, key: str) -> None:
    """非法日期必须抛 `RangeError`。

    为什么"抛"而不是"返回 null"：这些都是**编程错误**（调用方传错了），
    不是用户输入错误。静默返回什么都会让错误往后传 ——
    最糟的是 `Date` 的默认行为：把 2 月 30 日"顺延"成 3 月 2 日，
    于是黄历会一本正经地给出一个**不存在的那一天**的宜忌。
    """
    g = probe["guards"][key]
    assert g["threw"], f"{key} 应当抛错，实际返回了 {g['value']}"
    assert g["error"] == "RangeError", f"{key} 抛的是 {g['error']}，期望 RangeError"


def test_guards_accept_valid_input(probe: dict) -> None:
    """守卫不得误报 —— 一个总在报警的校验器等于没有校验器。

    `2026-02-28` 是平年最后一个有效日期，必须顺利通过。
    """
    g = probe["guards"]["valid"]
    assert not g["threw"], f"合法日期被拒绝：{g['error']}"
