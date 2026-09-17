"""生成 APP 图标与启动图（Android 打包必需）。

为什么需要这个脚本而不是直接放几张图：
  图标与启动图是**派生产物** —— 由设计 token（配色）与一个几何定义推导而来。
  把 PNG 当源码提交，改配色时没人知道该重新导出哪几张、用什么尺寸。
  脚本化之后，配色变了就重跑一次，不存在"漏导出一张"的可能。

配色取自 src/theme/tokens.ts 里像素采样的五个主色，此处与其保持一致。

用法：python scripts/gen_app_assets.py
产物：
  apps/mobile/assets/icon.png             1024x1024  深蓝底 + 金色罗盘（应用图标）
  apps/mobile/assets/adaptive-icon.png    1024x1024  透明底 + 金色罗盘（Android 自适应前景）
  apps/mobile/assets/splash.png           1024x1024  米色底 + 深蓝罗盘（启动图）
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# 与 src/theme/tokens.ts 同源
NAVY = (1, 58, 108)
GOLD = (218, 179, 125)
CREAM = (229, 215, 199)
RED = (185, 62, 53)

SIZE = 1024


def draw_compass(
    *,
    size: int = SIZE,
    background: tuple[int, int, int, int] | None,
    ring: tuple[int, int, int],
    tick: tuple[int, int, int],
    needle: tuple[int, int, int],
    scale: float = 0.74,
) -> Image.Image:
    """画一个罗盘符号：外环 + 24 山刻度 + 内环 + 四正指线。

    24 个刻度是刻意的：这个 APP 的领域模型就是二十四山，每山 15°。
    图标上放 24 个刻度等于把核心概念画进 logo，而不是随便找个圆。
    """
    img = Image.new("RGBA", (size, size), background)
    d = ImageDraw.Draw(img)
    cx = cy = size / 2
    radius = size * scale / 2

    # 外环
    ring_w = max(2, int(radius * 0.055))
    d.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=ring, width=ring_w)

    # 24 山刻度：每 45° 一个长刻度（四正四隅），其余短刻度
    tick_outer = radius * 0.99
    for i in range(24):
        angle = math.radians(i * 15 - 90)  # -90 让 0° 指向正上方
        is_major = i % 3 == 0
        length = radius * (0.19 if is_major else 0.095)
        width = max(1, int(radius * (0.030 if is_major else 0.018)))
        x1, y1 = cx + math.cos(angle) * tick_outer, cy + math.sin(angle) * tick_outer
        x2 = cx + math.cos(angle) * (tick_outer - length)
        y2 = cy + math.sin(angle) * (tick_outer - length)
        d.line([x1, y1, x2, y2], fill=tick, width=width)

    # 内环
    inner = radius * 0.60
    d.ellipse([cx - inner, cy - inner, cx + inner, cy + inner],
              outline=ring, width=max(1, int(radius * 0.020)))

    # 四正指线：南北用强调色，形成"坐向"的视觉暗示
    line_out = inner * 1.30
    for idx, (color, w) in enumerate([(needle, 0.042), (ring, 0.026), (needle, 0.042), (ring, 0.026)]):
        angle = math.radians(idx * 90 - 90)
        x1, y1 = cx + math.cos(angle) * line_out, cy + math.sin(angle) * line_out
        x2, y2 = cx - math.cos(angle) * line_out, cy - math.sin(angle) * line_out
        d.line([x1, y1, x2, y2], fill=color, width=max(1, int(radius * w)))

    # 中心点
    hub = radius * 0.075
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=ring)

    return img


def main() -> int:
    out_dir = Path(__file__).resolve().parent.parent / "apps" / "mobile" / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 应用图标：深蓝底 + 金色罗盘
    icon = draw_compass(background=NAVY, ring=GOLD, tick=GOLD, needle=GOLD)
    icon.convert("RGB").save(out_dir / "icon.png")

    # Android 自适应图标前景：透明底，图形缩到 60% 以避开圆形/方形遮罩的裁切
    adaptive = draw_compass(background=None, ring=GOLD, tick=GOLD, needle=GOLD, scale=0.46)
    adaptive.save(out_dir / "adaptive-icon.png")

    # 启动图：米色底 + 深蓝罗盘
    splash = draw_compass(background=CREAM, ring=NAVY, tick=NAVY, needle=RED)
    splash.convert("RGB").save(out_dir / "splash.png")

    for name in ("icon.png", "adaptive-icon.png", "splash.png"):
        path = out_dir / name
        print(f"  {name:22} {path.stat().st_size / 1024:.1f} KB")

    print(f"\n已输出到 {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
