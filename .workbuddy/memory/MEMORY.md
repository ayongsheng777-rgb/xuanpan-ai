# 玄盘AI · 项目长期记忆（规则索引）

> v2026-09-19。接手顺序：`HANDOFF.md`(状态) → `AGENTS.md`(规范) → 本文件(索引) → `PITFALLS.md`(根因详版)。
> AI 无跨会话记忆，**git 历史 + 记忆文件是唯一载体**。本文件只留「必须做什么」+ 指针，细节一律在另两文件。
> PITFALLS：§1 工具链 §2 假绿 §3 Expo §4 CDP §5 快照 §6 前端 §7 后端/管理台 §8 界面工艺 §9 运行时配置 §10 UI 导出包 §11 术数落地（含一百二十分金专项）。

## 基本盘

- **定位**：罗盘视觉识别 × 确定性术数计算 × AI 解释的移动端 APP。核心是**把实体罗盘转成结构化数字数据**（勿与「龙息」A 股项目混淆）
- **原则**：AI 看/理解/解释；代码算/校验/映射。**计算层唯一真源，禁 LLM 介入**
- 仓库 `D:\WorkBuddy\玄盘AI`(main)；remote `ayongsheng777-rgb/xuanpan-ai`(私有，每轮收尾推)
- 权威：`AGENTS.md`(最高) ＋ `docs/玄盘 AI — 产品基线规范.md`(**SSOT**，冲突以它为准；未覆盖的**先问**)
- 技术栈：RN+Expo(SDK52) `apps/mobile`｜FastAPI `services/api`＋`/admin`｜内核 `packages/fortune-core`(`lunar-python`；`sxtwl` Py3.13 无 wheel 已弃)｜**SQLite 单文件**——报告里的 PG/Redis/S3 只是 `[推测]`，**代码无任何 Redis/S3 调用**｜docker compose 单 service，宿主 8360→容器 8352
- 🔴 **领域数据表在 `packages/fortune-core/data/`**；根 `data/` 只装运行时产物

## 铁律（`AGENTS.md`）

1. **每次改动 = 单独 commit**，一 commit 一逻辑单元；**禁 `git add -A`**
2. **每次改动同步测试、交付前全绿**，附**实际命令 + 真实输出**；未运行不得声称「测试通过」

约定：`<type>(<scope>): <中文简述>`；结论标 `[已确认]`/`[推测]`/`[待验证]`；交付四段；引新依赖先说明成本。

## 环境快查（详版 §1）

- 端口 **8360**（8352 被 SysCenter 占）｜npm 走 npmmirror｜容器 pip 走清华源（本机解析不了 pypi.org）
- 本机有系统代理，**连本机服务必须 `trust_env=False`**
- `$PY` = `~/.workbuddy/binaries/python/envs/default/Scripts/python.exe`；`$NODE` = managed node 22.22.2
- `$T` = `tempfile.gettempdir()`；**pytest `--basetemp`、expo export 产物必须放 `$T` 下**
- 🔴 高频坑：`--basetemp` 落非 Temp→大批 ERROR｜`expo export --clear` 被 safe-delete 拦｜`output-dir /tmp/x` 落到 `D:\tmp`｜Chrome 截图用 CDP 设视口｜CDP 脚本结束 `process.exit()`
- 🔴 **`git fetch` / `update-ref` 在本环境写 ref 不落地**（报 exit=0、文件却不在）：修远端追踪只能手动 `printf '<sha>\n' > .git/refs/remotes/origin/main`；判同步只信 `git ls-remote` 比 sha｜§1

## 不可擅改（SSOT 已裁定）

🔴 改 UI 前必读：配色与导航**不在「重新设计」的自由度里**；能改的只有排版/间距/层级/状态/动效/图标/信息密度。
5 项裁定：底部导航 **5 栏**｜AI 报告**三标签**｜**配色取演示图**｜相机**双入口**（拍照+相册同管线）｜隐私表述**「数据可外流」**。
Token：`primary #013A6C` `gold #DAB37D` `sand #E5D7C7` `jade #3C7066` `cinnabar #B93E35`；V2 深色域 `bg #0A1626` `surface #12223A` `needle #E05548`。
🔴 **演示图配色已采纳，但术数数据不可采信**（实算证其八字日柱/时柱/日主三项错）。
🔴 **V2 的 8 屏演示图不在仓库**：照「第 N 屏」做页面前先读 `docs/玄盘 AI — V2 评估与实施路线.md`；缺细节问阿勇，**别自己编一屏**。

