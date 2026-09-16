# 罗盘 AI 风水命理 APP 项目完整设计文档
## 项目代号：玄盘 AI（XuanPan AI）
> 定位：物理罗盘视觉识别 × 确定性术数计算 × 八字 × 六爻 × 灵签 × 姓名/起名 × AI 解释的移动端应用  
> 文档版本：V1.0  
> 目标：可直接交给 Codex / Claude Code / Gemini 作为项目实施蓝图

---

## 1. 项目定位

玄盘 AI 不是一个单纯的“AI 算命聊天 App”，而是一套：

**拍摄实体罗盘 → 识别罗盘关键数据 → 用户确认 → 程序精确计算 → 结合生辰八字/事由 → AI 生成解释报告**

的混合系统。

核心工程原则：

> **AI 负责看、理解、解释；代码负责算、校验、映射。**

严禁让 LLM 自行完成关键历法、角度、二十四山、分金等确定性计算。

---

# 2. 核心产品闭环

```text
用户
 │
 ├── 拍摄罗盘
 │       ↓
 │   图像预处理
 │       ↓
 │   视觉模型识别
 │       ↓
 │   坐山 / 向山候选结果
 │       ↓
 │   用户确认 / 修正
 │
 ├── 输入出生信息
 │       ↓
 │   八字排盘引擎
 │
 ├── 输入所问事由
 │       ↓
 │
 └──────────────┐
                ↓
        ┌───────────────┐
        │ 术数计算内核   │
        │ 二十四山       │
        │ 坐向关系       │
        │ 分金            │
        │ 五行            │
        │ 八字            │
        │ 六爻/灵签       │
        └───────┬───────┘
                ↓
        Structured Context
                ↓
             LLM
                ↓
       结构化 AI 解读报告
                ↓
       用户继续追问 / 分享
```

---

# 3. 与 suanming-mcp 的功能整合

参考项目：

`https://github.com/Enoch666/suanming-mcp`

该项目目前采用 MCP Server 架构，并提供六类工具：

- `fortune_bazi`：八字排盘
- `fortune_liuyao`：六爻起卦
- `fortune_qian`：灵签
- `fortune_name`：姓名分析
- `fortune_mingming`：起名
- `fortune_coder`：程序员黄历

其 README 明确采用“确定性工具 + HTML 报告”的模式，并将八字、六爻、抽签、姓名、起名等能力拆分为独立工具。源码入口也采用独立 tool module 注册 MCP Server。  
本项目不建议直接把 MCP Server 当作手机 App 后端，而应：

**提取其可复用的术数数据结构/算法思想 → 重构为独立 `fortune-core` → App/API/MCP 三端共用。**

参考依据：
- suanming-mcp README：`fortune_bazi / fortune_liuyao / fortune_qian / fortune_name / fortune_mingming / fortune_coder`。 
- suanming-mcp `src/index.ts`：六个工具通过 MCP Server 注册，并分别调用 `tools/bazi.ts`、`liuyao.ts`、`qian.ts`、`name.ts`、`mingming.ts`、`coder.ts`。

---

# 4. 产品功能矩阵

| 模块 | V1 | V2 |
|---|---:|---:|
| 罗盘拍照 | ✅ | |
| AI 识别坐山/向山 | ✅ | |
| 用户手动修正 | ✅ | |
| 二十四山 | ✅ | |
| 八字排盘 | ✅ | |
| 五行统计 | ✅ | |
| 坐向关系 | ✅ | |
| 一百二十分金 | △ 基础 | ✅ 完整 |
| 纳音 | △ | ✅ |
| 净阴净阳 | △ | ✅ |
| AI 事由解读 | ✅ | |
| 报告生成 | ✅ | |
| 历史命盘 | ✅ | |
| 六爻 | | ✅ |
| 灵签 | | ✅ |
| 姓名分析 | | ✅ |
| 起名 | | ✅ |
| 多轮追问 | | ✅ |
| MCP | | ✅ |
| 专业罗盘全圈层 OCR | | V3 |
| 多品牌罗盘适配 | | V3 |

