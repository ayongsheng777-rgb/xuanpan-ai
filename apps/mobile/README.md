# xuanpan-mobile — 玄盘 AI 移动端

React Native + Expo（expo-router）。**只做界面与交互，不做任何术数计算。**

计算的唯一真源是 `packages/fortune-core`（Python，经 `services/api` 暴露）。
客户端如果把某条规则"顺手也实现一遍"，就会出现两份口径 —— 后端改了前端没跟，
用户看到的是本地算的、与服务端不一致的结论。所以本工程**不含**任何五行、
干支、纳音之类的查表或公式；`src/lib/ring24.ts` 是唯一的例外，见下。

---

## 一、目录结构

```
apps/mobile/
├── app/                         # expo-router 路由（文件即路由）
│   ├── _layout.tsx              # 根栈：安全区 + 深色状态栏 + 栈式页面声明
│   ├── (tabs)/                  # 底部五栏（基线规范 §1）
│   │   ├── _layout.tsx
│   │   ├── index.tsx            # 首页 —— 罗盘图形 + 双入口 + 快捷术式
│   │   ├── chart.tsx            # 命盘 —— 生辰录入
│   │   ├── divine.tsx           # 占测 —— 六爻 / 灵签
│   │   ├── history.tsx          # 历史 —— 会话列表
│   │   └── mine.tsx             # 我的 —— 模型线路 / 数据 / 免责
│   ├── scan.tsx                 # 罗盘识向（拍摄 / 相册双入口）
│   ├── confirm/[sessionId].tsx  # 确认坐向（RULE-004 闸门）
│   ├── session/[sessionId].tsx  # 会话详情（记录视角：依据与原始输入）
│   └── report/[sessionId].tsx   # AI 解读报告（结论视角：三标签）
├── src/
│   ├── api/
│   │   ├── types.ts             # 与 services/api/xuanpan_api/schemas.py 一一对应
│   │   └── client.ts            # 带超时、错误分类、密钥零持有的 HTTP 客户端
│   ├── components/              # AppText / Card / Banner / Screen / MountainRing …
│   ├── lib/
│   │   ├── ring24.ts            # 二十四山环形选择器几何（纯函数，已跨语言校验）
│   │   └── useAsync.ts          # 极简异步状态（读 / 写两条路径 + 错误分类）
│   └── theme/tokens.ts          # 五色设计 Token（唯一真源）
└── scripts/ring24_probe.ts      # 几何探针：供 pytest 做跨语言一致性校验
```

---

## 二、为什么 `ring24.ts` 里会有一份山表

这是全工程唯一"同一规则存在两处"的地方，属于**有意为之的取舍**：

- 环形选择器必须在**首帧**就画出 24 个格子。若等 `/api/v1/meta/mountains`
  回来再渲染，用户会先看到一段空白，然后格子"啪"地出现。
- 但属性（五行 / 卦 / 三元龙）一律走接口，只有**顺序与山心角**内嵌。

代价是顺序可能漂移，而漂移的后果是静默的灾难：用户点了「午」，算出的是「未」。
因此设了两道防线：

| 防线 | 位置 | 触发时机 |
|---|---|---|
| `validateMountainOrder()` | `src/lib/ring24.ts` | 运行时，接口返回后 |
| `tests/mobile/test_ring24_parity.py` | 仓库根 `tests/` | `pytest` 阶段 |

第二道是主力。它**真正执行** `ring24.ts`（Node ≥ 22.6 的
`--experimental-strip-types`，不需要装依赖、不需要构建），把几何结果取回 Python，
与 `fortune_core.mountain24` 逐位比对 24 座山的名称、山心角、对宫关系，
以及 0..359 每个整度的归属。

> 该测试做过变异验证：把 `子` 与 `癸` 互换后，8 个用例立刻失败，
> 且诊断信息可直接定位（`癸：TS 对宫=午 PY 对宫=丁`）。
> 值得注意的是探针自检仍然通过 —— **几何自洽不等于与后端一致**，
> 这也是必须有跨语言比对、不能只靠"前端自己看着对"的原因。

---

## 三、网络与环境

后端地址**默认 `http://127.0.0.1:8360`**，在 `app.json` 的 `extra.apiBaseUrl` 配置。

- 不用 `8352`：该端口被同机另一个服务（SysCenter）占用。
- 真机调试要改成局域网地址，例如 `http://192.168.1.10:8360`
  （`127.0.0.1` 在手机上指向手机自己）。

**客户端不持有任何模型密钥**（AGENTS.md §5.5 红线）。
provider 的能力与可用性一律从 `/api/v1/meta/ai-providers` 读服务端状态，
客户端只负责展示。密钥只存在于服务端的 `.env` 里。

### npm 源

`apps/mobile/.npmrc` 把 registry 指向 `registry.npmmirror.com`。

本机 `registry.npmjs.org` **不可达**（实测 curl 返回 `000`），用默认源装依赖会
停在依赖解析阶段十几分钟、不报错、`node_modules` 一直不出现 ——
症状很像"Expo 依赖本来就大"，实则完全没在下载。该文件必须提交。

