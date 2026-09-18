# 玄盘AI · 项目长期记忆

> v2026-09-18（V2 罗盘域收尾）。接手顺序：`HANDOFF.md` → `AGENTS.md` → 本文件。
> **AI 无跨会话记忆，git 历史 + 记忆文件是唯一载体。** 本文件只放**规则**，状态类内容在 HANDOFF。

## 基本盘

- **定位**：罗盘视觉识别 × 确定性术数计算 × AI 解释的移动端 APP。核心不是「AI 算命」，而是**把实体罗盘转成结构化数字数据**（勿与「龙息」A 股项目混淆）
- **原则**：AI 看 / 理解 / 解释；代码算 / 校验 / 映射。**计算层唯一真源，禁 LLM 介入**
- 仓库 `D:\WorkBuddy\玄盘AI`（main）；remote `ayongsheng777-rgb/xuanpan-ai`（私有，每轮收尾推）
- 权威：`AGENTS.md`（最高）＋ `docs/玄盘 AI — 产品基线规范.md`（**唯一真源 SSOT**，冲突以它为准；它未覆盖的**先问，别自行择一**）

## 技术栈（照实现写，别照报告写）

| 层 | 实际 |
|---|---|
| 移动端 | RN + Expo（expo-router SDK 52）`apps/mobile` |
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

## 环境与工具坑（🔴 = 会导出错误结论的）

- 端口统一 **8360**（8352 被 SysCenter 占）；npm 走 `registry.npmmirror.com`；容器 pip 走清华源（本机解析不了 pypi.org）
- 本机有系统代理，**连本机服务必须 `trust_env=False`**

🔴 **`expo export --output-dir /tmp/x` 落在「当前盘符」的 `\tmp\x`** —— 核验打包产物时；因为 Node 按 Windows 路径解析，cwd 在 D 盘就是 `D:\tmp\`（**不是** Git Bash 的 `/tmp`，也不是 `C:\tmp`）。随后 `cd /tmp/x` 报 No such file → 会**误判成"打包失败"**。
🔴 **`.hbc` 里的中文串是 UTF-16LE** —— 想证明「页面真进了包」时；用 utf-8 grep 得 **0 命中（假阴性）**。用 `bytes.count(s.encode('utf-16-le'))`，并**带一个旧页面的串做对照组**自证探测方法有效。
🔴 **`Path.write_text()` 在 Windows 把 LF 转 CRLF** —— 做「读-改-写」还原文件时；用 `read_bytes`/`write_bytes` 才字节级还原。
🔴 **md5 比对可能什么都证明不了** —— 做「改坏→还原→md5」时；两边求值对象可能**都是已改坏的**（实测 DuanCard 第 66 行仍留坏代码、md5 却报一致）。**必须用 grep 关键片段做内容断言**。
🔴 **pytest 的 `--basetemp` 必须落在系统 Temp 下** —— 跑全量/大批量用例时；因为 WorkBuddy safe-delete 只豁免 `tempfile.gettempdir()` 之下（及 pip 临时目录）的路径（shim `_should_bypass_safe_delete`），其余路径每删一个文件/目录都先问批量守卫，**同一次工具调用内累计删除 > 50** 即 `raise SystemExit(1)`（JSON 里 `scope:"turn"`）→ 落在 fixture teardown 就是**大批 ERROR**。同一份代码三种跑法实测：`--basetemp=D:/tmp/...` → 970 passed 后首个 fixture ERROR 即停（全量口径 **1469 passed + 87 errors**、exit=1）｜`--basetemp="$T/xxx"`（`$T` = `tempfile.gettempdir()`）→ **1560 passed, 2 skipped, exit=0**｜不带 basetemp → 用例全过（100%、无 `F`/`E`）但收尾删 `pytest-of-*/garbage-*` 被拦（`count:175`）→ **汇总行丢失、exit=1**。⚠️ **旧规则「用 D:/tmp 绕开 safe-delete」方向是反的**（把"丢一行"升级成"87 个 ERROR"）。判据仍是**有没有 `F`/`E` + 那行 JSON**；也别重复传 `-q`（addopts 已含，再传吞掉汇总行）
🔴 **非沙箱工具调用里批量守卫不计数** —— 想用微探针直接验证 safe-delete 判据时；实测在非沙箱调用中删 120 个**非 Temp** 文件也不被拦（阳性对照失效），会误导出"豁免范围很大"的错误结论。探针必须先自检 shim 真被 patch（`os.unlink.__module__ == "sitecustomize"`、`os.unlink.__name__ == "_safe_remove"`），且**整段对照实验都要在沙箱内**跑；否则只能拿"真实全量跑"的结果当证据
🔴 **刷新 UI 快照要三件套，顺序不能变** —— 改过前端页面后核对视觉时；`cd apps/mobile && npx expo export --platform web --output-dir "$T/xp-web"`（**不加 `--clear`**，会被 safe-delete 拦；产物放系统 Temp）→ 起 `scripts/ui_render/preview_server.py <dist> <port>` → 跑 `render_pages.mjs <chrome> docs/ui-render http://127.0.0.1:<port>`（不传第 4 个参数才是全量 16 页）。`16-admin-config` 靠页面清单第 6 个元素「点击选择器」进懒渲染的配置视图，日志里 `clicked=clicked` 才是「面板真被点开」的证据——没有它，拍到的是没点成功的初始页
🔴 **全量 >190s 超 Bash 默认 120s 前台超时** —— 会被截断且**无任何输出**（易误判成崩溃）。用 `run_in_background` 或分模块跑。
🔴 **`.workbuddy/` 是项目数据，非缓存，不得删除。**

