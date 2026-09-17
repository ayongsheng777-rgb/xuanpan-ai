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

services/api/xuanpan_api/
  ├── routers/     # calc / sessions / report / scan / meta ＋ almanac / zeri / duan / admin
  ├── static/admin.html   # 管理台（单文件、零依赖、**无 CDN** —— 容器没有外网）
  └── schemas.py / storage.py / config.py / app.py
services/mcp/server.py   # 9 个 MCP 工具

apps/mobile/
  ├── app/(tabs)/  # 底部 5 栏：index(罗盘) / chart(命盘) / divine(占测) / history / mine
  ├── app/         # 根 Stack：scan / almanac / confirm/[id] / report/[id] / session/[id]
  └── src/
      ├── api/         # client.ts + types.ts（**手写**，与后端 schemas 对应）
      ├── components/  # DuanCard(断卦展示) / Chip+Tag / CompassDial / Card / …
      ├── lib/date.ts  # 本地日期**唯一实现点**（别在页面里另写一份）
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
# 全量测试（当前 940 passed）
"$PY" -m pytest

# 分层
"$PY" -m pytest packages/fortune-core/tests    # 计算内核（新增三式/择日测试放这里）
"$PY" -m pytest tests/test_mcp_server.py       # MCP 暴露层（真实 stdio 子进程）
"$PY" -m pytest tests/vision                   # 罗盘识别
"$PY" -m pytest tests/api tests/ai tests/mobile
```

> 🔴 **全量跑完拿不到「940 passed」那一行，是已知现象，不是测试失败。**
> WorkBuddy 的 `[safe-delete]` 在 teardown 清理 pytest 临时目录（实测 399 个文件 > 阈值 50）
> 时会**直接拦停进程**，汇总行来不及打印、并把 exit code 变成 1。
> 现象是：点阵走到 `[100%]`、一个 `F` 都没有，紧跟着一行 `[SAFE_DELETE_BULK_CONFIRM_REQUIRED]`。
>
> **取真实数字的办法**（也是判断"是不是真失败"的办法）：分模块跑，逐个核对 exit code。
> 命令行**不要传 `-q`** —— `pyproject` 的 addopts 已含 `-q`，再传会变成 `-qq` 从而**吞掉汇总行**。
>
> ```bash
> for m in packages/fortune-core/tests tests/vision tests/ai tests/api tests/mobile \
>          tests/test_mcp_server.py tests/test_doctests.py; do
>   printf '%-32s %s\n' "$m" "$("$PY" -m pytest "$m" -p no:warnings --tb=short 2>&1 \
>     | grep -E 'passed|failed' | tail -1)"
> done
> ```
> 分模块合计 = 全量数，且每个模块都能看到明确的 `N passed in Xs`。
> 想拿总数又不跑测试：`"$PY" -m pytest --collect-only -p no:warnings | tail -3`。

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
3. **真机 UI 走查** —— 本轮之后**比之前更必要**，理由见下
4. SKILL.md 打包（让仓库同时是 MCP Server + Agent Skill，可抄 suanming-mcp 的 Agent 入口）
5. 神煞吉凶分级（建议留给 AI 层，内核只给 FACT）
6. 建 remote 仓库

### 7.1 🔴 本轮未验证项（接手时别当成"已经验过了"）

离线能验的都已验（`tsc` 零错、`expo export` 出包、接口契约、真实 HTTP 的 62 项断言、
两处变异验证）。但下面这些**只能在真机/模拟器上确认**，本轮**没有做**：

| 未验证项 | 为什么离线验不了 |
|---|---|
| `/almanac` 路由是否真的跳得过去 | 类型检查不校验路由；`expo export` 只证明文件进了包 |
| 黄历 / 择日页布局是否溢出、长文案是否折行得当 | 没有渲染器，只能真机看 |
| 六爻断卦的类别 chip 在窄屏是否换行得体 | 同上 |
| 大运倾向的两列网格在小屏是否挤在一起 | 同上 |
| 「3 秒内确认」的真实体感 | 只有真机能测 |
| 键盘弹起是否遮挡输入框 | 同上 |

> 这些**不是"大概没问题"** —— 而是**确实没测**。接手做真机走查时按这张表逐项过。

---

## 8. 外部项目结论（勿重复调研）

- **suanming-mcp（玄机阁）**：已评估完毕，**术数计算层不可信**（六爻卦序 63/64 错配、八字月柱 10/10 错、笔画表缺字按 Unicode 静默编造），**不做依赖、不移植算法**。三处可借鉴：MCP 暴露层写法、SKILL.md 打包范式、水墨 HTML 渲染。详见 `docs/外部项目评估 — suanming-mcp（玄机阁）.md`。
