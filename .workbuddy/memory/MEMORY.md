# 玄盘AI · 项目长期记忆

> 最近更新：2026-09-17 14:00（第五轮：术数全面追赶 + 罗盘仿真 UI）

## 项目基本盘

- **定位**：**玄盘 AI（XuanPan AI）** —— 罗盘视觉识别 × 确定性术数计算 × AI 解释的移动端 APP。核心不是「AI 算命」，而是**把实体罗盘转成结构化数字数据**（勿与「龙息 · 全息监控引擎」A 股项目混淆）
- **工程核心原则**：AI 负责看 / 理解 / 解释；代码负责算 / 校验 / 映射。**计算层是唯一真源，禁 LLM 介入**
- **仓库**：`D:\WorkBuddy\玄盘AI`，默认分支 `main`，尚无 remote

## 技术栈（2026-09-16 核对实现后的实际情况）

| 层 | 实际用的 | 注意 |
|---|---|---|
| 移动端 | React Native + Expo（expo-router，SDK 52） | `apps/mobile` |
| 后端 | FastAPI + uvicorn | `services/api` |
| 计算内核 | 自研 `packages/fortune-core` | 历法引擎 `lunar-python`（`sxtwl` 在 Py3.13 无 wheel，已弃） |
| **存储** | **SQLite 单文件** | ⚠️ 报告 §4 列的 PostgreSQL / Redis / S3-MinIO 只是 `[推测]` 选型建议，**未落地，代码里没有任何 Redis / S3 调用**。别再照它写编排或文档 |
| 识别 | 本地 CV（`classical`，零成本）为默认；云端视觉 opt-in | `?provider=openai_compat` 才用 |
| 部署 | docker compose（单 service） | 宿主 8360 → 容器 8352 |

🔴 **领域数据表在 `packages/fortune-core/data/`**，不是根 `data/`。根 `data/` 只装运行时产物（`xuanpan.db`、上传原件）。

## 开发规范（根目录 `AGENTS.md` 为最高规范）

🔴 **新会话必须先完整阅读 `AGENTS.md`** —— AI 无跨会话记忆，仓库状态与 git 历史是唯一记忆载体

两条铁律：

1. **每次改动必须创建对应的单独 commit**，一个 commit 一个逻辑单元；禁用 `git add -A`
2. **每次改动必须同步测试，交付前全绿**，且必须附上**实际执行的命令 + 真实输出**；未实际运行不得声称「测试通过」

约定：提交格式 `<type>(<scope>): <中文简述>`；结论标 `[已确认]`/`[推测]`/`[待验证]`；交付固定四段（完成内容 / 修改文件 / 验证结果 / 剩余问题及下一步）；引入新依赖前先说明成本。

## 环境

- git 身份：`ayongsheng777-rgb` / `277914440+ayongsheng777-rgb@users.noreply.github.com`
- **端口**：本地联调与容器宿主映射统一用 **8360**（8352 已被本机 SysCenter 占用）
- **npm**：`apps/mobile/.npmrc` 固定 `registry.npmmirror.com`（`registry.npmjs.org` 本机不可达）
- **pip（容器内）**：Dockerfile 的 `PIP_INDEX_URL` ARG 默认指向清华源 —— 本机连宿主都解析不了 `pypi.org`（宿主靠 `HTTP_PROXY` 代理远端解析才装得上）
- 本机有系统代理（`HTTP_PROXY` 指向 127.0.0.1），**用 httpx/requests 连本机服务必须 `trust_env=False`**
- 🔴 **`Path.write_text()` 在 Windows 会把 LF 转 CRLF** —— 写脚本做「读-改-写」还原文件时；
  因为仓库 `.gitattributes` 声明 `*.py text eol=lf`，入库虽会归一，但**工作区文件已被静默改脏**
  （实测：555 行全变 CRLF，MD5 变化）。要保持字节级还原须用 `read_bytes`/`write_bytes`，
  并**用 md5 核对还原结果，不能只信脚本自报「已还原」**
- 🔴 **全量测试约 190s，超过 Bash 默认 120s 前台超时** —— 跑 `-m pytest` 全量时；
  因为会被 SIGTERM 截断且**无任何输出**（易误判成测试崩溃）。须显式加大 timeout 或落盘后 tail
- 🔴 **`.workbuddy/` 目录是项目数据，非缓存，不得删除**

## 材料与裁定

