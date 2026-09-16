"""Gate 1 评测 —— 罗盘识别可用性。

Gate 1 判据（生产路线报告 §5）：
    普通用户拿手机拍一张真实罗盘照片，系统能否稳定识别鱼丝线对应的二十四山，
    并让用户在 3 秒内确认。

本脚本把其中**可量化**的部分做成可复现的实测，两个子命令语义严格分开：

  synthetic   合成退化扫描。随时可跑，用于定位识别失效的边界
              （尺寸 / 模糊 / 噪点 / 斜拍 / 反光 / 组合退化）。
              **它不能代替 Gate 1** —— 合成图没有真实罗盘的印刷细节、
              材质反光、手握遮挡与背景杂物。把它的结果当作 Gate 1 通过
              是本项目最容易犯的自我欺骗。

  photos      真实照片评测。这才是 Gate 1 的正式判据，需自备照片与标签。

不可量化项：「3 秒内确认」是交互指标，headless 测不了，需真机 + 人工计时。
脚本会把它显式列为 [需真机]，不会伪造。

用法（[Host]）：
    # 合成退化扫描
    python scripts/gate1_eval.py synthetic
    python scripts/gate1_eval.py synthetic --out docs/gate1-合成退化扫描.md

    # 真实照片评测（Gate 1 正式判据）
    python scripts/gate1_eval.py photos --dir real_photos --labels real_photos/labels.csv

标签文件格式（CSV，逗号分隔，**必须含表头**）：
    filename,angle,sitting
    IMG_001.jpg,177.0,
    IMG_002.jpg,,午
    IMG_003.jpg,92.5,卯

    - `angle` 与 `sitting` 至少给一个。`angle` 优先；只给 `sitting` 时按该山心角作真值。
    - 两者都给且互相矛盾时，该行会被标为「标签冲突」并跳过 —— 真值本身不可信
      的样本没有任何评测价值。
    - filename 是相对于 --dir 的路径。

退出码：0 = 跑完且达标；1 = 跑完但未达标；2 = 无法运行（缺照片或标签）。
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
for rel in ("services/api", "services/ai", "services/vision", "packages/fortune-core"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from fortune_core.mountain24 import degree_of, mountain_at, opposite  # noqa: E402
from xuanpan_vision.pipeline import analyze_compass  # noqa: E402
from xuanpan_vision.testing import angle_error, expected_mountains  # noqa: E402

#：建议验收阈值。**这是建议值，不是权威判据** —— Gate 1 的最终阈值由阿勇裁定。
DEFAULT_ACCEPT = 0.80


# ======================================================================
# 单个样本的结果
# ======================================================================


@dataclass
class CaseResult:
    """一个样本的评测结果。字段全部来自真实调用，不含任何推算。"""

    label: str
    truth_angle: float
    accepted: bool = False
    pair_ok: bool = False            # 候选对 == 真值对（与单测同一判据）
    truth_covered: bool = False      # 真值山名至少出现在候选中（宽松）
    angle_err: float | None = None   # 角度误差（0~90°）
    candidates: tuple[str, ...] = ()
    needs_confirm: bool | None = None
    #：被拒原因。取自 `uncertain_regions` —— `CompassVisionResult.rejected()`
    #: 把 reason 放在这里（不是 warnings）。读错会让「被拒」看起来像「无原因的失败」。
    reason: str = ""
    warnings: tuple[str, ...] = ()
    note: str = ""                   # 标签侧的说明（如「标签冲突」）
    error: str = ""                  # 跑挂时的异常（与「被拒」不同，要分开计）

    @property
    def ok(self) -> bool:
        return self.pair_ok

    @property
    def crashed(self) -> bool:
        return bool(self.error)


def evaluate_one(
    label: str,
    truth_angle: float,
    source: Any,
    *,
    note: str = "",
) -> CaseResult:
    """跑一次识别并与真值比对。

    被拒（识别不出）与跑挂（异常）分开记录：前者是识别能力问题，
    后者是代码缺陷，混在一起会掩盖 bug。
    """
    res = CaseResult(label=label, truth_angle=truth_angle, note=note)
    try:
        result, _ = analyze_compass(source)
    except Exception as exc:  # noqa: BLE001 - 评测脚本必须跑完整个扫描
        res.error = f"{type(exc).__name__}: {exc}"
        return res

    res.accepted = bool(result.compass_detected)
    res.needs_confirm = result.needs_user_confirmation
    names = tuple(c.name for c in result.mountain_candidates)
    res.candidates = names
    res.warnings = tuple(result.warnings)
    # 原因优先取 uncertain_regions：rejected() 把 reason 存在那里，warnings 往往为空
    res.reason = "；".join(result.uncertain_regions) or "；".join(result.warnings)

    want = expected_mountains(truth_angle)
    got = set(names)
    res.pair_ok = got == want
    res.truth_covered = mountain_at(truth_angle).name in got

    # 角度误差：只取「名字等于真值山」的那个候选，避免拿对宫项去比
    truth_name = mountain_at(truth_angle).name
    for c in result.mountain_candidates:
        if c.name == truth_name and c.angle is not None:
            res.angle_err = angle_error(float(c.angle), truth_angle)
            break

    return res


# ======================================================================
# 合成退化扫描
# ======================================================================


@dataclass
class Tier:
    """一档拍摄条件。name 会直接出现在报告里，要写成人能看懂的话。"""

    name: str
    renders: Callable[[float], Any]
    hint: str = ""


def build_tiers() -> list[Tier]:
    from PIL import ImageDraw

    from xuanpan_vision.testing import render_compass as rc

    def renderer(**kw: Any) -> Callable[[float], Any]:
        return lambda angle: rc(thread_angle=angle, **kw)

    def with_dark_rect(box: tuple[int, int, int, int], value: int = 20) -> Callable[[float], Any]:
        """渲染后叠一块深色矩形，模拟桌面边缘 / 阴影 / 手边物件。

        render_compass 没有这个参数，属**新增的评测条件** —— 它测的不是
        几何算法，而是前景掩膜在真实背景下的抗污染能力。
        """

        def _render(angle: float) -> Any:
            im = rc(size=900, thread_angle=angle)
            ImageDraw.Draw(im).rectangle(list(box), fill=value)
            return im

        return _render

    return [
        Tier("清晰·大图", renderer(size=1200), "理想条件，作为上限基线"),
        Tier("标准", renderer(size=900), "默认参数"),
        Tier("低分辨率", renderer(size=480), "老机型 / 缩放后上传"),
        Tier("噪点", renderer(size=900, noise=8.0), "弱光高 ISO"),
        Tier("失焦", renderer(size=900, blur=2.0), "手抖 / 未对焦"),
        Tier("轻斜拍", renderer(size=900, squash=0.90, tilt=6.0), "略微俯拍"),
        Tier("重斜拍", renderer(size=900, squash=0.70, tilt=25.0), "明显斜角拍摄"),
        Tier("反光", renderer(size=900, glare_box=(520, 240, 760, 430)), "盘面玻璃反光"),
        Tier(
            "弱对比",
            renderer(size=900, background=205, body=185, inner=192, tick_value=150),
            "盘体与背景颜色接近（托盘同色系）",
        ),
        Tier(
            "背景杂物·贴边阴影",
            with_dark_rect((0, 400, 60, 500)),
            "画面左缘深色物件（桌面边 / 阴影）",
        ),
        Tier(
            "背景杂物·角落物件",
            with_dark_rect((60, 60, 300, 300)),
            "角落深色物件（手边物品 / 包角）",
        ),
        Tier(
            "组合·随手拍",
            renderer(size=640, noise=6.0, blur=1.2, squash=0.82, tilt=12.0),
            "最接近真实手持拍摄的合成近似",
        ),
    ]


#：扫描用的真值角度。含四正、四隅与一个非整角（177°，沿用冒烟脚本的值）。
SWEEP_ANGLES: tuple[float, ...] = (0.0, 15.0, 45.0, 90.0, 135.0, 177.0, 270.0, 345.0)


def run_synthetic(args: argparse.Namespace) -> int:
    print("=" * 72)
    print("Gate 1 · 合成退化扫描  —— ⚠️ 本结果不能代替真实照片评测")
    print("=" * 72)
    print(f"角度集：{list(SWEEP_ANGLES)}")
    print(f"档位数：{len(build_tiers())}    每档样本：{len(SWEEP_ANGLES)}\n")

    sections: list[str] = []
    overall: list[CaseResult] = []

    header = f"{'档位':<14}{'命中':>7}{'覆盖':>7}{'角度中位误差':>14}  说明"
    print(header)
    print("-" * 72)

    for tier in build_tiers():
        cases: list[CaseResult] = []
        for angle in SWEEP_ANGLES:
            try:
                img = tier.renders(angle)
            except Exception as exc:  # noqa: BLE001
                cases.append(
                    CaseResult(
                        label=f"{tier.name}@{angle:g}°",
                        truth_angle=angle,
                        error=f"渲染失败 {type(exc).__name__}: {exc}",
                    )
                )
                continue
            cases.append(evaluate_one(f"{tier.name}@{angle:g}°", angle, img))

        overall.extend(cases)
        n = len(cases)
        pairs = sum(1 for c in cases if c.pair_ok)
        covers = sum(1 for c in cases if c.truth_covered)
        errs = [c.angle_err for c in cases if c.angle_err is not None]
        med = f"{statistics.median(errs):.2f}°" if errs else "—"

        print(f"{tier.name:<14}{pairs:>4}/{n:<3}{covers:>4}/{n:<3}{med:>14}  {tier.hint}")
        sections.append(_tier_section(tier, cases))

    # ---------------- 汇总 ----------------
    n = len(overall)
    pairs = sum(1 for c in overall if c.pair_ok)
    covers = sum(1 for c in overall if c.truth_covered)
    crashes = sum(1 for c in overall if c.crashed)
    accepted = sum(1 for c in overall if c.accepted)
    false_ok = accepted - pairs
    errs = [c.angle_err for c in overall if c.angle_err is not None]

    print("-" * 72)
    print(f"合计 {n} 例：整对命中 {pairs} ({pairs / n:.1%})，真值覆盖 {covers} ({covers / n:.1%})")
    print(f"       识别到盘体 {accepted} ({accepted / n:.1%})，异常 {crashes}")
    if false_ok:
        print(
            f"       ⚠️ 假阳性 {false_ok}（{false_ok / n:.1%}）：给出了山名候选但都不对"
        )
    if errs:
        print(
            f"       角度误差 中位 {statistics.median(errs):.2f}° / "
            f"最大 {max(errs):.2f}°"
        )
    if crashes:
        print("\n⚠️ 存在异常（不是「识别不出」，是代码缺陷）：")
        for c in overall:
            if c.crashed:
                print(f"   - {c.label}: {c.error}")

    print(
        "\n⚠️ 提醒：以上是合成图结果。合成图缺少真实罗盘的印刷细节、材质反光、\n"
        "   手握遮挡与背景杂物。**Gate 1 未因此通过**，需跑 `photos` 子命令。"
    )

    if args.out:
        _write_report(
            Path(args.out),
            title="Gate 1 · 合成退化扫描",
            intro=_synthetic_intro(),
            sections=sections,
            summary=_summary_block(overall, args),
            verdict=_synthetic_verdict(overall, args),
        )
        print(f"\n报告已写入：{args.out}")

    return 1 if crashes else 0


# ======================================================================
# 真实照片评测（Gate 1 正式判据）
# ======================================================================


@dataclass
class Label:
    path: Path
    angle: float
    note: str = ""


@dataclass
class LoadOutcome:
    labels: list[Label] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def load_labels(csv_path: Path, photo_dir: Path) -> LoadOutcome:
    """读标签。**任何可疑的标签都不猜，直接挑出来报告。**"""
    out = LoadOutcome()
    if not csv_path.exists():
        out.problems.append(f"标签文件不存在：{csv_path}")
        return out

    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = {c.strip().lower() for c in (reader.fieldnames or [])}
        if "filename" not in cols:
            out.problems.append(f"标签缺少 filename 列，实际列：{sorted(cols)}")
            return out

        for i, row in enumerate(reader, start=2):
            raw = {str(k).strip().lower(): (v or "").strip() for k, v in row.items() if k}
            name = raw.get("filename", "")
            if not name:
                out.problems.append(f"第 {i} 行：filename 为空，跳过")
                continue

            path = photo_dir / name
            if not path.exists():
                out.problems.append(f"第 {i} 行：文件不存在 {path}")
                continue

            angle_txt = raw.get("angle", "")
            sitting = raw.get("sitting", "")

            angle: float | None = None
            if angle_txt:
                try:
                    angle = float(angle_txt)
                except ValueError:
                    out.problems.append(f"第 {i} 行：angle={angle_txt!r} 不是数字，跳过")
                    continue

            if sitting:
                try:
                    sit_angle = degree_of(sitting)
                except Exception:  # noqa: BLE001
                    out.problems.append(f"第 {i} 行：sitting={sitting!r} 不是合法山名，跳过")
                    continue
                if angle is not None and abs((angle - sit_angle + 180.0) % 360.0 - 180.0) > 0.01:
                    out.problems.append(
                        f"第 {i} 行：标签自相矛盾 —— angle={angle:g}° 与 sitting={sitting}"
                        f"（山心角 {sit_angle:g}°）不一致，跳过。"
                        "真值本身不可信的样本没有评测价值。"
                    )
                    continue
                angle = sit_angle if angle is None else angle
            elif angle is None:
                out.problems.append(f"第 {i} 行：angle 与 sitting 至少给一个，跳过")
                continue

            note = raw.get("note", "") or (f"标签坐山={sitting}" if sitting else "")
            out.labels.append(Label(path=path, angle=float(angle), note=note))

    return out


def run_photos(args: argparse.Namespace) -> int:
    photo_dir = Path(args.dir)
    print("=" * 72)
    print("Gate 1 · 真实照片评测（正式判据）")
    print("=" * 72)
    print(f"照片目录：{photo_dir}")

    if not photo_dir.is_dir():
        print(f"\n✗ 目录不存在：{photo_dir}")
        _print_photo_howto()
        return 2

    csv_path = Path(args.labels) if args.labels else photo_dir / "labels.csv"
    loaded = load_labels(csv_path, photo_dir)
    for p in loaded.problems:
        print(f"  ✗ {p}")

    if not loaded.labels:
        print(f"\n✗ 没有可用样本（标签：{csv_path}）")
        _print_photo_howto()
        return 2

    print(f"样本数：{len(loaded.labels)}\n")
    cases: list[CaseResult] = []
    for lab in loaded.labels:
        img = _load_photo(lab.path)
        if isinstance(img, str):
            cases.append(
                CaseResult(
                    label=lab.path.name, truth_angle=lab.angle,
                    note=lab.note, error=img,
                )
            )
            continue
        cases.append(evaluate_one(lab.path.name, lab.angle, img, note=lab.note))

    pairs = sum(1 for c in cases if c.pair_ok)
    n = len(cases)
    rate = pairs / n

    print(f"{'样本':<28}{'真值':>9}{'候选':>14}{'角误差':>9}  结果")
    print("-" * 72)
    for c in cases:
        truth = f"{c.truth_angle:g}°"
        cand = "/".join(c.candidates) if c.candidates else "—"
        err = f"{c.angle_err:.2f}°" if c.angle_err is not None else "—"
        if c.crashed:
            mark = f"异常 {c.error[:28]}"
        elif c.pair_ok:
            mark = "命中"
        elif c.truth_covered:
            mark = "覆盖（多/少候选）"
        elif c.accepted:
            mark = "识别到盘但山名不符"
        else:
            mark = f"未识别 {c.reason[:24]}"
        print(f"{c.label[:27]:<28}{truth:>9}{cand:>14}{err:>9}  {mark}")

    print("-" * 72)
    print(f"坐向整对命中：{pairs}/{n} = {rate:.1%}    建议阈值 {args.accept:.0%}")
    errs = [c.angle_err for c in cases if c.angle_err is not None]
    if errs:
        print(f"角度误差：中位 {statistics.median(errs):.2f}° / 最大 {max(errs):.2f}°")
    crashes = sum(1 for c in cases if c.crashed)
    if crashes:
        print(f"⚠️ 异常 {crashes} 例（代码缺陷，非识别能力问题）")

    passed = rate >= args.accept and crashes == 0
    print(f"\n量化部分判定：{'达标' if passed else '未达标'}")
    print("[需真机] 「3 秒内确认」为交互指标，须在真机上人工计时，本脚本无法测量。")

    if args.out:
        _write_report(
            Path(args.out),
            title="Gate 1 · 真实照片评测",
            intro=_photos_intro(photo_dir, csv_path, n),
            sections=[_photos_table(cases)],
            summary=_summary_block(cases, args),
            verdict=_photos_verdict(cases, args),
        )
        print(f"\n报告已写入：{args.out}")

    return 0 if passed else 1


def _load_photo(path: Path) -> Any:
    """读照片。失败返回**错误说明字符串**（与成功返回 Image 区分）。"""
    try:
        from PIL import Image

        with Image.open(path) as im:
            return im.convert("RGB").copy()
    except Exception as exc:  # noqa: BLE001
        return f"读取失败 {type(exc).__name__}: {exc}"


def _print_photo_howto() -> None:
    print(
        "\n怎么准备真实照片样本：\n"
        "  1. 建目录 real_photos/，放真实罗盘照片（手机拍的原图，不要先修图）\n"
        "  2. 建 real_photos/labels.csv，第一行表头固定为：\n"
        "         filename,angle,sitting\n"
        "     angle = 鱼丝线真值角度（0=北，顺时针）；不知道角度就填 sit 山名。\n"
        "  3. 重跑本命令\n\n"
        "  拍照建议覆盖这几类，否则测不出边界：\n"
        "    - 光线充足正面拍（基准）\n"
        "    - 弱光 / 反光\n"
        "    - 斜拍（明显俯角）\n"
        "    - 盘体与背景同色系\n"
        "    - 手指遮挡盘沿\n"
        "  每类至少 3 张，合计 ≥ 15 张，样本太少时成功率没有统计意义。"
    )


# ======================================================================
# 报告输出
# ======================================================================


def _tier_section(tier: Tier, cases: list[CaseResult]) -> str:
    n = len(cases)
    pairs = sum(1 for c in cases if c.pair_ok)
    covers = sum(1 for c in cases if c.truth_covered)
    errs = [c.angle_err for c in cases if c.angle_err is not None]
    med = f"{statistics.median(errs):.2f}°" if errs else "—"

    lines = [
        f"### {tier.name}",
        "",
        f"- 条件：{tier.hint or '—'}",
        f"- 整对命中：{pairs}/{n}（{pairs / n:.0%}）",
        f"- 真值覆盖：{covers}/{n}（{covers / n:.0%}）",
        f"- 角度中位误差：{med}",
        "",
        "| 真值角 | 候选山 | 角误差 | 判定 |",
        "|---|---|---|---|",
    ]
    for c in cases:
        cand = "/".join(c.candidates) if c.candidates else "—"
        err = f"{c.angle_err:.2f}°" if c.angle_err is not None else "—"
        if c.crashed:
            verdict = f"⚠️ 异常 `{c.error}`"
        elif c.pair_ok:
            verdict = "✅ 命中"
        elif c.truth_covered:
            verdict = "🟡 覆盖"
        elif c.accepted:
            verdict = "🟠 识别到盘但山名不符"
        else:
            verdict = f"❌ 未识别（{c.reason or '无原因说明'}）"
        lines.append(f"| {c.truth_angle:g}° | {cand} | {err} | {verdict} |")
    lines.append("")
    return "\n".join(lines)


def _photos_table(cases: list[CaseResult]) -> str:
    lines = [
        "### 逐张结果",
        "",
        "| 样本 | 真值 | 候选 | 角误差 | 判定 | 备注 |",
        "|---|---|---|---|---|---|",
    ]
    for c in cases:
        cand = "/".join(c.candidates) if c.candidates else "—"
        err = f"{c.angle_err:.2f}°" if c.angle_err is not None else "—"
        if c.crashed:
            verdict = "⚠️ 异常"
        elif c.pair_ok:
            verdict = "✅ 命中"
        elif c.truth_covered:
            verdict = "🟡 覆盖"
        elif c.accepted:
            verdict = "🟠 山名不符"
        else:
            verdict = "❌ 未识别"
        lines.append(
            f"| {c.label} | {c.truth_angle:g}° | {cand} | {err} | {verdict} | {c.note or '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _summary_block(cases: list[CaseResult], args: argparse.Namespace) -> str:
    n = len(cases)
    if n == 0:
        return "- 无样本。\n"
    # 用 getattr 而非直接取：两个子命令的参数集不同，新增子命令时不该炸在这里
    accept = getattr(args, "accept", DEFAULT_ACCEPT)
    pairs = sum(1 for c in cases if c.pair_ok)
    covers = sum(1 for c in cases if c.truth_covered)
    accepted = sum(1 for c in cases if c.accepted)
    false_ok = accepted - pairs
    crashes = sum(1 for c in cases if c.crashed)
    errs = [c.angle_err for c in cases if c.angle_err is not None]

    lines = [
        f"- 样本数：{n}",
        f"- **坐向整对命中：{pairs}/{n} = {pairs / n:.1%}**（参考阈值 {accept:.0%}）",
        f"- 真值覆盖：{covers}/{n} = {covers / n:.1%}",
        f"- 识别到盘体：{accepted}/{n} = {accepted / n:.1%}",
        f"- **⚠️ 假阳性：{false_ok}/{n} = {false_ok / n:.1%}**"
        "（给出了山名候选但都不对 —— 这类失败最危险："
        "用户看到的不是「识别不出」，而是一个看起来正常的错误坐向）",
        f"- 异常（代码缺陷）：{crashes}",
    ]
    if errs:
        lines += [
            f"- 角度误差中位：{statistics.median(errs):.2f}°",
            f"- 角度误差最大：{max(errs):.2f}°",
        ]
    return "\n".join(lines) + "\n"


def _synthetic_intro() -> str:
    return (
        "> ⚠️ **这不是 Gate 1 的判据。** 合成图只验证几何与算法，缺少真实罗盘的\n"
        "> 印刷细节、材质反光、手握遮挡与背景杂物。"  # noqa: D400
        "本文件用于定位「算法在哪种拍摄条件下开始失效」。\n"
        "> Gate 1 必须由 `photos` 子命令的真实照片结果判定。\n"
    )


def _photos_intro(photo_dir: Path, csv_path: Path, n: int) -> str:
    return (
        f"- 照片目录：`{photo_dir}`\n"
        f"- 标签文件：`{csv_path}`\n"
        f"- 样本数：{n}\n"
    )


def _synthetic_verdict(cases: list[CaseResult], args: argparse.Namespace) -> str:
    crashes = sum(1 for c in cases if c.crashed)
    accepted = sum(1 for c in cases if c.accepted)
    pairs = sum(1 for c in cases if c.pair_ok)
    false_ok = accepted - pairs

    lines = [
        "## 结论",
        "",
        "本扫描**不构成 Gate 1 通过**。它给出的是：",
        "",
        "- 算法在哪些拍摄条件下仍然可靠（见各档位命中率）",
        "- 从哪一档开始失效（这是后续优化或引入云端 Vision 的触发点）",
    ]
    if crashes:
        lines.append(f"- ⚠️ 存在 {crashes} 例异常，属代码缺陷，须先修复再谈识别率")

    lines += [
        "",
        "### 两类失败要分开看",
        "",
        "| 类型 | 含义 | 危害 |",
        "|---|---|---|",
        "| **明确拒绝** | 返回 `compass_detected=False` + 可操作提示 | 低 —— 用户知道要重拍，符合 RULE-003 |",
        "| **假阳性** | 返回了山名候选，但山名是错的 | **高** —— 用户看到的不是「识别不出」，"
        "而是一个看似正常的错误坐向 |",
        "",
    ]
    if false_ok:
        lines += [
            f"本次扫描中**假阳性 {false_ok} 例**（识别到盘体 {accepted} − 命中 {pairs}）。"
            "当前唯一的防线是 `needs_user_confirmation=True`（RULE-004）——"
            "用户必须在确认页核对坐向。**这条防线一旦被「优化掉」，假阳性就会变成静默的错误结果。**",
            "",
            "优先排查方向：背景杂物（深色物件、桌面边缘）污染前景掩膜，"
            "使质心偏移、极坐标展开错位，从而整体偏出若干山位。",
            "",
        ]
    lines += [
        "**下一步**：用真实罗盘照片跑 `photos` 子命令，才是 Gate 1 的正式评测。",
        "",
    ]
    return "\n".join(lines)


def _photos_verdict(cases: list[CaseResult], args: argparse.Namespace) -> str:
    n = len(cases)
    pairs = sum(1 for c in cases if c.pair_ok)
    accepted = sum(1 for c in cases if c.accepted)
    crashes = sum(1 for c in cases if c.crashed)
    false_ok = accepted - pairs
    rate = pairs / n if n else 0.0
    passed = rate >= args.accept and crashes == 0

    lines = [
        "## 结论",
        "",
        f"- 坐向量化判据（整对命中率 ≥ {args.accept:.0%}）：**{'达标' if passed else '未达标'}**"
        f"（实测 {rate:.1%}）",
        f"- 假阳性（给了山名但都不对）：**{false_ok}/{n}**"
        " —— 这类失败靠 RULE-004 的确认页兜底，不计入「识别成功」",
        "- 「3 秒内确认」：`[需真机]` —— 交互指标，须在真机上人工计时",
        "",
        "> 阈值是**建议值**，最终 Gate 1 判定由阿勇裁定。若要调整，加 `--accept` 重跑。",
        "",
    ]
    if crashes:
        lines += [
            f"⚠️ 有 {crashes} 例异常（代码缺陷）。**异常不计入识别率** —— "
            "把它们算作「识别失败」会掩盖 bug，算作「成功」则是造假。",
            "",
        ]
    if not passed and n < 15:
        lines += [
            f"⚠️ 样本量偏小（{n} < 15），成功率无统计意义。补足样本再判定。",
            "",
        ]
    return "\n".join(lines)


def _write_report(
    path: Path,
    *,
    title: str,
    intro: str,
    sections: list[str],
    summary: str,
    verdict: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        f"# {title}",
        "",
        "> 本文件由 `scripts/gate1_eval.py` 生成。**请勿手工编辑** —— 手改的数字无法追溯。",
        "> 若要更新结论，改脚本或补数据后重跑。",
        "",
        f"- 生成时间：{_now()}",
        f"- 命令：`{' '.join(sys.argv)}`",
        "",
        intro,
        "## 汇总",
        "",
        summary,
        *sections,
        verdict,
    ]
    path.write_text("\n".join(body), encoding="utf-8")


def _now() -> str:
    import datetime as _dt

    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ======================================================================


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Gate 1 罗盘识别可用性评测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("synthetic", help="合成退化扫描（不能代替 Gate 1）")
    s1.add_argument("--accept", type=float, default=DEFAULT_ACCEPT, help="报告中标出的参考阈值")
    s1.add_argument("--out", default="", help="把报告写到该 Markdown 路径")
    s1.set_defaults(func=run_synthetic)

    s2 = sub.add_parser("photos", help="真实照片评测（Gate 1 正式判据）")
    s2.add_argument("--dir", default="real_photos", help="照片目录（默认 real_photos）")
    s2.add_argument("--labels", default="", help="标签 CSV（默认 <dir>/labels.csv）")
    s2.add_argument("--accept", type=float, default=DEFAULT_ACCEPT, help="建议验收阈值")
    s2.add_argument("--out", default="", help="把报告写到该 Markdown 路径")
    s2.set_defaults(func=run_photos)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
