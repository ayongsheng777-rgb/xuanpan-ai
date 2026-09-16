# xuanpan-api · 后端服务

玄盘 AI 的接口层。**只做 HTTP 语义、输入校验、持久化与装配**，
不做任何术数计算（`fortune_core`）、图像识别（`xuanpan_vision`）或文本生成（`xuanpan_ai`）。

## 快速启动

```bash
# [Host] 项目根目录
PYTHONPATH='services/api;services/ai;services/vision;packages/fortune-core' \
  python -m uvicorn xuanpan_api.app:create_app --factory --host 127.0.0.1 --port 8360
```

或：

```bash
PYTHONPATH='...' python -m xuanpan_api      # 读 XUANPAN_PORT，默认 8352
```

> ⚠️ **8352 已被本机 SysCenter 占用**，本地联调请用 8360 等其它端口。

文档：<http://127.0.0.1:8360/docs>

## 端到端冒烟

```bash
python scripts/smoke_api.py --base http://127.0.0.1:8360
```

脚本对**真实运行中的服务**发请求，覆盖：健康检查 → 元信息 → 计算预览 →
合成罗盘识别 → 用户确认 → 增量录入 → 生成报告 → 多轮追问 → 历史 → 错误路径 → 删除。
退出码 0 = 全通过。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `XUANPAN_DB_PATH` | `./data/xuanpan.db` | SQLite 库位置 |
| `XUANPAN_MAX_UPLOAD_MB` | `12` | 上传图片上限 |
| `XUANPAN_KEEP_PHOTOS` | `false` | **是否保留原图**。默认 false：原图只在内存过一遍，落库的只有结构化识别结果 |
| `XUANPAN_PHOTO_DIR` | `./data/uploads` | 原图落盘目录（仅 `KEEP_PHOTOS=true` 时使用） |
| `XUANPAN_AI_MODE` | `auto` | `auto` / `cost` / `quality` |
| `XUANPAN_CORS_ORIGINS` | `*` | 逗号分隔 |
| `XUANPAN_PORT` | `8352` | 仅 `python -m xuanpan_api` 使用 |

红线：`.env` 与 `data/` 属重建禁区（AGENTS.md §6），本服务**只读**环境，不生成任何凭据文件。

## 接口一览（前缀 `/api/v1`）

### 元信息（不触发计算）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/meta/mountains` | 二十四山标准表 + 角度约定（0°=正北、顺时针） |
| GET | `/meta/schools` | 流派清单与可用性 |
| GET | `/meta/question-categories` | 问题类别 + 敏感类别（触发额外免责） |
| GET | `/meta/disclaimer` | 统一免责声明 |
| GET | `/meta/ai-providers` | AI 模型能力矩阵 + 端点预设 + 可用性 |
| GET | `/meta/vision-providers` | 识别 provider 能力矩阵 |
| GET | `/meta/qian-sets` | 可用签库（`demo=true` 为演示签） |
| GET | `/meta/capabilities` | 规则表就绪状态（如分金干支表） |

### 识别（双入口合一）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/scan` | `multipart/form-data` 上传罗盘照片 → 候选坐向 |

- 相机拍照与相册选图在客户端是不同的系统能力，服务端只有这一个入口
- 返回 `needs_user_confirmation` **恒为 true**（RULE-004）：几何识别无法判断哪一端是坐山
- 模糊 / 过曝 / 未找到盘体 → `compass_detected=false` + `uncertain_regions` 说明原因，候选为空（RULE-003）

### 计算预览（无状态、不落库）

`POST /calc/{compass|bazi|liuyao|qian|naming}` → `{facts, tradition, uncertainties}`

### 会话

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/sessions` | 新建会话 |
| GET | `/sessions` | 列表（含每会话报告数） |
| GET | `/sessions/{id}` | 详情：已录入模块 + 两层结果 + 不确定性 |
| PATCH | `/sessions/{id}/inputs` | 增量录入（**先全部构造成功再落库**，保证原子性） |
| POST | `/sessions/{id}/compass/confirm` | **确认坐向 —— RULE-004 闸门** |
| DELETE | `/sessions/{id}` | 删除会话（级联报告与对话） |

### 报告与多轮

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/sessions/{id}/report` | 生成报告（三层全量落库） |
| POST | `/sessions/{id}/ask` | 多轮追问 |
| GET | `/sessions/{id}/reports` | 报告列表 |
| GET | `/sessions/{id}/turns` | 对话记录 |
| GET | `/reports/{report_id}` | 读取单份报告 |

## 三条不可让步的设计

**1. 只存用户输入，不存派生结果**

数据库里是"用户给了什么"（生辰、坐向、摇卦结果），不是"算出了什么"。
因为内核是确定性的：同输入必得同输出。好处是**不可能出现"库里一份、内核一份"的双真源**，
内核升级后历史记录自动按新口径重算，而不是留一批旧口径的僵尸数据（并在测试里有断言禁止派生列）。

例外：**AI 报告必须落库** —— 它是外部模型产物，非确定性、不可重算，丢了就没了。

**2. 确认闸门只有一道，且由服务端强制**

`/compass/confirm` 把 `confirmed_by_user` **强制**置 `True`，客户端传 `False` 无效。
识别原件（`recognition` 列）**不被确认结果覆盖** —— 用户改了什么永远可追溯（RULE-008）。

**3. 错误按"谁的错"分流，不混成 500**

| 情形 | 状态码 |
|---|---|
| 契约层不合法（字段名错、类别不在枚举、月份 13） | 422 |
| 输入不成立（山名写错、坐向冲突、角度与坐山矛盾） | 400 |
| 资源不存在 | 404 |
| 图片超限 / 非图像 | 413 / 400 |
| 所有模型失败 | 503 |
| 我们自己的 bug | 500 |

映射只写在 `app.py::_register_error_handlers` 一处，避免"同一个错误两种状态码"。

## 目录

```
services/api/
├── xuanpan_api/
│   ├── app.py               # 应用装配 + 异常翻译（唯一映射点）
│   ├── config.py            # 环境变量 → Settings
│   ├── deps.py              # 依赖注入（存储 / 配置 / AI 路由器）
│   ├── storage.py           # SQLite（只存输入）
│   ├── context_builder.py   # **唯一**与计算层耦合处
│   ├── schemas.py           # 请求 / 响应契约
│   ├── routers/             # meta / scan / calc / sessions / report
│   └── __main__.py          # python -m xuanpan_api
```
