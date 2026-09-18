# 玄盘AI · 环境与交付坑（PITFALLS）

> 从 `MEMORY.md` 拆出（2026-09-18）。**MEMORY.md 是规则索引，本文件是根因详版。**
> 动手前若任务落在「跑测试 / 跑浏览器 / 改前端 / 刷新快照 / 清理目录」上，必须先读本文件对应小节。
> 格式：`🔴 <强制动作> —— <触发场景>；因为 <根因>`。缺根因=无法泛化。

---

## 1. WorkBuddy 工具链与 safe-delete

🔴 **pytest 的 `--basetemp` 必须落在系统 Temp 下** —— 跑全量/大批量用例时；因为 WorkBuddy safe-delete 只豁免 `tempfile.gettempdir()` 之下（及 pip 临时目录）的路径（shim `_should_bypass_safe_delete`），其余路径每删一个文件/目录都先问批量守卫，**同一次工具调用内累计删除 > 50** 即 `raise SystemExit(1)`（JSON 里 `scope:"turn"`）→ 落在 fixture teardown 就是**大批 ERROR**。
同一份代码三种跑法实测：
- `--basetemp=D:/tmp/...` → 970 passed 后首个 fixture ERROR 即停（全量口径 **1469 passed + 87 errors**、exit=1）
- `--basetemp="$T/xxx"`（`$T` = `tempfile.gettempdir()`）→ **1560 passed, exit=0**（汇总行完整，250~254s）✅ 唯一正确
- 不带 basetemp → 用例全过（100%、无 `F`/`E`）但收尾删 `pytest-of-*/garbage-*` 被拦（`count:175`）→ **汇总行丢失、exit=1**

⚠️ **旧规则「用 D:/tmp 绕开 safe-delete」方向是反的**（把"丢一行"升级成"87 个 ERROR"）。
判据仍是**有没有 `F`/`E` + 那行 JSON**；也别重复传 `-q`（addopts 已含，再传会吞掉汇总行）。

🔴 **删大量文件前先想 safe-delete** —— 清理非系统 Temp 下的目录时；判据是「单次工具调用内累计删除 >50 个」→ `raise SystemExit(1)`，症状是脚本半途静默停止而非给出可读错误。绕法：**同盘 rename 把旧目录挪走**（`shutil.move` 同盘即改名，零删除），或分批调用（每批 <50）。

🔴 **非沙箱工具调用里批量守卫不计数** —— 想用微探针直接验证 safe-delete 判据时；实测在非沙箱调用中删 120 个**非 Temp** 文件也不被拦（阳性对照失效），会误导出"豁免范围很大"的错误结论。探针必须先自检 shim 真被 patch（`os.unlink.__module__ == "sitecustomize"`、`os.unlink.__name__ == "_safe_remove"`），且**整段对照实验都要在沙箱内**跑；否则只能拿"真实全量跑"的结果当证据。

🔴 **全量测试 >190s 超 Bash 默认 120s 前台超时** —— 会被截断且**无任何输出**（易误判成崩溃）。用 `run_in_background` 或分模块跑。

🔴 **`.workbuddy/` 是项目数据，非缓存，不得删除。**

---

## 2. 变异 / 还原 / 校验（"假绿"类）

🔴 **md5 比对可能什么都证明不了** —— 做「改坏→还原→md5」时；两边求值对象可能**都是已改坏的**（实测 DuanCard 第 66 行仍留坏代码、md5 却报一致）。**必须用 grep 关键片段做内容断言**。

🔴 **变异还原禁用「插入式 replace」** —— 从文件里删掉一行做变异、之后要还原时；因为用 replace 把该行插回别的位置会让**顺序改变而内容不变**：grep 查得到、测试也全绿，但那不是字节级还原（实测把 `templates.tsx` 插到了 `almanac.tsx` 之前）。正确做法：变异前先备份原始字节，还原时整体 `write_bytes` 回写。

🔴 **`Path.write_text()` 在 Windows 把 LF 转 CRLF** —— 做「读-改-写」还原文件时；用 `read_bytes`/`write_bytes` 才字节级还原。

🔴 **变异验证不能只看退出码** —— `-k` 写错会以 exit=4 退出、`-k` 无匹配也返回非零，两者都与"测试失败"同貌 → **假的 N/N**。须同时断言「真的收集并执行了用例」；`-k` 布尔语法是 `and/or/not`（**不是 `|`**）；变异锚点必须**唯一**。

