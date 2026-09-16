"""灵签 —— 签库可插拔，抽签确定性可复现。

⚠️ **关于签文数据的重要声明**：
本仓库**不分发**任何传世签文全文（观音灵签 / 关帝灵签 / 月老灵签等），
因为无法保证文本的准确性与版本一致性 —— 而"看起来像但其实是错的"签文，
恰恰是本项目最想避免的问题（参见 RULE-001 的实测佐证）。

因此：
- `data/qian/demo_guanyin.json` 是**自撰演示样例**，元数据中 `demo: true` 明确标出
- 引擎本身完整可用：只要把合法签库 JSON 放进 `data/qian/`，即可直接启用
- 抽签为**确定性**函数：给定 `seed` 必得同一签（可测、可复现、可留痕）
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from .exceptions import DomainDataMissingError, InvalidInputError

DEFAULT_DATA_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "qian"
DEFAULT_SET_ID: Final[str] = "demo_guanyin"


@dataclass(frozen=True, slots=True)
class QianResult:
    """抽签结果。"""

    set_id: str
    set_name: str
    number: int
    level: str
    title: str
    poem: tuple[str, ...]
    interpretation: str
    advice: str
    demo: bool
    source_note: str

    def to_facts(self) -> dict[str, Any]:
        """FACT 层：抽签的确定性结果。"""
        return {
            "set_id": self.set_id,
            "set_name": self.set_name,
            "number": self.number,
            "level": self.level,
            "title": self.title,
            "poem": list(self.poem),
            "is_demo_data": self.demo,
        }

    def to_tradition(self) -> dict[str, Any]:
        """TRADITION 层：签文与签解。"""
        return {
            "interpretation": self.interpretation,
            "advice": self.advice,
            "source_note": self.source_note,
            "uncertainties": (
                ["当前签库为演示样例，非传世签文；正式使用前需导入合法签库"] if self.demo else []
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"facts": self.to_facts(), "tradition": self.to_tradition()}


@lru_cache(maxsize=16)
def _load_raw(set_id: str, data_dir: str) -> dict[str, Any]:
    path = Path(data_dir) / f"{set_id}.json"
    if not path.exists():
        raise DomainDataMissingError(
            f"签库不存在：{path}。请将合法签库 JSON 放入该目录，或改用已存在的签库。"
        )
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    signs = data.get("signs")
    if not isinstance(signs, list) or not signs:
        raise DomainDataMissingError(f"签库 {set_id} 缺少有效的 signs 数组：{path}")
    expected = data.get("total")
    if isinstance(expected, int) and expected != len(signs):
        raise DomainDataMissingError(
            f"签库 {set_id} 声明 total={expected}，实际 signs={len(signs)}，数据不自洽"
        )
    numbers = [s.get("number") for s in signs]
    if len(set(numbers)) != len(numbers):
        raise DomainDataMissingError(f"签库 {set_id} 存在重复签号：{numbers}")
    return data


def load_qian_set(set_id: str = DEFAULT_SET_ID, data_dir: str | Path | None = None) -> dict[str, Any]:
    """加载签库（带自洽性校验）。"""
    return _load_raw(set_id, str(data_dir or DEFAULT_DATA_DIR))


def list_qian_sets(data_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """列出可用签库。"""
    d = Path(data_dir or DEFAULT_DATA_DIR)
    if not d.exists():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        try:
            data = _load_raw(f.stem, str(d))
        except DomainDataMissingError:
            continue
        out.append({
            "set_id": f.stem,
            "name": data.get("name", f.stem),
            "total": len(data.get("signs", [])),
            "demo": bool(data.get("demo", False)),
            "note": data.get("note", ""),
        })
    return out


def draw_qian(
    seed: int,
    *,
    set_id: str = DEFAULT_SET_ID,
    data_dir: str | Path | None = None,
) -> QianResult:
    """按 seed 抽签（确定性）。

    Args:
        seed: 任意整数。**由调用方决定其来源**（时间、用户摇签结果的哈希等）。
              引擎不做随机，保证可复现、可测试、可留痕。

    >>> draw_qian(0, set_id="demo_guanyin").number
    1
    """
    data = load_qian_set(set_id, data_dir)
    signs = data["signs"]
    idx = int(seed) % len(signs)
    sign = signs[idx]

    number = sign.get("number")
    if not isinstance(number, int):
        raise DomainDataMissingError(f"签库 {set_id} 第 {idx} 条缺少合法 number 字段")

    return QianResult(
        set_id=set_id,
        set_name=data.get("name", set_id),
        number=number,
        level=sign.get("level", "未标"),
        title=sign.get("title", ""),
        poem=tuple(sign.get("poem", [])),
        interpretation=sign.get("interpretation", ""),
        advice=sign.get("advice", ""),
        demo=bool(data.get("demo", False)),
        source_note=data.get("note", ""),
    )


def find_sign_by_number(
    number: int, *, set_id: str = DEFAULT_SET_ID, data_dir: str | Path | None = None
) -> QianResult:
    """按签号取签（供历史记录回查）。"""
    data = load_qian_set(set_id, data_dir)
    for sign in data["signs"]:
        if sign.get("number") == number:
            return QianResult(
                set_id=set_id,
                set_name=data.get("name", set_id),
                number=number,
                level=sign.get("level", "未标"),
                title=sign.get("title", ""),
                poem=tuple(sign.get("poem", [])),
                interpretation=sign.get("interpretation", ""),
                advice=sign.get("advice", ""),
                demo=bool(data.get("demo", False)),
                source_note=data.get("note", ""),
            )
    raise InvalidInputError(f"签库 {set_id} 中不存在签号 {number}")


__all__ = [
    "DEFAULT_DATA_DIR", "DEFAULT_SET_ID", "QianResult",
    "load_qian_set", "list_qian_sets", "draw_qian", "find_sign_by_number",
]
