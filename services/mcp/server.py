"""玄盘 AI —— MCP 暴露层。

把 `fortune-core` 的纯函数内核包成 Model Context Protocol (MCP) 工具，
供任意 MCP 客户端（Claude Desktop / WorkBuddy / Cursor 等）调用。

设计原则（对齐 RULE-001 / RULE-002 / RULE-006，并修正 suanming-mcp 的反模式）：

1. **回 `structuredContent`，不回自然语言摘要** —— 每个工具返回内核的
   `to_dict()`（内含 FACT / TRADITION 两层现成 JSON），让调用方拿到结构化数据，
   而不是一段需要重新解析的中文文本。

2. **纯 stdio，不弹浏览器** —— 工具只做计算，不触发任何 GUI / 浏览器动作。

3. **计算层是唯一真源，禁 LLM 介入** —— MCP 工具只是内核函数的薄封装，
   不含任何 AI 生成逻辑。

用法（stdio 模式，MCP 客户端配置示例）::

    {
      "mcpServers": {
        "xuanpan": {
          "command": "<python>",
          "args": ["services/mcp/server.py"],
          "env": {"PYTHONPATH": "packages/fortune-core"}
        }
      }
    }
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# fortune-core 内核（纯函数，唯一真源）
from fortune_core import (
    AlmanacResult,
    BaziChart,
    BirthInput,
    CompassOrientation,
    FortuneError,
    LiuYaoResult,
    NameAnalysis,
    QianResult,
    ZeriResult,
    analyze_name,
    calculate_almanac,
    calculate_bazi,
    calculate_orientation,
    cast_liuyao,
    draw_qian,
    duan_bazi,
    duan_liuyao,
    select_auspicious_days,
)
from fortune_core.liuyao import zhuang_gua
from lunar_python import Solar

APP_VERSION = "0.1.0"

server = MCPServer(
    name="xuanpan",
    title="玄盘 AI · 术数计算内核",
    description=(
        "确定性术数计算（八字 / 六爻 / 黄历 / 择日 / 姓名 / 灵签 / 罗盘坐向）。"
        "计算由代码完成，AI 只负责解释结果，不介入计算。"
    ),
    version=APP_VERSION,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _facts_dict(result: Any) -> dict[str, Any]:
    """统一取结构化输出：优先 to_dict()（含 facts + tradition 两层）。"""
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return {"facts": str(result)}


def _domain_errors_as_tool_error(fn):
    """把内核领域异常转成 MCP ToolError，让调用方看到具体原因。

    内核异常（InvalidInputError / DomainDataMissingError / OrientationConflictError /
    SchoolNotFoundError）都继承 FortuneError，代表「用户输入或数据有问题」，
    而不是程序 bug。若让它们直接抛出去，MCP 会包装成笼统的
    "Error executing tool xxx"，调用方（Agent）看不到「非法公历日期：1990-13-1」。
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except FortuneError as exc:
            raise ToolError(str(exc)) from exc

    return wrapper


def _today_ganzhi() -> tuple[str, str]:
    """当日干支与月干支（供六爻装卦，取本地当前日期）。"""
    now = _dt.datetime.now()
    lunar = Solar.fromYmd(now.year, now.month, now.day).getLunar()
    return lunar.getDayInGanZhi(), lunar.getMonthInGanZhi()


# ---------------------------------------------------------------------------
# 工具定义
# ---------------------------------------------------------------------------