- 🔴 **`docs/玄盘 AI — 产品基线规范.md` 是唯一真源（SSOT）**，冲突时以其为准，不得自行择一执行
- 🔴 **界面演示图：配色已采纳，但术数数据不可采信** —— 实算已证其八字「日柱/时柱/日主」三项错误

### 已裁决 5 项（2026-09-16）

| 项 | 结论 |
|---|---|
| 底部导航 | **方案 A：5 栏** —— 罗盘 ｜ 命盘 ｜ 占测 ｜ **历史** ｜ 我的 |
| AI 报告结构 | **方案 B：三标签** —— 盘面事实 ｜ 传统分析 ｜ AI 解读 |
| 配色 | **演示图色板**（像素实测提取） |
| 相机入口 | **双入口：拍照 + 相册上传**，共用同一识别管线 |
| **隐私表述** | **「数据可外流」** —— 承认照片出端的事实，按真实架构措辞。**已执行并全仓核查完毕**，无残留「不外流」假承诺 |

### Design Token（像素实测）

`--brand-primary` `#013A6C` ｜ `--brand-gold` `#DAB37D` ｜ `--brand-sand` `#E5D7C7` ｜ `--brand-jade` `#3C7066` ｜ `--brand-cinnabar` `#B93E35`

## 现状（2026-09-17 16:30）

- **Phase 0~3 全部落地**，**834 测全绿**（基线演进：626 → 765 → 786 → 834）
- 术数能力已补齐：六爻装卦层、八字大运/流年/神煞/长生十二宫、黄历/择日、
  **断卦层（`duangua.py`：六爻/八字吉凶倾向 + 流派标注）**、
  **择日决策（`zeri.py`：17 事件反推吉日，分级非断语 + 流派模块化）**
  （详见 `docs/玄盘 AI — 术数能力追赶路线图.md`）
- **康熙笔画字库已扩至 20794 字**（`verified:true`，权威源 shunshi-kangxi-core，
  修正 28 处简繁混用错误；「玄盘」「阿哲」等常用字全部可算）
- **MCP 暴露层已交付**（`services/mcp/server.py`，**9 个工具**，回 structuredContent，
  纯 stdio 不弹浏览器；测试走真实 stdio 子进程）
- 移动端罗盘盘面仿真（`CompassDial`/`CompassAdjuster`）+ 每页右上角讲解入口（`HelpButton`）
- 端到端冒烟、容器化、移动端闭环均已交付；`[未验证]` 真机 UI 走查未做
- 无 remote 仓库

## 风险与下一步

- **R1**：罗盘识别可行性 —— 全项目根基风险
- **R8 🔴 假阳性**：识别给出山名候选但山名错误（实测 15/96）。**与「识别不出」性质完全不同** ——
  用户看到的是一个看似正常的错误坐向，不会去重拍。当前**唯一防线是 `needs_user_confirmation`
  （RULE-004），不得为降低确认率而移除**
- **R9 已修复**：贴边判据因噪点恒定误报「罗盘未完整进入镜」→ 改为几何判据，命中率 63.7% → 80.0%

### 待办（按性价比）

1. **真实罗盘照片取证**（Gate 1 唯一卡点，需人提供）：`real_photos/` + `labels.csv`，
   ≥5 类拍摄条件 × 各 ≥3 张；跑 `scripts/gate1_eval.py photos`
2. 修 R8：掩膜抗污染（排除与盘体不连通的边缘连通域 / 鲁棒质心）
3. 先建假阳性回归基线（当前 15/96），否则修 R8 时无法判断是否真变好
4. 真机 UI 走查 —— 「3 秒内确认」只能在真机测
5. 尚无 remote 仓库

### 术数追赶下一步（2026-09-17 择日决策亦已收官，剩余唯一空白 = 三式）

已落地：MCP 暴露层 / 康熙笔画字库 / 断卦层 / **择日决策**（`b3831eb` 核心 + `45c45a0` MCP）。
剩余按性价比：

1. **SKILL.md 打包范式**（让仓库同时是 MCP Server + Agent Skill，抄 suanming-mcp 的 Agent 入口）
2. **三式**（奇门/六壬/太乙）—— **全项目唯一剩余空白**，长线挂起，价值高但算法难；
   先奇门或六壬二选一，先给方案+排盘对照表再动手
3. 择日进阶（三煞/太岁/五黄、按当事人八字择日）—— 已显式列为未覆盖项
4. 神煞吉凶分级 —— **不建议做**，宜留给 AI 层（内核只给 FACT）