---

# 5. MVP 必须控制的范围

第一版不要识别整个罗盘。

只识别：

1. 罗盘中心区域
2. 天池
3. 鱼丝线
4. 二十四山
5. 坐山
6. 向山

例如：

```json
{
  "mountain": "午",
  "direction": "子",
  "confidence": 0.91,
  "source": "vision",
  "userConfirmed": false
}
```

然后进入确认页：

```text
AI 识别结果

坐山：午
向山：子

AI 置信度：91%

[确认]
[重新拍摄]
[手动选择]
```

---

# 6. 罗盘视觉识别架构

## 6.1 不采用传统 OCR 作为第一入口

传统 OCR 对罗盘存在以下问题：

- 同心圆文字密集
- 文字尺寸很小
- 字体旋转
- 径向排列
- 透视变形
- 反光
- 鱼丝线遮挡
- 罗盘品牌和盘式差异
- 阴阳、干支、八卦、二十四山混排

因此 V1：

```text
Camera
 ↓
图像质量检测
 ↓
透视校正
 ↓
圆心/罗盘边缘检测
 ↓
ROI 截取
 ↓
Vision LLM
 ↓
结构化 JSON
 ↓
确定性规则校验
 ↓
用户确认
```

---

# 7. 图像预处理

客户端先完成：

### 7.1 清晰度检测

```text
Laplacian Variance
```

如果低于阈值：

```text
照片过于模糊，请重新拍摄
```

### 7.2 反光检测

检测大面积高亮区域。

### 7.3 透视校正

四点/圆形边缘检测。

目标：

```text
原始照片
   ↓
梯形
   ↓
近似正圆
```

### 7.4 自动裁剪

只将罗盘主体送给视觉模型。

---

# 8. Vision Prompt 设计

必须明确：

```text
你是罗盘图像信息提取器。

你的任务不是进行风水推理。

只识别图片中实际印刷/显示的文字和鱼丝线指向位置。

禁止：
1. 根据风水理论猜测
2. 根据八字补全文字
3. 根据上下文纠正图片中的文字
4. 将“可能是”输出成确定值

如果无法确认，返回 null。

重点识别：
- 二十四山
- 鱼丝线所对应的山
- 坐山
- 向山

输出严格 JSON。
```

输出：

```json
{
  "compass_detected": true,
  "center": {
    "x": 512,
    "y": 510
  },
  "mountain_candidates": [
    {
      "name": "午",
      "angle": 180,
      "confidence": 0.92
    }
  ],
  "direction_candidates": [
    {
      "name": "子",
      "angle": 0,
      "confidence": 0.95
    }
  ],
  "printed_text": [],
  "uncertain_regions": [],
  "needs_user_confirmation": true
}
```

---

# 9. 二十四山计算核心

建立唯一标准表：

```text
子
癸
丑
艮
寅
甲
卯
乙
辰
巽
巳
丙
午
丁
未
坤
申
庚
酉
辛
戌
乾
亥
壬
```

但必须注意：

**二十四山的排列、角度、坐向定义必须作为领域配置，而不是散落在 UI 或 LLM Prompt 中。**

建立：

```ts
interface TwentyFourMountain {
  id: string
  name: string
  angle: number
  element: FiveElement
  yinYang: "yin" | "yang"
  branch?: string
  stem?: string
  gua?: string
}
```

---

# 10. 坐向模型

```ts
interface CompassOrientation {
  sittingMountain: string
  facingMountain: string

  sittingAngle: number
  facingAngle: number

  exactDegree?: number

  confidence: number
  confirmedByUser: boolean
}
```

必须做：

```text
坐山 ≠ 向山
```

以及：

```text
坐山与向山应处于相对方向关系
```

如果识别结果不符合基本几何关系：

```text
⚠️ 当前识别结果存在方向冲突
请重新确认
```

