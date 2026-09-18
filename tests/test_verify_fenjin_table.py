"""`scripts/verify_fenjin_table.py` 的守卫测试。

为什么必须给它写守卫：这个脚本存在的**全部意义**是「在补表环节拦住静默降级」。
如果它自己也静默失效（判据写反、导入路径改坏、永远返回 0），
那它就是**看起来在守卫、实际什么都没守** —— 比没有它更糟，
因为人会因为"跑过了、绿的"而放行一张残缺的表。

因此这里两类断言都要有：
1. **该报的要报** —— 缺山 / 山内重复 / 整山空亡 / 缺在用流派的 key
2. **不该报的不报** —— 完整的表必须零问题（误报会训练人忽略脚本）

全部是纯函数与 `main()` 返回值层面的检查，毫秒级。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "verify_fenjin_table.py"

sys.path.insert(0, str(REPO / "packages" / "fortune-core"))

from fortune_core.constants import JIAZI_60  # noqa: E402
from fortune_core.mountain24 import MOUNTAIN_ORDER  # noqa: E402


@pytest.fixture(scope="module")
def verifier():
    """按文件路径加载脚本（`scripts/` 不是包，不能直接 import）。"""
    if not SCRIPT.exists():
        pytest.skip("校验脚本不存在")
    spec = importlib.util.spec_from_file_location("verify_fenjin_table", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # 必须先登记 sys.modules：脚本用了 @dataclass，而 dataclasses 解析注解时
    # 会按 cls.__module__ 反查 sys.modules —— 不登记就抛 AttributeError，
    # 且报错位置在 dataclasses 内部，很难看出是加载方式的问题。
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _full_table() -> dict[str, dict[str, list[str | None]]]:
    """二十四山齐备、无山内重复、无整山空亡 —— 应当**零问题**的表。"""
    return {
        "default": {
            name: [JIAZI_60[(i * 5 + k) % 60] for k in range(5)]
            for i, name in enumerate(MOUNTAIN_ORDER)
        }
    }


def _write(tmp_path: Path, name: str, data: object) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _messages(issues) -> str:
    return " | ".join(str(i) for i in issues)


# ==========================================================================
# 判据：该报的报
# ==========================================================================


class TestJudgeReports:
    def test_缺山要报并点名(self, verifier) -> None:
        table = _full_table()
        del table["default"]["艮"]
        _, issues = verifier.validate(table)
        text = _messages(issues)
        assert "缺 1 个山" in text, text
        assert "艮" in text, f"必须点名是哪个山，否则无从下手：{text}"
        assert "5 格" in text, "要换算成受影响格数，人才有量级感"

    def test_山内重复要报(self, verifier) -> None:
        table = _full_table()
        table["default"]["子"] = ["甲子", "甲子", "戊子", "庚子", "壬子"]
        _, issues = verifier.validate(table)
        text = _messages(issues)
        assert "子山 内干支重复" in text and "甲子" in text, text

    def test_整山全空亡要报(self, verifier) -> None:
        table = _full_table()
        table["default"]["辰"] = [None] * 5
        _, issues = verifier.validate(table)
        text = _messages(issues)
        assert "辰山 5 格全为 null" in text, text
        assert "WARN" in text, "这是可疑而非确定错误，不该判 FAIL"

    def test_缺在用流派的key要报(self, verifier) -> None:
        """表里没有任何当前开放流派的 key —— 分金会静默无干支。"""
        _, issues = verifier.validate({"some_unknown_school": {}})
        text = _messages(issues)
        assert "当前可用流派所需的 key 缺失" in text, text

    def test_判据等级只有WARN与FAIL(self, verifier) -> None:
        table = _full_table()
        del table["default"]["艮"]
        _, issues = verifier.validate(table)
        assert {i.level for i in issues} <= {"WARN", "FAIL"}
        assert all(i.level == "WARN" for i in issues), (
            "完整性问题一律 WARN —— 结构错由加载器判 FAIL，"
            "把'我觉得不对'升级成 FAIL 会误报"
        )


# ==========================================================================
# 判据：不该报的不报（防误报 —— 误报会训练人忽略脚本）
# ==========================================================================


class TestJudgeStaysSilent:
    def test_完整表零问题(self, verifier) -> None:
        reports, issues = verifier.validate(_full_table())
        assert issues == [], f"完整表不该有任何问题，实际：{_messages(issues)}"
        assert len(reports) == 1

    def test_未开放流派缺key不报(self, verifier) -> None:
        """`sanhe` / `sanyuan` 在 schools.py 里声明但**未开放**。

        缺它们是预期状态。若一并告警，每次跑都有一条恒定噪音 ——
        而恒定的告警等于没有告警。
        """
        _, issues = verifier.validate(_full_table())
        assert not any("sanhe" in str(i) or "sanyuan" in str(i) for i in issues), _messages(issues)

    def test_null不算重复也不算缺格(self, verifier) -> None:
        """`null` 是合法的「该流派下空亡」，不是漏填。"""
        table = _full_table()
        table["default"]["子"] = [None, "丙子", None, "庚子", None]
        _, issues = verifier.validate(table)
        assert issues == [], f"3 个 null 是合法排法，不该报：{_messages(issues)}"

    def test_报告数值正确(self, verifier) -> None:
        table = _full_table()
        table["default"]["子"] = [None, None, "戊子", "庚子", "壬子"]
        reports, _ = verifier.validate(table)
        (r,) = reports
        assert r.school == "default"
        assert r.mountains == len(MOUNTAIN_ORDER)
        assert r.cells == len(MOUNTAIN_ORDER) * 5
        assert r.filled == r.cells - 2
        assert r.empty == 2


# ==========================================================================
# main()：退出码是脚本唯一的对外信号
# ==========================================================================


class TestMainExitCodes:
    def _run(self, verifier, monkeypatch, capsys, *argv: str) -> tuple[int, str]:
        monkeypatch.setattr(sys, "argv", ["verify_fenjin_table.py", *argv])
        code = verifier.main()
        return code, capsys.readouterr().out

    def test_表不存在算通过(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        """「表还没提供」是已声明的状态，不是错误 —— 否则每次体检都红。"""
        code, out = self._run(verifier, monkeypatch, capsys, "--table", str(tmp_path / "nope.json"))
        assert code == 0, out
        assert "尚未提供" in out and "0" in out

    def test_表不存在_require时失败(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        code, out = self._run(
            verifier, monkeypatch, capsys, "--table", str(tmp_path / "nope.json"), "--require"
        )
        assert code == 1, out

    def test_表不存在时打印表格式(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        """给准备补表的人看的 —— 这是他第一次跑这个脚本时的唯一上下文。"""
        _, out = self._run(verifier, monkeypatch, capsys, "--table", str(tmp_path / "nope.json"))
        assert '"子"' in out and "null" in out, "应给出可照抄的表格式示例"

    def test_完整表通过(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        p = _write(tmp_path, "ok.json", _full_table())
        code, out = self._run(verifier, monkeypatch, capsys, "--table", str(p))
        assert code == 0, out
        assert "[OK]" in out
        assert "不判断" in out, "必须自我声明边界：排法对错不归脚本管"

    def test_残缺表默认仍通过但报告WARN(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        table = _full_table()
        del table["default"]["艮"]
        p = _write(tmp_path, "partial.json", table)
        code, out = self._run(verifier, monkeypatch, capsys, "--table", str(p))
        assert code == 0, "WARN 默认不阻断（避免误报阻断流水线）"
        assert "缺 1 个山" in out

    def test_残缺表_strict时失败(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        table = _full_table()
        del table["default"]["艮"]
        p = _write(tmp_path, "partial.json", table)
        code, _ = self._run(verifier, monkeypatch, capsys, "--table", str(p), "--strict")
        assert code == 1

    def test_结构错失败并给修复指引(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        p = _write(tmp_path, "broken.json", {"default": {"子": ["甲子", "丙子", "戊子"]}})
        code, out = self._run(verifier, monkeypatch, capsys, "--table", str(p))
        assert code == 1, out
        assert "应有 5 格，实为 3" in out, f"必须带得上具体位置：{out}"
        assert "修复指引" in out
        assert "重启" in out, "表有缓存，不提这一条人会以为改完就生效"

    def test_JSON语法错被单独识别(self, verifier, tmp_path, monkeypatch, capsys) -> None:
        p = tmp_path / "syntax.json"
        p.write_text('{"default": {"子": ["甲子"],}}', encoding="utf-8")
        code, out = self._run(verifier, monkeypatch, capsys, "--table", str(p))
        assert code == 1
        assert "JSON 解析失败" in out, out


# ==========================================================================
# 可独立运行 —— 脚本必须能直接跑，不能依赖调用方设 PYTHONPATH
# ==========================================================================


class TestStandalone:
    def test_不带PYTHONPATH也能跑起来(self, tmp_path: Path) -> None:
        """脚本自己注入 `packages/fortune-core`。

        这一条是**真跑子进程**：`main()` 里的导入若失败，
        脚本会以 ImportError 崩掉 —— 而它在 pytest 里可能因 conftest
        已经注入了路径而看不出问题。
        """
        p = _write(tmp_path, "ok.json", _full_table())
        env = {k: v for k, v in __import__("os").environ.items() if k != "PYTHONPATH"}
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--table", str(p)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
        )
        assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
        assert "[OK]" in r.stdout

    def test_对仓库默认表跑一遍不报错(self) -> None:
        r = subprocess.run(
            [sys.executable, str(SCRIPT)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"


__all__: list[str] = []
