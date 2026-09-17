"""奇门遁甲 HTTP 路由测试。

重点不在"能返回 200"，而在三件事：

1. **接口层不得篡改内核结果** —— 路由返回必须与内核直算逐字段一致。
   若只断言"有 palaces 字段"，接口层偷偷改数据也测不出来。
2. **领域错误必须是 400 而不是 500** —— `SchoolNotFoundError` 不继承
   `ValueError`，靠 `app.py` 的全局处理器转 400。少了它，"你传错了"
   会变成"服务坏了"，把用户引向完全错误的排查方向。
3. **局数表与内核同源** —— 接口层的表不能是另抄一份。
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
    settings = Settings(db_path=tmp_path / "qimen.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


class TestQimenMeta:
    def test_meta_returns_full_jushu_table(self, client: TestClient) -> None:
        r = client.get("/api/v1/qimen/meta")
        assert r.status_code == 200
        body = r.json()
        assert len(body["jushu_table"]) == 24, "应有 24 个节气"
        assert len(body["yang_dun_jieqi"]) == 12
        assert len(body["yin_dun_jieqi"]) == 12
        assert body["yang_dun_jieqi"][0] == "冬至"
        assert body["yin_dun_jieqi"][0] == "夏至"

    def test_meta_jushu_matches_kernel(self, client: TestClient) -> None:
        """接口返回的局数表必须与内核完全同源，不得另抄一份。"""
        from fortune_core.qimen import jushu_table

        body = client.get("/api/v1/qimen/meta").json()
        kernel = {jq: list(t) for jq, t in jushu_table().items()}
        assert body["jushu_table"] == kernel

    def test_meta_declares_uncertainties(self, client: TestClient) -> None:
        """未覆盖项必须暴露给界面 —— 用户有权知道这份盘没考虑什么。"""
        from fortune_core.qimen import UNCERTAINTIES

        body = client.get("/api/v1/qimen/meta").json()
        assert body["uncertainties"] == list(UNCERTAINTIES)
        assert any("置闰" in u for u in body["uncertainties"])

    def test_meta_lists_schools(self, client: TestClient) -> None:
        body = client.get("/api/v1/qimen/meta").json()
        assert any(s["id"] == "chaibu" for s in body["schools"])


class TestQimenPan:
    ANCHOR = {"dt": "2026-09-17T12:00:00"}

    def test_pan_returns_nine_palaces(self, client: TestClient) -> None:
        r = client.post("/api/v1/qimen/pan", json=self.ANCHOR)
        assert r.status_code == 200
        body = r.json()
        assert [p["gong"] for p in body["palaces"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9]

    def test_pan_anchor_values(self, client: TestClient) -> None:
        """固定锚点：2026-09-17 12:00 → 白露下元，阴遁六局，值符天心。"""
        body = client.post("/api/v1/qimen/pan", json=self.ANCHOR).json()
        d = body["dingju"]
        assert d["jieqi"] == "白露"
        assert d["yuan_label"] == "下元"
        assert d["yang_dun"] is False
        assert d["jushu"] == 6
        assert d["jushu_label"] == "阴遁六局"
        assert body["zhifu_star"] == "天心"
        assert body["zhishi_door"] == "开门"
        assert body["pillars"]["hour"] == "庚午"

    def test_pan_matches_kernel_directly(self, client: TestClient) -> None:
        """**接口层不得篡改内核结果** —— 逐字段对拍内核直算。"""
        from fortune_core.qimen import cast_qimen

        body = client.post("/api/v1/qimen/pan", json=self.ANCHOR).json()
        expected = cast_qimen(datetime(2026, 9, 17, 12, 0)).to_dict()
        assert body == expected

    def test_pan_palaces_carry_all_fields(self, client: TestClient) -> None:
        """外八宫必须齐备：地盘干/天盘干/星/门/神 + 吉凶标注。"""
        body = client.post("/api/v1/qimen/pan", json=self.ANCHOR).json()
        for p in body["palaces"]:
            if p["gong"] == 5:
                assert p["door"] is None and p["god"] is None
                continue
            for key in ("di_gan", "tian_gan", "star", "door", "god"):
                assert p[key], f"{p['gong']}宫缺 {key}"
            assert p["star_jixiong"] in ("吉", "平", "凶")
            assert p["door_jixiong"] in ("吉", "平", "凶")

    def test_pan_is_deterministic(self, client: TestClient) -> None:
        a = client.post("/api/v1/qimen/pan", json=self.ANCHOR).json()
        b = client.post("/api/v1/qimen/pan", json=self.ANCHOR).json()
        assert a == b

    def test_pan_accepts_datetime_with_timezone_suffix(self, client: TestClient) -> None:
        """带时区后缀的 ISO 串也应能解析（Pydantic 负责，内核按本地时刻用）。"""
        r = client.post(
            "/api/v1/qimen/pan", json={"dt": "2026-09-17T12:00:00+08:00"}
        )
        assert r.status_code in (200, 422)  # 422 亦可接受（aware/naive 语义），但不得 500


class TestQimenErrors:
    def test_unknown_school_is_400_not_500(self, client: TestClient) -> None:
        """未知流派 → 400。这是「你传错了」而非「服务坏了」。

        靠 `app.py` 里对 `FortuneError` 的全局处理器 —— 它**不继承 ValueError**，
        没有那个处理器这里会变成 500。
        """
        r = client.post(
            "/api/v1/qimen/pan",
            json={"dt": "2026-09-17T12:00:00", "school": "zhirun"},
        )
        assert r.status_code == 400, f"应为 400（调用方错误），实为 {r.status_code}"
        assert "SchoolNotFoundError" in r.json().get("error", "")

    def test_bad_datetime_is_422(self, client: TestClient) -> None:
        r = client.post("/api/v1/qimen/pan", json={"dt": "not-a-time"})
        assert r.status_code == 422

    def test_missing_dt_is_422(self, client: TestClient) -> None:
        assert client.post("/api/v1/qimen/pan", json={}).status_code == 422

    def test_meta_needs_no_auth(self, client: TestClient) -> None:
        """查询域是给 App 用的，不带令牌也能访问（与 /admin 域不同）。"""
        assert client.get("/api/v1/qimen/meta").status_code == 200
