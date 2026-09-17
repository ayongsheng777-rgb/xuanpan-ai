# 玄盘 AI · MCP 暴露层

把 `fortune-core` 的纯函数内核包成 Model Context Protocol (MCP) 工具，供任意
MCP 客户端（Claude Desktop / WorkBuddy / Cursor 等）调用。

## 设计原则

对齐 RULE-001 / RULE-002 / RULE-006，并修正 suanming-mcp（玄机阁）的反模式：

| 原则 | 说明 |
|---|---|
| **回 `structuredContent`** | 每个工具返回内核 `to_dict()`（FACT/TRADITION 两层现成 JSON），不回自然语言摘要 |
| **纯 stdio，不弹浏览器** | 工具只做计算，不触发任何 GUI / 浏览器动作 |
| **计算层唯一真源** | MCP 工具只是内核函数的薄封装，不含任何 AI 生成逻辑 |
| **领域异常清晰化** | 内核领域异常（InvalidInputError 等）转成 ToolError，调用方能看到具体原因 |

## 8 个工具

| 工具 | 能力 |
|---|---|
| `xuanpan_bazi` | 八字排盘（四柱/十神/大运流年/神煞/长生十二宫） |
| `xuanpan_liuyao` | 六爻起卦 + 装卦（纳甲/六亲/世应/六神/伏神/旬空/用神） |
| `xuanpan_duan_liuyao` | 六爻断卦（吉凶倾向 + 流派标注） |
| `xuanpan_duan_bazi` | 八字断卦（日主旺衰 + 大运吉凶倾向） |
| `xuanpan_almanac` | 黄历（建除/二十八宿/黄黑道/冲煞/宜忌） |
| `xuanpan_name` | 姓名分析（康熙笔画/五格/三才，20794 字库） |
| `xuanpan_qian` | 灵签抽签 |
| `xuanpan_compass` | 罗盘坐向（玄盘独有能力：二十四山/分金/五行生克） |

## 接入方式

### WorkBuddy

在 `~/.workbuddy/mcp.json` 的 `mcpServers` 加一条（路径按实际仓库改）：

```json
{
  "mcpServers": {
    "xuanpan": {
      "command": "C:/Users/anyong/.workbuddy/binaries/python/envs/default/Scripts/python.exe",
      "args": ["D:/WorkBuddy/玄盘AI/services/mcp/server.py"],
      "env": {
        "PYTHONPATH": "D:/WorkBuddy/玄盘AI/packages/fortune-core"
      }
    }
  }
}
```

### Claude Desktop

在 `claude_desktop_config.json` 的 `mcpServers` 加同样一条。

## 运行与验证

```bash
# 直接启动（stdio 模式，等待 JSON-RPC 消息）
PYTHONPATH=packages/fortune-core python services/mcp/server.py

# 跑端到端测试（真实 stdio 子进程）
python -m pytest tests/test_mcp_server.py
```

## 依赖

- `mcp>=2.0`（已加入 `pyproject.toml` 依赖）
- `lunar-python`（内核既有依赖）

## 关键实现点

1. **structured_output**：`@server.tool(structured_output=True)`，mcp 2.x 会把返回
   dict 包装成 `structuredContent`，调用方拿到结构化数据而非文本。

2. **领域异常转换**：`_domain_errors_as_tool_error` 装饰器把 `FortuneError` 子类
   （InvalidInputError / DomainDataMissingError 等）转成 `ToolError`，让 Agent
   看到「非法公历日期：1990-13-1」而非笼统的 "Error executing tool"。

3. **六爻装卦需要当日干支**：`_today_ganzhi()` 从 lunar-python 取当日/当月干支，
   供 `zhuang_gua` 计算月建旺衰与日辰关系（不自算历法）。
