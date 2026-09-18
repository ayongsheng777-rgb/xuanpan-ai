"""界面文案必须是纯文本 —— RN 的 `<Text>` 不做 Markdown 解析。

## 为什么需要这道测试

`apps/mobile` 的文案里混进了 Markdown 强调标记（`**这样**`），而 RN 的
`<Text>` 是把 children 当**纯文本**渲染的，不做任何 Markdown 解析 ——
结果是用户在界面上**真的看到两个星号**：

    把照片里罗盘的**外圈**对到矢量盘的外缘

这不是风格问题，是用户在读的句子被符号切开了；而且三处防线全部漏掉它：

- `tsc` 只查类型，字符串内容是什么它不管
- 单元测试不渲染界面，看不到字符
- 离线快照（`test_ui_render.py`）只回传**布局诊断**（溢出量 / JS 错误），
  不核对正文里有没有不该出现的字符

## 同一类缺陷已经在这个仓库发生过一次

管理台（`static/admin.html`）踩过完全一样的坑，修法见
`tests/api/test_admin_config.py::TestCopyIsPlainText` —— 该文件的注释写着：

    实测（2026-09-18，用 CDP 真渲染管理台「配置」视图）：写进 `description`
    的强调标记会原样显示成星号 —— 面板是把说明当纯文本塞进 DOM 的

**当时只扫了管理台，没有扫 App** —— 于是 App 侧的同款标记一直留着，
其中 `src/content/help.ts` 是最大的一处（每页右上角「讲解」抽屉的全部正文）。

## 判据

界面文案的载体只有两种：**字符串字面量** 与 **JSX 文本节点**。
两者都不做 Markdown 解析，所以只要在这些位置出现 `**` 就是缺陷。

注释里的 `**` 是**合法的**（本仓库大量用 `**强调**` 写中文注释），
所以扫描前必须先剥掉 `/* */` 与 `//` —— 剥注释的扫描器本身也有测试守着
（`test_scanner_ignores_comments_but_catches_text`），避免它退化成永远通过。
"""

from __future__ import annotations

import pathlib
import re

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_MOBILE = _ROOT / "apps" / "mobile"

_SCAN_DIRS = (_MOBILE / "app", _MOBILE / "src")
_SUFFIXES = (".ts", ".tsx")


