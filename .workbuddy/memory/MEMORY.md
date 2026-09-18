# 玄盘AI · 项目长期记忆（规则索引）

> v2026-09-18c。接手顺序：`HANDOFF.md`（状态）→ `AGENTS.md`（规范）→ 本文件（**规则索引**）→ `PITFALLS.md`（**根因详版**）。
> **AI 无跨会话记忆，git 历史 + 记忆文件是唯一载体。** 本文件只写「必须做什么」，**为什么 + 复现步骤一律在 `PITFALLS.md`**。
> 🔴 **本文件受注入长度限制**：一旦某节把文件顶到被截断，就把它的详版拆去 `PITFALLS.md`，这里只留一行索引。
> `PITFALLS.md` 小节：§1 工具链 §2 假绿 §3 Expo §4 CDP §5 快照 §6 前端 §7 后端/管理台 §8 界面工艺 §9 运行时配置 §10 UI 导出包 §11 术数落地。

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

## 环境快查（详版 PITFALLS §1–§5）

- 端口统一 **8360**（8352 被 SysCenter 占）；npm 走 `registry.npmmirror.com`；容器 pip 走清华源（本机解析不了 pypi.org）
- 本机有系统代理，**连本机服务必须 `trust_env=False`**
- `$PY` = `C:/Users/anyong/.workbuddy/binaries/python/envs/default/Scripts/python.exe`；`$NODE` = `.../node/versions/22.22.2-3/node.exe`
- `$T` = `tempfile.gettempdir()`；**pytest `--basetemp` / expo export 产物都必须放 `$T` 下**
- 🔴 高频五坑：`--basetemp` 落非 Temp → 大批 ERROR｜`expo export --clear` 被 safe-delete 拦｜`output-dir /tmp/x` 落在 `D:\tmp`｜Chrome 截图要用 CDP 设视口｜CDP 脚本结束必须 `process.exit()`

## 材料与裁定

- 🔴 **演示图：配色已采纳（像素实测），但术数数据不可采信** —— 实算已证其八字「日柱 / 时柱 / 日主」三项错误
- 🔴 **V2 的 8 屏演示图不在仓库里** —— 照「第 N 屏」做页面前先读 `docs/玄盘 AI — V2 评估与实施路线.md`；缺细节问阿勇，**别自己编一屏**
- **已裁决 5 项（不得擅改）**：底部导航 **5 栏**（罗盘/命盘/占测/历史/我的）｜AI 报告**三标签**（盘面事实/传统分析/AI 解读）｜**配色取演示图**｜相机**双入口**（拍照+相册同管线）｜隐私表述**「数据可外流」**（承认照片出端，已全仓核查）
- Token：`primary #013A6C`｜`gold #DAB37D`｜`sand #E5D7C7`｜`jade #3C7066`｜`cinnabar #B93E35`；V2 `instrument` 深色域（**仅测量相关页**）`bg #0A1626` / `surface #12223A` / `needle #E05548`
- 🔴 **改 UI 前必读**：配色与导航是 SSOT 已裁定的，**不在「重新设计」的自由度里**；能改的是排版/间距/层级/状态/动效/图标/信息密度

## 界面工艺规则（索引 —— 详版 PITFALLS §8）

这一类问题的共同点：**看着不丑、但说不上哪里不对，且不会让任何测试失败**（不是假绿，是**根本没测**）。

🔴 **标题不得比它管的正文更小更淡**（层级倒挂）｜改任何卡片/分区标题时
🔴 **表面原语只有三个**：`Card`(浅)/`Panel`(深仪器)/`Pressable*`；**别手写第四个**｜加页面时
🔴 **深色域不用投影**，层级靠「底差 + 1px 描边」｜做深色页时
🔴 **按压反馈只有 `usePressScale`**，从 `interaction` 取；用 `scale` 不换底色｜加可点元素时
🔴 **不引 `react-native-reanimated`**（不在依赖里，要动 babel+新架构）｜想做动效时
🔴 **一屏一个 `Metric` 读数**，第二个降一档｜放仪表读数时
🔴 **凡原地变化的数值一律等宽数字**（`tabular-nums`）｜写读数时
🔴 **不内嵌中文字体**（5–10MB，APK 翻几倍）；功夫花在字号×字重×字距｜想"提升质感"时
🔴 **图标语义不许撞脸、不许用 AI 陈词**（`sparkles`→`shapes`；`locate`→`scan`）｜动底栏/图标时
🔴 **改 UI / 改文案后必须重渲染快照 + 登记导出包分卷白名单**｜改 `app/`、`src/` 下任何文件时
🔴 **管理台快照拍的是容器镜像里的那份页面** → 改完 `admin.html` 必须先 `docker compose up -d --build`，否则拍到**旧界面而诊断全绿**；判据是 `curl :8360/admin` 与磁盘文件比 sha256（详版 PITFALLS §5）｜刷新管理台快照时
🔴 **界面文案必须是纯文本，不得出现 Markdown 标记**（`**x**` 会原样显示星号，且零测试会失败）｜写任何会渲染的字符串时。守卫 `tests/mobile/test_ui_copy_plain_text.py`；管理台侧缺口由 `tests/api/test_admin_page_wiring.py::TestStaticCopy` 补

**管理台专项**：CSS 变量层 / HTML 结构 / JS **三块一起改**；文字只做三级（第四级裁掉）；禁用态用中性灰不 `opacity`；焦点环用主色 outline（金 on 白仅 1.96:1）；`role=tablist/tab/tabpanel` + **roving tabindex** 手写。