🔴 **Chrome 在沙箱内/受限 shell 下静默 exit 0** —— 跑无头浏览器（截图/PDF/自动化）时；表现是**退出码 0、零输出、零产物**，极易误判成"参数写错了"。必须沙箱外执行，`--no-sandbox` 救不了（实测）。
🔴 **`chrome --headless --screenshot --window-size=390,844` 在本机不生效** —— 做"手机尺寸截图"时；实测页面 `innerWidth=500`，截出的 390px 图是把 500px 布局**裁掉右边**，看着像横向溢出、实为假象。要用 CDP 的 `Emulation.setDeviceMetricsOverride`。
🔴 **同一轮批量截图不要每页重启 Chrome** —— 批量任务；实例间互相干扰，实测**第二页起永久挂起**（20 分钟只出一页、无任何报错）。改为启动一次 Chrome + 每页独立 target。
🔴 **CDP/WebSocket 脚本结束必须 `process.exit()`** —— 写 Node 浏览器自动化时；不关 WebSocket 会让事件循环一直存活 → 进程永不退出 → 调用方（pytest/shell）跟着挂死（实测卡过 14 分钟）。杀 Chrome 要用 `spawnSync('taskkill',['/F','/T','/PID',pid])`，`spawn` 异步派发不够。
🔴 **`expo export --clear` 会被 `[safe-delete]` 拦** —— 重新导出产物时；报 `checkBulkDeleteGuard`（大批量删除保护），与吞 pytest 汇总行同一机制。改成输出到**新目录**、不加 `--clear`。

## 材料与裁定

- 🔴 **演示图：配色已采纳（像素实测），但术数数据不可采信** —— 实算已证其八字「日柱 / 时柱 / 日主」三项错误
- 🔴 **V2 的 8 屏演示图不在仓库里** —— 照「第 N 屏」做页面前先读 `docs/玄盘 AI — V2 评估与实施路线.md`；缺细节问阿勇，**别自己编一屏**
- 已裁决 5 项：底部导航 **5 栏**（罗盘/命盘/占测/历史/我的）｜AI 报告**三标签**（盘面事实/传统分析/AI 解读）｜配色取演示图｜相机**双入口**（拍照+相册同管线）｜隐私表述**「数据可外流」**（承认照片出端，已全仓核查）
- Token：`primary #013A6C`｜`gold #DAB37D`｜`sand #E5D7C7`｜`jade #3C7066`｜`cinnabar #B93E35`；V2 `instrument` 深色域（**仅罗盘域**）`bg #0A1626` / `surface #12223A` / `needle #E05548`

## 现状（细节见 `HANDOFF.md`）

