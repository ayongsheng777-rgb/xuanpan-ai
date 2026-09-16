"""端到端冒烟脚本 —— 对**真实运行中的服务**发请求，跑通整条链路。

与 `tests/api/test_api.py` 的区别：
- 测试用的是进程内 `TestClient`（快、可 mock）
- 本脚本用真实 HTTP 打到 127.0.0.1，验证"服务真的能起来并对外工作"

用法（先起服务）：

    # [Host] 起服务
    PYTHONPATH='services/api;services/ai;services/vision;packages/fortune-core' \\
      python -m uvicorn xuanpan_api.app:create_app --factory --port 8360

    # [Host] 跑冒烟
    python scripts/smoke_api.py --base http://127.0.0.1:8360

退出码：0 全部通过；1 有断言失败。
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from typing import Any

# 允许脚本直接以源码运行（无需安装）
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for rel in ("services/api", "services/ai", "services/vision", "packages/fortune-core"):
    p = str(ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

import httpx  # noqa: E402

PASS = 0
FAIL = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    mark = "PASS" if ok else "FAIL"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def compass_png(thread_angle: float, size: int = 900) -> bytes:
    from xuanpan_vision.testing import render_compass

    buf = io.BytesIO()
    render_compass(size=size, thread_angle=thread_angle).save(buf, format="PNG")
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8360")
    ap.add_argument("--angle", type=float, default=177.0, help="合成罗盘的真值角度")
    ap.add_argument("--keep", action="store_true", help="跑完不删除会话（便于人工查看）")
    args = ap.parse_args()

    base = args.base.rstrip("/")
    client = httpx.Client(base_url=base, timeout=90.0)

    # ---------------------------------------------------------------- 健康
    section("健康检查")
    r = client.get("/healthz")
    check("GET /healthz 返回 200", r.status_code == 200, r.text[:80])
    check("status == ok", r.json().get("status") == "ok")

    # ---------------------------------------------------------------- 元信息
    section("元信息")
    m = client.get("/api/v1/meta/mountains").json()
    check("二十四山共 24 座", len(m["mountains"]) == 24)
    check("0° 为子（正北）", m["mountains"][0]["name"] == "子")

    prov = client.get("/api/v1/meta/ai-providers").json()
    template = next(p for p in prov["providers"] if p["id"] == "template")
    check("本地模板可用（零成本路径）", template["available"] is True)

    caps = client.get("/api/v1/meta/capabilities").json()
    print(f"  [INFO] 分金干支规则表就绪：{caps['fenjin_table_available']}")
    if not caps["fenjin_table_available"]:
        print("  [INFO] 规则表未提供 → 分金只输出几何格位，干支为「未定」（不猜，符合 RULE-003）")

    # ---------------------------------------------------------------- 计算预览
    section("纯计算预览")
    bz = client.post(
        "/api/v1/calc/bazi",
        json={
            "year": 1981, "month": 9, "day": 14, "hour": 8, "minute": 0,
            "calendar": "solar", "gender": "male", "timezone": "Asia/Shanghai",
            "longitude": 114.3,
        },
    ).json()
    pillars = bz["facts"]["bazi"]["pillars"]
    print(f"  [INFO] 四柱：{pillars}")
    check("日柱为乙未", pillars["day"] == "乙未", str(pillars))
    check("日主为乙", bz["facts"]["bazi"]["day_master"] == "乙")

    # ---------------------------------------------------------------- 识别
    section("罗盘识别（合成图）")
    files = {"image": ("compass.png", compass_png(args.angle), "image/png")}
    r = client.post("/api/v1/scan", files=files)
    check("POST /scan 返回 200", r.status_code == 200, r.text[:120])
    scan = r.json()
    sid = scan["session_id"]

    check("识别到罗盘", scan["compass_detected"] is True)
    check("强制要求用户确认（RULE-004）", scan["needs_user_confirmation"] is True)
    names = sorted(c["name"] for c in scan["mountain_candidates"])
    check("两候选互为对宫（子/午）", names == ["午", "子"], str(names))
    angles = {c["name"]: c["angle"] for c in scan["mountain_candidates"]}
    print(f"  [INFO] 候选实测角：{angles}")
    near = min(abs(a - args.angle) for a in angles.values())
    check(f"实测角保留到 2° 内（真值 {args.angle}°）", near < 2.0, f"最近 {near:.2f}°")

    # ---------------------------------------------------------------- 确认
    section("用户确认坐向")
    r = client.post(
        f"/api/v1/sessions/{sid}/compass/confirm",
        json={"sitting": "午", "degree": args.angle, "note": "冒烟脚本确认"},
    )
    check("确认成功", r.status_code == 200, r.text[:160])
    facts = r.json()["facts"]["compass"] if r.status_code == 200 else {}
    if facts:
        print(f"  [INFO] 坐{facts['sitting']} 向{facts['facing']} 实测 {facts.get('exact_degree')}°")
        fen = facts.get("fenjin")
        print(f"  [INFO] 分金：{fen}")
        check("坐向互为对宫", facts["sitting"] != facts["facing"])
        check("分金几何格位已算出", isinstance(fen, dict) and fen.get("index") is not None)

    # ---------------------------------------------------------------- 录入
    section("增量录入（八字 + 姓名）")
    r = client.patch(
        f"/api/v1/sessions/{sid}/inputs",
        json={
            "bazi": {
                "year": 1981, "month": 9, "day": 14, "hour": 8, "minute": 0,
                "calendar": "solar", "gender": "male", "timezone": "Asia/Shanghai",
                "longitude": 114.3,
            },
            "naming": {"name": "张伟"},
            "question_category": "事业",
            "question_text": "今年适合换工作吗",
        },
    )
    check("PATCH inputs 成功", r.status_code == 200, r.text[:160])
    check("返回两个模块预览", set(r.json().get("updated", [])) == {"bazi", "naming"})

    # ---------------------------------------------------------------- 报告
    section("生成报告（强制本地模板 → 可复现、零成本）")
    r = client.post(
        f"/api/v1/sessions/{sid}/report",
        json={"force_template": True, "question_category": "事业", "question_text": "今年适合换工作吗"},
    )
    check("报告生成成功", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        rep = r.json()["report"]
        check("三层字段齐备", {"facts", "tradition", "interpretation"} <= set(rep))
        check("含不确定性清单", len(rep["uncertainties"]) > 0, f"{len(rep['uncertainties'])} 条")
        check("含免责声明", bool(rep["disclaimer"]))
        check("facts 为只读事实层", rep["facts"]["compass"]["sitting"] == "午")

        sec_titles = [s["title"] for s in rep["interpretation"]["sections"]]
        print(f"  [INFO] 解读区块：{sec_titles}")
        print("\n---- AI 解读正文 ----")
        for s in rep["interpretation"]["sections"]:
            print(f"【{s['title']}】{s['body'][:200]}")
        print("---- 系统保证的不确定性 ----")
        for u in rep["uncertainties"]:
            print(f"  · {u}")

    # ---------------------------------------------------------------- 追问
    section("多轮追问")
    before = client.get(f"/api/v1/sessions/{sid}").json()["facts"]
    r = client.post(
        f"/api/v1/sessions/{sid}/ask",
        json={"question_text": "那如果留在原公司呢？", "force_template": True},
    )
    check("追问成功", r.status_code == 200, r.text[:160])
    after = client.get(f"/api/v1/sessions/{sid}").json()["facts"]
    check("追问不改变盘面事实（三层分离）", before == after)

    turns = client.get(f"/api/v1/sessions/{sid}/turns").json()["items"]
    check("对话留痕 4 轮", len(turns) == 4, str([t["role"] for t in turns]))

    # ---------------------------------------------------------------- 持久化
    section("持久化与历史")
    listing = client.get("/api/v1/sessions").json()
    check("会话列表包含本次会话", any(i["session_id"] == sid for i in listing["items"]))
    check("报告已落库", len(client.get(f"/api/v1/sessions/{sid}/reports").json()["items"]) == 2)

    detail = client.get(f"/api/v1/sessions/{sid}").json()
    print(f"  [INFO] 会话 {sid}")
    print(f"  [INFO] 已录入模块：{detail['modules']}")
    print(f"  [INFO] 识别原件仍保留：{detail['recognition'] is not None}")
    check("确认动作未覆盖识别原件（RULE-008）", detail["recognition"]["compass_detected"] is True)

    # ---------------------------------------------------------------- 错误路径
    section("错误路径")
    check(
        "非法山名被拒 400",
        client.post("/api/v1/calc/compass", json={"sitting": "戊"}).status_code == 400,
    )
    check(
        "坐向冲突被拒 400",
        client.post("/api/v1/calc/compass", json={"sitting": "午", "facing": "午"}).status_code == 400,
    )
    check(
        "未知字段被拒 422",
        client.post("/api/v1/calc/compass", json={"sit": "午"}).status_code == 422,
    )
    check(
        "不存在的会话 404",
        client.get("/api/v1/sessions/sess_nope").status_code == 404,
    )

    # ---------------------------------------------------------------- 清理
    section("清理")
    if args.keep:
        print(f"  [SKIP] 保留会话 {sid}")
    else:
        r = client.delete(f"/api/v1/sessions/{sid}")
        check("删除会话", r.status_code == 200 and r.json()["deleted"] is True)
        check("删除后 404", client.get(f"/api/v1/sessions/{sid}").status_code == 404)

    # ---------------------------------------------------------------- 汇总
    print(f"\n{'=' * 46}")
    print(f"结果：{PASS} 通过，{FAIL} 失败")
    print(f"{'=' * 46}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
