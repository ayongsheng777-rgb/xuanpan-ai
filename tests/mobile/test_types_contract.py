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

    # 内联对象类型的各分量都写在**同一行**（如
    # `gan_zhi: { year: string; month: string; day: string };`）。
    # 若花括号深度判定失效，year/month/day 会被当成 AlmanacFacts 的顶层字段，
    # 于是对着真实响应报出「缺 year」这种**假失败** —— 第一版就栽在这里，故显式钉住。
    assert ts_interfaces["AlmanacFacts"] == [
        "solar_date", "lunar", "gan_zhi", "jian_chu", "xiu", "tian_shen",
        "chong", "yi", "ji", "ji_shen", "xiong_sha", "peng_zu", "rule_consistency",
    ]
    # 可选字段的 `?` 不能把字段名吞掉，否则它会整天报"响应里没有 unverified"
    assert "unverified" in ts_interfaces["ZeriSchool"]
    assert "description" in ts_interfaces["ZeriSchool"]


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

        # ---- 日历域与断卦（不落库、不进会话体系）----
        #
        # 这三组接口与 session 完全独立：没有会话、没有报告、也不写库。
        # 日期一律**写死**而不是用"今天" —— 这几条断言要的是"某一天的宜忌是什么"
        # 这种确定事实，用相对日期会让结果随运行日漂移，失败时也说不清是算错还是日期变了。
        day = client.get("/api/v1/almanac/day?date=2026-09-17").json()
        out["AlmanacDay"] = day
        out["AlmanacFacts"] = day["facts"]
        out["AlmanacTradition"] = day["tradition"]
        out["AlmanacRange"] = client.get(
            "/api/v1/almanac/range?start=2026-09-17&end=2026-09-19"
        ).json()

        zeri_events = client.get("/api/v1/zeri/events").json()
        out["ZeriEventsResponse"] = zeri_events
        out["ZeriEvent"] = zeri_events["events"][0]
        out["ZeriSchool"] = zeri_events["schools"][0]

        # `include_unfavorable` 必须开：默认只回"可用"的日子，而某个区间
        # 可能一天都没有 —— 那样 candidates 为空，`ZeriDay` 就无从校验，
        # 测试会变成"没测到"而不是"测过"，且表现为通过。
        sel = client.post(
            "/api/v1/zeri/select",
            json={
                "event": "jiaqu",
                "start": "2026-09-17",
                "end": "2027-09-17",
                "limit": 5,
                "include_unfavorable": True,
            },
        ).json()
        out["ZeriResultResponse"] = sel
        out["ZeriResultFacts"] = sel["facts"]
        out["ZeriResultTradition"] = sel["tradition"]
        assert sel["facts"]["candidates"], (
            "开了 include_unfavorable 仍无候选日 —— 无法校验 ZeriDay，"
            "请换一个区间或事件"
        )
        out["ZeriDay"] = sel["facts"]["candidates"][0]

        # `cast_date` 同样写死：起卦日决定日辰与月令，用"今天"会让旺衰结论
        # 随运行日变化，而本测试要核对的是**字段是否齐全**，不该被结论变动干扰。
        # 顺带覆盖"补录隔夜的卦"这条路径（显式传起卦日）。
        out["DuanResponse"] = client.post(
            "/api/v1/duan/liuyao",
            json={
                "method": "yao",
                "yao_values": [7, 7, 7, 7, 7, 7],
                "topic": "事业",
                "gender": "male",
                "cast_date": "2026-09-17",
            },
        ).json()

        # 八字断卦与六爻共用同一个 `DuanResponse` 类型，但 **verdict 的语义不同**：
        # 六爻是吉凶倾向，八字是「身强 / 身弱」这种日主状态。前端靠
        # `verdictLabel` 与白名单着色来区分，所以两份响应都要采回来核对。
        out["DuanBaziResponse"] = client.post(
            "/api/v1/duan/bazi",
            json={
                "year": 1981, "month": 9, "day": 14, "hour": 8, "minute": 0,
                "calendar": "solar", "gender": "male", "timezone": "Asia/Shanghai",
            },
        ).json()

        # ---- 三式 · 奇门（同样不落库、不进会话体系）----
        # 时刻**写死**：奇门以时辰起局，局数随时刻变；用"现在"会让
        # 断言结果随运行时刻漂移，失败时说不清是算错还是时刻变了。
        qimen_meta = client.get("/api/v1/qimen/meta").json()
        out["QimenMetaResponse"] = qimen_meta
        out["QimenSchool"] = qimen_meta["schools"][0]

        chart = client.post(
            "/api/v1/qimen/pan",
            json={"dt": "2026-09-17T12:00:00", "school": "chaibu"},
        ).json()
        out["QimenChart"] = chart
        out["QimenDingju"] = chart["dingju"]
        out["QimenPillars"] = chart["pillars"]
        # 取**中五宫**：它是唯一 `door` / `god` 为 null 的宫，
        # 取首宫会漏掉"IE 端把 null 当成字段缺失"这种情况。
        out["QimenPalace"] = next(p for p in chart["palaces"] if p["gong"] == 5)

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
    # 日历域与断卦 —— 这三组是新接入 App 的，属于最容易漂移的一批：
    # 它们是手写类型，且此前只经 MCP 暴露，前端从未核对过。
    "AlmanacDay", "AlmanacFacts", "AlmanacTradition", "AlmanacRange",
    "ZeriEventsResponse", "ZeriEvent", "ZeriSchool",
    "ZeriResultResponse", "ZeriResultFacts", "ZeriResultTradition", "ZeriDay",
    "DuanResponse",
    # 三式 · 奇门 —— 与日历域同一类风险：手写类型、此前从未被前端核对过。
    # 其中 `QimenPalace` 取自**中五宫**（该宫 door/god 为 null），
    # 正是最容易把"字段值为 null"误当成"字段不存在"的地方。
    "QimenMetaResponse", "QimenSchool",
    "QimenChart", "QimenDingju", "QimenPillars", "QimenPalace",
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


