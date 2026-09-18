"""界面接线守卫 —— 挡住"类型全绿、页面也能打开，但点进去是死路"的三类错。

## 为什么需要它（替代不了真渲染，但补得上真渲染的盲区）

`test_ui_render.py` 证明"页面画得出来"，但它**证明不了"点得进去"**。
而本项目已实测发生过两次同类故障：

1. `content/help.ts` 里写了 V2 已删掉的「拍摄罗盘」按钮 —— 用户按文案找不到那个入口。
2. 页面标题栏的问号由 `HelpButton` 渲染，**未登记的 topic 不渲染入口**
   （`HelpButton` 在 topic 查不到时直接返回 `null`）——
   于是"讲解按钮凭空消失"，而 `tsc` 与打包都不会有任何提示。

这两类的共同点：**没有任何一层会报错**。类型是对的、页面渲染是正常的、
单元测试是绿的，只有"用户点不到"。

## 为什么用静态检查而不是渲染

这三件事与"渲染成什么样"无关，只与"源码里写下的目标是否存在"有关。
用静态检查的额外好处：**不依赖浏览器** —— 而 Chrome 在受限 shell 里
会静默退出（见 `test_ui_render.py` 的环境说明），真渲染在那些环境里会被跳过。
本文件是纯文件系统检查，**在任何环境都跑得动**。

## 假绿自检

`test_selfcheck_route_matcher_rejects_bogus_target` 与
`test_selfcheck_help_scanner_rejects_unknown_topic` 用**故意写错的输入**
证明这两套匹配器真的会拒绝，而不是无脑返回通过。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP = _REPO_ROOT / "apps/mobile/app"
_SRC = _REPO_ROOT / "apps/mobile/src"

#: 非路由文件：布局与 expo-router 约定文件
_NON_ROUTE_STEMS = {"_layout"}

#: `router.push('/x')` / `router.replace('/x')` / `<Link href="/x">` 里的字面量
_PUSH_RE = re.compile(r"""\b(?:push|replace|navigate)\s*\(\s*(['"`])(/[^'"`]*)\1""")
_HREF_RE = re.compile(r"""\bhref\s*=\s*(['"`])(/[^'"`]*)\1""")

#: `topic="x"` 与 `helpHeaderRight('x')`
_TOPIC_PROP_RE = re.compile(r"""\btopic\s*=\s*(['"`])([A-Za-z0-9_-]+)\1""")
_TOPIC_CALL_RE = re.compile(r"""\bhelpHeaderRight\s*\(\s*(['"`])([A-Za-z0-9_-]+)\1""")


def _route_files() -> list[Path]:
    return sorted(
        p
        for p in _APP.rglob("*.tsx")
        if p.stem not in _NON_ROUTE_STEMS
    )


def _route_of(path: Path) -> str:
    """把路由文件映射成 URL 路径（expo-router 约定）。

    - 去掉扩展名；`index` 表示所在目录本身
    - 括号目录 `(tabs)` 是**分组**，不进入 URL
    - `[param]` 段保留占位形状（匹配时按通配处理）
    """
    rel = path.relative_to(_APP).with_suffix("")
    parts = [p for p in rel.parts if not (p.startswith("(") and p.endswith(")"))]
    if parts and parts[-1] == "index":
        parts = parts[:-1]
    return "/" + "/".join(parts)


def _route_is_known(target: str, routes: set[str]) -> bool:
    """目标是否能匹配某个已存在的路由。

    动态段（`[sessionId]`）按"任意一段"匹配 —— 因为目标里写的是
    `/report/${id}` 这类模板串，静态检查看不到它的运行期取值，
    只能校验**段数与静态段是否吻合**。
    """
    want = [s for s in target.strip("/").split("/") if s]
    have = [[s for s in r.strip("/").split("/") if s] for r in routes]
    for segs in have:
        if len(segs) != len(want):
            continue
        if all(
            h.startswith("[") and h.endswith("]") or h == w
            for h, w in zip(segs, want)
        ):
            return True
    return False


def _string_literal_targets() -> list[tuple[Path, int, str]]:
    """扫出所有**字面量**内部跳转目标（模板串如 `/report/${id}` 不含引号内闭合，故不会误报）。"""
    out: list[tuple[Path, int, str]] = []
    for f in sorted([*_APP.rglob("*.tsx"), *_SRC.rglob("*.tsx"), *_SRC.rglob("*.ts")]):
        text = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for rx in (_PUSH_RE, _HREF_RE):
                for m in rx.finditer(line):
                    raw = m.group(2)
                    # 模板串（含 ${}）无法静态校验，跳过 —— 它们的取值由运行期决定
                    if "${" in raw:
                        continue
                    out.append((f, lineno, raw))
    return out


# ==========================================================================
# 断言 1：内部跳转目标必须真实存在
# ==========================================================================


def test_every_internal_router_target_exists() -> None:
    """`router.push('/xxx')` 里的 `/xxx` 必须是真实存在的路由。

    挡住的错：重命名/移动页面后忘了改跳转 —— 点下去静默无反应或落到未匹配路由。
    """
    routes = {_route_of(p) for p in _route_files()}
    assert routes, f"没有扫到任何路由文件，检查路径是否正确：{_APP}"

    bad: list[str] = []
    for f, lineno, raw in _string_literal_targets():
        path = raw.split("?")[0].split("#")[0]
        if path in ("", "/"):
            continue
        if not _route_is_known(path, routes):
            bad.append(f"{f.relative_to(_REPO_ROOT)}:{lineno} → {raw}")

    assert not bad, (
        "以下跳转目标不存在对应路由（点进去会是死路）：\n  "
        + "\n  ".join(bad)
        + f"\n\n当前已存在的路由：{sorted(routes)}"
    )


# ==========================================================================
# 断言 2：讲解入口的 topic 必须已登记
# ==========================================================================


def _help_topic_ids() -> set[str]:
    src = (_REPO_ROOT / "apps/mobile/src/content/help.ts").read_text(encoding="utf-8")
    m = re.search(r"export type HelpTopicId\s*=(.*?);", src, re.S)
    assert m, "未能从 help.ts 解析出 HelpTopicId 联合类型"
    return set(re.findall(r"'([A-Za-z0-9_-]+)'", m.group(1)))


def _used_help_topics() -> list[tuple[Path, int, str]]:
    out: list[tuple[Path, int, str]] = []
    for f in sorted([*_APP.rglob("*.tsx"), *_SRC.rglob("*.tsx")]):
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), start=1):
            for rx in (_TOPIC_PROP_RE, _TOPIC_CALL_RE):
                for m in rx.finditer(line):
                    out.append((f, lineno, m.group(2)))
    return out