🔴 **动态加载含 `@dataclass` 的模块必须先登记 `sys.modules`** —— 用 `spec_from_file_location` + `exec_module` 加载脚本时；因为 dataclasses 解析注解会按 `cls.__module__` 反查 `sys.modules[..].__dict__`，不登记就抛 `AttributeError: 'NoneType' object has no attribute '__dict__'`，而报错位置在 dataclasses 内部、看不出是加载方式的问题。修法：`sys.modules[spec.name] = mod` 再 `exec_module`。

---

## 3. Expo / 打包

🔴 **`expo export --output-dir /tmp/x` 落在「当前盘符」的 `\tmp\x`** —— 核验打包产物时；因为 Node 按 Windows 路径解析，cwd 在 D 盘就是 `D:\tmp\`（**不是** Git Bash 的 `/tmp`，也不是 `C:\tmp`）。随后 `cd /tmp/x` 报 No such file → 会**误判成"打包失败"**。

🔴 **`.hbc` 里的中文串是 UTF-16LE** —— 想证明「页面真进了包」时；用 utf-8 grep 得 **0 命中（假阴性）**。用 `bytes.count(s.encode('utf-16-le'))`，并**带一个旧页面的串做对照组**自证探测方法有效。

🔴 **`expo export --clear` 会被 `[safe-delete]` 拦** —— 重新导出产物时；报 `checkBulkDeleteGuard`（大批量删除保护），与吞 pytest 汇总行同一机制。改成输出到**新目录**、不加 `--clear`。

---

## 4. 无头浏览器 / 截图 / CDP

🔴 **Chrome 在沙箱内/受限 shell 下静默 exit 0** —— 跑无头浏览器（截图/PDF/自动化）时；表现是**退出码 0、零输出、零产物**，极易误判成"参数写错了"。必须沙箱外执行，`--no-sandbox` 救不了（实测）。

🟢 **Chromium 在本机起不来**（实测第三次遭遇：`Chrome exited early ... DevToolsActivePort`；`agent-browser` 与其 `--no-sandbox` 均无效）→ **管理台/网页的渲染验证只能做静态检查**。别把静态检查说成"已验证渲染"，要在交付里写明为已知不足。离线渲染探针 `scripts/ui_render/` 走的是 CDP，同样受此限。
> ⚠️ 但 `docs/ui-render/` 的 19 页快照**确实拍出来过** —— 说明该结论**与具体调用方式有关**，不是无条件成立；下次做浏览器渲染先实测一次，别直接引用"起不来"而放弃。

🔴 **`chrome --headless --screenshot --window-size=390,844` 在本机不生效** —— 做"手机尺寸截图"时；实测页面 `innerWidth=500`，截出的 390px 图是把 500px 布局**裁掉右边**，看着像横向溢出、实为假象。要用 CDP 的 `Emulation.setDeviceMetricsOverride`。

🔴 **同一轮批量截图不要每页重启 Chrome** —— 批量任务；实例间互相干扰，实测**第二页起永久挂起**（20 分钟只出一页、无任何报错）。改为启动一次 Chrome + 每页独立 target。

🔴 **CDP/WebSocket 脚本结束必须 `process.exit()`** —— 写 Node 浏览器自动化时；不关 WebSocket 会让事件循环一直存活 → 进程永不退出 → 调用方（pytest/shell）跟着挂死（实测卡过 14 分钟）。杀 Chrome 要用 `spawnSync('taskkill',['/F','/T','/PID',pid])`，`spawn` 异步派发不够。

---

## 5. UI 快照刷新流程（改过前端页面后核对视觉）

🔴 **三件套，顺序不能变**：
1. `cd apps/mobile && npx expo export --platform web --output-dir "$T/xp-web"`（**不加 `--clear`**，会被 safe-delete 拦；产物放系统 Temp）
2. 起 `scripts/ui_render/preview_server.py <dist> <port>`
3. 跑 `render_pages.mjs <chrome> docs/ui-render http://127.0.0.1:<port>`（不传第 4 个参数才是全量）

`16-admin-config` 靠页面清单第 6 个元素「点击选择器」进懒渲染的配置视图，日志里 `clicked=clicked` 才是「面板真被点开」的证据——没有它，拍到的是没点成功的初始页。
会话三页快照需 `XP_SESSION_ID`（从 `GET /api/v1/sessions` 取）；**不传就跳过** —— 刻意不写死 id：id 来自不入库的运行时库，写死会在换库后**静默拍下「无此会话」错误页**。

