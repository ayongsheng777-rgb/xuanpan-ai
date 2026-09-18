"""生成 APP 图标与启动图（Android 打包必需）。

为什么需要这个脚本而不是直接放几张图：
  图标与启动图是**派生产物** —— 由一张品牌源图加一组实测裁切参数推导而来。
  把 PNG 当源码提交，换品牌稿时没人知道该重新导出哪几张、用什么尺寸。
  脚本化之后，源图换了就重跑一次，不存在"漏导出一张"的可能。

为什么从「几何绘制」改为「品牌源图裁切」：
  上一版图标是用 PIL 几何画出的 24 山线条罗盘，配色与 tokens.ts 同源。
  它在 1024 尺寸下看着没问题，但**在桌面尺寸下视觉重量归零**：
  adaptive-icon 的不透明像素只占 2%，换算到 108dp 画布上线宽约 0.5dp，
  肉眼看到的就是一个纯蓝色圆 —— 用户的原话是「没有 logo」。
  线条图形在 48dp 上必然遇到这个问题，实物感的主体才有足够的色块面积。
  所以改为从设计稿裁切（源图入库在 docs/ 下），并新增生成时的占比自检。

用法：
    "$PY" scripts/gen_app_assets.py            # 生成到 apps/mobile/assets/
    "$PY" scripts/gen_app_assets.py --dry-run  # 只生成到临时目录并打印，不覆盖

--------------------------------------------------------------------------
改动前必读：下面这几个数字是**实测**出来的，不是估的，改之前先重测
--------------------------------------------------------------------------

1) 圆形盘面裁切参数 (CIRCLE_CX, CIRCLE_CY, CIRCLE_R)

   源图底部有两样东西紧挨着：朱红印章（「天元之光」）底面在 y≈403，
   铜质铭牌（「玄盘 AI」）顶面在 y≈409 —— 中间只有 6px 的缝。

   圆底必须落进这条缝里，否则：
     * 圆底 > 409 → 圆的下缘会露出半截铭牌，看着像没抠干净的残影
     * 圆底 < 403 → 印章被切掉一截
   实测圆底 = 241 + 165 = 406，正落在缝中。

   圆的**水平**范围同时要覆盖外圈青绿同心纹样（x 325~695），
   半径因此不能小于 165，这是半径的下限来源。

2) 为什么桌面图标用「圆形盘面」而不是整只木盒

   木盒是圆角方形，而 Android 自适应图标按「108dp 画布 / 72dp 可见圆」裁切。
   实测两种做法都不可用：
     * 整盒完整放进可见圆 → 只能占画布 46%，桌面 48dp 里只剩 22dp，细节糊成一团
     * 整盒撑满画布       → 四角被圆切掉，且底部铭牌被切一半
   圆形盘面与圆形裁切 100% 契合，零浪费 —— 这才是这套参数存在的理由，
   不是因为「盘面好看」。

3) splash 必须是**透明底**

   expo-splash-screen 的 plugin 模式会把图叠在 backgroundColor 上，
   图自带底色会导致「图里一块底色 + 屏幕另一块底色」两层色。
   底色一律交给 app.json 的 backgroundColor。

产物：
  apps/mobile/assets/icon.png             1024x1024  深蓝底 + 圆形盘面（iOS / legacy / 通用）
  apps/mobile/assets/adaptive-icon.png    1024x1024  透明底 + 圆形盘面（Android 自适应前景）
  apps/mobile/assets/splash.png           1024x1024  透明底 + 整只木盒（启动图）
  apps/mobile/assets/favicon.png            196x196  深蓝底 + 圆形盘面（Web）
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "docs" / "玄盘 AI — 品牌图标源图.png"
ASSETS = REPO / "apps" / "mobile" / "assets"

# ---- 品牌色（与 apps/mobile/src/theme/tokens.ts 保持一致）----
BRAND_BLUE = (1, 58, 108, 255)  # tokens: brand primary #013A6C
BRAND_SAND = (229, 215, 199, 255)  # tokens: sand #E5D7C7

# ---- 源图上的实测区域 ----
BOX = (273, 59, 731, 501)  # 木盒本体（不含布纹背景与投影）
CIRCLE_CX, CIRCLE_CY, CIRCLE_R = 510, 241, 165  # 圆形盘面（见文件头说明 1）

# ---- 输出规格 ----
SPECS = {
    "adaptive-icon.png": dict(
        kind="circle", size=1024, diameter=683, bg=None,
        why="Android 自适应图标前景：直径 683 = 1024×(72/108)，正好填满可见圆"),
    "icon.png": dict(
        kind="circle", size=1024, diameter=860, bg=BRAND_BLUE,
        why="iOS / legacy Android / 通用方形：深蓝底 + 盘面，任何裁切形状下都完整"),
    "splash.png": dict(
        kind="box", size=1024, width=870, bg=None,
        why="启动图：透明底 + 木盒整体（含「玄盘 AI」铭牌），底色交给 backgroundColor"),
    "favicon.png": dict(
        kind="circle", size=196, diameter=168, bg=BRAND_BLUE,
        why="Web favicon"),
}


def _circle(src: Image.Image, diameter: int) -> Image.Image:
    """裁出圆形盘面。半径与圆心见文件头说明 1。"""
    box = src.crop((CIRCLE_CX - CIRCLE_R, CIRCLE_CY - CIRCLE_R,
                    CIRCLE_CX + CIRCLE_R, CIRCLE_CY + CIRCLE_R))
    # 4× 超采样做遮罩，避免边缘锯齿
    mask = Image.new("L", (CIRCLE_R * 8, CIRCLE_R * 8), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, CIRCLE_R * 8 - 1, CIRCLE_R * 8 - 1], fill=255)
    mask = mask.resize(box.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.7))
    box.putalpha(mask)
    return box.resize((diameter, diameter), Image.LANCZOS) \
        .filter(ImageFilter.UnsharpMask(2, 60, 3))


def _box(src: Image.Image, width: int) -> Image.Image:
    """裁出整只木盒并做圆角遮罩（去掉四周布纹）。"""
    crop = src.crop(BOX)
    w, h = crop.size
    out = crop.resize((width, int(h * width / w)), Image.LANCZOS) \
        .filter(ImageFilter.UnsharpMask(2, 55, 3))
    mask = Image.new("L", out.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, out.size[0] - 1, out.size[1] - 1],
        radius=max(1, int(42 * width / w)), fill=255)
    out.putalpha(mask.filter(ImageFilter.GaussianBlur(1.0)))
    return out


def build(out_dir: Path) -> list[Path]:
    if not SOURCE.exists():
        raise SystemExit(
            f"找不到品牌源图：{SOURCE}\n"
            "它应该作为设计依据入库到 docs/ 下（不是临时截图路径）。"
        )
    src = Image.open(SOURCE).convert("RGBA")
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name, spec in SPECS.items():
        canvas = Image.new("RGBA", (spec["size"], spec["size"]),
                           spec["bg"] or (0, 0, 0, 0))
        subj = _circle(src, spec["diameter"]) if spec["kind"] == "circle" \
            else _box(src, spec["width"])
        canvas.alpha_composite(subj, ((canvas.size[0] - subj.size[0]) // 2,
                                      (canvas.size[1] - subj.size[1]) // 2))
        path = out_dir / name
        # 不透明底色的图（icon / favicon）必须去掉 alpha 通道：
        # iOS 不接受带透明的图标，会把它合成到黑底上 —— 深蓝底会镶一圈黑边。
        # 透明底的图（adaptive-icon / splash）保留 alpha。
        if spec["bg"] is not None:
            canvas = canvas.convert("RGB")
        # optimize=True：照片类 PNG 用最优滤波重排，无损再省几个百分点
        canvas.save(path, optimize=True)
        written.append(path)
    return written


def check(written: list[Path]) -> None:
    """自检：桌面图标的前景不透明占比不能太低，否则桌面上视觉重量归零。

    这条判据来自上一版图标的实际失败（细线罗盘 = 2%，看起来「没有 logo」）。
    没有它，将来换一张线条型设计稿会再次静默产出看不见的图标。
    """
    fg = next(p for p in written if p.name == "adaptive-icon.png")
    im = Image.open(fg).convert("RGBA")
    alpha = im.getchannel("A").histogram()
    ratio = sum(alpha[240:256]) / (im.size[0] * im.size[1])
    print(f"  adaptive-icon 前景不透明占比 = {ratio:.1%}")
    if ratio < 0.25:
        raise SystemExit(
            f"前景占比仅 {ratio:.1%}，桌面尺寸下会糊成一片（旧版细线罗盘就是 2%）。"
            "请改用视觉重量更大的构图。"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="生成 APP 图标与启动图")
    ap.add_argument("--dry-run", action="store_true",
                    help="生成到临时目录，不覆盖 apps/mobile/assets/")
    args = ap.parse_args()

    out_dir = Path(tempfile.gettempdir()) / "xp-app-assets" if args.dry_run else ASSETS
    print(f"源图   : {SOURCE}")
    print(f"输出到 : {out_dir}")
    written = build(out_dir)
    for p in written:
        im = Image.open(p)
        print(f"  ✓ {p.name:20} {im.size[0]}x{im.size[1]}  {p.stat().st_size:>7} bytes")
    check(written)
    if args.dry_run:
        print("（dry-run：未写入 apps/mobile/assets/）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
