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
| 择日决策 | ✅ 已完成（2026-09-17） | `b3831eb` 核心层 + `45c45a0` MCP 工具 |
| 三式 · 奇门遁甲 | ✅ **全链路已交付** | 批次 6：`6eee59a` → `8226b62` |
| 三式 · 大六壬 | ✅ **全链路已交付** | 批次 7：`ff2d7c8` → `86a5a22` |
| 三式 · 太乙神数 | ✅ **全链路已交付**（年局/岁计） | 批次 8 |
| **V2 产品改造（演示图深色仪器风）** | ✅ **本轮范围已完成**（§2.5） | `6b3a27f` → `350c78e`（9 个，已推送） |

> **当前主线 = V2 已完成收尾，下一步是「真机 UI 走查」**（V2 又增 3 个页面，见 §7.1）。
> V2 的实现细节与三条守住的语义见 §2.5。

> 🔴 **一个容易踩的心智陷阱**：「内核做完了」≠「用户用得上」。
> 2026-09-17 下午做过一轮专项排查（§2.3）：`almanac` / `zeri` / `duangua`
> 三个能力内核里有、MCP 有，但**HTTP 没有路由、App 里 0 处引用** ——
> 能力存在，用户碰不到。接手后若要评估"某能力是否真的交付了"，
> 必须查**三条链路各通不通**：内核 → HTTP/MCP → App 界面。

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

### 2.2 三式（奇门遁甲 / 大六壬 / 太乙神数）✅ 三式全部完成

**现状**：三式全部打通**全链路**（内核 → HTTP/MCP → 管理台 → App）。
奇门（批次 6）、六壬（批次 7）、太乙（批次 8，年局/岁计）。

**接手时只需知道**：
- 太乙只做**年局（岁计）**，月/日/时局未实现（显式列在 `uncertainties`，勿当遗漏去补）
- 太乙宫号与洛书**逐宫错位**，`taiyi/constants.py` 刻意不复用奇门九宫表
- 三个术式的 HTTP 出口：`/qimen/pan`（排盘）、`/liuren/cast`（起课）、`/taiyi/cast`（起局）
  —— 动词各异是领域术语使然，非缺陷，别为"统一"去改路径（会破坏契约）
- 每个核心算法都有锚点测试（奇门定局 / 六壬四课三传 / 太乙 1972 等古籍锚点），
  改算法前先看 `packages/fortune-core/tests/` 下的对应锚点

### 2.3 最后一公里：查询域 HTTP + 管理台 + 前端接线 ✅ 已完成（2026-09-17 晚）

阿勇原话：「解决所有问题，**后端带管理界面，前端 APP 能实战**」。

**问题**：`almanac` / `zeri` / `duangua` 三个能力只经 MCP 暴露 ——
HTTP 层无路由、App 里 0 处引用。本轮把三条链路打通：

| 层 | 交付 | commit |
|---|---|---|
| 内核 | （上一轮已完成） | `b3831eb` / `a3ca381` |
| HTTP | `/api/v1/almanac/{day,range}`、`/zeri/{events,evaluate,select}`、`/duan/{liuyao,bazi}` | `a6eb3e5` |
| 管理台 | `/admin` 单文件页面 + `/api/v1/admin/*`（令牌鉴权，安全默认关） | `7ef24bb` |
| 前端 | 黄历/择日页、六爻断卦、大运倾向、共用断卦展示层 | `f09b298` / `fdd0a5d` / `22e8028` |

**接手时只需知道**：

- 管理台默认**关闭**（`XUANPAN_ADMIN_TOKEN` 为空 → 403 + 配置指引）。
  会话含出生日期等隐私数据，不设默认口令。页面与数据分离：令牌只存
  sessionStorage，并用 `replaceState` 从 URL 抹掉。
- `/zeri/select` 的区间上界 **3660 天在内核**（`MAX_RANGE_DAYS`），不在路由层 ——
  这样 MCP 与 HTTP 自动共享同一个界，不会出现"两个入口限制不一样"。
  （`/almanac/range` 的 31 天上界则确实在路由层，两个端点口径不同，别混淆。）
- `FortuneError` **不继承 `ValueError`**。`app.py` 里注册了全局处理器把它转 400；
  删掉它，本该是"你传错了"的错误会全变成 500。
