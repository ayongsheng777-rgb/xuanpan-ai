# 玄盘 AI V2 产品改造与实施规范

> 项目：`xuanpan-ai`  
> GitHub：`ayongsheng777-rgb/xuanpan-ai`  
> 产品名称：**玄盘 AI**  
> 版本：**V2.0 产品化改造实施规范**  
> 文档定位：供 Codex / Claude Code / Gemini / WorkBuddy 等 AI 编程智能体执行的产品与工程规范

---

## 1. 产品定位

玄盘 AI V2 不再只是“术数计算 + AI 解读 + 罗盘识别”应用，而是升级为：

> **真实罗盘数字化 + 手机传感器测量 + 数字罗盘仿真 + 视觉识别 + 人工校准 + 确定性计算 + AI 分析 + 测盘档案管理**

核心产品链路：

```text
真实罗盘
   ↓
手机传感器采集
   ↓
拍照 / 导入罗盘照片
   ↓
视觉识别
   ↓
罗盘结构还原
   ↓
数字罗盘显示
   ↓
人工微调 / 校准
   ↓
确定性计算
   ↓
AI 分析
   ↓
测盘档案
```

### V2 核心原则

1. **AI 负责识别、理解、解释，不负责替代确定性计算。**
2. **罗盘数据必须结构化保存，不能只保存一张图片。**
3. **任何 AI / CV 识别结果都允许人工确认和修正。**
4. **原始数据不能被覆盖，修正必须形成历史记录。**
5. **传感器数据、照片数据、人工数据必须可以相互校验。**
6. **现有功能必须保留，V2 以增量改造为主。**
7. **优先稳定、低维护、可扩展架构，不为了技术炫技增加复杂依赖。**

---

# 2. V2 产品目标

## 2.1 用户最终可以完成什么

用户拿着真实罗盘进行测量：

1. 打开玄盘 AI。
2. 手机传感器实时采集方向、姿态、磁场等数据。
3. 将真实罗盘放入拍摄区域。
4. 拍照或者导入已有罗盘照片。
5. 系统识别罗盘类型、圆心、方向、主要盘层。
6. 将真实罗盘还原为 APP 内的数字罗盘。
7. 用户通过旋转、缩放、圆心、角度等参数进行精确校准。
8. 确认坐山、向山、分金等数据。
9. 调用现有确定性术数计算模块。
10. 选择 AI 模型和分析模式。
11. AI 根据结构化测盘数据生成分析报告。
12. 所有结果保存为一份完整的“测盘档案”。

---

# 3. 产品信息架构

V2 底部导航建议调整为：

```text
┌────────┬────────┬────────┬────────┬────────┐
│  罗盘  │  测盘  │  分析  │  档案  │  我的  │
└────────┴────────┴────────┴────────┴────────┘
```

## 3.1 罗盘

定位：

> 实时数字罗盘 + 手机传感器工作台

主要内容：

- 大型数字罗盘
- 当前方位角
- 磁北
- 坐山
- 向山
- 分金
- 磁场强度
- 手机水平状态
- 传感器质量
- 旋转控制
- 锁定控制

快捷操作：

- `扫描真实罗盘`
- `传感器测量`
- `手动罗盘`
- `校准`
- `保存测盘`

---

# 4. 数字罗盘系统

## 4.1 Compass Engine

建立统一罗盘核心模型：

```text
CompassEngine
├── CompassModel
├── CompassRing
├── CompassLayer
├── CompassOrientation
├── CompassCalibration
├── CompassRenderer
└── CompassInteraction
```

## 4.2 CompassModel

建议：

```typescript
interface CompassModel {
  id: string
  name: string
  type: CompassType

  center: {
    x: number
    y: number
  }

  radius: number

  orientation: {
    rotation: number
    north: number
    magneticDeclination?: number
  }

  rings: CompassRing[]

  calibration: CompassCalibration

  source?: {
    type: 'builtin' | 'photo' | 'import' | 'custom'
    imageUri?: string
  }

  createdAt: string
  updatedAt: string
}
```

---

# 5. 罗盘盘层设计

罗盘不能写死为一个 SVG 圆盘。

必须采用：

```text
Compass
 ├── Center
 ├── Heaven Pool
 ├── Ring 01
 ├── Ring 02
 ├── Ring 03
 ├── Ring 04
 ├── Ring ...
 └── Pointer
```

每一个 Ring 都是独立配置。

