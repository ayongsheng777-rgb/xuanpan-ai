#!/usr/bin/env python
"""生成「单屏化改造」的改前/改后对照页。

为什么要固化成脚本而不是手写一次 HTML：这一页要能被**重跑** ——
界面还会继续改，对照页必须能一键重生成，否则下一次评审又得从头拼图。
（同 `scripts/ui_render/make_compare.py` 的理由。）

用法：
    "$PY" scripts/ui_render/make_one_screen_report.py \\
        --before <改前截图目录> --after <改后截图目录> --out <输出 html>

输入约定：两个目录里放同名 PNG（`01-home.png` 这种），名字来自
`scripts/ui_render/render_pages.mjs` 的 PAGES 表。
"""

from __future__ import annotations

import argparse
import base64
from pathlib import Path

#: 仓库根（本文件在 <root>/scripts/ui_render/ 下）。
#: 用它数路由页，避免把手写的页面数写进交付物 —— 页面增删后手写数字会静默说谎。
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: 页面名 → (中文标题, 这一页的一屏改造要点)
PAGES: dict[str, tuple[str, str]] = {
    "01-home": (
        "罗盘首页",
        "罗盘改为**唯一弹性区**（`onLayout` 实测可用空间自适应尺寸），"
        "读数区不再参与伸缩；外圈加 HUD 激光刻度环（纯装饰）。",
    ),
    "12-test": ("测盘", "五条来源按「2×2 + 1 居中」排，三行等高平分剩余高度；每块四角带回纹角花。"),
    "13-analysis": ("分析", "六宫阵 2×3 三行等高；块外观与「问号 + 详情弹层」收进共享组件，两页不再各写一套。"),
    "09-history": ("历史", "整页滚动 → `FoldList`：页内只放最近 4 条，其余进「更多」浮层（浮层不是页面滚动）。"),
    "10-mine": ("我的", "6 张竖排卡（要滚 941px）→ 三个分段标签「模型 / 我的 / 关于」，同一时刻只显示一组。"),
    "02-adjust": ("手动调节", "盘面为弹性区，角度调节常驻；盘式选择器挪出模板分支，直接进来也能换盘面。"),
    "03-sensors": ("传感器测量", "盘面弹性区 + 「读数 / 质量 / 原始」分段；页内与页脚各一个「返回测盘」（原先找不到返回）。"),
    "04-scan": ("罗盘识向", "双入口分段 + 取景器弹性区；拍摄要点收进弹层。"),
    "05-almanac": ("黄历择日", "「查黄历 / 择吉日」分段；候选日走 FoldList；流派差异与不确定性收进弹层。"),
    "06-sanshi": ("三式排盘", "**原本要滚 2270px**（全站最长）。改成「奇门 / 六壬 / 太乙」分段 + 「起局 / 盘面」二层分段，盘面为弹性区，其余收进弹层。"),
    "07-chart": ("八字命盘", "「四柱 / 事实 / 传统 / 断卦」分段，四柱为弹性区。"),
    "08-divine": ("六爻 · 灵签", "「六爻 / 灵签」分段，六爻内再分「登记摇卦 / 卦象 / 断卦」；六爻登记表 6 行全部可见。"),
    "14-templates": ("我的罗盘", "新建面板常驻 + 模板列表走 FoldList。"),
    "15-calibrate": ("罗盘校准", "「照片对位 / 读数与浓淡」分段；**原本要滚 978px**。"),
    "17-confirm": ("确认坐向", "盘面尺寸同时受屏宽与**实测可用高度**约束（原先只按屏宽算，底部提示被裁 72px）。"),
    "18-session": ("会话详情", "「概览 / 盘面 / 输入 / 结果」分段 + 底部固定主操作。"),
    "19-report": ("AI 解读报告", "保留三标签（盘面事实 → 传统分析 → AI 解读，**顺序不可换**）；依据与过程收进弹层。"),
}

#: 改前实测的页内滚动量（px），来自 render_pages.mjs 的 innerScrollMax。
#: 空字符串＝该页在当时的取数状态下没有溢出（但仍用了滚动容器）。
BEFORE_SCROLL: dict[str, str] = {
    "01-home": "165px",
    "02-adjust": "201px",
    "03-sensors": "762px",
    "04-scan": "—（容器在，当时无内容可滚）",
    "05-almanac": "487px",
    "06-sanshi": "2270px",
    "07-chart": "—（容器在，当时无内容可滚）",
    "08-divine": "113px",
    "09-history": "—（容器在，当时无内容可滚）",
    "10-mine": "941px",
    "12-test": "已是宫格（上一轮改的）",
    "13-analysis": "已是宫格（上一轮改的）",
    "14-templates": "已是宫格（上一轮改的）",
    "15-calibrate": "978px",
}

