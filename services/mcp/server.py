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
    InvalidInputError,
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
from fortune_core.liuren import LiurenChart, cast_liuren
from fortune_core.qimen import QimenChart, cast_qimen
from fortune_core.taiyi import TaiyiChart, cast_taiyi
from lunar_python import Solar

APP_VERSION = "0.1.0"

server = MCPServer(
    name="xuanpan",
    title="玄盘 AI · 术数计算内核",
    description=(
        "确定性术数计算（八字 / 六爻 / 黄历 / 择日 / 姓名 / 灵签 / 罗盘坐向 / 三式）。"
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


def _parse_local_dt(raw: str | None) -> _dt.datetime:
    """解析「本地时刻」字符串。

    容忍三种写法（Agent 调用时经常只给日期）：
    - "" / None        → 当前时刻
    - "YYYY-MM-DD"     → 该日 12:00（正午，避开子时换日与早/晚子时之争）
    - "YYYY-MM-DD HH:MM[:SS]"

    只给日期时取 12:00 而不是 00:00：**00:00 在奇门里属子时**，
    而子时存在早子/晚子换日争议，用正午可以绕开这个流派歧义。
    """
    text = (raw or "").strip()
    if not text:
        return _dt.datetime.now()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = _dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if fmt == "%Y-%m-%d":
            return parsed.replace(hour=12)
        return parsed
    raise InvalidInputError(
        f"无法解析时刻 {text!r}；请用「YYYY-MM-DD HH:MM」或「YYYY-MM-DD」"
    )


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


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_qimen(datetime_str: str = "", school: str = "chaibu") -> dict[str, Any]:
    """奇门遁甲排盘（三式之一）：定局 + 地盘/天盘/九星/八门/八神。

    参数:
        datetime_str: 本地时刻。不填或传 "" 取当前时刻；支持
            "YYYY-MM-DD HH:MM" 与 "YYYY-MM-DD"（后者取该日 12:00）。
            奇门以**时辰**起局，故不接受只有日期之外的更粗粒度。
        school: 定局流派，目前仅 chaibu（拆补法）。

    返回: 结构化 dict：
        dingju  —— 节气 / 三元 / 阴阳遁 / 局数（含中文标签如「阴遁六局」）
        pillars —— 年 / 月 / 日 / 时四柱
        xunshou / zhifu_yi / zhifu_gong / zhifu_star / zhishi_door —— 旬首与值符值使
        palaces —— 九宫（每宫含地盘干 / 天盘干 / 九星 / 八门 / 八神 + 空亡/驿马标记）
        xun_kong / yima —— 旬空与驿马
        uncertainties —— **本版未覆盖项**，务必如实向用户转述

    说明: 局数与盘面全部由确定性内核算出（RULE-001），不含随机数、不调用语言模型。
        格局吉凶判断（十干克应等）不在内核范围，属上层解读，请勿把盘面当断语。
    """
    dt = _parse_local_dt(datetime_str)
    chart: QimenChart = cast_qimen(dt, school=school)
    return _facts_dict(chart)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_liuren(datetime_str: str = "", school: str = "default") -> dict[str, Any]:
    """大六壬起课（三式之二）：月将加时 + 四课 + 三传 + 十二天将。

    参数:
        datetime_str: 本地时刻。不填或传 "" 取当前时刻；支持
            "YYYY-MM-DD HH:MM" 与 "YYYY-MM-DD"（后者取该日 12:00）。
            六壬以**月将加时**起课，同一个日子的不同时辰是完全不同的课，
            故必须给到时辰粒度。
        school: 流派，目前仅 default（通行本）。

    返回: 结构化 dict：
        day_ganzhi / hour_zhi —— 日柱与占时支
        month_general / month_general_name / zhongqi —— 月将及其所依中气
        guiren —— 昼/夜贵、贵人支、所临地盘宫、顺布或逆布
        lessons —— 四课（每课含上下神、五行、是否初传所出）
        palaces —— 十二宫（地盘支 / 天盘支 / 所带天将 + 天将吉凶属性）
        chuan —— 初/中/末三传（含所带天将与遁干）
        chuanke —— 取传所用宗门（九宗门之一），chuanke_note 为其口径说明
        xun_kong / yima —— 旬空与驿马
        uncertainties —— **本版未覆盖项**，务必如实向用户转述

    说明: 月将按**中气**换将（非节气），天地盘、四课、九宗门取三传、天将顺逆布
        全部由确定性内核算出（RULE-001）。天将的吉凶属性是**天将自身的属性**，
        不是对所问之事的结论；内核不给吉凶断语，断语属上层解读（RULE-008）。
        三传的遁干若为 null，表示该支落旬空 —— 这是领域信号，不是数据缺失。
    """
    dt = _parse_local_dt(datetime_str)
    chart: LiurenChart = cast_liuren(dt, school=school)
    return _facts_dict(chart)


@server.tool(structured_output=True)
@_domain_errors_as_tool_error
def xuanpan_taiyi(year: int | None = None, school: str = "default") -> dict[str, Any]:
    """太乙神数起局（三式之三）：年局 —— 太乙落宫 + 三目 + 主客定三算 + 八门。

    参数:
        year: 公元年份，如 2026。不填取当前年份。
            ⚠️ 只接受**年份**，不接受日期或时刻 —— 太乙年局的最小单位就是年。
            这与大六壬「必须给到时辰」刚好相反，两者不可互相套用：
            传 datetime 会让人以为太乙年局随时辰而变。
        school: 流派。默认 default（金镜式积年 10153917）；
            taojin 为淘金歌积年 10153977。两者相差 60（一甲子），
            会让太乙落宫、文昌、局数、值事门**全部不同** ——
            向用户说明时必须点明用的是哪一派，否则数字对不上任何一本书。

    返回: 结构化 dict：
        epoch      —— 五元六纪：第几元 / 元内第几局（如「壬子元第 31 局」）/ 第几纪
        taiyi      —— 太乙落宫（宫号 / 卦 / 方位 / 入宫第几年 / 理天·理地·理人）
        wenchang   —— 文昌天目所在十六神位
        jishen     —— 计神所在支
        shiji      —— 始击客目所在十六神位
        dingmu     —— 定目所在十六神位
        sansuan    —— 主算 / 客算 / 定算：算数 + 大将/参将落宫 + 长短 + 三才 + 和数/孤数
        bamen      —— 值事门 + 八门落宫（含门自身的吉凶属性）
        warnings   —— 命中边界情形时的提示（如「间神与太乙同宫」），需人工核对
        uncertainties —— **本版未覆盖项**，务必如实向用户转述

    说明: 🔴 太乙宫号与洛书**逐宫错位**（乾1 离2 艮3 震4 兑6 坤7 坎8 巽9），
        不要套用奇门的九宫。全部结果由确定性内核算出（RULE-001）。
        **本版只做年局**，太乙另有月局 / 日局 / 时局，未实现。
        三算的长短、和数、孤数、三才，以及八门吉凶，都是**属性**（FACT）——
        内核不给「利主 / 利客」这类结论，格局（掩迫囚击关格）与断法属上层解读
        （RULE-008）。请勿把三算数字直接说成吉凶。
    """
    y = year if year is not None else _dt.datetime.now().year
    chart: TaiyiChart = cast_taiyi(y, school=school)
    return _facts_dict(chart)


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
