"""管理台页面的**接线守卫** —— 静态检查那些"页面看起来只是卡住"的故障。

为什么需要这个文件：`admin.html` 是单文件、零依赖、无构建的原生 JS。它没有类型
检查、没有打包校验、没有运行期测试，因此最典型的坏法是：

1. `$('someId')` 写错 → 返回 `null` → `.addEventListener` 抛异常 →
   **整个 `<script>` 从这里往后全都不执行**。现象是页面"某几个按钮没反应"，
   控制台之外完全看不出原因。
2. JS 读了一个后端不返回的字段 → 得到 `undefined` → 界面静默错
   （显示"（空）"、开关永远停在关闭）。这一类连控制台都不报错。
3. 新增了 `data-view="x"` 却忘了加 `view-x` 区块，或忘了更新 `switchView`
   里那份**硬编码的视图名单** → 点了导航什么都不发生。

这三种都不会被后端测试覆盖（后端一切正常），所以必须单独守。

能真正执行 DOM 的浏览器在当前环境**不可用**（RHEL/RDP 会话里 Chromium 起不来，
报 `Chrome exited early ... DevToolsActivePort`，非本仓库可修）。因此这里走静态
检查：能挡住上面三类，但挡不住"逻辑写错"。后者靠 `test_admin_config.py`
在接口层覆盖 + 人工在浏览器里走一遍。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings
from xuanpan_api.runtime_config import RuntimeConfig

PAGE = Path(__file__).parents[2] / "services/api/xuanpan_api/static/admin.html"

#: 托管运行时优先（见 AGENTS.md §5.3），找不到再退回 PATH 上的 node
_MANAGED_NODE = Path.home() / ".workbuddy/binaries/node/versions/22.22.2-3/node.exe"


def _read_page() -> str:
    return PAGE.read_text(encoding="utf-8")


def _html_part(html: str) -> str:
    """`<script>` 之前的 HTML。

    **必须切开再扫**：JS 里有大量 `'<div id="' + x + '">'` 这样的拼接，
    直接对全文扫 `id="..."` 会把它们当成"HTML 里定义过的 id"，
    于是"引用了不存在的 id"这条检查会被自己的字符串骗过去。
    """
    return html.split("<script>", 1)[0]


def _defined_ids(html: str) -> set[str]:
    """页面上**真正会出现**的 id。

    两部分：静态 HTML 里的，加上 JS 字符串里注入进去的（如会话详情卡是
    运行时拼出来的 `#repOut` / `#delBtn`）。只算前者会把合法的动态 id
    误报成"引用了不存在的 id"，于是检查会逼人去删掉正确的引用。
    """
    static = set(re.findall(r'\bid="([A-Za-z][\w-]*)"', _html_part(html)))
    injected = set(re.findall(r'\bid="([A-Za-z][\w-]*)"', _script(html)))
    return static | injected


def _script(html: str) -> str:
    match = re.search(r"<script>(.*?)</script>", html, re.S)
    assert match, "admin.html 里找不到 <script> 块"
    return match.group(1)


def _node() -> str | None:
    if _MANAGED_NODE.exists():
        return str(_MANAGED_NODE)
    return shutil.which("node")


def _fields_read(js: str, var: str) -> set[str]:
    """取出 `var.fieldName` 形式读到的字段名。

    `(?<![.\\w])` 是必需的：没有它，`saved.cleared.join` 里的 `cleared.join`
    会被当成"从 cleared 读了 join 字段"，报出 `join`/`length` 这类假阳性。
    假阳性一多，人就不看这些断言了 —— 那比没有断言更糟。
    """
    pattern = r"(?<![.\w])" + re.escape(var) + r"\.([a-zA-Z_$][a-zA-Z0-9_$]*)"
    return set(re.findall(pattern, js))


# ==========================================================================
# 一、id 接线
# ==========================================================================


class TestIdWiring:
    def test_every_referenced_id_exists(self) -> None:
        """`$('x')` 引用的每个 id 都必须真的会出现。"""
        html = _read_page()
        refs = set(re.findall(r"\$\('([^']+)'\)", _script(html)))

        missing = sorted(refs - _defined_ids(html))
        assert not missing, (
            "以下 id 被 JS 引用但页面上不存在 —— 会导致 `$()` 返回 null、"
            "后续 `.addEventListener` 抛异常，整个脚本从此不再执行：\n"
            + "\n".join(f"  {i}" for i in missing)
        )

    def test_no_duplicate_ids_in_static_html(self) -> None:
        """同一 id 静态出现两次时，`$()` 只会拿到第一个 —— 另一个变成死元素。"""
        ids = re.findall(r'\bid="([^"]+)"', _html_part(_read_page()))
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        assert not dupes, f"静态 HTML 里重复的 id：{dupes}"

    def test_config_panel_ids_are_all_present(self) -> None:
        """配置面板的 id 逐个点名。

        不依赖上一条的"集合包含"关系：上一条在有人把 `$('cfgSave')` 误删成
        `$('x')` 时同样会过（只要 x 存在）。这里钉住的是**面板本身**。
        """
        defined = _defined_ids(_read_page())
        for name in ("view-config", "cfgMsg", "cfgAi", "cfgOther", "aiSummary",
                     "cfgAiStatus", "cfgModelList", "aiProbeHint",
                     "cfgSave", "cfgDiscard", "cfgResetAll", "cfgDirtyNote"):
            assert name in defined, f"配置面板缺少 #{name}"


# ==========================================================================
# 二、视图切换接线
# ==========================================================================


class TestViewWiring:
    def test_every_nav_view_has_a_section(self) -> None:
        html = _read_page()
        views = re.findall(r'data-view="([^"]+)"', _html_part(html))
        ids = set(re.findall(r'\bid="([^"]+)"', _html_part(html)))

        missing = [v for v in views if f"view-{v}" not in ids]
        assert not missing, f"导航项没有对应的区块：{missing}"

    def test_switch_view_list_covers_every_nav_entry(self) -> None:
        """`switchView` 里那份硬编码的视图名单必须与导航一致。

        漏一个的后果很具体：点导航切换过去，但**上一个区块不会隐藏**，
        于是两个视图叠在一起显示。
        """
        html = _read_page()
        views = re.findall(r'data-view="([^"]+)"', _html_part(html))
        js = _script(html)

        match = re.search(r"\['overview'[^\]]*\]\.forEach", js)
        assert match, "switchView 里的视图名单不见了，请恢复或更新本测试"
        listed = re.findall(r"'([a-z0-9_-]+)'", match.group(0))

        assert set(listed) == set(views), (
            f"switchView 名单 {sorted(listed)} 与导航 {sorted(views)} 不一致"
        )

    def test_config_view_is_loaded_on_switch(self) -> None:
        """切到配置页必须触发一次读取，否则进去是一张空表。"""
        js = _script(_read_page())
        assert re.search(r"if \(name === 'config'\)\s*loadConfig\(\)", js), (
            "switchView 里没有为 config 触发 loadConfig"
        )


# ==========================================================================
# 三、字段契约（后端给什么，页面才读什么）
# ==========================================================================


def _config_keys_union() -> dict[str, set[str]]:
    """把各分支都走一遍，取键名并集。

    只走一种状态是不够的：密钥项的 `masked`/`configured` 只在"已配置"时才有意义，
    `override_updated_at` 只在"有覆盖"时出现，`choices`/`minimum` 只对某些 kind
    出现；`ai/status` 还有一条 `available:false`（`xuanpan_ai` 未安装时）的
    分支，只带 `reason`。用单份样本做契约检查，会因为"这次恰好走的是这条路"
    而放过一个只在别的分支下才暴露的字段错。
    """
    settings_keys: set[str] = set()
    effective_keys: set[str] = set()
    patch_keys: set[str] = set()
    status_keys: set[str] = set()

    scenarios = (
        ({}, {}),                                                     # 全新：default 来源、密钥未配置
        ({"XUANPAN_AI_MODE": "cost", "XUANPAN_LLM_MODEL": "m"}, {}),   # env 来源
        ({}, {"ai_mode": "quality", "llm.api_key": "sk-probe", "llm.model": "m",
              "cors_origins": ["https://a.test"]}),                    # override 来源、密钥已配置
    )

    class _RouterUnavailable(RuntimeConfig):
        """模拟 `xuanpan_ai` 未安装：`ai_router()` 返回 None。

        这条分支不是假想的 —— `services/ai` 是可选依赖，缺了它接口会走
        `{"available": false, "reason": ...}`，而页面确实读了 `reason`。
        """

        def ai_router(self, store: object) -> None:
            return None

    with tempfile.TemporaryDirectory() as tmp:
        for index, (env, patch) in enumerate(scenarios):
            settings = Settings(db_path=Path(tmp) / f"s{index}.db", admin_token="t")
            app = create_app(settings)
            app.dependency_overrides[get_settings] = lambda s=settings: s
            app.state.runtime_config = RuntimeConfig(settings, env=env)
            headers = {"X-Xuanpan-Admin-Token": "t"}
            with TestClient(app, headers=headers) as client:
                if patch:
                    resp = client.patch("/api/v1/admin/config", json=patch)
                    assert resp.status_code == 200, resp.text
                    patch_keys |= set(resp.json())
                body = client.get("/api/v1/admin/config").json()
                for item in body["settings"]:
                    settings_keys |= set(item)
                effective_keys |= set(body["effective"])
                status_keys |= set(client.get("/api/v1/admin/ai/status").json())

        # 再走一次 ai_router 不可用的分支
        settings = Settings(db_path=Path(tmp) / "norouter.db", admin_token="t")
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        app.state.runtime_config = _RouterUnavailable(settings, env={})
        with TestClient(app, headers={"X-Xuanpan-Admin-Token": "t"}) as client:
            status = client.get("/api/v1/admin/ai/status").json()
            assert status["available"] is False, "该分支应报告不可用"
            status_keys |= set(status)

    return {
        "item": settings_keys,
        "effective": effective_keys,
        "patch": patch_keys,
        "status": status_keys,
    }


class TestPayloadContract:
    """"JS 读的字段" ⊆ "后端给的字段"。

    这条守的是最安静的一类坏法：字段名写错 → `undefined` → 界面显示"（空）"
    或开关永远停在关闭。**不报错、不抛异常**，只是不对。

    每条断言都配一个「读到了东西」的自检。原因：这些都是靠**变量名**定位读取点
    的正则，变量一改名就会读到 0 个字段，于是"没有任何字段错"成立 —— 检查看起来
    是绿的，其实已经空转。这类假绿比没有检查更危险。
    """

    @pytest.fixture(scope="class")
    def keys(self) -> dict[str, set[str]]:
        return _config_keys_union()

    def test_config_item_fields_are_all_provided(self, keys: dict[str, set[str]]) -> None:
        js = _script(_read_page())
        reads = _fields_read(js, 'item')
        assert reads, "没有从配置条目读到任何字段，检查已空转"
        unknown = sorted(reads - keys["item"])
        assert not unknown, (
            f"页面读取了后端不提供的配置字段：{unknown}\n"
            f"后端实际提供：{sorted(keys['item'])}"
        )

    def test_effective_fields_are_all_provided(self, keys: dict[str, set[str]]) -> None:
        """只看真正持有 `effective` 的那个变量（页面里叫 `eff`）。

        不能写成宽松的 `\\be\\.` —— 那会把 `catch (e)` 的 `e.key`、
        `beforeunload` 的 `e.preventDefault` 一起收进来，报一堆假阳性，
        检查随即失去判别力（人也就不再看了）。
        """
        js = _script(_read_page())
        assert "const eff = cfgData.effective" in js, (
            "承载 effective 的变量被改名了 —— 本检查靠这个名字定位读取点，"
            "改名会让它静默变成空转（读到 0 个字段也算通过）。请同步更新本测试。"
        )
        reads = _fields_read(js, 'eff')
        assert reads, "没有从 effective 读到任何字段，检查已空转"
        unknown = sorted(reads - keys["effective"])
        assert not unknown, (
            f"页面从 effective 读了不存在的字段：{unknown}；后端提供：{sorted(keys['effective'])}"
        )

    def test_save_response_fields_are_all_provided(self, keys: dict[str, set[str]]) -> None:
        """保存与清除两种响应的字段都取自同一套后端返回结构。

        页面里分别叫 `saved` / `cleared` —— 与探针响应的 `probe` **刻意不同名**：
        同名会让两套结构混在一起判，检查就分不清是哪一处读错了。
        """
        js = _script(_read_page())
        for name in ("saved", "cleared"):
            reads = _fields_read(js, name)
            assert reads, f"没有从 {name} 响应读到任何字段，检查已空转"
            unknown = sorted(reads - keys["patch"])
            assert not unknown, (
                f"页面从 {name} 响应读了不存在的字段：{unknown}；"
                f"后端提供：{sorted(keys['patch'])}"
            )

    def test_ai_status_fields_are_all_provided(self, keys: dict[str, set[str]]) -> None:
        js = _script(_read_page())
        reads = _fields_read(js, 'st')
        assert reads, "没有从 ai/status 读到任何字段，检查已空转"
        unknown = sorted(reads - keys["status"])
        assert not unknown, (
            f"页面从 ai/status 读了不存在的字段：{unknown}；后端提供：{sorted(keys['status'])}"
        )

    def test_model_probe_fields_are_all_provided(self) -> None:
        """模型探针响应的字段。成功与失败两种形状都要覆盖。"""
        js = _script(_read_page())
        reads = _fields_read(js, 'probe')
        assert reads, "没有从探针响应读到任何字段，检查已空转"
        allowed = {"available", "models", "count", "current", "current_in_list",
                   "note", "reason", "hint", "url"}
        unknown = sorted(reads - allowed)
        assert not unknown, f"页面从探针响应读了不存在的字段：{unknown}"

    def test_provider_row_fields_are_all_provided(self) -> None:
        """provider 行读的是 `p.*`，取自 `available_providers()` 的条目。"""
        js = _script(_read_page())
        reads = _fields_read(js, 'p')
        assert reads, "没有从 provider 行读到任何字段，检查已空转"
        # available_providers 的条目 = describe() 的字段 + name/capability/available
        allowed = {"name", "capability", "available", "model", "requires_api_key",
                   "base_url", "timeout"}
        unknown = sorted(reads - allowed)
        assert not unknown, f"provider 行读取了不存在的字段：{unknown}"

    def test_labels_cover_every_registry_key(self) -> None:
        """每个注册表里的配置项都要有中文名 —— 否则界面会露出技术键名。

        露出来不致命，但会让运维在两个名字之间来回对照，多一层出错机会。
        """
        from xuanpan_api.runtime_config import SPEC_BY_KEY

        js = _script(_read_page())
        block = re.search(r"const CFG_LABEL = \{(.*?)\n\};", js, re.S)
        assert block, "CFG_LABEL 不见了，请恢复或更新本测试"
        labeled = set(re.findall(r"'([a-z0-9_.]+)':", block.group(1)))

        missing = sorted(set(SPEC_BY_KEY) - labeled)
        assert not missing, f"这些配置项没有中文名：{missing}"

    def test_label_map_has_no_stale_key(self) -> None:
        """反向：中文名表里不该留已经不存在的配置项。"""
        from xuanpan_api.runtime_config import SPEC_BY_KEY

        js = _script(_read_page())
        block = re.search(r"const CFG_LABEL = \{(.*?)\n\};", js, re.S)
        labeled = set(re.findall(r"'([a-z0-9_.]+)':", block.group(1)))

        stale = sorted(labeled - set(SPEC_BY_KEY))
        assert not stale, f"中文名表里有已被移除的配置项：{stale}"


# ==========================================================================
# 四、脚本可被解析
# ==========================================================================


class TestScriptParses:
    def test_script_passes_node_syntax_check(self, tmp_path: Path) -> None:
        """整段脚本必须能被 JS 引擎解析。

        语法错会让**整个 `<script>` 一行都不执行**：页面能打开、样式正常、
        但什么都不工作 —— 看起来像"服务没起来"，排查方向完全跑偏。
        """
        node = _node()
        if node is None:
            pytest.skip("未找到 node，跳过管理台脚本语法检查")

        target = tmp_path / "admin_script.js"
        target.write_bytes(_script(_read_page()).encode("utf-8"))

        proc = subprocess.run([node, "--check", str(target)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert proc.returncode == 0, f"admin.html 的脚本有语法错误：\n{proc.stderr}"

    def test_no_duplicate_top_level_function_names(self) -> None:
        """同名函数定义两次时，后一个静默覆盖前一个。

        没有模块作用域的单文件脚本里，这是很难发现的一类覆盖 ——
        两边单独看都没问题，行为却是其中一个的。
        """
        names = re.findall(r"^function ([a-zA-Z_$][\w$]*)", _script(_read_page()), re.M)
        dupes = sorted({n for n in names if names.count(n) > 1})
        assert not dupes, f"顶层函数被重复定义（后者会静默覆盖前者）：{dupes}"


# ==========================================================================
# 五、带 body 的请求必须声明 JSON
# ==========================================================================


class TestRequestContentType:
    def test_api_helper_sets_content_type(self) -> None:
        """`api()` 必须显式设 `Content-Type: application/json`。

        fetch 对**字符串** body 默认发 `text/plain;charset=UTF-8`，服务端按
        JSON 解析会直接给 422。这个坑此前一直没暴露，因为 `api()` 只被用于
        GET / DELETE（都没有 body）；配置面板是第一个带 JSON body 的调用。
        """
        js = _script(_read_page())
        block = re.search(r"async function api\(path, options\) \{(.*?)\n\}", js, re.S)
        assert block, "api() 不见了，请恢复或更新本测试"
        assert "'Content-Type': 'application/json'" in block.group(1), (
            "api() 没有设置 Content-Type —— 带 body 的写接口会得到 422"
        )

    def test_write_calls_go_through_api_helper(self) -> None:
        """配置面板的写操作必须走 `api()`（带令牌 + JSON 头），不能用 `publicApi()`。

        `publicApi` 不发令牌，用它调管理接口只会拿到 401；
        而 401 在界面上与"接口坏了"长得一样。
        """
        js = _script(_read_page())
        for call in re.findall(r"publicApi\(([^\n]*)\)", js):
            assert "/admin/" not in call, (
                f"管理接口被 publicApi 调用（不会带令牌）：{call.strip()}"
            )


__all__: list[str] = []