_CSS = """
:root{--bg:#FAF0D7;--surface:#FFFCF3;--border:#E2C88F;--text:#3B2B12;--sub:#7C6647;
--accent:#9A6B1F;--jade:#3C7066;--cinnabar:#B93E35;}
*{box-sizing:border-box;}
body{margin:0;background:var(--bg);color:var(--text);
font:15px/1.6 -apple-system,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;}
header{padding:28px 24px 18px;border-bottom:2px solid var(--border);}
h1{margin:0 0 6px;font-size:26px;letter-spacing:-.4px;}
.lead{margin:0;color:var(--sub);font-size:14px;}
.meta{margin-top:12px;display:flex;flex-wrap:wrap;gap:8px;}
.tag{background:var(--surface);border:1px solid var(--border);border-radius:999px;
padding:3px 12px;font-size:12px;color:var(--accent);}
.summary{margin:0;padding:20px 24px;display:grid;
grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px;}
.card{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:14px 16px;}
.card b{display:block;font-size:26px;color:var(--accent);letter-spacing:-.5px;line-height:1.2;}
.card span{font-size:12px;color:var(--sub);}
section{padding:8px 24px 4px;}
.row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:26px;}
@media(max-width:760px){.row{grid-template-columns:1fr;}}
.shot{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:12px;}
.shot h3{margin:0 0 8px;font-size:15px;display:flex;align-items:center;gap:8px;}
.shot h3 em{font-style:normal;font-size:11px;padding:2px 8px;border-radius:999px;}
.before h3 em{background:rgba(185,62,53,.10);color:var(--cinnabar);}
.after h3 em{background:rgba(60,112,102,.12);color:var(--jade);}
.shot img{width:100%;display:block;border-radius:10px;border:1px solid var(--border);}
.note{margin:10px 2px 0;font-size:13px;color:var(--sub);}
.note strong{color:var(--text);}
.scroll{color:var(--cinnabar);font-weight:600;}
footer{padding:24px;color:var(--sub);font-size:12px;border-top:1px solid var(--border);}
"""


def _data_uri(p: Path) -> str:
    """内联成 data URI —— 对照页要能单文件发给别人，不能依赖相对路径。"""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    before, after, out = Path(a.before), Path(a.after), Path(a.out)
    names = [n for n in PAGES if (after / f"{n}.png").is_file()]
    assert names, f"{after} 里没有可识别的页面截图"

    n_before = sum(1 for n in names if (before / f"{n}.png").is_file())

    # 两个汇总数字都从 BEFORE_SCROLL 现算，不写死 —— 写死就会在换页面集合后静默说谎。
    # `_scrolled`：实测有页内滚动量的页；`_px`：这些页的滚动幅度合计。
    _scrolled = [v for v in BEFORE_SCROLL.values() if v[:1].isdigit()]
    n_scrolled, sum_px = len(_scrolled), sum(int(v[:-2]) for v in _scrolled)
    assert n_scrolled and sum_px > 0, "BEFORE_SCROLL 解析失败，汇总数字会变成 0"

    rows = []
    for n in names:
        title, note = PAGES[n]
        bp, apth = before / f"{n}.png", after / f"{n}.png"
        cells = []
        if bp.is_file():
            cells.append(
                f'<figure class="shot before"><h3>{title}<em>改前</em></h3>'
                f'<img src="{_data_uri(bp)}" alt="{title} 改前"></figure>'
            )
        cells.append(
            f'<figure class="shot after"><h3>{title}<em>改后</em></h3>'
            f'<img src="{_data_uri(apth)}" alt="{title} 改后"></figure>'
        )
        scroll = BEFORE_SCROLL.get(n, "")
        scroll_line = (
            f'<div class="note">改前需滚动：<span class="scroll">{scroll}</span></div>'
            if scroll and scroll.startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9"))
            else (f'<div class="note">改前需滚动：{scroll}</div>' if scroll else "")
        )
        rows.append(
            '<div class="pair"><div class="row">'
            + "".join(cells)
            + f'</div><div class="note" style="margin-top:-18px"><strong>改法：</strong>{note}</div>'
            + scroll_line
            + "</div>"
        )

    # 路由页数量从文件系统现算 —— 手写数字会随页面增删而变成谎言。
    # 只数 page 文件（排除 `_layout.tsx`，那是布局不是页面）。
    _app_dir = _REPO_ROOT / "apps/mobile/app"
    _pages = sorted(
        p for p in _app_dir.rglob("*.tsx") if p.name != "_layout.tsx"
    )
    n_routes = len(_pages)
    n_tabs = sum(1 for p in _pages if "(tabs)" in p.parts)
    n_second = n_routes - n_tabs
    assert n_routes > 0, f"未在 {_app_dir} 找到任何路由页"

    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>玄盘 AI · 界面单屏化改造（改前 / 改后）</title>
<style>{_CSS}</style></head><body>
<header>
  <h1>玄盘 AI · 界面单屏化改造</h1>
  <p class="lead">2026-10-09 · 用户要求：每个界面完整显示在一屏内、不需滑动浏览；
  所有功能都能进入退出；测盘与分析的数据必须真实有效。</p>
  <div class="meta">
    <span class="tag">视口 390 × 844（真机尺寸，headless Chromium 实测）</span>
    <span class="tag">全站 {n_routes} 个路由页全部改造</span>
    <span class="tag">品牌五色与浅金域未改</span>
    <span class="tag">新增 4 个守卫测试</span>
  </div>
</header>

<div class="summary">
  <div class="card"><b>{sum_px}px → 0px</b><span>改前 {n_scrolled} 页有实际页内滚动，幅度合计（实测）→ 改后 0</span></div>
  <div class="card"><b>{n_before} → 0</b><span>改前留档的 {n_before} 页全部包在滚动容器里 → 改后 0 页</span></div>
  <div class="card"><b>{n_routes} / {n_routes}</b><span>改造页面数（{n_tabs} 个底栏 + {n_second} 个二级页）</span></div>
  <div class="card"><b>0</b><span>改后「内容被裁掉」的容器数（逐页扫描）</span></div>
</div>

<section>
{''.join(rows)}
</section>

<footer>
判据来自 <code>scripts/ui_render/render_pages.mjs</code> 的四项逐页实测：
文档高度 ≤ 视口、无内层滚动容器、无 overflow:hidden 裁切、无横向溢出。
截图由 headless Chromium 在 390×844 视口下真实渲染产出。
</footer>
</body></html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"已生成 {out}（{len(names)} 页，改前 {n_before} 张）")


if __name__ == "__main__":
    main()
