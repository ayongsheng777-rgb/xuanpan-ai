#!/usr/bin/env python
"""把玄盘 AI 移动端的 UI 设计代码导出成一个自包含的资料包，供其他智能体分析。

为什么需要这个脚本，而不是手工打包：
    手工打包的问题是**没有守卫**。UI 加了新组件、新页面，包不会自动知道，
    于是"导出物"与"源码"静默漂移 —— 收到包的一方会基于一份不完整的材料
    下结论，而双方都看不出问题。本脚本对 apps/mobile 下所有源码做**归档完整性自检**：
    凡未被任何一卷收录、又不在 EXCLUDED 白名单里的文件，一律报错退出。

包结构（默认 dist/ui-design-export/）：
    README.md                  导读（手写，来自 docs/ 下的源文档）
    00-design-tokens.md        设计令牌
    01-components-base.md      基础组件
    02-components-domain.md    领域组件（罗盘 / 术数结果）
    03-pages-compass.md        罗盘域页面（核心链路）
    04-pages-divination.md     命盘 / 占测 / 三式页面
    05-pages-system.md         导航与系统页
    06-content-copy.md         界面讲解文案
    07-ui-logic.md             UI 侧几何 / 样式 / 状态逻辑
    08-api-contract.md         后端字段契约（界面数据的来源）
    MANIFEST.md                清单与校验指纹（自动生成）
    snapshots/                 真机视口渲染快照（PNG）
    source/                    UI 源码副本（保留原目录结构）
    references/                上游设计规范文档

用法：
    "$PY" scripts/export_ui_design.py                    # 生成到 dist/ui-design-export/
    "$PY" scripts/export_ui_design.py --zip              # 同时打 zip
    "$PY" scripts/export_ui_design.py --out D:/tmp/exp   # 指定输出目录
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOBILE = REPO / "apps" / "mobile"
SNAPSHOT_DIR = REPO / "docs" / "ui-render"
INTRO_SRC = REPO / "docs" / "玄盘 AI — UI 设计导出导读.md"

# 上游设计规范：UI 的约束来自这些文档，脱离它们无法判断某个界面"为什么长这样"
REFERENCE_DOCS = (
    "玄盘 AI — 产品基线规范.md",
    "玄盘 AI — UI、模型配置与网络线路设计规范.md",
    "玄盘_AI_V2_产品改造与实施规范.md",
)

# 随包附带的移动端工程配置（主题色 / 启动图 / 依赖版本都在这里）
EXTRA_ROOT_FILES = (
    "package.json",
    "app.json",
    "app.config.js",
    "tsconfig.json",
    "README.md",
)


@dataclass(frozen=True)
class Volume:
    """一卷 Markdown = 一个可独立阅读的主题。"""

    slug: str
    title: str
    blurb: str
    files: tuple[str, ...]

    @property
    def filename(self) -> str:
        return f"{self.slug}.md"


VOLUMES: tuple[Volume, ...] = (
    Volume(
        slug="00-design-tokens",
        title="设计令牌（Design Tokens）",
        blurb=(
            "全 App 唯一的色值 / 间距 / 字号 / 圆角 / 阴影真源。"
            "五色由演示图逐像素中位数取样实测得出，不是随手挑的色板；"
            "`instrument` 是罗盘域专用的深色仪器色域，与暖色中性阶双轨并存。"
            "组件内禁止出现硬编码色值（对应 RULE-005「规则不散落」）。"
        ),
        files=("src/theme/tokens.ts",),
    ),
    Volume(
        slug="01-components-base",
        title="基础组件",
        blurb=(
            "与术数领域无关的通用 UI 原件：排版、容器、按钮、标签、横幅、分段切换、讲解入口。"
            "这些组件决定了全 App 的视觉基调，也是判断「设计系统是否被真正执行」的第一手材料。"
        ),
        files=(
            "src/components/AppText.tsx",
            "src/components/Screen.tsx",
            "src/components/Card.tsx",
            "src/components/Chip.tsx",
            "src/components/Banner.tsx",
            "src/components/SegmentedTabs.tsx",
            "src/components/HelpButton.tsx",
            "src/components/usePressScale.ts",
        ),
    ),
    Volume(
        slug="02-components-domain",
        title="领域组件",
        blurb=(
            "承载术数语义的组件。读数与几何的呈现方式直接关系到「用户会不会误读」，"
            "例如：罗盘盘式的图层与配色角色、坐向修正的环形选择器、"
            "识别步骤列表（只由真实返回驱动）、断卦结论的中性色规则。"
        ),
        files=(
            "src/components/CompassDial.tsx",
            "src/components/CompassAdjuster.tsx",
            "src/components/StepList.tsx",
            "src/components/DuanCard.tsx",
            "src/components/FactList.tsx",
        ),
    ),
    Volume(
        slug="03-pages-compass",
        title="罗盘域页面（核心链路）",
        blurb=(
            "产品主链路的完整界面序列：首页 → 拍摄/相册 → 识别步骤 → 用户确认 → 会话详情 → AI 报告，"
            "外加传感器测量与手动调节两条辅助路径。这一卷是理解「产品到底在做什么」的关键，"
            "也集中了深色仪器风与浅色暖调双轨的边界。"
        ),
        files=(
            "app/_layout.tsx",
            "app/(tabs)/index.tsx",
            "app/scan.tsx",
            "app/confirm/[sessionId].tsx",
            "app/session/[sessionId].tsx",
            "app/report/[sessionId].tsx",
            "app/sensors.tsx",
            "app/adjust.tsx",
        ),
    ),
    Volume(
        slug="05-pages-system",
        title="命盘 / 占测 / 三式页面",
        blurb=(
            "术数计算结果的呈现层：八字命盘、六爻与灵签、三式（奇门 / 六壬 / 太乙）、"
            "黄历择日、罗盘牌库。这些页面的共性是「信息密度高、字段多」，"
            "因此空态、缺项（`null` → 「未定」）与长文案折行是主要设计难点。"
        ),
        files=(
            "app/chart.tsx",
            "app/divine.tsx",
            "app/sanshi.tsx",
            "app/almanac.tsx",
            "app/templates.tsx",
        ),
    ),
    Volume(
        slug="04-pages-divination",
        title="导航与系统页",
        blurb=(
            "底栏骨架（决定信息架构）、测盘、分析、历史、我的，以及罗盘校准。"
            "底栏当前是「罗盘 ｜ 测盘 ｜ 分析 ｜ 历史 ｜ 我的」——"
            "命盘与占测已并入「分析」内页，理由见 `(tabs)/_layout.tsx` 顶部注释。"
        ),
        files=(
            "app/(tabs)/_layout.tsx",
            "app/(tabs)/test.tsx",
            "app/(tabs)/analysis.tsx",
            "app/(tabs)/history.tsx",
            "app/(tabs)/mine.tsx",
            "app/calibrate.tsx",
        ),
    ),
    Volume(
        slug="06-content-copy",
        title="界面讲解文案",
        blurb=(
            "各页「帮助」入口展开的操作说明与运作原理讲解。"
            "它是产品「把黑箱讲清楚」这一主张的落地物，"
            "也是判断文案与界面是否一致（有没有把已删除的按钮写进说明）的唯一依据。"
        ),
        files=("src/content/help.ts",),
    ),
    Volume(
        slug="07-ui-logic",
        title="UI 侧逻辑：几何 / 样式 / 状态",
        blurb=(
            "不是纯视觉，但直接决定界面看起来什么样：环形与盘面的几何计算、"
            "盘面配色角色、迷你曲线、传感器质量判据、异步状态机、"
            "以及三式的九宫与十二宫布局。这些模块被刻意做成不依赖 React Native 的纯函数，"
            "才能在无设备的条件下被真跑验证。"
        ),
        files=(
            "src/lib/compassDial.ts",
            "src/lib/ring24.ts",
            "src/lib/dialStyle.ts",
            "src/lib/sparkline.ts",
            "src/lib/sensorQuality.ts",
            "src/lib/qimenLayout.ts",
            "src/lib/liurenLayout.ts",
            "src/lib/taiyiLayout.ts",
            "src/lib/useAsync.ts",
            "src/lib/date.ts",
            "src/lib/apiCandidates.ts",
            "src/services/useSensors.ts",
        ),
    ),
    Volume(
        slug="08-api-contract",
        title="后端字段契约",
        blurb=(
            "界面上的每个数字都来自后端，`types.ts` 与后端 schema 一一对应。"
            "看这一卷能回答「这个格子里的值是谁算的、字段名叫什么、缺数据时是什么形态」——"
            "也是判断前端有没有自己算术数的依据（结论：没有，唯一例外是二十四山的顺序与山心角）。"
        ),
        files=(
            "src/api/types.ts",
            "src/api/client.ts",
            "src/types/env.d.ts",
        ),
    ),
)

# 归档完整性自检只覆盖界面代码（app/ 与 src/），scripts/ 是工具目录、不参与。
# apps/mobile/scripts/ 下的 *_probe.ts 是校验桩：它们把几何与配色的**期望值**写成
# 可执行断言，给 pytest 做跨语言比对用（见 tests/mobile/）。对分析设计系统有参考价值，
# 故整体复制进 source/scripts/，但不单独成卷 —— 它们不是界面代码。


def sha12(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def git_rev() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout.strip()
    except Exception:
        return "(非 git 工作区)"


def git_dirty() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO,
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(out.stdout.strip())
    except Exception:
        return False


def lang_of(path: str) -> str:
    if path.endswith(".tsx"):
        return "tsx"
    if path.endswith(".ts"):
        return "ts"
    if path.endswith(".json"):
        return "json"
    if path.endswith(".js"):
        return "js"
    return "text"


def read_text(path: Path) -> str:
    """统一行尾。源码里混入 CRLF 会让导出的 Markdown 在别处显示成多一个空行。"""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip() + "\n"


def code_block(text: str, lang: str) -> str:
    """代码里若本身含三反引号，围栏必须加长，否则内容会被截断成两段。"""
    longest = 0
    run = 0
    for ch in text:
        if ch == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    fence = "`" * max(3, longest + 1)
    return f"{fence}{lang}\n{text}{fence}\n"


def render_volume(vol: Volume) -> tuple[str, list[tuple[str, int, int, str]]]:
    """生成一卷 Markdown，同时回传每个文件的行数/字节/指纹供 MANIFEST 使用。"""
    entries: list[tuple[str, int, int, str]] = []
    blocks: list[str] = []
    toc: list[str] = []

    for rel in vol.files:
        path = MOBILE / rel
        if not path.exists():
            raise SystemExit(f"[导出失败] 卷 {vol.slug} 声明的文件不存在：apps/mobile/{rel}")
        raw = path.read_bytes()
        text = read_text(path)
        lines = text.count("\n")
        entries.append((rel, lines, len(raw), sha12(raw)))
        toc.append(f"- `apps/mobile/{rel}` — {lines} 行")
        blocks.append(
            "\n---\n\n"
            f"## `apps/mobile/{rel}`\n\n"
            f"> {lines} 行 ｜ {len(raw):,} 字节\n\n"
            + code_block(text, lang_of(rel))
        )

    total_lines = sum(e[1] for e in entries)
    total_bytes = sum(e[2] for e in entries)

    head = (
        f"# {vol.title}\n\n"
        f"> {vol.blurb}\n\n"
        f"> 📄 **本卷由 `scripts/export_ui_design.py` 自动生成，请勿直接编辑。**\n"
        f"> 它只是源码的镜像；要改内容请改源码后重跑脚本，否则两者会不一致。\n\n"
        f"**本卷含 {len(vol.files)} 个文件，合计 {total_lines:,} 行 / {total_bytes:,} 字节。**\n\n"
        f"## 文件清单\n\n" + "\n".join(toc) + "\n"
    )
    return head + "".join(blocks), entries


def copy_tree(src: Path, dst: Path) -> int:
    """复制源码副本（保留目录结构）。只收源码与配置，不收 node_modules / 构建产物。"""
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    n = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        parts = set(rel.parts)
        if parts & {"node_modules", ".expo", "android", "ios", "dist", "build"}:
            continue
        if path.suffix in {".pyc", ".map", ".hbc"}:
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        n += 1
    return n


def assert_no_orphans() -> list[str]:
    """归档完整性自检 —— 这是本脚本存在的核心理由。

    只检查 app/ 与 src/：漏掉一个界面文件，收到包的一方就会基于不完整的材料下结论，
    而这种缺失双方都看不出来。apps/mobile/scripts/ 是校验桩工具目录，不参与本守卫。
    """
    claimed: set[str] = set()
    for vol in VOLUMES:
        claimed.update(vol.files)

    found: set[str] = set()
    for base in ("app", "src"):
        root = MOBILE / base
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".ts", ".tsx"}:
                continue
            if set(path.relative_to(MOBILE).parts) & {"node_modules", ".expo", "android", "ios"}:
                continue
            found.add(str(path.relative_to(MOBILE)).replace("\\", "/"))

    orphans = sorted(found - claimed)
    missing = sorted(claimed - found)
    problems = []
    if orphans:
        problems.append(
            "以下源码未被任何一卷收录（导出包会不完整）：\n  " + "\n  ".join(orphans)
        )
    if missing:
        problems.append(
            "以下文件被某卷声明，但在磁盘上找不到：\n  " + "\n  ".join(missing)
        )
    return problems


def build(out_root: Path, force: bool = False) -> dict[str, object]:
    out_root = out_root.resolve()
    if out_root.exists() and any(out_root.iterdir()):
        # 为什么不默认自动清除：在本机 WorkBuddy 环境下，删除操作会被
        # `sitecustomize` 的 safe-delete 钩子接管，**只有系统 Temp 之下的路径被豁免**。
        # 导出包有近百个文件，一次 rmtree 就会累计超过「单次工具调用 >50 个」的阈值，
        # 钩子随即 raise SystemExit(1) —— 症状是脚本半途静默停止，而不是给出可读错误。
        # 所以把"要不要抹掉旧包"交给调用者显式决定。
        if not force:
            raise SystemExit(
                f"[输出目录已存在] {out_root}\n"
                "为避免误删，本脚本不自动清除已有目录。请二选一：\n"
                "  1) 先自行清理它（注意：本环境下一次性删除大量文件会触发\n"
                "     safe-delete 批量守卫，建议分批删，或用同盘改名先挪走）；\n"
                "  2) 加 --force，让脚本清除后重建。"
            )
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    problems = assert_no_orphans()
    if problems:
        raise SystemExit("[导出失败] 归档完整性自检未通过：\n\n" + "\n\n".join(problems))
    print("归档完整性自检：通过（app/ 与 src/ 下无未收录源码）")

    volume_entries: dict[str, list[tuple[str, int, int, str]]] = {}
    for vol in VOLUMES:
        md, entries = render_volume(vol)
        (out_root / vol.filename).write_text(md, encoding="utf-8", newline="\n")
        volume_entries[vol.filename] = entries
        print(f"  {vol.filename:<28} {len(entries):>2} 文件  {sum(e[1] for e in entries):>6,} 行")

    # 导读
    intro_bytes = b""
    if INTRO_SRC.exists():
        intro_bytes = INTRO_SRC.read_bytes()
        (out_root / "README.md").write_bytes(intro_bytes)
        print(f"  {'README.md':<28} 导读（来自 docs/）")
    else:
        print(f"  ⚠️ 未找到导读源文档：{INTRO_SRC}")

    # 快照
    shots = sorted(SNAPSHOT_DIR.glob("*.png")) if SNAPSHOT_DIR.exists() else []
    snap_out = out_root / "snapshots"
    snap_out.mkdir()
    shot_entries = []
    for png in shots:
        shutil.copy2(png, snap_out / png.name)
        data = png.read_bytes()
        shot_entries.append((png.name, len(data), sha12(data)))
    print(f"  {'snapshots/':<28} {len(shots):>2} 张渲染快照")

    # 源码副本
    src_files = copy_tree(MOBILE / "app", out_root / "source" / "app")
    src_files += copy_tree(MOBILE / "src", out_root / "source" / "src")
    src_files += copy_tree(MOBILE / "scripts", out_root / "source" / "scripts")
    for name in EXTRA_ROOT_FILES:
        p = MOBILE / name
        if p.exists():
            shutil.copy2(p, out_root / "source" / name)
            src_files += 1
    print(f"  {'source/':<28} {src_files:>2} 个文件（保留原目录结构）")

    # 上游规范
    ref_out = out_root / "references"
    ref_out.mkdir()
    ref_entries = []
    for name in REFERENCE_DOCS:
        p = REPO / "docs" / name
        if p.exists():
            shutil.copy2(p, ref_out / name)
            data = p.read_bytes()
            ref_entries.append((name, len(data), sha12(data)))
    print(f"  {'references/':<28} {len(ref_entries):>2} 份上游规范")

    # MANIFEST
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    rev = git_rev()
    dirty = git_dirty()
    lines: list[str] = [
        "# MANIFEST —— 玄盘 AI UI 设计导出包",
        "",
        f"- 生成时间：{now}",
        f"- 来源 commit：`{rev}`" + ("　⚠️ **生成时工作区有未提交改动**" if dirty else ""),
        f"- 导出脚本：`scripts/export_ui_design.py`",
        "",
        "> 校验用途：若你手里的源码与下表指纹不一致，说明包与源码已经漂移，",
        "> 结论需要重新核对。指纹是文件原始字节（未经行尾归一）的 SHA256 前 12 位。",
        "",
        "## 卷",
        "",
        "| 文件 | 文件数 | 行数 |",
        "|---|---|---|",
    ]
    for vol in VOLUMES:
        e = volume_entries[vol.filename]
        lines.append(f"| `{vol.filename}` | {len(e)} | {sum(x[1] for x in e):,} |")

    lines += ["", "## 源码文件指纹", "", "| 路径（相对 `apps/mobile/`） | 行数 | 字节 | SHA256/12 |", "|---|---|---|---|"]
    for vol in VOLUMES:
        for rel, n_lines, n_bytes, digest in volume_entries[vol.filename]:
            lines.append(f"| `{rel}` | {n_lines:,} | {n_bytes:,} | `{digest}` |")

    if shot_entries:
        lines += ["", "## 渲染快照", "", "| 文件 | 字节 | SHA256/12 |", "|---|---|---|"]
        for name, n_bytes, digest in shot_entries:
            lines.append(f"| `snapshots/{name}` | {n_bytes:,} | `{digest}` |")

    if ref_entries:
        lines += ["", "## 上游规范", "", "| 文件 | 字节 | SHA256/12 |", "|---|---|---|"]
        for name, n_bytes, digest in ref_entries:
            lines.append(f"| `references/{name}` | {n_bytes:,} | `{digest}` |")

    (out_root / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    total_files = sum(1 for f in out_root.rglob("*") if f.is_file())
    total_bytes = sum(f.stat().st_size for f in out_root.rglob("*") if f.is_file())
    print(f"\n输出目录：{out_root}")
    print(f"合计 {total_files} 个文件 / {total_bytes / 1024 / 1024:.1f} MB")
    return {"out": out_root, "files": total_files, "bytes": total_bytes}


def make_zip(out_root: Path) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d")
    zip_path = out_root.parent / f"玄盘AI-UI设计导出-{stamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(out_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(out_root.parent))
    size = zip_path.stat().st_size
    print(f"\nzip：{zip_path}（{size / 1024 / 1024:.1f} MB）")
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description="导出玄盘 AI 移动端 UI 设计代码")
    ap.add_argument("--out", default=str(REPO / "dist" / "ui-design-export"), help="输出目录")
    ap.add_argument("--zip", action="store_true", help="同时打包 zip")
    ap.add_argument(
        "--force",
        action="store_true",
        help="输出目录已存在时清除后重建（默认报错退出，不会自动删除）",
    )
    args = ap.parse_args()

    result = build(Path(args.out), force=args.force)
    if args.zip:
        make_zip(result["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