```typescript
interface CompassRing {
  id: string
  name: string
  type: string
  enabled: boolean

  innerRadius: number
  outerRadius: number

  rotation: number

  labels: CompassLabel[]

  style: {
    fontSize: number
    opacity: number
    lineWidth: number
  }
}
```

---

# 6. 必须支持的数字罗盘操作

## 6.1 手势

- 单指旋转
- 双指缩放
- 双指旋转
- 长按
- 拖动
- 点击盘层

## 6.2 精确调节

必须提供：

```text
-10°
-1°
-0.1°
当前角度
+0.1°
+1°
+10°
```

同时允许：

```text
输入角度：347.28°
```

## 6.3 锁定功能

提供：

- 锁定罗盘
- 锁定磁北
- 锁定中心
- 锁定当前角度
- 锁定盘层
- 解锁全部

---

# 7. 手机传感器系统

## 7.1 SensorService

建立统一传感器服务：

```text
SensorService
├── Magnetometer
├── Accelerometer
├── Gyroscope
├── DeviceMotion
└── Location
```

## 7.2 SensorFusion

将多个传感器转换为统一测量结果：

```typescript
interface SensorSnapshot {
  timestamp: string

  azimuth: number

  pitch: number
  roll: number

  magneticField?: {
    x: number
    y: number
    z: number
    magnitude: number
  }

  accuracy: number

  levelQuality: number
  magneticQuality: number
  overallQuality: number

  source: 'phone'
}
```

---

# 8. 传感器质量判断

不能简单读取手机磁力计就认为数据可信。

必须实时检测：

### 8.1 磁场

检测：

- 当前磁场强度
- 磁场波动
- 磁场异常
- 磁干扰

### 8.2 水平

检测：

- pitch
- roll
- 水平误差

### 8.3 稳定性

连续采样：

```text
t-3
t-2
t-1
t
```

计算：

```text
方向变化
磁场变化
姿态变化
```

形成：

```text
传感器质量：92%
```

## 8.4 用户提示

例如：

```text
✓ 手机水平
✓ 磁场稳定
✓ 当前方向稳定

可以开始测量
```

异常：

```text
⚠ 当前磁场异常

可能原因：
附近存在电脑、音箱、车辆、磁铁或金属结构。

建议：
移动手机 1～2 米后重新测量。
```

---

# 9. 真实罗盘拍照识别

建立：

```text
CompassVisionEngine
```

完整流程：

```text
照片
 ↓
图像质量检测
 ↓
罗盘区域检测
 ↓
圆形检测
 ↓
透视校正
 ↓
圆心检测
 ↓
半径检测
 ↓
盘层检测
 ↓
文字识别 OCR
 ↓
24山识别
 ↓
八卦识别
 ↓
120分金识别
 ↓
方向识别
 ↓
罗盘类型识别
 ↓
结构化 CompassModel
```

---

# 10. 不允许采用“只 OCR”的方案

真实罗盘识别不是简单：

```text
照片 → OCR → 文字
```

必须：

```text
照片
 ↓
几何结构
 ↓
圆心
 ↓
圆环
 ↓
角度
 ↓
文字
 ↓
盘层
 ↓
CompassModel
```

最终 APP 中重新绘制。

---

# 11. 罗盘重建数据模型

示例：

```json
{
  "compass": {
    "type": "三元三合综合盘",
    "diameter": 120,
    "center": {
      "x": 512,
      "y": 512
    }
  },
  "orientation": {
    "north": 0,
    "rotation": 23.72
  },
  "rings": [
    {
      "type": "heaven_stems",
      "enabled": true
    },
    {
      "type": "24_mountains",
      "enabled": true
    },
    {
      "type": "bagua",
      "enabled": true
    },
    {
      "type": "120_fenjin",
      "enabled": true
    }
  ]
}
```

---

# 12. 真实罗盘 → 数字罗盘校准工作台

这是 V2 的核心功能之一。

界面采用：

```text
┌─────────────────────────────┐
│       真实罗盘照片           │
│                             │
│     ┌───────────────┐       │
│     │ 数字罗盘叠加层 │       │
│     └───────────────┘       │
│                             │
└─────────────────────────────┘

透明度 ─────────●────

角度   -0.1°   347.28°   +0.1°

缩放   -        100%      +

圆心   ←  ↑  →  ↓

[确认校准]       [重新识别]
```

## 12.1 必须支持