## 详版指针（这几块内容较厚，已整体移到 PITFALLS，动手前先读）

- **运行时配置层**（`runtime_config.py`，改任何配置相关需求前必读）→ **PITFALLS §9**
  摘要：优先级「管理台覆盖 > 环境变量 > 默认值」，每项报 `source`（来源列不能省）｜`get_settings`(基线) 与 `get_active_settings`(叠加) **并存别合并**，请求期一律用后者｜AI 路由器按**配置指纹**缓存｜密钥明文**唯一出口** `RuntimeConfig.llm()`，展示走 `entries()`，新增密钥必须进 `SECRET_KEYS`｜新增环境变量看 **4 处**
- **UI 设计导出包**（`scripts/export_ui_design.py --zip`）→ **PITFALLS §10**
  摘要：产物在 `dist/` 不入库、脚本入库｜**核心理由是归档完整性自检**（`app/`+`src/` 有源码未入卷就报错退出）｜输出目录已存在默认报错要 `--force`｜**深色域边界＝「是不是在测量」**（6 页，确认页是浅色盘）｜导读是门面要同步
- **术数落地要点**（避免重复造轮子）→ **PITFALLS §11**
  摘要：lunar-python **无神煞接口**，但长生十二宫/身宫/胎息/黄历全套/大运**全是现成接口**｜三式 HTTP 动词各异是领域术语**别统一**｜太乙只做年局、宫号与洛书逐宫错位（**别当遗漏补**）｜神煞吉凶分级不做｜择日改事件词必须跑 `verify_zeri_table.py --check-veto`；**别把「忌行丧/忌分居」加进嫁娶否决**（实测误杀 14%）

## 现状（细节见 `HANDOFF.md`）

- **V2 本轮范围已完成**（基线 tag `v0.1.0-pre-v2` 可回滚）。**V2 不做**：导航不动、**不做全局深色化**（双轨）、Phase 3+ 暂缓 —— **别越界**
- **2026-09-18 增量**：AI 解读拆**双文体**（专业分析 / 白话讲解）｜**运行时可调配置** + 管理台「配置」面板（含模型列表探针）｜全量测试 **1560 passed, 3 skipped, EXIT=0**｜UI 快照 **21 张**（19 页 App ＋ 管理台 4 视图，含此前从未拍过的「能力调试台」）｜管理台 HTML 工艺重做（49 token / 焦点可见性 / 层级 / roving tabindex）＋静态文案守卫｜**UI 设计导出包** 100 文件一键生成｜改前后对照脚本 `scripts/ui_render/make_compare.py`
- 术数：六爻装卦、八字大运/流年/神煞/长生十二宫、黄历/择日、断卦层、**择日决策**、**三式全部**（全链路贯通）
- MCP 12 工具；HTTP `/api/v1/{almanac,zeri,duan,qimen,liuren,taiyi}`；管理台 **4 个导航页**（概览/会话/配置/调试台）
- APK：`dist/玄盘AI-v0.1.0-v2-ui.apk`（98.6 MB，含 V2 + 本轮界面工艺修复）；**debug 签名**，对外分发须换正式签名
- 🔴 **真机 UI 走查仍未做**（7 个新界面）→ 最高优先级，逐项清单见 HANDOFF §7.1

## 风险与待办

- **R1**：罗盘识别可行性 = 全项目根基风险
- **R8 🔴 假阳性**：给出山名候选但山名错（实测 15/96）。**与「识别不出」性质完全不同** —— 用户看到的是看似正常的错误坐向、不会去重拍。**唯一防线 `needs_user_confirmation`（RULE-004），不得为降低确认率而移除**
- R9 已修复（贴边判据 → 几何判据，命中率 63.7% → 80.0%）
- 待办序：① **真机走查**（唯一能证伪「APP 能实战」；tsc/export 证不了溢出/换行/键盘/体感）② 真实照片取证（Gate 1 唯一卡点，需阿勇给图）③ 修 R8 **前先建假阳性基线**（15/96）④ 重打 APK ⑤ SKILL.md 打包 ⑥ `/adjust` 补讲解入口
- **待阿勇拍板**（详 `HANDOFF.md` §7.0）：① `15-calibrate` 浅色 `Card` 要不要改深色 `Panel` ② 底栏名（文档「命盘/占测」vs APP「测盘/分析」）③ 深色仪器风要不要铺全站 ④ 去标记后的强调要不要改成真加粗 ⑤ APK 是否换正式签名、可疑权限（RECORD_AUDIO/SYSTEM_ALERT_WINDOW 等）要不要收

## 外部项目（勿重复调研）

**suanming-mcp（玄机阁）** <https://github.com/Enoch666/suanming-mcp> commit `f08ec272` —— **已评估：术数计算层不可信，不做依赖、不移植算法**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画缺字按 Unicode 码位静默编造）。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`，复算脚本 `scripts/cmp_suanming_mcp.py`。**可借鉴**：MCP 暴露层写法、`SKILL.md` 打包范式、水墨 HTML 渲染。**它揭示的行业缺口**：开源项目全都停在「排盘/起卦」，**装卦层与三式全空** —— 这正是玄盘最该吃下的差异点。

## 数据缺口

- ✅ `data/kangxi_strokes.json` 已 20794 字 `verified:true`；缺字抛 `DomainDataMissingError`（**不静默取错值**）
- `fenjin120` 规则表缺失（管理台 `available=false`）—— 退化为「只输出几何格位 + 警告」