---

# 11. 一百二十分金

V1 可先抽象为：

```ts
interface FenjinResult {
  degree: number
  stem?: string
  branch?: string
  naYin?: string
  element?: string
  status?: string
}
```

V2 再加入完整规则表。

重要原则：

**一百二十分金必须使用程序规则表计算，不能由 AI 推测。**

---

# 12. 八字模块

直接复用 suanming-mcp 的产品思想，但建议重新实现为：

```text
fortune-core
└── bazi
    ├── calendar
    ├── ganzhi
    ├── wuxing
    ├── nayin
    ├── strength
    └── useful-god
```

输入：

```json
{
  "calendar": "solar",
  "year": 1990,
  "month": 5,
  "day": 20,
  "hour": 10,
  "gender": "male",
  "timezone": "Asia/Shanghai"
}
```

输出：

```json
{
  "pillars": {
    "year": "庚午",
    "month": "辛巳",
    "day": "甲子",
    "hour": "己巳"
  },
  "dayMaster": "甲",
  "fiveElements": {
    "wood": 2,
    "fire": 3,
    "earth": 1,
    "metal": 1,
    "water": 1
  }
}
```

---

# 13. 历法引擎

推荐：

- `lunar-python`
- `sxtwl`

二选一作为基础历法引擎。

工程上必须固定：

```text
公历
农历
节气
时区
真太阳时（可选）
夏令时
出生地
```

特别是：

**不能只使用简单公历年月日直接让 LLM 推八字。**

---

# 14. AI Context Protocol

AI 不直接接收原始用户输入。

建立：

```ts
interface FortuneContext {
  compass: CompassContext
  bazi?: BaziContext
  divination?: DivinationContext
  question: QuestionContext
  calculation: CalculationContext
}
```

示例：

```json
{
  "compass": {
    "sitting": "午",
    "facing": "子",
    "degree": 180,
    "fenjin": "庚",
    "nayin": "..."
  },
  "bazi": {
    "year": "...",
    "month": "...",
    "day": "...",
    "hour": "...",
    "dayMaster": "辛",
    "fiveElements": {}
  },
  "question": {
    "category": "事业",
    "text": "最近事业是否适合调整方向？"
  }
}
```

---

# 15. AI 解读层

AI 的职责：

### 可以

- 解释
- 归纳
- 对比
- 组织语言
- 根据事由调整重点
- 多轮回答
- 用通俗语言解释传统术语

### 不可以

- 修改程序计算结果
- 自己重新排八字
- 自己计算角度
- 自己改变坐山
- 把不确定识别结果说成确定
- 把传统术数表达包装成科学事实

---

# 16. AI 输出结构

```json
{
  "summary": "",
  "facts": [],
  "traditionalInterpretation": [],
  "questionAnalysis": [],
  "suggestions": [],
  "uncertainties": []
}
```

UI：

```text
━━━━━━━━━━━━━━━━
玄盘 AI
罗盘 × 八字
━━━━━━━━━━━━━━━━

【盘面事实】

坐山：午
向山：子
分金：庚

【命盘事实】

日主：辛金
五行分布：……

【传统术数解读】

……

【针对你的问题】

……

【参考建议】

……

⚠️ 以上内容属于传统文化娱乐/学习参考
```

---

# 17. 整合 suanming-mcp 的六项能力

## 17.1 八字

直接成为核心模块：

```text
fortune_bazi
```

入口：

```text
命盘 → 八字
```

---

## 17.2 六爻

V2 加入：

```text
问题
 ↓
起卦
 ↓
本卦
 ↓
变爻
 ↓
变卦
 ↓
AI 解读
```

对应：

```text
fortune_liuyao
```

---

## 17.3 灵签

加入：

```text
每日一签
```

以及：

```text
针对当前问题抽签
```

对应：

```text
fortune_qian
```

---

## 17.4 姓名分析

用户可以保存：

```text
命主
姓名
出生信息
```

