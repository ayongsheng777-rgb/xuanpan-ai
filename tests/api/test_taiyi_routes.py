"""太乙神数 HTTP 路由测试。

重点不在「能返回 200」，而在四件事：

1. **接口层不得篡改内核结果** —— 路由返回必须与内核直算逐字段一致。
   只断言「有三算字段」的话，接口层偷偷改数据也测不出来。
2. **领域错误必须是 400 而不是 500** —— `SchoolNotFoundError` 不继承 `ValueError`，
   靠 `app.py` 的全局处理器转 400。少了它，「你传错了」会变成「服务坏了」。
3. **领域表与内核同源** —— 九宫表 / 十六神 / 八门不能是另抄一份。
   太乙宫号与洛书逐宫错位，抄错一宫的后果是整盘偏 45° 而不报错。
4. **锚点覆盖关键年份** —— 1972（阳遁第一局，古籍给了完整数字）、
   2004（太乙艮三宫入宫第 3 年）、1984（值事生门）、2002（壬子元第 31 局）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings


@pytest.fixture()
def client(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(db_path=tmp_path / "taiyi.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


class TestTaiyiMeta:
    def test_meta_returns_domain_tables(self, client: TestClient) -> None:
        r = client.get("/api/v1/taiyi/meta")
        assert r.status_code == 200
        body = r.json()
        assert len(body["palace_gua"]) == 9
        assert len(body["palace_direction"]) == 9
        assert len(body["palace_door_name"]) == 9
        assert len(body["shen_names"]) == 16
        assert len(body["shen_palace"]) == 8
        assert len(body["zheng_shen"]) == 8
        assert len(body["jian_shen"]) == 8
        assert len(body["wenchang_seq"]) == 18
        assert len(body["bamen_order"]) == 8
        assert len(body["taiyi_xun_gong"]) == 8
        assert len(body["wuyuan_names"]) == 5

    def test_meta_tables_match_kernel(self, client: TestClient) -> None:
        """接口返回的每一张表都必须与内核同源，不得另抄一份。"""
        from fortune_core.taiyi import (
            BAMEN_BENWEI,
            BAMEN_JIXIONG,
            BAMEN_ORDER,
            JIAN_SHEN,
            LIUHE,  # noqa: F401  (存在性由 meta 的 jishen_rule 间接体现)
            PALACE_DIRECTION,
            PALACE_DOOR_NAME,
            PALACE_FENYE,
            PALACE_GUA,
            PALACE_QI,
            SHEN_NAME,
            SHEN_PALACE,
            TAIYI_XUN_GONG,
            WENCHANG_SEQ_YANG,
            WUYUAN_NAMES,
            ZHENG_GONG_SHEN,
        )

        body = client.get("/api/v1/taiyi/meta").json()

        def strkey(d: dict[int, str]) -> dict[str, str]:
            return {str(k): v for k, v in d.items()}

        assert body["palace_gua"] == strkey(PALACE_GUA)
        assert body["palace_direction"] == strkey(PALACE_DIRECTION)
        assert body["palace_door_name"] == strkey(PALACE_DOOR_NAME)
        assert body["palace_fenye"] == strkey(PALACE_FENYE)
        assert body["palace_qi"] == strkey(PALACE_QI)
        assert body["shen_names"] == dict(SHEN_NAME)
        assert body["shen_palace"] == strkey(SHEN_PALACE)
        assert body["zheng_shen"] == list(ZHENG_GONG_SHEN)
        assert body["jian_shen"] == list(JIAN_SHEN)
        assert body["wenchang_seq"] == list(WENCHANG_SEQ_YANG)
        assert body["bamen_order"] == list(BAMEN_ORDER)
        assert body["bamen_benwei"] == dict(BAMEN_BENWEI)
        assert body["bamen_jixiong"] == dict(BAMEN_JIXIONG)
        assert body["taiyi_xun_gong"] == list(TAIYI_XUN_GONG)
        assert body["wuyuan_names"] == list(WUYUAN_NAMES)

    def test_meta_gong_biao_differs_from_luoshu(self, client: TestClient) -> None:
        """接口下发的九宫表必须与奇门洛书**不同** —— 这是最该防的一处串表。

        若哪天有人为了「复用」把两张表统一了，太乙盘会整体偏 45°，
        而界面上每个字看着都对。
        """
        from fortune_core.qimen.constants import GONG_GUA

        body = client.get("/api/v1/taiyi/meta").json()
        same = [p for p in map(str, range(1, 10)) if body["palace_gua"][p] == GONG_GUA[int(p)]]
        assert same == ["5"], f"除中宫外不应与洛书相同，实际 {same}"

    def test_meta_declares_uncertainties(self, client: TestClient) -> None:
        """未覆盖项必须暴露给界面 —— 用户有权知道这份局没考虑什么。"""
        from fortune_core.taiyi import UNCERTAINTIES

        body = client.get("/api/v1/taiyi/meta").json()
        assert body["uncertainties"] == list(UNCERTAINTIES)
        assert any("年局" in u for u in body["uncertainties"])
        assert any("三基" in u for u in body["uncertainties"])

    def test_meta_lists_schools(self, client: TestClient) -> None:
        body = client.get("/api/v1/taiyi/meta").json()
        assert {s["id"] for s in body["schools"]} == {"default", "taojin"}
        assert body["jiyan_base"] == 10153917

    def test_meta_needs_no_auth(self, client: TestClient) -> None:
        """查询域是给 App 用的，不带令牌也能访问（与 /admin 域不同）。"""
        assert client.get("/api/v1/taiyi/meta").status_code == 200


class TestTaiyiCast:
    #: 阳遁第一局 —— 古籍给了该局的完整数字
    FIRST_JU = {"year": 1972}

    def test_cast_returns_three_counts_and_bamen(self, client: TestClient) -> None:
        r = client.post("/api/v1/taiyi/cast", json=self.FIRST_JU)
        assert r.status_code == 200
        body = r.json()
        assert [s["name"] for s in body["sansuan"]] == ["主算", "客算", "定算"]
        layout = body["bamen"]["layout"]
        assert len(layout) == 8
        # 八门必须恰好覆盖八门各一次、且落在八个非中宫宫位上
        assert sorted(x["door"] for x in layout) == sorted(
            ["开门", "休门", "生门", "伤门", "杜门", "景门", "死门", "惊门"]
        )
        assert sorted(x["palace"] for x in layout) == [1, 2, 3, 4, 6, 7, 8, 9]

    def test_first_ju_anchor(self, client: TestClient) -> None:
        """阳遁第一局（1972）八项锚点 —— 与古籍逐项吻合。"""
        body = client.post("/api/v1/taiyi/cast", json=self.FIRST_JU).json()
        assert body["year_ganzhi"] == "壬子"
        assert body["epoch"]["wuyuan"] == "壬子元"
        assert body["epoch"]["ju"] == 1
        assert body["taiyi"]["palace"] == 1
        assert body["taiyi"]["gua"] == "乾"
        assert body["wenchang"]["pos"] == "申"
        assert body["wenchang"]["name"] == "武德"
        assert body["jishen"]["zhi"] == "寅"
        assert body["shiji"]["pos"] == "坤"
        assert body["dingmu"]["pos"] == "坤"
        assert body["sansuan"][0]["value"] == 7      # 主算
        assert body["sansuan"][1]["value"] == 13     # 客算
        assert body["sansuan"][2]["value"] == 13     # 定算

    def test_2004_anchor(self, client: TestClient) -> None:
        """太乙在艮三宫、入宫第 3 年（理人）。"""
        body = client.post("/api/v1/taiyi/cast", json={"year": 2004}).json()
        assert body["taiyi"]["palace"] == 3
        assert body["taiyi"]["gua"] == "艮"
        assert body["taiyi"]["ru_gong_year"] == 3
        assert body["taiyi"]["li"] == "理人"

    def test_1984_zhishi_men_anchor(self, client: TestClient) -> None:
        body = client.post("/api/v1/taiyi/cast", json={"year": 1984}).json()
        assert body["bamen"]["zhishi"] == "生门"

    def test_2002_epoch_anchor(self, client: TestClient) -> None:
        body = client.post("/api/v1/taiyi/cast", json={"year": 2002}).json()
        assert body["epoch"]["wuyuan"] == "壬子元"
        assert body["epoch"]["ju"] == 31

    def test_cast_matches_kernel_directly(self, client: TestClient) -> None:
        """**接口层不得篡改内核结果** —— 逐字段对拍内核直算。"""
        from fortune_core.taiyi import cast_taiyi

        for year in (1972, 1984, 2002, 2004, 2026):
            body = client.post("/api/v1/taiyi/cast", json={"year": year}).json()
            assert body == cast_taiyi(year).to_dict(), f"{year} 年响应与内核不一致"

    def test_taiyi_never_in_center_palace(self, client: TestClient) -> None:
        """太乙不入中五宫 —— 对**响应体**再验一遍（防止路由串参）。"""
        for year in range(1980, 2060):
            body = client.post("/api/v1/taiyi/cast", json={"year": year}).json()
            assert body["taiyi"]["palace"] != 5, f"{year} 年太乙落中宫"

    def test_zhishi_door_sits_on_taiyi_palace_in_response(
        self, client: TestClient
    ) -> None:
        """响应里值事门必须真的落在太乙宫上（端到端复验布门规则）。"""
        for year in (1972, 1984, 2026):
            body = client.post("/api/v1/taiyi/cast", json={"year": year}).json()
            layout = {x["palace"]: x["door"] for x in body["bamen"]["layout"]}
            assert layout[body["taiyi"]["palace"]] == body["bamen"]["zhishi"]

    def test_counts_have_jiang_and_are_legal(self, client: TestClient) -> None:
        body = client.post("/api/v1/taiyi/cast", json={"year": 2026}).json()
        for s in body["sansuan"]:
            assert 1 <= s["da_jiang"] <= 9
            assert 1 <= s["can_jiang"] <= 9
            assert s["length"] in {"长", "中", "短"}
            assert isinstance(s["san_cai"], list)

    def test_no_fortune_verdict_in_response(self, client: TestClient) -> None:
        """🔴 内核不下吉凶断语：门的吉凶属性可以给（FACT），聚合结论不可以。"""
        body = client.post("/api/v1/taiyi/cast", json={"year": 2026}).json()
        forbidden = {"verdict", "judgement", "judgment", "吉凶", "断语", "结论", "score"}
        assert not (set(body) & forbidden)
        assert not (set(body["taiyi"]) & forbidden)
        for s in body["sansuan"]:
            assert not (set(s) & forbidden)
        assert all(
            x["jixiong"] in {"大吉", "吉", "小吉", "小凶", "大凶"}
            for x in body["bamen"]["layout"]
        )

    def test_cast_is_deterministic(self, client: TestClient) -> None:
        a = client.post("/api/v1/taiyi/cast", json={"year": 2026}).json()
        b = client.post("/api/v1/taiyi/cast", json={"year": 2026}).json()
        assert a == b

    def test_school_switch_changes_result(self, client: TestClient) -> None:
        """两派积年基数差 60，结果必须不同 —— 否则流派开关是摆设。"""
        a = client.post("/api/v1/taiyi/cast", json={"year": 2002}).json()
        b = client.post(
            "/api/v1/taiyi/cast", json={"year": 2002, "school": "taojin"}
        ).json()
        assert a["school"] == "default" and b["school"] == "taojin"
        assert (a["epoch"]["ju"], a["taiyi"]["palace"]) != (
            b["epoch"]["ju"],
            b["taiyi"]["palace"],
        )

    def test_bad_year_is_422(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/taiyi/cast", json={"year": "not-a-year"}
        ).status_code == 422

    def test_missing_year_is_422(self, client: TestClient) -> None:
        assert client.post("/api/v1/taiyi/cast", json={}).status_code == 422

    def test_out_of_range_year_is_422(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/taiyi/cast", json={"year": 99999}
        ).status_code == 422


class TestTaiyiErrors:
    def test_unknown_school_is_400_not_500(self, client: TestClient) -> None:
        """未知流派 → 400。这是「你传错了」而非「服务坏了」。"""
        r = client.post(
            "/api/v1/taiyi/cast", json={"year": 2026, "school": "不存在的流派"}
        )
        assert r.status_code == 400, f"应为 400（调用方错误），实为 {r.status_code}"
        assert "SchoolNotFoundError" in r.json().get("error", "")

    def test_takes_integer_year_not_datetime(self, client: TestClient) -> None:
        """太乙年局的最小单位是年 —— 传 datetime 字符串应当被拒。

        这条防的是「为了接口统一，把三式都改成 datetime」这种顺手重构：
        一旦接受 datetime，用户会以为年局随时辰而变，而那是六壬的性质。
        """
        r = client.post("/api/v1/taiyi/cast", json={"year": "2026-09-17T10:00:00"})
        assert r.status_code == 422