- **V2 本轮范围已完成**（9 commit；基线 tag `v0.1.0-pre-v2` 可回滚）。**V2 不做**：导航不动、**不做全局深色化**（双轨：罗盘域深色、其余浅色待真机走查后定）、Phase 3+ 暂缓 —— **别越界**
- **2026-09-18 增量（回应「webui 后台没什么变革」）**：
  - AI 解读拆成**双文体**（专业分析 / 白话讲解），报告页可切换
  - **运行时可调配置**（后端 `runtime_config.py` + SQLite `app_settings` 表）
  - **管理台新增「配置」面板**（含 AI 模型选择与模型列表探针）
  - 全量测试 **1560 passed, 2 skipped**（单进程全量；`--basetemp` 放系统 Temp 才拿得到汇总行，见上方 safe-delete 条）
  - UI 快照补齐到 **16 页**：底栏改版新增的 4 页（测盘/分析/牌库/校准）**此前从未渲染过**，本轮首次核对 —— 全部 `overflowX=0`、`errors=[]`；管理台配置面板一并纳入
- 术数：六爻装卦、八字大运/流年/神煞/长生十二宫、黄历/择日、断卦层、**择日决策**、**三式全部**（全链路贯通）
- MCP 12 工具；HTTP `/api/v1/{almanac,zeri,duan,qimen,liuren,taiyi}`；管理台 **4 个导航页**（概览/会话/配置/调试台）
- 康熙笔画 20794 字 `verified:true`；APK 含三式但**不含 V2**（V2 验证后重打），**debug 签名**，对外分发须换正式签名
- 🔴 **真机 UI 走查仍未做**（V2 新增 3 页 + 底栏改版新增 4 页 = 7 个新界面，离线渲染已核对布局那部分）→ 最高优先级，逐项清单见 HANDOFF §7.1

## 运行时配置层（新增，改配置相关需求前必读）

`services/api/xuanpan_api/runtime_config.py` —— **环境变量给默认，管理台覆盖，改完即时生效**。

- **优先级**：管理台覆盖 > 环境变量 > 代码默认值。每项都报 `source`，界面显示来源。
  🔴 **来源列不能省** —— 没有它，「改了 .env 却没变化」无法自证，排查方向从第一步就错
- 🔴 **两种配置并存，别合并**：`get_settings`（环境基线）与 `get_active_settings`（叠加覆盖）。
  只剩生效值 → 回答不了"清掉覆盖会变回什么"；只剩基线 → 业务路径读不到覆盖
- 🔴 **请求期读配置一律用 `get_active_settings`**，用 `get_settings` 会让后台改动不生效
- 🔴 **AI 路由器按配置指纹缓存**（`RuntimeConfig.ai_router`），指纹变了才重建。
  改回"启动时构造一次挂 `app.state.ai_router`" = 改模型要重启，接口 200 但行为不变
- 🔴 **密钥明文只有一个出口**：`RuntimeConfig.llm()` 的返回值，唯一调用点是构造 AI provider。
  展示层走 `entries()`，只给「已配置 + 掩码 + 长度」，**密钥项压根不带 `value` 字段**。
  新增密钥类配置**必须**加进 `SECRET_KEYS`（有测试守 `SECRET_KEYS ≡ SPECS` 的脱敏标记）
- `admin_token` **不可从界面改**（改错的那一刻它自己就用不了了）；
  `cors_origins` 标「需重启服务」（middleware 启动时读取）
- 新增一个环境变量要看 **4 处**：`config.py`、`runtime_config.SPECS`、`.env.example`、`docker-compose.yml`
- `XUANPAN_LLM_CAPABILITY` 取值只有 `reasoning/fast/local`（排序表在 `router.py::_capability_rank`）。
  🔴 写别的不报错，只**静默落到默认档** —— `.env.example` 里曾错写 `vision`，已修

## 风险与待办

- **R1**：罗盘识别可行性 = 全项目根基风险
- **R8 🔴 假阳性**：给出山名候选但山名错（实测 15/96）。**与「识别不出」性质完全不同** —— 用户看到的是一个看似正常的错误坐向、不会去重拍。**唯一防线 `needs_user_confirmation`（RULE-004），不得为降低确认率而移除**
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

## 前端与交付要点（🔴 都是"改完看似没事、实际错"的）

