# HANDOFF.md — 玄盘 AI 项目接手指南

> 给**下一个接手本项目的 WorkBuddy / AI 账号**。新会话打开仓库后，先读本文件，再按 §0 顺序读规范。

---

## 0. 接手第一步（固定顺序）

1. 读本文件（当前页）
2. 完整读 `AGENTS.md`（最高开发规范，两条铁律 + RULE-001~010）
3. `git status` + `git log --oneline -15`，确认工作区干净、最近提交
4. 读 `.workbuddy/memory/MEMORY.md`（项目长期记忆）与最近 `.workbuddy/memory/YYYY-MM-DD.md`（日志）
5. 读 `docs/玄盘 AI — 术数能力追赶路线图.md`（术数能力矩阵 + 缺口地图）

> 关键心智模型：**AI 没有跨会话记忆，git 历史 + 记忆文件是唯一记忆载体**。接手时务必先读，别凭猜测动手。

---

## 1. 项目一句话

**玄盘 AI（XuanPan AI）**：罗盘视觉识别 × 确定性术数计算 × AI 解释的移动端 App。
核心不是「AI 算命」，而是**把实体罗盘转成结构化数字数据**。
工程铁律：**AI 负责看/理解/解释；代码负责算/校验/映射；计算层是唯一真源，禁 LLM 介入**。

> ⚠️ 勿与「龙息 · 全息监控引擎」（A 股量化）混淆，那是另一条产品线。

---

## 2. 待完成事项（阿勇的原话目标）

> 「整理项目，把此目录丢给另一个 workbuddy 账号后能继续完成『三式』和『择日决策』」

详见路线图 §3.5 / §3.6。**进展如下**：

| 事项 | 状态 | commit |
|---|---|---|
| 择日决策 | ✅ **已完成**（2026-09-17） | `b3831eb` 核心层 + `45c45a0` MCP 工具 |
| 三式（奇门/六壬/太乙） | ⚪ **未开始**，等待实施 | — |

### 2.1 择日决策 ✅ 已完成（无需重做）

**已交付**：`packages/fortune-core/fortune_core/zeri.py`
（`evaluate_day` 单日评价 + `select_auspicious_days` 区间筛选，17 个事件，
MCP 工具 `xuanpan_zeri`）。

**接手时只需知道**（想扩展再看细节）：
- 事件宜忌词目全部取自 lunar-python 真实词表，**改词目前先跑**
  `python scripts/verify_zeri_table.py --check-veto`（会检出造词 / 死规则 / 同词宜忌冲突）
- veto 采用「忌优先」；**不要**把「忌行丧 / 忌分居」加进嫁娶否决 ——
  实测会误杀 37 天（占婚嫁吉日 14%），因为行丧与婚嫁无对应关系
- 若要加**新事件**：改 `data/zeri_events.json` 的 events 段，并**同步更新
  MCP 工具 docstring**（有测试守卫，漏更新会失败）

### 2.2 三式（奇门遁甲 / 大六壬 / 太乙神数）—— 长线，难度高

**现状**：全行业空白，无开源 MCP 项目在做 `[推测]`。**尚未开始**。

**要做**：先攻克排盘算法（奇门定局/排盘、六壬天地盘/四课三传、太乙积年）。**建议先做奇门遁甲或大六壬二选一**，勿三个一起上。

**硬约束**：
- 这是**算法攻坚**，不是简单复用。先读权威术数教材/开源参考，**先给方案 + 排盘对照表再动手**（AGENTS.md §3 工作流）
- 每个核心算法必须配单元测试（RULE-007），用已知公历时刻的权威排盘结果做对照锚点
- 明确区分「已确认的排盘事实」与「流派差异」（如奇门置闰/拆补、六壬昼夜贵神等，各家口径不一，必须模块化 RULE-006）

---

## 3. 技术栈速查（以 MEMORY.md 为准，勿信 AGENTS.md 旧表）

| 层 | 实际 | 位置 |
|---|---|---|
| 移动端 | React Native + Expo（expo-router，SDK 52） | `apps/mobile` |
| 后端 | FastAPI + uvicorn | `services/api` |
| 计算内核 | 自研 `packages/fortune-core`（Python 纯函数） | `packages/fortune-core/fortune_core` |
| 历法引擎 | `lunar-python`（`sxtwl` 在 Py3.13 无 wheel，已弃） | — |
| 存储 | **SQLite 单文件**（PostgreSQL/Redis/S3 只是报告 `[推测]`，未落地） | 根 `data/` 运行时产物 |
| MCP 暴露层 | `services/mcp/server.py`，9 工具，stdio | `services/mcp` |
| 识别 | 本地 CV（classical，零成本）默认；云端 opt-in | `services/vision` |

🔴 **领域数据表在 `packages/fortune-core/data/`**，不是根 `data/`。

### 关键目录