# ==========================================================================
# 断卦：可回溯性
# ==========================================================================


def test_duan_liuyao_carries_traceable_basis(responses: dict[str, Any]) -> None:
    """断卦结果必须写明「本盘用的是哪一天的日辰月令」。

    这是断卦能否被信任的前提：旺衰完全由日辰与月令决定。
    若响应里不说明用的是哪一天，**补录隔夜的卦**会拿到一套依据全错的结论，
    而结论本身看起来完全正常 —— 没有任何迹象。
    所以 `detail.basis` 不是可选装饰，而是这个接口的契约。
    """
    detail = responses["DuanResponse"]["detail"]
    assert "basis" in detail, "断卦响应缺少 detail.basis，倾向无法回溯"

    basis = detail["basis"]
    assert set(basis) >= {
        "cast_date", "day_pillar", "month_pillar", "topic", "gender", "yongshen",
    }, f"basis 字段不全：{sorted(basis)}"
    assert basis["cast_date"] == "2026-09-17", "回传的起卦日与请求不符"
    assert basis["topic"] == "事业", "回传的占问类别与请求不符"
    assert basis["day_pillar"] and basis["month_pillar"], "日辰 / 月令不得为空"
    assert basis["yongshen"], "指定了占问类别，就必须取到用神（否则是静默降级）"


def test_duan_liuyao_includes_full_zhuang_result(responses: dict[str, Any]) -> None:
    """`detail.divination` 必须带**完整装卦结果**，而不是只有卦名。

    只给一个「偏吉」而不给六亲 / 世应 / 旬空 / 旺衰，等于让用户无条件相信一个黑盒。
    更要紧的是：装卦层是断卦的**唯一依据**，缺了它，倾向就无法被复核 ——
    而"无法复核的结论"正是本项目 RULE-001 要防的东西。
    """
    div = responses["DuanResponse"]["detail"].get("divination")
    assert isinstance(div, dict) and div, "断卦响应里没有装卦结果"

    facts = div.get("facts")
    assert isinstance(facts, dict) and facts, "装卦结果缺少 facts 层"
    assert set(facts) >= {
        "gua", "day_pillar", "month_pillar", "palace", "palace_stage",
        "shi_position", "ying_position", "xun_kong", "yao_details",
    }, f"装卦 facts 字段不全：{sorted(facts)}"

    # 六爻六爻 —— 少于六条说明纳甲装卦没跑完
    assert len(facts["yao_details"]) == 6, (
        f"装卦应有 6 爻，实得 {len(facts['yao_details'])}"
    )
    one = facts["yao_details"][0]
    assert set(one) >= {"position", "liu_qin", "liu_shen", "month_state"}, (
        f"单爻明细字段不全：{sorted(one)}"
    )


