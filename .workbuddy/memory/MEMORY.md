# 玄盘AI · 项目长期记忆

> v2026-09-18（V2 罗盘域收尾）。接手顺序：`HANDOFF.md` → `AGENTS.md` → 本文件 → **`PITFALLS.md`**。
> **AI 无跨会话记忆，git 历史 + 记忆文件是唯一载体。** 本文件只放**规则**，状态类内容在 HANDOFF。
> **2026-09-18 重组**：环境/交付坑的**详版已拆到 `PITFALLS.md`**（原文件 26KB 超注入上限被截断）。
> 任务落在「跑测试 / 浏览器截图 / 改前端 / 刷新快照 / 清理目录 / 动后端」上时，**先读 PITFALLS.md 对应小节**。

## 基本盘

- **定位**：罗盘视觉识别 × 确定性术数计算 × AI 解释的移动端 APP。核心不是「AI 算命」，而是**把实体罗盘转成结构化数字数据**（勿与「龙息」A 股项目混淆）
- **原则**：AI 看 / 理解 / 解释；代码算 / 校验 / 映射。**计算层唯一真源，禁 LLM 介入**
- 仓库 `D:\WorkBuddy\玄盘AI`（main）；remote `ayongsheng777-rgb/xuanpan-ai`（私有，每轮收尾推）
- 权威：`AGENTS.md`（最高）＋ `docs/玄盘 AI — 产品基线规范.md`（**唯一真源 SSOT**，冲突以它为准；它未覆盖的**先问，别自行择一**）

## 技术栈（照实现写，别照报告写）

| 层 | 实际 |
|---|---|
| 移动端 | RN + Expo（expo-router SDK 52）`apps/mobile`（页面+组件 ≈10.6k 行） |
| 后端 | FastAPI + uvicorn `services/api`；管理台 `/admin` |
| 内核 | `packages/fortune-core`；历法 `lunar-python`（`sxtwl` Py3.13 无 wheel，已弃） |
| **存储** | **SQLite 单文件**。报告列的 PG / Redis / S3 只是 `[推测]`，**代码里无任何 Redis/S3 调用**，别照它写编排 |
| 识别 | 本地 CV（零成本）默认；云端 opt-in |
| 部署 | docker compose 单 service，宿主 8360 → 容器 8352 |

🔴 **领域数据表在 `packages/fortune-core/data/`**；根 `data/` 只装运行时产物。

## 铁律（`AGENTS.md`）

1. **每次改动 = 单独 commit**，一 commit 一逻辑单元；**禁 `git add -A`**
2. **每次改动同步测试、交付前全绿**，附**实际命令 + 真实输出**；未运行不得声称「测试通过」

约定：`<type>(<scope>): <中文简述>`；结论标 `[已确认]`/`[推测]`/`[待验证]`；交付四段（完成 / 修改文件 / 验证 / 剩余）；引新依赖先说明成本。

## 环境快查（详版见 `PITFALLS.md`）

- 端口统一 **8360**（8352 被 SysCenter 占）；npm 走 `registry.npmmirror.com`；容器 pip 走清华源（本机解析不了 pypi.org）
- 本机有系统代理，**连本机服务必须 `trust_env=False`**
- `$PY` = `C:/Users/anyong/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
- `$T` = `tempfile.gettempdir()`；**pytest `--basetemp` / expo export 产物都必须放 `$T` 下**
- 🔴 高频五坑：`--basetemp` 落非 Temp → 大批 ERROR｜`expo export --clear` 被 safe-delete 拦｜`output-dir /tmp/x` 落在 `D:\tmp`｜Chrome 截图要用 CDP 设视口｜CDP 脚本结束必须 `process.exit()`

## 材料与裁定

- 🔴 **演示图：配色已采纳（像素实测），但术数数据不可采信** —— 实算已证其八字「日柱 / 时柱 / 日主」三项错误
- 🔴 **V2 的 8 屏演示图不在仓库里** —— 照「第 N 屏」做页面前先读 `docs/玄盘 AI — V2 评估与实施路线.md`；缺细节问阿勇，**别自己编一屏**
- **已裁决 5 项（不得擅改）**：底部导航 **5 栏**（罗盘/命盘/占测/历史/我的）｜AI 报告**三标签**（盘面事实/传统分析/AI 解读）｜**配色取演示图**｜相机**双入口**（拍照+相册同管线）｜隐私表述**「数据可外流」**（承认照片出端，已全仓核查）
- Token：`primary #013A6C`｜`gold #DAB37D`｜`sand #E5D7C7`｜`jade #3C7066`｜`cinnabar #B93E35`；V2 `instrument` 深色域（**仅测量相关页**）`bg #0A1626` / `surface #12223A` / `needle #E05548`
- 🔴 **改 UI 前必读**：配色与导航是 SSOT 已裁定的，**不在「重新设计」的自由度里**；能改的是排版/间距/层级/状态/动效/图标/信息密度

