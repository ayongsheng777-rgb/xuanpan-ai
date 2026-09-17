"""姓名分析 —— 五格剖象法。

**算法与数据分离**（这是本模块最重要的设计）：
- 五格**算法**：确定性公式，本模块实现，用显式传入的笔画数即可完整测试
- 笔画**数据**：康熙字典笔画数以 JSON 表提供，`data/kangxi_strokes.json`
- 数理**吉凶**（81 数）：属流派规则表，**未提供时返回 `None`，不编造**

因此：`analyze_name` 必须能拿到全部字的笔画数，否则抛 `DomainDataMissingError`
并**列出缺哪些字** —— 让"数据不全"显式可见，而不是默默用错笔画算出一个漂亮结果。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final, Mapping

from .exceptions import DomainDataMissingError, InvalidInputError

DEFAULT_STROKES_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "kangxi_strokes.json"

# 常用复姓（用于正确切分姓氏与名）
COMPOUND_SURNAMES: Final[frozenset[str]] = frozenset({
    "欧阳", "太史", "端木", "上官", "司马", "东方", "独孤", "南宫", "万俟", "闻人",
    "夏侯", "诸葛", "尉迟", "公羊", "赫连", "澹台", "皇甫", "宗政", "濮阳", "公冶",
    "太叔", "申屠", "公孙", "慕容", "仲孙", "钟离", "长孙", "宇文", "司徒", "鲜于",
    "司空", "闾丘", "子车", "亓官", "司寇", "巫马", "公西", "颛孙", "壤驷", "公良",
    "漆雕", "乐正", "宰父", "谷梁", "拓跋", "夹谷", "轩辕", "令狐", "段干", "百里",
    "呼延", "东郭", "南门", "羊舌", "微生", "梁丘", "左丘", "西门", "第五", "南荣",
    "东里", "仲长", "即墨", "达奚", "褚师", "子桑", "公乘", "公皙",
})

# 笔画个位 -> 五行（五格三才用）
_STROKE_ELEMENT: Final[dict[int, str]] = {
    1: "木", 2: "木",
    3: "火", 4: "火",
    5: "土", 6: "土",
    7: "金", 8: "金",
    9: "水", 0: "水",
}


@dataclass(frozen=True, slots=True)
class NameAnalysis:
    """姓名五格分析结果。"""

    name: str
    surname: str
    given: str
    strokes: dict[str, int]
    tiange: int      # 天格
    renge: int       # 人格
    dige: int        # 地格
    waige: int       # 外格
    zongge: int      # 总格
    sancai: tuple[str, str, str]
    number_luck: dict[str, Any] | None = None   # 81 数理，规则表未提供时 None
    uncertainties: tuple[str, ...] = ()

    @property
    def sancai_label(self) -> str:
        return "".join(self.sancai)

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：五格数值（纯计算）。"""
        return {
            "name": self.name,
            "surname": self.surname,
            "given": self.given,
            "strokes": dict(self.strokes),
            "wuge": {
                "天格": self.tiange,
                "人格": self.renge,
                "地格": self.dige,
                "外格": self.waige,
                "总格": self.zongge,
            },
            "sancai": list(self.sancai),
            "sancai_label": self.sancai_label,
            "number_luck_available": self.number_luck is not None,
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：数理吉凶与三才解读。"""
        return {
            "number_luck": self.number_luck,
            "uncertainties": list(self.uncertainties),
            "note": "五格剖象法的笔画取值与三才配置属流派做法，不同体系数值可能不同。",
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}


@lru_cache(maxsize=4)
def load_strokes(path: str | None = None) -> dict[str, int]:
    """加载康熙笔画表。文件不存在 → 返回空表（**不编造**）。"""
    p = Path(path) if path else DEFAULT_STROKES_PATH
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    table = raw.get("strokes", raw)
    if not isinstance(table, dict):
        raise DomainDataMissingError(f"笔画表格式错误，应为 dict：{p}")
    out: dict[str, int] = {}
    for ch, v in table.items():
        if not isinstance(v, int) or not 1 <= v <= 64:
            raise DomainDataMissingError(f"笔画表存在非法条目：{ch!r} -> {v!r}")
        if len(ch) != 1:
            raise DomainDataMissingError(f"笔画表的键须为单字：{ch!r}")
        out[ch] = v
    return out


def split_name(name: str) -> tuple[str, str]:
    """切分姓氏与名。

    >>> split_name("欧阳修")
    ('欧阳', '修')
    >>> split_name("李白")
    ('李', '白')
    """
    n = name.strip()
    if len(n) < 2:
        raise InvalidInputError(f"姓名至少 2 字，收到 {name!r}")
    if len(n) >= 3 and n[:2] in COMPOUND_SURNAMES:
        return n[:2], n[2:]
    return n[0], n[1:]


def _resolve_strokes(
    chars: str,
    provided: Mapping[str, int] | None,
    table_path: str | None,
) -> dict[str, int]:
    table = load_strokes(table_path)
    out: dict[str, int] = {}
    missing: list[str] = []
    for ch in chars:
        if provided and ch in provided:
            v = provided[ch]
            if not isinstance(v, int) or v <= 0:
                raise InvalidInputError(f"传入笔画非法：{ch!r} -> {v!r}")
            out[ch] = v
        elif ch in table:
            out[ch] = table[ch]
        else:
            missing.append(ch)
    if missing:
        raise DomainDataMissingError(
            f"缺少以下字的康熙笔画：{''.join(missing)}。"
            "请通过 strokes 参数显式提供；内置表已覆盖 20794 常用字，缺字多为扩展区生僻字。"
        )
    return out


def compute_wuge(surname: str, given: str, strokes: Mapping[str, int]) -> dict[str, int]:
    """五格计算（纯公式，与笔画数据来源无关）。

    规则：
        天格 = 单姓: 姓笔画 + 1 ｜ 复姓: 姓两字笔画和
        人格 = 姓末字 + 名首字
        地格 = 单名: 名笔画 + 1 ｜ 双名: 名两字笔画和
        外格 = 单姓单名: 2 ｜ 单姓双名: 名次字 + 1
              ｜ 复姓单名: 姓首字 + 1 ｜ 复姓双名: 姓首字 + 名次字
        总格 = 全部笔画和
    """
    s_chars, g_chars = list(surname), list(given)
    if not s_chars or not g_chars:
        raise InvalidInputError("姓氏与名均不可为空")

    s_vals = [strokes[c] for c in s_chars]
    g_vals = [strokes[c] for c in g_chars]

    single_surname = len(s_chars) == 1
    single_given = len(g_chars) == 1

    tiange = s_vals[0] + 1 if single_surname else s_vals[0] + s_vals[1]
    renge = s_vals[-1] + g_vals[0]
    dige = g_vals[0] + 1 if single_given else g_vals[0] + g_vals[1]

    if single_surname and single_given:
        waige = 2
    elif single_surname and not single_given:
        waige = g_vals[1] + 1
    elif not single_surname and single_given:
        waige = s_vals[0] + 1
    else:
        waige = s_vals[0] + g_vals[1]

    zongge = sum(s_vals) + sum(g_vals)

    return {
        "天格": tiange, "人格": renge, "地格": dige, "外格": waige, "总格": zongge,
    }


def stroke_element(count: int) -> str:
    """笔画数 → 五行（按个位：1/2木 3/4火 5/6土 7/8金 9/0水）。

    >>> [stroke_element(n) for n in (12, 13, 5, 8, 9, 10)]
    ['木', '火', '土', '金', '水', '水']
    """
    if count <= 0:
        raise InvalidInputError(f"笔画数须为正整数，收到 {count}")
    return _STROKE_ELEMENT[count % 10]


def analyze_name(
    name: str,
    *,
    strokes: Mapping[str, int] | None = None,
    table_path: str | None = None,
    provided_wuge: Mapping[str, int] | None = None,
) -> NameAnalysis:
    """姓名分析。

    Args:
        name: 完整姓名
        strokes: 显式笔画覆盖（优先于内置表）
        table_path: 自定义笔画表路径
        provided_wuge: 直接给定五格（省去笔画依赖，用于外部已有五格结果的场景）
    """
    surname, given = split_name(name)
    chars = surname + given
    resolved = _resolve_strokes(chars, strokes, table_path)

    wuge = dict(provided_wuge) if provided_wuge else compute_wuge(surname, given, resolved)
    required = ("天格", "人格", "地格", "外格", "总格")
    absent = [k for k in required if k not in wuge]
    if absent:
        raise InvalidInputError(f"provided_wuge 缺少字段：{absent}")

    sancai = (
        stroke_element(wuge["天格"]),
        stroke_element(wuge["人格"]),
        stroke_element(wuge["地格"]),
    )

    uncertainties = [
        "五格剖象法为流派做法之一，笔画取值与三才配置存在不同体系",
        "81 数理吉凶规则表未提供，故不输出吉凶判定",
    ]

    return NameAnalysis(
        name=name,
        surname=surname,
        given=given,
        strokes=resolved,
        tiange=wuge["天格"],
        renge=wuge["人格"],
        dige=wuge["地格"],
        waige=wuge["外格"],
        zongge=wuge["总格"],
        sancai=sancai,
        number_luck=None,
        uncertainties=tuple(uncertainties),
    )


__all__ = [
    "COMPOUND_SURNAMES", "DEFAULT_STROKES_PATH", "NameAnalysis",
    "load_strokes", "split_name", "compute_wuge", "stroke_element", "analyze_name",
]