## 界面工艺（索引，详版 §8）

共同点：**看着不丑、但说不上哪里不对，且不会让任何测试失败**。最易违反的 12 条：
标题不得比它管的正文更小更淡｜表面原语只有三个 `Card`(浅)/`Panel`(深仪器)/`Pressable*`，别手写第四个｜深色域不用投影（靠底差+1px 描边）｜按压只有 `usePressScale`（`scale` 不换底色）｜不引 `react-native-reanimated`｜一屏一个 `Metric`｜数值等宽｜不内嵌中文字体｜图标语义不撞脸（`sparkles`→`shapes`、`locate`→`scan`）｜改 UI 后重渲染快照+登记分卷白名单｜管理台快照必须先 `docker compose up -d --build`｜**界面文案不得含 Markdown 标记**（守卫 `tests/mobile/test_ui_copy_plain_text.py`）
管理台专项：CSS 变量层/HTML/JS **三块一起改**；文字只做三级；禁用态用中性灰不 `opacity`；焦点环用主色 outline；`role=tablist/tab/tabpanel`+**roving tabindex**。

## 详版指针（动手前先读 PITFALLS）

- **运行时配置 §9**：优先级「管理台覆盖 > 环境变量 > 默认值」，每项报 `source`｜`get_settings`(基线) 与 `get_active_settings`(叠加) **并存别合并**，请求期一律用后者｜AI 路由器按**配置指纹**缓存｜密钥明文**唯一出口** `RuntimeConfig.llm()`，新增密钥必须进 `SECRET_KEYS`｜新增环境变量看 **4 处**
- **UI 导出包 §10**：产物在 `dist/` 不入库｜**核心理由是归档完整性自检**｜输出目录已存在要 `--force`｜**深色域边界＝「是不是在测量」**（6 页，确认页是浅色盘）
- **术数落地 §11**：lunar-python **无神煞接口**，但长生十二宫/身宫/胎息/黄历全套/大运**全是现成接口**｜三式 HTTP 动词各异**别统一**｜太乙只做年局、宫号与洛书逐宫错位（**别当遗漏补**）｜**别把「忌行丧/忌分居」加进嫁娶否决**（实测误杀 14%）

## 现状与风险（细节见 `HANDOFF.md`）

- V2 范围已完成（tag `v0.1.0-pre-v2` 可回滚）。**不做**：导航改动、全局深色化、Phase 3+ —— **别越界**
- 🔴 **真机 UI 走查仍未做**（7 个新界面）→ 最高优先级，清单见 HANDOFF §7.1
- **R8 🔴 假阳性**（给候选但山名错，实测 15/96）：与「识别不出」性质完全不同，用户看到的是看似正常的错坐向、不会重拍。**唯一防线 `needs_user_confirmation`(RULE-004)，不得为降确认率而移除**
- 待办序：① 真机走查 ② 真实照片取证 ③ 修 R8 前先建假阳性基线 ④ 重打 APK
- **待阿勇拍板**（HANDOFF §7.0）：`15-calibrate` 浅色 Card 改深色？｜底栏名冲突｜深色风铺全站？｜APK 签名/权限

## 数据缺口

- ✅ `kangxi_strokes.json` 20794 字 `verified:true`；缺字抛 `DomainDataMissingError`（**不静默取错值**）
- `fenjin120` 规则表缺失 → 退化「只输出几何格位 + 警告」。**加固已完成**（三层：严格加载/运行期降级/`table_load_error`；补表零回归；校验 `scripts/verify_fenjin_table.py`），**只差内容依据（须阿勇给）**｜§11 一百二十分金专项

## 外部项目（勿重复调研）

**suanming-mcp（玄机阁）** `f08ec272` —— **已评估：术数计算层不可信，不依赖、不移植算法**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画缺字静默编造）。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`。**可借鉴**：MCP 暴露层、`SKILL.md` 打包。**行业缺口**：开源全停在「排盘/起卦」，**装卦层与三式全空**。