🔴 **「内核做完了」≠「用户用得上」** —— 判定交付度必查**三条链路**：内核 → HTTP/MCP → App 界面。评估时先 grep App 有没有引用。
🔴 **日期换算只有一处实现** `apps/mobile/src/lib/date.ts` —— **任何页面不许写 `toISOString().slice(0,10)`**（东八区凌晨退一天，且只在前 1/3 时段出现）。守卫 `tests/mobile/test_local_date.py`。
🔴 **八字「身强 / 身弱」是状态不是吉凶** —— 必须走中性色（`DuanCard.verdictTone` 白名单只认「偏吉/偏凶」）。把「身弱」画红 = RULE-008 违规。
🔴 **断卦必须带 `detail.basis`** —— 缺了它，补录隔夜的卦会拿到一套依据全错的结论，而结论看起来完全正常。
🔴 **AI 解读有两种文体，切换判据只有一个** —— 动报告页时；`专业分析`/`白话讲解` 各是一整套区块，前端**只认后端的 `has_plain` 布尔**，不许自己写 `plain_sections.length > 0`（"只有不确定性区块、没有正文"不算有白话版，前端再判一次就会得出与后端不一致的结论 → 给一个点开是空的开关）。契约守卫 `tests/mobile/test_types_contract.py::test_interpretation_exposes_both_registers`。
🔴 **两套文体用同一批区块标题，必须先按文体切分再解析** —— 改 `report.py`/`prompt.py` 的解析时；整体解析会得到 8 个块、两种文体混在一起无法归属（`split_registers`）。
🔴 **零成本模板 provider 也必须产出两文体** —— 改 `providers/template.py` 时；不配 key 的用户走的就是这条路径，少了白话版，双文体能力在零成本路径上等于不存在（界面永远显示"本篇只有专业分析"）。白话版要**真的解释术语**（术语表就地注解），否则是"标题白话、正文照旧"的假白话。
🔴 **`content/help.ts` 必须与页面逐字对齐** —— 未登记的 topic 不渲染入口；文案里写了**已不存在的按钮**会把人引到死路（实测首页讲解还写着 V2 已删掉的「拍摄罗盘」）。
🔴 **改 `lib/` 里的规则必须配「Node 探针 + Python 锚点测试」并做变异验证**（现有 compassDial / ring24 / sensorQuality / sparkline / qimen / liuren / taiyi / date / apiCandidates）。
🔴 **变异验证不能只看退出码** —— `-k` 写错会以 exit=4 退出、`-k` 无匹配也返回非零，两者都与"测试失败"同貌 → **假的 N/N**。须同时断言「真的收集并执行了用例」；`-k` 布尔语法是 `and/or/not`（**不是 `|`**）；变异锚点必须**唯一**。
🔴 **几何 / 归一化必须防「恒定输入除零」** —— 静止时 `max-min≈0` 当分母得 `NaN` → 曲线**静默消失**（见 `lib/sparkline.ts` 的 `DEFAULT_MIN_SPAN`，它同时防"把 0.3 μT 噪声放大成剧烈波动"的假象）。
🔴 **「无数据」是一等状态** —— 显示「—」+ 可操作提示，**不编造、不转圈等**；且**别画会被误读的替代图形**（无方位数据时画一个静止在 0° 的罗盘，会被读成"方位就是 0°"）。
🔴 **改了后端代码必须 `docker compose up -d --build`** —— 只 `up -d` 会继续跑旧镜像：代码里明明有 `/admin` 却 404（**404 = 路由本身不存在，不是文件缺失**）。
**403 与 401 是两种故障**：403 = `XUANPAN_ADMIN_TOKEN` **没配**（整体关闭）；401 = 配了但值不对。鉴权头 **`X-Xuanpan-Admin-Token`**，亦接受 `?token=` / Cookie。**页面本身不需要令牌**（否则陷入"打不开 → 不知配什么 → 更打不开"死循环）。
🔴 **`/zeri/select` 的 3660 天上界在内核**（`MAX_RANGE_DAYS`）不在路由（MCP/HTTP 自动同界）；而 `/almanac/range` 的 31 天**确实在路由层** —— 两个端点口径不同，别混淆。
🔴 **`FortuneError` 不继承 `ValueError`** —— `app.py` 注册了全局处理器转 400；删掉它，本该是"你传错了"的错误会全变成 500。
🔴 **APK 内联的是「候选地址表」而非单个地址** —— 本机 3 块网卡分属 3 个网段，旧脚本只内联一个，手机不在该网段就**只是"一直转圈"**。现在启动**并发探活**自动选线（`lib/apiCandidates.ts` + `_layout.tsx`），换网段不必重打包；`oc.ayong.qzz.io` 实测**已无法解析**，已降为候选末位。
🔴 **`apiCandidates.ts` 刻意不依赖 React Native** —— 抽成纯模块才能被裸 node 探针真跑。凡"决定能不能连上"的逻辑都该这样。

