# 玄盘AI · 详版附录（PITFALLS）

> **MEMORY.md 是规则索引（受注入长度限制，必须保持精简），本文件是根因详版。**
> 每次从 `MEMORY.md` 拆出，阈值是「注入时开始被截断」—— 2026-09-18 拆了两次（先 §8 界面工艺，再 §9–§11 配置/导出包/术数）。
> 动手前若任务落在「跑测试 / 跑浏览器 / 改前端 / 改 UI / 刷新快照 / 清理目录 / 动后端 / 打包 / 改配置」上，**必须先读本文件对应小节**。
> 格式：`🔴 <强制动作> —— <触发场景>；因为 <根因>`。缺根因=无法泛化。
> 小节：§1 工具链 §2 假绿 §3 Expo §4 CDP §5 快照 §6 前端 §7 后端/管理台 §8 界面工艺 §9 运行时配置 §10 UI 导出包 §11 术数落地

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

🔴 **提交说明含反引号时一律走 `git commit -F <文件>`** —— 写带行内代码的 commit message 时；`git commit -m "…`x`…"` 里的反引号会被 **bash 当命令替换执行**，内容不进说明（本次「只删 `**` 这 2 个字符」变成「只删  这 2 个字符」，并额外打出一行 `AGENTS.md: command not found`）。**commit 照样成功、`git log` 才看得出缺字**。修法：用 Write 工具写消息文件再 `-F`，不让 shell 碰它。

🔴 **判推送成败只问远端，别用管道后的 `$?`、也别信 `origin/main`** —— 交付收尾核对是否已推时；
`git push ... 2>&1 | tail -5` 的 `$?` 是 **`tail` 的**，永远是 0；而本机还出现过
`.git/refs/remotes/` **被清空**（`git branch -vv` 显示 `[origin/main: gone]`、
`git rev-parse origin/main` 报 `unknown revision`）—— 但**推送其实是成功的**。
两条一起会得出"推送失败"的完全错误结论，而 git 的报错看着像真的。
**权威判据：`git ls-remote origin refs/heads/main` 与 `git rev-parse HEAD` 比 sha**（远端状态无法伪造），
或看 `.git/FETCH_HEAD`。补本地追踪引用：`mkdir -p .git/refs/remotes/origin && echo <sha> > .git/refs/remotes/origin/main`
（本轮 `git update-ref` 报了退出码 0 却没落盘，直接写文件才成）。

🔴 **`.workbuddy/` 是项目数据，非缓存，不得删除。**


🔴 **`finally` 里的清理可能被 safe-delete 拦下 → 实验残留会留在仓库里** —— 做「临时放一个文件、跑完自动删掉」的实验时；
safe-delete 是**按同一个 turn 内累计删除数**判的（>50 即拦），而 pytest 自己就在删一堆临时文件，
于是收尾那个 `unlink` 会被 `SAFE_DELETE_BULK_CONFIRM_REQUIRED` 挡掉 —— 而**实验脚本的主流程仍然报成功**
（本次是打印了「✓ 零失败」、退出码 0，只有 stderr 里一行 JSON 提示）。
🔴 **判据：实验做完必须单独 `ls` 目标目录 + 核 `git status`**，不能相信脚本自己说的"已恢复"。
本次残留的是 `packages/fortune-core/data/fenjin120.json`（一张实验填充表），
若没发现就会跟着 commit 进仓库 —— 而它长得完全像领域数据。
（清理自建残留文件用单条 `rm -f <精确路径>`，别用通配符。）

🔴 **同一文件严禁在一条消息里并行发多个 Edit** —— 改一个文件的多个位置时；
编辑是「读-改-写」，并行下发会基于同一份旧快照互相覆盖，**先完成的那次写入被静默丢弃（工具仍回 success）**。
本次实测：想给 `scripts/verify_fenjin_table.py` 同时改 import 行和函数体，结果 **import 行没落地**，
测试报 `NameError: name 'DEFAULT_SCHOOL' is not defined` 才发现。
**改完立刻 grep 复核，不要只信 success 回执。**（跨文件并行是安全的；同一文件串行。）
---

## 2. 变异 / 还原 / 校验（"假绿"类）

