"""管理台配置接口测试 —— 重点是**改了就生效**与**密钥不泄露**。

这个功能最容易出现的两种失败，都不是报错，而是"看起来正常"：

1. **写了不生效**：接口返回 200、库里也存下了，但业务路径仍读启动时的环境值。
   用户改了模型名，报告按老模型生成 —— 他会以为是自己没保存成功。
   本文件的 `TestTakesEffectWithoutRestart` 专门守这一类。

2. **密钥回显**：配置页把 `llm.api_key` 原样吐出来。它看起来是"功能正常显示"，
   实际是一次泄露（页面可能被截图、被浏览器缓存、被日志采集）。
   `TestSecretNeverEchoed` 用**整段响应体里搜不到明文**来守，而不是只检查某个
   字段名 —— 后者在换个字段名返回时就会失效。

环境变量用注入方式给（`RuntimeConfig(settings, env=...)`），不依赖测试进程的真实
环境：否则开发机上恰好设了 `XUANPAN_LLM_API_KEY` 就会让"来源"断言随机变红。
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings
from xuanpan_api.runtime_config import (
    APPLIES_RESTART,
    SECRET_KEYS,
    SPECS,
    SPEC_BY_KEY,
    RuntimeConfig,
)

TOKEN = "test-admin-token-0123456789"
#：一个不可能自然出现在其它地方的密钥值 —— 用它来证明"响应体里没有它"
SECRET_VALUE = "sk-probe-DEADBEEF-0123456789-abcdefghijklmn"


def make_client(
    tmp_path: Path,
    *,
    env: dict[str, str] | None = None,
    admin_token: str = TOKEN,
    **settings_kw: object,
) -> TestClient:
    """构造客户端。

    默认**带上管理令牌** —— 这是整组管理接口的测试，逐个请求手写 header
    既啰嗦又容易漏一处（漏了就是 401，而 401 与"接口坏了"的表现一样）。
    传 `admin_token=""` 用来验证关闭态。
    """
    settings = Settings(
        db_path=tmp_path / "cfg.db",
        admin_token=admin_token,
        **settings_kw,  # type: ignore[arg-type]
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    # 覆盖 create_app 里那个读真实环境变量的实例，使环境来源可确定
    app.state.runtime_config = RuntimeConfig(settings, env=env or {})
    headers = {"X-Xuanpan-Admin-Token": admin_token} if admin_token else {}
    return TestClient(app, headers=headers)


@pytest.fixture()
def client(tmp_path: Path):  # type: ignore[no-untyped-def]
    with make_client(tmp_path) as c:
        yield c


def _entries(client: TestClient) -> dict[str, dict]:
    body = client.get("/api/v1/admin/config").json()
    return {item["key"]: item for item in body["settings"]}


def _patch(client: TestClient, changes: dict) -> dict:
    r = client.patch("/api/v1/admin/config", json=changes)
    assert r.status_code == 200, r.text
    return r.json()


# ==========================================================================
# 一、鉴权：配置接口本身也在闸门内
# ==========================================================================


class TestRequiresAdmin:
    def test_config_endpoints_refused_without_token(self, tmp_path: Path) -> None:
        with make_client(tmp_path, admin_token="") as locked:
            for method, path in (
                ("get", "/api/v1/admin/config"),
                ("patch", "/api/v1/admin/config"),
                ("post", "/api/v1/admin/config/reset"),
                ("get", "/api/v1/admin/ai/models"),
                ("get", "/api/v1/admin/ai/status"),
            ):
                kwargs = {"json": {}} if method in ("patch", "post") else {}
                r = getattr(locked, method)(path, **kwargs)
                assert r.status_code == 403, f"{method.upper()} {path} 未拦住"

    def test_config_refused_with_wrong_token(self, client: TestClient) -> None:
        r = client.get("/api/v1/admin/config", headers={"X-Xuanpan-Admin-Token": "wrong"})
        assert r.status_code == 401


# ==========================================================================
# 二、来源标注 —— "改了 .env 没变化"必须能一眼看出原因
# ==========================================================================


class TestSourceReporting:
    def test_lists_every_registered_setting(self, client: TestClient) -> None:
        entries = _entries(client)
        assert set(entries) == {s.key for s in SPECS}, "注册表与接口返回不一致"
        assert len(SPECS) == len(SPEC_BY_KEY), "键名重复"

    def test_default_source_when_nothing_set(self, client: TestClient) -> None:
        entry = _entries(client)["llm.model"]
        assert entry["source"] == "default"
        assert entry["source_label"] == "代码默认值"
        assert entry["value"] == ""

    def test_env_source_when_environment_sets_it(self, tmp_path: Path) -> None:
        with make_client(tmp_path, env={"XUANPAN_LLM_MODEL": "gpt-4o-mini"}) as c:
            entry = _entries(c)["llm.model"]
            assert entry["source"] == "env", "环境变量设置后来源应显示为环境变量"
            assert entry["value"] == "gpt-4o-mini"

    def test_override_beats_environment(self, tmp_path: Path) -> None:
        """覆盖必须压过环境变量 —— 这是"优先级"这条规则的实际内容。"""
        with make_client(tmp_path, env={"XUANPAN_LLM_MODEL": "from-env"}) as c:
            _patch(c, {"llm.model": "from-override"})
            entry = _entries(c)["llm.model"]
            assert entry["value"] == "from-override"
            assert entry["source"] == "override"
            assert entry["overridden"] is True
            assert entry["override_updated_at"], "应记录覆盖写入时间"

    def test_clearing_override_falls_back_to_env(self, tmp_path: Path) -> None:
        """清除覆盖要能回到环境值 —— 否则用户没法"撤销"一次误改。

        用 null 表达清除（而不是空字符串）：`llm.api_key` 置空本身是个有意义的
        取值（"我不再用云端了"），与"我没动过这一项"必须能区分。
        """
        with make_client(tmp_path, env={"XUANPAN_LLM_MODEL": "from-env"}) as c:
            _patch(c, {"llm.model": "from-override"})
            result = _patch(c, {"llm.model": None})
            assert result["cleared"] == ["llm.model"]
            assert result["cleared_existing"] == 1, "应报告真的删掉了一行"
            entry = _entries(c)["llm.model"]
            assert entry["value"] == "from-env"
            assert entry["source"] == "env"

    def test_clearing_a_key_that_had_no_override_reports_zero(
        self, client: TestClient
    ) -> None:
        """点了"清除"但本来就没有覆盖 —— 必须能分辨，否则用户以为按钮坏了。"""
        result = _patch(client, {"llm.model": None})
        assert result["cleared"] == ["llm.model"]
        assert result["cleared_existing"] == 0

    def test_restart_required_is_reported(self, client: TestClient) -> None:
        """改了要重启才生效的项必须显式回报，否则会被当成"改动失败"。"""
        result = _patch(client, {"cors_origins": ["http://a.test"]})
        assert "cors_origins" in result["restart_required"]
        assert SPEC_BY_KEY["cors_origins"].applies == APPLIES_RESTART

    def test_immediate_items_not_flagged_as_restart(self, client: TestClient) -> None:
        result = _patch(client, {"ai_mode": "cost"})
        assert result["restart_required"] == []


# ==========================================================================
# 三、密钥永不回显
# ==========================================================================


class TestSecretNeverEchoed:
    def test_api_key_never_appears_in_response_body(self, client: TestClient) -> None:
        """最强形式：整段响应体里搜不到明文，而不是只检查某个字段。"""
        _patch(client, {"llm.api_key": SECRET_VALUE})

        for path in ("/api/v1/admin/config", "/api/v1/admin/overview", "/api/v1/admin/ai/status"):
            text = client.get(path).text
            assert SECRET_VALUE not in text, f"{path} 回显了密钥"

    def test_admin_token_never_appears_in_response_body(self, client: TestClient) -> None:
        text = client.get("/api/v1/admin/config").text
        assert TOKEN not in text, "管理令牌不该出现在配置响应里"

    def test_api_key_reports_configured_mask_and_length(self, client: TestClient) -> None:
        _patch(client, {"llm.api_key": SECRET_VALUE})
        entry = _entries(client)["llm.api_key"]
        assert entry["configured"] is True
        assert entry["length"] == len(SECRET_VALUE)
        assert entry["masked"] != SECRET_VALUE
        # 掩码只暴露首尾极短片段，中间不得出现
        assert SECRET_VALUE[8:20] not in entry["masked"]
        assert "value" not in entry, "密钥项不该带 value 字段（少一个可被误用的字段）"

    def test_unconfigured_secret_reports_false(self, client: TestClient) -> None:
        entry = _entries(client)["llm.api_key"]
        assert entry["configured"] is False
        assert entry["masked"] == ""
        assert entry["length"] == 0

    def test_short_secret_is_fully_masked(self, client: TestClient) -> None:
        """短到无法安全掩码时只给长度，不给任何字符片段。"""
        _patch(client, {"llm.api_key": "abc"})
        entry = _entries(client)["llm.api_key"]
        assert entry["masked"] == "***"
        assert "abc" not in entry["masked"]

    def test_all_secret_keys_are_marked_secret(self) -> None:
        """注册表与脱敏名单必须一致 —— 不一致就是一条静默泄露路径。"""
        declared = {s.key for s in SPECS if s.secret}
        assert declared == set(SECRET_KEYS), (
            f"SECRET_KEYS 与 SPECS 不一致：{declared ^ set(SECRET_KEYS)}"
        )


# ==========================================================================
# 四、校验 —— 坏值要给出可执行的错误
# ==========================================================================


class TestValidation:
    def test_unknown_key_rejected_with_available_list(self, client: TestClient) -> None:
        r = client.patch("/api/v1/admin/config", json={"llm.model_name": "x"})
        assert r.status_code == 400
        assert "llm.model" in r.json()["detail"], "错误里应列出可用项"

    def test_bad_enum_rejected_with_choices(self, client: TestClient) -> None:
        r = client.patch("/api/v1/admin/config", json={"ai_mode": "turbo"})
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert "auto" in detail and "cost" in detail and "quality" in detail

    def test_int_out_of_range_rejected(self, client: TestClient) -> None:
        assert client.patch("/api/v1/admin/config", json={"max_upload_mb": 0}).status_code == 400
        assert client.patch("/api/v1/admin/config", json={"max_upload_mb": 999}).status_code == 400
        assert client.patch("/api/v1/admin/config", json={"max_upload_mb": "abc"}).status_code == 400

    def test_bad_bool_rejected(self, client: TestClient) -> None:
        r = client.patch("/api/v1/admin/config", json={"keep_photos": "maybe"})
        assert r.status_code == 400

    def test_bool_accepts_string_form(self, client: TestClient) -> None:
        """curl 手测时写 `"true"` 是很自然的，别逼人记类型。"""
        _patch(client, {"keep_photos": "true"})
        assert _entries(client)["keep_photos"]["value"] is True

    def test_admin_token_is_not_editable(self, client: TestClient) -> None:
        """令牌不可从界面改：改错它的那一刻，这个界面自己就用不了了。"""
        r = client.patch("/api/v1/admin/config", json={"admin_token": "new"})
        assert r.status_code == 400
        assert "不可从界面修改" in r.json()["detail"]

    def test_rejected_value_is_not_persisted(self, client: TestClient) -> None:
        """校验失败必须**整批拒绝**，不能只写进一半。"""
        r = client.patch(
            "/api/v1/admin/config",
            json={"ai_mode": "cost", "max_upload_mb": 9999},
        )
        assert r.status_code == 400
        assert _entries(client)["ai_mode"]["value"] == "auto", "同批次里合法的项也不该落库"
        assert _entries(client)["ai_mode"]["source"] == "default"


# ==========================================================================
# 五、改了就生效（本文件最重要的一组）
# ==========================================================================


class TestTakesEffectWithoutRestart:
    """这一组必须**先让路由器建起来，再改配置**。

    为什么顺序不能反：若先改配置、再第一次取路由器，那第一次构造就是按新配置
    建的 —— 测试通过，而"配置变了不重建"这个 bug 根本没被碰到。
    变异验证证实过这一点：把指纹比对去掉后，只有先取过一次的用例会红，
    另外两条照样通过。它们当时守的是"配置能被读到"，不是"路由器会重建"。
    """

    def test_ai_mode_change_reaches_the_ai_router(self, client: TestClient) -> None:
        """改 ai_mode 必须让路由器真的重建。

        这条守的是最容易出现的假成功：写库成功、接口 200，但
        `app.state.ai_router` 还是启动时那个旧对象，行为毫无变化。
        """
        assert client.get("/api/v1/admin/ai/status").json()["mode"] == "auto"  # 先把缓存建起来
        _patch(client, {"ai_mode": "quality"})
        assert client.get("/api/v1/admin/ai/status").json()["mode"] == "quality"

    def test_model_change_reaches_the_provider_chain(self, client: TestClient) -> None:
        before = client.get("/api/v1/admin/ai/status").json()  # 先把缓存建起来
        assert [p["name"] for p in before["providers"]] == ["template"], (
            "未配置云端时链上应只有模板兜底"
        )

        _patch(
            client,
            {
                "llm.base_url": "https://llm.example.test/v1",
                "llm.api_key": SECRET_VALUE,
                "llm.model": "probe-model-1",
            },
        )
        status = client.get("/api/v1/admin/ai/status").json()
        assert status["cloud_ready"] is True
        models = [p.get("model") for p in status["providers"]]
        assert "probe-model-1" in models, (
            f"改完模型名后 provider 链仍是旧的（配置没触发重建）：{models}"
        )

    def test_model_change_swaps_the_provider_entry(self, client: TestClient) -> None:
        """再改一次必须换掉，而不是叠出两个云端 provider。"""
        base = {"llm.base_url": "https://llm.example.test/v1", "llm.api_key": SECRET_VALUE}
        _patch(client, {**base, "llm.model": "model-a"})
        primed = client.get("/api/v1/admin/ai/status").json()  # 先把缓存建起来
        assert "model-a" in [p.get("model") for p in primed["providers"]]

        _patch(client, {**base, "llm.model": "model-b"})
        status = client.get("/api/v1/admin/ai/status").json()
        cloud = [p for p in status["providers"] if p["name"] == "openai_compat"]
        assert len(cloud) == 1, f"云端 provider 重复了：{cloud}"
        assert cloud[0]["model"] == "model-b", (
            f"换模型后链上仍是旧模型：{cloud[0].get('model')}"
        )

    def test_cloud_ready_requires_all_three(self, client: TestClient) -> None:
        assert client.get("/api/v1/admin/ai/status").json()["cloud_ready"] is False
        _patch(client, {"llm.base_url": "https://llm.example.test/v1"})
        assert client.get("/api/v1/admin/ai/status").json()["cloud_ready"] is False, (
            "只配了地址不算齐备"
        )
        _patch(client, {"llm.model": "m"})
        assert client.get("/api/v1/admin/ai/status").json()["cloud_ready"] is False, (
            "缺密钥不算齐备"
        )
        _patch(client, {"llm.api_key": SECRET_VALUE})
        assert client.get("/api/v1/admin/ai/status").json()["cloud_ready"] is True

    def test_keep_photos_actually_persists_the_upload(self, tmp_path: Path) -> None:
        """最深一层的证据：改配置后原图**真的落了盘**。

        只在响应里断言 effective.keep_photos 变了是不够的 —— 那只证明
        "展示层读到了新值"，没证明业务路径读的是同一份配置。
        """
        from xuanpan_vision.testing import render_compass

        photos = tmp_path / "photos"
        with make_client(tmp_path, photo_dir=photos) as c:
            buf = io.BytesIO()
            render_compass(size=600, thread_angle=177.0).save(buf, format="PNG")
            payload = buf.getvalue()

            r = c.post("/api/v1/scan", files={"image": ("c.png", payload, "image/png")})
            assert r.status_code == 200, r.text
            assert not list(photos.glob("*")), "默认不落盘：未开启时不该有原件"

            _patch(c, {"keep_photos": True})
            r = c.post("/api/v1/scan", files={"image": ("c.png", payload, "image/png")})
            assert r.status_code == 200, r.text
            assert len(list(photos.glob("*"))) == 1, "开启后应落盘一份原件"

    def test_max_upload_limit_takes_effect(self, tmp_path: Path) -> None:
        """上传上限也要能从界面改 —— 否则"改配置"只覆盖了 AI 那一半。"""
        with make_client(tmp_path, max_upload_bytes=10 * 1024 * 1024) as c:
            big = b"x" * (2 * 1024 * 1024)
            assert c.post("/api/v1/scan", files={"image": ("b.png", big, "image/png")}).status_code != 413

            _patch(c, {"max_upload_mb": 1})
            r = c.post("/api/v1/scan", files={"image": ("b.png", big, "image/png")})
            assert r.status_code == 413, r.text
            assert "1MB" in r.json()["detail"], "错误文案应反映新的上限"

    def test_baseline_settings_are_not_mutated(self, tmp_path: Path) -> None:
        """覆盖不得污染环境基线 —— 两种配置视图必须能分辨。

        若覆盖直接改写 `Settings`，界面就再也回答不了"我清掉覆盖会变回什么"。
        """
        base = Settings(db_path=tmp_path / "cfg.db", admin_token=TOKEN, keep_photos=False)
        app = create_app(base)
        app.dependency_overrides[get_settings] = lambda: base
        app.state.runtime_config = RuntimeConfig(base, env={})
        with TestClient(app, headers={"X-Xuanpan-Admin-Token": TOKEN}) as c:
            _patch(c, {"keep_photos": True})
            assert base.keep_photos is False, "环境基线被改动了"
            assert c.get("/api/v1/admin/config").json()["effective"]["keep_photos"] is True


# ==========================================================================
# 六、持久化 —— 重启后仍在
# ==========================================================================


class TestPersistence:
    def test_override_survives_a_new_app_instance(self, tmp_path: Path) -> None:
        """覆盖落在库里，换一个 app 实例（等价于重启进程）仍要生效。"""
        with make_client(tmp_path) as first:
            _patch(first, {"ai_mode": "quality", "llm.model": "persisted-model"})

        with make_client(tmp_path) as second:
            assert _entries(second)["ai_mode"]["value"] == "quality"
            assert _entries(second)["ai_mode"]["source"] == "override"
            assert second.get("/api/v1/admin/ai/status").json()["mode"] == "quality"
            assert second.get("/api/v1/admin/ai/status").json()["configured_model"] == "persisted-model"

    def test_reset_all_clears_every_override(self, tmp_path: Path) -> None:
        with make_client(tmp_path, env={"XUANPAN_LLM_MODEL": "from-env"}) as c:
            _patch(c, {"ai_mode": "cost", "llm.model": "override-x"})
            r = c.post("/api/v1/admin/config/reset", json=None)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["cleared_existing"] == 2
            assert "admin_token" not in body["cleared"], (
                "全清不该牵扯不可编辑项 —— 它本来就不会有覆盖，"
                "把它算进来会让这个正当操作直接失败"
            )
            entries = _entries(c)
            assert entries["ai_mode"]["source"] == "default"
            assert entries["llm.model"]["value"] == "from-env", "应回落到环境变量而非默认值"

    def test_reset_rejects_unknown_key(self, client: TestClient) -> None:
        assert client.post("/api/v1/admin/config/reset", json=["nope"]).status_code == 400

    def test_reset_rejects_explicitly_naming_a_locked_key(self, client: TestClient) -> None:
        """显式点名不可编辑项才报错 —— 那是调用方真的弄错了。"""
        r = client.post("/api/v1/admin/config/reset", json=["admin_token"])
        assert r.status_code == 400
        assert "不可从界面修改" in r.json()["detail"]


# ==========================================================================
# 七、AI 模型探针 —— 不内置清单，问真实端点
# ==========================================================================


class TestModelProbe:
    def _probe(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        from xuanpan_api.routers.admin import _probe_models

        return _probe_models(*args, **kwargs)

    def test_without_base_url_reports_reason_without_network(self) -> None:
        """没配地址就直说，**不发网络请求** —— 探针不该在缺配置时去连一个空地址。"""
        out = self._probe("", "")
        assert out["available"] is False
        assert "未配置模型接入地址" in out["reason"]
        assert out["hint"], "失败必须给可执行的下一步"

    def test_without_api_key_reports_reason(self) -> None:
        out = self._probe("https://llm.example.test/v1", "")
        assert out["available"] is False
        assert "未配置模型密钥" in out["reason"]

    def test_404_means_endpoint_not_implemented(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """404 与"连不上"是两回事，必须能分辨。"""
        import httpx

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(404, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", fake_get)
        out = self._probe("https://llm.example.test/v1", SECRET_VALUE)
        assert out["available"] is False
        assert "未实现 /models" in out["reason"]
        assert "手动填写模型名" in out["hint"], "网关没这个端点不代表不能用，要告诉用户能怎么绕过"

    def test_401_is_reported_as_auth_problem(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(401, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", fake_get)
        out = self._probe("https://llm.example.test/v1", SECRET_VALUE)
        assert out["available"] is False
        assert "鉴权" in out["reason"]

    def test_network_error_is_distinguished(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx, "get", fake_get)
        out = self._probe("https://llm.example.test/v1", SECRET_VALUE)
        assert out["available"] is False
        assert "无法连接" in out["reason"]

    def test_success_returns_sorted_model_ids(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(
                200,
                json={"data": [{"id": "z-model"}, {"id": "a-model"}, {"nope": 1}]},
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(httpx, "get", fake_get)
        out = self._probe("https://llm.example.test/v1", SECRET_VALUE)
        assert out["available"] is True
        assert out["models"] == ["a-model", "z-model"], "无 id 的条目应被丢掉，不是填充空串"
        assert out["count"] == 2

    def test_unexpected_shape_is_reported(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(200, json={"foo": "bar"}, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", fake_get)
        out = self._probe("https://llm.example.test/v1", SECRET_VALUE)
        assert out["available"] is False
        assert "不是预期的模型列表结构" in out["reason"]

    def test_secret_is_not_in_probe_output(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import httpx

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            raise httpx.ConnectError("boom")

        monkeypatch.setattr(httpx, "get", fake_get)
        out = self._probe("https://llm.example.test/v1", SECRET_VALUE)
        assert SECRET_VALUE not in str(out)

    def test_endpoint_reports_current_model_explicitly(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """当前模型不在列表里不是错误，但必须**说出来**。

        不说的话，用户会以为"列表里没有 = 我配错了"，然后去改一个本来正确的配置。
        """
        import httpx

        _patch(
            client,
            {
                "llm.base_url": "https://llm.example.test/v1",
                "llm.api_key": SECRET_VALUE,
                "llm.model": "private-model",
            },
        )

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            return httpx.Response(
                200, json={"data": [{"id": "public-model"}]}, request=httpx.Request("GET", url)
            )

        monkeypatch.setattr(httpx, "get", fake_get)
        out = client.get("/api/v1/admin/ai/models").json()
        assert out["available"] is True
        assert out["current"] == "private-model"
        assert out["current_in_list"] is False
        assert "不代表它不可用" in out["note"]

    def test_endpoint_uses_configured_base_url(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        """探针必须打在**当前配置的**地址上，而不是某个默认地址。"""
        import httpx

        _patch(client, {"llm.base_url": "https://llm.example.test/v1", "llm.api_key": SECRET_VALUE})
        seen: list[str] = []

        def fake_get(url, **kwargs):  # type: ignore[no-untyped-def]
            seen.append(url)
            return httpx.Response(200, json={"data": []}, request=httpx.Request("GET", url))

        monkeypatch.setattr(httpx, "get", fake_get)
        client.get("/api/v1/admin/ai/models")
        assert seen == ["https://llm.example.test/v1/models"], seen


# ==========================================================================
# 八、概览页与配置页不得互相打架
# ==========================================================================


class TestOverviewConsistency:
    def test_overview_reports_effective_values(self, client: TestClient) -> None:
        """概览页读的必须是生效值。

        两页对同一项给出不同的值，运维会先怀疑缓存或部署问题，
        而实际上只是两处读的不是同一份配置。
        """
        _patch(client, {"ai_mode": "cost", "keep_photos": True})
        cfg = client.get("/api/v1/admin/overview").json()["config"]
        assert cfg["ai_mode"] == "cost"
        assert cfg["keep_photos"] is True
        assert cfg["editable_at"], "应指出去哪儿改"

    def test_healthz_reports_effective_ai_mode(self, client: TestClient) -> None:
        _patch(client, {"ai_mode": "quality"})
        assert client.get("/healthz").json()["ai_mode"] == "quality"

    def test_healthz_reports_cloud_readiness(self, client: TestClient) -> None:
        assert client.get("/healthz").json()["cloud_ai_ready"] is False
        _patch(
            client,
            {
                "llm.base_url": "https://llm.example.test/v1",
                "llm.api_key": SECRET_VALUE,
                "llm.model": "m",
            },
        )
        body = client.get("/healthz").json()
        assert body["cloud_ai_ready"] is True
        assert SECRET_VALUE not in str(body)