```
packages/fortune-core/fortune_core/
  ├── bazi/        # 八字：chart / dynamics(大运流年) / shensha(18神煞) / strength(旺衰) / wuxing
  ├── liuyao/      # 六爻：gua / najia(纳甲) / zhuang(装卦)
  ├── almanac.py   # 黄历（查每日宜忌）
  ├── zeri.py      # 择日决策（evaluate_day / select_auspicious_days，17 事件）
  ├── duangua.py   # 断卦层（duan_liuyao / duan_bazi，倾向+流派标注）
  ├── naming.py    # 姓名五格（康熙笔画 20794 字）
  ├── qian.py      # 灵签
  ├── compass.py / mountain24.py / fenjin120.py  # 罗盘二十四山/一百二十分金
  ├── schools.py   # 流派定义（RULE-006 模块化）
  └── context.py / exceptions.py / constants.py
services/mcp/server.py   # 9 个 MCP 工具
```

---

## 4. 关键约束（新账号最容易踩的坑）

### 4.1 两条铁律（AGENTS.md §2）

1. **每次改动 = 一个独立 commit**，一个 commit 一个逻辑单元，**禁 `git add -A`**
2. **每次改动必须同步测试、交付前全绿**，且附**实际执行的命令 + 真实输出**；未运行不得声称「测试通过」

### 4.2 术数专属铁律（RULE-001~010，全文见 AGENTS.md §2.3）

- RULE-001 确定性计算由代码完成
- RULE-002 LLM 不得修改计算层输出
- RULE-006 流派规则模块化（`schools.py`）
- RULE-007 核心算法必须有单元测试
- RULE-009 规则变更同步更新测试
- RULE-010 医疗/投资/法律不得伪装成命理确定性结论

### 4.3 结论标注（AGENTS.md §4）

每个结论显式标 `[已确认]` / `[推测]` / `[待验证]`，禁止把推测当事实。

### 4.4 交付格式（AGENTS.md §7）

每次交付固定四段：【完成内容】【修改文件】【验证结果】【剩余问题及下一步】。

---

## 5. 验证命令（在项目根目录跑）

```bash
# $PY = C:/Users/anyong/.workbuddy/binaries/python/envs/default/Scripts/python.exe（managed venv）
# 全量测试（当前 834 passed）
"$PY" -m pytest

# 分层
"$PY" -m pytest packages/fortune-core/tests    # 计算内核（新增三式/择日测试放这里）
"$PY" -m pytest tests/test_mcp_server.py       # MCP 暴露层（真实 stdio 子进程）
"$PY" -m pytest tests/vision                   # 罗盘识别
"$PY" -m pytest tests/api tests/ai tests/mobile
```

> ⚠️ 环境坑：WorkBuddy 的 `[safe-delete]` 会拦截 pytest 临时目录清理，可能**吞掉 `N passed` 汇总行并强制 exit≠0**。遇到「测试全绿但 exit=1」时，按模块分别跑并核对每个模块的 exit code，别误判成失败。详见 MEMORY.md / 日志。

> ⚠️ 本机有系统代理（`HTTP_PROXY` 指向 127.0.0.1），用 httpx/requests 连本机服务必须 `trust_env=False`。

### MCP 层单独跑

```bash
PYTHONPATH=packages/fortune-core "$PY" services/mcp/server.py   # stdio 模式启动
```

---

## 6. 环境事实（接手即用）

- git 身份：`ayongsheng777-rgb`；**尚无 remote 仓库**（如需跨账号协作，建议先建 remote 推上去）
- 端口：本地联调统一 **8360**（8352 被本机 SysCenter 占用）
- npm 源：`apps/mobile/.npmrc` 固定 `registry.npmmirror.com`
- pip 源：容器内 `PIP_INDEX_URL` 默认清华源（本机连宿主都解析不了 pypi.org）
- Python：3.13.12（managed venv）；Node：22.22.2（managed）
- 测试无需 `pip install -e`，`conftest.py` 已注入 5 个包路径

---

## 7. 其它待办（非本次目标，但接手时可能遇到）

按性价比（详见 MEMORY.md「待办」与路线图 §4）：

1. **真实罗盘照片取证**（Gate 1 唯一卡点，需阿勇提供照片）：`real_photos/` + `labels.csv`，跑 `scripts/gate1_eval.py photos`
2. 修 R8 假阳性（识别山名错误 15/96）—— 先建假阳性回归基线
3. 真机 UI 走查（「3 秒内确认」只能在真机测）
4. SKILL.md 打包（让仓库同时是 MCP Server + Agent Skill，可抄 suanming-mcp 的 Agent 入口）
5. 神煞吉凶分级（建议留给 AI 层，内核只给 FACT）
6. 建 remote 仓库

---

## 8. 外部项目结论（勿重复调研）

- **suanming-mcp（玄机阁）**：已评估完毕，**术数计算层不可信**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画表缺字按 Unicode 静默编造），**不做依赖、不移植算法**。三处可借鉴：MCP 暴露层写法、SKILL.md 打包范式、水墨 HTML 渲染。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`。
