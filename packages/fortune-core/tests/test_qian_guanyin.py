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
    path = Path(DEFAULT_DATA_DIR) / f"{SET_ID}.json"
    return json.loads(path.read_text(encoding="utf-8"))


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

    def test_demo_default_untouched(self) -> None:
        """新增签库不得改变默认签库的行为。"""
        from fortune_core.qian import DEFAULT_SET_ID, draw_qian as draw

        assert DEFAULT_SET_ID == "demo_guanyin"
        assert draw(0).set_id == "demo_guanyin"