@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_bazi(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    gender: str | None = None,
    calendar: str = "solar",
    sect: int = 2,
    timezone: str = "Asia/Shanghai",
    longitude: float | None = None,
    latitude: float | None = None,
) -> dict[str, Any]:
    """八字排盘：四柱 / 十神 / 藏干 / 纳音 / 旬空 / 大运流年 / 神煞 / 长生十二宫。

    参数:
        year/month/day/hour: 出生年月日时（公历）。
        minute: 分钟，默认 0。
        gender: 性别，male/female（大运顺逆需要）；不填则不排大运。
        calendar: solar（公历）或 lunar（农历）。
        sect: 流派，1=晚子时日柱算次日，2=晚子时日柱算当天（默认 2）。
        timezone: 时区，默认 Asia/Shanghai。
        longitude/latitude: 真太阳时校正（可选）。

    返回: 结构化 dict，含 facts（确定性盘面）与 tradition（流派相关）。
    """
    birth = BirthInput(
        year=year, month=month, day=day, hour=hour, minute=minute,
        gender=gender, calendar=calendar, timezone=timezone,
        longitude=longitude, latitude=latitude,
    )
    chart: BaziChart = calculate_bazi(birth, sect=sect)
    return _facts_dict(chart)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_liuyao(
    yao_values: list[int] | None = None,
    coins: list[list[bool]] | None = None,
    topic: str | None = None,
    gender: str | None = None,
) -> dict[str, Any]:
    """六爻起卦 + 装卦：纳甲 / 六亲 / 世应 / 六神 / 伏神 / 旬空 / 月建旺衰 / 用神。

    参数:
        yao_values: 六爻数值（自下而上，6 个数）。每爻 6/7/8/9（老阴/少阳/少阴/老阳）。
        coins: 摇卦结果（6 组，每组 3 枚铜钱正反面），与 yao_values 二选一。
        topic: 占问类别（财运/事业/婚姻/健康等），用于取用神。
        gender: 婚姻占问时需提供。

    返回: 结构化 dict（起卦结果 + 装卦详表 + 用神取用）。
    """
    result: LiuYaoResult = cast_liuyao(yao_values=yao_values, coins=coins)
    day_pillar, month_pillar = _today_ganzhi()
    divination = zhuang_gua(
        result, day_pillar=day_pillar, month_pillar=month_pillar,
        topic=topic, gender=gender,
    )
    return divination.to_dict()


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_duan_liuyao(
    yao_values: list[int] | None = None,
    coins: list[list[bool]] | None = None,
    topic: str | None = None,
    gender: str | None = None,
) -> dict[str, Any]:
    """六爻断卦：基于装卦结果，综合用神旺衰 / 世应 / 旬空 / 动爻给出吉凶倾向。

    参数同 xuanpan_liuyao（起卦 + 装卦 + 断卦一键完成）。
    返回: 结构化 dict（装卦事实 + 吉凶倾向 + 流派不确定性）。
    注意: 吉凶为「倾向」（偏吉/中平/偏凶），非绝对断语，属流派规则。
    """
    result: LiuYaoResult = cast_liuyao(yao_values=yao_values, coins=coins)
    day_pillar, month_pillar = _today_ganzhi()
    divination = zhuang_gua(
        result, day_pillar=day_pillar, month_pillar=month_pillar,
        topic=topic, gender=gender,
    )
    duan = duan_liuyao(divination)
    return {"divination": divination.to_dict(), "duan": duan.to_dict()}


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_duan_bazi(
    year: int,
    month: int,
    day: int,
    hour: int,
    minute: int = 0,
    gender: str | None = None,
    sect: int = 2,
) -> dict[str, Any]:
    """八字断卦：日主旺衰 + 喜用神 + 大运吉凶倾向。

    参数同 xuanpan_bazi 的关键字段。
    返回: 结构化 dict（盘面事实 + 旺衰 + 大运吉凶倾向 + 流派不确定性）。
    注意: 吉凶为「倾向」（偏吉/中平/偏凶），取用神体系属流派规则（本版扶抑法）。
    """
    birth = BirthInput(year=year, month=month, day=day, hour=hour, minute=minute, gender=gender)
    chart: BaziChart = calculate_bazi(birth, sect=sect)
    duan = duan_bazi(chart)
    return {"chart": chart.to_dict(), "duan": duan.to_dict()}


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_almanac(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
) -> dict[str, Any]:
    """黄历：建除十二神 / 二十八宿 / 黄道黑道 / 冲煞 / 宜忌 / 彭祖百忌。

    参数:
        year/month/day: 阳历日期；不填则取今日。

    返回: 结构化 dict（当日黄历全量事实 + 宜忌说明）。
    """
    now = _dt.datetime.now()
    dt = _dt.date(year or now.year, month or now.month, day or now.day)
    result: AlmanacResult = calculate_almanac(dt)
    return _facts_dict(result)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_zeri(
    event: str,
    start: str | None = None,
    end: str | None = None,
    limit: int = 10,
    shengxiao: str | None = None,
    detail: bool = False,
) -> dict[str, Any]:
    """择日：给定事件，在其日期区间内反推候选吉日（黄历只能正向查宜忌，本工具反向筛选）。

    参数:
        event: 事件 key。可选：
            jiaqu(嫁娶)、dianli(订婚纳采)、kaiye(开业开市)、dongtu(动土起基)、
            yiru(入宅移徙)、anzhuang(安床)、jisi(祭祀祈福)、chuxing(出行)、
            qiuyi(求医问诊)、anzang(安葬)、kaiguang(开光)、xiuzhuang(修造装修)、
            ruxue(入学)、furen(赴任就职)、zaizhong(栽种)、shangliang(上梁立柱)、
            zuozao(作灶安灶)
        start / end: 阳历 YYYY-MM-DD。不填 start 取今日，不填 end 取 start 起 90 天。
            只问某一天是否相宜时，令 start == end。
        limit: 最多返回候选数（按评分降序），<=0 表示不限。
        shengxiao: 当事人属相（如「鼠」）；填写后自动排除冲该属相的日子。
        detail: True 时把被否决的日子连同否决原因一并返回（可用于解释「为何这天不行」）。

    返回: 结构化 dict（facts 层 = 候选吉日与评分依据；tradition 层 = 流派口径与不确定性）。
        候选为空是合法结果（如「赴任」本就吉日稀少），不是错误。

    说明: 结果为「吉/次吉/平/不宜」分级倾向，属通行黄历口径，不等同于宜忌断语。
    """
    today = _dt.date.today()
    raw_start = start or today.isoformat()
    raw_end = end or (today + _dt.timedelta(days=90)).isoformat()
    result: ZeriResult = select_auspicious_days(
        event, raw_start, raw_end,
        limit=limit, shengxiao=shengxiao, include_unfavorable=detail,
    )
    return _facts_dict(result)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_name(name: str, surname: str | None = None) -> dict[str, Any]:
    """姓名分析：康熙笔画 / 五格（天格人格地格外格总格）/ 三才配置。

    参数:
        name: 姓名（如「玄盘」「欧阳娜娜」）。
        surname: 复姓时显式指定（如 name="娜娜", surname="欧阳"）；单姓可省略。

    返回: 结构化 dict（五格数理 + 三才 + 流派不确定性说明）。
    """
    full = f"{surname}{name}" if surname else name
    result: NameAnalysis = analyze_name(full)
    return _facts_dict(result)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_qian(seed: int, set_id: str = "demo_guanyin") -> dict[str, Any]:
    """灵签抽签。

    参数:
        seed: 抽签随机种子（整数）。
        set_id: 签库标识（默认 demo_guanyin）。

    返回: 结构化 dict（签号 / 签名 / 签诗 / 等级 / 解读）。
    """
    result: QianResult = draw_qian(seed, set_id=set_id)
    return _facts_dict(result)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_compass(
    sitting: str | None = None,
    facing: str | None = None,
    degree: float | None = None,
    confidence: float = 1.0,
    confirmed_by_user: bool = False,
) -> dict[str, Any]:
    """罗盘坐向（玄盘独有能力）：二十四山坐向 / 五行生克 / 分金。

    参数:
        sitting: 坐山名（如「午」「子山」）；facing 与 degree 可替代。
        facing: 向山名。
        degree: 罗盘实测角度（0~360）。
        confidence: 识别置信度 0~1。
        confirmed_by_user: 是否已由用户确认。

    返回: 结构化 dict（坐向 + 分金 + 五行关系）。
    """
    result: CompassOrientation = calculate_orientation(
        sitting=sitting, facing=facing, degree=degree,
        confidence=confidence, confirmed_by_user=confirmed_by_user,
    )
    return _facts_dict(result)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