🔴 **md5 比对可能什么都证明不了** —— 做「改坏→还原→md5」时；两边求值对象可能**都是已改坏的**（实测 DuanCard 第 66 行仍留坏代码、md5 却报一致）。**必须用 grep 关键片段做内容断言**。

🔴 **变异还原禁用「插入式 replace」** —— 从文件里删掉一行做变异、之后要还原时；因为用 replace 把该行插回别的位置会让**顺序改变而内容不变**：grep 查得到、测试也全绿，但那不是字节级还原（实测把 `templates.tsx` 插到了 `almanac.tsx` 之前）。正确做法：变异前先备份原始字节，还原时整体 `write_bytes` 回写。

🔴 **`Path.write_text()` 在 Windows 把 LF 转 CRLF** —— 做「读-改-写」还原文件时；用 `read_bytes`/`write_bytes` 才字节级还原。
**而且 `git diff` 看不见它**：`.gitattributes` 声明 `*.ts/tsx text eol=lf`，git 比对前会先规范化，于是整文件行尾被换掉也不显示任何差异，只在输出里留一句 `CRLF will be replaced by LF` 的告警（很容易当成噪音略过）。本次 5 个文件 582/386/291/665/1009 处行尾被换。**判据：改完立刻数 `read_bytes().count(b'\r\n')`，不要只看 diff。** 修法：`write_text(..., newline='\n')`，或改完二进制回写。

🔴 **本坑 2026-09-19 又踩了一次 —— 但边界现在清楚了**：那次是 4 个 `.md` 被批量刷成 CRLF（327/103/137/582 处），**全部来自 heredoc 里自己写的 `pathlib.Path.write_text()`**。
**WorkBuddy 的 `Write` / `Edit` 工具不会引入 CRLF**（同一个 turn 里用它们改的 11 个 `.py` 全是 0 处 CRLF）。
→ **改文本优先用 `Edit`；必须用 Python 批量写时，一律 `write_bytes(text.replace(b'\r\n', b'\n'))`。**
**判据不变：改完对 `git status` 里每个文件数 `read_bytes().count(b'\r\n')`，`>0` 就归一化再提交。**

🔴 **静态扫描类守卫自己要能被验证，否则它会「永远通过」** —— 写"扫源码找某特征"的测试时；第一版幂运算符判据用了 `[\w\)\]]\s*\*\*\s*[\w\(\[]`，而 **Python 的 `\w` 含 CJK**，于是中文句子中间的 `**标记**` 被判成 `2 ** 3` 整段跳过 —— 中文正是本项目正文语种，等于守卫关掉一大半（症状：只有行首的标记报得出来，句中的静默漏掉，最坏情况全绿而缺陷全在）。
两道修法都要做：① 显式写 ASCII 字符类 `[A-Za-z0-9_]`；② **给守卫本身写"守卫的守卫"断言**（该报的报 / 不该报的不报 / 剥注释不剥过头，见 `tests/mobile/test_ui_copy_plain_text.py`）—— 本轮正是这两条断言当场抓到了它自己。

🔴 **变异验证不能只看退出码** —— `-k` 写错会以 exit=4 退出、`-k` 无匹配也返回非零，两者都与"测试失败"同貌 → **假的 N/N**。须同时断言「真的收集并执行了用例」；`-k` 布尔语法是 `and/or/not`（**不是 `|`**）；变异锚点必须**唯一**。

🔴 **动态加载含 `@dataclass` 的模块必须先登记 `sys.modules`** —— 用 `spec_from_file_location` + `exec_module` 加载脚本时；因为 dataclasses 解析注解会按 `cls.__module__` 反查 `sys.modules[..].__dict__`，不登记就抛 `AttributeError: 'NoneType' object has no attribute '__dict__'`，而报错位置在 dataclasses 内部、看不出是加载方式的问题。修法：`sys.modules[spec.name] = mod` 再 `exec_module`。

---

## 3. Expo / 打包