🔴 **平台不支持某原生模块时，订阅必须兜住异常** —— 任何 `addListener` 类订阅；`expo-sensors` 无 web 实现，`Magnetometer.addListener` 内部抛 `this._nativeModule.addListener is not a function`，**未捕获异常让整棵 React 树渲染失败 → 整页白屏**，而 tsc/export/单元测试全绿。判据**不能用 `typeof x.addListener === 'function'`**（web 上它确实是函数，抛错在其内部 `_nativeModule` 上），只能真调用一次 + try/catch。
🟢 **离线看界面已可行**：`scripts/ui_render/`（CDP 精确手机视口 + SPA 回落 + 渲染探针），快照 `docs/ui-render/`（**16 页**，含管理台配置面板），回归 `tests/mobile/test_ui_render.py`（设 `XP_WEB_DIST` 启用）。它渲染的是**同一套 React 组件树**，可替代真机走查里"布局/折行/配色/空态"那部分；键盘遮挡、传感器真实数据、真机字体与安全区仍只能真机。渲染器支持页面清单第 6 个元素「点击选择器」，可进懒渲染的视图（`16-admin-config` 就是这么拍到的）
🔵 **后台管理台已于 2026-09-18 改造**：`services/api/xuanpan_api/static/admin.html` 新增「配置」页（AI 模型 / 其它配置 / 候选链）。仍是浅色工程风，与 APP 深色仪器风分属两套体系 —— **这是有意的**，别顺手"统一"。

🔴 **admin.html 有接线守卫，改页面前先读它** —— 改管理台页面时；`tests/api/test_admin_page_wiring.py`（18 条）守三类静默故障：① `$('id')` 写错 → `null` → `.addEventListener` 抛异常 → **整个 `<script>` 从此不再执行**（现象只是"某几个按钮没反应"）；② JS 读了后端不返回的字段 → `undefined` → 界面显示"（空）"却**不报任何错**；③ 加了 `data-view` 忘了加 `view-` 区块或忘了更新 `switchView` 里那份**硬编码视图名单** → 点导航什么都不发生。
🔴 **`api()` 封装必须显式设 `Content-Type: application/json`** —— 发带 body 的请求时；fetch 对**字符串** body 默认发 `text/plain`，服务端按 JSON 解析给 **422**。此前只用于 GET/DELETE 故未暴露。
🔴 **静态契约检查必须配「读到了东西」的自检** —— 写靠变量名定位读取点的检查时；变量一改名就读到 0 个字段，"没有任何字段错"成立 → **假绿**。同理，**同名变量别承载不同结构**（`res` 曾同时是 fetch Response / 探针响应 / 保存响应，三种形状混在一起判，检查失去判别力）。
🔴 **页面守卫断言「全文不得出现带协议的网址」**（容器不出网，CDN 引用必白屏）—— 加任何含 URL 的文案前先 grep；**连解释这条规则的注释也不能写出那个前缀**（实测触红）。要加就改文案，别把守卫改松。

🟢 **Chromium 在本机起不来**（实测第三次遭遇：`Chrome exited early ... DevToolsActivePort`；`agent-browser` 与其 `--no-sandbox` 均无效）→ **管理台/网页的渲染验证只能做静态检查**。别把静态检查说成"已验证渲染"，要在交付里写明为已知不足。离线渲染探针 `scripts/ui_render/`（见上一节）走的是 CDP，同样受此限。

## 外部项目（勿重复调研）

**suanming-mcp（玄机阁）** <https://github.com/Enoch666/suanming-mcp> commit `f08ec272` —— **已评估：术数计算层不可信，不做依赖、不移植算法**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画缺字按 Unicode 码位静默编造）。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`，复算脚本 `scripts/cmp_suanming_mcp.py`。**可借鉴**：MCP 暴露层写法、`SKILL.md` 打包范式、水墨 HTML 渲染。**它揭示的行业缺口**：开源项目全都停在「排盘/起卦」，**装卦层与三式全空** —— 这正是玄盘最该吃下的差异点。

## 数据缺口

- ✅ `data/kangxi_strokes.json` 已 20794 字 `verified:true`；缺字抛 `DomainDataMissingError`（**不静默取错值**）
- `fenjin120` 规则表缺失（管理台 `available=false`）—— 退化为「只输出几何格位 + 警告」
