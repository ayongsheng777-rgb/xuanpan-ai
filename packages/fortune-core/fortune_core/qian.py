"""灵签 —— 签库可插拔，抽签确定性可复现。

⚠️ **关于签文数据的重要声明**：
本仓库**不自撰、不校对**任何传世签文全文（观音灵签 / 关帝灵签 / 月老灵签等），
因为无法保证文本的准确性与版本一致性 —— 而"看起来像但其实是错的"签文，
恰恰是本项目最想避免的问题（参见 RULE-001 的实测佐证）。

因此：`data/qian/guanyin/` 是**第三方来源**（见 manifest.json 内 `note`
的出处与获取日期），**未做传世版本校对** —— 文本准确性以来源为准，
由用户自行判断是否采用（2026-10-07 由用户指定引入）。

演示样例库（`demo_guanyin`）已于 2026-10-08 按用户要求移除：
演示签文会让人误以为是真签文，而"看起来像但其实是错的"正是本项目
最想避免的问题。引擎本身完整可用：只要把合法签库放进 `data/qian/`，
即可直接启用。
签库两种形态（`load_qian_set` 自动识别）：
- 单文件：`data/qian/<set_id>.json`（含 `signs` 数组）
- 分卷：`data/qian/<set_id>/manifest.json`（元数据）+
  `data/qian/<set_id>/part-*.json`（`signs` 分片，按文件名排序合并；
  用于单文件过大的数据集，合并后与单文件语义一致）
抽签为**确定性**函数：给定 `seed` 必得同一签（可测、可复现、可留痕）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from .exceptions import DomainDataMissingError, InvalidInputError

DEFAULT_DATA_DIR: Final[Path] = Path(__file__).resolve().parent.parent / "data" / "qian"
DEFAULT_SET_ID: Final[str] = "guanyin"


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
    single = Path(data_dir) / f"{set_id}.json"
    if single.exists():
        with single.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        # 分卷签库：大数据集拆成目录（manifest.json + part-*.json），
        # 避免单个文件过大。合并后与单文件格式完全一致。
        data = _load_sharded(set_id, Path(data_dir) / set_id)
        if data is None:
            raise DomainDataMissingError(
                f"签库不存在：{single}（或分卷目录 {set_id}/manifest.json）。"
                "请将合法签库放入该目录，或改用已存在的签库。"
            )

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


def _load_sharded(set_id: str, shard_dir: Path) -> dict[str, Any] | None:
    """加载分卷签库；目录结构不合法时返回 None（由调用方报"签库不存在"）。

    目录约定：`<set_id>/manifest.json`（元数据，不含 signs）+
    `<set_id>/part-*.json`（每个含 `signs` 数组，按文件名排序合并）。
    """
    manifest_path = shard_dir / "manifest.json"
    if not shard_dir.is_dir() or not manifest_path.exists():
        return None
    with manifest_path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    parts = sorted(shard_dir.glob("part-*.json"))
    if not parts:
        raise DomainDataMissingError(f"分卷签库 {set_id} 没有 part-*.json：{shard_dir}")
    signs: list[dict[str, Any]] = []
    for part_path in parts:
        with part_path.open("r", encoding="utf-8") as fh:
            part = json.load(fh)
        part_signs = part.get("signs")
        if not isinstance(part_signs, list):
            raise DomainDataMissingError(f"分卷 {part_path.name} 缺少 signs 数组")
        signs.extend(part_signs)
    data = dict(manifest)
    data["signs"] = signs
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
    # 分卷签库：子目录（含 manifest.json）
    for sub in sorted(p for p in d.iterdir() if p.is_dir()):
        if not (sub / "manifest.json").exists():
            continue
        try:
            data = _load_raw(sub.name, str(d))
        except DomainDataMissingError:
            continue
        out.append({
            "set_id": sub.name,
            "name": data.get("name", sub.name),
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

    >>> draw_qian(0, set_id="guanyin").number
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