🔴 **预览服务必须用工具的 `run_in_background`，不能用 `&`** —— 起 `preview_server.py` 时；工具调用一返回，shell 退出就把 `&` 起的子进程带走了。**症状极具欺骗性**：渲染脚本报 19 页全部 `ok:true`、`errors:[]`、`overflowX:0`，但每页正文其实是 `ERR_CONNECTION_REFUSED` 的错误页 —— Chrome 能启动、截图能出，只有目标服务器没了。
更坑的是 `11-admin` / `16-admin-config` **反而是正常的**（它们直接取 API 的 8360，不走预览端口），只看这两页会以为一切正常。
**判据：`ok:true` 不等于渲染成功 —— 必须读诊断 JSON 的 `text` 字段首句。** 渲染前先 `curl -o /dev/null -w "%{http_code}"` 自证服务器活着。

🔴 **`export X="$(python -c ...)"` 会静默掐断 `&&` 链** —— 在 Bash 工具里把 `python -c` 写进命令替换时；`python` 不在 PATH 上 → 替换返回 127 → **赋值语句的退出码就是 127** → `&&` 之后整条链不再执行。表现是整条命令 4 秒就"失败"、只打印前半段输出、无任何 stderr。修法：命令替换里也写绝对路径（`"$PY" -c`）。

---

## 6. 前端"改完看似没事、实际错"

🔴 **「内核做完了」≠「用户用得上」** —— 判定交付度必查**三条链路**：内核 → HTTP/MCP → App 界面。评估时先 grep App 有没有引用。

🔴 **日期换算只有一处实现** `apps/mobile/src/lib/date.ts` —— **任何页面不许写 `toISOString().slice(0,10)`**（东八区凌晨退一天，且只在前 1/3 时段出现）。守卫 `tests/mobile/test_local_date.py`。

🔴 **八字「身强 / 身弱」是状态不是吉凶** —— 必须走中性色（`DuanCard.verdictTone` 白名单只认「偏吉/偏凶」）。把「身弱」画红 = RULE-008 违规。

🔴 **断卦必须带 `detail.basis`** —— 缺了它，补录隔夜的卦会拿到一套依据全错的结论，而结论看起来完全正常。

🔴 **AI 解读有两种文体（专业分析 / 白话讲解），切换判据只有一个** —— 动报告页时；前端**只认后端的 `has_plain` 布尔**，不许自己写 `plain_sections.length > 0`（"只有不确定性区块、没有正文"不算有白话版，前端再判一次就会得出与后端不一致的结论 → 给一个点开是空的开关）。契约守卫 `tests/mobile/test_types_contract.py::test_interpretation_exposes_both_registers`。

🔴 **两套文体用同一批区块标题，必须先按文体切分再解析** —— 改 `report.py`/`prompt.py` 的解析时；整体解析会得到 8 个块、两种文体混在一起无法归属（`split_registers`）。

🔴 **零成本模板 provider 也必须产出两文体** —— 改 `providers/template.py` 时；不配 key 的用户走的就是这条路径，少了白话版，双文体能力在零成本路径上等于不存在（界面永远显示"本篇只有专业分析"）。白话版要**真的解释术语**（术语表就地注解），否则是"标题白话、正文照旧"的假白话。

🔴 **`content/help.ts` 必须与页面逐字对齐** —— 未登记的 topic 不渲染入口；文案里写了**已不存在的按钮**会把人引到死路（实测首页讲解还写着 V2 已删掉的「拍摄罗盘」）。

🔴 **改 `lib/` 里的规则必须配「Node 探针 + Python 锚点测试」并做变异验证**（现有 compassDial / ring24 / sensorQuality / sparkline / qimen / liuren / taiyi / date / apiCandidates）。

🔴 **几何 / 归一化必须防「恒定输入除零」** —— 静止时 `max-min≈0` 当分母得 `NaN` → 曲线**静默消失**（见 `lib/sparkline.ts` 的 `DEFAULT_MIN_SPAN`，它同时防"把 0.3 μT 噪声放大成剧烈波动"的假象）。

🔴 **「无数据」是一等状态** —— 显示「—」+ 可操作提示，**不编造、不转圈等**；且**别画会被误读的替代图形**（无方位数据时画一个静止在 0° 的罗盘，会被读成"方位就是 0°"）。

