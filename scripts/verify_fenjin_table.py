"""校验一百二十分金规则表 —— 拦住「不会报错、只会静默降级」的那类问题。

背景（为什么需要这个脚本）：

`load_fenjin_table()` 已经校验了**结构合法性**（顶层是 dict、山名合法、
每山恰好 5 格、干支属六十甲子）。但它**管不到完整性**，而完整性不足
不会抛异常，只会让分金**静默地少给数据**：

- 只写了 3 个山 → 另外 21 个山的 105 格永远无干支，用户看到「未定」却不知为何
- 漏了某个流派 key → 该流派静默不可用，而 `schools.py` 明明声明了它
- 某山 5 格全为 `null` → 整山空亡（罕见），多半是漏填

这与 `verify_zeri_table.py` 是同一类风险：**错误的规则表不会崩，只会悄悄算错。**

🔴 **本脚本不判断排法对错。** 各格配什么干支、哪格旺相哪格孤虚属流派规则
（RULE-006），各派不同，必须由人给出依据。脚本只回答两个问题：
① 表能不能被加载（结构是否合法）；② 填得完不完整（覆盖度是否够）。
排法正确性请在 `data/fenjin120.json` 的出处注明依据。

用法（[Host] managed venv）::

    "$PY" scripts/verify_fenjin_table.py                  # 体检
    "$PY" scripts/verify_fenjin_table.py --strict         # 有 WARN 也算失败
    "$PY" scripts/verify_fenjin_table.py --require        # 表不存在直接算失败（交付检查）
    "$PY" scripts/verify_fenjin_table.py --table X.json   # 校验别的候选表

退出码：0 = 通过；1 = 有问题。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TABLE = REPO / "packages" / "fortune-core" / "data" / "fenjin120.json"

# 脚本要能独立跑（不依赖调用方设 PYTHONPATH）—— 与 verify_zeri_table.py 不同之处
sys.path.insert(0, str(REPO / "packages" / "fortune-core"))

from fortune_core.constants import JIAZI_60  # noqa: E402
from fortune_core.fenjin120 import FENJIN_PER_MOUNTAIN, load_fenjin_table  # noqa: E402
from fortune_core.mountain24 import MOUNTAIN_ORDER  # noqa: E402
from fortune_core.schools import DEFAULT_SCHOOL, SCHOOLS  # noqa: E402

TABLE_TEMPLATE = """表格式（每山恰好 5 格，null = 该流派下空亡/不用）::

    {
      "default": {
        "子": ["甲子", "丙子", null, "庚子", null],
        "癸": [...],
        ... 二十四山全部 24 个 key ...
      }
    }

`schools.py` 声明了三个流派 key，按需各自提供一份（缺失的流派会静默不可用）：