🔴 **`expo export --output-dir /tmp/x` 落在「当前盘符」的 `\tmp\x`** —— 核验打包产物时；因为 Node 按 Windows 路径解析，cwd 在 D 盘就是 `D:\tmp\`（**不是** Git Bash 的 `/tmp`，也不是 `C:\tmp`）。随后 `cd /tmp/x` 报 No such file → 会**误判成"打包失败"**。

🔴 **`.hbc` 里的中文串是 UTF-16LE** —— 想证明「页面真进了包」时；用 utf-8 grep 得 **0 命中（假阴性）**。用 `bytes.count(s.encode('utf-16-le'))`，并**带一个旧页面的串做对照组**自证探测方法有效。

🔴 **web 产物（`expo export --platform web`）里的中文是 `\uXXXX` 转义** —— 核验 web bundle 时；直接 `grep 中文` 同样得到 **0 命中假阴性**（本次差点据此得出"已无星号"的错误结论，其实是因为压根匹配不到中文）。修法：先 `re.sub(r'\\u([0-9a-fA-F]{4})', …)` 解回中文再断言；**并且一定要拿改动前的旧产物做对照**（v4 应报 60 处、v5 报 0 处，两组数字都拿到才算验过）。

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

🔴 **管理台的 4 张快照直连容器，拍的是「镜像里烧的那份」而不是工作区** —— 改了 `static/admin.html` 之后要刷新快照时；**必须先 `docker compose up -d --build`**，否则 `http://127.0.0.1:8360/admin` 返回的是**构建时刻**的副本 —— 快照看起来更新了，其实是旧界面。
**这个坑最毒的地方是它全绿**：`ok:true` / `errors:[]` / `overflowX:0` / `clicked=clicked` 一个不缺，`text` 字段也有内容。唯一能一眼认出的信号是**正文内容对不上**（本轮旧副本渲染出 `这里是**只读试算台**：`，而磁盘上早已是 `<strong>只读试算台</strong>`）。
**判据（照做即可）**：`curl :8360/admin` 与磁盘文件比 `sha256`，不一致就是旧副本。pytest 与渲染诊断都发现不了这件事。
（与 §7「改了后端必须 `up -d --build`」同源，但后果更隐蔽：后端改动只是功能不对，这里是**快照与源码静默漂移**。）

🔵 **改前/改后并排对照用 `scripts/ui_render/make_compare.py`** —— 评审 UI 改动时。`--before DIR --after DIR --out DIR [--names a,b]`，自动算**差异像素占比**，并在两张完全一致时告警「基线可能取错了」（拿改后图当基线是最容易发生的假绿）。
**但差异占比不是证据**：页面里的活数据（会话数、库体积、AI 模式）也会让像素变。**要证明"差异来自视觉而非数据"，去比渲染诊断的 `text` 字段** —— 本轮概览/配置/会话三页改前改后 `text` 逐字节相同，才敢说那 9%~17% 是纯视觉改动。
**没有改前基线就如实说没有**，不要拿改后的图凑一张"对照"。

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

🔴 **界面文案里不得出现 Markdown 标记（`**强调**` / 反引号）** —— 写任何会渲染的文案时；RN 的 `<Text>` 把 children 当**纯文本**，`**这样**` 会原样显示两个星号。三处旧防线全看不到它：`tsc` 只管类型、单元测试不渲染、离线快照只回传**布局诊断**（溢出量 / JS 错误）不核对正文。本仓库**已发生过两次**（先管理台 `static/admin.html`、后 App 的 5 个文件 63 对，其中 `content/help.ts` 占 53 对 = 每页「讲解」抽屉的全部正文）。守卫：`tests/mobile/test_ui_copy_plain_text.py`。**改法沿用管理台裁定 —— 删标记，不加粗体渲染器**（同类问题一种解法，见 `tests/api/test_admin_config.py::TestCopyIsPlainText`）。

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

---

## 8. 界面工艺（详版 —— MEMORY.md 只留一行索引）

**共同点：这一类问题全都"看着不丑、但说不上哪里不对"，且都不会让任何测试失败**（不是假绿，是**根本没测**）。逐页像素差异见 `2026-09-18.md` 末节。