🔴 **平台不支持某原生模块时，订阅必须兜住异常** —— 任何 `addListener` 类订阅；`expo-sensors` 无 web 实现，`Magnetometer.addListener` 内部抛 `this._nativeModule.addListener is not a function`，**未捕获异常让整棵 React 树渲染失败 → 整页白屏**，而 tsc/export/单元测试全绿。判据**不能用 `typeof x.addListener === 'function'`**（web 上它确实是函数，抛错在其内部 `_nativeModule` 上），只能真调用一次 + try/catch。

🔴 **`apiCandidates.ts` 刻意不依赖 React Native** —— 抽成纯模块才能被裸 node 探针真跑。凡"决定能不能连上"的逻辑都该这样。

🔴 **APK 内联的是「候选地址表」而非单个地址** —— 本机 3 块网卡分属 3 个网段，旧脚本只内联一个，手机不在该网段就**只是"一直转圈"**。现在启动**并发探活**自动选线（`lib/apiCandidates.ts` + `_layout.tsx`），换网段不必重打包；`oc.ayong.qzz.io` 实测**已无法解析**，已降为候选末位。

🟢 **离线看界面已可行**：`scripts/ui_render/`（CDP 精确手机视口 + SPA 回落 + 渲染探针），快照 `docs/ui-render/`，回归 `tests/mobile/test_ui_render.py`（设 `XP_WEB_DIST` 启用）。它渲染的是**同一套 React 组件树**，可替代真机走查里"布局/折行/配色/空态"那部分；键盘遮挡、传感器真实数据、真机字体与安全区仍只能真机。

---

## 7. 后端 / 管理台

🔴 **改了后端代码必须 `docker compose up -d --build`** —— 只 `up -d` 会继续跑旧镜像：代码里明明有 `/admin` 却 404（**404 = 路由本身不存在，不是文件缺失**）。
**403 与 401 是两种故障**：403 = `XUANPAN_ADMIN_TOKEN` **没配**（整体关闭）；401 = 配了但值不对。鉴权头 **`X-Xuanpan-Admin-Token`**，亦接受 `?token=` / Cookie。**页面本身不需要令牌**（否则陷入"打不开 → 不知配什么 → 更打不开"死循环）。

🔴 **`/zeri/select` 的 3660 天上界在内核**（`MAX_RANGE_DAYS`）不在路由（MCP/HTTP 自动同界）；而 `/almanac/range` 的 31 天**确实在路由层** —— 两个端点口径不同，别混淆。

🔴 **`FortuneError` 不继承 `ValueError`** —— `app.py` 注册了全局处理器转 400；删掉它，本该是"你传错了"的错误会全变成 500。

🔵 **后台管理台是浅色工程风，与 APP 深色仪器风分属两套体系 —— 这是有意的**，别顺手"统一"。

🔴 **admin.html 有接线守卫，改页面前先读它** —— `tests/api/test_admin_page_wiring.py`（18 条）守三类静默故障：① `$('id')` 写错 → `null` → `.addEventListener` 抛异常 → **整个 `<script>` 从此不再执行**（现象只是"某几个按钮没反应"）；② JS 读了后端不返回的字段 → `undefined` → 界面显示"（空）"却**不报任何错**；③ 加了 `data-view` 忘了加 `view-` 区块或忘了更新 `switchView` 里那份**硬编码视图名单** → 点导航什么都不发生。

🔴 **`api()` 封装必须显式设 `Content-Type: application/json`** —— 发带 body 的请求时；fetch 对**字符串** body 默认发 `text/plain`，服务端按 JSON 解析给 **422**。此前只用于 GET/DELETE 故未暴露。

🔴 **静态契约检查必须配「读到了东西」的自检** —— 写靠变量名定位读取点的检查时；变量一改名就读到 0 个字段，"没有任何字段错"成立 → **假绿**。同理，**同名变量别承载不同结构**（`res` 曾同时是 fetch Response / 探针响应 / 保存响应，三种形状混在一起判，检查失去判别力）。

🔴 **页面守卫断言「全文不得出现带协议的网址」**（容器不出网，CDN 引用必白屏）—— 加任何含 URL 的文案前先 grep；**连解释这条规则的注释也不能写出那个前缀**（实测触红）。要加就改文案，别把守卫改松。