然后：

```text
fortune_name
```

---

## 17.5 起名

将：

```text
八字五行
+
姓氏
+
性别
+
命名偏好
```

组合。

对应：

```text
fortune_mingming
```

---

## 17.6 程序员黄历

不建议作为核心功能。

可以隐藏为：

```text
实验室
```

保留 suanming-mcp 的趣味属性。

---

# 18. APP 信息架构

底部导航：

```text
┌──────────────────────────────┐
│                              │
│          页面内容            │
│                              │
├──────────────────────────────┤
│ 罗盘 │ 命盘 │ 占测 │ 历史 │ 我的 │
└──────────────────────────────┘
```

## 首页

```text
今日
玄盘

[ 📷 拍摄罗盘 ]

快速功能

八字排盘
六爻
灵签
姓名
起名

最近记录
```

---

# 19. 罗盘扫描页

必须做成“拍照引导工具”，而不是普通相机。

UI：

```text
┌────────────────────────────┐
│        扫描罗盘             │
│                            │
│      ┌────────────┐        │
│      │            │        │
│      │    ○       │        │
│      │  罗盘区域   │        │
│      │            │        │
│      └────────────┘        │
│                            │
│ 保持罗盘完整、避免反光      │
│                            │
│          ●                 │
└────────────────────────────┘
```

---

# 20. AI 识别确认页

```text
AI 已识别

坐山
        午

向山
        子

识别置信度
        92%

[确认结果]

[重新识别]

[手动修改]
```

这是 MVP 的核心信任机制。

---

# 21. 手动罗盘选择器

不要让用户输入复杂角度。

采用：

```text
二十四山环形选择器
```

视觉：

```text
           子
      壬         癸

   亥               丑

  乾                   艮

  戌                   寅

   辛               甲

      酉         卯
```

用户拖动指针即可。

---

# 22. 报告页面

采用“现代东方 + 水墨”的视觉体系。

参考 suanming-mcp 已有的水墨 HTML 思路，但移动端不要照搬网页。

视觉关键词：

```text
宣纸
淡墨
朱砂
圆形罗盘
细线
留白
现代卡片
```

颜色：

```text
#F5F0E8
#2C2416
#C41E1E
#8B7355
```

---

# 23. 技术栈推荐

## APP

推荐：

```text
React Native + Expo
```

如果需要更强原生相机能力：

```text
React Native
+ VisionCamera
```

---

# 24. 后端

推荐：

```text
Python FastAPI
```

结构：

```text
API
 ↓
Fortune Service
 ↓
fortune-core
 ↓
AI Adapter
```

---

# 25. 数据库

推荐：

```text
PostgreSQL
```

主要表：

```text
users
profiles
birth_profiles
compass_scans
compass_results
bazi_charts
fortune_sessions
fortune_reports
questions
conversation_messages
```

---

# 26. 缓存

```text
Redis
```

用途：

- AI 请求缓存
- OCR/视觉结果缓存
- 六爻结果缓存
- 灵签结果
- 限流
- 会话状态

---

# 27. 对象存储

照片不能直接长期塞数据库。

采用：

```text
S3 / MinIO
```

结构：

```text
user/
 └── compass/
      └── yyyy/mm/dd/
```

默认：

```text
原始照片短期保存
用户确认后可选择删除
```

---

# 28. AI Provider 抽象

不要绑定单一模型。

```ts
interface VisionProvider {
  analyzeCompass(image: Image): Promise<CompassVisionResult>
}

interface LLMProvider {
  interpret(context: FortuneContext): Promise<FortuneReport>
}
```

支持：

```text
OpenAI
Claude
Gemini
DeepSeek
本地模型
```

未来可以根据成本/质量动态切换。

---

# 29. MCP 架构

未来提供：

```text
xuanpan-mcp
```

Tools：

```text
scan_compass
calculate_orientation
fortune_bazi
fortune_liuyao
fortune_qian
fortune_name
fortune_mingming
interpret_fengshui
```

