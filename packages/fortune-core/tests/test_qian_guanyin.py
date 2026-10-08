"""观音灵签签库（第三方来源）校验测试。

策略：不复制被测实现，只校验**数据自洽性** ——
签号唯一连续、必填字段非空、total 与声明一致、抽签确定性。
文本本身的准确性本仓库不做断言（见 qian.py 模块声明）。
"""

from __future__ import annotations

import json
from pathlib import Path

from fortune_core.qian import (
    DEFAULT_DATA_DIR,
    draw_qian,
    find_sign_by_number,
    list_qian_sets,
    load_qian_set,
)

SET_ID = "guanyin"


def _raw() -> dict:
    """从分卷目录重组出与单文件等价的数据（manifest + part-*.json 按序合并）。"""
    shard = Path(DEFAULT_DATA_DIR) / SET_ID
    manifest = json.loads((shard / "manifest.json").read_text(encoding="utf-8"))
    signs: list = []
    for part_path in sorted(shard.glob("part-*.json")):
        part = json.loads(part_path.read_text(encoding="utf-8"))
        signs.extend(part["signs"])
    return {**manifest, "signs": signs}


class TestDatasetIntegrity:
    def test_set_registered(self) -> None:
        sets = {s["set_id"]: s for s in list_qian_sets()}
        assert SET_ID in sets
        assert sets[SET_ID]["demo"] is False
        assert sets[SET_ID]["total"] == 100

    def test_total_matches(self) -> None:
        data = _raw()
        assert data["total"] == len(data["signs"]) == 100

    def test_numbers_unique_and_complete(self) -> None:
        data = _raw()
        numbers = [s["number"] for s in data["signs"]]
        assert sorted(numbers) == list(range(1, 101))

    def test_required_fields_non_empty(self) -> None:
        for sign in _raw()["signs"]:
            assert isinstance(sign["number"], int)
            assert sign["level"].strip()
            assert sign["title"].strip()
            assert len(sign["poem"]) == 4 and all(line.strip() for line in sign["poem"])
            assert sign["interpretation"].strip()
            assert sign["advice"].strip()

    def test_levels_within_declared(self) -> None:
        data = _raw()
        declared = set(data["levels"])
        assert declared == {"上吉", "中平", "中凶"}
        assert {s["level"] for s in data["signs"]} <= declared

    def test_provenance_note_present(self) -> None:
        data = _raw()
        assert "shetengteng/tt-qimen" in data["note"]
        assert "未做传世版本校对" in data["note"] or "校对" in data["note"]


class TestShardedFormat:
    """分卷机制本身：用临时目录验证 manifest + part 合并语义。"""

    def test_shard_roundtrip(self, tmp_path) -> None:
        from fortune_core.qian import _load_sharded  # noqa: PLC2701（白盒测内部合并）

        shard = tmp_path / "myset"
        shard.mkdir()
        (shard / "manifest.json").write_text(
            json.dumps({"set_id": "myset", "total": 3}), encoding="utf-8"
        )
        (shard / "part-01.json").write_text(
            json.dumps({"signs": [{"number": 1}, {"number": 2}]}), encoding="utf-8"
        )
        (shard / "part-02.json").write_text(
            json.dumps({"signs": [{"number": 3}]}), encoding="utf-8"
        )
        data = _load_sharded("myset", shard)
        assert data is not None
        assert [s["number"] for s in data["signs"]] == [1, 2, 3]
        assert data["total"] == 3

    def test_missing_manifest_returns_none(self, tmp_path) -> None:
        from fortune_core.qian import _load_sharded

        shard = tmp_path / "empty"
        shard.mkdir()
        assert _load_sharded("empty", shard) is None

    def test_list_includes_sharded_sets(self, tmp_path) -> None:
        from fortune_core.qian import list_qian_sets

        shard = tmp_path / "myset"
        shard.mkdir()
        (shard / "manifest.json").write_text(
            json.dumps({"set_id": "myset", "name": "测试集", "demo": False}),
            encoding="utf-8",
        )
        (shard / "part-01.json").write_text(
            json.dumps({"signs": [{"number": 1}]}), encoding="utf-8"
        )
        sets = {s["set_id"]: s for s in list_qian_sets(str(tmp_path))}
        assert sets["myset"]["total"] == 1
        assert sets["myset"]["name"] == "测试集"


class TestEngineBehavior:
    def test_draw_deterministic(self) -> None:
        a = draw_qian(20261007, set_id=SET_ID)
        b = draw_qian(20261007, set_id=SET_ID)
        assert a == b
        assert a.number == 8  # seed % 100 → 第 8 支（索引 7）

    def test_find_by_number(self) -> None:
        r = find_sign_by_number(1, set_id=SET_ID)
        assert r.number == 1
        assert r.title == "钟离成道"
        assert r.set_id == SET_ID

    def test_guanyin_is_default(self) -> None:
        """默认签库是观音一百签（演示库已于 2026-10-08 按用户要求移除）。"""
        from fortune_core.qian import DEFAULT_SET_ID, draw_qian as draw

        assert DEFAULT_SET_ID == "guanyin"
        assert draw(0).set_id == "guanyin"