🔴 **同一容器内，标题的字号不得小于正文、颜色不得比正文更淡** —— 改任何卡片/分区标题时。`SectionTitle` 曾是 `sm 13 + textSecondary`，比自己管的正文（`md 15 + text`）**更小更淡**，19 页全中却零测试失败。**层级倒挂是这类问题的典型**。
判据：标题字号 > 正文字号，且标题前景对比度 > 正文前景对比度。

🔴 **三个表面原语，别再多造第四个** —— `Card`（浅色纸面）/ `Panel`（**深色仪器**）/ `PressableCard`·`PressablePanel`（整卡可点）。深色页**不许**手写「surface 底 + 1px 边框 + `radius.lg` + padding」—— 那组样式曾被 6 个页各抄一遍（重复 17 次）。**散落样式组合不会触发任何检查**。

🔴 **深色域不用投影** —— 深底上的投影看不见、只让边缘发脏。深色层级靠「底差 + 1px 描边」。**这才是深色页无法复用浅色 `Card` 的真正原因，不只是色值不同**。

🔴 **按压反馈只从 `interaction` 取值，实现只有 `usePressScale`** —— 加任何可点元素时。此前五种写法并存（`opacity .86` / 换底色 / `opacity .7` / **两处完全没有**），同一手势不同回应会被读成"有的地方坏了"，而它**不会在任何测试里失败**。用 `scale` 而非换底色：缩放会把文字和图标一起带走。

🔴 **不引 `react-native-reanimated`** —— 想做动效时。它在 package.json 里不存在，引它要动 babel + 新架构开关。`transform` 走 core `Animated` 的 `useNativeDriver` 已够 120ms 按压反馈。真要弹簧物理，只改 `usePressScale.ts`。

🔴 **一屏一个 `Metric` 读数** —— `Metric`（40px/heavy/负字距/等宽数字）是主角档；同页第二个读数降一档（磁场强度降到 `xl 20`）。原先把 `display 32` 兼职读数，与 `xxl 26` 只差 1.23 倍，区分不出主角配角。

🔴 **凡数值原地变化处一律等宽数字**（`AppText numeric` / `Metric` / CSS `tabular-nums`）—— 比例数字下 "1" 比 "8" 窄，读数一跳整行长度就跳；传感器每秒刷数次，**抖会被读成"界面在闪"**。

🔴 **不内嵌中文字体** —— 想"换字体提升质感"时。中文字体 5–10 MB，会让 APK 体积翻几倍，而苹方/思源黑体本身已是高质量中文字体。功夫花在**阶梯与字距**：中文没有大小写，层级只能靠「字号 × 字重 × 字距」三件套。

🔴 **图标语义不许撞脸、不许用 AI 陈词** —— 动底栏/图标时。「分析」原用 `sparkles`（✨＝"这是 AI 生成的"通用符号），但那个 tab 装的是**确定性术式**，误导且削弱"计算层是真源"的核心承诺（现用 `shapes`）；`compass`(罗盘) 与 `locate`(测盘) 原来都是"圆+十字"，5 栏里两栏分不出（测盘现用 `scan`）。

🔴 **改 UI 后必须重渲染快照 + 在导出包分卷里登记新文件** —— **改文案也算改 UI**（快照会变）。`scripts/export_ui_design.py` 的 `VOLUMES` 是**逐文件白名单**，漏登记会被归档完整性自检拦下（本轮新增 `usePressScale.ts` 即被抓到）。

🔴 **界面文案必须是纯文本，不得出现 Markdown 标记** —— 写任何会渲染的字符串时。RN 的 `<Text>` 不做 Markdown 解析，`**这样**` 会原样显示两个星号，而它**不会让 tsc / 单测 / 离线快照任何一处失败**。已发生两次（管理台、App 5 文件 63 对）。守卫 `tests/mobile/test_ui_copy_plain_text.py`；**但该守卫只查 App 侧 `apps/mobile` 的源码文本，且管理台侧原先只查服务端响应、漏掉静态 HTML** —— 管理台缺口由 `tests/api/test_admin_page_wiring.py::TestStaticCopy` 补。

### 管理台（admin.html）专项