### 三个必须显式声明的依赖（都是上游打包缺陷，不是本工程的多余依赖）

| 包 | 为什么需要 | 移除后果 |
|---|---|---|
| `expo-asset` | `@expo/metro-config` 启动时强制要求 | 打包直接失败：`The required package expo-asset cannot be found` |
| `expo-font` | `@expo/vector-icons` 的运行时依赖 | 图标字体不加载 |
| `expo-splash-screen` | `expo-router` 的启动图流程 | 启动图配置失效 |
| `query-string` | **`expo-router@4.0.22` 的 build 产物 `require("query-string")`，但它自己的 `package.json` 里没声明**（SDK 52 期望的正是 4.0.22，不是版本问题） | 打包失败：`Unable to resolve module query-string` |

`query-string` 这条尤其值得记：它不是"我们多装的包"，而是在替上游补一个
声明遗漏。升级 expo-router 时应重新验证这条是否还需要 ——
上游一旦修好，就应当把它删掉，而不是永远留在依赖里。

---

## 四、命令

> 运行环境：`[Host]` = 本机 Shell。Python / Node 均用托管运行时（见 AGENTS.md §5.3）。

```bash
# [Host] 安装依赖（首次，约 2~5 分钟）
cd apps/mobile && npm install

# [Host] 类型检查（零容忍，必须全绿）
cd apps/mobile && npm run typecheck

# [Host] 打包验证（**最强的一道**：真实解析全部 import 与依赖图）
#        产出 .hbc 字节码即为通过；不需要设备、不需要模拟器
cd apps/mobile && npx expo export --platform android --output-dir <临时目录>

# [Host] 导出几何结果（JSON 到 stdout），供人工核对
cd apps/mobile && npm run geometry:probe

# [Host] 跨语言一致性校验 + 类型契约校验（仓库根执行）
python -m pytest tests/mobile -v
```

> **为什么打包验证不能省**：`tsc` 只检查类型，不检查模块是否真的能被解析。
> 本轮 `query-string` 缺失就是这样 —— 类型全绿、`tsc` 零报错，
> 一打包才暴露。三道检查各有覆盖：`tsc` 管类型，`expo export` 管依赖图，
> `pytest tests/mobile` 管前后端契约。

启动开发服务器前**必须先起后端**（否则所有页面都是网络错误）：

```bash
# [Host] 终端 1 —— 后端
cd "D:/WorkBuddy/玄盘AI" && \
  PYTHONPATH='D:/WorkBuddy/玄盘AI/services/api;D:/WorkBuddy/玄盘AI/services/ai;D:/WorkBuddy/玄盘AI/services/vision;D:/WorkBuddy/玄盘AI/packages/fortune-core' \
  python -m uvicorn xuanpan_api.app:create_app --factory --host 0.0.0.0 --port 8360

# [Host] 终端 2 —— 移动端
cd apps/mobile && npm start
```

> `--host 0.0.0.0` 只在真机调试时需要；仅用模拟器/Web 时用 `127.0.0.1` 即可，
> 不要长期把服务暴露到局域网。

---

## 五、界面上的几条硬约束（改 UI 前请先读）

这些不是风格偏好，是基线规范与 RULE 的落地要求，破坏它们等于破坏产品前提：

1. **不给角度输入框。** 手动修正坐向的唯一入口是环形选择器（§4.1）。
   用户不知道 `177.03°` 是什么意思，但知道罗盘上「午」在哪；
   而 `17.7` 与 `177` 混淆会静默产生完全错误的结论。

2. **向山不可独立选择。** 坐向是一条直线，向山必然是坐山的对宫。
   允许独立选会造出"坐午向巳"这种几何上不成立的状态，计算层会直接抛错。
   在交互层就约束住，比让用户走到报错要好。

3. **不显示"AI 正在思考"。** 识别过程要展示**可验证的步骤**
   （质检 → 边界 → 天池 → 透视 → 二十四山 → 坐向 → 分金 → 解读，见 `StepList`）。
   客户端拿不到服务端中间态，所以步骤状态只由**真实返回**驱动，
   不按定时器自嗨式推进 —— 那是在编造过程。

4. **`null` 一律渲染为「未定」，绝不留空。** 计算层在"规则表未提供"时返回 `null`
   （RULE-003 不猜）。渲染成空白会让用户以为程序坏了。

5. **三个标签内容物理分离，不合并渲染。** `facts` / `tradition` 直接取自后端，
   AI 只填 `interpretation`。前端**不得**把 facts 拼进 AI 文本里，
   否则"防幻觉污染盘面"的机制就在界面层被破掉了。

6. **不确定性清单不得折叠或改写。** `UncertaintyList` 是用户判断结论可靠性的
   唯一依据，后端把它作为"系统保证"写入报告，模型改不了。

7. **免责声明固定在标签之外。** 它属于整份报告，跟着标签切换而消失等于没附。

8. **组件内不得出现硬编码色值。** 一律引用 `src/theme/tokens.ts`
   （对应 RULE-005「规则不散落」）。