- 前端日期换算只有一处实现：`apps/mobile/src/lib/date.ts`。
  **不要在任何页面里写 `toISOString().slice(0,10)`** —— 东八区凌晨会退一天，
  且只在一天的前 1/3 出现。回归守卫 `tests/mobile/test_local_date.py`。
- 八字断卦的 verdict 是「身强/身弱」，属**状态**而非吉凶，
  前端必须走中性色（`DuanCard.verdictTone` 的白名单只认「偏吉/偏凶」）。
  跨层守卫会解析 `DuanCard.tsx` 与内核常量对撞。

---

### 2.4 APK 与 WEBUI 的端到端可用性 ✅ 已完成（2026-09-17 深夜）

阿勇原话：「前端APK，后端WEBUI呢」。查下来的结论是 —— **两者都已存在，但都没到"能直接用"**：

- APK 是**六壬落地之前**打的（解包 grep「大六壬」「奇门」全部命中 0 次）
- WEBUI 的页面代码在仓库里，但跑着的容器是 **21 小时前的旧镜像**，`/admin` 直接 404

#### WEBUI（`/admin`）

| 事实 | 说明 |
|---|---|
| 访问 | `http://127.0.0.1:8360/admin?token=<令牌>`，令牌见本机 `.env` |
| 面板 | 概览 / 会话记录 / 黄历 / 择日筛选 / 六爻断卦 / 八字 / 奇门遁甲 / 大六壬（8 张） |
| 🔴 改了**后端**代码后必须 `docker compose up -d --build` | **只 `up -d` 不 `--build` 会继续跑旧镜像**。本轮故障就是这个：代码里有 `/admin`、容器里没有 |
| 令牌 | 本机 `.env` 已配 `XUANPAN_ADMIN_TOKEN`（`.gitignore` 已忽略 `.env`） |
| 鉴权途径 | 请求头 `X-Xuanpan-Admin-Token` / 查询参数 `?token=` / Cookie，三者之一 |
| 403 vs 401 | **403 = 令牌没配**（功能整体关闭）；**401 = 配了但值不对**。这个区分能省很多排查时间 |
| 页面本身不需要令牌 | 空壳页面 —— 若连页面都要令牌，用户会陷进「打不开 → 不知配什么 → 更打不开」的死循环 |

#### APK

- 构建：`bash apps/mobile/scripts/build-apk.sh`（实测约 30-40 分钟）
- 🔴 **`oc.ayong.qzz.io` 已无法解析**（nslookup 无记录 / ping 报"找不到主机"）。
  脚本曾把它当默认地址 —— 照默认打出的包，真机**必然连不上**。现已降为候选末位。
- 默认候选表 = **自动枚举的本机局域网 IPv4** + 域名兜底；APP 启动时并发探活自动选线。
  换网段不必重新打包。
- 手工指定候选：`API_BASE_URLS=http://a:8360,http://b:8360 bash apps/mobile/scripts/build-apk.sh`
- APP 内也可手改：「我的 → 网络线路」（**先探活再切换**，改错不会把自己锁在外面）

#### 本轮发现但未做

- `/qimen/pan` 与 `/liuren/cast` **命名不一致**（一个 `pan`、一个 `cast`）。
  不影响功能，但 Agent 与新人容易猜错路径（本轮就猜错了一次）。
- `fenjin120` 规则表缺失（管理台 `available=False`）—— 已知数据缺口，
  当前退化为「只输出几何格位 + 警告」。

---

### 2.5 V2 产品改造（演示图深色仪器风）—— ✅ 本轮范围已完成（2026-09-18）

**背景**：阿勇提供 V2 规范（`docs/玄盘_AI_V2_产品改造与实施规范.md`，2307 行）+ 8 屏演示图
（⚠️ **这 8 屏图不在仓库里**，仓库只有 `docs/ChatGPT Image …png` 那张原始界面图）。
差距分析、冲突裁决、本轮范围已全部固化在 **`docs/玄盘 AI — V2 评估与实施路线.md`**。
改造前基线 tag：**`v0.1.0-pre-v2`**，出问题可对照回滚。

**已完成（9 个 commit，已推送）**：