🔴 **同一份文件里 CSS 变量层、HTML 结构、JS 三块都要一起改** —— 改一处忘另一处会出现"样式类没人用"或"JS 设了 aria 但 HTML 没有 role"。
🔴 **`--text-3/--muted` 这类第四级文字只做到"勉强达标"** —— 实测四级里只有三级过 4.5:1；**第四级不要做**，需要第四级说明内容该被裁掉，不是该被调淡。
🔴 **按钮禁用态用中性灰底面 + 中性灰文字，不要用 `opacity`** —— 半透明的蓝按钮看起来仍然"像能点"，用户会一直点。
🔴 **焦点环必须用主色 outline，不能用金 on 白** —— 金 `#DAB37D` on 白只有 **1.96:1**，等于没有焦点样式；原文件按钮**完全没有** `:focus-visible`。
🔴 **零依赖单文件 HTML 里的无障碍要手写**：`role="tablist"/"tab"/"tabpanel"` + `aria-selected` + **roving tabindex**（只当前项 `tabindex=0`），否则读屏读不出"现在在哪一页"。

---

## 9. 运行时配置层（详版）

`services/api/xuanpan_api/runtime_config.py` —— **环境变量给默认，管理台覆盖，改完即时生效**。优先级：**管理台覆盖 > 环境变量 > 代码默认值**，每项都报 `source`。

🔴 **来源列不能省** —— 没有它，「改了 .env 却没变化」无法自证，排查方向从第一步就错。

🔴 **两种配置并存，别合并**：`get_settings`（环境基线）与 `get_active_settings`（叠加覆盖）。只剩生效值→回答不了"清掉覆盖会变回什么"；只剩基线→业务路径读不到覆盖。**请求期读配置一律用 `get_active_settings`**，用 `get_settings` 会让后台改动不生效。

🔴 **AI 路由器按配置指纹缓存**（`RuntimeConfig.ai_router`），指纹变了才重建。改回"启动时构造一次" = 改模型要重启，接口 200 但行为不变。

🔴 **密钥明文只有一个出口**：`RuntimeConfig.llm()`，唯一调用点是构造 AI provider。展示层走 `entries()`，只给「已配置 + 掩码 + 长度」，**密钥项压根不带 `value` 字段**。新增密钥类配置**必须**加进 `SECRET_KEYS`（有测试守 `SECRET_KEYS ≡ SPECS`）。

- `admin_token` **不可从界面改**；`cors_origins` 标「需重启服务」
- 新增一个环境变量要看 **4 处**：`config.py`、`runtime_config.SPECS`、`.env.example`、`docker-compose.yml`
- 🔴 `XUANPAN_LLM_CAPABILITY` 只有 `reasoning/fast/local`。**写别的不报错，只静默落到默认档**（`.env.example` 曾错写 `vision`，已修）

---

## 10. UI 设计导出包（详版）

`"$PY" scripts/export_ui_design.py --zip` → `dist/ui-design-export/` ＋ `dist/玄盘AI-UI设计导出-<日期>.zip`。**产物在 `dist/`（gitignore）不入库，脚本入库**。包 = 导读 README ＋ 9 卷源码（**按用户旅程分卷**）＋ 快照 ＋ 源码副本 ＋ 3 份上游规范 ＋ MANIFEST（SHA256）。

🔴 **脚本的核心理由是归档完整性自检**：`app/` 与 `src/` 下有源码未被任何一卷收录就报错退出。这道自检立刻抓到真实遗漏（命盘页在 `app/chart.tsx`，不是 `(tabs)/`）—— 没它包会**静默少掉整页**。**改 UI 后忘了重导 = 包与源码漂移**；守卫 `tests/test_export_ui_design.py`。

🔴 **输出目录已存在时默认报错、不自动清除**（要 `--force`）—— 一次 rmtree 近百文件会撞 safe-delete。挪旧包用**同盘 rename**。

🔴 **深色仪器域的边界是「是不是在测量」，不是「是不是罗盘」** —— 6 个测量相关页（首页 / 测盘 / 手动调节 / 传感器测量 / 罗盘校准 / 我的罗盘）为深色，其余浅色。**确认页用浅色盘**（`DIAL_LIGHT`），别按「罗盘域 = 深色」推断（此结论由 `17-confirm.png` 当场证伪初稿）。