## 界面工艺规则（2026-09-18 用 ui-skills 重做后固化）

详细诊断与逐页像素差异见 `2026-09-18.md` 末节。**这些是"看着不丑、但说不上哪里不对"的来源，且都不会让测试失败**。

🔴 **同一容器内，标题的字号不得小于正文，颜色不得比正文更淡** —— 改任何卡片/分区标题时；因为 `SectionTitle` 曾是 `sm 13 + textSecondary`，比自己管的正文（`md 15 + text`）**更小更淡**，19 页全中却零测试失败。层级倒挂是这类问题的典型
🔴 **三个表面原语，别再多造第四个** —— 加新页面时；`Card`（浅色纸面）/ `Panel`（**深色仪器**）/ `PressableCard`·`PressablePanel`（整卡可点）。深色页**不许**手写「surface 底 + 1px 边框 + `radius.lg` + padding」——那组样式曾被 6 个页各抄一遍（重复 17 次），而**散落样式组合不会触发任何检查**
🔴 **深色域不用投影** —— 做深色页时；深底上的投影看不见、只让边缘发脏。深色层级靠「底差 + 1px 描边」。**这正是深色页无法复用浅色 `Card` 的真正原因，不只是色值不同**
🔴 **按压反馈只从 `interaction` 取值，实现只有 `usePressScale`** —— 加任何可点元素时；因为此前五种写法并存（`opacity .86` / 换底色 / `opacity .7` / **两处完全没有**），同一手势不同回应会被读成"有的地方坏了"，而它**不会在任何测试里失败**。`scale` 而非换底色：缩放会把文字和图标一起带走
🔴 **不引 `react-native-reanimated`** —— 想做动效时；它在 package.json 里不存在，引它要动 babel + 新架构开关。`transform` 走 core `Animated` 的 `useNativeDriver` 已够 120ms 按压反馈。真要弹簧物理，只改 `usePressScale.ts`
🔴 **一屏一个 `Metric` 读数** —— 放仪表读数时；`Metric`（40px/heavy/负字距/等宽数字）是主角档，同页第二个读数降一档（磁场强度降到 `xl 20`）。原先把 `display 32` 兼职读数，与 `xxl 26` 只差 1.23 倍，区分不出主角配角
🔴 **凡数值原地变化处一律等宽数字**（`AppText numeric` 或 `Metric`）—— 写读数时；比例数字下 "1" 比 "8" 窄，读数一跳整行长度就跳；传感器每秒刷数次，抖会被读成"界面在闪"
🔴 **不内嵌中文字体** —— 想"换字体提升质感"时；中文字体文件 5–10 MB，会让 APK 体积翻几倍，而苹方/思源黑体本身已是高质量中文字体。功夫花在**阶梯与字距**上（中文没有大小写，层级只能靠"字号 × 字重 × 字距"三件套）
🔴 **图标语义不许撞脸、不许用 AI 陈词** —— 动底栏/图标时；「分析」原用 `sparkles`（✨＝"这是 AI 生成的"通用符号），但那个 tab 装的是**确定性术式**，误导且削弱"计算层是真源"的核心承诺（现用 `shapes`）；`compass`(罗盘) 与 `locate`(测盘) 原来都是"圆+十字"，5 栏里两栏分不出（测盘现用 `scan`）
🔴 **改 UI 后必须重渲染快照 + 在导出包分卷里登记新文件** —— 加/删 `app/`、`src/` 下任何源码时；`scripts/export_ui_design.py` 的 `VOLUMES` 是**逐文件白名单**，漏登记会被归档完整性自检拦下（本轮新增 `usePressScale.ts` 即被抓到）。另：`docs/玄盘 AI — UI 设计导出导读.md` 是包的门面，改设计系统/信息架构要同步

- 🔴 **一致性疑点（未裁定，保持原样）**：`15-calibrate`（深色页）仍用**浅色 `Card`**（白卡浮在近黑底上）—— 当时无深色原语。观感尚可但与同域另外五页不一致。SSOT 未覆盖 → **等阿勇裁定**，别自行改