| 内容 | commit |
|---|---|
| V2 规范入库 + 评估与实施路线 | `6b3a27f` |
| tokens.ts 增加 `instrument` 深色仪器色域（仅罗盘域用） | `6b9666f` |
| CompassDial 双轨调色板（`DIAL_LIGHT` 默认 / `DIAL_DARK`） | `ff57318` |
| `sensorQuality.ts` 质量评估纯函数库 + 22 锚点测试（含变异验证） | `da1472b` |
| 罗盘首页改深色仪器风（演示图第 1 屏 · 仿真模式） | `09be135` |
| `/adjust` 手动调节罗盘页（演示图第 2 屏） | `e90f135` |
| `sparkline.ts` 曲线几何纯函数 + 17 锚点测试（含变异验证） | `f0d21d0` |
| **`/sensors` 传感器测量页**（演示图第 3 屏）+ 讲解主题 | `95bfa7c` |
| 罗盘首页讲解文案同步（V2 改仿真模式后已与实现不符） | `350c78e` |

**`/sensors` 实现要点（改它之前先看这几条，都是「看起来对但会误导」的坑）**：

- 要素：磁北指示 → 深色盘面（`rotation = -方位角`，磁针不随盘转）→ 方位角大字 →
  综合质量（含 磁场/水平/稳定 三项分解）→ 三张指标卡（磁场强度+波动 σ / 设备水平 /
  磁场质量 0~100）→ 可操作提示（V2 §8.4）→ 磁场强度曲线 → 原始三轴数据表
- 🔴 **三条守住的语义**（已写进 `sensors.tsx` 文件头注释，别"顺手优化"掉）：
  1. **无数据是一等状态**：显示「—」+ 可操作提示，**盘面不渲染** ——
     画一个静止在 0° 的盘面会被读成"当前方位就是 0°"（RULE-008 同精神）；
  2. **读数是相对磁北**，未做磁偏角改正 → 盘面山格只作方向参考，**不构成坐向结论**；
  3. **「磁场质量」不叫"精度"** —— 那个分数衡量的是强度是否在区间、波动是否小，
     本页不保证角度准确性，就不该用"精度"这个词（上一版本节写的「磁场精度」是演示图口径，已按此改）
- 🔴 **曲线几何不在页面里算**，走 `lib/sparkline.ts`：恒定读数（手机静止）时 `max-min≈0`
  当分母会得 `NaN` → 曲线**静默消失**（不报错、不崩溃，只是空白）；
  另有「最小跨度 4 μT」保护，否则静止时 0.3 μT 的噪声会被画成剧烈起伏。
  锚点测试 17 条且做过变异验证（去掉保护 → 7 failed）
- 折线用 `react-native-svg`（既有依赖，非新增）；`expo-sensors` 是上一轮引入的

**V2 本轮明确不做（别越界，裁决理由见评估文档）**：
- 底部导航**不动**（产品基线规范已裁定 5 栏：罗盘/命盘/占测/历史/我的）
- **不做全局深色化** —— 双轨并存：罗盘域深色（instrument）、其余页面保持浅色，
  待真机走查后再定是否推广
- 「自动水平 / 盘体跟随」、相机扫描增强、V2 Phase 3+ 全部暂缓

**遗留（是明确挂起，不是遗漏）**：

- `/adjust` 页**没有讲解入口**（其余页面都有）。它有两个锁、两种模式，其实比多数页更需要讲解；
  本轮不做是为了不越出断点范围。要补 = `help.ts` 加一个 `adjust` 主题 + 该页 `headerRight` 换成 `HelpButton`
- 真机 UI 走查仍未做，且 V2 又增 3 个页面 → 见 §7.1

---

### 2.6 AI 双文体 + 运行时可调配置 + 管理台配置面板（2026-09-18 续，10 个 commit 已推送）

**目标（阿勇原话口径）**：AI 解读要能切换**专业分析 / 白话讲解**；配置要能**在后台改、改完即时生效**，
不必改代码重打 APK。

| 内容 | commit |
|---|---|
| **AI 双文体**：`专业分析` / `白话讲解` 各出一整套区块 | `7829587` |
| 报告页可切换双文体（前端只认后端 `has_plain`） | `78c747c` |
| 双文体守卫：解析 / 术语 / 契约 / 端到端 | `c827f0f` |
| provider 链接受已解析配置，不再只认 `os.environ` | `f160184` |
| **运行时可调配置**：环境变量给默认，后台覆盖即时生效 | `21a92b2` |
| `.env.example` 修正错误的能力标签 | `6291d39` |
| 配置接口守卫 47 条：改了就生效 + 密钥永不回显 | `c10b6ee` |
| **管理台配置面板**（第 4 个导航页） | `f08e495` |
| 管理台页面接线守卫 18 条 | `dff8230` |
| 配置说明里的 Markdown 标记会原样显示成星号 | `bdfa456` |

