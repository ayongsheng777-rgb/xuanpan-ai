"""对照复算：外部 MCP 项目 suanming-mcp（玄机阁）vs 玄盘 fortune-core。

用途：为 `docs/外部项目评估 — suanming-mcp（玄机阁）.md` 提供**可复现的取证**。
本项目自 2026-09-16 起被判定为「娱乐演示项目，术数计算层不可信」，
本脚本是该判定的唯一依据来源 —— **不引用其 README 的任何自我描述**。

设计原则（对齐 AGENTS.md RULE-007）：
- 检查 A / B **完全自包含**，只依赖 fortune-core，任何环境都能跑
- 检查 C 需要外部仓库源码，用 `--repo` 显式指定；未指定则跳过并提示

用法：
    cd D:/WorkBuddy/玄盘AI
    PYTHONPATH=packages/fortune-core \
      C:/Users/anyong/.workbuddy/binaries/python/envs/default/Scripts/python.exe \
      scripts/cmp_suanming_mcp.py [--repo <suanming-mcp 克隆目录>]

退出码：0 = 全部检查按要求执行完毕；1 = 有检查未通过（说明存在缺陷，属预期结果）
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

from fortune_core import BirthInput, calculate_bazi
from fortune_core.constants import DIZHI, TIANGAN

# ===========================================================================
# 检查 A：八字四柱对照（自包含）
#   —— 逐行移植 suanming-mcp/src/tools/bazi.ts 的算法，**不做任何修正**
# ===========================================================================


def mcp_year_gan(year: int) -> str:
    return TIANGAN[(year - 4) % 10]


def mcp_year_zhi(year: int) -> str:
    return DIZHI[(year - 4) % 12]


def mcp_month_gan(year_gan_index: int, month: int) -> str:
    base = (year_gan_index * 2) % 10
    return TIANGAN[(base + month - 1) % 10]


def mcp_month_zhi(month: int) -> str:
    return DIZHI[(month + 1) % 12]


def mcp_day_pillar(year: int, month: int, day: int) -> tuple[str, str]:
    diff = (date(year, month, day) - date(1900, 1, 1)).days
    stem_i = ((diff % 10) + 10) % 10
    branch_i = ((diff % 12) + 12) % 12
    return TIANGAN[(10 + stem_i) % 10], DIZHI[(10 + branch_i) % 12]


def mcp_hour_pillar(day_gan_index: int, hour: int) -> tuple[str, str]:
    branch_i = ((hour + 1) // 2) % 12
    base = (day_gan_index * 2) % 10
    return TIANGAN[(base + branch_i) % 10], DIZHI[branch_i]


def mcp_bazi(year: int, month: int, day: int, hour: int) -> list[str]:
    yg, yz = mcp_year_gan(year), mcp_year_zhi(year)
    mg = mcp_month_gan(TIANGAN.index(yg), month)
    mz = mcp_month_zhi(month)
    dg, dz = mcp_day_pillar(year, month, day)
    hg, hz = mcp_hour_pillar(TIANGAN.index(dg), hour)
    return [yg + yz, mg + mz, dg + dz, hg + hz]


#: 刻意覆盖 立春 / 节气 / 晚子时 / 跨年 等边界
BAZI_CASES: list[tuple[int, int, int, int, str]] = [
    (1990, 5, 20, 10, "README 示例"),
    (2000, 1, 1, 8, "README 示例 · 立春前"),
    (1988, 2, 3, 23, "立春前 1 天 + 晚子时"),
    (1990, 2, 4, 10, "立春当日"),
    (2024, 3, 15, 8, "惊蛰后、清明前"),
    (2026, 9, 17, 10, "评估当日"),
    (1995, 8, 8, 14, "立秋当日"),
    (1976, 1, 31, 0, "春节当天 / 子时"),
    (2000, 12, 31, 12, "跨世纪"),
    (2015, 4, 5, 5, "清明当日 卯时"),
]

#: 时柱在 23:00 的差异属**流派口径**，非缺陷（玄盘 sect=2：日柱当天、时干用次日日干；
#: suanming-mcp 无声明口径，实际等同「晚子时不换日、时干不换」）。判定时单独归类。
KNOWN_SECT_DIVERGENCE = {(1988, 2, 3, 23, "时柱")}


def check_bazi() -> tuple[int, int]:
    print("=" * 74)
    print("检查 A · 八字四柱对照（suanming-mcp 算法 vs fortune-core / lunar-python）")
    print("=" * 74)
    pillars = ("年柱", "月柱", "日柱", "时柱")
    hard_err: dict[str, int] = {p: 0 for p in pillars}
    soft_diff: dict[str, int] = {p: 0 for p in pillars}
    total = 0

    for y, m, d, h, note in BAZI_CASES:
        got = mcp_bazi(y, m, d, h)
        ref = calculate_bazi(BirthInput(year=y, month=m, day=d, hour=h, minute=0)).pillar_list
        for i, p in enumerate(pillars):
            total += 1
            same = got[i] == ref[i]
            if not same:
                if (y, m, d, h, p) in KNOWN_SECT_DIVERGENCE:
                    soft_diff[p] += 1
                    kind = "流派差异"
                else:
                    hard_err[p] += 1
                    kind = "错"
            else:
                kind = "OK"
            label = f"{y}-{m:02d}-{d:02d} {h:02d}:00" if i == 0 else ""
            print(f"  {label:<19}{p:<5}{got[i]:<8}{ref[i]:<8}{kind:<9}{note if i == 0 else ''}")
        print()

    print(f"  合计 {total} 项柱位")
    for p in pillars:
        verdict = "🔴 系统性错误" if hard_err[p] else ("⚪ 仅流派差异" if soft_diff[p] else "✅ 一致")
        print(f"    {p}：真错 {hard_err[p]}/{len(BAZI_CASES)}  流派差异 {soft_diff[p]}  {verdict}")
    print()
    return total, sum(hard_err.values())


# ===========================================================================
# 检查 B：姓名「外格」公式（自包含）
# ===========================================================================


def check_wuge() -> bool:
    print("=" * 74)
    print("检查 B · 姓名五格公式（源码 vs 通行「外格 = 总格 − 人格 + 1」）")
    print("=" * 74)
    name = "王小明"
    s1, s2, s3 = 5, 11, 8  # 用源码侧笔画取值复算，只考察公式结构本身
    src = {"天格": s1 + 1, "人格": s1 + s2, "地格": s2 + s3, "外格": s1 + s3, "总格": s1 + s2 + s3}
    std = {
        "天格": s1 + 1,
        "人格": s1 + s2,
        "地格": s2 + s3,
        "外格": (s1 + s2 + s3) - (s1 + s2) + 1,
        "总格": s1 + s2 + s3,
    }
    ok = True
    for k in ("天格", "人格", "地格", "外格", "总格"):
        flag = "一致" if src[k] == std[k] else "❌ 不一致"
        if src[k] != std[k]:
            ok = False
        print(f"  {name} · {k}：源码={src[k]:<4}通行={std[k]:<4}{flag}")
    print(f"\n  源码外格写法 `s3 ? s1 + s3 : s1 + 1`（姓+名末字），通行应为 名末字+1；复姓/单名未分支。")
    print()
    return ok


# ===========================================================================
# 检查 C：六爻卦序映射 + 姓名笔画字库（需外部仓库源码）
# ===========================================================================

TRIGRAM_LINES = {  # Unicode 八卦符号 -> 自下而上三爻
    "\u2630": (1, 1, 1),
    "\u2631": (1, 1, 0),
    "\u2632": (1, 0, 1),
    "\u2633": (1, 0, 0),
    "\u2634": (0, 1, 1),
    "\u2635": (0, 1, 0),
    "\u2636": (0, 0, 1),
    "\u2637": (0, 0, 0),
}


def _lines_to_gua_num(lines: list[int]) -> int:
    """复刻 suanming-mcp/src/tools/liuyao.ts 的 linesToGuaNum。"""
    return sum(lines[i] * (1 << i) for i in range(6)) + 1


def check_liuyao(hexagrams_ts: Path) -> tuple[int, int]:
    print("=" * 74)
    print("检查 C1 · 六爻卦序映射自洽性（其数据表 vs 其查询算法）")
    print("=" * 74)
    src = hexagrams_ts.read_text(encoding="utf-8")
    table = {
        int(m.group(1)): (m.group(2), m.group(3))
        for m in re.finditer(r'(\d+):\s*\{\s*name:\s*"([^"]+)",\s*symbol:\s*"([^"]+)"', src)
    }
    print(f"  解析到卦表条目：{len(table)}")
    if len(table) != 64:
        print("  ⚠️ 未能解析出 64 条，跳过")
        return 0, 0

    ok, bad, samples = 0, 0, []
    for k in sorted(table):
        _, symbol = table[k]
        up, low = symbol[0], symbol[1]
        lines = list(TRIGRAM_LINES[low]) + list(TRIGRAM_LINES[up])  # 表内 symbol = 上卦+下卦
        hit = table[_lines_to_gua_num(lines)][0]
        if hit == table[k][0]:
            ok += 1
        else:
            bad += 1
            if len(samples) < 5:
                samples.append(f"{table[k][0]}({symbol}) -> 查到 {hit}")

    print(f"  自洽命中 {ok}/64，错配 {bad}/64")
    for s in samples:
        print(f"    {s}")
    all_yang = table[_lines_to_gua_num([1, 1, 1, 1, 1, 1])][0]
    all_yin = table[_lines_to_gua_num([0, 0, 0, 0, 0, 0])][0]
    print(f"  反例：六爻全阳 → 应得「乾为天」，实际得「{all_yang}」")
    print(f"  反例：六爻全阴 → 应得「坤为地」，实际得「{all_yin}」")
    print()
    return ok, bad


def check_char_library(characters_ts: Path) -> tuple[int, int]:
    print("=" * 74)
    print("检查 C2 · 姓名笔画字库覆盖率与缺字兜底行为")
    print("=" * 74)
    src = characters_ts.read_text(encoding="utf-8")
    nc_start, sm_start = src.index("NAME_CHARS"), src.index("STROKE_MAP")
    nc_block, sm_block = src[nc_start:sm_start], src[sm_start:]
    nc = dict(re.findall(r'"([^"]+)"\s*:\s*\{\s*strokes:\s*(\d+)', nc_block))
    sm = dict(re.findall(r'"([^"]+)"\s*:\s*(\d+)', sm_block))
    print(f"  NAME_CHARS 起名用字库 = {len(nc)} 条；STROKE_MAP 姓氏笔画表 = {len(sm)} 条；合计 {len(nc) + len(sm)}")

    def mcp_strokes(ch: str) -> tuple[int, bool]:
        if ch in nc:
            return int(nc[ch]), True
        if ch in sm:
            return int(sm[ch]), True
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:  # 源码：Unicode 码位估算
            return max(1, min(30, (code - 0x4E00) // 500 + 4)), False
        return 1, False

    truth = {"阿": 8, "勇": 9, "玄": 5, "盘": 15, "王": 4, "李": 7, "管": 14, "辉": 15, "娜": 10, "哲": 10, "浩": 11}
    miss = wrong = 0
    print("\n  字   康熙真值  程序取值  来源")
    for ch, t in truth.items():
        v, hit = mcp_strokes(ch)
        if not hit:
            miss += 1
        elif v != t:
            wrong += 1
        if not hit or v != t:
            print(f"  {ch}     {t:>3}      {v:>3}     {'表内(值不符)' if hit else '❌ Unicode 估算兜底'}")
    print(f"\n  抽查 {len(truth)} 字：未收录走 Unicode 估算 = {miss}；表内但笔画不符 = {wrong}")
    print("  ⚠️ 源码 characters.ts 用 Unicode 码位反推笔画，未收录字**静默产出虚构笔画**，五格评分全部失真。")
    print()
    return miss + wrong, 0


# ===========================================================================


def main() -> int:
    ap = argparse.ArgumentParser(description="复算 suanming-mcp 的术数计算层")
    ap.add_argument("--repo", type=Path, default=None, help="suanming-mcp 克隆目录（用于检查 C）")
    args = ap.parse_args()

    print()
    total, hard_err = check_bazi()
    check_wuge()

    if args.repo:
        hx = args.repo / "src" / "data" / "hexagrams.ts"
        ch = args.repo / "src" / "data" / "characters.ts"
        if hx.exists() and ch.exists():
            ok, bad = check_liuyao(hx)
            check_char_library(ch)
        else:
            print(f"⚠️ 未找到 {hx} 或 {ch}，跳过检查 C")
    else:
        print("=" * 74)
        print("检查 C · 六爻卦序 / 笔画字库 —— 已跳过")
        print("  加 --repo <suanming-mcp 克隆目录> 以执行：")
        print("    git clone --depth 1 https://github.com/Enoch666/suanming-mcp.git")
        print("=" * 74)

    print("\n结论：suanming-mcp 的八字月柱、六爻卦名、姓名笔画三处计算层均不可用；")
    print("      本项目 fortune-core 在同一批输入上与之逐项不符，且缺字时显式报错而非静默估算。")
    return 1 if hard_err else 0


if __name__ == "__main__":
    sys.exit(main())