def _strip_comments(src: str) -> str:
    """把 `/* */` 与 `//` 注释替换成等长空白，**保留换行**（行号才对得上）。

    引号感知：字符串里的 `//`（如 `'http://x'`）不能被当成行注释起点，
    所以扫描时要在单引号 / 双引号 / 模板字符串里"穿过"整段字面量。
    注释内的换行原样保留，其余字符换成空格，这样剥完的字符串与原文字符
    **一一对位**，可以直接按位置回推行号。
    """
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]

        # ---- 字符串 / 模板字面量：整段原样穿过 ----
        if c in "'\"`":
            quote = c
            out.append(c)
            i += 1
            while i < n:
                if src[i] == "\\":  # 转义：连跳两个字符
                    out.append(src[i : i + 2])
                    i += 2
                    continue
                out.append(src[i])
                if src[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        # ---- 块注释：保留其中的换行，其余换空格 ----
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i < n and not (src[i] == "*" and i + 1 < n and src[i + 1] == "/"):
                out.append("\n" if src[i] == "\n" else " ")
                i += 1
            i += 2 if i < n else 0
            out.append("  ")
            continue

        # ---- 行注释 ----
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


# JS 的幂运算符也是 `**`（`2 ** 3`）。它在**代码位置**必然两侧是操作数，
# 而 Markdown 强调标记两侧是正文字符。用它把两者分开，避免误报。
#
# 🔴 这里**不能**用 `\w`：Python 的 `\w` 含 CJK，`程序**不会**替你摇`
#    会被判成"幂运算符"从而整段跳过 —— 中文正是本项目的正文语种，
#    等于把守卫关掉了大半（当时"守卫看起来在跑、却漏掉句中的标记"）。
#    必须显式写 ASCII 字符类。
_OPERAND = r"[A-Za-z0-9_\)\]]"
_OPERAND_LEFT = r"[A-Za-z0-9_\(\[]"
_EXPONENT = re.compile(rf"{_OPERAND}\s*\*\*\s*{_OPERAND_LEFT}")


def _text_surfaces(code: str) -> list[str]:
    """从"已剥注释"的源码里取出**会进入界面的文本片段**。

    取两类：
    1. 引号内的字面量内容（单引号 / 双引号 / 模板字符串）
    2. 引号外的代码位置 —— JSX 文本节点就落在这里（注释已在上一环剥掉）
    """
    surfaces: list[str] = []
    i, n = 0, len(src := code)
    plain_start = 0
    while i < n:
        c = src[i]
        if c in "'\"`":
            surfaces.append(src[plain_start:i])  # 引号外的部分
            quote = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == quote:
                    break
                j += 1
            surfaces.append(src[i + 1 : j])  # 字面量内容
            i = j + 1
            plain_start = i
            continue
        i += 1
    surfaces.append(src[plain_start:])
    return surfaces


def _offenders_from_source(rel: str, raw: str) -> list[str]:
    """从一份源码文本里找出全部"会渲染出星号"的片段。

    `_EXPONENT` 的过滤是**按片段**做的：只要该片段里出现幂运算符的形态，
    整段就不再检查。这比逐个匹配点判断更保守（宁可漏报一次指数运算，
    也不要把 `2 ** 3` 当成 Markdown 报出来）。
    """
    code = _strip_comments(raw)
    found: list[str] = []
    for surface in _text_surfaces(code):
        if "**" not in surface:
            continue
        if _EXPONENT.search(surface):
            continue
        for m in re.finditer(r"\*\*(.+?)\*\*|\*\*", surface):
            found.append(f"{rel}: {m.group(0)[:60]!r}")
    return found


def _offenders_in(path: pathlib.Path) -> list[str]:
    return _offenders_from_source(
        path.relative_to(_ROOT).as_posix(), path.read_text(encoding="utf-8")
    )


def _iter_sources():
    for d in _SCAN_DIRS:
        for p in sorted(d.rglob("*")):
            if p.is_file() and p.suffix in _SUFFIXES:
                yield p


# ==========================================================================
# 扫描器自身的守卫 —— 防止它退化成"永远通过"
# ==========================================================================


def test_scanner_ignores_comments_but_catches_text() -> None:
    """剥注释的扫描器必须**该报的报、不该报的不报**。

    没有这条，扫描器一旦写错（比如早早 return 空串），
    下面那条断言就会变成永远通过的假绿 —— 比没有测试更糟。
    """
    sample = """// 头部注释
    /** 注释里的 ** 强调 ** 是合法的，不该报 */
    // 行注释里的 ** 也不该报
    const a = '文案里的 **外圈** 要报';   // 行尾注释里的 ** 不报
    const b = "另一处 **逐宫错位**";
    const c = 2 ** 3;                     // 幂运算符不报
    const d = 5 ** 2;                     // 幂运算符不报
    """
    offenders = _offenders_from_source("sample.tsx", sample)

    assert len(offenders) == 2, f"期望恰好 2 处命中，实得 {offenders}"
    assert "外圈" in offenders[0], offenders
    assert "逐宫错位" in offenders[1], offenders


def test_scanner_does_not_swallow_string_contents() -> None:
    """扫描器不能把字符串内容一起当注释剥掉。

    防的是另一方向的假绿：剥注释剥过头 → 真正的缺陷也被吃掉。
    这里给一份**只有一处**标记的源码，必须报出来。
    """
    sample = """
    const t = '把照片里罗盘的**外圈**对到矢量盘的外缘';
    """
    offenders = _offenders_from_source("sample2.tsx", sample)
    assert len(offenders) == 1, offenders
    assert "外圈" in offenders[0]


# ==========================================================================
# 主断言
# ==========================================================================


def test_ui_copy_has_no_markdown_markup() -> None:
    """`apps/mobile` 的界面文案里不得出现 Markdown 强调标记。

    它会被 RN 的 `<Text>` 原样渲染成两个星号 —— 用户看到的是一句被符号切开的话。
    """
    offenders: list[str] = []
    scanned = 0
    for path in _iter_sources():
        scanned += 1
        offenders += _offenders_in(path)

    assert scanned > 0, "没扫到任何源文件 —— 扫描路径写错了，这条断言会变成假绿"
    assert not offenders, (
        "下列界面文案含 Markdown 强调标记，会被 RN <Text> 原样渲染成星号。\n"
        "改法：去掉 `**`（本仓库管理台的同类文案就是这么修的，见 "
        "tests/api/test_admin_config.py::TestCopyIsPlainText）。\n" + "\n".join(offenders)
    )