**双文体要点**：

- 前端**只认** `has_plain` 布尔，不去猜文体；后端一次给两套 section
- 🔴 **解析顺序是「先按文体切分、再解析各区块」** —— 反过来的话，白话正文里出现的
  「专业」字样会让两套区块串台（结论看着正常、内容却是错的那套）
- **零成本模板 provider（`rule-template`）也必须产出两文体**，否则断网/未配 key 时
  切换键点了没反应；冒烟里专门有一条断言「两文体逐字不同的区块 > 0」，防的正是
  「白话版就是专业版复制一遍」

**运行时配置层要点（改配置相关代码前必读）**：

- 优先级 **管理台覆盖 > 环境变量 > 代码默认值**，接口对每一项都报来源（`override/env/default`）
- 两套配置并存：`get_settings`（环境基线，启动时冻结）vs `get_active_settings`（生效值）。
  **业务路径一律用后者**；只有 `app.state` 初始化还用前者。`deps.py` 里两者都在，别拿错
- AI 路由器按**配置指纹**缓存、指纹变化即重建（`RuntimeConfig.ai_router`）—— 这是「即时生效」的落点；
  去掉指纹比对，测试只会有 1 条红（另 2 条是「先改后首次取路由器」，构造上就按新值，抓不到）
- 密钥明文**只有一个出口**：`RuntimeConfig.llm()`。`entries()` 对密钥项**压根不带 `value` 字段**
  （不是打码，是不给）。`SECRET_KEYS = {llm.api_key, admin_token}`
- `admin_token` 刻意**不可从界面修改**（改错就把自己锁在门外）；「清除全部覆盖」只清可编辑项，
  显式点名不可编辑键才报错
- 覆盖落 SQLite `app_settings` 表（`SCHEMA_VERSION` 已由 1 升到 2）
- 🔴 **`admin.html` 的 `api()` 必须显式设 `Content-Type: application/json`** ——
  否则 fetch 对字符串 body 发 `text/plain`，FastAPI 直接 422，现象是「保存按钮点了没反应」。
  守这条的是 `tests/api/test_admin_page_wiring.py`
- 🔴 **管理台有静态接线守卫**（`tests/api/test_admin_page_wiring.py`，18 条）：`$('x')` 引用的 id 必须存在、
  `switchView` 名单与导航一致、JS 读的字段 ⊆ 后端给的字段、脚本可过 `node --check`、
  带 body 的请求必须声明 JSON。**加面板/改字段后它是最先报错的那道防线**
- 页面**不需要令牌**即可打开（否则陷入「打不开 → 不知配什么 → 更打不开」的死循环）；
  401 = 令牌值不对，403 = `XUANPAN_ADMIN_TOKEN` 没配（整体关闭）

---

## 3. 技术栈速查（以 MEMORY.md 为准，勿信 AGENTS.md 旧表）

| 层 | 实际 | 位置 |
|---|---|---|
| 移动端 | React Native + Expo（expo-router，SDK 52） | `apps/mobile` |
| 后端 | FastAPI + uvicorn | `services/api` |
| 计算内核 | 自研 `packages/fortune-core`（Python 纯函数） | `packages/fortune-core/fortune_core` |
| 历法引擎 | `lunar-python`（`sxtwl` 在 Py3.13 无 wheel，已弃） | — |
| 存储 | **SQLite 单文件**（PostgreSQL/Redis/S3 只是报告 `[推测]`，未落地） | 根 `data/` 运行时产物 |
| MCP 暴露层 | `services/mcp/server.py`，**12 工具**（含三式 qimen/liuren/taiyi），stdio | `services/mcp` |
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

services/api/xuanpan_api/
  ├── routers/     # calc / sessions / report / scan / meta ＋ almanac / zeri / duan / admin
  │                # ＋ qimen / liuren / taiyi（三式）
  ├── static/admin.html   # 管理台（单文件、零依赖、**无 CDN** —— 容器没有外网）
  └── schemas.py / storage.py / config.py / app.py
services/mcp/server.py   # 12 个 MCP 工具