# ==========================================================================
# 断卦：前端着色契约（跨层漂移守卫）
# ==========================================================================

_DUAN_CARD_TS = Path(__file__).resolve().parents[2] / "apps/mobile/src/components/DuanCard.tsx"


def _frontend_graded_verdicts() -> set[str]:
    """从 `DuanCard.tsx` 的 `verdictTone` 里抽出前端判为**吉或凶**的词。

    直接从源码抽，而不是在测试里另抄一份常量 —— 抄的那份不会随实现更新，
    于是"漂移检测"就变成了两个我在互相对答案。
    """
    assert _DUAN_CARD_TS.exists(), f"未找到前端断卦卡片：{_DUAN_CARD_TS}"
    src = _DUAN_CARD_TS.read_text(encoding="utf-8")
    # 实现里的写法是 `if (verdict === '偏吉') return 'good';`
    return set(re.findall(r"verdict === '([^']+)'", src))


def test_frontend_verdict_whitelist_matches_kernel() -> None:
    """前端判为吉 / 凶的词，必须**恰好等于**内核定义的吉凶词。

    为什么值得单独钉：前端给 verdict 上色用的是**白名单** ——
    不在表里的一律按中性渲染。于是有两种方向相反的漂移，而且**都不会报错**：

    - 前端多认一个词 → 某个中性结论被染成吉 / 凶（把「身弱」画成凶兆）
    - 内核改了吉凶词而前端没跟 → 真正的吉凶被画成中性（「偏凶」看起来像「平」）

    第二种尤其危险：它不会让任何测试失败，只表现为颜色不对，
    而颜色不对最容易被当成"设计如此"而放过。
    """
    from fortune_core.duangua import (
        VERDICT_FAVORABLE,
        VERDICT_NEUTRAL,
        VERDICT_UNFAVORABLE,
    )

    graded = _frontend_graded_verdicts()
    assert graded == {VERDICT_FAVORABLE, VERDICT_UNFAVORABLE}, (
        f"前端判为吉凶的词 {sorted(graded)} 与内核的 "
        f"{{{VERDICT_FAVORABLE!r}, {VERDICT_UNFAVORABLE!r}}} 不一致。\n"
        "→ 改了内核的吉凶词，或改了 DuanCard.verdictTone 的白名单，请同步另一端。"
    )

    # 中性词不得被前端当成吉凶
    assert VERDICT_NEUTRAL not in graded
    assert not (graded & {"身强", "身弱"}), (
        "「身强 / 身弱」是**日主状态**，与吉凶无关；"
        "把它们染成朱红等于把一个中性事实渲染成凶兆"
    )


def test_duan_bazi_verdict_is_a_status_not_a_fortune(responses: dict[str, Any]) -> None:
    """八字断卦的 verdict 必须是「身强 / 身弱」这类**状态词**，而不是吉凶词。

    这条直接对应界面上最容易被做错的一处：八字 verdict 走的是
    `verdictLabel="日主状态"` + 中性色。若后端哪天把八字 verdict 改成
    「偏吉 / 偏凶」，前端会**照常按吉凶上色** —— 因为它只看词。
    那时"日主状态"这个标签配上吉凶色，就是在用术语包装一个命定论结论。
    """
    from fortune_core.duangua import VERDICT_FAVORABLE, VERDICT_UNFAVORABLE

    verdict = responses["DuanBaziResponse"]["verdict"]
    assert verdict in {"身强", "身弱"}, (
        f"八字断卦的 verdict 是 {verdict!r}，期望「身强 / 身弱」。\n"
        "→ 若确实要改成吉凶倾向，必须同步前端："
        "apps/mobile/app/(tabs)/chart.tsx 的 verdictLabel 与 DuanCard 的着色。"
    )
    assert verdict not in {VERDICT_FAVORABLE, VERDICT_UNFAVORABLE}


# ==========================================================================
# 三式 · 奇门
# ==========================================================================


def test_qimen_middle_palace_has_no_door_or_god(responses: dict[str, Any]) -> None:
    """中五宫必须**没有**八门与八神 —— 这是规则，不是数据缺失。

    奇门里中宫寄坤，不布门、不布神。前端据此把这两格显示为空；
    如果后端某天"顺手补上"一个默认门/神，界面不会报错，
    只会显示一个**不存在的门**，而用户无从分辨。
    """
    mid = responses["QimenPalace"]
    assert mid["gong"] == 5, "本用例取的是中五宫，采集逻辑变了？"
    assert mid["door"] is None, f"中五宫不应有门，实为 {mid['door']!r}"
    assert mid["god"] is None, f"中五宫不应有神，实为 {mid['god']!r}"
    # 地盘干与天盘干在中宫依然存在（寄宫不等于整格为空）
    assert mid["di_gan"], "中五宫应当有地盘干"
    assert mid["tian_gan"], "中五宫应当有天盘干"


