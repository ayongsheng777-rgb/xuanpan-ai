#!/usr/bin/env python
"""把「改前 / 改后」两张同名快照拼成一张并排对照图。

用法
----
    "$PY" scripts/ui_render/make_compare.py \\
        --before "$T/ui-admin-before" --after docs/ui-render --out dist/ui-compare \\
        [--names 11-admin,16-admin-lab] [--scale 0.5]

参数
----
--before/--after  两个装着同名 PNG 的目录
--out             输出目录（自动创建）
--names           逗号分隔；省略则取两目录的**交集**（同名文件）
--scale           缩放系数，默认 1.0。桌面视口（1440px）拼两张会很宽，酌情降

为什么要固化成脚本
------------------
快照只说明"现在长这样"，回答不了"这次改动把界面动了哪里"。并排图是本仓库
评审 UI 改动的**主要凭据**，被反复需要 —— 每轮临时写一遍既浪费又容易漏掉
"像素差异比例"这个最该给的数字。

输出
----
`<out>/<name>-before-after.png`，左改前右改后，页眉标注、页脚给出尺寸与
**差异像素占比**。差异占比 >0 才算真的动过图；两张完全一样说明基线取错了。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

#: 中文字体。缺失时退回 Pillow 内置位图字体（英文可读、中文会变方框）——
#: 宁可标签难看也不要因为字体缺失让整个脚本报错。
_FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)

_LABEL_BEFORE = "改前"
_LABEL_AFTER = "改后"

PAD = 16
GAP = 24
HEADER_H = 44
FOOTER_H = 30
BG = (255, 255, 255)
FG = (17, 24, 39)
MUTED = (107, 114, 128)
RULE = (209, 213, 219)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in _FONT_CANDIDATES:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _diff_ratio(a: Image.Image, b: Image.Image) -> tuple[float, str]:
    """两张图的差异像素占比。尺寸不同时按**公共区域**比，并如实标注。"""
    note = ""
    if a.size != b.size:
        note = f"  (尺寸不同 {a.size}→{b.size}，仅比公共区域)"
        w = min(a.size[0], b.size[0])
        h = min(a.size[1], b.size[1])
        a = a.crop((0, 0, w, h))
        b = b.crop((0, 0, w, h))
    diff = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
    # 容差：截图有轻微抗锯齿 / 亚像素差，0 容差会把"没改"也报成改过
    bbox = diff.convert("L").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None:
        return 0.0, note
    gray = diff.convert("L").point(lambda v: 255 if v > 8 else 0)
    changed = sum(gray.histogram()[255:])
    total = a.size[0] * a.size[1]
    return changed / total, note


def _panel(label: str, im: Image.Image, f_head, f_foot, note: str) -> Image.Image:
    """单侧面板：页眉标签 + 图 + 页脚尺寸。"""
    w, h = im.size
    box = Image.new("RGB", (w, HEADER_H + h + FOOTER_H), BG)
    box.paste(im.convert("RGB"), (0, HEADER_H))
    d = ImageDraw.Draw(box)
    d.text((2, 10), label, font=f_head, fill=FG)
    d.text((2, HEADER_H + h + 6), f"{im.size[0]}×{im.size[1]}{note}", font=f_foot, fill=MUTED)
    d.line([(0, HEADER_H + h + 2), (w, HEADER_H + h + 2)], fill=RULE)
    return box


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生成改前/改后并排对照图")
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--names", default="")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args(argv)

    before_dir, after_dir, out_dir = Path(args.before), Path(args.after), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.names.strip():
        names = [n.strip() for n in args.names.split(",") if n.strip()]
    else:
        names = sorted(
            p.stem for p in after_dir.glob("*.png") if (before_dir / p.name).exists()
        )

    if not names:
        print("没有可比的同名快照 —— 检查 --before / --after 是否指对了目录", file=sys.stderr)
        return 2

    f_head, f_foot = _font(22), _font(15)
    made, unchanged = 0, []
    for name in names:
        bp, apth = before_dir / f"{name}.png", after_dir / f"{name}.png"
        if not bp.exists() or not apth.exists():
            print(f"跳过 {name}：{'缺改前' if not bp.exists() else '缺改后'}")
            continue

        a, b = Image.open(bp), Image.open(apth)
        ratio, note = _diff_ratio(a, b)
        if ratio == 0.0:
            unchanged.append(name)

        if args.scale != 1.0:
            size = (max(1, round(a.size[0] * args.scale)), max(1, round(a.size[1] * args.scale)))
            a, b = a.resize(size, Image.LANCZOS), b.resize(size, Image.LANCZOS)

        left = _panel(_LABEL_BEFORE, a, f_head, f_foot, "")
        right = _panel(_LABEL_AFTER, b, f_head, f_foot, "")
        canvas = Image.new(
            "RGB", (PAD * 2 + left.size[0] + GAP + right.size[0], PAD * 2 + left.size[1]), BG
        )
        canvas.paste(left, (PAD, PAD))
        canvas.paste(right, (PAD + left.size[0] + GAP, PAD))

        d = ImageDraw.Draw(canvas)
        pct = f"{ratio * 100:.2f}%"
        d.text((PAD, 2), f"{name}   差异像素 {pct}{note}", font=f_foot, fill=FG)

        target = out_dir / f"{name}-before-after.png"
        canvas.save(target)
        made += 1
        print(f"{name:22s} 差异 {pct:>7s}{note}  -> {target}")

    print(f"\n生成 {made} 张对照图到 {out_dir}")
    if unchanged:
        print(f"⚠ 以下 {len(unchanged)} 张改前改后**完全一致**，基线可能取错了：{unchanged}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