- 照片透明度
- 数字罗盘透明度
- 旋转
- 缩放
- X/Y 移动
- 圆心调整
- 半径调整
- 透视修正
- 单个盘层开关
- 单层旋转
- 手动修改识别结果

---

# 13. 人工校准优先级

识别结果：

```text
视觉识别：
坐山 = 午
置信度 = 86%
```

用户修改：

```text
坐山 = 丁
```

不能覆盖原数据。

必须保存：

```json
{
  "visionResult": {
    "value": "午",
    "confidence": 0.86
  },
  "userCorrection": {
    "value": "丁",
    "reason": "manual",
    "timestamp": "..."
  }
}
```

---

# 14. 罗盘类型识别

建议支持：

- 三元盘
- 三合盘
- 三元三合综合盘
- 综合盘
- 玄空盘
- 金锁玉关盘
- 传统二十四山盘
- 自定义罗盘

识别结果：

```text
罗盘类型
三元三合综合盘

识别置信度
91%

识别盘层
✓ 二十四山
✓ 八卦
✓ 天干
✓ 地支
✓ 120分金
```

用户可以：

```text
[确认]
[手动修改]
```

---

# 15. 我的罗盘

增加罗盘模板库：

```text
我的罗盘

┌────────────────────┐
│ 李师傅三元盘        │
│ 三元盘              │
│ 已校准              │
└────────────────────┘

┌────────────────────┐
│ 三元三合综合盘      │
│ 综合盘              │
│ 已校准              │
└────────────────────┘

[＋ 创建自定义罗盘]
```

保存内容：

- 罗盘照片
- CompassModel
- 盘层
- 校准参数
- 识别结果
- 用户修正
- 使用次数
- 最近使用时间

---

# 16. 测盘 Session：V2 最重要的数据实体

V2 不应该让“照片、传感器、分析、历史”各自独立。

建立：

```text
MeasurementSession
```

一份测盘就是一份完整档案。

```text
测盘 #20260918-001

来源：
真实罗盘照片 + 手机传感器 + 用户校准

罗盘：
三元三合综合盘

磁北：
347.28°

坐：
午

向：
子

分金：
......

用户修正：
2 次

AI：
DeepSeek

分析：
已完成
```

---

# 17. MeasurementSession 数据结构

```typescript
interface MeasurementSession {
  id: string

  createdAt: string
  updatedAt: string

  source: {
    photo?: string
    sensor: boolean
    manual: boolean
    imported: boolean
  }

  compassModelId?: string

  compassCapture?: CompassCapture

  sensorSnapshot?: SensorSnapshot

  visionResult?: VisionResult

  calibration?: CompassCalibration

  orientation?: OrientationResult

  calculation?: CalculationResult

  aiAnalysis?: AIAnalysis

  attachments?: Attachment[]

  status:
    | 'draft'
    | 'captured'
    | 'calibrated'
    | 'calculated'
    | 'analyzed'
    | 'completed'
}
```

---

# 18. 数据库设计

现有 SQLite 可以继续使用。

建议增加：

```text
sessions
compass_capture
sensor_snapshot
vision_result
compass_model
compass_ring
compass_calibration
correction_history
calculation_result
ai_analysis
attachments
```

关系：

```text
sessions
  ├── compass_capture
  ├── sensor_snapshot
  ├── vision_result
  ├── compass_calibration
  ├── correction_history
  ├── calculation_result
  ├── ai_analysis
  └── attachments
```

---

# 19. 历史档案

原来的“历史”升级为：

> **测盘档案**

列表显示：

```text
2026-09-18 07:32

三元三合综合盘

坐：午
向：子

磁北：347.28°
传感器：92%
识别：91%

AI分析：已完成
```

进入详情：

```text
① 原始照片
② 数字罗盘
③ 传感器数据
④ 视觉识别
⑤ 用户校准
⑥ 确定性计算
⑦ AI分析
⑧ 修改记录
```

---

# 20. AI 分析中心

AI 配置不能只做：

```text
API Key
Model
Prompt
```

必须建立完整 AI Router。

架构：

```text
APP
 ↓
Backend
 ↓
AI Router
 ├── Vision Model
 ├── Reasoning Model
 ├── Fast Model
 └── Fallback Model
 ↓
Provider
```

---

# 21. AI Provider

建议支持统一 OpenAI Compatible 接口，同时允许独立 Provider：

```text
OpenAI Compatible
DeepSeek
Gemini
Claude
MiniMax
Qwen
本地模型
自定义 API
```