## 现状（细节见 `HANDOFF.md`）

- **V2 本轮范围已完成**（9 commit；基线 tag `v0.1.0-pre-v2` 可回滚）。**V2 不做**：导航不动、**不做全局深色化**（双轨：罗盘域深色、其余浅色待真机走查后定）、Phase 3+ 暂缓 —— **别越界**
- **2026-09-18 增量**：AI 解读拆**双文体**（专业分析 / 白话讲解，报告页可切换）｜**运行时可调配置**（`runtime_config.py` + SQLite `app_settings`）｜管理台新增**「配置」面板**（含模型列表探针）｜全量测试 **1560 passed, 3 skipped, EXIT=0**（单进程 250.73s）｜UI 快照补齐到 **19 页**（此前主链路是断的）｜**UI 设计导出包**可一键生成
- 术数：六爻装卦、八字大运/流年/神煞/长生十二宫、黄历/择日、断卦层、**择日决策**、**三式全部**（全链路贯通）
- MCP 12 工具；HTTP `/api/v1/{almanac,zeri,duan,qimen,liuren,taiyi}`；管理台 **4 个导航页**（概览/会话/配置/调试台）
- 康熙笔画 20794 字 `verified:true`；APK 含三式但**不含 V2**，**debug 签名**，对外分发须换正式签名
- 🔴 **真机 UI 走查仍未做**（7 个新界面）→ 最高优先级，逐项清单见 HANDOFF §7.1

## 运行时配置层（改配置相关需求前必读）

`services/api/xuanpan_api/runtime_config.py` —— **环境变量给默认，管理台覆盖，改完即时生效**。

- **优先级**：管理台覆盖 > 环境变量 > 代码默认值。每项都报 `source`，界面显示来源。
  🔴 **来源列不能省** —— 没有它，「改了 .env 却没变化」无法自证，排查方向从第一步就错
- 🔴 **两种配置并存，别合并**：`get_settings`（环境基线）与 `get_active_settings`（叠加覆盖）。只剩生效值→回答不了"清掉覆盖会变回什么"；只剩基线→业务路径读不到覆盖
- 🔴 **请求期读配置一律用 `get_active_settings`**，用 `get_settings` 会让后台改动不生效
- 🔴 **AI 路由器按配置指纹缓存**（`RuntimeConfig.ai_router`），指纹变了才重建。改回"启动时构造一次" = 改模型要重启，接口 200 但行为不变
- 🔴 **密钥明文只有一个出口**：`RuntimeConfig.llm()`，唯一调用点是构造 AI provider。展示层走 `entries()`，只给「已配置 + 掩码 + 长度」，**密钥项压根不带 `value` 字段**。新增密钥类配置**必须**加进 `SECRET_KEYS`（有测试守 `SECRET_KEYS ≡ SPECS`）
- `admin_token` **不可从界面改**；`cors_origins` 标「需重启服务」
- 新增一个环境变量要看 **4 处**：`config.py`、`runtime_config.SPECS`、`.env.example`、`docker-compose.yml`
- `XUANPAN_LLM_CAPABILITY` 只有 `reasoning/fast/local`。🔴 写别的不报错，只**静默落到默认档**（`.env.example` 曾错写 `vision`，已修）

## UI 设计导出包（供外部智能体分析）

`"$PY" scripts/export_ui_design.py --zip` → `dist/ui-design-export/` ＋ `dist/玄盘AI-UI设计导出-<日期>.zip`。**产物在 `dist/`（gitignore）不入库，脚本入库**。包 = 导读 README ＋ 9 卷源码（**按用户旅程分卷**）＋ 19 张快照 ＋ 源码副本 ＋ 3 份上游规范 ＋ MANIFEST（SHA256/12）。

- 🔴 **脚本的核心理由是归档完整性自检**：`app/` 与 `src/` 下有源码未被任何一卷收录就报错退出。这道自检立刻抓到真实遗漏（命盘页在 `app/chart.tsx`，不是 `(tabs)/`）—— 没它包会**静默少掉整页**。**改 UI 后忘了重导 = 包与源码漂移**；守卫 `tests/test_export_ui_design.py`
- 🔴 **输出目录已存在时默认报错、不自动清除**（要 `--force`）—— 一次 rmtree 近百文件会撞 safe-delete。挪旧包用**同盘 rename**
- 🔴 **深色仪器域的边界**：**6 个测量相关页**（首页 / 测盘 / 手动调节 / 传感器测量 / 罗盘校准 / 我的罗盘）为深色，其余浅色。**分界线是「是不是在测量」，不是「是不是罗盘」** —— 确认页用**浅色盘**（`DIAL_LIGHT`），别按「罗盘域 = 深色」推断（此结论由 `17-confirm.png` 当场证伪初稿）
- 🔴 **导读 `docs/玄盘 AI — UI 设计导出导读.md` 是导出包的门面**，改设计系统/信息架构要同步更新
- 底栏实际是「罗盘/测盘/分析/历史/我的」，与 SSOT 裁定的「罗盘/命盘/占测/历史/我的」不一致（V2 改版，理由见 `(tabs)/_layout.tsx` 注释）；`apps/mobile/README.md` 目录结构章节**仍是旧结构**

