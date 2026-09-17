"""查询域 API 测试 —— 黄历 / 择日 / 断卦。

这三组是**无状态查询**：不落库、不产生会话、不进 `FortuneContext`。
因此测试也刻意不建会话 —— 若哪天有人把它们接进了会话体系，这里会立刻变红。

测试策略与 `test_api.py` 一致：独立临时库 + TestClient，
另加两条**独立复算**断言（不复制实现，直接用 lunar-python 对拍），
避免接口与内核一起漂移还全绿。
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
    settings = Settings(db_path=tmp_path / "query.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


# ==========================================================================
# 一、黄历
# ==========================================================================


class TestAlmanac:
    def test_single_day_anchor(self, client: TestClient) -> None:
        """固定锚点：2026-09-17。数字写死，库变了就要显式面对。"""
        r = client.get("/api/v1/almanac/day?date=2026-09-17")
        assert r.status_code == 200
        f = r.json()["facts"]
        assert f["solar_date"] == "2026-09-17"
        assert f["gan_zhi"] == {"year": "丙午", "month": "丁酉", "day": "甲午"}
        assert f["jian_chu"] == "收"
        assert f["xiu"] == {"name": "角", "luck": "吉"}
        assert f["tian_shen"]["name"] == "金匮"
        assert f["tian_shen"]["is_huang_dao"] is True
        assert f["chong"]["shengxiao"] == "鼠"
        assert "嫁娶" in f["yi"]

    def test_matches_lunar_python_independently(self, client: TestClient) -> None:
        """独立复算：接口的日干支必须等于 lunar-python 直算值。

        这条不依赖上面的锚点常量，两者互为交叉验证 ——
        接口返回错值但锚点被"顺手改对"的情况会被它抓住。
        """
        from lunar_python import Solar

        for iso in ("2026-01-01", "2026-09-17", "2027-03-08"):
            y, m, d = (int(x) for x in iso.split("-"))
            lunar = Solar.fromYmdHms(y, m, d, 12, 0, 0).getLunar()
            r = client.get(f"/api/v1/almanac/day?date={iso}")
            assert r.status_code == 200
            assert r.json()["facts"]["gan_zhi"]["day"] == lunar.getDayInGanZhi()
            assert r.json()["facts"]["jian_chu"] == lunar.getZhiXing()

    def test_date_optional_defaults_today(self, client: TestClient) -> None:
        r = client.get("/api/v1/almanac/day")
        assert r.status_code == 200
        assert r.json()["facts"]["solar_date"] == date.today().isoformat()

    def test_range_returns_every_day(self, client: TestClient) -> None:
        r = client.get("/api/v1/almanac/range?start=2026-09-17&end=2026-09-23")
        assert r.status_code == 200
        body = r.json()
        assert body["start"] == "2026-09-17" and body["end"] == "2026-09-23"
        assert len(body["days"]) == 7
        assert body["days"][0]["facts"]["solar_date"] == "2026-09-17"
        assert body["days"][-1]["facts"]["solar_date"] == "2026-09-23"

    def test_single_day_range_is_one_day(self, client: TestClient) -> None:
        r = client.get("/api/v1/almanac/range?start=2026-09-17&end=2026-09-17")
        assert r.status_code == 200 and len(r.json()["days"]) == 1

    def test_range_rejects_reversed(self, client: TestClient) -> None:
        r = client.get("/api/v1/almanac/range?start=2026-09-23&end=2026-09-17")
        assert r.status_code == 400
        assert "结束日期早于起始日期" in r.json()["detail"]

    def test_range_rejects_too_long(self, client: TestClient) -> None:
        r = client.get("/api/v1/almanac/range?start=2026-09-01&end=2026-12-31")
        assert r.status_code == 400
        assert "31 天" in r.json()["detail"]

    def test_range_accepts_exactly_limit(self, client: TestClient) -> None:
        """边界值必须放行 —— 差一天就拒会让前端不得不留余量。"""
        r = client.get("/api/v1/almanac/range?start=2026-09-01&end=2026-10-01")
        assert r.status_code == 200 and len(r.json()["days"]) == 31

    def test_bad_date_format_rejected_at_boundary(self, client: TestClient) -> None:
        """非法日期由 pydantic 挡在边界（422），不进内核。"""
        assert client.get("/api/v1/almanac/day?date=not-a-date").status_code == 422


# ==========================================================================
# 二、择日
# ==========================================================================


class TestZeri:
    def test_events_cover_rule_table(self, client: TestClient) -> None:
        """事件清单必须与规则表逐条一致 —— 接口不得私有另一份事件表。"""
        import json

        table_path = Path(__file__).parents[2] / "packages" / "fortune-core" / "data" / "zeri_events.json"
        table = json.loads(table_path.read_text(encoding="utf-8"))

        r = client.get("/api/v1/zeri/events")
        assert r.status_code == 200
        body = r.json()
        assert {e["event"] for e in body["events"]} == set(table["events"])
        assert {s["id"] for s in body["schools"]} == set(table["schools"])
        # 每个事件的宜忌词都必须非空，否则该事件永远筛不出东西
        for e in body["events"]:
            assert e["label"] and e["ji"], f"{e['event']} 缺 label 或忌词"

    def test_evaluate_vetoed_day(self, client: TestClient) -> None:
        """2026-10-05 忌嫁娶，且冲马 → 必须被否决。"""
        r = client.get("/api/v1/zeri/evaluate?event=jiaqu&date=2026-10-05&shengxiao=马")
        assert r.status_code == 200
        d = r.json()["day"]
        assert d["usable"] is False
        assert d["grade"] == "不宜"
        assert any("忌" in v for v in d["veto"])
        assert any("冲马" in v for v in d["veto"])

    def test_evaluate_without_shengxiao_may_pass(self, client: TestClient) -> None:
        """不填属相时，冲煞否决不应生效 —— 否则等于替用户默认了一个属相。"""
        with_zodiac = client.get(
            "/api/v1/zeri/evaluate?event=jiaqu&date=2026-10-05&shengxiao=马"
        ).json()["day"]
        without = client.get(
            "/api/v1/zeri/evaluate?event=jiaqu&date=2026-10-05"
        ).json()["day"]
        assert any("冲马" in v for v in with_zodiac["veto"])
        assert not any("冲" in v for v in without["veto"])

    def test_evaluate_labels_from_rule_table(self, client: TestClient) -> None:
        r = client.get("/api/v1/zeri/evaluate?event=jiaqu&date=2026-09-17")
        body = r.json()
        assert body["event_label"] == "嫁娶"
        assert body["school_name"] == "通行黄历择日"
        assert body["event_note"]  # 规则表里写了备注，接口必须透出

    def test_select_orders_by_score_desc(self, client: TestClient) -> None:
        r = client.post("/api/v1/zeri/select", json={
            "event": "jiaqu", "start": "2026-10-01", "end": "2026-12-31",
            "shengxiao": "马", "limit": 5,
        })
        assert r.status_code == 200
        body = r.json()
        cands = body["facts"]["candidates"]
        assert len(cands) == 5
        scores = [c["score"] for c in cands]
        assert scores == sorted(scores, reverse=True)
        assert body["facts"]["range"]["days_scanned"] == 92
        assert all(c["usable"] for c in cands)

    def test_select_excludes_zodiac_clash(self, client: TestClient) -> None:
        """属马时，被筛出的候选日一律不得冲马。"""
        r = client.post("/api/v1/zeri/select", json={
            "event": "jiaqu", "start": "2026-10-01", "end": "2026-12-31",
            "shengxiao": "马", "limit": 0,
        })
        assert r.status_code == 200
        for c in r.json()["facts"]["candidates"]:
            assert c["chong_shengxiao"] != "马"

    def test_include_unfavorable_returns_rejected(self, client: TestClient) -> None:
        """开启后应能拿到被否决的日子（供解释用），且它们 usable=False。"""
        payload = {"event": "jiaqu", "start": "2026-10-01", "end": "2026-10-31", "limit": 0}
        only_ok = client.post("/api/v1/zeri/select", json=payload).json()
        with_bad = client.post(
            "/api/v1/zeri/select", json={**payload, "include_unfavorable": True}
        ).json()
        assert len(with_bad["facts"]["candidates"]) > len(only_ok["facts"]["candidates"])
        assert any(not c["usable"] for c in with_bad["facts"]["candidates"])

    def test_empty_candidates_is_not_an_error(self, client: TestClient) -> None:
        """候选为空是**合法结果**，必须 200 且给出可读说明。"""
        r = client.post("/api/v1/zeri/select", json={
            "event": "furen", "start": "2026-01-01", "end": "2026-01-03",
        })
        assert r.status_code == 200
        assert r.json()["tradition"]["summary"]  # 有说明文字，不是空白

    def test_unknown_event_is_400_not_500(self, client: TestClient) -> None:
        """**关键**：内核 FortuneError 不继承 ValueError，靠 app.py 的注册转 400。

        若那个处理器被误删，这条会变成 500 —— 而 500 的语义是"服务坏了"，
        会把用户引向完全错误的排查方向。
        """
        r = client.get("/api/v1/zeri/evaluate?event=buzhidao&date=2026-10-05")
        assert r.status_code == 400
        assert r.json()["error"] == "InvalidInputError"
        assert "buzhidao" in r.json()["detail"]

    def test_unknown_school_is_400_not_500(self, client: TestClient) -> None:
        r = client.get("/api/v1/zeri/evaluate?event=jiaqu&date=2026-10-05&school=nope")
        assert r.status_code == 400
        assert r.json()["error"] == "SchoolNotFoundError"

    def test_select_range_cap_enforced(self, client: TestClient) -> None:
        """区间超上限必须报错而不是硬算 —— 十年区间会让请求挂住很久。"""
        r = client.post("/api/v1/zeri/select", json={
            "event": "jiaqu", "start": "2020-01-01", "end": "2032-12-31",
        })
        assert r.status_code == 400
        assert "3660" in r.json()["detail"]

    def test_select_reversed_range_is_400(self, client: TestClient) -> None:
        r = client.post("/api/v1/zeri/select", json={
            "event": "jiaqu", "start": "2026-12-31", "end": "2026-01-01",
        })
        assert r.status_code == 400

    def test_limit_out_of_range_rejected(self, client: TestClient) -> None:
        r = client.post("/api/v1/zeri/select", json={
            "event": "jiaqu", "start": "2026-10-01", "end": "2026-10-31", "limit": 999,
        })
        assert r.status_code == 422


# ==========================================================================
# 三、断卦
# ==========================================================================


class TestDuan:
    def test_liuyao_returns_full_chain(self, client: TestClient) -> None:
        """必须同时给出：吉凶倾向 + 装卦事实 + 依据所用的日辰。"""
        r = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 8, 9, 6, 7, 8], "topic": "财运", "cast_date": "2026-09-17",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] and body["school"]
        assert body["reasons"]
        # 装卦层六爻齐全
        yao = body["detail"]["divination"]["facts"]["yao_details"]
        assert len(yao) == 6
        assert all(y["liu_qin"] in {"父母", "兄弟", "子孙", "妻财", "官鬼"} for y in yao)
        # 依据可追溯
        assert body["detail"]["basis"] == {
            "cast_date": "2026-09-17", "day_pillar": "甲午", "month_pillar": "丁酉",
            "topic": "财运", "gender": None, "yongshen": "妻财",
        }

    def test_liuyao_cast_date_changes_day_pillar(self, client: TestClient) -> None:
        """起卦日是**输入**而非装饰：换一天必须换日辰，否则补录隔夜的卦会算错。"""
        a = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "cast_date": "2026-09-17",
        }).json()["detail"]["basis"]["day_pillar"]
        b = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "cast_date": "2026-10-20",
        }).json()["detail"]["basis"]["day_pillar"]
        assert a != b

    def test_liuyao_matches_zhuang_gua_independently(self, client: TestClient) -> None:
        """独立复算：接口的装卦结果必须与直接调内核逐位一致。

        这条不经过 HTTP 的构造逻辑，能抓住"接口传错参数"这类问题
        （如月令用了另一套口径）。
        """
        from fortune_core.liuyao import cast_liuyao, zhuang_gua

        values = [9, 7, 8, 7, 6, 8]
        expected = zhuang_gua(
            cast_liuyao(yao_values=values),
            day_pillar="甲午", month_pillar="丁酉", topic="事业",
        ).to_dict()

        r = client.post("/api/v1/duan/liuyao", json={
            "yao_values": values, "topic": "事业", "cast_date": "2026-09-17",
        })
        assert r.status_code == 200
        assert r.json()["detail"]["divination"] == expected

    def test_all_categories_resolve_yongshen(self, client: TestClient) -> None:
        """App 里每个可选的类别（除「其他」）都必须取到用神。

        取不到时断卦会退化成与所问之事无关的「中平」—— 看起来正常，实为无效结果。
        """
        from fortune_core.context import QUESTION_CATEGORIES
        from fortune_core.liuyao.zhuang import yongshen_of

        for cat in QUESTION_CATEGORIES:
            if cat in ("其他", "婚姻"):
                continue
            assert yongshen_of(cat) is not None, f"{cat} 取不到用神"

            r = client.post("/api/v1/duan/liuyao", json={
                "yao_values": [7, 7, 7, 7, 7, 7], "topic": cat, "cast_date": "2026-09-17",
            })
            assert r.status_code == 200
            assert r.json()["detail"]["basis"]["yongshen"] is not None

    def test_marriage_category_needs_gender(self, client: TestClient) -> None:
        """婚姻类：传性别则取用神，不传则显式告知未取 —— 两者都不能编造。"""
        with_g = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "topic": "婚姻", "gender": "female",
        }).json()
        assert with_g["detail"]["basis"]["yongshen"] == "官鬼"

        no_g = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "topic": "婚姻",
        }).json()
        assert no_g["detail"]["basis"]["yongshen"] is None
        assert any("未取用神" in u for u in no_g["uncertainties"])

    def test_no_topic_marks_uncertainty(self, client: TestClient) -> None:
        """未指定类别时必须说明，不能把"信息缺失"伪装成"卦象如此"。"""
        body = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "cast_date": "2026-09-17",
        }).json()
        assert any("未指定占问类别" in u for u in body["uncertainties"])

    def test_bad_topic_typo_is_400(self, client: TestClient) -> None:
        """类别打错字必须报错：静默降级会让用户拿到一个无效的「中平」。"""
        r = client.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "topic": "事业运",
        })
        assert r.status_code == 400
        assert "事业运" in r.json()["detail"]
        assert "事业" in r.json()["detail"]  # 报错要列出可用值

    def test_liuyao_bad_yao_values(self, client: TestClient) -> None:
        r = client.post("/api/v1/duan/liuyao", json={"yao_values": [7, 7, 7]})
        assert r.status_code == 422

    def test_bazi_returns_verdict_and_dayun(self, client: TestClient) -> None:
        r = client.post("/api/v1/duan/bazi", json={
            "year": 1981, "month": 9, "day": 14, "hour": 10, "minute": 30, "gender": "male",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] in ("身强", "身弱")
        assert body["school"] == "扶抑法"
        assert body["detail"]["favorable"]
        # 大运倾向逐运给出，且取值受限于三档
        assert body["detail"]["da_yun_verdicts"]
        assert set(body["detail"]["da_yun_verdicts"].values()) <= {"偏吉", "中平", "偏凶"}

    def test_bazi_bad_input_is_422(self, client: TestClient) -> None:
        r = client.post("/api/v1/duan/bazi", json={
            "year": 1981, "month": 13, "day": 14, "hour": 10,
        })
        assert r.status_code == 422