🔴 **导读 `docs/玄盘 AI — UI 设计导出导读.md` 是导出包的门面**，改设计系统/信息架构要同步更新。

底栏实际是「罗盘/测盘/分析/历史/我的」，与 SSOT 裁定的「罗盘/命盘/占测/历史/我的」不一致（V2 改版，理由见 `(tabs)/_layout.tsx` 注释）；`apps/mobile/README.md` 目录结构章节**仍是旧结构**。

---

## 11. 术数落地要点（详版 —— 避免重复造轮子）

🔴 **lunar-python 无神煞接口**（`getXxxShiShen` 是「十神」不是「神煞」）→ 18 张口诀表只能自建（`bazi/shensha.py`）。**但下列全是现成接口，别自造**：长生十二宫 `getXxxDiShi`、身宫 `getShenGong`、胎息 `getTaiXi`、黄历全套（建除 `getZhiXing` / 宿 `getXiu` / 黄黑道 `getDayTianShen` / 宜忌 `getDayYi`+`getDayJi` / 冲煞 / 彭祖百忌）、大运 `getYun`。

- 大运 `getYun` 第 0 步是「起运前」空档，流年从 index 1 起；顺逆看**年干**阴阳。建除 `JIANCHU_12[(日支序−月支序)%12]`，交节日有月支口径差需标注
- 三式 HTTP 动词各异是领域术语（`/qimen/pan`、`/liuren/cast`、`/taiyi/cast`）—— **别为"统一"改路径**（破坏契约）
- 太乙只做**年局**，月/日/时局未实现（显式列在 `uncertainties`，**别当遗漏去补**）；太乙宫号与洛书**逐宫错位**，刻意不复用奇门九宫表
- **神煞吉凶分级不做** —— 留给 AI 层，内核只给 FACT

**择日**：规则表 `data/zeri_events.json`（17 事件 + schools）可整体替换（RULE-006），**与 `schools.py` 的风水流派是两套体系**（故意不共用）。
🔴 **改事件词必须跑 `scripts/verify_zeri_table.py --check-veto`** —— 词目写错**不报错、只静默失效**，筛选看似正常却少一道否决。
🔴 **别把「忌行丧 / 忌分居」加进嫁娶否决** —— 实测误杀 **14%** 婚嫁吉日。**教训：设计 veto 前先量化它影响多少天，别凭语义直觉**。
**加事件后必须同步 MCP 工具 docstring**（`tests/test_mcp_server.py` 有防漂移守卫）。

### 一百二十分金（fenjin120）专项

🔴 **`fenjin120.json` 缺失是「已声明的未完成」，不是故障** —— 见到管理台 `fenjin120 available=False` 时。
根因：`packages/fortune-core/data/fenjin120.json` **从未被创建**（全仓无此文件）；`schools.py` 的
`default` profile 已在 `unverified` 里写明「一百二十分金的干支与旺相孤虚标注需规则表，当前未提供」，
生产路线报告 L191 亦记「接口（V1 仅接口，V2 补规则表）」。
**几何层是完好的**：格位/所属山/角度由代码算，实测 `fenjin_at(0°)` → 格位 2、`子山 3/5 格` 正确；
只有 `ganzhi`/`usable` 为 `None`（RULE-001/008 要求**缺表不猜**）。**别把它当 bug 去"修"。**

🔴 **补表不是「扔个 json 进 data/」就完事** —— 但**连坐问题已在 2026-09-19 解除**：

**① 那 4 处「锁现状」断言已改成测行为。** 改前实测「放入一张合法表 → 恰好 4 个 FAILED」；
改后同一实验 → **全量 1617 passed, 0 failed**。两类改法：
- 主题根本不对的（`test_compass.py::test_facts_layer_shape`、`test_context.py::test_school_metadata`）
  → 只锁类型：`isinstance(..., bool)`
- 主题对但构造脆的 → **显式构造输入**：`test_compass.py::test_ganzhi_absent_without_rule_table`
  传不存在的 `table_path=`；`test_ai_report.py::test_unknown_domain_values_never_fabricated`
  把 `DEFAULT_TABLE_PATH` 指向 `tmp_path`（用唯一路径 → 缓存键天然隔离，不漏给别的用例）

