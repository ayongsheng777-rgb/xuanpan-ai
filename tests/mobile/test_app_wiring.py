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
#: JSX 属性写法 `<Link href="/x">`
_HREF_RE = re.compile(r"""\bhref\s*=\s*(['"`])(/[^'"`]*)\1""")
#: 对象属性写法 `{ href: '/x' }` —— 用的是冒号而不是等号。
#: 漏掉这一种会让"数据表里声明的跳转"整批逃过校验（本文件就是这么漏掉了
#: 测盘页五张来源卡的 href）。
_HREF_PROP_RE = re.compile(r"""\bhref\s*:\s*(['"`])(/[^'"`]*)\1""")

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
            for rx in (_PUSH_RE, _HREF_RE, _HREF_PROP_RE):
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
# 断言 4：推过去的查询参数，目标页必须真的读
# ==========================================================================

#: 对象形式：`router.push({ pathname: '/x', params: { a: ..., b: ... } })`
_OBJ_PUSH_RE = re.compile(
    r"""pathname\s*:\s*(['"])(/[^'"]*)\1[\s\S]{0,400}?params\s*:\s*\{([\s\S]{0,400}?)\}""",
    re.S,
)
_PARAM_KEY_RE = re.compile(r"""(?:^|[,{\s])([A-Za-z_][A-Za-z0-9_]*)\s*:""")


def _pushed_params() -> list[tuple[Path, int, str, str]]:
    """扫出（文件, 行号, 目标路径, 参数名）。

    只认**字面量**：对象形式的 `pathname` + `params` 键，以及字符串形式里的
    字面量查询串。手拼的模板串（`'/x?' + parts.join('&')`）静态看不见 ——
    所以 templates.tsx 特意改成了对象形式（见该文件注释）。
    """
    out: list[tuple[Path, int, str, str]] = []
    for f in sorted([*_APP.rglob("*.tsx"), *_SRC.rglob("*.tsx"), *_SRC.rglob("*.ts")]):
        text = f.read_text(encoding="utf-8")
        for m in _OBJ_PUSH_RE.finditer(text):
            path, block = m.group(2), m.group(3)
            lineno = text[: m.start()].count("\n") + 1
            for key in _PARAM_KEY_RE.findall(block):
                out.append((f, lineno, path, key))
        # 字符串形式里带字面量查询串的
        for _, lineno, raw in _string_literal_targets():
            if "?" not in raw:
                continue
            path, _, query = raw.partition("?")
            for pair in query.split("&"):
                key = pair.split("=")[0].strip()
                if key:
                    out.append((f, lineno, path, key))
    return out


def _param_reading_region(src: str) -> str | None:
    """取页面"读参数"的那段源码。

    优先取 `useLocalSearchParams<{...}>()` 的泛型块；没有泛型时退化为
    调用点后 300 字符（覆盖 `const { a, b } = useLocalSearchParams()` 写法）。
    返回 None 表示该文件根本不读任何参数。

    ⚠️ 必须跳过 **import 语句**里的那个名字 —— `import { useLocalSearchParams }`
    是文件里第一次出现它的地方，直接取首个匹配会拿到一行 import，
    于是所有参数都判成"没解出"（本匹配器首版就是这么错的）。
    """
    for m in re.finditer(r"\buse(?:Local|Global)SearchParams\b", src):
        tail = src[m.end() :]
        nxt = tail.lstrip()[:1]
        if nxt not in ("<", "("):
            continue  # import 语句 / 类型引用，不是调用点
        generic = re.match(r"\s*<\s*([\s\S]{0,600}?)\s*>\s*\(", tail)
        if generic:
            return generic.group(1)
        return tail[:300]
    return None


def _route_file_of(target: str) -> Path | None:
    want = [s for s in target.strip("/").split("/") if s]
    for p in _route_files():
        segs = [s for s in _route_of(p).strip("/").split("/") if s]
        if len(segs) != len(want):
            continue
        if all(h.startswith("[") and h.endswith("]") or h == w for h, w in zip(segs, want)):
            return p
    return None


def test_pushed_query_params_are_read_by_target_page() -> None:
    """推过去的参数，目标页必须真的读。

    挡住的错（本项目刚发生过）：`templates.tsx` 推了
    `template/style/sitting/degree`，而 `adjust.tsx` 一个字都没读 ——
    用户点模板落到手动调节页，什么都没生效，界面看起来却完全正常。

    这类错**没有任何一层会报错**：路由对、参数名也没拼错，只是没人消费。
    """
    pushed = _pushed_params()
    assert pushed, "没有扫到任何带参数的跳转（扫描正则可能失效了）"

    # 已知的关键参数必须在扫描结果里 —— 否则某天正则失效，本测试就变成空跑。
    # 这三条都是真实存在的接线，是"扫描器还活着"的锚点。
    keys = {(path, key) for _, _, path, key in pushed}
    for expect in (("/adjust", "template"), ("/calibrate", "photo"), ("/scan", "entry")):
        assert expect in keys, (
            f"扫描结果缺少 {expect} —— 参数扫描器可能已失效，本测试会沦为假绿。"
            f"当前扫到：{sorted(keys)}"
        )

    bad: list[str] = []
    for f, lineno, path, key in pushed:
        rf = _route_file_of(path)
        if rf is None:
            bad.append(f"{f.relative_to(_REPO_ROOT)}:{lineno} → {path}（路由不存在）")
            continue
        region = _param_reading_region(rf.read_text(encoding="utf-8"))
        if region is None:
            bad.append(
                f"{f.relative_to(_REPO_ROOT)}:{lineno} 推了 '{key}' 给 {path}，"
                f"但 {rf.relative_to(_REPO_ROOT)} 没有调用 useLocalSearchParams"
            )
        elif key not in region:
            bad.append(
                f"{f.relative_to(_REPO_ROOT)}:{lineno} 推了 '{key}' 给 {path}，"
                f"但 {rf.relative_to(_REPO_ROOT)} 读参数时没有解出 '{key}'"
            )

    assert not bad, "以下参数在目标页没有落地（推了等于没推）：\n  " + "\n  ".join(
        sorted(set(bad))
    )


