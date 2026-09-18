"""罗盘模板库 API 测试。

## 这组测试守的是什么

模板的接口语义里有两处「写错了也不报错、只是行为不对」：

1. **PATCH 必须是局部更新。** 若实现成"字段全变 Optional 的全量覆盖"，
   列表页点一下收藏（只传 `is_favorite`）会把没传的 `name` 抹成 `None` ——
   接口返回 200、模板还在，只是名字没了。用户完全不知道发生了什么。
2. **`is_favorite` 出参必须是 JSON bool。** 存的是 SQLite 的 0/1，
   若漏了归一，前端收到 `0`；而 `if (tpl.is_favorite)` 在 0 上恰好也工作
   （0 是 falsy），于是这个谎话能藏很久，直到某处写成 `=== false`。

排序用**受控时钟**（每次调用递增一秒）而不是 sleep ——
靠真实时间排序的测试在 CI 上会随机红。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import xuanpan_api.storage as storage_mod
from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings

BASE = "/api/v1/templates"


@pytest.fixture()
def client(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = Settings(db_path=tmp_path / "templates.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def clock(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """受控时钟：每次取时间都前进一秒。

    为什么要它：`Store` 用秒级时间戳，同一秒内建的多个模板
    `created_at` 完全相同，"最近优先"的排序就无法断言。
    用 `time.sleep(1)` 能解决但要跑好几秒，且在慢机器上仍可能翻车。
    """

    class _Clock:
        def __init__(self) -> None:
            self.t = datetime(2026, 1, 1, 0, 0, 0)

        def __call__(self) -> str:
            self.t += timedelta(seconds=1)
            return self.t.isoformat(timespec="seconds")

    c = _Clock()
    monkeypatch.setattr(storage_mod, "_now", c)
    return c


def _create(client: TestClient, name: str, **kw: object) -> dict:
    body = {"name": name, "style": "zonghe"}
    body.update(kw)
    r = client.post(BASE, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _names(client: TestClient) -> list[str]:
    return [t["name"] for t in client.get(BASE).json()["items"]]


# ==========================================================================
# 一、增删查
# ==========================================================================


class TestCrud:
    def test_create_returns_full_record(self, client: TestClient) -> None:
        tpl = _create(client, "李师傅三元盘", sitting="午", facing="子", degree=180.24)
        assert tpl["name"] == "李师傅三元盘"
        assert tpl["style"] == "zonghe"
        assert tpl["sitting"] == "午"
        assert tpl["facing"] == "子"
        assert tpl["degree"] == pytest.approx(180.24)
        assert tpl["template_id"].startswith("tpl_")
        # 新建即带时间戳：列表要能显示"上次使用时间"，出厂就得有值
        assert tpl["created_at"] and tpl["updated_at"]
        assert tpl["use_count"] == 0
        assert tpl["last_used_at"] is None

    def test_is_favorite_is_json_bool_not_int(self, client: TestClient) -> None:
        """🔴 必须是 JSON 的 true/false，不能是 1/0。

        存储层存的是 SQLite 的 0/1；漏了归一的话前端收到 `0`，
        而 `if (tpl.is_favorite)` 在 0 上恰好工作（falsy），
        于是 TS 里声明的 `boolean` 成了谎话却能藏很久。
        """
        tpl = _create(client, "收藏盘", is_favorite=True)
        assert tpl["is_favorite"] is True, f"应为 bool True，实得 {tpl['is_favorite']!r}"
        raw = client.get(f"{BASE}/{tpl['template_id']}").text
        assert '"is_favorite":true' in raw, f"原始 JSON 里应是 true，实得：{raw[:200]}"

        plain = _create(client, "普通盘")
        assert plain["is_favorite"] is False

    def test_list_returns_items_and_total(self, client: TestClient) -> None:
        _create(client, "A")
        _create(client, "B")
        body = client.get(BASE).json()
        assert body["total"] == 2
        assert len(body["items"]) == 2

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        r = client.get(f"{BASE}/tpl_nonexistent")
        assert r.status_code == 404
        assert "不存在" in r.json()["detail"]

    def test_delete_then_gone(self, client: TestClient) -> None:
        tpl = _create(client, "待删")
        r = client.delete(f"{BASE}/{tpl['template_id']}")
        assert r.status_code == 200 and r.json()["deleted"] is True
        assert client.get(f"{BASE}/{tpl['template_id']}").status_code == 404
        assert _names(client) == []

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        assert client.delete(f"{BASE}/tpl_nope").status_code == 404


# ==========================================================================
# 二、PATCH 必须是局部更新（本节是重点）
# ==========================================================================


class TestPatchIsPartial:
    def test_patch_only_favorite_keeps_other_fields(self, client: TestClient) -> None:
        """🔴 只传 `is_favorite` 时，绝不能把 name / sitting 抹掉。

        这是"全量覆盖 vs 局部更新"的经典陷阱：接口返回 200、
        模板也还在，只是名字变成了 null —— 用户完全看不出发生了什么。
        """
        tpl = _create(client, "李师傅三元盘", sitting="午", facing="子", degree=180.24, note="师傅口传")

        r = client.patch(f"{BASE}/{tpl['template_id']}", json={"is_favorite": True})
        assert r.status_code == 200, r.text
        after = r.json()

        assert after["name"] == "李师傅三元盘", "局部更新把 name 抹掉了"
        assert after["sitting"] == "午"
        assert after["facing"] == "子"
        assert after["degree"] == pytest.approx(180.24)
        assert after["note"] == "师傅口传"
        assert after["is_favorite"] is True
        # 落库后也要一致，不能只是响应体好看
        assert client.get(f"{BASE}/{tpl['template_id']}").json()["name"] == "李师傅三元盘"

    def test_patch_can_explicitly_clear_a_field(self, client: TestClient) -> None:
        """显式传 null 必须能清空字段。

        这条与上一条是一对：`exclude_unset=True`（只收显式给的键）
        能同时满足两者；换成 `exclude_none=True` 上一条通过、这一条挂。
        """
        tpl = _create(client, "有备注", note="占位")
        r = client.patch(f"{BASE}/{tpl['template_id']}", json={"note": None})
        assert r.status_code == 200
        assert r.json()["note"] is None

    def test_patch_without_any_field_is_rejected(self, client: TestClient) -> None:
        """空 PATCH 明确报错，而不是静默返回 200。

        静默成功会让前端以为保存生效了，实际什么都没改。
        """
        tpl = _create(client, "空更新")
        r = client.patch(f"{BASE}/{tpl['template_id']}", json={})
        assert r.status_code == 422

    def test_patch_missing_template_returns_404(self, client: TestClient) -> None:
        r = client.patch(f"{BASE}/tpl_nope", json={"name": "x"})
        assert r.status_code == 404

    def test_patch_rejects_unknown_field(self, client: TestClient) -> None:
        """未知字段必须 422（`ApiModel` 的 `extra="forbid"`）。

        静默忽略打错的字段名，会让人以为设置生效了。
        """
        tpl = _create(client, "字段校验")
        assert client.patch(f"{BASE}/{tpl['template_id']}", json={"nam": "typo"}).status_code == 422


# ==========================================================================
# 三、使用记录
# ==========================================================================


class TestTouch:
    def test_touch_increments_count_and_stamps_time(self, client: TestClient, clock) -> None:  # type: ignore[no-untyped-def]
        tpl = _create(client, "常用盘")
        assert tpl["use_count"] == 0 and tpl["last_used_at"] is None

        first = client.post(f"{BASE}/{tpl['template_id']}/use").json()
        assert first["use_count"] == 1
        assert first["last_used_at"] is not None

        second = client.post(f"{BASE}/{tpl['template_id']}/use").json()
        assert second["use_count"] == 2
        assert second["last_used_at"] >= first["last_used_at"]

    def test_touch_does_not_change_content(self, client: TestClient) -> None:
        """「使用」是副作用，不得顺手改动模板内容。"""
        tpl = _create(client, "只读不改", sitting="卯", note="别动我")
        after = client.post(f"{BASE}/{tpl['template_id']}/use").json()
        assert after["sitting"] == "卯" and after["note"] == "别动我"

    def test_touch_missing_returns_404(self, client: TestClient) -> None:
        assert client.post(f"{BASE}/tpl_nope/use").status_code == 404

    def test_get_list_does_not_touch(self, client: TestClient) -> None:
        """🔴 读列表不得产生副作用。

        若"打开列表"就给每个模板记一次使用，排序会当场失效 ——
        列表页是最常打开的页面，用几次之后所有模板的 last_used_at 都一样。
        """
        tpl = _create(client, "列表不改数")
        client.get(BASE)
        client.get(f"{BASE}/{tpl['template_id']}")
        assert client.get(f"{BASE}/{tpl['template_id']}").json()["use_count"] == 0


# ==========================================================================
# 四、排序
# ==========================================================================


class TestOrdering:
    def test_favorite_first(self, client: TestClient, clock) -> None:  # type: ignore[no-untyped-def]
        _create(client, "普通一")
        _create(client, "普通二")
        _create(client, "常用盘", is_favorite=True)
        assert _names(client)[0] == "常用盘", "常用模板必须在最上面（列表是给手指点的）"

    def test_recently_used_before_never_used(self, client: TestClient, clock) -> None:  # type: ignore[no-untyped-def]
        old = _create(client, "早建未用")
        _create(client, "晚建未用")
        # 早建的那个被用过 → 应排到前面
        client.post(f"{BASE}/{old['template_id']}/use")
        assert _names(client)[0] == "早建未用", (
            "最近使用的模板未排到最前：COALESCE(last_used_at, created_at) 的排序失效了"
        )

    def test_newest_first_when_all_unused(self, client: TestClient, clock) -> None:  # type: ignore[no-untyped-def]
        _create(client, "最先建")
        _create(client, "最后建")
        assert _names(client) == ["最后建", "最先建"]


# ==========================================================================
# 五、盘式 id 不校验枚举（刻意的设计）
# ==========================================================================


class TestStyleNotValidated:
    def test_unknown_style_is_accepted(self, client: TestClient) -> None:
        """未知盘式 id 必须能存能读。

        🔴 后端刻意**不**维护「盘式 → 层数」表（那份表在前端 dialStyle.ts）。
        如果这里加了枚举校验，删掉某个盘式后，旧模板会变成打不开的 500 ——
        而正确的行为是读出来、由前端 `coerceDialStyle` 回落到默认盘。
        """
        tpl = _create(client, "旧版盘", style="legacy_pan_v9")
        assert tpl["style"] == "legacy_pan_v9"
        assert client.get(f"{BASE}/{tpl['template_id']}").json()["style"] == "legacy_pan_v9"

    def test_style_length_is_bounded(self, client: TestClient) -> None:
        r = client.post(BASE, json={"name": "超长盘式", "style": "x" * 40})
        assert r.status_code == 422
