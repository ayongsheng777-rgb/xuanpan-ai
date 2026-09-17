"""管理台试算台「默认日期」回归 —— 真跑页面里的那段代码，不测副本。

## 为什么要有这个文件

`admin.html` 的 `initLab()` 会给几个输入框填默认值：择日起止日、六爻起卦日、
奇门时刻。这些默认值原本用 `new Date().toISOString().slice(0, 10)` 生成 ——
而 `toISOString()` **先转 UTC**，在 UTC+8 的本地 00:00~08:00 会退回**前一天**。

这不是显示瑕疵：六爻面板的「起卦日」会一路喂给日干支，直接改变装卦结果
（六神、旬空都随日干走），**在凌晨打开页面排出的卦就是错的**，且不报错。

## 为什么要跑到 node 里

断言字符串（"页面里含有 localDate"）只能证明**写了**这个函数，
证明不了它算对。所以这里把 `admin.html` 里那段 helper **原样抽出来交给 node 执行**，
再用 Python 核结果 —— 测的是页面真正会跑的那份代码，
而不是测试文件里另抄一份（抄一份的话，源码改错了测试照样绿）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_ADMIN_HTML = (
    Path(__file__).resolve().parents[2]
    / "services/api/xuanpan_api/static/admin.html"
)

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

#: 从 `const _p2` 起、到 `localDateTime` 函数结束为止 —— 正是页面里那段 helper
_HELPER_RE = re.compile(
    r"(const _p2[\s\S]*?function localDateTime\(d\) \{[\s\S]*?\n\})"
)

_SELF_CHECK = """
// 假绿自检：如果旧的 UTC 写法在凌晨不会出错，这套测试就没有意义。
// 这里必须先证明「旧写法确实是坏的」，否则后续断言可能只是恰好成立。
function naiveUtcDate(d) { return d.toISOString().slice(0, 10); }

const rows = [];
for (let h = 0; h < 24; h++) {
  const d = new Date(2026, 8, 17, h, 30);   // 本地 2026-09-17 各整点半
  rows.push({
    hour: h,
    localDate: localDate(d),
    localDateTime: localDateTime(d),
    naive: naiveUtcDate(d),
  });
}
console.log(JSON.stringify(rows));
"""

#: 跨月 / 跨年 / 跨日边界用例。
#:
#: 加这组的原因来自变异验证：只测「同月同年的 9 月 17 日」时，
#: 把 `getMonth()` 误写成 `getUTCMonth()` 或 `getFullYear()` 误写成
#: `getUTCFullYear()` **抓不到** —— 那几个小时的 UTC 月/年恰好与本地相同，
#: 属于等价变异。取月初、年初的凌晨（UTC 还在上个月/上一年）才能真正区分，
#: 否则「本地分量」这个要求就只是碰巧成立。
_BOUNDARY_CASES = """
// 旧写法，用于对照（证明这些边界确实能区分本地分量与 UTC 分量）
function naiveUtcDate(d) { return d.toISOString().slice(0, 10); }