def test_qimen_chart_has_exactly_nine_palaces(responses: dict[str, Any]) -> None:
    """九宫恰好九格、宫序 1~9 不重不漏。

    前端按洛书把九宫摆进 3×3 网格；少一格会留下一个空洞，
    多一格会挤掉一格 —— 两种都不会报错。
    """
    palaces = responses["QimenChart"]["palaces"]
    assert len(palaces) == 9, f"应为九宫，实为 {len(palaces)}"
    assert sorted(p["gong"] for p in palaces) == list(range(1, 10))


def test_qimen_carries_uncertainties(responses: dict[str, Any]) -> None:
    """`uncertainties` 不得为空 —— 界面靠它如实交代未覆盖项。

    空的 uncertainties 不会让界面报错，只会让"本版不覆盖什么"这一节
    直接从页面上消失，而用户以为看到的是全部。
    """
    chart = responses["QimenChart"]
    assert chart["uncertainties"], "奇门盘必须携带 uncertainties"
    meta = responses["QimenMetaResponse"]
    assert meta["uncertainties"], "奇门 meta 必须携带 uncertainties"
    # 两处必须是**同一份**（内核常量是唯一真源，不得各写一份）
    assert chart["uncertainties"] == meta["uncertainties"], (
        "排盘结果与 meta 的 uncertainties 不一致 —— 说明有两份文案在漂移"
    )


def test_qimen_meta_covers_all_twenty_four_jieqi(responses: dict[str, Any]) -> None:
    """局数表覆盖全部二十四节气，且每项三元、局数在 1~9。

    局数表是领域数据（RULE-005），缺一个节气会让那一天排不出盘；
    而前端不自己维护副本，所以这张表的完整性只能在这里守。
    """
    meta = responses["QimenMetaResponse"]
    table = meta["jushu_table"]
    assert len(table) == 24, f"局数表应覆盖二十四节气，实为 {len(table)} 个"
    assert len(meta["yang_dun_jieqi"]) == 12
    assert len(meta["yin_dun_jieqi"]) == 12
    assert sorted(meta["yang_dun_jieqi"] + meta["yin_dun_jieqi"]) == sorted(table)
    for jieqi, triple in table.items():
        assert len(triple) == 3, f"{jieqi} 应有上/中/下三元的局数，实为 {triple}"
        assert all(1 <= n <= 9 for n in triple), f"{jieqi} 局数越界：{triple}"


def test_qimen_dingju_chain_is_self_consistent(responses: dict[str, Any]) -> None:
    """定局链路自洽：局数表[节气][三元-1] 必须等于实排局数。

    这是把「定局」这条推导链的**最后一跳**拿真值核一遍 ——
    前面几步（节气、天数、三元）都对了、最后查表查错，结果同样是一张错盘，
    而且错得毫无征兆。
    """
    dingju = responses["QimenDingju"]
    table = responses["QimenMetaResponse"]["jushu_table"]
    assert dingju["jieqi"] in table, f"实排节气 {dingju['jieqi']!r} 不在局数表里"
    expected = table[dingju["jieqi"]][dingju["yuan"] - 1]
    assert dingju["jushu"] == expected, (
        f"{dingju['jieqi']} 的{dingju['yuan_label']}应为 {expected} 局，"
        f"实排 {dingju['jushu']} 局"
    )
    # 阴阳遁与节气归属必须一致（阳遁节气表 / 阴遁节气表）
    meta = responses["QimenMetaResponse"]
    in_yang = dingju["jieqi"] in meta["yang_dun_jieqi"]
    assert dingju["yang_dun"] is in_yang, (
        f"{dingju['jieqi']} 的阴阳遁标记与节气归属表不符"
    )


# ==========================================================================
# 三式 · 奇门
# ==========================================================================