apps/mobile/
  ├── app/(tabs)/  # 底部 5 栏：index(罗盘·V2深色仪器风) / chart(命盘) / divine(占测) / history / mine
  ├── app/         # 根 Stack：scan / almanac / sanshi(三式) / adjust(V2调节) / confirm/[id] / report/[id] / session/[id]
  └── src/
      ├── api/         # client.ts + types.ts（**手写**，与后端 schemas 对应）
      ├── components/  # DuanCard(断卦展示) / Chip+Tag / CompassDial(双轨调色板) / Card / …
      ├── lib/         # date.ts(本地日期唯一实现点) / sensorQuality.ts(V2) / compassDial.ts / taiyiLayout.ts …
      ├── services/    # useSensors.ts（V2 传感器 Hook，三路订阅）
      ├── theme/tokens.ts  # 含 instrument 深色仪器色域（仅罗盘域用）
      └── content/help.ts  # 每页右上角讲解文案
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
# 全量测试 = 1560 passed, 3 skipped（2026-09-18 实测，单进程全量 + 汇总行完整，EXIT=0）
# 🔴 跑全量必须把 basetemp 放到**系统 Temp 下**，否则会撞 safe-delete 批量守卫（见下方说明）
"$PY" -m pytest --basetemp="$("$PY" -c 'import tempfile;print(tempfile.gettempdir())')/xp-full"

# 分层
"$PY" -m pytest packages/fortune-core/tests    # 计算内核（新增三式/择日测试放这里）
"$PY" -m pytest tests/test_mcp_server.py       # MCP 暴露层（真实 stdio 子进程）
"$PY" -m pytest tests/vision                   # 罗盘识别
"$PY" -m pytest tests/api tests/ai tests/mobile
```

> 🔴 **`[safe-delete]` 批量守卫会打断 pytest；basetemp 放哪里，决定你是「丢一行」还是「丢 87 个用例」。**
>
> **机制**（`D:/software/WorkBuddy/resources/app.asar.unpacked/cli/vendor/shim/sitecustomize.py`，
> 已读源码确认）：`_should_bypass_safe_delete()` 只豁免三类路径 —— `tempfile.gettempdir()` 之下、
> pip 的 site-packages 临时目录、WorkBuddy 托管的 pip 路径。**其余路径每删一个文件/目录，
> 都要先去问批量守卫**（`_try_trash()` 的第一行就是 `_check_bulk_delete_guard()`）；
> 同一次工具调用内累计删除数 > 50（JSON 里 `scope:"turn"`）即 `raise SystemExit(1)`。
> 这个异常落在 pytest 的 fixture teardown 里 → 该用例变 **ERROR**；落在收尾清理里 → **汇总行来不及打印、exit=1**。
>
> **三种跑法实测对照（同一份代码，2026-09-18）**：
>
> | basetemp | 实测结果 | 危害 |
> |---|---|---|
> | `--basetemp=D:/tmp/pytest-clean1`（**非 Temp 目录**） | 970 passed 后首个 fixture ERROR 即停（`-x`）；全量口径 **1469 passed + 87 errors**，exit=1 | 🔴 最重：**大批用例集体 ERROR**，看着像代码坏了 |
> | `--basetemp="$T/xp-full1"`（`$T` = 系统 Temp） | **1560 passed, exit=0**，汇总行完整（254s；同口径 250.73s 复测一致） | ✅ **推荐** |
> | 不带 `--basetemp`（默认） | 用例**全部通过**（进度 100%、一个 `F`/`E` 都没有），收尾删 `pytest-of-anyong/garbage-*` 时被拦（实测 `count:175`）→ **汇总行丢失、exit=1** | ⚠️ 假失败，但至少没 ERROR |
>
> **结论（照这个来）**：
> 1. 跑全量/大批量一律 `--basetemp="$T/xxx"`，`$T` = `"$PY" -c 'import tempfile;print(tempfile.gettempdir())'`；
> 2. 🔴 **绝不要把 basetemp 指到 `D:/tmp` 这类非 Temp 目录** —— 本文档早版曾把它当「绕开守卫」的解法，
>    **方向是反的**：它把「丢一行汇总」升级成「87 个用例 ERROR」，比原来的问题严重得多；
> 3. 判据始终是**有没有 `F`/`E` + 那行 safe-delete JSON**，不是只看 exit code；
> 4. 命令行**不要传 `-q`**（`pyproject` 的 addopts 已含 `-q`，再传变 `-qq` 同样会吞掉汇总行）。
>
> **备选取数法**：分模块跑、逐个核 exit code。
>
> ```bash
> for m in packages/fortune-core/tests tests/vision tests/ai tests/api tests/mobile \
>          tests/test_mcp_server.py tests/test_doctests.py; do
>   printf '%-32s %s\n' "$m" "$("$PY" -m pytest "$m" -p no:warnings --tb=short 2>&1 \
>     | grep -E 'passed|failed' | tail -1)"
> done
> ```
> 想拿总数又不跑测试：`"$PY" -m pytest --collect-only -p no:warnings | tail -3`。
>
> ⚠️ **仍未查清的一环（别当成已定论）**：默认 basetemp 那次被拦的目标路径**就在系统 Temp 下**，
> 按上面的豁免规则本应放行。用两个独立探针直接测过「系统 Temp 下的普通路径」与「`\\?\` 长路径前缀」
> 各删 120 个，**都没被拦**（探针自检确认 shim 已 patch：`unlink.__module__ == "sitecustomize"`）——
> 但那些探针是在**非沙箱**工具调用里跑的，疑似此时批量计数本身就没启用，故**不能据此推断豁免边界**。
> 操作层结论不受影响（上表是三次真实全量跑的结果）；谁要追这一环，得在**沙箱内**做对照实验。

> ⚠️ 本机有系统代理（`HTTP_PROXY` 指向 127.0.0.1），用 httpx/requests 连本机服务必须 `trust_env=False`。

### MCP 层单独跑

```bash
PYTHONPATH=packages/fortune-core "$PY" services/mcp/server.py   # stdio 模式启动
```

---

## 6. 环境事实（接手即用）

- git 身份：`ayongsheng777-rgb`；**remote 已建**：`https://github.com/ayongsheng777-rgb/xuanpan-ai`（**私有**）。
  约定：**每轮收尾把 main 推上去**。此处不写具体 commit 哈希 —— 写了必然过时，看 `git log -1` 更可靠