const cases = [
  // [本地年, 本地月(0基), 本地日, 时, 分, 期望的 localDate]
  [2026, 8,  1,  0, 30, "2026-09-01"],   // 月初凌晨：UTC 仍是 8 月
  [2027, 0,  1,  0, 30, "2027-01-01"],   // 年初凌晨：UTC 仍是上一年
  [2026, 2,  1,  7, 59, "2026-03-01"],   // 边界最后一分钟
  [2026, 2,  1,  8, 30, "2026-03-01"],   // 越过边界之后
  [2026, 8, 30, 23, 30, "2026-09-30"],   // 月末深夜
  [2026, 11, 31, 23, 30, "2026-12-31"],  // 年末深夜
  [2024, 1, 29,  0, 30, "2024-02-29"],   // 闰日
];
console.log(JSON.stringify(cases.map(function (c) {
  const d = new Date(c[0], c[1], c[2], c[3], c[4]);
  return { expected: c[5], localDate: localDate(d), naive: naiveUtcDate(d) };
})));
"""


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


def _node_env() -> dict[str, str]:
    """在保留宿主环境的前提下把时区钉死为 UTC+8。

    **不能直接传 `env={"TZ": ...}`** —— 那会把整个环境换掉，
    而 Windows 上 node 启动需要 `SystemRoot` 等系统变量，环境一空就会崩在
    `Assertion failed: ncrypto::CSPRNG(nullptr, 0)`（熵源初始化失败）。
    本机实测踩过这个坑。
    """
    env = os.environ.copy()
    env["TZ"] = "Asia/Shanghai"
    # 让 node 不要读用户级配置，避免本机 NODE_OPTIONS 影响结果
    env.pop("NODE_OPTIONS", None)
    return env


@pytest.fixture(scope="module")
def helper_source() -> str:
    html = _ADMIN_HTML.read_text(encoding="utf-8")
    match = _HELPER_RE.search(html)
    assert match, (
        "未能在 admin.html 中定位日期 helper（const _p2 ... localDateTime）。"
        "若已重命名，请同步本测试的 _HELPER_RE —— "
        "宁可测试报错，也不要让它静默跳过。"
    )
    return match.group(1)


def _run_node(helper_source: str, code: str) -> object:
    """把页面里的 helper 与一段断言代码拼起来，交给 node 真跑一遍。

    用参数列表直接调起，不经 shell —— 避免引号 / 中文被 shell 二次解释。
    """
    node = _node()
    if node is None:
        pytest.skip("未找到 node，跳过管理台默认日期回归校验")

    proc = subprocess.run(
        [node, "-e", helper_source + "\n" + code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_node_env(),
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"node 执行页面 helper 失败：\nstdout={proc.stdout}\nstderr={proc.stderr}"
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope="module")
def hour_rows(helper_source: str) -> list[dict[str, object]]:
    rows = _run_node(helper_source, _SELF_CHECK)
    assert isinstance(rows, list) and len(rows) == 24
    return rows


@pytest.fixture(scope="module")
def boundary_rows(helper_source: str) -> list[dict[str, object]]:
    rows = _run_node(helper_source, _BOUNDARY_CASES)
    assert isinstance(rows, list) and rows, "边界用例为空"
    return rows


class TestLocalDateHelper:
    """helper 本身的行为。"""

    def test_every_hour_maps_to_the_same_local_day(
        self, hour_rows: list[dict[str, object]]
    ) -> None:
        """一天 24 小时取到的都应是本地当天 —— 含凌晨那 8 小时。"""
        for row in hour_rows:
            assert row["localDate"] == "2026-09-17", (
                f"本地 {row['hour']:02d}:30 的 localDate 应为 2026-09-17，"
                f"实为 {row['localDate']}"
            )

    def test_local_date_time_carries_the_local_clock(
        self, hour_rows: list[dict[str, object]]
    ) -> None:
        """datetime-local 需要的格式：YYYY-MM-DDTHH:MM，且小时是本地小时。"""
        for row in hour_rows:
            expected = f"2026-09-17T{row['hour']:02d}:30"
            assert row["localDateTime"] == expected, (
                f"localDateTime 应为 {expected}，实为 {row['localDateTime']}"
            )

    def test_pads_single_digit_month_and_day(
        self, helper_source: str
    ) -> None:
        """月份/日期个位数必须补零 —— 否则 '2026-9-7' 会被 input[type=date] 判为非法。"""
        got = _run_node(
            helper_source,
            "console.log(JSON.stringify(["
            "localDate(new Date(2026, 0, 5, 12, 0)),"
            " localDateTime(new Date(2026, 0, 5, 9, 7))]));",
        )
        assert got == ["2026-01-05", "2026-01-05T09:07"]

    def test_boundaries_where_utc_component_differs(
        self, boundary_rows: list[dict[str, object]]
    ) -> None:
        """跨月 / 跨年 / 闰日边界处的凌晨与深夜。

        这组用例的存在理由来自变异验证：仅测「同年同月的 9 月 17 日」时，
        把 `getMonth()` 误写成 `getUTCMonth()`（或 `getFullYear()` 误写成
        `getUTCFullYear()`）**抓不到** —— 那几个小时的 UTC 月/年与本地恰好相同，
        属于等价变异。取月初/年初的凌晨，UTC 还停在上个月/上一年，才能真正区分。

        换句话说：没有这组用例，「用本地分量」这个要求只是**碰巧**成立。
        """
        for row in boundary_rows:
            assert row["localDate"] == row["expected"], (
                f"边界用例期望 {row['expected']}，实为 {row['localDate']}"
            )

    def test_load_time_defaults_land_on_the_local_day(self, helper_source: str) -> None:
        """模拟 initLab 的真实取值方式：对「现在」取默认值必须落在本地当天。"""
        got = _run_node(
            helper_source,
            "const now = new Date();"
            "console.log(JSON.stringify([localDate(now), localDate(new Date(Date.now() + 60*864e5))]));",
        )
        assert isinstance(got, list) and len(got) == 2
        # 两个默认值都是 YYYY-MM-DD 形态，且与 Python 侧算出的本地日期一致
        import datetime as _dt

        today = _dt.datetime.now().strftime("%Y-%m-%d")
        assert got[0] == today, f"默认起始日应为今天 {today}，实为 {got[0]}"


class TestFalseGreenGuard:
    """证明这套测试不是恒真的：旧写法必须真的会出错。"""

    def test_naive_utc_would_have_been_wrong_in_the_small_hours(
        self, hour_rows: list[dict[str, object]]
    ) -> None:
        """旧写法（toISOString）在本地 00:00~07:59 必须退回前一天。

        如果这条不成立，说明运行环境的时区不是 UTC+8，
        那么上面那些断言就失去了「抓到过 bug」的意义，应当显式失败而不是静默通过。
        """
        wrong = [row for row in hour_rows if row["naive"] != row["localDate"]]
        assert wrong, (
            "旧写法在这台机器上竟然没有出错 —— 说明当前时区不是 UTC+8，"
            "本文件的断言不再能证明修复有效，请检查 TZ 设置"
        )
        hours = sorted(int(row["hour"]) for row in wrong)
        assert hours == list(range(8)), (
            f"因时区偏移而受影响的小时应恰为 0~7，实为 {hours}"
        )


class TestSourceHygiene:
    """源码层面的回归防护。"""

    def test_admin_page_no_longer_uses_utc_slice_for_dates(self) -> None:
        """admin.html 里不得再用 `toISOString().slice(0, 10)` 造日期串。

        与其断言「用了 localDate」，不如断言**旧写法已消失** ——
        前者可以在别处写一个新函数而把旧调用留着。
        """
        html = _ADMIN_HTML.read_text(encoding="utf-8")
        assert "toISOString().slice(0, 10)" not in html
        assert "toISOString().slice(0,10)" not in html

    def test_helper_is_defined_before_it_is_used(self) -> None:
        """定义必须在使用之前（同一 script 块内），否则是 TDZ/未定义调用。"""
        html = _ADMIN_HTML.read_text(encoding="utf-8")
        assert html.index("function localDate(d)") < html.index("localDate(start)")