这样：

```text
手机 APP
      │
      ├── REST API
      │
      └── fortune-core
                 ↑
              MCP Server
                 ↑
          Claude / Codex / Agent
```

实现“一套计算内核，多种入口”。

---

# 30. 项目目录

```text
xuanpan-ai/
│
├── apps/
│   ├── mobile/
│   │   ├── app/
│   │   ├── components/
│   │   ├── screens/
│   │   ├── camera/
│   │   └── services/
│   │
│   └── admin/
│
├── services/
│   ├── api/
│   │   ├── routers/
│   │   ├── schemas/
│   │   └── services/
│   │
│   ├── vision/
│   │   ├── preprocess/
│   │   ├── compass/
│   │   └── providers/
│   │
│   └── ai/
│       ├── prompts/
│       ├── providers/
│       └── context/
│
├── packages/
│   └── fortune-core/
│       ├── bazi/
│       ├── ganzhi/
│       ├── wuxing/
│       ├── compass/
│       ├── mountain24/
│       ├── fenjin120/
│       ├── liuyao/
│       ├── qian/
│       ├── name/
│       └── naming/
│
├── mcp/
│   └── xuanpan-mcp/
│
├── data/
│   ├── compass/
│   ├── qian/
│   └── naming/
│
├── tests/
│   ├── bazi/
│   ├── compass/
│   ├── fenjin/
│   └── vision/
│
├── docs/
│
├── docker-compose.yml
├── AGENTS.md
└── README.md
```

---

# 31. 最重要的数据模型

## CompassScan

```ts
interface CompassScan {
  id: string
  imageUrl: string

  detected: boolean

  sittingMountain?: string
  facingMountain?: string

  degree?: number

  confidence?: number

  visionRaw?: unknown

  userConfirmed: boolean

  createdAt: string
}
```

---

# 32. 计算层必须可测试

例如：

```text
输入：

坐山 = 午
向山 = 子

输出：

坐向关系
二十四山
阴阳
五行
分金
纳音
```

测试：

```python
def test_zi_wu_orientation():
    result = calculate_orientation("午", "子")
    assert result.facing == "子"
```

禁止：

```text
LLM → 判断正确答案
```

必须：

```text
Rule Engine → 正确答案
```

---

# 33. AI 幻觉防护

每个 AI 报告分成：

### FACT

程序计算：

```text
坐山
向山
角度
八字
五行
分金
```

### TRADITION

传统术数规则：

```text
净阴净阳
纳音
生克
传统解释
```

### AI_INTERPRETATION

LLM：

```text
语言组织
问题关联
叙事
解释
```

### UNCERTAINTY

```text
识别不确定
规则存在流派差异
用户未确认
```

---

# 34. 流派差异处理

风水命理存在不同流派。

因此不要把：

```text
某一流派规则
```

写死到核心系统。

建立：

```ts
interface SchoolProfile {
  id: string
  name: string

  compassRules: RuleSet
  fenjinRules: RuleSet
  baziRules: RuleSet
  interpretationRules: RuleSet
}
```

例如：

```text
default
sanhe
sanyuan
traditional
custom
```

第一版只开放：

```text
默认规则
```

内部保留扩展接口。

---

# 35. 用户体验核心

整个产品必须遵循：

```text
机器识别
 ↓
用户确认
 ↓
程序计算
 ↓
AI 解读
```

不要：

```text
拍照
 ↓
AI 自己猜
 ↓
直接给结论
```

---

# 36. 用户可追问

报告完成后：

```text
你还可以继续问：

“这个坐向对事业怎么看？”

“如果用于住宅呢？”

“结合我的八字再看看？”

“换一个流派分析会有什么不同？”
```

AI 只能基于当前：

```text
FortuneContext
```

回答。

---

# 37. 历史记录

每次分析保存：

```text
罗盘照片
↓
识别结果
↓
用户修正
↓
计算结果
↓
AI 报告
↓
追问
```