- 端口：本地联调统一 **8360**（8352 被本机 SysCenter 占用）
- npm 源：`apps/mobile/.npmrc` 固定 `registry.npmmirror.com`
- pip 源：容器内 `PIP_INDEX_URL` 默认清华源（本机连宿主都解析不了 pypi.org）
- Python：3.13.12（managed venv）；Node：22.22.2（managed）
- 测试无需 `pip install -e`，`conftest.py` 已注入 5 个包路径
- 管理台令牌：本机 `.env` 已配 `XUANPAN_ADMIN_TOKEN`（`.env` 被 .gitignore 挡住，未入库）

---

## 7. 其它待办（非本次目标，但接手时可能遇到）

按性价比（详见 MEMORY.md「待办」与路线图 §4）：

0. ✅ **V2 断点已收尾**（§2.5，2026-09-18）：`/sensors` 页 + 曲线几何库 + 讲解文案同步
1. 🔴 **真机 UI 走查 —— 现在排第 1 位。** 唯一能证伪「前端 APP 能实战」的手段：
   键盘遮挡 / 「3 秒内确认」手感 / 真机字体与安全区，这些**只有真机能测**。
   但布局溢出、窄屏换行、配色观感已在 2026-09-18 用离线渲染核对过
   （§7.1 A 表 + `docs/ui-render/`）—— **走查时只需逐项过 B 表**，别重复做 A 表。
   顺带可补 `/adjust` 的讲解入口（§2.5 遗留）
2. **真实罗盘照片取证**（Gate 1 唯一卡点，需阿勇提供照片）：`real_photos/` + `labels.csv`，跑 `scripts/gate1_eval.py photos`
3. 修 R8 假阳性（识别山名错误 15/96）—— 先建假阳性回归基线，否则改完无法判断是否真变好
4. SKILL.md 打包（让仓库同时是 MCP Server + Agent Skill，可抄 suanming-mcp 的 Agent 入口）
5. 神煞吉凶分级（建议留给 AI 层，内核只给 FACT）
6. ~~建 remote 仓库~~ ✅ 已完成（2026-09-17，GitHub 私有库）
7. V2 全量验证后**重打 APK**（当前 dist 里的包不含 V2 罗盘域改版）

### 7.1 未验证项清单（走查时逐项过，别当成"已经验过了"）

离线能验的都已验（`tsc` 零错、`expo export` 出包并核到字节码字符串、接口契约、
端到端冒烟、`tests/mobile` 的一致性校验、多处变异验证）。

