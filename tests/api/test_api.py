"""API 层测试 —— 覆盖"拍照 → 确认 → 计算 → 报告 → 追问 → 历史 → 删除"整条链路。

测试策略：
- 用**合成罗盘**（已知真值）代替真实照片，让识别链路可复现
- `force_template=True` 让报告走本地模板 → 输出确定、零成本、无需 API key
- 每个测试用独立临时库，避免相互污染
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings

# ==========================================================================


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """独立临时库；`keep_photos=False` 与生产默认一致（原图不落盘）。"""
    return Settings(db_path=tmp_path / "test.db", keep_photos=False)


@pytest.fixture()
def client(settings: Settings):  # type: ignore[no-untyped-def]
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


def _compass_png(thread_angle: float = 177.0, size: int = 900) -> bytes:
    """合成一张罗盘图（真值已知），返回 PNG 字节。"""
    from xuanpan_vision.testing import render_compass

    buf = io.BytesIO()
    render_compass(size=size, thread_angle=thread_angle).save(buf, format="PNG")
    return buf.getvalue()


def _new_session(client: TestClient, **kw) -> str:  # type: ignore[no-untyped-def]
    resp = client.post("/api/v1/sessions", json=kw)
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


BAZI_INPUT = {
    "year": 1981, "month": 9, "day": 14, "hour": 8, "minute": 0,
    "calendar": "solar", "gender": "male", "timezone": "Asia/Shanghai",
    "longitude": 114.3,
}


# ==========================================================================
# 基础与元信息
# ==========================================================================


class TestOps:
    def test_healthz(self, client: TestClient) -> None:
        body = client.get("/healthz").json()
        assert body["status"] == "ok"
        assert body["keep_photos"] is False

    def test_root_points_to_docs(self, client: TestClient) -> None:
        assert client.get("/").json()["api"] == "/api/v1"

    def test_openapi_generates(self, client: TestClient) -> None:
        """OpenAPI 能生成 = 所有响应模型与签名都是合法的。"""
        spec = client.get("/openapi.json").json()
        assert "/api/v1/scan" in spec["paths"]


class TestMeta:
    def test_mountains_has_24_and_convention(self, client: TestClient) -> None:
        body = client.get("/api/v1/meta/mountains").json()
        assert len(body["mountains"]) == 24
        assert "正北" in body["convention"]
        names = [m["name"] for m in body["mountains"]]
        assert names[0] == "子", "0° 必须是子（正北）"

    def test_question_categories_includes_sensitive(self, client: TestClient) -> None:
        body = client.get("/api/v1/meta/question-categories").json()
        assert "事业" in body["categories"]
        assert body["sensitive"]["健康"].startswith("涉及健康的问题不构成医疗建议")

    def test_ai_providers_lists_template_available(self, client: TestClient) -> None:
        body = client.get("/api/v1/meta/ai-providers").json()
        by_id = {p["id"]: p for p in body["providers"]}
        assert by_id["template"]["available"] is True, "本地模板必须始终可用"
        assert by_id["template"]["requires_api_key"] is False

    def test_capabilities_reports_fenjin_table_state(self, client: TestClient) -> None:
        body = client.get("/api/v1/meta/capabilities").json()
        assert isinstance(body["fenjin_table_available"], bool)

    def test_qian_sets_marks_demo(self, client: TestClient) -> None:
        sets = client.get("/api/v1/meta/qian-sets").json()["sets"]
        assert any(s.get("demo") for s in sets), "演示签库须自带 demo 标记"


# ==========================================================================
# 纯计算预览
# ==========================================================================


class TestCalcPreview:
    def test_compass_preview(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/calc/compass", json={"sitting": "午", "degree": 177.0}
        ).json()
        assert body["facts"]["compass"]["sitting"] == "午"
        assert body["facts"]["compass"]["facing"] == "子"
        assert "compass" in body["tradition"]

    def test_bazi_preview_has_pillars(self, client: TestClient) -> None:
        facts = client.post("/api/v1/calc/bazi", json=BAZI_INPUT).json()["facts"]["bazi"]
        assert set(facts["pillars"]) == {"year", "month", "day", "hour"}
        assert facts["pillars"]["day"] == "乙未", "1981-09-14 日柱应为乙未"
        assert facts["day_master"] == "乙"

    def test_liuyao_preview(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/calc/liuyao",
            json={"method": "yao", "yao_values": [9, 8, 7, 6, 8, 7]},
        ).json()
        facts = body["facts"]["liuyao"]
        # 键名以计算层为准（original_gua 而非 gua_name）；同时锁定变卦与动爻
        assert facts["original_gua"] == "贲"
        assert facts["changed_gua"] == "旅"
        assert facts["moving_positions"] == [1, 4]
        assert facts["has_moving"] is True

    def test_qian_preview_is_deterministic(self, client: TestClient) -> None:
        a = client.post("/api/v1/calc/qian", json={"seed": 20260916}).json()
        b = client.post("/api/v1/calc/qian", json={"seed": 20260916}).json()
        assert a == b, "同一 seed 必须得到同一签"

    def test_naming_preview(self, client: TestClient) -> None:
        body = client.post("/api/v1/calc/naming", json={"name": "张伟"}).json()
        assert body["facts"]["name"]

    def test_preview_does_not_persist(self, client: TestClient) -> None:
        client.post("/api/v1/calc/bazi", json=BAZI_INPUT)
        assert client.get("/api/v1/sessions").json()["total"] == 0

    def test_invalid_category_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/v1/sessions", json={"question_category": "占卜"})
        assert resp.status_code == 422, "未知问题类别必须被拒绝（防静默算错）"

    def test_conflicting_degree_and_sitting_rejected(self, client: TestClient) -> None:
        """角度落在别的山 → 报错，不静默纠正用户输入（RULE-008）。"""
        resp = client.post("/api/v1/calc/compass", json={"sitting": "午", "degree": 30.0})
        assert resp.status_code == 400
        assert "不符" in resp.json()["detail"]

    def test_illegal_mountain_name_returns_400_not_500(self, client: TestClient) -> None:
        """未知山名是**输入问题**，必须 400 并列出可用值。

        早先 `get_mountain` 抛的 KeyError 没人翻译，直接冒成 500 ——
        前端只能显示"服务器错误"，用户根本不知道自己写错了山名。
        """
        resp = client.post("/api/v1/calc/compass", json={"sitting": "戊"})
        assert resp.status_code == 400, resp.text
        assert "不是二十四山之一" in resp.json()["detail"]
        assert "子" in resp.json()["detail"], "必须告诉用户可用值"

    def test_illegal_mountain_in_bazi_is_422(self, client: TestClient) -> None:
        resp = client.post("/api/v1/calc/bazi", json={**BAZI_INPUT, "year": 1800})
        assert resp.status_code == 422, "早于 1900 的年份由契约层拦截"


# ==========================================================================
# 识别链路（RULE-003 / RULE-004）
# ==========================================================================


class TestScan:
    def test_scan_creates_session_and_candidates(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/scan",
            files={"image": ("compass.png", _compass_png(), "image/png")},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        assert body["compass_detected"] is True
        assert body["needs_user_confirmation"] is True, "RULE-004：永不允许自动放行"
        assert body["session_id"].startswith("sess_")

        names = {c["name"] for c in body["mountain_candidates"]}
        assert names == {"子", "午"}, f"177° 的两端应为子/午，实得 {names}"

    def test_scan_preserves_measured_angle(self, client: TestClient) -> None:
        body = client.post(
            "/api/v1/scan",
            files={"image": ("c.png", _compass_png(177.0), "image/png")},
        ).json()
        angles = {c["name"]: c["angle"] for c in body["mountain_candidates"]}
        assert abs(angles["午"] - 177.0) < 2.0, (
            f"实测角必须保留（分金依赖 3° 级精度），实得 {angles['午']}"
        )

    def test_scan_rejects_non_image(self, client: TestClient) -> None:
        resp = client.post("/api/v1/scan", files={"image": ("a.txt", b"not an image", "text/plain")})
        assert resp.status_code == 400

    def test_scan_rejects_empty(self, client: TestClient) -> None:
        resp = client.post("/api/v1/scan", files={"image": ("a.png", b"", "image/png")})
        assert resp.status_code == 400

    def test_scan_rejects_oversized(self, client: TestClient, settings: Settings) -> None:
        blob = b"\x89PNG\r\n\x1a\n" + b"\x00" * (settings.max_upload_bytes + 1)
        resp = client.post("/api/v1/scan", files={"image": ("big.png", blob, "image/png")})
        assert resp.status_code == 413

    def test_scan_does_not_persist_photo(self, client: TestClient, settings: Settings) -> None:
        client.post("/api/v1/scan", files={"image": ("c.png", _compass_png(), "image/png")})
        assert not settings.photo_dir.exists(), "默认不落盘原图（隐私默认）"

    def test_blurry_image_rejected_with_reason(self, client: TestClient) -> None:
        """模糊图必须被拒绝并给出**可执行**的提示，而不是返回空结果。"""
        from xuanpan_vision.testing import render_compass

        buf = io.BytesIO()
        render_compass(size=900, blur=12.0).save(buf, format="PNG")
        body = client.post(
            "/api/v1/scan", files={"image": ("b.png", buf.getvalue(), "image/png")}
        ).json()

        assert body["compass_detected"] is False
        assert body["uncertain_regions"], "必须说明为什么没识别出来"
        assert body["mountain_candidates"] == [], "RULE-003：不确定就不给候选"


class TestCompassConfirm:
    def _scan(self, client: TestClient) -> str:
        return client.post(
            "/api/v1/scan",
            files={"image": ("c.png", _compass_png(177.0), "image/png")},
        ).json()["session_id"]

    def test_confirm_produces_facts(self, client: TestClient) -> None:
        sid = self._scan(client)
        resp = client.post(
            f"/api/v1/sessions/{sid}/compass/confirm",
            json={"sitting": "午", "degree": 177.0},
        )
        assert resp.status_code == 200, resp.text
        facts = resp.json()["facts"]["compass"]
        assert facts["sitting"] == "午"
        assert facts["facing"] == "子"
        # 实测角 → 分金必须真的算出来（3° 级精度，177° 落在午山第几格）
        assert facts["fenjin"] is not None
        assert facts["fenjin"]["index"] is not None

    def test_confirm_forces_confirmed_by_user(self, client: TestClient) -> None:
        """客户端无法通过传 False 绕过确认闸门。"""
        sid = self._scan(client)
        client.post(
            f"/api/v1/sessions/{sid}/compass/confirm",
            json={"sitting": "午", "degree": 177.0},
        )
        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert detail["inputs"]["compass_input"]["confirmed_by_user"] is True
        assert detail["confirm_state"]["confirmed"] is True

    def test_confirm_keeps_recognition_intact(self, client: TestClient) -> None:
        """确认不得覆盖识别原件 —— 用户改了什么必须可追溯（RULE-008）。"""
        sid = self._scan(client)
        before = client.get(f"/api/v1/sessions/{sid}").json()["recognition"]

        # 用户把坐山改成了与识别建议不同的一侧
        client.post(
            f"/api/v1/sessions/{sid}/compass/confirm",
            json={"sitting": "子", "degree": 357.0, "note": "我确定坐山是子"},
        )
        after = client.get(f"/api/v1/sessions/{sid}").json()

        assert after["recognition"] == before, "识别原件不得被确认动作覆盖"
        assert after["confirm_state"]["user_note"] == "我确定坐山是子"

    def test_confirm_conflict_returns_400(self, client: TestClient) -> None:
        sid = self._scan(client)
        resp = client.post(
            f"/api/v1/sessions/{sid}/compass/confirm",
            json={"sitting": "午", "facing": "午"},
        )
        assert resp.status_code == 400

    def test_confirm_requires_a_side(self, client: TestClient) -> None:
        sid = self._scan(client)
        resp = client.post(f"/api/v1/sessions/{sid}/compass/confirm", json={})
        assert resp.status_code == 400

    def test_confirm_unknown_session_404(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sessions/sess_nope/compass/confirm", json={"sitting": "午"}
        )
        assert resp.status_code == 404


# ==========================================================================
# 会话与录入
# ==========================================================================


class TestSessions:
    def test_create_and_get(self, client: TestClient) -> None:
        sid = _new_session(client, question_category="事业", question_text="今年适合换工作吗")
        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert detail["question"]["category"] == "事业"
        assert detail["modules"] == []
        assert detail["facts"] == {}

    def test_patch_inputs_returns_previews(self, client: TestClient) -> None:
        sid = _new_session(client)
        body = client.patch(
            f"/api/v1/sessions/{sid}/inputs",
            json={"bazi": BAZI_INPUT, "naming": {"name": "张伟"}},
        ).json()

        assert set(body["updated"]) == {"bazi", "naming"}
        assert body["previews"]["bazi"]["facts"]["bazi"]["day_master"] == "乙"
        assert body["previews"]["naming"]["facts"]["name"]

    def test_patch_is_incremental(self, client: TestClient) -> None:
        """只传一部分模块时，其余模块必须保持原值。"""
        sid = _new_session(client)
        client.patch(f"/api/v1/sessions/{sid}/inputs", json={"bazi": BAZI_INPUT})
        client.patch(f"/api/v1/sessions/{sid}/inputs", json={"naming": {"name": "张伟"}})

        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert set(detail["modules"]) == {"bazi", "naming"}
        assert detail["inputs"]["bazi_input"]["year"] == 1981

    def test_detail_reports_uncertainties(self, client: TestClient) -> None:
        sid = _new_session(client)
        client.patch(f"/api/v1/sessions/{sid}/inputs", json={"compass": {"sitting": "午"}})
        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert any("向山由坐山对宫推导" in u for u in detail["uncertainties"])

    def test_bad_input_surfaces_as_400_not_silent(self, client: TestClient) -> None:
        sid = _new_session(client)
        resp = client.patch(
            f"/api/v1/sessions/{sid}/inputs",
            json={"bazi": {**BAZI_INPUT, "month": 13}},
        )
        assert resp.status_code == 422, "非法月份必须在契约层就被拦住"

    def test_invalid_input_is_not_persisted(self, client: TestClient) -> None:
        """非法输入必须在落库**之前**被拒绝。

        早先的实现是"先落库、再预览"，于是非法山名被写进库、接口还返回 200，
        下次打开会话直接 500。数据要么完整可用，要么不落。
        """
        sid = _new_session(client)
        assert client.patch(
            f"/api/v1/sessions/{sid}/inputs", json={"compass": {"sitting": "戊"}}
        ).status_code == 400

        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert detail["inputs"]["compass_input"] is None, "非法输入不得落库"
        assert detail["modules"] == []
        assert detail["build_error"] is None, "会话仍应保持可读"

    def test_partial_batch_is_atomic(self, client: TestClient) -> None:
        """一次提交里只要有一个模块非法，整批都不落库（不做半截写入）。"""
        sid = _new_session(client)
        resp = client.patch(
            f"/api/v1/sessions/{sid}/inputs",
            json={"bazi": BAZI_INPUT, "compass": {"sitting": "戊"}},
        )
        assert resp.status_code == 400
        assert client.get(f"/api/v1/sessions/{sid}").json()["modules"] == []

    def test_unknown_field_rejected(self, client: TestClient) -> None:
        """字段名打错必须报错 —— 静默忽略会产出"用默认值算出来"的错误结果。"""
        resp = client.post("/api/v1/calc/compass", json={"sit": "午"})
        assert resp.status_code == 422

    def test_list_and_delete(self, client: TestClient) -> None:
        sid = _new_session(client)
        assert client.get("/api/v1/sessions").json()["total"] == 1

        assert client.delete(f"/api/v1/sessions/{sid}").json()["deleted"] is True
        assert client.get(f"/api/v1/sessions").json()["total"] == 0
        assert client.get(f"/api/v1/sessions/{sid}").status_code == 404

    def test_delete_cascades_reports_and_turns(self, client: TestClient) -> None:
        sid = _new_session(client)
        client.patch(f"/api/v1/sessions/{sid}/inputs", json={"bazi": BAZI_INPUT})
        client.post(f"/api/v1/sessions/{sid}/report", json={"force_template": True})

        assert client.get(f"/api/v1/sessions/{sid}/reports").json()["items"] != []
        client.delete(f"/api/v1/sessions/{sid}")
        assert client.get(f"/api/v1/sessions/{sid}").status_code == 404


# ==========================================================================
# 报告与多轮
# ==========================================================================


class TestReport:
    def _ready_session(self, client: TestClient) -> str:
        sid = _new_session(client, question_category="事业", question_text="今年适合换工作吗")
        client.patch(
            f"/api/v1/sessions/{sid}/inputs",
            json={"compass": {"sitting": "午", "degree": 177.0}, "bazi": BAZI_INPUT},
        )
        return sid

    def test_report_is_three_layers(self, client: TestClient) -> None:
        sid = self._ready_session(client)
        body = client.post(
            f"/api/v1/sessions/{sid}/report", json={"force_template": True}
        ).json()

        report = body["report"]
        assert set(report) >= {"facts", "tradition", "interpretation", "uncertainties", "disclaimer"}
        assert report["facts"]["bazi"]["day_master"] == "乙"
        assert report["interpretation"]["provider"] == "template"

    def test_report_facts_match_recomputed_inputs(self, client: TestClient) -> None:
        """三层不漂移：报告里的 facts 必须与按输入重算的结果逐字节一致。"""
        sid = self._ready_session(client)
        report = client.post(
            f"/api/v1/sessions/{sid}/report", json={"force_template": True}
        ).json()["report"]

        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert report["facts"] == detail["facts"]
        assert report["tradition"] == detail["tradition"]

    def test_report_carries_system_uncertainties(self, client: TestClient) -> None:
        sid = self._ready_session(client)
        report = client.post(
            f"/api/v1/sessions/{sid}/report", json={"force_template": True}
        ).json()["report"]
        assert report["uncertainties"], "不确定性清单必须由系统写入，不能为空"

    def test_report_rejects_empty_session(self, client: TestClient) -> None:
        sid = _new_session(client)
        resp = client.post(f"/api/v1/sessions/{sid}/report", json={"force_template": True})
        assert resp.status_code == 422
        assert "还没有任何可用输入" in resp.json()["detail"]

    def test_report_is_persisted_and_retrievable(self, client: TestClient) -> None:
        sid = self._ready_session(client)
        created = client.post(
            f"/api/v1/sessions/{sid}/report", json={"force_template": True}
        ).json()

        fetched = client.get(f"/api/v1/reports/{created['report_id']}").json()
        assert fetched["payload"] == created["report"], "报告必须原样落库（AI 输出不可重算）"

        listed = client.get(f"/api/v1/sessions/{sid}/reports").json()["items"]
        assert [x["report_id"] for x in listed] == [created["report_id"]]

    def test_report_unknown_session_404(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/sessions/sess_x/report", json={"force_template": True}
        ).status_code == 404

    def test_report_unknown_id_404(self, client: TestClient) -> None:
        assert client.get("/api/v1/reports/rep_nope").status_code == 404

    def test_ask_appends_turns(self, client: TestClient) -> None:
        sid = self._ready_session(client)
        client.post(f"/api/v1/sessions/{sid}/report", json={"force_template": True})
        client.post(
            f"/api/v1/sessions/{sid}/ask",
            json={"question_text": "那如果留在原公司呢？", "force_template": True},
        )

        turns = client.get(f"/api/v1/sessions/{sid}/turns").json()["items"]
        assert [t["role"] for t in turns] == ["user", "assistant", "user", "assistant"]
        assert turns[-1]["content"], "助手回复不得为空"

    def test_ask_does_not_change_facts(self, client: TestClient) -> None:
        """追问改变了问题，但不得改变盘面事实 —— 三层分离的核心保证。"""
        sid = self._ready_session(client)
        before = client.get(f"/api/v1/sessions/{sid}").json()["facts"]
        client.post(
            f"/api/v1/sessions/{sid}/ask",
            json={"question_text": "再看感情方面", "force_template": True},
        )
        after = client.get(f"/api/v1/sessions/{sid}").json()["facts"]
        assert before == after

    def test_ask_on_empty_session_422(self, client: TestClient) -> None:
        sid = _new_session(client)
        resp = client.post(
            f"/api/v1/sessions/{sid}/ask",
            json={"question_text": "在吗", "force_template": True},
        )
        assert resp.status_code == 422


# ==========================================================================
# 持久化策略
# ==========================================================================


class TestPersistencePolicy:
    def test_inputs_are_stored_as_given(self, client: TestClient, settings: Settings) -> None:
        """录入即原样保存（RULE-008）：不篡改、不"顺手规范化"用户数据。"""
        import sqlite3

        sid = _new_session(client)
        client.patch(
            f"/api/v1/sessions/{sid}/inputs",
            json={"bazi": {**BAZI_INPUT, "longitude": 114.3}},
        )
        conn = sqlite3.connect(settings.db_path)
        raw = conn.execute(
            "SELECT bazi_input FROM sessions WHERE session_id = ?", (sid,)
        ).fetchone()[0]
        conn.close()

        import json

        assert json.loads(raw)["longitude"] == 114.3

    def test_no_computed_columns_in_schema(self, client: TestClient, settings: Settings) -> None:
        """库里不应存在"计算结果"列 —— 那会成为与内核不一致的第二真源。"""
        import sqlite3

        conn = sqlite3.connect(settings.db_path)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        conn.close()

        forbidden = {"facts", "tradition", "pillars", "bazi_result", "orientation"}
        assert not (cols & forbidden), f"出现了派生结果列：{cols & forbidden}"

    def test_timestamps_present(self, client: TestClient) -> None:
        sid = _new_session(client)
        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert detail["created_at"] and detail["updated_at"]
        # 可解析即合法
        datetime.fromisoformat(detail["created_at"])


# ==========================================================================
# 图像与识别的边界
# ==========================================================================


class TestImageEdges:
    def test_uniform_image_reports_no_compass(self, client: TestClient) -> None:
        """纯色图（既无圆也无对比）→ 明确告知"没找到罗盘"，不给假候选。"""
        buf = io.BytesIO()
        Image.new("RGB", (900, 900), (200, 200, 200)).save(buf, format="PNG")
        body = client.post(
            "/api/v1/scan", files={"image": ("flat.png", buf.getvalue(), "image/png")}
        ).json()

        assert body["compass_detected"] is False
        assert body["mountain_candidates"] == []
        assert body["needs_user_confirmation"] is True

    def test_scan_result_readable_from_session(self, client: TestClient) -> None:
        sid = client.post(
            "/api/v1/scan",
            files={"image": ("c.png", _compass_png(), "image/png")},
        ).json()["session_id"]

        detail = client.get(f"/api/v1/sessions/{sid}").json()
        assert detail["recognition"]["compass_detected"] is True
        assert detail["recognition"]["needs_user_confirmation"] is True
        assert "scan" == detail["origin"]
