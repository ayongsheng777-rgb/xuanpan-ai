"""校验择日规则表 —— 保证事件词目全部来自 lunar-python 真实发出的宜忌词汇。

背景（为什么需要这个脚本）：

择日规则表的每个事件都要写「宜/忌」词目。这些词目**如果写错，不会报错，
只会静默失效** —— 比如把「忌嫁娶」写成「忌娶嫁」，规则永远不命中，
筛选结果看起来正常，实际上少了一道否决，用户拿到的是错的日子。
这与 RULE-008「不得为了看起来合理而修正数据」是同一类风险：
**错误的规则表不会崩，只会悄悄算错。**

因此本脚本做三件事：

1. **词目存在性**：事件表里每个 yi/ji 词，都必须在实测区间内被
   `lunar-python` 真实发出过。凭空造的词直接报错。
2. **死规则检测**：某词目在实测区间内命中次数为 0 → 提示「可能写错或过于生僻」。
3. **自相矛盾检测**：同一个词**同时**出现在宜与忌中（`lunar-python` 若发出这种
   日，veto 规则会有歧义）—— 当前实测为 0，此脚本持续守住这个前提。

用法（[Host] managed venv）::

    "$PY" scripts/verify_zeri_table.py                    # 校验（默认扫 730 天）
    "$PY" scripts/verify_zeri_table.py --days 1095        # 加大样本
    "$PY" scripts/verify_zeri_table.py --check-veto       # 额外输出各事件 veto 频次

退出码：0 = 全部通过；1 = 发现问题。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TABLE = REPO / "packages" / "fortune-core" / "data" / "zeri_events.json"
START = dt.date(2024, 1, 1)


def collect_vocabulary(days: int) -> tuple[set[str], set[str], int]:
    """跑真实历法，收集 lunar-python 实际发出的宜/忌词汇表。"""
    from lunar_python import Solar

    yi_all: set[str] = set()
    ji_all: set[str] = set()
    conflicts = 0
    for i in range(days):
        d = START + dt.timedelta(days=i)
        lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
        yi, ji = set(lunar.getDayYi()), set(lunar.getDayJi())
        yi_all |= yi
        ji_all |= ji
        conflicts += len(yi & ji)
    return yi_all, ji_all, conflicts


def main() -> int:
    ap = argparse.ArgumentParser(description="校验择日规则表词目是否来自真实数据")
    ap.add_argument("--days", type=int, default=730, help="实测天数（默认 730）")
    ap.add_argument("--check-veto", action="store_true", help="额外输出各事件 veto 频次")
    ap.add_argument("--table", default=str(TABLE), help="规则表路径")
    args = ap.parse_args()

    path = Path(args.table)
    if not path.exists():
        print(f"[FAIL] 规则表不存在：{path}")
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    events = data["events"]

    print(f"规则表：{path}")
    print(f"实测区间：{START} ~ {START + dt.timedelta(days=args.days - 1)}（{args.days} 天）")
    yi_all, ji_all, conflicts = collect_vocabulary(args.days)
    print(f"真实宜词表 {len(yi_all)} 词 / 忌词表 {len(ji_all)} 词")
    print(f"同词既宜又忌的真冲突日：{conflicts} 天\n")

    problems: list[str] = []

    # 1 + 2：词目存在性与死规则检测
    print(f"{'事件':<12} {'宜命中':>6} {'忌命中':>6}  词目校验")
    hit_counter: dict[str, Counter[str]] = {}
    for key, ev in sorted(events.items()):
        yi_hits = ji_hits = 0
        bad_words: list[str] = []
        dead_words: list[str] = []
        for word in ev["yi"]:
            if word not in yi_all:
                bad_words.append(f"宜词 {word!r} 不在真实宜词表")
        for word in ev["ji"]:
            if word not in ji_all:
                bad_words.append(f"忌词 {word!r} 不在真实忌词表")

        # 实际命中统计（逐日重扫，保证命中数真实）
        from lunar_python import Solar

        c = Counter()
        ev_yi, ev_ji = set(ev["yi"]), set(ev["ji"])
        for i in range(args.days):
            d = START + dt.timedelta(days=i)
            lunar = Solar.fromYmdHms(d.year, d.month, d.day, 12, 0, 0).getLunar()
            yi, ji = set(lunar.getDayYi()), set(lunar.getDayJi())
            hy, hj = bool(yi & ev_yi), bool(ji & ev_ji)
            c["yi"] += hy
            c["ji"] += hj
            for w in ev_yi:
                if w in yi:
                    c[f"w:{w}"] += 1
            for w in ev_ji:
                if w in ji:
                    c[f"w:{w}"] += 1
        hit_counter[key] = c
        yi_hits, ji_hits = c["yi"], c["ji"]

        for w in ev["yi"]:
            if c[f"w:{w}"] == 0:
                dead_words.append(f"宜词 {w!r} 零命中")
        for w in ev["ji"]:
            if c[f"w:{w}"] == 0:
                dead_words.append(f"忌词 {w!r} 零命中")

        status = "OK"
        if bad_words:
            status = "FAIL"
            problems.extend(f"[{key}] {b}" for b in bad_words)
        if dead_words:
            status = "WARN"
            problems.extend(f"[{key}] {d}（规则永不生效，请确认是否写错）" for d in dead_words)
        print(f"{ev['label']:<12} {yi_hits:>6} {ji_hits:>6}  {status}")

    # 3：真冲突（前提守卫）
    if conflicts:
        problems.append(
            f"检测到 {conflicts} 天出现「同词既宜又忌」，veto 规则将产生歧义，需重新设计"
        )

    print()
    if args.check_veto:
        print("=== veto 词目命中明细 ===")
        for key, ev in sorted(events.items()):
            c = hit_counter[key]
            detail = "、".join(f"{w}:{c[f'w:{w}']}" for w in ev["ji"])
            print(f"  {ev['label']:<12} 忌命中 {c['ji']:>3} 天   明细：{detail or '（无 veto 词）'}")
        print()

    if problems:
        print("=== 发现问题 ===")
        for p in problems:
            print(" -", p)
        print(f"\n[FAIL] 共 {len(problems)} 项")
        return 1

    print("[OK] 规则表全部词目均来自真实宜忌词表，无死规则，无同词宜忌冲突。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