每个 Provider：

```typescript
interface AIProvider {
  id: string
  name: string
  baseUrl: string
  apiKeyRef: string
  enabled: boolean

  models: AIModel[]
}
```

---

# 22. API Key 安全

**禁止把真实 API Key 固定写入 APK / React Native 前端。**

推荐：

```text
APP
 ↓
HTTPS
 ↓
Backend
 ↓
AI Router
 ↓
Provider
```

API Key 只保存在服务器安全配置中。

支持：

- 加密存储
- 环境变量
- 权限控制
- 日志脱敏
- 请求审计
- Key 测试
- Provider 启停

---

# 23. AI Model 配置

模型至少记录：

```text
模型名称
Provider
能力
上下文长度
输入方式
输出方式
价格
速度
是否启用
```

能力：

```text
Vision
Reasoning
Text
OCR
Analysis
```

---

# 24. AI 任务路由

例如：

```text
罗盘照片识别
→ Vision Model

复杂综合分析
→ Reasoning Model

快速解释
→ Fast Model

主模型失败
→ Fallback Model
```

不要让每一个页面自己调用 AI。

统一：

```text
AIService
   ↓
AIRouter
   ↓
Provider
```

---

# 25. AI 分析模式

提供：

```text
快速
标准
专业
深度
```

## 快速

适合：

- 当前坐向解释
- 简短说明

## 标准

适合：

- 普通测盘
- 综合判断

## 专业

适合：

- 多盘层
- 多规则
- 多数据源

## 深度

适合：

- 罗盘
- 八字
- 择日
- 三式
- 历史案例
- 用户资料

---

# 26. AI 上下文配置

允许用户控制：

```text
☑ 内置传统资料
☑ 用户资料
☑ 用户上传资料
☑ 指定流派规则
☑ 历史案例
☑ 当前测盘
☑ 八字
☑ 择日
```

---

# 27. AI 输入必须结构化

禁止把整个页面文字拼成 Prompt。

AI 接收：

```json
{
  "compass": {},
  "sensor": {},
  "orientation": {},
  "mountain": {},
  "fenjin": {},
  "school": {},
  "bazi": {},
  "zeri": {},
  "analysis_context": {}
}
```

Prompt 只负责：

```text
任务
规则
输出格式
解释要求
```

---

# 28. 确定性计算与 AI 分工

必须保持：

```text
用户数据
 ↓
确定性计算
 ↓
结构化结果
 ↓
AI解释
```

例如：

```text
APP计算：
坐山 = 午
向山 = 子
角度 = 0°
分金 = XXX
```

AI：

```text
根据上述结构化结果进行解释。
```

不能：

```text
AI自行猜测坐山
AI自行计算角度
AI自行改变结果
```

---

# 29. AI 输出结构

建议：

```json
{
  "summary": "",
  "facts": [],
  "analysis": [],
  "risks": [],
  "recommendations": [],
  "references": [],
  "confidence": 0
}
```

其中：

- facts = 已确定数据
- analysis = AI解释
- risks = 数据不足或冲突
- recommendations = 根据用户选择生成的建议
- references = 使用的资料来源

---

# 30. UI 人性化改造

原则：

> **一个页面只解决一个核心问题。**

避免：

```text
一个页面塞：
罗盘
八字
六爻
奇门
AI
设置
历史
```

---

# 31. 罗盘首页 UI

建议布局：

```text
┌─────────────────────────────┐
│ 玄盘 AI                ⚙    │
├─────────────────────────────┤
│                             │
│          347.28°            │
│                             │
│        ╭─────────╮          │
│       ╱           ╲         │
│      │    罗盘     │         │
│       ╲           ╱         │
│        ╰─────────╯          │
│                             │
│  磁北 347.28°   磁场 48.7μT │
│  水平 1.42°     稳定 92%    │
│                             │
├─────────────────────────────┤
│ [扫描真实罗盘] [传感器]     │
│ [手动调节]     [保存测盘]   │
└─────────────────────────────┘
```

核心数据永远优先。

---

# 32. 测盘页面

```text
┌─────────────────────────────┐
│ 测盘                       │
├─────────────────────────────┤
│                             │
│  📷 拍照真实罗盘             │
│                             │
│  🖼 导入罗盘照片             │
│                             │
│  🧭 手机传感器测量           │
│                             │
│  🎛 手动输入                 │
│                             │
│  📐 我的罗盘                 │
│                             │
└─────────────────────────────┘
```

