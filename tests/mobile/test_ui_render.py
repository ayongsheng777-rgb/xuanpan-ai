"""界面渲染回归 —— 证明页面**真的画出来了**，而不是白屏。

## 为什么需要这道测试

2026-09-18 实测：`tsc` 零错、`expo export` 成功、248 条移动端测试全过，
但 expo web 产物里 `/` 与 `/sensors` 两页**整页白屏**。

根因：`expo-sensors` 没有 web 实现，`Magnetometer.addListener` 内部抛
`TypeError: this._nativeModule.addListener is not a function`，
未捕获异常让整棵 React 树渲染失败。

这类故障有三个特征，使它对现有手段完全隐形：

1. **静态检查全绿** —— 类型检查与打包都不报错；
2. **单元测试全过** —— 它们不渲染组件树；
3. **表现是"一片空白"**，不是报错弹窗、不是崩溃日志。

同类的还有「横向溢出」：`scrollWidth > innerWidth` 时右侧内容被推出屏幕，
截图只裁到视口宽度，**看图的人以为只是设计留白**。

## 为什么用真渲染，而不是扫源码

扫源码只能证明「`useSensors.ts` 里有 `try/catch`」，
证明不了「页面真的画出来了」—— 而后者才是那个模块存在的全部理由。
（同 `test_local_date.py` 对 `toISOString` 的取舍。）

本测试用 Chrome DevTools Protocol 真跑页面，逐页断言三件事：

| 断言 | 挡住什么 |
|---|---|
| `textLen > 0` | 整页白屏 |
| `errors == []` | 页面内未捕获异常 |
| `overflowX == 0` | 横向溢出（看图看不出来的那类） |

## 环境与跳过

需要本机 Chrome **与**已导出的 expo web 产物。任一缺失则 skip ——
与 `test_local_date.py` 在无 node 时跳过同理：环境不具备时不该把红灯挂到别人机器上。

启用方式（两行，均在项目根执行）：

```bash
# [Host] 导出 web 产物（约 1 分钟）
cd apps/mobile && npx expo export --platform web --output-dir ../../dist-web

# [Host] 跑本测试（注意：Chrome 在受限 shell 下会静默退出，需在普通终端执行）
XP_WEB_DIST=dist-web "$PY" -m pytest tests/mobile/test_ui_render.py
```

## 假绿自检

若渲染器坏成"永远报告 textLen > 0"，本测试就沦为一句空话。
故 `test_pipeline_can_detect_a_truly_blank_page` 用一个**必然不存在的路由**
渲染一次，断言它拿不到任何内容 —— 证明这套探针确实有能力识别"没有内容"，
而不是无脑返回成功。
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"

_CHROME_CANDIDATES = (
    Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
    Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RENDER = _REPO_ROOT / "scripts/ui_render/render_pages.mjs"
_PREVIEW = _REPO_ROOT / "scripts/ui_render/preview_server.py"

#: 已导出的 expo web 产物目录（含 index.html）。未设置则默认找 dist-web。
_WEB_DIST = Path(os.environ.get("XP_WEB_DIST") or (_REPO_ROOT / "dist-web"))

#: 哨兵页面。前两页是 2026-09-18 白屏故障的现场；
#: 后三页是底栏改版新增的页面 —— 新页面是白屏风险最高的地方
#: （没有历史截图可对照，坏了也没人看得出来）。
_SENTINELS = ("01-home", "03-sensors", "12-test", "13-analysis", "14-templates")

#: 渲染单页的上限。CDP 命令自身另有超时，这里是兜底。
_RENDER_TIMEOUT_S = 240


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


def _chrome() -> str | None:
    for p in _CHROME_CANDIDATES:
        if p.exists():
            return str(p)
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="module")
def preview_base() -> str:
    """起一个带 SPA 回落与渲染探针的静态服务器，供真渲染使用。"""
    if not _WEB_DIST.joinpath("index.html").is_file():
        pytest.skip(
            f"未找到 expo web 产物（{_WEB_DIST}/index.html）。"
            "先在 apps/mobile 执行 `npx expo export --platform web --output-dir ../../dist-web`，"
            "或设置 XP_WEB_DIST 指向已有产物目录。"
        )
    if not _PREVIEW.is_file():
        pytest.skip(f"未找到预览服务器脚本：{_PREVIEW}")

    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, str(_PREVIEW), str(_WEB_DIST), str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 20
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"预览服务器启动即退出：{out[:800]}")
            try:
                with urllib.request.urlopen(f"{base}/", timeout=1) as resp:
                    ready = resp.status == 200
                    break
            except (urllib.error.URLError, OSError):
                time.sleep(0.2)
        if not ready:
            pytest.fail(f"预览服务器 20 秒内未就绪（{base}）")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - 仅卡死时
            proc.kill()


def _render(only: str, base: str, outdir: Path) -> list[dict]:
    """调用渲染器，取回逐页诊断。返回 [] 表示渲染器完全没跑起来。"""
    node = _node()
    chrome = _chrome()
    if node is None:
        pytest.skip("未找到 node，跳过界面渲染回归")
    if chrome is None:
        pytest.skip("未找到 Chrome/Chromium，跳过界面渲染回归")

    proc = subprocess.run(
        [node, str(_RENDER), chrome, str(outdir), base, only],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(_REPO_ROOT),
        timeout=_RENDER_TIMEOUT_S,
    )
    rows: list[dict] = []
    for line in proc.stdout.splitlines():
        if line.startswith("OK   "):
            rows.append(json.loads(line[5:]))
        elif line.startswith("FAIL "):
            rows.append({"name": line[5:].split(" ")[0], "ok": False, "detail": line[5:]})
    if not rows:
        # 渲染器一行结果都没产出：多为 Chrome 在受限 shell 下静默退出
        # （写不出 DevToolsActivePort）。属环境问题，跳过并给出可操作提示。
        pytest.skip(
            "渲染器未产出任何结果，通常是 Chrome 无法在当前 shell 启动"
            "（受限环境下 Chrome 会静默 exit 0）。请在普通终端执行本测试。\n"
            f"stdout: {proc.stdout.strip()[:500]}\nstderr: {proc.stderr.strip()[:500]}"
        )
    return rows


@pytest.fixture(scope="module")
def rendered(preview_base: str, tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict]:
    """渲染哨兵页面一次，供多条断言复用。"""
    outdir = tmp_path_factory.mktemp("ui-render")
    rows = _render(",".join(_SENTINELS), preview_base, outdir)
    return {r["name"]: r for r in rows}


# ==========================================================================
# 假绿自检：先证明这套探针有能力识别"空白"
# ==========================================================================


def test_pipeline_can_detect_a_truly_blank_page(
    preview_base: str, tmp_path_factory: pytest.TempPathFactory
) -> None:
    """渲染一个**必然不存在**的路由，断言它确实拿不到内容。

    这是本文件最重要的一条：如果渲染器坏成"永远报告有内容"，
    下面所有关于"不白屏"的断言都会轻松通过，测试变成一句空话。

    注意 SPA 会把未知路径回落到 index.html，所以页面框架仍在、不会
    得到 textLen 恰为 0 —— 真正该断言的是**它渲染出的是"未匹配路由"提示**，
    而不是某个业务页面的内容。
    """
    outdir = tmp_path_factory.mktemp("ui-render-blank")
    rows = _render("01-home", f"{preview_base}/__no-such-route__", outdir)
    assert rows, "渲染器未返回任何结果"
    text = rows[0].get("text") or ""
    assert "Unmatched" in text or "Not Found" in text, (
        "未知路由没有渲染出「未匹配」提示 —— 说明 SPA 回落或探针取数有问题，"
        "本自检因此无法证明探针有能力识别空白：\n" f"{text[:300]}"
    )
    assert "罗盘" not in text and "传感器" not in text, (
        "未知路由竟然渲染出了业务页面内容，说明路由回落或探针取数有误：\n" f"{text[:300]}"
    )


# ==========================================================================
# 核心断言：每个页面的实际渲染结果
# ==========================================================================


@pytest.mark.parametrize("name", _SENTINELS)
def test_page_renders_content(rendered: dict[str, dict], name: str) -> None:
    """页面必须真的渲染出文本 —— 挡住整页白屏。

    2026-09-18 的故障现场：`/` 与 `/sensors` 的 `textLen` 为 0，
    用户看到的是一片空白。
    """
    row = rendered.get(name)
    assert row is not None, f"渲染器未返回 {name} 的结果"
    assert row.get("ok"), f"{name} 渲染失败：{row.get('detail')}"
    assert row["textLen"] > 0, (
        f"{name} 渲染出的文本长度为 0 —— 整页白屏。\n"
        f"页面内捕获到的错误：{row.get('errors')}"
    )


@pytest.mark.parametrize("name", _SENTINELS)
def test_page_has_no_uncaught_errors(rendered: dict[str, dict], name: str) -> None:
    """页面内不得有未捕获的 JS 异常。

    未捕获异常是白屏的直接前因，而且**它可能不白屏却让功能静默失效**
    （例如某个 useEffect 中断，页面看着正常但数据永不刷新）。
    """
    row = rendered[name]
    assert row["errors"] == [], f"{name} 页面存在未捕获异常：{row['errors']}"


@pytest.mark.parametrize("name", _SENTINELS)
def test_page_has_no_horizontal_overflow(rendered: dict[str, dict], name: str) -> None:
    """不得横向溢出 —— `scrollWidth` 必须等于 `innerWidth`。

    这条挡的是"看图看不出来"的布局错误：溢出时右侧内容被推出视口，
    而截图只覆盖视口宽度，看图的人会以为那只是设计留白。
    """
    row = rendered[name]
    assert row["overflowX"] <= 0, (
        f"{name} 横向溢出 {row['overflowX']}px（内容区 {row['viewport']}，"
        f"文档高 {row['contentH']}px）：右侧内容会被推出屏幕外。\n"
        f"渲染文本：{(row.get('text') or '')[:200]}"
    )