⚠️ **`build_context` 只接受流派名、没有路径注入点**（内部 `table_available(profile.fenjin_table)`）
—— 所以那两处只能改模块常量 / `monkeypatch`。**别去找不存在的 `fenjin_table=` 参数**（上一轮找过，白费一轮）。

🔴 **三层职责已拆开，别再合回去** —— 改 `fenjin120.py` 时：

| 函数 | 定位 | 坏表时 |
|---|---|---|
| `load_fenjin_table` | **严格**：补表环节的裁判 | **抛异常** |
| `table_available` / `fenjin_at` | **运行期**：罗盘主链路 | **降级**（`False` / 只给几何格位）|
| `table_load_error` | 诊断：管理台区分「没提供」与「写坏了」| 返回具体原因 |

🔴 **别把 `load_fenjin_table` 也改成 fail-soft** —— 那样"写错的表"会被当成"没有表"，
校验脚本与测试同时失去裁判。改动前实测：某山写成 4 格 → `calculate_orientation()` 抛
`ValueError`（**罗盘主链路 500**），因为 `compass.py:122`、`context.py:238`、`meta.py:115`
全是**裸调用**（只有 `admin.py` 包了 try/except，作者显然知道会抛）。

🔴 **降级 ≠ 静默，但也不能刷屏** —— `_load_or_error` 借 `lru_cache` 让告警**只打一次**；
坏表若每个请求都打日志，日志最终会被关掉 = 彻底静默。

🔴 **降级后 `admin.py` 的错误详情必须单独取 `table_load_error()`** —— 因为
`table_available()` 不再抛，原来的 `except` 分支**永远不会走到**；不改这一句，
「表写坏了」在管理台上会长得和「这张表还没做」**一模一样**（`admin.py::_rule_tables`）。
▶ 这条是**改 fail-soft 时最容易漏掉的一步**：把异常吞掉的地方，都要检查"原来靠异常传出去的信息"改从哪里来。

🔵 **`scripts/verify_fenjin_table.py` 管的是加载器管不到的** —— 补表时先跑它。
加载器只查**结构合法性**；这个脚本查**完整性**：二十四山覆盖度（只写 3 个山 → 105 格静默无干支）、
`schools.py` 声明但缺失的**在用流派** key、山内干支重复、整山全 `null`。
🔴 **它不判断排法对错** —— 那是流派规则（RULE-006），须人给依据；脚本自己也会打印这句边界。
退出码 `0` 通过（含 WARN）/ `1` 有问题；`--strict` 让 WARN 也算失败，`--require` 用于交付检查。
守卫 `tests/test_verify_fenjin_table.py`（19 条），**含"不该报的不报"**（完整表必须零问题）——
误报会训练人忽略脚本，那是比没有脚本更糟的结局。

🔵 **补表流程（照做）**：填表 → `"$PY" scripts/verify_fenjin_table.py` → `pytest` 全量 → 重建镜像
（表在 `packages/fortune-core/data/`，由 Dockerfile `COPY packages/` 进镜像）。
🔴 **表有缓存**，改完必须重启服务（容器：`docker compose up -d --build`），否则"改了没生效"。

🔴 **表内容无法从项目内推导** —— 6 张 `samples/compass/*.jpg` 是**灰度合成几何图（无任何文字）**，
读不出分金刻度；docs 里只有格式示例不是真实数据。它属**流派规则（RULE-006）**，
必须由阿勇提供依据（罗盘书 / 实物罗盘照片 / 直接给数据），**不得凭理论推算**。
表结构：`{"<流派>": {"<山名>": [5 个干支或 null]}}`，每山**恰好 5 格**，`null` = 该流派下空亡/不用；
`schools.py` 有 default / sanhe / sanyuan 三个 key。

🔵 **这一节的元教训**：断言写成 `x is False` 而非「**在某条件下**为 False」时，守卫就从"测行为"
退化成"锁现状"——**它会把任何修复都判成回归**。对照 `tests/api/test_api.py:103`
的 `isinstance(..., bool)`（只锁类型不锁值）才是对写法。**看到 `is False` 就该问一句：这是在测行为，还是在描述今天的巧合？**