---

# 33. 分析页面

```text
┌─────────────────────────────┐
│ AI 分析                     │
├─────────────────────────────┤
│ 当前测盘                    │
│                             │
│ 坐：午      向：子           │
│ 磁北：347.28°                │
│                             │
│ AI模型：DeepSeek             │
│ 模式：专业                   │
│                             │
│ [开始分析]                   │
├─────────────────────────────┤
│ 分析配置                     │
│ 模型管理                     │
│ Provider                    │
│ Prompt                      │
│ 路由                         │
│ 用量                         │
└─────────────────────────────┘
```

---

# 34. 我的页面

建议：

```text
我的

个人资料
我的罗盘
AI配置
测量设置
显示设置
数据备份
隐私与安全
关于玄盘
```

---

# 35. 设置体系

设置分层：

```text
我的
├── 我的罗盘
├── AI中心
│   ├── Provider
│   ├── 模型
│   ├── 路由
│   ├── Prompt
│   ├── 用量
│   └── 测试
├── 测量
│   ├── 传感器
│   ├── 磁场阈值
│   ├── 自动校准
│   └── 精度
├── 罗盘
│   ├── 默认盘
│   ├── 盘层
│   ├── 显示
│   └── 手势
├── 数据
│   ├── 导出
│   ├── 导入
│   ├── 备份
│   └── 清理
└── 系统
```

---

# 36. 测量流程 UX

推荐使用“向导式”：

```text
① 选择罗盘
       ↓
② 传感器检测
       ↓
③ 拍照 / 导入
       ↓
④ 自动识别
       ↓
⑤ 用户校准
       ↓
⑥ 确认坐向
       ↓
⑦ 计算
       ↓
⑧ AI分析
       ↓
⑨ 保存档案
```

用户随时可以：

```text
返回
跳过
重新识别
手动修改
```

---

# 37. 视觉设计原则

推荐：

- 深色专业仪器风
- 大面积罗盘视觉中心
- 半透明卡片
- 适度玻璃拟态
- 高对比数据
- 大字号核心角度
- 小字号辅助数据
- 红色仅用于方向/警告
- 不使用过度装饰
- 保持传统罗盘视觉元素

整体感觉：

> **现代数字仪器 + 中国传统罗盘**

而不是普通聊天 AI App。

---

# 38. 技术架构

建议整体：

```text
React Native / Expo
        │
        ├── UI Layer
        │
        ├── Compass Engine
        │
        ├── Sensor Service
        │
        ├── Camera / Import
        │
        ├── Vision Adapter
        │
        ├── Calculation Core
        │
        ├── Local Database
        │
        └── API Client
                 │
                 ↓
              Backend
                 │
          ┌──────┴──────┐
          │             │
       AI Router     Data API
          │
    ┌─────┼─────┐
    │     │     │
 Vision Reason Fast
```

---

# 39. 推荐目录结构

在现有项目结构基础上逐步演进：

```text
src/
├── components/
│   ├── compass/
│   ├── sensor/
│   ├── capture/
│   ├── calibration/
│   └── ai/
│
├── core/
│   ├── compass/
│   ├── sensor/
│   ├── calculation/
│   └── measurement/
│
├── services/
│   ├── sensor/
│   ├── vision/
│   ├── ai/
│   ├── storage/
│   └── api/
│
├── models/
│   ├── CompassModel.ts
│   ├── MeasurementSession.ts
│   ├── SensorSnapshot.ts
│   ├── VisionResult.ts
│   └── AIAnalysis.ts
│
├── screens/
│   ├── Compass/
│   ├── Measurement/
│   ├── Analysis/
│   ├── Archive/
│   └── Settings/
│
└── database/
    ├── migrations/
    └── repositories/
```

---

# 40. 现有功能保护原则

V2 改造前必须建立功能清单。

现有能力原则上全部保留，包括：

- 罗盘
- 二十四山
- 后天八卦
- 120分金
- 坐向计算
- 罗盘照片识别
- 八字
- 六爻
- 奇门遁甲
- 大六壬
- 太乙
- 黄历
- 日期选择
- AI解释
- 历史
- 管理后台
- SQLite
- Docker
- MCP

任何删除功能必须：

1. 明确原因
2. 记录迁移方案
3. 完成替代功能
4. 通过回归测试

---

# 41. 开发阶段

## Phase 0：基线保护