这样用户以后可以：

```text
再次打开
继续追问
重新生成报告
更换 AI 模型
```

---

# 38. 隐私设计

生辰信息属于高敏感个人信息，应采用最小化保存原则。

默认：

```text
出生信息：
本地加密 / 服务端加密
```

用户可以：

```text
删除命盘
删除照片
删除历史记录
```

罗盘照片建议提供：

```text
分析完成后自动删除原图
```

---

# 39. 商业化设计

V1：

```text
免费：
3次罗盘识别
3次 AI 解读
```

Pro：

```text
无限命盘
历史记录
深度报告
多轮追问
六爻
灵签
姓名
起名
```

专业版：

```text
完整罗盘
120分金
多流派
批量分析
PDF报告
```

---

# 40. 成本控制

最贵的是：

```text
Vision
LLM
```

因此：

```text
客户端预处理
 ↓
减少上传图片尺寸
 ↓
先传统 CV
 ↓
再 Vision
 ↓
只有必要时调用 LLM
```

并缓存：

```text
相同图片
相同 Context
相同问题
```

避免重复调用。

---

# 41. MVP 开发阶段

## Phase 0：计算内核

先完成：

```text
二十四山
坐向
八字
五行
基础分金
```

没有 APP。

---

## Phase 1：罗盘识别 Demo

只做：

```text
拍照
 ↓
AI
 ↓
坐山
 ↓
向山
 ↓
人工确认
```

目标：

**验证视觉识别是否达到可用水平。**

---

## Phase 2：AI 命理解读

加入：

```text
八字
+
坐向
+
事由
```

生成报告。

---

## Phase 3：移动端 MVP

实现：

```text
首页
扫描
确认
命盘
报告
历史
```

---

## Phase 4：suanming-mcp 功能整合

加入：

```text
六爻
灵签
姓名
起名
```

---

## Phase 5：MCP

发布：

```text
xuanpan-mcp
```

---

# 42. 第一版验收标准

## 罗盘

- [ ] 能拍照
- [ ] 能判断是否检测到罗盘
- [ ] 能识别二十四山候选
- [ ] 能输出置信度
- [ ] 能人工修改
- [ ] 能保存最终结果

## 八字

- [ ] 公历
- [ ] 农历
- [ ] 四柱
- [ ] 五行
- [ ] 日主
- [ ] 时区

## AI

- [ ] 不计算八字
- [ ] 不修改坐山
- [ ] 不猜测图片
- [ ] 输出结构化结果
- [ ] 明确区分事实和解读

## APP

- [ ] 扫描页
- [ ] 确认页
- [ ] 报告页
- [ ] 历史页
- [ ] 删除数据

---

# 43. AGENTS.md 核心开发规则

Codex / Claude Code 必须遵循：

```text
RULE-001
确定性计算必须由代码完成。

RULE-002
LLM 不得修改计算层输出。

RULE-003
视觉模型无法确认时必须返回 null。

RULE-004
所有 AI 识别结果必须允许用户修正。

RULE-005
罗盘规则不得散落在 UI。

RULE-006
流派规则必须模块化。

RULE-007
所有核心算法必须有单元测试。

RULE-008
不得为了“看起来合理”而修正用户数据。

RULE-009
任何领域规则变更必须同步更新测试。

RULE-010
医疗、投资、法律等问题不得伪装成命理确定性结论。
```

---

# 44. 推荐实施顺序

最关键的一点：

**不要先开发完整 APP UI。**

正确顺序：

```text
① fortune-core
        ↓
② 罗盘视觉识别 Demo
        ↓
③ 用户确认机制
        ↓
④ AI Context Protocol
        ↓
⑤ AI 报告
        ↓
⑥ 移动端 UI
        ↓
⑦ 六爻/灵签/姓名/起名
        ↓
⑧ MCP
        ↓
⑨ 商业化
```

---

# 45. 最终产品形态

