"""生成可直接装进手机相册的罗盘样张，用于验证「APP ↔ 后端」链路是否打通。

⚠️ 这些是**合成图**，不能代替 Gate 1 的真实照片评测（原因见
   docs/玄盘 AI — Gate1 合成退化扫描.md：合成图在设计上就缺少真实照片的
   传感器噪点分布、镜头畸变与背景杂物，它测不出真实拍摄的失效模式）。
   本脚本产物的用途只有一个：在拿到真实罗盘照片之前，让
   拍摄 → 识别 → 确认坐向 → 生成报告 这条链路能在手机被完整走通一遍，
   从而把「APP 装不上/连不上后端」与「识别算法不准」这两类问题分开。

用法：
    python scripts/gen_sample_photos.py                 # 默认输出到 samples/compass
    python scripts/gen_sample_photos.py --out D:/xxx    # 自定义输出目录
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path[:0] = ["services/vision", "packages/fortune-core"]

from xuanpan_vision.testing import render_compass  # noqa: E402

# (文件名, 说明, 渲染参数)
SAMPLES: list[tuple[str, str, dict]] = [
    ("compass-000.jpg", "子山午向（正北），清晰大图", dict(thread_angle=0.0, size=1200)),
    ("compass-045.jpg", "艮山坤向（东北），清晰大图", dict(thread_angle=45.0, size=1200)),
    ("compass-090.jpg", "卯山酉向（正东），清晰大图", dict(thread_angle=90.0, size=1200)),
    ("compass-180.jpg", "午山子向（正南），清晰大图", dict(thread_angle=180.0, size=1200)),
    ("compass-270.jpg", "酉山卯向（正西），清晰大图", dict(thread_angle=270.0, size=1200)),
    (
        "compass-045-handheld.jpg",
        "艮山坤向，模拟随手拍（小图+噪点+轻斜）",
        dict(thread_angle=45.0, size=720, noise=4.0, blur=0.6, squash=0.92, tilt=6.0),
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="生成罗盘样张（合成图，非 Gate 1 评测）")
    parser.add_argument("--out", default="samples/compass", help="输出目录")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, str]] = []
    for name, note, kwargs in SAMPLES:
        image = render_compass(**kwargs)
        image.save(out_dir / name, quality=92)
        rows.append(
            {
                "filename": name,
                "angle": str(kwargs["thread_angle"]),
                "note": note,
            }
        )
        print(f"  {name:32} {image.size[0]}x{image.size[1]}  {note}")

    # labels.csv 只用于跑 gate1_eval.py photos 做**链路自测**。
    # 文件名与 README 都写明是合成图，避免被当成 Gate 1 的真实评测结果。
    with (out_dir / "labels.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["filename", "angle", "note"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n已输出 {len(rows)} 张到 {out_dir.resolve()}")
    print("⚠️  合成图，仅用于验证 APP↔后端链路，不构成 Gate 1 评测。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