目标：

> 先保证现在能用。

任务：

- 建立现有功能清单
- 建立 Git tag
- 建立数据库备份
- 建立 UI 截图基线
- 建立核心计算测试
- 建立现有罗盘结果快照

验收：

```text
V2改造前所有主要功能可运行。
```

---

# 42. Phase 1：数字罗盘引擎

开发：

```text
CompassModel
CompassRing
CompassLayer
CompassOrientation
CompassCalibration
CompassRenderer
```

实现：

- 旋转
- 缩放
- 精确角度
- 手动调整
- 锁定
- 多盘层

验收：

```text
误差控制在设计精度范围内。
连续旋转不发生跳变。
重新进入页面状态可恢复。
```

---

# 43. Phase 2：手机传感器

实现：

- Magnetometer
- Accelerometer
- Gyroscope
- SensorFusion
- 质量检测
- 校准

验收：

```text
可以实时显示：
方位角
俯仰
横滚
磁场
传感器质量
```

异常时必须有用户提示。

---

# 44. Phase 3：真实罗盘数字化

实现：

- 拍照
- 导入
- 图像预处理
- 圆形检测
- 中心检测
- OCR
- 盘层识别
- 24山识别
- 罗盘类型识别
- CompassModel 重建

验收：

```text
照片不是最终结果。
系统必须生成可操作数字罗盘。
```

---

# 45. Phase 4：校准工作台

实现：

- 原图层
- 数字层
- 透明度
- 旋转
- 缩放
- 中心
- 半径
- 手动修改

验收：

```text
用户可以把数字罗盘与真实照片对齐。
```

---

# 46. Phase 5：测盘档案

实现：

- MeasurementSession
- 数据关联
- 修改历史
- 附件
- 搜索
- 筛选
- 导出

验收：

```text
一份测盘可以完整恢复：
照片
传感器
罗盘
校准
计算
AI分析
```

---

# 47. Phase 6：AI 中心

实现：

- Provider
- Model
- Capability
- Router
- Fallback
- Prompt
- Cost
- Usage
- Test

验收：

```text
用户可以在不升级 APP 的情况下更换 AI Provider / Model。
```

---

# 48. Phase 7：UI 重构

最终统一：

```text
罗盘
测盘
分析
档案
我的
```

要求：

- 首页不堆功能
- 核心数据突出
- 操作路径清晰
- 专业用户快速操作
- 新用户可以通过向导完成测量

---

# 49. 数据完整性原则

所有重要数据必须具有：

```text
原始值
计算值
识别值
人工修正值
最终采用值
来源
时间
```

例如：

```text
坐山

视觉识别：午
置信度：86%

算法计算：午

用户修正：丁

最终值：丁

来源：manual
```

---

# 50. 冲突检测

如果：

```text
传感器 = 347.28°
视觉识别 = 351.20°
人工校准 = 350.90°
```

不要静默选择。

显示：

```text
⚠ 数据存在差异

传感器：347.28°
视觉识别：351.20°
人工校准：350.90°

差异：3.62°

[使用传感器]
[使用视觉]
[手动校准]
```

---

# 51. 数据可信度

建立统一：

```typescript
interface DataConfidence {
  value: number
  source: string
  factors: {
    sensor?: number
    vision?: number
    calculation?: number
    manual?: number
  }
}
```

注意：

> “置信度”用于表达数据质量，不代表传统术数结论的真实性。

---

# 52. 错误处理

所有关键流程必须允许：

```text
重试
重新识别
手动输入
跳过
返回
保存草稿
```

例如 AI 服务失败：

```text
AI分析失败

原因：
Provider Timeout

[重试]
[切换备用模型]
[保存测盘]
```

---

# 53. 离线能力

以下功能尽量离线：

- 数字罗盘
- 手动调节
- 基础传感器
- 基础计算
- 历史档案
- 我的罗盘
- 本地数据

以下功能通常需要网络：

- 云端 Vision
- 云端 AI
- 云端资料
- 云端同步

---

# 54. 隐私

罗盘照片、测盘资料属于用户数据。

要求：

- 默认本地保存
- 上传前明确提示
- AI 上传的数据可配置
- API 日志不保存完整用户资料
- API Key 不进入客户端
- 删除操作必须可追踪
- 数据导出使用结构化格式

---

# 55. 导入 / 导出

支持：

```text
JSON
ZIP
图片
PDF报告
```

JSON 至少包含：