"""


@dataclass(frozen=True)
class Issue:
    level: str  # "FAIL" | "WARN"
    scope: str  # 流派名，或 "（全局）"
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.scope}：{self.message}"


@dataclass(frozen=True)
class SchoolReport:
    school: str
    mountains: int
    cells: int
    filled: int

    @property
    def empty(self) -> int:
        return self.cells - self.filled

    @property
    def ratio(self) -> str:
        return f"{self.filled / self.cells:.0%}" if self.cells else "—"


def declared_school_keys() -> list[str]:
    """`schools.py` 里声明过的全部分金流派 key（去重后排序）。"""
    return sorted({p.fenjin_table for p in SCHOOLS.values()})


def active_school_keys() -> list[str]:
    """**当前对用户开放**的流派所用的 key。

    判据按 `schools.py` 的口径（`available = (p.id == DEFAULT_SCHOOL)`）。
    只有这一档缺失才告警 —— `sanhe` / `sanyuan` 尚未开放，缺它们是预期状态，
    若一并告警就会变成**误报**，而误报会训练人忽略整个脚本。
    """
    return sorted({p.fenjin_table for p in SCHOOLS.values() if p.id == DEFAULT_SCHOOL})


def validate(table: Mapping[str, Any]) -> tuple[list[SchoolReport], list[Issue]]:
    """体检一张**已成功加载**的表。

    结构合法性由 `load_fenjin_table` 负责（它抛异常时本函数不会被调用），
    这里只查它管不到的**完整性**与**分布**。
    """
    issues: list[Issue] = []
    reports: list[SchoolReport] = []
    all_mountains = list(MOUNTAIN_ORDER)

    missing_active = [k for k in active_school_keys() if k not in table]
    if missing_active:
        issues.append(
            Issue(
                "WARN",
                "（全局）",
                f"当前可用流派所需的 key 缺失：{missing_active} —— "
                f"该流派的分金会静默无干支（available=False），"
                f"而使用者以为是计算层坏了",
            )
        )

    for school in sorted(table):
        by_mountain = table[school]
        if not isinstance(by_mountain, Mapping):
            continue  # 加载器已拦；这里只做防御，避免体检脚本自己崩

        missing = [m for m in all_mountains if m not in by_mountain]
        if missing:
            issues.append(
                Issue(
                    "WARN",
                    school,
                    f"缺 {len(missing)} 个山（共 {len(missing) * FENJIN_PER_MOUNTAIN} 格）："
                    f"{'、'.join(missing)} —— 这些格永远无干支，界面显示「未定」而原因不明",
                )
            )

        filled = 0
        for name, cells in by_mountain.items():
            values = [c for c in cells if c is not None]
            filled += len(values)

            dup = sorted(v for v, n in Counter(values).items() if n > 1)
            if dup:
                issues.append(
                    Issue("WARN", school, f"{name}山 内干支重复：{'、'.join(dup)}")
                )
            if len(values) == 0:
                issues.append(
                    Issue(
                        "WARN",
                        school,
                        f"{name}山 5 格全为 null —— 整山空亡极为罕见，多半是漏填",
                    )
                )

        reports.append(
            SchoolReport(
                school=school,
                mountains=len(by_mountain),
                cells=len(by_mountain) * FENJIN_PER_MOUNTAIN,
                filled=filled,
            )
        )

    return reports, issues


def _ganzhi_distribution(table: Mapping[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for by_mountain in table.values():
        if isinstance(by_mountain, Mapping):
            for cells in by_mountain.values():
                counts.update(c for c in cells if c is not None)
    return counts


def _load(path: Path) -> tuple[dict[str, Any] | None, Issue | None]:
    """复用**严格**加载器 —— 脚本不为"能不能加载"另写一套判断。"""
    try:
        return load_fenjin_table(str(path)), None
    except json.JSONDecodeError as exc:
        return None, Issue(
            "FAIL",
            "（全局）",
            f"JSON 解析失败：{exc}（常见原因：中文引号、多余逗号、UTF-8 BOM）",
        )
    except Exception as exc:  # noqa: BLE001 - 结构校验的各类异常都要转成可读报告
        return None, Issue("FAIL", "（全局）", f"结构不合法：{type(exc).__name__}: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description="校验一百二十分金规则表的完整性与合法性")
    ap.add_argument("--table", default=str(DEFAULT_TABLE), help="规则表路径")
    ap.add_argument("--strict", action="store_true", help="把 WARN 也算作失败")
    ap.add_argument("--require", action="store_true", help="表不存在即失败（交付检查用）")
    args = ap.parse_args()

    path = Path(args.table)
    print(f"规则表：{path}")

    if not path.exists():
        print("\n[!] 表「尚未提供」—— 这是已知状态，不是错误。")
        print("    当前分金只输出几何格位（格位/所属山/角度），干支为 None。")
        print("    见 HANDOFF「fenjin120 规则表缺失」段与 schools.py 的 unverified 声明。\n")
        print(TABLE_TEMPLATE)
        for key in declared_school_keys():
            profile = next(p for p in SCHOOLS.values() if p.fenjin_table == key)
            print(f"    {key:10s} （schools.py 中 {profile.id} 流派使用）")
        if args.require:
            print("\n[FAIL] --require 要求表必须存在，但它不在。")
            return 1
        return 0

    table, load_issue = _load(path)
    if load_issue is not None:
        print(f"\n{load_issue}")
        print("\n=== 修复指引 ===")
        print("  1. 按上面的报错定位到具体山 / 格位（报错里已写明「应有 N 格，实为 M」）")
        print("  2. 本脚本与加载器共用同一套结构校验，修好后重跑本脚本即可确认")
        print("  3. 🔴 若表是在运行中的服务上修改：表有缓存，必须重启服务才生效")
        print("     （容器部署则是 `docker compose up -d --build`）")
        return 1

    assert table is not None
    active, declared = active_school_keys(), declared_school_keys()
    print(f"流派 key：表内有 {sorted(table)}")
    print(f"          当前开放流派需要 {active}；schools.py 共声明 {declared}")
    not_yet = [k for k in declared if k not in table and k not in active]
    if not_yet:
        print(f"          {'、'.join(not_yet)} 尚未开放，缺它属预期状态（不计为问题）")
    print()

    reports, issues = validate(table)

    print(f"{'流派':<12} {'山':>3} {'格':>4} {'已填':>5} {'空亡':>5}  完整度")
    for r in reports:
        print(f"{r.school:<12} {r.mountains:>3} {r.cells:>4} {r.filled:>5} {r.empty:>5}  {r.ratio}")

    dist = _ganzhi_distribution(table)
    if dist:
        by_count: dict[int, list[str]] = {}
        for gz in JIAZI_60:
            by_count.setdefault(dist.get(gz, 0), []).append(gz)
        print(f"\n干支出现次数分布（六十甲子共 {len(JIAZI_60)} 个，本表出现 {len(dist)} 个）：")
        for n in sorted(by_count):
            names = by_count[n]
            shown = "、".join(names[:6]) + ("…" if len(names) > 6 else "")
            print(f"  {n:>2} 次 × {len(names):>2} 个   {shown}")
        if dist and max(dist.values()) == 2 and len(dist) == len(JIAZI_60):
            print("  → 每个干支恰好 2 次（120 格铺满两周期的典型形状）")

    fails = [i for i in issues if i.level == "FAIL"]
    warns = [i for i in issues if i.level == "WARN"]

    print()
    if issues:
        print("=== 发现问题 ===")
        for i in issues:
            print(" -", i)
        print(f"\n共 {len(fails)} 项 FAIL、{len(warns)} 项 WARN")
    else:
        print("[OK] 结构合法、二十四山齐备、无山内重复、无整山空亡。")
        print("     ⚠️ 本脚本不判断**排法**对错 —— 那是流派规则（RULE-006），须由人给定依据。")

    if fails or (args.strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