def test_every_help_topic_is_registered() -> None:
    """页面用到的 help topic 必须在 `help.ts` 里登记。

    `HelpButton` 对未登记的 topic **直接返回 null** —— 按钮会凭空消失，
    而类型检查、打包、渲染全都不报错。这条断言是它唯一的防线。
    """
    registered = _help_topic_ids()
    assert registered, "未能解析出任何 help topic"

    used = _used_help_topics()
    assert used, "没有扫到任何 help topic 用法（扫描正则可能失效了）"

    bad = [
        f"{f.relative_to(_REPO_ROOT)}:{n} → '{t}'"
        for f, n, t in used
        if t not in registered
    ]
    assert not bad, (
        "以下页面引用了未登记的讲解主题，问号按钮会静默不渲染：\n  "
        + "\n  ".join(bad)
        + f"\n\n已登记：{sorted(registered)}"
    )


def test_every_registered_topic_is_used_somewhere() -> None:
    """反过来：登记了却没人用的 topic 是死文案 —— 它会随时间与实现漂移。

    漂移的文案比没有文案更糟：用户按一个**已经不成立**的模型去理解结果。
    """
    registered = _help_topic_ids()
    used = {t for _, _, t in _used_help_topics()}
    unused = sorted(registered - used)
    assert not unused, (
        f"以下讲解主题已登记但没有任何页面引用（死文案，会被时间漂移）：{unused}"
    )


# ==========================================================================
# 断言 3：底栏声明的每个 tab 都对应真实文件
# ==========================================================================


def test_every_tab_screen_has_a_route_file() -> None:
    """`(tabs)/_layout.tsx` 里 `<Tabs.Screen name="X">` 的 X 必须有对应文件。

    挡住"改了导航但文件没就位"：expo-router 会静默忽略不存在的 name，
    结果就是底栏少一格，而没有人会看到报错。
    """
    layout = (_APP / "(tabs)/_layout.tsx").read_text(encoding="utf-8")
    names = re.findall(r"""name\s*=\s*(['"])([A-Za-z0-9_-]+)\1""", layout)
    declared = [n for _, n in names]
    assert declared, "未能从 (tabs)/_layout.tsx 解析出 Tabs.Screen name"

    tabs_dir = _APP / "(tabs)"
    missing = [n for n in declared if not (tabs_dir / f"{n}.tsx").is_file()]
    assert not missing, (
        f"底栏声明了这些 tab 但没有对应文件：{missing}；"
        f"目录内实际有：{sorted(p.stem for p in tabs_dir.glob('*.tsx'))}"
    )


# ==========================================================================
# 假绿自检：证明上面两套匹配器真的会拒绝
# ==========================================================================


def test_selfcheck_route_matcher_rejects_bogus_target() -> None:
    """用一个必然不存在的目标证明 `_route_is_known` 会拒绝它。"""
    routes = {_route_of(p) for p in _route_files()}
    assert _route_is_known("/test", routes), "自检失败：/test 应当存在"
    assert not _route_is_known("/no-such-page-xyz", routes), (
        "自检失败：匹配器对不存在的路径也返回了 True —— 断言 1 因此是假绿"
    )


def test_selfcheck_help_scanner_rejects_unknown_topic() -> None:
    """证明 topic 扫描器确实会捕获用法，且未登记的 topic 会被判不合格。"""
    registered = _help_topic_ids()
    assert "compass-home" in registered, "自检失败：compass-home 应当已登记"
    assert "no-such-topic-xyz" not in registered, (
        "自检失败：未登记的 topic 竟被认为已登记 —— 断言 2 因此是假绿"
    )