## 风险与待办

- **R1**：罗盘识别可行性 = 全项目根基风险
- **R8 🔴 假阳性**：给出山名候选但山名错（实测 15/96）。**与「识别不出」性质完全不同** —— 用户看到的是看似正常的错误坐向、不会去重拍。**唯一防线 `needs_user_confirmation`（RULE-004），不得为降低确认率而移除**
- R9 已修复（贴边判据 → 几何判据，命中率 63.7% → 80.0%）
- 待办序：① **真机走查**（唯一能证伪「APP 能实战」；tsc/export 证不了溢出/换行/键盘/体感）② 真实照片取证（Gate 1 唯一卡点，需阿勇给图）③ 修 R8 **前先建假阳性基线**（15/96）④ 重打 APK ⑤ SKILL.md 打包 ⑥ `/adjust` 补讲解入口

## 术数落地要点（避免重复造轮子）

- 🔴 **lunar-python 无神煞接口**（`getXxxShiShen` 是「十神」不是「神煞」）→ 18 张口诀表只能自建（`bazi/shensha.py`）。**但下列全是现成接口，别自造**：长生十二宫 `getXxxDiShi`、身宫 `getShenGong`、胎息 `getTaiXi`、黄历全套（建除 `getZhiXing` / 宿 `getXiu` / 黄黑道 `getDayTianShen` / 宜忌 `getDayYi`+`getDayJi` / 冲煞 / 彭祖百忌）、大运 `getYun`
- 大运 `getYun` 第 0 步是「起运前」空档，流年从 index 1 起；顺逆看**年干**阴阳。建除 `JIANCHU_12[(日支序−月支序)%12]`，交节日有月支口径差需标注
- 三式 HTTP 动词各异是领域术语（`/qimen/pan`、`/liuren/cast`、`/taiyi/cast`）—— **别为"统一"改路径**（破坏契约）
- 太乙只做**年局**，月/日/时局未实现（显式列在 `uncertainties`，**别当遗漏去补**）；太乙宫号与洛书**逐宫错位**，刻意不复用奇门九宫表
- **神煞吉凶分级不做** —— 留给 AI 层，内核只给 FACT
- 择日：规则表 `data/zeri_events.json`（17 事件 + schools）可整体替换（RULE-006），**与 `schools.py` 的风水流派是两套体系**（故意不共用）
  🔴 **改事件词必须跑 `scripts/verify_zeri_table.py --check-veto`** —— 词目写错**不报错、只静默失效**，筛选看似正常却少一道否决
  🔴 **别把「忌行丧 / 忌分居」加进嫁娶否决** —— 实测误杀 **14%** 婚嫁吉日。**教训：设计 veto 前先量化它影响多少天，别凭语义直觉**
  **加事件后必须同步 MCP 工具 docstring**（`tests/test_mcp_server.py` 有防漂移守卫）

## 外部项目（勿重复调研）

**suanming-mcp（玄机阁）** <https://github.com/Enoch666/suanming-mcp> commit `f08ec272` —— **已评估：术数计算层不可信，不做依赖、不移植算法**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画缺字按 Unicode 码位静默编造）。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`，复算脚本 `scripts/cmp_suanming_mcp.py`。**可借鉴**：MCP 暴露层写法、`SKILL.md` 打包范式、水墨 HTML 渲染。**它揭示的行业缺口**：开源项目全都停在「排盘/起卦」，**装卦层与三式全空** —— 这正是玄盘最该吃下的差异点。

## 数据缺口

- ✅ `data/kangxi_strokes.json` 已 20794 字 `verified:true`；缺字抛 `DomainDataMissingError`（**不静默取错值**）
- `fenjin120` 规则表缺失（管理台 `available=false`）—— 退化为「只输出几何格位 + 警告」