def test_qimen_middle_palace_has_no_door_or_god(responses: dict[str, Any]) -> None:
    """中五宫必须**没有**八门与八神 —— 这是规则，不是数据缺失。

    奇门里中宫寄坤，不布门、不布神。前端据此把这两格显示为空；
    如果后端某天"顺手补上"一个默认门/神，界面不会报错，
    只会显示一个**不存在的门**，而用户无从分辨。
    """
    mid = responses["QimenPalace"]
    assert mid["gong"] == 5, "本用例取的是中五宫，采集逻辑变了？"
    assert mid["door"] is None, f"中五宫不应有门，实为 {mid['door']!r}"
    assert mid["god"] is None, f"中五宫不应有神，实为 {mid['god']!r}"
    # 地盘干与天盘干在中宫依然存在（寄宫不等于整格为空）
    assert mid["di_gan"], "中五宫应当有地盘干"
    assert mid["tian_gan"], "中五宫应当有天盘干"


def test_qimen_chart_has_exactly_nine_palaces(responses: dict[str, Any]) -> None:
    """九宫恰好九格、宫序 1~9 不重不漏。

    前端按洛书把九宫摆进 3×3 网格；少一格会留下一个空洞，
    多一格会挤掉一格 —— 两种都不会报错。
    """
    palaces = responses["QimenChart"]["palaces"]
    assert len(palaces) == 9, f"应为九宫，实为 {len(palaces)}"
    assert sorted(p["gong"] for p in palaces) == list(range(1, 10))


def test_qimen_carries_uncertainties(responses: dict[str, Any]) -> None:
    """`uncertainties` 不得为空 —— 界面靠它如实交代未覆盖项。

    空的 uncertainties 不会让界面报错，只会让"本版不覆盖什么"这一节
    直接从页面上消失，而用户以为看到的是全部。
    """
    chart = responses["QimenChart"]
    assert chart["uncertainties"], "奇门盘必须携带 uncertainties"
    meta = responses["QimenMetaResponse"]
    assert meta["uncertainties"], "奇门 meta 必须携带 uncertainties"
    # 两处必须是**同一份**（内核常量是唯一真源，不得各写一份）
    assert chart["uncertainties"] == meta["uncertainties"], (
        "排盘结果与 meta 的 uncertainties 不一致 —— 说明有两份文案在漂移"
    )


def test_qimen_meta_covers_all_twenty_four_jieqi(responses: dict[str, Any]) -> None:
    """局数表覆盖全部二十四节气，且每项三元、局数在 1~9。

    局数表是领域数据（RULE-005），缺一个节气会让那一天排不出盘；
    而前端不自己维护副本，所以这张表的完整性只能在这里守。
    """
    meta = responses["QimenMetaResponse"]
    table = meta["jushu_table"]
    assert len(table) == 24, f"局数表应覆盖二十四节气，实为 {len(table)} 个"
    assert len(meta["yang_dun_jieqi"]) == 12
    assert len(meta["yin_dun_jieqi"]) == 12
    assert sorted(meta["yang_dun_jieqi"] + meta["yin_dun_jieqi"]) == sorted(table)
    for jieqi, triple in table.items():
        assert len(triple) == 3, f"{jieqi} 应有上/中/下三元的局数，实为 {triple}"
        assert all(1 <= n <= 9 for n in triple), f"{jieqi} 局数越界：{triple}"


def test_qimen_dingju_chain_is_self_consistent(responses: dict[str, Any]) -> None:
    """定局链路自洽：局数表[节气][三元-1] 必须等于实排局数。

    这是把「定局」这条推导链的**最后一跳**拿真值核一遍 ——
    前面几步（节气、天数、三元）都对了、最后查表查错，结果同样是一张错盘，
    而且错得毫无征兆。
    """
    dingju = responses["QimenDingju"]
    table = responses["QimenMetaResponse"]["jushu_table"]
    assert dingju["jieqi"] in table, f"实排节气 {dingju['jieqi']!r} 不在局数表里"
    expected = table[dingju["jieqi"]][dingju["yuan"] - 1]
    assert dingju["jushu"] == expected, (
        f"{dingju['jieqi']} 的{dingju['yuan_label']}应为 {expected} 局，"
        f"实排 {dingju['jushu']} 局"
    )
    # 阴阳遁与节气归属必须一致（阳遁节气表 / 阴遁节气表）
    meta = responses["QimenMetaResponse"]
    in_yang = dingju["jieqi"] in meta["yang_dun_jieqi"]
    assert dingju["yang_dun"] is in_yang, (
        f"{dingju['jieqi']} 的阴阳遁标记与节气归属表不符"
    )