> 🔵 **2026-09-18 更新：这张表里一半以上已经能用「离线渲染」验掉了。**
> `scripts/ui_render/` 可把 expo web 产物按**精确手机视口**渲染成 PNG，并把实测数据
> （横向溢出量 / 全文 / 未捕获 JS 错误）回传出来。快照见 `docs/ui-render/`（**16 页**），
> 回归测试 `tests/mobile/test_ui_render.py`（设 `XP_WEB_DIST` 启用）。
> **它验的是同一套 React 组件树**，不是手绘示意图。
>
> 🔄 **刷新快照（2026-09-18 实测一次跑通，16 页全 OK / `exit=0`）**：
>
> ```bash
> cd apps/mobile && npx expo export --platform web --output-dir "$T/xp-web"   # $T = 系统 Temp
> "$PY" scripts/ui_render/preview_server.py "$T/xp-web" 8955 &
> XP_ADMIN_TOKEN=… "$NODE" scripts/ui_render/render_pages.mjs \
>   "C:/Program Files/Google/Chrome/Application/chrome.exe" docs/ui-render http://127.0.0.1:8955
> ```
> ⚠️ 导出**别加 `--clear`**（会被 safe-delete 拦）；产物目录也放系统 Temp 下。
> `11-admin` / `16-admin-config` 走绝对 URL 打到本机后端，需**先起 API**。

**A. 本轮已离线核对通过（除非改动对应页面，否则不必重复）**

| 项 | 实测证据 |
|---|---|
| 各页路由是否真的跳得过去 | **16 页**全部渲染出内容，`errors = []` |
| 各页布局是否横向溢出 | 全部 `overflowX = 0`（`scrollWidth == innerWidth`） |
| 六爻类别 chip、大运两列网格在窄屏是否换行得体 | 见 `08-divine.png` / `07-chart.png`，可直接肉眼核对 |
| V2 深色盘对比度、双轨配色并存观感 | `01-home / 02-adjust / 03-sensors.png` 对比 `07-chart.png` |
| V2 三张指标卡 / 三轴表在窄屏是否挤成两行 | `03-sensors.png`（且 `overflowX = 0`） |
| 「无数据」一等状态的实际呈现 | `03-sensors.png` 实测为**虚线空盘 + 说明文案**，确实没画盘面 |
| 黄历 / 择日长文案折行 | `05-almanac.png`（含干支、建除、28 宿、宜忌全字段） |
| **底栏改版新增 4 页**（测盘 / 分析 / 牌库 / 校准） | `12-test / 13-analysis / 14-templates / 15-calibrate.png`，均 `overflowX = 0`、`errors = []`。这 4 页**此前从未渲染过**（有页面没快照 = 白屏风险最高的地方），本轮补齐 |
| **管理台配置面板**（本轮新增） | `16-admin-config.png`。渲染器本轮新增「先点击再截图」能力，日志里 `clicked=clicked` 证明真点开了；面板正文 1346 字 vs 总览 347 字，`overflowX = 0`、`errors = []` |
| **管理台说明文案是否残留 Markdown 标记** | 静态检查与单测全绿，**只有 CDP 真渲染读 innerText 才发现裸星号**（已修 + 已加稳态守卫） |

**B. 仍需真机 —— 离线确实证不了**

| 项 | 为什么离线验不了 |
|---|---|
| `/sensors` 曲线在真机是否真有数据、静止时是否接近水平 | 浏览器与模拟器都没有磁力计，web 渲染**必然走空态分支** |
| 「3 秒内确认」的真实体感 | 只有真机能测 |
| 键盘弹起是否遮挡输入框 | 同上 |
| 真机字体度量与安全区差异 | web 无 safe-area inset，底部导航在真机上另有留白；字体渲染也不同 |
| 相机取景 / 相册选择是否真可用 | web 只验到权限分支（`04-scan.png` 停在「需要相机权限」） |

> 这些**不是"大概没问题"** —— 而是**确实没测**。接手做真机走查时按 **B 表**逐项过；
> A 表已核对过，除改动对应页面外不必重复。

---

## 8. 外部项目结论（勿重复调研）

- **suanming-mcp（玄机阁）**：已评估完毕，**术数计算层不可信**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画表缺字按 Unicode 静默编造），**不做依赖、不移植算法**。三处可借鉴：MCP 暴露层写法、SKILL.md 打包范式、水墨 HTML 渲染。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`。
