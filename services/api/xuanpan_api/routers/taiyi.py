"""太乙神数 —— 起局查询（三式之三）。

两条端点：

| 端点 | 用户心里想的是 |
|---|---|
| `GET  /taiyi/meta` | 「起局界面需要知道什么？」—— 九宫表 + 十六神 + 八门 + 未覆盖项 |
| `POST /taiyi/cast` | 「给我排这一年的局」 |

输入是**整数年份**，不是 datetime —— 太乙年局的最小单位就是年。
这与六壬「必须给到时辰」刚好相反；两者是不同术式的固有差异，
不要为了「接口统一」而给太乙强加月日（那会让人以为年局随时辰而变）。

⚠️ 路径用 `/taiyi/cast` 而不是 `/taiyi/pan`：与六壬一致。
奇门那边是 `/qimen/pan`，两者命名不统一是历史遗留，已记入待办 ——
**新增的接口一律用 `cast`**，避免把这个不一致继续扩散。

**九宫表 / 十六神 / 八门由接口返回，前端不得自己算**（RULE-005）：
太乙宫号与洛书逐宫错位，前端照奇门的表自己摆一遍，整盘会偏 45° 而不报错。

未知流派由内核抛 `SchoolNotFoundError`（`FortuneError` 子类），
经 `app.py` 的统一处理器转 400。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..schemas import TaiyiCastRequest, TaiyiMetaResponse

router = APIRouter(prefix="/taiyi", tags=["taiyi"])


@router.get("/meta", response_model=TaiyiMetaResponse, summary="太乙元数据（九宫与十六神）")
def taiyi_meta() -> TaiyiMetaResponse:
    """九宫表 / 十六神 / 八门 / 五元六纪 / 流派 / 未覆盖项。

    `uncertainties` 取自内核常量，与起局结果里那份是**同一个来源** ——
    界面应把它展示成「本版不覆盖」，而不是省略：
    用户有权知道这份局没有考虑什么（例如本版只做年局，无月局/日局/时局）。

    八门吉凶一并返回，但它是**门自身的属性**（FACT），
    不是对所占之事的结论；界面对它只做展示，不做推断（RULE-008）。
    """
    from fortune_core.taiyi import (
        BAMEN_BENWEI,
        BAMEN_CYCLE_YEARS,
        BAMEN_JIXIONG,
        BAMEN_ORDER,
        BAMEN_SWITCH_YEARS,
        JIAN_SHEN,
        JIYAN_BASE,
        PALACE_DIRECTION,
        PALACE_DOOR_NAME,
        PALACE_FENYE,
        PALACE_GUA,
        PALACE_QI,
        SCHOOLS,
        SHEN_NAME,
        SHEN_PALACE,
        TAIYI_XUN_GONG,
        TAIYI_YEARS_PER_PALACE,
        TAIYI_CYCLE_YEARS,
        UNCERTAINTIES,
        WENCHANG_CYCLE_YEARS,
        WENCHANG_SEQ_YANG,
        WUYUAN_NAMES,
        ZHENG_GONG_SHEN,
    )

    def skey(d: dict[int, str]) -> dict[str, str]:
        """宫号做键的表转成字符串键 —— JSON 对象键只能是字符串，
        而 Pydantic 的类型标注写 int 会让 schema 与实际 JSON 不一致。"""
        return {str(k): v for k, v in d.items()}

    return TaiyiMetaResponse(
        # id 就是 SCHOOLS 的键，不往内核表里再塞一份 —— 两份必然会漂移，
        # 而漂移的表现是「界面按 A 提交、后端按 B 校验」，报的还是流派不存在。
        schools=[{"id": k, **v} for k, v in SCHOOLS.items()],
        jiyan_base=JIYAN_BASE,
        palace_gua=skey(PALACE_GUA),
        palace_direction=skey(PALACE_DIRECTION),
        palace_door_name=skey(PALACE_DOOR_NAME),
        palace_fenye=skey(PALACE_FENYE),
        palace_qi=skey(PALACE_QI),
        shen_names=dict(SHEN_NAME),
        shen_palace=skey(SHEN_PALACE),
        zheng_shen=list(ZHENG_GONG_SHEN),
        jian_shen=list(JIAN_SHEN),
        wenchang_seq=list(WENCHANG_SEQ_YANG),
        jishen_rule="子岁计神寅上起，丑牛寅鼠逆周流（逆行十二支，不用四维）",
        bamen_order=list(BAMEN_ORDER),
        bamen_benwei=dict(BAMEN_BENWEI),
        bamen_jixiong=dict(BAMEN_JIXIONG),
        taiyi_xun_gong=list(TAIYI_XUN_GONG),
        years_per_palace=TAIYI_YEARS_PER_PALACE,
        cycle_years=TAIYI_CYCLE_YEARS,
        wenchang_cycle_years=WENCHANG_CYCLE_YEARS,
        bamen_switch_years=BAMEN_SWITCH_YEARS,
        bamen_cycle_years=BAMEN_CYCLE_YEARS,
        wuyuan_names=list(WUYUAN_NAMES),
        uncertainties=list(UNCERTAINTIES),
    )


@router.post("/cast", summary="太乙神数起局（年局）")
def taiyi_cast(payload: TaiyiCastRequest) -> dict[str, Any]:
    """排一张太乙年局。

    返回结构见 `fortune_core.taiyi.TaiyiChart.to_dict()`：
    `taiyi` 是太乙落宫（宫号 / 卦 / 方位 / 入宫第几年 / 理天理地理人），
    `wenchang` / `shiji` / `dingmu` 是三个目，
    `sansuan` 是主算 / 客算 / 定算（含大将、参将落宫、长短、三才、和数、孤数），
    `bamen` 是值事门与八门落宫。

    前端只需按宫号摆放，不需要再做任何推导（RULE-005）。
    内核不下吉凶断语：三算的各类数字与门的吉凶都只是 FACT（RULE-008）。
    """
    from fortune_core.taiyi import cast_taiyi

    return cast_taiyi(payload.year, school=payload.school).to_dict()


__all__ = ["router"]
