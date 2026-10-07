"""每日运程接口测试 —— `/api/v1/daily/fortune`。

无状态查询：不落库、不建会话。另加一条**独立复算**断言
（直接调 fortune_core.daily 对拍），避免接口与内核一起漂移还全绿。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings


@pytest.fixture()
def client(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(db_path=tmp_path / "daily.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


class TestDailyFortune:
    def test_basic(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/daily/fortune",
            json={"birth_date": "1981-05-21", "target_date": "2026-10-07"},
        )
        assert r.status_code == 200
        body = r.json()
        f, t = body["facts"], body["tradition"]
        assert f["date"] == "2026-10-07"
        assert f["day_ganzhi"] == "甲寅"
        assert f["day_master"] == "己"
        assert [d["name"] for d in f["domains"]] == ["事业", "财运", "感情", "健康", "贵人"]
        assert all(1 <= d["stars"] <= 5 for d in f["domains"])
        assert t["summary"]
        # 时辰未知 → tradition 层必须留痕
        assert t["uncertainties"] != []

    def test_matches_core_independently(self, client: TestClient) -> None:
        """独立复算：接口结果必须等于内核直算（防接口/内核一起漂移）。"""
        from fortune_core.daily import daily_fortune

        expected = daily_fortune(date(1981, 5, 21), date(2026, 10, 8), birth_hour=9)
        r = client.post(
            "/api/v1/daily/fortune",
            json={"birth_date": "1981-05-21", "birth_hour": 9, "target_date": "2026-10-08"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["facts"] == expected.to_facts()
        assert body["tradition"] == expected.to_tradition()

    def test_default_date_is_today(self, client: TestClient) -> None:
        r = client.post("/api/v1/daily/fortune", json={"birth_date": "1990-02-28"})
        assert r.status_code == 200
        assert r.json()["facts"]["date"] == date.today().isoformat()

    def test_invalid_birth_hour_rejected(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/daily/fortune",
            json={"birth_date": "1990-02-28", "birth_hour": 25},
        )
        assert r.status_code == 422

    def test_out_of_range_birth_date(self, client: TestClient) -> None:
        r = client.post(
            "/api/v1/daily/fortune",
            json={"birth_date": "1899-12-31", "target_date": "2026-10-07"},
        )
        # 内核抛 InvalidInputError → 应用层统一转 400（见 app.py 异常处理器）
        assert r.status_code == 400