```text
CompassModel
MeasurementSession
SensorSnapshot
VisionResult
Calibration
CalculationResult
AIAnalysis
```

---

# 56. 未来罗盘视觉数据集

长期建立：

> 玄盘 AI 罗盘视觉数据集

分类：

```text
三元盘
三合盘
综合盘
玄空盘
金锁玉关
自定义盘
```

环境：

```text
室内
室外
强光
弱光
反光
倾斜
遮挡
复杂背景
```

标注：

```text
圆心
半径
北向
24山
八卦
120分金
盘层
文字
罗盘类型
```

人工修正数据可以反向成为高价值训练数据。

---

# 57. 后续 AI/CV 演进

V2 初期：

```text
第三方 Vision / OCR
+
规则
+
人工校准
```

积累数据后：

```text
自有罗盘检测模型
        ↓
自有盘层识别
        ↓
自有文字识别
        ↓
自有罗盘结构重建
```

最终形成玄盘 AI 自有数据资产。

---

# 58. 性能要求

APP：

- 罗盘旋转必须流畅
- 传感器更新不能阻塞 UI
- 图片识别放入异步任务
- AI 请求不得阻塞页面
- 大图需要压缩
- 历史列表分页
- 数据库查询必须索引

禁止：

```text
UI线程执行大型 OCR
UI线程执行复杂计算
UI线程直接等待 AI
```

---

# 59. AI 编程智能体执行规则

Codex / Claude Code / Gemini / WorkBuddy 执行本项目时必须：

## 第一原则

**先读代码，再改代码。**

禁止：

```text
看到需求
→ 直接重写
```

必须：

```text
分析
→ 定位
→ 设计
→ 小步修改
→ 测试
→ 回归
```

---

# 60. 修改流程

每次改动：

```text
1. 查看现有实现
2. 找到依赖关系
3. 判断是否影响旧功能
4. 建立最小改动方案
5. 编码
6. 类型检查
7. 单元测试
8. UI测试
9. 构建
10. 回归
```

---

# 61. 不允许的开发行为

禁止：

- 无依据删除旧功能
- 大规模重写核心模块
- 为简单功能引入大型框架
- API Key 硬编码
- AI 直接替代计算核心
- 把照片当成唯一罗盘数据
- 修改识别结果而不保存原始结果
- 不测试直接提交
- 不处理错误状态
- 只完成 UI 不完成数据链路

---

# 62. Git 提交规范

建议：

```text
feat(compass): add manual rotation calibration
feat(sensor): add magnetic field quality monitor
feat(vision): add compass reconstruction
feat(ai): add provider router
feat(session): add measurement archive
refactor(ui): redesign main navigation
fix(sensor): stabilize azimuth calculation
test(compass): add orientation regression tests
```

---

# 63. 测试体系

至少建立：

```text
Unit Test
Integration Test
UI Test
Regression Test
Build Test
```

核心测试：

### 罗盘

- 0°
- 90°
- 180°
- 270°
- 359.9°
- 360°归零
- 负角度
- 连续旋转

### 传感器

- 正常
- 异常
- 权限拒绝
- 传感器不可用
- 磁场干扰

### 视觉

- 正面
- 倾斜
- 反光
- 弱光
- 部分遮挡

### AI

- 正常
- Timeout
- Rate Limit
- Provider 不可用
- Fallback

---

# 64. V2 MVP 优先级

如果开发资源有限，优先级必须是：

## P0

1. 数字罗盘手动调节
2. 手机传感器
3. 测盘 Session
4. 真实罗盘照片识别
5. 数字罗盘还原
6. 人工校准
7. 历史档案

## P1

8. AI Provider
9. AI Router
10. AI 分析中心
11. 我的罗盘
12. 数据导入导出

## P2

13. 自有视觉模型
14. 数据集
15. 高级统计
16. 云同步
17. 高级报告

---

# 65. 最终产品架构

```text
                    玄盘 AI
                       │
          ┌────────────┴────────────┐
          │                         │
       测量层                     分析层
          │                         │
   ┌──────┼──────┐          ┌───────┼───────┐
   │      │      │          │       │       │
 手机   拍照   导入       计算    规则    AI
传感器 真实盘  图片
   │      │      │          │       │       │
   └──────┼──────┘          └───────┼───────┘
          │                         │
          └──────────┬──────────────┘
                     │
             MeasurementSession
                     │
                测盘档案
```

---

# 66. V2 最终用户体验