最终玄盘 AI 可以形成：

```text
                 玄盘 AI
                    │
        ┌───────────┼───────────┐
        │           │           │
      视觉        计算          AI
        │           │           │
      罗盘        八字          解读
      OCR        二十四山       报告
      CV         分金           追问
                 六爻
                 灵签
                 姓名
                 起名
        │           │           │
        └───────────┼───────────┘
                    │
              Fortune Context
                    │
              ┌─────┴─────┐
              │           │
             APP         MCP
```

这套架构的核心价值不是“让 AI 更会算命”，而是：

> **把实体罗盘这种传统人工工具，转换成结构化数字数据，再利用确定性计算和 AI 语言能力完成现代化交互。**

---

# 46. 最终技术原则

### 第一原则

**罗盘是数据入口，不是 AI 猜谜游戏。**

### 第二原则

**算法内核与 AI 解读彻底解耦。**

### 第三原则

**任何关键结果都必须能够追溯到具体计算规则。**

### 第四原则

**AI 识别必须允许人工纠错。**

### 第五原则

**suanming-mcp 的六项能力应该作为 Fortune Core 的功能模块吸收，而不是把整个 MCP 项目硬塞进 APP。**

### 第六原则

**APP、Web、MCP、未来 Agent 全部共享同一套 Fortune Core。**

---

## 47. 推荐项目名称

中文：

**玄盘 AI**

副标题：

**一盘入局，AI 解盘**

英文：

**XuanPan AI**

内部项目：

```text
xuanpan-ai
fortune-core
xuanpan-mcp
```

---

## 48. 参考项目

- `suanming-mcp`：传统命理 MCP Server，提供八字、六爻、灵签、姓名、起名、程序员黄历等工具。
- 项目 README：包含工具定义、安装方式、HTML 报告模式与项目结构。
- `src/index.ts`：展示 MCP Server 的工具注册与调用方式。

原项目：
`https://github.com/Enoch666/suanming-mcp`

**License：使用其代码时必须遵循原项目 LICENSE；若仅借鉴架构/产品思路，则仍应独立实现核心代码并保留来源说明。**

---

# 49. 给 Codex / Claude Code 的第一条任务

```text
你现在开始开发 xuanpan-ai。

不要先开发完整 UI。

第一阶段只完成 fortune-core。

任务顺序：

1. 创建 monorepo
2. 创建 packages/fortune-core
3. 实现二十四山数据模型
4. 实现坐山/向山模型
5. 实现角度与二十四山映射
6. 实现八字数据模型
7. 接入可靠历法库
8. 实现五行统计
9. 创建 Fenjin120 接口
10. 创建统一 FortuneContext
11. 编写完整单元测试
12. 创建 REST API 骨架
13. 创建 VisionProvider 接口
14. 创建 LLMProvider 接口

禁止：

- 先做 UI
- 把计算交给 LLM
- 把规则写进 Prompt
- 使用随机结果冒充真实计算
- 为了通过测试硬编码答案

完成后输出：

- 项目目录
- 已完成模块
- 测试结果
- 尚未完成模块
- 下一步实施计划
```

---

## 50. 结论

**这款 APP 最值得做的不是“AI 算命”，而是“罗盘数字化”。**

因此第一阶段真正应该验证的是：

> **普通用户拿手机拍一张真实罗盘照片，系统能否稳定识别鱼丝线对应的二十四山，并让用户在 3 秒内确认。**

只要这一入口成立，后面的：

```text
八字
+
二十四山
+
分金
+
五行
+
六爻
+
灵签
+
AI
```

都可以逐步叠加。

而 `suanming-mcp` 最适合承担的是第二层能力：**把已有的八字、六爻、灵签、姓名、起名能力沉淀为 Fortune Core，并进一步通过 MCP 暴露给 Claude / Codex / Agent。**

> **最终架构：Camera → Vision → Human Confirm → Fortune Core → Fortune Context → AI → Report → Multi-turn Agent。**
