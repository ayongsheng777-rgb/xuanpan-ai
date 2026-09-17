"""管理界面测试 —— 重点是**鉴权**，不是排版。

管理台会列出全部会话记录（含生辰等隐私数据），所以这里要守住的第一件事是：
没有令牌就**拿不到任何数据**，且失败方式是明确的拒绝而非静默放行。

第二件事是回归保护：给管理台加鉴权时，**不能顺手把 App 用的公开接口也锁上**。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings

TOKEN = "test-admin-token-0123456789"


def _client(tmp_path: Path, *, admin_token: str) -> TestClient:
    settings = Settings(db_path=tmp_path / "admin.db", keep_photos=False, admin_token=admin_token)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.fixture()
def locked(tmp_path: Path):  # type: ignore[no-untyped-def]
    """管理界面**未启用**（默认状态）。"""
    with _client(tmp_path, admin_token="") as c:
        yield c


@pytest.fixture()
def unlocked(tmp_path: Path):  # type: ignore[no-untyped-def]
    """已配置令牌。"""
    with _client(tmp_path, admin_token=TOKEN) as c:
        yield c


# ==========================================================================
# 一、安全默认：未配置令牌即关闭
# ==========================================================================


class TestDisabledByDefault:
    def test_overview_refused_when_no_token_configured(self, locked: TestClient) -> None:
        """未配置时必须 403 —— 这是本项目对隐私数据的默认立场。

        刻意不接受「未配置就只读放行」：只读同样泄露隐私，
        那只是把风险描述得小一点。
        """
        r = locked.get("/api/v1/admin/overview")
        assert r.status_code == 403

    def test_refusal_carries_actionable_guidance(self, locked: TestClient) -> None:
        """拒绝时必须告诉人怎么开 —— 否则运维只能去翻代码。"""
        detail = locked.get("/api/v1/admin/overview").json()["detail"]
        assert "XUANPAN_ADMIN_TOKEN" in detail
        assert ".env" in detail
        assert "secrets.token_urlsafe" in detail  # 给出可直接照抄的生成命令

    def test_every_admin_endpoint_is_closed(self, locked: TestClient) -> None:
        """逐个端点确认，而不是只测一个就假定整组都受保护。"""
        assert locked.get("/api/v1/admin/sessions").status_code == 403
        assert locked.get("/api/v1/admin/sessions/sess-whatever").status_code == 403
        assert locked.delete("/api/v1/admin/sessions/sess-whatever").status_code == 403
        assert locked.get("/api/v1/admin/reports/rep-whatever").status_code == 403

    def test_page_itself_is_still_reachable(self, locked: TestClient) -> None:
        """页面必须能打开 —— 否则用户陷入「打不开→不知配什么→更打不开」。

        页面是空壳：不含数据、不需要令牌。
        """
        r = locked.get("/admin")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]


# ==========================================================================
# 二、令牌校验
# ==========================================================================


class TestAuth:
    def test_no_token_is_401(self, unlocked: TestClient) -> None:
        assert unlocked.get("/api/v1/admin/overview").status_code == 401

    def test_wrong_token_is_401(self, unlocked: TestClient) -> None:
        r = unlocked.get("/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": "nope"})
        assert r.status_code == 401

    def test_header_token(self, unlocked: TestClient) -> None:
        r = unlocked.get("/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": TOKEN})
        assert r.status_code == 200

    def test_query_token(self, unlocked: TestClient) -> None:
        """查询参数这条路径供「首次点链接」用。"""
        assert unlocked.get(f"/api/v1/admin/overview?token={TOKEN}").status_code == 200

    def test_cookie_token(self, unlocked: TestClient) -> None:
        unlocked.cookies.set("xuanpan_admin", TOKEN)
        assert unlocked.get("/api/v1/admin/overview").status_code == 200

    def test_token_not_echoed_back(self, unlocked: TestClient) -> None:
        """响应里绝不能回显令牌 —— 那会让它进日志、进代理缓存。"""
        body = unlocked.get(
            "/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": TOKEN}
        ).text
        assert TOKEN not in body


# ==========================================================================
# 三、令牌到期/为空时的边界
# ==========================================================================


class TestTokenEdges:
    def test_empty_token_param_is_rejected(self, unlocked: TestClient) -> None:
        """空串不能因为「配置了令牌」就蒙混过关。"""
        assert unlocked.get("/api/v1/admin/overview?token=").status_code == 401

    def test_prefix_of_token_rejected(self, unlocked: TestClient) -> None:
        """令牌前缀不得放行。"""
        r = unlocked.get("/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": TOKEN[:10]})
        assert r.status_code == 401


# ==========================================================================
# 四、功能
# ==========================================================================


class TestOverview:
    def test_shape(self, unlocked: TestClient) -> None:
        r = unlocked.get("/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": TOKEN})
        assert r.status_code == 200
        body = r.json()
        assert set(body["counts"]) == {"sessions", "reports", "turns"}
        assert body["counts"] == {"sessions": 0, "reports": 0, "turns": 0}
        assert "db_path" in body["storage"] and "size_bytes" in body["storage"]
        assert body["config"]["admin_enabled"] is True
        assert body["note"]  # 隐私提醒必须在

    def test_rule_tables_reported(self, unlocked: TestClient) -> None:
        """规则表状态必须如实反映 —— 缺表时要能一眼看出是「表没进镜像」。"""
        rt = unlocked.get(
            "/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": TOKEN}
        ).json()["rule_tables"]
        assert rt["zeri_events"]["available"] is True
        assert rt["zeri_events"]["events"] == 17
        assert rt["kangxi_strokes"]["available"] is True
        assert rt["kangxi_strokes"]["verified"] is True
        # 每个条目都必须报告就绪状态，不允许留空。
        # 注意**不要求**「不可用必有 error」：`available=False` 有两种成因 ——
        # 一是规则表本就未提供（fenjin120 当前即如此，属正常状态而非故障），
        # 二是读取过程抛了异常（此时才必须有 error 说明原因）。混为一谈会让
        # 这条断言在正常缺表时误报。
        for name, item in rt.items():
            assert item.get("available") is not None, f"{name} 未报告就绪状态"
            if item.get("error"):
                assert item["available"] is False, f"{name} 有 error 却声称可用"

    def test_counts_reflect_real_sessions(self, unlocked: TestClient) -> None:
        """写一条会话后，统计必须跟着变 —— 防止把统计写成常量。"""
        created = unlocked.post("/api/v1/sessions", json={"title": "管理台测试"})
        assert created.is_success, created.text
        counts = unlocked.get(
            "/api/v1/admin/overview", headers={"X-Xuanpan-Admin-Token": TOKEN}
        ).json()["counts"]
        assert counts["sessions"] == 1


class TestSessions:
    def test_list_and_detail(self, unlocked: TestClient) -> None:
        h = {"X-Xuanpan-Admin-Token": TOKEN}
        sid = unlocked.post("/api/v1/sessions", json={"title": "待查会话"}).json()["session_id"]

        listed = unlocked.get("/api/v1/admin/sessions", headers=h).json()
        assert listed["total"] == 1
        assert listed["items"][0]["session_id"] == sid
        assert listed["items"][0]["title"] == "待查会话"

        detail = unlocked.get(f"/api/v1/admin/sessions/{sid}", headers=h).json()
        assert detail["session"]["session_id"] == sid
        assert detail["reports"] == [] and detail["turns"] == []

    def test_detail_404(self, unlocked: TestClient) -> None:
        r = unlocked.get("/api/v1/admin/sessions/sess-nonexistent",
                         headers={"X-Xuanpan-Admin-Token": TOKEN})
        assert r.status_code == 404

    def test_delete_removes_session(self, unlocked: TestClient) -> None:
        h = {"X-Xuanpan-Admin-Token": TOKEN}
        sid = unlocked.post("/api/v1/sessions", json={"title": "将被删除"}).json()["session_id"]

        assert unlocked.delete(f"/api/v1/admin/sessions/{sid}", headers=h).status_code == 200
        assert unlocked.get(f"/api/v1/admin/sessions/{sid}", headers=h).status_code == 404
        assert unlocked.get("/api/v1/admin/sessions", headers=h).json()["total"] == 0

    def test_delete_404(self, unlocked: TestClient) -> None:
        r = unlocked.delete("/api/v1/admin/sessions/sess-nonexistent",
                            headers={"X-Xuanpan-Admin-Token": TOKEN})
        assert r.status_code == 404

    def test_delete_requires_token(self, unlocked: TestClient) -> None:
        """写操作尤其不能裸奔 —— 未带令牌时不得删掉任何东西。"""
        sid = unlocked.post("/api/v1/sessions", json={"title": "保护中"}).json()["session_id"]
        assert unlocked.delete(f"/api/v1/admin/sessions/{sid}").status_code == 401
        # 确认真的没被删
        assert unlocked.get(f"/api/v1/admin/sessions/{sid}",
                            headers={"X-Xuanpan-Admin-Token": TOKEN}).status_code == 200


class TestReport:
    def test_report_404(self, unlocked: TestClient) -> None:
        r = unlocked.get("/api/v1/admin/reports/rep-nonexistent",
                         headers={"X-Xuanpan-Admin-Token": TOKEN})
        assert r.status_code == 404


# ==========================================================================
# 五、页面内容
# ==========================================================================


class TestAdminPage:
    def test_page_contains_no_data_and_no_token(self, unlocked: TestClient) -> None:
        """空壳页面：既不含令牌，也不含任何业务数据。"""
        html = unlocked.get("/admin").text
        assert TOKEN not in html
        assert "sess-" not in html  # 不该出现任何会话 ID
        assert "XUANPAN_ADMIN_TOKEN" in html  # 但要告诉用户去哪找令牌

    def test_page_avoids_cdn(self, unlocked: TestClient) -> None:
        """容器运行期不出网，任何 CDN 引用都会白屏。"""
        html = unlocked.get("/admin").text
        assert "http://" not in html.replace("http://127.0.0.1", "")
        assert "https://" not in html
        assert "<script src=" not in html

    def test_page_has_token_hygiene(self, unlocked: TestClient) -> None:
        """令牌只进 sessionStorage 并从地址栏抹掉。

        断言针对**调用**而非文本：页面注释里解释了「为什么不写 localStorage」，
        直接断言 `"localStorage" not in html` 会被这段注释误伤 ——
        那样测试就在惩罚"把原因写清楚"这个行为。
        """
        html = unlocked.get("/admin").text
        assert "sessionStorage.setItem" in html
        assert "sessionStorage.getItem" in html
        assert "localStorage.setItem" not in html
        assert "localStorage.getItem" not in html
        assert "replaceState" in html

    def test_every_query_route_has_a_lab_entry(self, unlocked: TestClient) -> None:
        """防漂移：每个查询域路由都必须在试算台有对应入口。

        这条守的是「内核做完 ≠ 用户能用」那个坑 —— 后端加了能力但管理台没接线，
        页面照常渲染、测试照常全绿，只是那个能力**从界面上不可达**。
        所以这里直接用路由路径做断言：加了路由不加面板就会红。

        断言必须带**引号边界**（`'/api/v1/qimen/pan'` 整体匹配）：
        写成裸子串的话，`"/api/v1/qimen/pan" in html` 对
        `/api/v1/qimen/panXYZ` 也成立 —— 路径拼错一位照样绿。
        （这条是变异验证发现断言偏弱后补的。）
        """
        html = unlocked.get("/admin").text
        for path in (
            "/api/v1/almanac/day",
            "/api/v1/zeri/select",
            "/api/v1/duan/liuyao",
            "/api/v1/calc/bazi",
            "/api/v1/qimen/pan",
        ):
            assert re.search(rf"""['"]{re.escape(path)}['"]""", html), (
                f"试算台缺少 {path} 的入口"
            )

    def test_lab_controls_exist_for_every_panel(self, unlocked: TestClient) -> None:
        """面板的输入与按钮 id 必须齐全 —— 少一个就是点了没反应的死按钮。"""
        html = unlocked.get("/admin").text
        for element_id in (
            # 黄历
            "almDate", "almRun",
            # 择日
            "zeriEvent", "zeriStart", "zeriEnd", "zeriRun",
            # 六爻
            "lyYao", "lyTopic", "lyDate", "lyRun",
            # 八字
            "bzY", "bzM", "bzD", "bzH", "bzRun",
            # 奇门
            "qmDt", "qmSchool", "qmRun", "qmOut",
        ):
            assert f'id="{element_id}"' in html, f"试算台缺少控件 {element_id}"

    def test_lab_ids_are_unique(self, unlocked: TestClient) -> None:
        """重复 id 会让 getElementById 静默拿到错误元素 —— 不报错，只是行为诡异。"""
        html = unlocked.get("/admin").text
        ids = re.findall(r'\bid="([^"]+)"', html)
        duplicated = {i for i in ids if ids.count(i) > 1}
        assert not duplicated, f"存在重复 id：{sorted(duplicated)}"


# ==========================================================================
# 六、回归：加了鉴权不能影响公开接口
# ==========================================================================


class TestPublicRoutesUnaffected:
    def test_sessions_api_still_open(self, unlocked: TestClient) -> None:
        """App 用的接口不能被管理台的鉴权波及 —— 它们本来就没有令牌可带。"""
        assert unlocked.get("/api/v1/sessions").status_code == 200
        assert unlocked.get("/api/v1/meta/mountains").status_code == 200
        assert unlocked.post("/api/v1/calc/bazi", json={
            "year": 1981, "month": 9, "day": 14, "hour": 10,
        }).status_code == 200

    def test_new_query_routes_still_open(self, unlocked: TestClient) -> None:
        assert unlocked.get("/api/v1/almanac/day?date=2026-09-17").status_code == 200
        assert unlocked.get("/api/v1/zeri/events").status_code == 200
        assert unlocked.post("/api/v1/duan/liuyao", json={
            "yao_values": [7, 7, 7, 7, 7, 7], "cast_date": "2026-09-17",
        }).status_code == 200

    def test_healthz_still_open(self, unlocked: TestClient) -> None:
        """健康检查是编排探活用的，绝不能要求令牌。"""
        assert unlocked.get("/healthz").status_code == 200