## 外部项目已评估（勿重复调研）

- **suanming-mcp（玄机阁）** —— <https://github.com/Enoch666/suanming-mcp>，
  commit `f08ec272b6928af8faa79300f50b4d740ffbbd1f`。**已于 2026-09-17 评估完毕，结论：术数计算层不可信，不做依赖、不移植算法。**
  六爻卦序 63/64 错配、八字月柱 10/10 错、笔画表缺字时按 Unicode 码位静默编造。
  详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`；复算工具 `scripts/cmp_suanming_mcp.py`。
  **三处可借鉴**：MCP 暴露层写法、`SKILL.md` 打包范式、水墨 HTML 渲染。
  **它揭示的行业缺口**：所有开源项目都停在「排盘/起卦」，**装卦层（六爻纳甲六亲世应、八字大运流年）与三式（奇门/六壬/太乙）全空** —— 这是玄盘 RULE-001 最该吃下的差异化领域

## 已知自身数据缺口

- ✅ **`data/kangxi_strokes.json` 已扩至 20794 字且 `verified: true`**（2026-09-17 完成，见上）。
  数据源 `data/kangxi_kx_source.json`（288KB，来自 shunshi-kangxi-core@0.1.1 MIT）。
  缺字（扩展区生僻字）仍由 `analyze_name` 抛 `DomainDataMissingError`（不静默取错值）。
  复算工具 `scripts/cmp_suanming_mcp.py` 与 `scripts/gen_strokes_table.py` 已就位。

## 术数能力落地要点（2026-09-17，避免重复造轮子）

- 🔴 **lunar-python 神煞接口不存在**（`getXxxShiShen` 是「十神」不是「神煞」），神煞 18 张口诀表只能自建（`bazi/shensha.py`）。
  但以下**全是现成接口，直接复用别自造**：长生十二宫 `getXxxDiShi`、身宫 `getShenGong`、胎息 `getTaiXi`、
  黄历全套（`getZhiXing` 建除 / `getXiu` 二十八宿 / `getDayTianShen` 黄黑道 / `getDayYi`/`getDayJi` 宜忌 /
  `getDayChong`/`getDaySha` 冲煞 / `getPengZuGan`/`getPengZuZhi` 彭祖百忌）、大运 `getYun`。
- 大运 `getYun` 第 0 步是「起运前」空档（干支空串），流年从 index 1 起；顺逆看**年干**阴阳（阳年男/阴年女顺排）。
- 建除推导 `JIANCHU_12[(日支序−月支序)%12]`，交节日（节气切换）与库有月支口径差，需跳过校验并标注。

### 择日层要点（2026-09-17，`zeri.py`，避免重复造轮子）

- **规则表** `packages/fortune-core/data/zeri_events.json`：17 事件 + `schools` 段
  （建除分档/权重/分级阈值/veto 项）可整体替换（RULE-006）。
  **择日流派与 `schools.py` 的风水流派（三合/三元）是两套体系**，故意不共用注册表。
- 🔴 **改事件词目前必须跑 `scripts/verify_zeri_table.py --check-veto`** ——
  词目若写错（如把「忌嫁娶」写成不存在的词）**不会报错，只会静默失效**，
  筛选结果看似正常却少了一道否决。脚本做三项校验：词目真实性 / 死规则 / 同词宜忌冲突。
- 🔴 **别把「忌行丧 / 忌分居」加进嫁娶否决** —— 实测这两词出现在 85 天，
  其中 **37 天同时「宜嫁娶」**，加了会误杀 **14% 的婚嫁吉日**；行丧与婚嫁无对应关系。
  **教训：设计 veto 规则前先量化它影响多少天，别凭语义直觉。**
- **「同词既宜又忌」实测 0 例**（730 天 × 17 事件）→「忌优先」veto 无歧义。
- **「馀事勿取」是条件否决**：仅当事件未被宜项命中时生效（锚点 2024-01-04
  宜含「安葬 + 馀事勿取」，安葬不应被否决）。「诸事不宜」才是绝对否决（仅 7/730 天）。
- 黄历词表实测：宜 109 词 / 忌 79 词；宿吉凶、黄黑道、天神吉凶均为干净二值；
  建除 12 值均匀分布（各约 60/730）。
- **加新事件后必须同步 MCP 工具 docstring** —— `tests/test_mcp_server.py` 有防漂移守卫，
  漏更新会直接测试失败（docstring 是 Agent 发现能力的第一入口）。
