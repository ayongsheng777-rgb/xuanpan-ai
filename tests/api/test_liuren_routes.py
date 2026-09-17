"""大六壬 HTTP 路由测试。

重点不在"能返回 200"，而在四件事：

1. **接口层不得篡改内核结果** —— 路由返回必须与内核直算逐字段一致。
   若只断言"有三传字段"，接口层偷偷改数据也测不出来。
2. **领域错误必须是 400 而不是 500** —— `SchoolNotFoundError` 不继承 `ValueError`，
   靠 `app.py` 的全局处理器转 400。少了它，"你传错了"会变成"服务坏了"。
3. **领域表与内核同源** —— 月将表 / 寄宫表 / 天将表不能是另抄一份。
4. **锚点覆盖边界路径** —— 下面三个时刻分别是**伏吟**、**涉害**、**贼克**，
   且覆盖昼贵与夜贵两种贵人。三个都已逐宫手工复核过（天地盘、四课、
   十二天将顺逆布、遁干与旬空）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings


@pytest.fixture()
def client(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(db_path=tmp_path / "liuren.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


class TestLiurenMeta:
    def test_meta_returns_domain_tables(self, client: TestClient) -> None:
        r = client.get("/api/v1/liuren/meta")
        assert r.status_code == 200
        body = r.json()
        assert len(body["yuejiang_table"]) == 12, "应有 12 个中气换将位"
        assert len(body["jigong"]) == 10, "十干寄宫应有 10 项"
        assert len(body["guiren"]) == 10
        assert len(body["tianjiang_order"]) == 12
        assert len(body["jiuzongmen"]) == 9

    def test_meta_tables_match_kernel(self, client: TestClient) -> None:
        """接口返回的每一张表都必须与内核同源，不得另抄一份。"""
        from fortune_core.liuren import (
            GUIREN,
            JIGONG,
            JIUZONGMEN,
            JIUZONGMEN_NOTE,
            TIANJIANG_JIXIONG,
            TIANJIANG_ORDER,
            YUEJIANG_NAME,
            ZHONGQI_TO_YUEJIANG,
        )

        body = client.get("/api/v1/liuren/meta").json()
        assert body["yuejiang_table"] == dict(ZHONGQI_TO_YUEJIANG)
        assert body["yuejiang_names"] == dict(YUEJIANG_NAME)
        assert body["jigong"] == dict(JIGONG)
        assert body["guiren"] == {k: list(v) for k, v in GUIREN.items()}
        assert body["tianjiang_order"] == list(TIANJIANG_ORDER)
        assert body["tianjiang_jixiong"] == dict(TIANJIANG_JIXIONG)
        assert body["jiuzongmen"] == list(JIUZONGMEN)
        assert body["jiuzongmen_note"] == dict(JIUZONGMEN_NOTE)

    def test_meta_declares_uncertainties(self, client: TestClient) -> None:
        """未覆盖项必须暴露给界面 —— 用户有权知道这份课没考虑什么。"""
        from fortune_core.liuren import UNCERTAINTIES

        body = client.get("/api/v1/liuren/meta").json()
        assert body["uncertainties"] == list(UNCERTAINTIES)
        assert any("涉害" in u for u in body["uncertainties"])
        assert any("贵人" in u for u in body["uncertainties"])

    def test_meta_lists_schools(self, client: TestClient) -> None:
        body = client.get("/api/v1/liuren/meta").json()
        assert any(s["id"] == "default" for s in body["schools"])

    def test_meta_needs_no_auth(self, client: TestClient) -> None:
        """查询域是给 App 用的，不带令牌也能访问（与 /admin 域不同）。"""
        assert client.get("/api/v1/liuren/meta").status_code == 200


class TestLiurenCast:
    #: 月将巳（处暑后）恰好等于时支巳 —— 走**伏吟**特例
    FUYIN = {"dt": "2026-09-17T10:00:00"}
    #: 月将巳、未时 —— 走**涉害**，昼贵
    SHEHAI = {"dt": "2026-09-17T14:00:00"}
    #: 月将巳、戌时 —— 走**贼克**，夜贵
    ZEIKE = {"dt": "2026-09-17T20:00:00"}

    def test_cast_returns_twelve_palaces_four_lessons_three_chuan(
        self, client: TestClient
    ) -> None:
        r = client.post("/api/v1/liuren/cast", json=self.FUYIN)
        assert r.status_code == 200
        body = r.json()
        assert len(body["palaces"]) == 12
        assert [p["ground"] for p in body["palaces"]] == list(
            "子丑寅卯辰巳午未申酉戌亥"
        )
        assert len(body["lessons"]) == 4
        assert [c["position"] for c in body["chuan"]] == ["初传", "中传", "末传"]

    def test_cast_fuyin_anchor(self, client: TestClient) -> None:
        """伏吟锚点：2026-09-17 10:00，甲午日巳时巳将。

        月将与占时同支 → 天地盘重叠 → 四课只剩两两重出；
        甲为刚日且无克 → 取干上神寅，中末递刑 寅→巳→申。
        """
        body = client.post("/api/v1/liuren/cast", json=self.FUYIN).json()
        assert body["day_ganzhi"] == "甲午"
        assert body["hour_zhi"] == "巳"
        assert body["month_general"] == "巳"
        assert body["month_general_name"] == "太乙"
        assert body["zhongqi"] == "处暑"
        assert body["chuanke"] == "伏吟"
        assert [c["zhi"] for c in body["chuan"]] == ["寅", "巳", "申"]
        # 天地盘重叠：每宫天盘 == 地盘
        assert all(p["ground"] == p["heaven"] for p in body["palaces"])

    def test_cast_shehai_anchor(self, client: TestClient) -> None:
        """涉害锚点：2026-09-17 14:00，甲午日未时巳将（昼贵丑临地盘卯）。"""
        body = client.post("/api/v1/liuren/cast", json=self.SHEHAI).json()
        assert body["hour_zhi"] == "未"
        assert body["chuanke"] == "涉害"
        assert body["guiren"]["is_day"] is True
        assert body["guiren"]["zhi"] == "丑"
        assert body["guiren"]["ground"] == "卯"
        assert body["guiren"]["shun"] is True
        assert [(x["upper"], x["lower_label"]) for x in body["lessons"]] == [
            ("子", "甲"), ("戌", "子"), ("辰", "午"), ("寅", "辰")
        ]
        assert [(c["zhi"], c["general"], c["dun_gan"]) for c in body["chuan"]] == [
            ("戌", "玄武", "戊"), ("申", "白虎", "丙"), ("午", "青龙", "甲")
        ]

    def test_cast_zeike_night_guiren_anchor(self, client: TestClient) -> None:
        """贼克锚点：2026-09-17 20:00，甲午日戌时巳将。

        戌时不在卯~申之内 → 取**夜贵**未（临地盘子，顺布）。
        中传辰落旬空 → 遁干必须为 null（这是领域信号，不是缺数据）。
        """
        body = client.post("/api/v1/liuren/cast", json=self.ZEIKE).json()
        assert body["hour_zhi"] == "戌"
        assert body["chuanke"] == "贼克"
        assert body["guiren"]["is_day"] is False
        assert body["guiren"]["kind"] == "夜贵"
        assert body["guiren"]["zhi"] == "未"
        assert body["guiren"]["ground"] == "子"
        assert [(c["zhi"], c["general"], c["dun_gan"]) for c in body["chuan"]] == [
            ("酉", "朱雀", "丁"), ("辰", "玄武", None), ("亥", "勾陈", "己")
        ]
        assert body["xun_kong"] == ["辰", "巳"]

    def test_cast_matches_kernel_directly(self, client: TestClient) -> None:
        """**接口层不得篡改内核结果** —— 逐字段对拍内核直算。"""
        from fortune_core.liuren import cast_liuren

        for payload in (self.FUYIN, self.SHEHAI, self.ZEIKE):
            body = client.post("/api/v1/liuren/cast", json=payload).json()
            expected = cast_liuren(
                datetime.fromisoformat(payload["dt"])
            ).to_dict()
            assert body == expected

    def test_guiren_ground_holds_guiren_in_response(self, client: TestClient) -> None:
        """响应里贵人落宫必须真的"上面坐着贵人"（反查定义的端到端复验）。

        这条路专门防的是"单测对、接口串参"：若路由把贵人支与落宫对调着传，
        内核单测照样全绿，只有对着**响应体**验一次才看得见。
        """
        for payload in (self.FUYIN, self.SHEHAI, self.ZEIKE):
            body = client.post("/api/v1/liuren/cast", json=payload).json()
            g = body["guiren"]
            palace = next(p for p in body["palaces"] if p["ground"] == g["ground"])
            assert palace["heaven"] == g["zhi"]
            assert palace["general"] == "贵人"
            assert palace["is_guiren_ground"] is True

    def test_chuan_positions_are_on_heaven_plate(self, client: TestClient) -> None:
        """三传之支必须都能在天盘上找到（防止传播公式把三传甩到盘外）。"""
        for payload in (self.FUYIN, self.SHEHAI, self.ZEIKE):
            body = client.post("/api/v1/liuren/cast", json=payload).json()
            heaven = {p["heaven"] for p in body["palaces"]}
            for c in body["chuan"]:
                assert c["zhi"] in heaven

    def test_no_fortune_verdict_in_response(self, client: TestClient) -> None:
        """🔴 内核不下吉凶断语：天将属性可以给（FACT），聚合结论不可以。"""
        body = client.post("/api/v1/liuren/cast", json=self.SHEHAI).json()
        forbidden = {"verdict", "judgement", "judgment", "吉凶", "断语", "结论", "score"}
        assert not (set(body) & forbidden)
        assert all(
            p["general_jixiong"] in {"吉", "凶", None} for p in body["palaces"]
        )

    def test_cast_is_deterministic(self, client: TestClient) -> None:
        a = client.post("/api/v1/liuren/cast", json=self.SHEHAI).json()
        b = client.post("/api/v1/liuren/cast", json=self.SHEHAI).json()
        assert a == b

    def test_bad_datetime_is_422(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/liuren/cast", json={"dt": "not-a-time"}
        ).status_code == 422

    def test_missing_dt_is_422(self, client: TestClient) -> None:
        assert client.post("/api/v1/liuren/cast", json={}).status_code == 422


class TestLiurenErrors:
    def test_unknown_school_is_400_not_500(self, client: TestClient) -> None:
        """未知流派 → 400。这是「你传错了」而非「服务坏了」。"""
        r = client.post(
            "/api/v1/liuren/cast",
            json={"dt": "2026-09-17T10:00:00", "school": "不存在的流派"},
        )
        assert r.status_code == 400, f"应为 400（调用方错误），实为 {r.status_code}"
        assert "SchoolNotFoundError" in r.json().get("error", "")
