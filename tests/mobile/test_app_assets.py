"""APP 图标与启动图的资源守卫。

这些断言守护的是**用户能看见的东西**，不是文件格式是否合规。

为什么需要它（真实事故）：
  v0.1.0 的图标是几何画出的细线罗盘，矢量上完全正确，`tsc` / 打包全绿，
  但它在桌面尺寸下视觉重量归零 —— adaptive-icon 的不透明像素只占 2%，
  换算到 108dp 画布上线宽约 0.5dp，肉眼看到的就是一个纯蓝色圆。
  用户反馈的原话是「没有 logo」。

  没有任何检查会发现这件事：图标文件存在、尺寸正确、能打包、能安装。
  所以这里补两道断言：**前景墨量**与**启动图透明底**。
  前者防"看不见的图标"复发，后者防"图自带底色 + backgroundColor 双层色"。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
ASSETS = REPO / "apps" / "mobile" / "assets"
GEN_SCRIPT = REPO / "scripts" / "gen_app_assets.py"

BRAND_BLUE = (1, 58, 108)


def _load_gen():
    """按路径加载生成脚本（scripts/ 不是包，只能这么导入）。"""
    spec = importlib.util.spec_from_file_location("gen_app_assets", GEN_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gen():
    return _load_gen()


# --------------------------------------------------------------------------
# 资源规格
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("name", "size", "mode_has_alpha"),
    [
        ("icon.png", 1024, False),
        ("adaptive-icon.png", 1024, True),
        ("splash.png", 1024, True),
        ("favicon.png", 196, False),
    ],
)
def test_asset_exists_with_spec(name: str, size: int, mode_has_alpha: bool) -> None:
    """四张资源都在，且尺寸符合各自用途（方形、2 的幂、够高清）。"""
    path = ASSETS / name
    assert path.exists(), f"{name} 缺失 —— 跑 scripts/gen_app_assets.py 重新生成"
    im = Image.open(path)
    assert im.size == (size, size), f"{name} 应为 {size}x{size}，实际 {im.size}"
    if mode_has_alpha:
        assert im.mode == "RGBA", f"{name} 需要 alpha 通道，实际 {im.mode}"


def test_icon_uses_brand_color_and_is_opaque() -> None:
    """icon.png 铺满品牌深蓝，没有透明洞。

    iOS 不接受带透明的图标，会把它合成到黑底上 —— 深蓝变黑边。
    """
    im = Image.open(ASSETS / "icon.png").convert("RGBA")
    assert im.getchannel("A").getextrema() == (255, 255), "icon.png 存在透明像素"
    for corner in ((2, 2), (1021, 2), (2, 1021), (1021, 1021)):
        r, g, b, _ = im.getpixel(corner)
        assert (r, g, b) == BRAND_BLUE, f"角 {corner} 不是品牌深蓝，实际 {(r, g, b)}"


# --------------------------------------------------------------------------
# 守卫 1：前景墨量 —— 防止「看不见的图标」复发
# --------------------------------------------------------------------------

def test_adaptive_foreground_has_enough_ink() -> None:
    """自适应图标前景的不透明像素占比必须够高。

    这是本次事故的直接固化：旧版细线罗盘只有 2%，桌面 48dp 下看不见。
    实物感的主体构图实测 34.6%，阈值取 25% 留出余量。
    """
    im = Image.open(ASSETS / "adaptive-icon.png").convert("RGBA")
    hist = im.getchannel("A").histogram()
    ratio = sum(hist[240:256]) / (im.size[0] * im.size[1])
    assert ratio > 0.25, (
        f"前景不透明占比仅 {ratio:.1%}，桌面尺寸下会糊成一片。"
        "旧版细线罗盘就是 2% —— 用户看到的是一个纯蓝色圆，反馈「没有 logo」。"
    )


def test_adaptive_foreground_corners_transparent() -> None:
    """四角必须透明：Android 会按 72/108 圆裁切，四角若有不透明内容会被切出硬边。"""
    im = Image.open(ASSETS / "adaptive-icon.png").convert("RGBA")
    w, h = im.size
    for corner in ((1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)):
        assert im.getpixel(corner)[3] == 0, f"角 {corner} 不透明，圆形裁切会留下硬边"


# --------------------------------------------------------------------------
# 守卫 2：启动图透明底 —— 防止双层底色
# --------------------------------------------------------------------------

def test_splash_background_is_transparent() -> None:
    """splash.png 必须是透明底。

    expo-splash-screen 的 plugin 模式把图叠在 backgroundColor 上：
    图自带底色时，屏幕上会出现「图里一块色 + 屏幕另一块色」两层，
    而且两者永远对不齐（图按 imageWidth 缩放，不铺满屏幕）。
    """
    im = Image.open(ASSETS / "splash.png").convert("RGBA")
    w, h = im.size
    for corner in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
        assert im.getpixel(corner)[3] == 0, (
            f"角 {corner} 不透明 —— 启动图自带底色，会与 backgroundColor 叠成两层色"
        )
    # 中间必须有内容（避免把一张全透明图当成"透明底"通过）
    hist = im.getchannel("A").histogram()
    assert sum(hist[240:256]) > im.size[0] * im.size[1] * 0.1, "splash 中央没有可见内容"


# --------------------------------------------------------------------------
# 反面对照：证明守卫真的会拒绝，而不是恒通过
# --------------------------------------------------------------------------

def test_ink_guard_rejects_thin_line_icon(tmp_path: Path, gen) -> None:
    """把守卫喂给一个「细线图标」，它必须拒绝。

    没有这条，无法区分「守卫在工作」和「守卫永远通过」。
    这里复刻旧版图标的失败形态：1024 画布上只画几根细线。
    """
    thin = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    d = ImageDraw.Draw(thin)
    for r in (300, 200):
        d.ellipse([512 - r, 512 - r, 512 + r, 512 + r], outline=(218, 179, 125, 255), width=3)
    d.line([212, 512, 812, 512], fill=(218, 179, 125, 255), width=3)
    path = tmp_path / "adaptive-icon.png"
    thin.save(path)

    with pytest.raises(SystemExit, match="前景占比"):
        gen.check([path])


def test_ink_guard_accepts_a_solid_subject(tmp_path: Path, gen) -> None:
    """对照的另一半：实心主体必须通过，否则守卫过于严格、会误杀正常设计稿。"""
    solid = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    ImageDraw.Draw(solid).ellipse([170, 170, 854, 854], fill=(90, 70, 40, 255))
    path = tmp_path / "adaptive-icon.png"
    solid.save(path)

    gen.check([path])  # 不应抛异常