用户不需要理解复杂技术。

只需要：

```text
拿罗盘
 ↓
打开玄盘 AI
 ↓
手机测方向
 ↓
拍照
 ↓
系统识别
 ↓
拖动校准
 ↓
确认
 ↓
分析
 ↓
保存
```

系统内部负责：

```text
传感器融合
图像处理
罗盘重建
确定性计算
数据关联
AI路由
报告生成
历史归档
```

---

# 67. 产品验收标准

V2 完成不能以：

> “页面做出来了”

作为验收标准。

必须满足：

### A. 罗盘

- [ ] 可以手动旋转
- [ ] 可以精确调整角度
- [ ] 可以锁定
- [ ] 可以缩放
- [ ] 可以控制盘层
- [ ] 罗盘状态可保存

### B. 传感器

- [ ] 可以读取磁力计
- [ ] 可以读取姿态
- [ ] 可以计算方位
- [ ] 可以检测磁场
- [ ] 可以检测稳定性
- [ ] 可以提示异常

### C. 真实罗盘

- [ ] 可以拍照
- [ ] 可以导入
- [ ] 可以识别
- [ ] 可以检测圆心
- [ ] 可以识别主要盘层
- [ ] 可以生成数字罗盘

### D. 校准

- [ ] 原图和数字罗盘可以叠加
- [ ] 可以调透明度
- [ ] 可以旋转
- [ ] 可以缩放
- [ ] 可以移动
- [ ] 可以手动修改
- [ ] 保存修改历史

### E. 测盘

- [ ] 一份 Session 可以保存完整数据
- [ ] 可以恢复
- [ ] 可以搜索
- [ ] 可以导出

### F. AI

- [ ] Provider 可配置
- [ ] Model 可配置
- [ ] Prompt 可配置
- [ ] Router 可配置
- [ ] Fallback 可配置
- [ ] API Key 安全
- [ ] AI 使用结构化数据
- [ ] AI 不覆盖确定性计算

### G. UI

- [ ] 五底部导航清晰
- [ ] 首页突出罗盘
- [ ] 测盘流程清楚
- [ ] AI集中管理
- [ ] 历史升级为档案
- [ ] 新用户无需理解技术细节即可完成一次测盘

---

# 68. 最终开发原则

整个 V2 项目始终遵循：

> **数据先于 AI，结构先于图片，计算先于解释，人工校准先于强制自动化。**

最终形成：

```text
真实世界
   ↓
传感器
   ↓
照片
   ↓
结构化罗盘
   ↓
数字罗盘
   ↓
人工确认
   ↓
确定性计算
   ↓
AI解释
   ↓
完整档案
```

这才是玄盘 AI V2 的核心产品闭环。

---

# 69. 给 AI 编程智能体的最终执行指令

```text
你现在负责将 xuanpan-ai 升级为“玄盘 AI V2”。

必须遵守以下顺序：

1. 先完整分析现有代码。
2. 建立现有功能清单。
3. 不得破坏已有术数计算、罗盘、历史、AI及管理功能。
4. 优先建立 CompassModel。
5. 将罗盘 UI 与罗盘数据模型解耦。
6. 增加 SensorService 和 SensorFusion。
7. 建立 MeasurementSession 作为核心业务实体。
8. 增加真实罗盘拍照/导入识别。
9. 将真实罗盘照片转换为结构化 CompassModel。
10. 增加照片与数字罗盘叠加校准工作台。
11. 所有视觉识别结果必须允许人工修改。
12. 原始识别结果不能被覆盖。
13. 所有修改必须写入 correction_history。
14. AI只能解释结构化数据，不得替代确定性计算。
15. 建立统一 AI Provider / Model / Router / Fallback 架构。
16. API Key不得硬编码到客户端。
17. 重构底部导航为：
    罗盘 / 测盘 / 分析 / 档案 / 我的
18. 采用渐进式改造，不进行无必要的大规模重写。
19. 每完成一个阶段都必须进行测试和回归。
20. 最终必须能够从“真实罗盘照片 + 手机传感器”完成一次完整测盘并保存为档案。

任何时候，如果现有代码与本规范冲突：

优先保护现有稳定功能，
再采用最小改动方式实现 V2。
```

---

## 70. V2 产品一句话定义

> **玄盘 AI，是一个把真实罗盘、手机传感器、数字罗盘、确定性术数计算和 AI 分析连接起来的数字化测盘工作台。**

