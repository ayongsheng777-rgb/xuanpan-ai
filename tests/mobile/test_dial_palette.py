"""盘面调色板的**双轨边界**守卫。

## 为什么需要它

V2 之后盘面有两套配色（《V2 评估与实施路线》冲突 2 裁决）：

- `DIAL_LIGHT` —— 暖色浅色盘，`session/[sessionId]` 等**浅色页面**在用；
- `DIAL_DARK`  —— 深色仪器盘，罗盘域 4 个页面在用。

两轨**共用同一套几何**（`lib/compassDial` + `lib/dialStyle`），只在深色轨上
多做一层明暗（径向渐变底）。这条线很容易被无意越过：顺手给 `DIAL_LIGHT`
也加上渐变，浅色页的盘面就会**静默换一个长相** —— 不报错、不影响任何计算，
而那几页正是"确认坐向"这类用户要拿实物逐格核对的界面。
**盘面长得变了，用户对识别结果的信任就会跟着变。**

## 校验方式与边界

`DIAL_LIGHT` / `DIAL_DARK` 定义在 `CompassDial.tsx`（含 JSX 与
`react-native-svg`），Node 的类型擦除**跑不起来**，故这里读源码做结构断言。

⚠️ 本文件守的是「配置不要漂移」，**不是**「渲染结果正确」——
后者由 `test_ui_render.py` 的快照负责。两者分工不同，不要用这里的绿
去推断界面一定对。
"""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DIAL_SRC = _REPO_ROOT / "apps/mobile/src/components/CompassDial.tsx"


def _source() -> str:
    assert _DIAL_SRC.exists(), f"找不到盘面组件：{_DIAL_SRC}"
    return _DIAL_SRC.read_text(encoding="utf-8")


def _palette_block(name: str) -> str:
    """取出某个调色板字面量的源码片段（从声明起到第一个 `\\n};` 止）。"""
    src = _source()
    marker = f"export const {name}: DialPalette = {{"
    start = src.index(marker)  # 找不到就抛异常 —— 调色板被改名时应当立刻红
    end = src.index("\n};", start)
    return src[start:end]


# ==========================================================================
# 一、双轨边界：渐变只许出现在深色轨
# ==========================================================================


def test_dark_palette_enables_the_radial_gradient() -> None:
    """深色盘必须启用径向渐变底，否则中心（天池）不会成为视觉焦点。"""
    assert "bodyGradient" in _palette_block("DIAL_DARK")


def test_light_palette_stays_flat() -> None:
    """🔴 浅色盘**不得**启用渐变 —— 这条是双轨制的分界线。

    一旦这里红了，先问一句：是真的要改浅色页的观感（那属于产品裁定，
    要同步改快照与导出包，并且真机走查），还是只是顺手复制了过去？
    """
    assert "bodyGradient" not in _palette_block("DIAL_LIGHT"), (
        "DIAL_LIGHT 被加上了径向渐变 —— 浅色页（确认坐向等）的盘面会静默换脸。"
        "若确属有意，请同步改 test_ui_render 快照并走真机走查。"
    )


# ==========================================================================
# 二、渐变色的来源
# ==========================================================================


def test_dark_palette_gradient_comes_from_tokens() -> None:
    """渐变的三个色阶必须引用 token，不得在组件里写死十六进制。

    与 `tokens.ts` 头部那条铁律同源：同一个语义在两处写死，改一处忘一处
    就会出现"渐变中心和盘体底色不是一族"的漂移 —— 而两处都是合法色值，
    没有任何检查会报错。
    """
    block = _palette_block("DIAL_DARK")
    assert "instrument.dialBodyGradient" in block, "渐变没有引用 tokens 里的定义"


def test_palettes_contain_no_hardcoded_colors() -> None:
    """两个调色板里都不许出现字面色值（`'#…`）。

    调色板是"哪一层用什么颜色"的**映射表**，它的每个值都应该是 token 引用；
    一旦写成字面量，改主题时就会漏掉盘面 —— 而盘面恰恰是最显眼的那块。
    """
    for name in ("DIAL_LIGHT", "DIAL_DARK"):
        block = _palette_block(name)
        assert "'#" not in block, f"{name} 里出现了硬编码色值：\n{block}"


def test_gradient_has_three_stops() -> None:
    """渐变必须是三阶 —— 两阶会读成"生硬的明暗分界"，四阶以上在盘面这个尺寸上分辨不出。

    形状约束读的是 **tokens.ts** 而不是组件：色阶的定义处只有一个
    （`instrument.dialBodyGradient`），CompassDial 里只有引用。
    在组件里找定义会永远找不到 —— 这条断言最初就是这么写错的。
    """
    tokens = (_REPO_ROOT / "apps/mobile/src/theme/tokens.ts").read_text(encoding="utf-8")
    start = tokens.index("dialBodyGradient:")
    line = tokens[start : tokens.index("]", start)]
    stops = line.count("'#")
    assert stops == 3, f"盘体渐变应为 3 档，实为 {stops} 档：{line}"
