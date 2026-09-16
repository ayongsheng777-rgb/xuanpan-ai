"""`apps/mobile/src/api/types.ts` ↔ 后端真实响应 的契约校验。

## 为什么需要这道测试

移动端的类型定义是**手写**的（`types.ts` 开头就写明"与 schemas.py 一一对应"），
而后端真正返回什么，只有真发一次请求才知道。两者一旦漂移，前端拿到的是
`undefined` —— 界面表现为"某一格空了"，而不是编译失败，最难查。

本轮开发就踩了两次，都是同一类错：

1. `Interpretation` 的原文键是 `raw_text`，前端写成了 `interpretation.text`
   → 追问记录里 AI 的回答会变成空字符串
2. `LayerPreview.facts` 被声明成 `Record<string, unknown>`，
   实际是「模块名 → 对象」两层结构 → 八字页/占测页共 20 处编译报错

第 2 条靠 `tsc` 当场暴露算走运；第 1 条类型完全合法，只有在真机上追问一次
才会发现。所以这里补一道**运行时**校验：把真实响应取回来，
逐字段核对 TS 声明。

## 方向性说明

只断言 **TS 声明的字段 ⊆ 真实响应**（单向）。

反向（响应里的每个字段都必须在 TS 里出现）**故意不assert** ——
后端可以随时新增字段供其它客户端使用，前端不声明并不构成缺陷。
把双向都钉死会让后端每加一个字段就要改前端，属于无谓耦合。

少数字段是真的**条件性出现**（如 vision provider 才有 `reads_printed_text`），
这类显式登记在 `CONDITIONAL` 里并写明原因 —— 用白名单而不是放宽断言，
否则"字段缺失"就再也检不出来了。
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from xuanpan_api.app import create_app
from xuanpan_api.config import Settings
from xuanpan_api.deps import get_settings

_TYPES_TS = Path(__file__).resolve().parents[2] / "apps/mobile/src/api/types.ts"

#: 确实是条件性出现的字段 → 原因。
#: 只有在这里登记过的字段允许缺失；其余任何缺失都说明前后端已经漂移。
CONDITIONAL: dict[str, str] = {
    "reads_printed_text": "仅 vision provider 携带，AI provider 无此字段",
    "name": "签库元信息按签库而异（demo 签库才带 name/count）",
    "demo": "同上",
    "count": "同上",
    "code": "ApiError 的 error 键仅在部分错误响应中出现",
}


# ==========================================================================
# 解析 types.ts
# ==========================================================================


def _parse_interfaces(src: str) -> dict[str, list[str]]:
    """从 TS 源码里抽出 `export interface X { ... }` 的顶层字段名。

    只做**行级**解析，不引 TypeScript 编译器 —— 本工程所有接口都是
    「一行一个字段」的写法，行级解析足够且没有依赖。

    必须追踪**花括号深度**：内联对象类型可以跨行，例如

        endpoint_presets: {
          id: string;
          name: string;
        }[];

    若只看行首缩进，`id` / `name` 会被误当成 `AiProvidersResponse` 的顶层字段，
    于是校验时报出「响应里没有 id」这种假失败 —— 而 `id` 本来是 `endpoint_presets`
    里的一项。第一版就踩了这个，故显式按深度判定。
    """
    out: dict[str, list[str]] = {}
    current: str | None = None
    depth = 0

    for raw in src.splitlines():
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("*") or line.startswith("/*"):
            continue

        if current is None:
            m = re.match(r"export interface (\w+)\s*\{", line)
            if m:
                current = m.group(1)
                out[current] = []
                depth = 1
            continue

        # 只在**顶层**（深度 1）记录字段
        if depth == 1:
            fm = re.match(r"(?:readonly\s+)?([A-Za-z_]\w*)\??\s*:", line)
            if fm:
                out[current].append(fm.group(1))

        depth += line.count("{") - line.count("}")
        if depth <= 0:
            current = None
            depth = 0

    return out


@pytest.fixture(scope="module")
def ts_interfaces() -> dict[str, list[str]]:
    assert _TYPES_TS.exists(), f"未找到前端类型定义：{_TYPES_TS}"
    parsed = _parse_interfaces(_TYPES_TS.read_text(encoding="utf-8"))
    assert parsed, "types.ts 里没解析出任何 interface —— 解析逻辑或文件结构已变"
    return parsed


def test_parser_actually_works(ts_interfaces: dict[str, list[str]]) -> None:
    """先证明解析器本身是对的，否则后面全是假绿。"""
    assert ts_interfaces["LayerPreview"] == ["facts", "tradition", "uncertainties"]
    assert ts_interfaces["MountainCandidate"] == ["name", "angle", "confidence", "end"]
    # 索引签名 `[k: string]: unknown` 不应被误当成字段
    assert "string" not in ts_interfaces["QianSet"]
    assert ts_interfaces["ReportSection"] == ["title", "body"]


# ==========================================================================
# 真实响应采集
# ==========================================================================


@pytest.fixture(scope="module")
def responses(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    """跑一遍完整链路，把各接口的真实响应按名字收好。"""
    from xuanpan_vision.testing import render_compass

    settings = Settings(db_path=tmp_path_factory.mktemp("contract") / "c.db", keep_photos=False)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings

    out: dict[str, Any] = {}
    with TestClient(app) as client:
        # ---- 元信息 ----
        out["MountainsResponse"] = client.get("/api/v1/meta/mountains").json()
        out["MountainInfo"] = out["MountainsResponse"]["mountains"][0]
        ai = client.get("/api/v1/meta/ai-providers").json()
        out["AiProvidersResponse"] = ai
        out["ProviderInfo"] = ai["providers"][0]
        out["VisionProvidersResponse"] = client.get("/api/v1/meta/vision-providers").json()
        out["QuestionCategoriesResponse"] = client.get("/api/v1/meta/question-categories").json()
        out["CapabilitiesResponse"] = client.get("/api/v1/meta/capabilities").json()
        out["QianSet"] = client.get("/api/v1/meta/qian-sets").json()["sets"][0]

        # ---- 会话 ----
        created = client.post(
            "/api/v1/sessions", json={"question_category": "事业", "question_text": "今年适合换工作吗"}
        ).json()
        out["SessionCreated"] = created

        listed = client.get("/api/v1/sessions").json()
        out["SessionListResponse"] = listed
        # 按 id 取回刚建的那条，不依赖列表排序
        out["SessionSummary"] = next(
            i for i in listed["items"] if i["session_id"] == created["session_id"]
        )

        # ---- 识别（合成罗盘，真值已知）----
        buf = io.BytesIO()
        render_compass(size=900, thread_angle=177.0).save(buf, format="PNG")
        scan = client.post(
            "/api/v1/scan?provider=classical",
            files={"image": ("c.png", buf.getvalue(), "image/png")},
        ).json()
        out["ScanResult"] = scan
        out["QualityReport"] = scan["quality"]
        out["MountainCandidate"] = scan["mountain_candidates"][0]

        # 识别会**自己建一个会话**并把快照写进去。后续的确认、详情、报告
        # 都必须落在这个会话上 —— 这正是产品真实路径（拍照 → 确认 → 报告），
        # 也是唯一能取到 `recognition` 的会话（手工会话没有它）。
        sid = scan["session_id"]

        # ---- 录入 + 确认 + 计算预览 ----
        client.patch(
            f"/api/v1/sessions/{sid}/inputs",
            json={
                "bazi": {
                    "year": 1981, "month": 9, "day": 14, "hour": 8, "minute": 0,
                    "calendar": "solar", "gender": "male", "timezone": "Asia/Shanghai",
                    "longitude": 114.3,
                }
            },
        )
        out["LayerPreview"] = client.post(
            f"/api/v1/sessions/{sid}/compass/confirm",
            json={"sitting": "午", "facing": "子", "degree": 177.0},
        ).json()
        out["CalcLayerPreview"] = client.post("/api/v1/calc/bazi", json={
            "year": 1981, "month": 9, "day": 14, "hour": 8, "minute": 0,
            "calendar": "solar", "gender": "male", "timezone": "Asia/Shanghai",
            "longitude": 114.3,
        }).json()

        detail = client.get(f"/api/v1/sessions/{sid}").json()
        out["SessionDetail"] = detail
        out["RecognitionSnapshot"] = detail["recognition"]
        out["CompassConfirmState"] = detail["confirm_state"]

        # ---- 报告（force_template：确定性、零成本、无需 key）----
        rep = client.post(
            f"/api/v1/sessions/{sid}/report",
            json={"force_template": True, "question_text": "今年适合换工作吗"},
        ).json()
        out["ReportResponse"] = rep
        out["Report"] = rep["report"]
        out["Interpretation"] = rep["report"]["interpretation"]
        out["ReportSection"] = rep["report"]["interpretation"]["sections"][0]

        # attempts 在模板 provider 下必有 1 条（成功）
        assert rep["report"]["interpretation"]["attempts"], "模板 provider 应至少产生一条 attempt"
        out["Attempt"] = rep["report"]["interpretation"]["attempts"][0]

        turns = client.get(f"/api/v1/sessions/{sid}/turns").json()
        assert turns["items"], "生成报告后应留下对话留痕"
        out["Turn"] = turns["items"][0]

        report_id = rep["report_id"]
        out["ReportMeta"] = client.get(f"/api/v1/sessions/{sid}/reports").json()["items"][0]
        out["GetReportEnvelope"] = client.get(f"/api/v1/reports/{report_id}").json()

        out["DeletedResponse"] = client.delete(f"/api/v1/sessions/{sid}").json()

    return out


# ==========================================================================
# 逐接口核对
# ==========================================================================

#: TS 接口名 → (真实响应在 responses 里的键, 该响应是 dict 还是 list-of-dict)
#: 全部是 dict；列表类已在上面的采集阶段取了首元素。
_CHECKED: tuple[str, ...] = (
    "MountainsResponse", "MountainInfo",
    "AiProvidersResponse", "ProviderInfo", "VisionProvidersResponse",
    "QuestionCategoriesResponse", "CapabilitiesResponse", "QianSet",
    "SessionCreated", "SessionListResponse", "SessionSummary",
    "ScanResult", "QualityReport", "MountainCandidate",
    "LayerPreview", "SessionDetail", "RecognitionSnapshot", "CompassConfirmState",
    "ReportResponse", "Report", "Interpretation", "ReportSection", "Attempt",
    "Turn", "ReportMeta", "DeletedResponse",
)


@pytest.mark.parametrize("name", _CHECKED)
def test_ts_fields_exist_in_real_response(
    name: str, ts_interfaces: dict[str, list[str]], responses: dict[str, Any]
) -> None:
    """TS 声明的每个字段，都必须在真实响应里存在。

    失败信息直接列出缺失字段 —— 这类问题的修法只有两种：
    改 TS 拼写，或改后端字段名，不能靠猜。
    """
    declared = ts_interfaces.get(name)
    assert declared is not None, f"types.ts 里没有 interface {name}（接口改名了？）"

    actual = responses[name]
    assert isinstance(actual, dict), f"{name} 的真实响应不是对象：{type(actual)}"

    missing = [
        f for f in declared
        if f not in actual and f not in CONDITIONAL
    ]
    if missing:
        pytest.fail(
            f"`{name}` 在 types.ts 里声明了但真实响应中没有这些字段：\n"
            f"  缺失：{missing}\n"
            f"  实际字段：{sorted(actual)}\n"
            "→ 改前端类型拼写，或改后端字段名；不要靠猜。"
        )


# ==========================================================================
# 形状断言（字段名对不上就罢了，结构错了更隐蔽）
# ==========================================================================


def test_layer_preview_facts_are_two_level(responses: dict[str, Any]) -> None:
    """`LayerPreview.facts` / `tradition` 必须是「模块名 → 对象」两层。

    这个结构错了不会报"字段缺失"，只会让 `facts['bazi']['day_master']`
    取到 `undefined`。本轮就因为这个把类型声明成了 `Record<string, unknown>`
    而未被发现，直到 `tsc` 在八字页/占测页报出 20 处错。
    """
    for key in ("LayerPreview", "CalcLayerPreview"):
        preview = responses[key]
        for layer in ("facts", "tradition"):
            data = preview[layer]
            assert isinstance(data, dict) and data, f"{key}.{layer} 不应为空"
            for module, body in data.items():
                assert isinstance(body, dict), (
                    f"{key}.{layer}['{module}'] 应为对象（模块名 → 字段），"
                    f"实际是 {type(body).__name__}"
                )


def test_report_facts_and_tradition_are_two_level(responses: dict[str, Any]) -> None:
    """报告里的两层同样是「模块名 → 对象」，且必须存在 compass / bazi。"""
    report = responses["Report"]
    for layer in ("facts", "tradition"):
        data = report[layer]
        assert isinstance(data, dict) and data
        for module, body in data.items():
            assert isinstance(body, dict), f"report.{layer}['{module}'] 应为对象"
    assert "compass" in report["facts"], "确认过坐向后，报告里必须有 compass 事实"
    assert "bazi" in report["facts"], "录入了生辰后，报告里必须有 bazi 事实"


def test_interpretation_sections_are_objects(responses: dict[str, Any]) -> None:
    """`sections` 是 `{title, body}` 列表 —— 前端直接按这两个键渲染。"""
    sections = responses["Interpretation"]["sections"]
    assert sections, "模板 provider 也必须产出至少一个区块"
    for s in sections:
        assert set(s) >= {"title", "body"}, f"区块缺少 title/body：{s}"


def test_report_sqlite_payload_roundtrip(responses: dict[str, Any]) -> None:
    """报告落库再取回，字段必须与直接生成时一致。

    报告是**唯一落库的派生数据**（AI 输出不可重算），如果落库/读取环节丢字段，
    用户从历史里打开报告会看到残缺内容 —— 而且无法重新生成一份一样的。
    """
    original = responses["Report"]
    got = responses["GetReportEnvelope"]["payload"]
    assert set(got) >= set(original), (
        f"落库后字段变少了：缺失 {sorted(set(original) - set(got))}"
    )


def test_turn_content_is_not_empty(responses: dict[str, Any]) -> None:
    """对话留痕的 content 不能是空串。

    本轮踩过的坑：前端取 `interpretation.text`（真实键是 `raw_text`）得到
    `undefined`，写进 turns 就是一个空回答。后端这一侧目前是直接取
    `report.interpretation.raw_text`，这里钉一下，避免以后有人改成写前端传来的值。
    """
    assert responses["Turn"]["content"].strip(), "追问留痕不该是空内容"
    assert responses["Interpretation"]["raw_text"].strip(), "AI 原文不该为空"