# ==========================================================================
# 断言 5：`degree` 参数一律以「坐山角」为准，不得来自向山候选
# ==========================================================================

_DEGREE_KEY_RE = re.compile(r"""\bdegree\s*:\s*""")


def _degree_expressions_in(src: str) -> list[tuple[int, str]]:
    """从一段源码里抽出所有 `degree: <表达式>` —— 返回 (行号, 表达式)。

    为什么不能按行取：本项目这一处本来就是多行嵌套调用
    （`String(result.mountain_candidates[0]?.angle ?? '')`），
    按行取只会拿到半截 —— 于是"表达式里没有 direction_candidates"
    会**必然成立**，断言沦为假绿。故这里按括号配平取到表达式结尾。

    做成**纯函数**（而不是直接遍历目录）是为了让自检拿一段字符串来验证，
    不必往 `apps/mobile/app/` 里写临时文件 —— 往被测目录里写文件会让
    自检与执行顺序、残留文件耦合，属于"测试自己制造假故障"。
    """
    out: list[tuple[int, str]] = []
    for m in _DEGREE_KEY_RE.finditer(src):
        i = m.end()
        depth = 0
        j = i
        while j < len(src):
            ch = src[j]
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and ch in ",\n":
                break
            j += 1
        expr = src[i:j].strip()
        if expr:
            out.append((src.count("\n", 0, i) + 1, expr))
    return out


def _degree_param_expressions() -> list[tuple[Path, int, str]]:
    """扫全部页面，把 `degree:` 表达式连同所在文件取出来。"""
    out: list[tuple[Path, int, str]] = []
    for f in sorted(_APP.rglob("*.tsx")):
        for lineno, expr in _degree_expressions_in(f.read_text(encoding="utf-8")):
            out.append((f, lineno, expr))
    return out


def test_degree_param_never_comes_from_the_facing_candidate() -> None:
    """全链路的 `degree` 是**坐山角**，任何一个 `degree:` 都不得引用向山候选。

    口径由一个地方定，且在内核里（RULE-001）：

        calculate_orientation(degree=180.24) → sitting='午', facing='子'

    识别层也把两个列表分得很清楚：`mountain_candidates` = 坐山候选、
    `direction_candidates` = 向山候选（见 `services/vision/.../models.py`）。

    挡住的错（本项目刚发生过）：`scan.tsx` 把 `direction_candidates[0].angle`
    作为 `degree` 推给校准页 —— 一路带到确认页、再原样提交给后端。
    灌进去的实测角比坐山差 180°，于是：
      · 用户按提示确认坐山 → 后端以 `mountain_at(degree) != sitting` 报冲突（可见）；
      · 用户改成选向山   → **静默存下一条坐向翻转的记录**（不可见，最坏的那种）。
    """
    exprs = _degree_param_expressions()
    assert exprs, "没有扫到任何 `degree:` 表达式（抽取器可能已失效）"

    # 锚点：抽取器必须真的看得见那一处多行嵌套调用，否则"没扫到"就变成假绿
    scan_exprs = [e for f, _, e in exprs if f.name == "scan.tsx"]
    assert scan_exprs, "抽取器没有扫到 scan.tsx 里的 degree 表达式"
    assert any("mountain_candidates" in e for e in scan_exprs), (
        f"抽取到的 scan.tsx 表达式不完整（可能是按行截断了）：{scan_exprs}"
    )

    bad = [
        f"{f.relative_to(_REPO_ROOT)}:{lineno} → {expr}"
        for f, lineno, expr in exprs
        if "direction_candidates" in expr
    ]
    assert not bad, (
        "以下 `degree` 取自**向山**候选 —— 与内核口径（degree 落在坐山）相差 180°：\n  "
        + "\n  ".join(bad)
    )


def test_selfcheck_degree_extractor_would_flag_a_facing_source() -> None:
    """用一个必然该判不合格的片段，证明上面的抽取器 + 判据真的会拒绝。"""
    snippet = """
      params: {
        session: x,
        degree: String(
          result.direction_candidates[0]?.angle ?? '',
        ),
      },
    """
    exprs = _degree_expressions_in(snippet)
    assert len(exprs) == 1, f"自检失败：抽取器取到 {len(exprs)} 个表达式，应为 1：{exprs}"
    assert "direction_candidates" in exprs[0][1], (
        f"自检失败：抽取器没能取出跨行表达式（取到 {exprs[0][1]!r}）—— 断言 5 因此是假绿"
    )

    # 再证一次"判据真的会把它标红"，而不是只靠人眼看抽取结果
    flagged = [e for _, e in exprs if "direction_candidates" in e]
    assert flagged, "自检失败：含 direction_candidates 的表达式没有被判据捕获"


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
