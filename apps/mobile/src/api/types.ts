/**
 * 后端契约的 TypeScript 映射。
 *
 * 与 `services/api/xuanpan_api/schemas.py` **一一对应**。
 * 字段名刻意不做"前端友好化"改名 —— 后端改名字时这里必须同步改，
 * 而 `tsc` 会立刻报错。若在这里另起一套词汇表，后端改名时前端会静默拿到
 * `undefined`，表现为"界面上某处空了"而不是"编译失败"，最难查。
 */

// ==========================================================================
// 元信息
// ==========================================================================

export interface MountainInfo {
  index: number;
  name: string;
  center_degree: number;
  start_degree: number;
  end_degree: number;
  kind: 'branch' | 'stem' | 'gua';
  element: string;
  yin_yang: 'yang' | 'yin';
  sanyuan: string;
  gua: string;
  full_name: string;
}

export interface MountainsResponse {
  convention: string;
  mountains: MountainInfo[];
}

export interface ProviderInfo {
  id: string;
  name: string;
  capability: string;
  requires_api_key: boolean;
  cost: string;
  description: string;
  available: boolean;
  /** 仅 vision provider 有 */
  reads_printed_text?: boolean;
}

export interface AiProvidersResponse {
  matrix: Omit<ProviderInfo, 'available'>[];
  providers: ProviderInfo[];
  endpoint_presets: {
    id: string;
    name: string;
    base_url: string;
    requires_api_key: string;
    note: string;
  }[];
}

export interface VisionProvidersResponse {
  matrix: Omit<ProviderInfo, 'available'>[];
  providers: ProviderInfo[];
  /** 输出即用户输入的 provider（如 manual）—— 这些路径免确认闸门 */
  user_authoritative: string[];
}

export interface QuestionCategoriesResponse {
  categories: string[];
  /** 敏感类别 → 额外免责声明（RULE-010） */
  sensitive: Record<string, string>;
}

export interface CapabilitiesResponse {
  fenjin_table_available: boolean;
  ai_provider_available: boolean;
  vision_provider_available: boolean;
  note: string;
}

export interface QianSet {
  set_id: string;
  name?: string;
  demo?: boolean;
  count?: number;
  [k: string]: unknown;
}

// ==========================================================================
// 通用
// ==========================================================================

/**
 * 一次计算的两层只读结果。
 *
 * `facts` / `tradition` 的**外层键是模块名**（`compass` / `bazi` / `liuyao` /
 * `qian` / `name`），内层才是字段。这与 `Report.facts`、`SessionDetail.facts`
 * 是同一个形状 —— 三处若不一致，就会出现"报告页能取到、预览页取不到"这类
 * 只在某个页面复现的怪问题。
 */
export interface LayerPreview {
  facts: Record<string, Record<string, unknown>>;
  tradition: Record<string, Record<string, unknown>>;
  uncertainties: string[];
}

export interface SessionCreated {
  session_id: string;
  created_at: string;
  title: string;
}

// ==========================================================================
// 罗盘模板库
// ==========================================================================

/**
 * 罗盘模板 —— 一套「盘式 + 默认坐向」的命名预设。
 *
 * 🔴 **接口里没有 `layers` 字段，这是有意的。**
 * 「盘式 → 层数」的表在 `lib/dialStyle.ts`，后端刻意不存副本 ——
 * 两边各存一份必然漂移，而漂移的表现是「列表写 18 层、打开画出 6 层」，
 * 数字对不上却不报任何错。层数一律由前端 `DIAL_STYLES[style].statedLayers` 查得。
 *
 * 同理 `style` 声明成 `string` 而不是联合类型：后端不校验枚举
 * （删掉某个盘式后旧模板仍要能读出来），故这里拿到的可能是未知值，
 * 使用前必须过 `coerceDialStyle`。
 */
export interface CompassTemplate {
  template_id: string;
  created_at: string;
  updated_at: string;
  name: string;
  /** 盘式 id。**可能是未知值**（旧存档），用前过 `coerceDialStyle` */
  style: string;
  sitting: string | null;
  facing: string | null;
  degree: number | null;
  school: string;
  note: string | null;
  is_favorite: boolean;
  use_count: number;
  last_used_at: string | null;
}

export interface TemplateListResponse {
  items: CompassTemplate[];
  total: number;
}

export interface TemplateCreateRequest {
  name: string;
  style?: string;
  sitting?: string | null;
  facing?: string | null;
  degree?: number | null;
  school?: string;
  note?: string | null;
  is_favorite?: boolean;
}

/**
 * 局部更新请求 —— 只给要改的字段。
 *
 * 刻意不写成 `Partial<CompassTemplate>`：那样会允许传 `template_id` /
 * `created_at` 等不可变字段，而服务端会 422（`extra="forbid"`），
 * 变成一个到运行时才发现的错误。
 */
export interface TemplateUpdateRequest {
  name?: string;
  style?: string;
  sitting?: string | null;
  facing?: string | null;
  degree?: number | null;
  school?: string;
  note?: string | null;
  is_favorite?: boolean;
}

export interface DeletedResponse {
  deleted: boolean;
  session_id: string;
}

// ==========================================================================
// 识别
// ==========================================================================

export interface MountainCandidate {
  name: string;
  /** **实测角度**（非山心角）。分金依赖它，务必回传而不是用山心角替换 */
  angle: number;
  confidence: number;
  end: 'sitting' | 'facing' | 'unknown';
}

export interface QualityIssue {
  code: string;
  severity: 'ok' | 'warn' | 'fail';
  message: string;
  metric?: number | null;
  threshold?: number | null;
}

export interface QualityReport {
  passed: boolean;
  blur_score: number;
  glare_ratio: number;
  brightness: number;
  /**
   * 画面尺寸 `[宽, 高]`。
   *
   * 后端 `QualityReport.to_dict()` 输出的是这个数组键（`size`），
   * 而不是扁平的 `width` / `height` —— 曾按后者声明，与实际响应不符。
   * 由 `tests/mobile/test_types_contract.py` 用真实响应钉住。
   */
  size: [number, number];
  issues: QualityIssue[];
}

export interface ScanResult {
  session_id: string;
  compass_detected: boolean;
  /** 恒为 true（RULE-004）。保留字段是为了让 UI 显式渲染"必须确认" */
  needs_user_confirmation: true;
  provider: string;
  quality: QualityReport | null;
  center: [number, number] | null;
  radius: number | null;
  mountain_candidates: MountainCandidate[];
  direction_candidates: MountainCandidate[];
  /** 哪里没看清 —— 直接展示给用户，不要改写 */
  uncertain_regions: string[];
  warnings: string[];
}

// ==========================================================================
// 会话
// ==========================================================================

export interface RecognitionSnapshot {
  compass_detected: boolean;
  confidence: number;
  needs_user_confirmation: boolean;
  uncertain_regions: string[];
  warnings: string[];
  mountain_candidates: MountainCandidate[];
  direction_candidates: MountainCandidate[];
  provider: string;
}

export interface SessionSummary {
  session_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  origin: string;
  question_category: string | null;
  question_text: string | null;
  has_compass: 0 | 1;
  has_bazi: 0 | 1;
  has_liuyao: 0 | 1;
  has_qian: 0 | 1;
  has_naming: 0 | 1;
  has_recognition: 0 | 1;
  report_count: number;
}

export interface SessionListResponse {
  total: number;
  items: SessionSummary[];
}

export type ModuleName = 'compass' | 'bazi' | 'liuyao' | 'qian' | 'naming';

export interface SessionDetail {
  session_id: string;
  created_at: string;
  updated_at: string;
  title: string;
  origin: string;
  question: { category: string | null; text: string | null };
  modules: ModuleName[];
  inputs: Record<string, Record<string, unknown> | null>;
  recognition: RecognitionSnapshot | null;
  confirm_state: CompassConfirmState | null;
  facts: Record<string, Record<string, unknown>>;
  tradition: Record<string, Record<string, unknown>>;
  uncertainties: string[];
  /** 非 null 表示这份会话当前算不出来（输入损坏），必须显式提示而不是当空数据 */
  build_error: string | null;
  report_count: number;
}

export interface CompassConfirmState {
  confirmed: boolean;
  sitting: string;
  facing: string;
  degree: number | null;
  user_note: string | null;
}

// ==========================================================================
// 报告
// ==========================================================================

export interface ReportSection {
  title: string;
  body: string;
}

export interface Attempt {
  provider: string;
  model: string;
  ok: boolean;
  detail: string;
  elapsed_ms: number;
}

export interface Interpretation {
  /**
   * **专业分析**的区块 —— 用术数术语写的那一版。
   *
   * ⚠️ 这个字段名没有体现"专业"二字，是历史原因（先有专业版、后加白话版）。
   * 不要据此以为是"两种文体合并后的结果"：它只装专业分析。
   */
  sections: ReportSection[];
  /**
   * **白话讲解**的区块 —— 同一批数据、不用术语的那一版。
   *
   * 后端没生成白话版时是 `[]`。**不要拿 `sections` 顶上** ——
   * 那会让文体切换按钮点了没反应，看起来像功能坏了。
   */
  plain_sections: ReportSection[];
  /**
   * 有没有白话版。**界面只用这个字段判断**，不要自己写
   * `plain_sections.length > 0`：多一处判断就多一个漏算点，
   * 而漏算的表现是"切换按钮点了没反应"。
   */
  has_plain: boolean;
  /**
   * 模型输出的**原文**（未切分区块）。
   *
   * 键名是 `raw_text` 而非 `text` —— 后端 `Interpretation.to_dict()` 就是这么发的。
   * 名字容易记成 `text`，而写错不会报错，只会让取值恒为 `undefined`
   * （表现为追问记录里 AI 的回答是空白）。由
   * `tests/mobile/test_types_contract.py` 用真实响应钉住。
   */
  raw_text: string;
  provider: string;
  model: string;
  degraded: boolean;
  attempts: Attempt[];
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  warnings: string[];
}

/** 三层**物理分离** —— 刻意是三个并列字段，不存在"合并后的文本" */
export interface Report {
  session_id: string;
  facts: Record<string, Record<string, unknown>>;
  tradition: Record<string, Record<string, unknown>>;
  interpretation: Interpretation;
  uncertainties: string[];
  question: { category: string; text: string } | null;
  calculation: Record<string, unknown>;
  disclaimer: string;
  generated_at: string;
}

export interface ReportResponse {
  report_id: string;
  report: Report;
}

export interface ReportMeta {
  report_id: string;
  session_id: string;
  created_at: string;
  question: string | null;
}

export interface Turn {
  id: number;
  report_id: string | null;
  created_at: string;
  role: 'user' | 'assistant';
  content: string;
}

// ==========================================================================
// 请求体
// ==========================================================================

export interface BaziInput {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute?: number;
  calendar?: 'solar' | 'lunar';
  gender?: 'male' | 'female' | null;
  timezone?: string;
  longitude?: number | null;
  latitude?: number | null;
  sect?: 1 | 2;
}

export interface CompassInput {
  sitting?: string | null;
  facing?: string | null;
  degree?: number | null;
  confidence?: number;
  confirmed_by_user?: boolean;
  source?: 'manual' | 'vision' | 'import';
  school?: string;
}

export interface LiuyaoInput {
  method?: 'coins' | 'yao' | 'numbers';
  coins?: boolean[][];
  yao_values?: number[];
  numbers?: number[];
}

export interface QianInput {
  seed: number;
  set_id?: string;
}

export interface NamingInput {
  name: string;
}

export interface InputPatch {
  compass?: CompassInput;
  bazi?: BaziInput;
  liuyao?: LiuyaoInput;
  qian?: QianInput;
  naming?: NamingInput;
  question_category?: string | null;
  question_text?: string | null;
  title?: string | null;
}

export interface ReportRequest {
  question_category?: string | null;
  question_text?: string | null;
  mode?: 'auto' | 'cost' | 'quality';
  force_template?: boolean;
}

export interface AskRequest {
  question_text: string;
  question_category?: string | null;
  mode?: 'auto' | 'cost' | 'quality';
  force_template?: boolean;
}

export interface CompassConfirmRequest {
  sitting?: string | null;
  facing?: string | null;
  degree?: number | null;
  school?: string;
  note?: string | null;
}

// ==========================================================================
// 日历域与断卦
// ==========================================================================
//
// 对应后端 `/api/v1/almanac`、`/zeri`、`/duan`。
//
// 这三组**不属于会话体系**：不落库、不进 `FortuneContext`、也没有报告。
// 因此它们**不复用 `LayerPreview`** —— 那个类型的外层键是模块名，
// 硬套会让「取 facts.bazi」这类路径在黄历上变成无意义的猜测。
//
// 字段逐一声明而非 `Record<string, unknown>`：后者会让「字段名写错」
// 一路活到运行时，表现为界面某一格静默变空（tsc 完全不会报）。
// `tests/mobile/test_types_contract.py` 正是为防这类漂移而存在。

/** 单日黄历事实层。与内核 `AlmanacResult.to_facts()` 一一对应。 */
export interface AlmanacFacts {
  solar_date: string;
  lunar: string;
  gan_zhi: { year: string; month: string; day: string };
  jian_chu: string;
  xiu: { name: string; luck: string };
  tian_shen: { name: string; type: string; luck: string; is_huang_dao: boolean };
  chong: { zhi: string; desc: string; shengxiao: string; sha_direction: string };
  yi: string[];
  ji: string[];
  ji_shen: string[];
  xiong_sha: string[];
  peng_zu: { gan: string; zhi: string };
  /**
   * 建除十二神的交叉校验结果。
   * 空数组 = 全部通过；交节日会留一条口径说明（属已知差异，不是错误）。
   */
  rule_consistency: string[];
}

export interface AlmanacTradition {
  summary: string;
  note: string;
  uncertainties: string[];
}

export interface AlmanacDay {
  facts: AlmanacFacts;
  tradition: AlmanacTradition;
}

export interface AlmanacRange {
  start: string;
  end: string;
  days: AlmanacDay[];
}

export interface ZeriEvent {
  event: string;
  label: string;
  yi: string[];
  ji: string[];
  note: string;
}

export interface ZeriSchool {
  id: string;
  name: string;
  description?: string;
  /**
   * 显式未覆盖项（三煞 / 太岁 / 五黄 / 当事人八字喜忌等）。
   * UI 必须展示为「本版不覆盖」，而不是省略 —— 用户有权知道
   * 这份吉日建议**没有考虑什么**。
   */
  unverified?: string[];
}

export interface ZeriEventsResponse {
  events: ZeriEvent[];
  schools: ZeriSchool[];
}

/** 择日单日评价。`veto` 非空即表示该日被否决。 */
export interface ZeriDay {
  solar_date: string;
  weekday: string;
  lunar: string;
  day_gan_zhi: string;
  jian_chu: string;
  xiu: { name: string; luck: string };
  tian_shen: { name: string; type: string };
  chong_shengxiao: string;
  sha_direction: string;
  score: number;
  grade: string;
  usable: boolean;
  matched_yi: string[];
  matched_ji: string[];
  veto: string[];
  veto_kinds: string[];
  reasons: string[];
}

export interface ZeriDayResponse {
  day: ZeriDay;
  event_label: string;
  school: string;
  school_name: string;
  event_note: string;
}

export interface ZeriSelectRequest {
  event: string;
  start: string;
  end: string;
  school?: string;
  shengxiao?: string | null;
  limit?: number;
  include_unfavorable?: boolean;
}

export interface ZeriResultFacts {
  event: string;
  event_label: string;
  range: { start: string; end: string; days_scanned: number };
  candidate_count: number;
  excluded_count: number;
  /** 各否决项的命中天数。**同一日可命中多项，故各项之和大于 excluded_count** */
  excluded_reasons: Record<string, number>;
  candidates: ZeriDay[];
}

export interface ZeriResultTradition {
  school: string;
  school_name: string;
  summary: string;
  note: string;
  uncertainties: string[];
}

export interface ZeriResultResponse {
  facts: ZeriResultFacts;
  tradition: ZeriResultTradition;
}

/**
 * 吉凶倾向。
 *
 * 四个**所有断卦共有**的字段放在顶层，各术式的差异细节（六爻的用神/世爻、
 * 八字的大运逐运倾向）放 `detail` —— 前端可先统一渲染
 * 「倾向 + 依据 + 流派标注」，再按术式补细节，不必写两套解析。
 */
export interface DuanResponse {
  verdict: string;
  reasons: string[];
  school: string;
  uncertainties: string[];
  detail: Record<string, unknown>;
}

export interface DuanLiuyaoRequest extends LiuyaoInput {
  /** 占问类别，决定用神取用。取值见 /meta/question-categories */
  topic?: string | null;
  /** 婚姻类占问需传：男占妻看妻财、女占夫看官鬼 */
  gender?: 'male' | 'female' | null;
  /**
   * 起卦日（决定日辰与月令）。
   * **补录隔夜的卦必须填**，否则会按今天的日辰算旺衰 —— 结论看似正常、依据全错。
   */
  cast_date?: string | null;
}

// ==========================================================================
// 三式 · 奇门遁甲
// ==========================================================================

/**
 * 定局结果 —— 「这一时刻落在哪一局」的完整推导链。
 *
 * 把 `jieqi` / `days_after_jieqi` / `yuan` 一并返回而不是只给 `jushu`：
 * 用户看到「阴遁六局」时，下一个问题永远是"凭什么"，这三个字段就是答案。
 */
export interface QimenDingju {
  solar_datetime: string;
  /** 所处节气 */
  jieqi: string;
  /** 该节气的**交节时刻**（精确到秒）—— 定局的真正分界点 */
  jieqi_time: string;
  /** 交节后第几天（当日算第 1 天） */
  days_after_jieqi: number;
  /** 1=上元 2=中元 3=下元 */
  yuan: number;
  yuan_label: string;
  yang_dun: boolean;
  dun_name: string;
  jushu: number;
  /** 中文局数，如「阴遁六局」 */
  jushu_label: string;
}

export interface QimenPillars {
  year: string;
  month: string;
  day: string;
  hour: string;
}

/**
 * 单宫。
 *
 * `door` / `god` 允许为 null：**中五宫不布门、不布神**（寄坤二宫），
 * 所以五宫有地盘干与天盘干、却没有门与神。前端必须容忍这件事 ——
 * 把 null 当成"数据没取到"去补默认值，就是把寄宫规则写进了界面（RULE-005）。
 */
export interface QimenPalace {
  /** 洛书宫序 1~9 */
  gong: number;
  /** 八卦名（中宫为「中」） */
  gua: string;
  /** 方位：北 / 东北 / 东 … */
  direction: string;
  element: string;
  /** 地盘干（三奇六仪原位） */
  di_gan: string;
  /** 天盘干（转动后） */
  tian_gan: string | null;
  star: string;
  /** 九星固有吉凶——**是星自己的属性，不是对所问之事的结论** */
  star_jixiong: '吉' | '凶' | '平';
  door: string | null;
  door_jixiong: '吉' | '凶' | '平' | null;
  god: string | null;
  is_xun_kong: boolean;
  is_yima: boolean;
}

/**
 * 一张奇门盘。
 *
 * 注意这是**扁平结构**（不像八字/六爻那样有 facts + tradition 两层）：
 * 奇门当前只有确定性的盘面事实，没有「传统分析」层。
 */
export interface QimenChart {
  dingju: QimenDingju;
  pillars: QimenPillars;
  /** 旬首（六甲之一） */
  xunshou: string;
  /** 值符所带之仪（三奇六仪之一） */
  zhifu_yi: string;
  /** 值符原宫 */
  zhifu_gong: number;
  zhifu_star: string;
  zhishi_door: string;
  zhishi_gong: number;
  /** 值符**转动后**所在之宫（随天盘，非原宫） */
  zhifu_gong_now: number;
  /** 旬空二支 */
  xun_kong: string[];
  /** 驿马支 */
  yima: string;
  /** 九宫，按宫序 1~9 排好；前端只需按洛书位置摆放，不需再推导 */
  palaces: QimenPalace[];
  school: string;
  school_name: string;
  /** 本版**未覆盖项**，界面应如实展示，不得省略 */
  uncertainties: string[];
}

export interface QimenSchool {
  id: string;
  name: string;
  note: string;
}

/**
 * 排盘界面需要的静态元数据。
 *
 * `jushu_table` 由接口返回而**不是前端自己算**：局数表是领域数据（RULE-005），
 * 前端硬编码一份必然与内核漂移，而漂移的表现是「界面显示的局数与实排不符」——
 * 不报错、只是静默不一致。
 */
export interface QimenMetaResponse {
  schools: QimenSchool[];
  /** 节气 -> [上元, 中元, 下元] 局数 */
  jushu_table: Record<string, number[]>;
  yang_dun_jieqi: string[];
  yin_dun_jieqi: string[];
  uncertainties: string[];
}

export interface QimenCastRequest {
  /**
   * 本地时刻（ISO 8601）。奇门以**时辰**起局 ——
   * 同一日不同时辰可能不同局，只给日期排不出盘。
   */
  dt: string;
  school?: string;
  day_boundary?: 'zi' | 'early_zi';
}
// ======================================================================
// 大六壬（三式之二）
// ======================================================================

/**
 * 一课。
 *
 * 第一课的 `lower` 是日干**寄宫支**（甲寄寅 → `寅`），它决定取哪一宫的上神；
 * 而 `lower_label` 是**日干本身**（`甲`），界面显示的是它，五行也按它取。
 * 两者不可互换 —— `lower` 用来取上神，`lower_label` 用来展示与判五行。
 */
export interface LiurenLesson {
  index: number;
  name: string;
  upper: string;
  lower: string;
  /** 下神的展示名：第一课是日干，其余是地支 */
  lower_label: string;
  upper_element: string;
  /** 第一课要按**日干五行**取，不能按寄宫支五行 */
  lower_element: string;
  /** 是否为初传所出的一课（界面靠它高亮「三传从哪来」） */
  is_ke: boolean;
  /** 下贼上 / 上克下 / null */
  ke_kind: string | null;
}

/** 一宫：地盘支、其上的天盘支、以及该天盘支所带的天将。 */
export interface LiurenPalace {
  ground: string;
  heaven: string;
  general: string | null;
  /**
   * 天将**自身的固有吉凶属性**（六吉六凶）——
   * 是"这个天将是什么"，不是"你问的这件事怎么样"。
   */
  general_jixiong: '吉' | '凶' | null;
  is_guiren_ground: boolean;
}

/**
 * 一传。
 *
 * `dun_gan` 为 null 表示该支**落旬空**（本旬没有配到天干）——
 * 这是**领域信号**，不是数据缺失。界面应显示为「空」，
 * 不能补一个默认天干（那等于把空亡抹掉）。
 */
export interface LiurenChuan {
  /** 初传 / 中传 / 末传 */
  position: string;
  zhi: string;
  general: string | null;
  dun_gan: string | null;
  element: string;
}

/** 贵人：昼/夜贵、落在地盘哪一宫、天将顺布还是逆布。 */
export interface LiurenGuiren {
  zhi: string;
  is_day: boolean;
  /** 昼贵 / 夜贵 */
  kind: string;
  /** 贵人所临的**地盘**宫 */
  ground: string;
  shun: boolean;
  /** 顺布 / 逆布 */
  direction: string;
}

/**
 * 一张大六壬课。
 *
 * 与奇门一样是**扁平结构**：月将、四课、三传、十二宫都在顶层，
 * 不分 facts / tradition 两层 —— 六壬当前只有确定性的盘面事实。
 */
export interface LiurenChart {
  solar_datetime: string;
  day_ganzhi: string;
  day_gan: string;
  day_zhi: string;
  /** 占时支 */
  hour_zhi: string;
  /** 月将支 */
  month_general: string;
  /** 神将名（登明 / 河魁 …） */
  month_general_name: string;
  month_general_label: string;
  /** 换将所依的**中气**（不是节气） */
  zhongqi: string;
  zhongqi_time: string;
  guiren: LiurenGuiren;
  /** 四课 */
  lessons: LiurenLesson[];
  /** 十二宫，按地支 子~亥 排好；前端只需按十二宫方图摆放 */
  palaces: LiurenPalace[];
  /** 初 / 中 / 末三传 */
  chuan: LiurenChuan[];
  /** 取传所用宗门（九宗门之一） */
  chuanke: string;
  /** 该宗门的口径说明 */
  chuanke_note: string;
  xun_kong: string[];
  yima: string;
  school: string;
  school_name: string;
  /** 本版**未覆盖项**，界面应如实展示，不得省略 */
  uncertainties: string[];
}

export interface LiurenSchool {
  id: string;
  name: string;
  note: string;
}

/**
 * 起课界面需要的静态元数据。
 *
 * 月将表 / 寄宫表 / 天将名目都由接口返回而**不是前端自己算**：
 * 它们是领域数据（RULE-005），前端存一份必然与内核漂移，
 * 而漂移的表现是「界面显示的月将与实排不符」——不报错、只静默不一致。
 */
export interface LiurenMetaResponse {
  schools: LiurenSchool[];
  /** 中气 -> 月将支 */
  yuejiang_table: Record<string, string>;
  /** 月将支 -> 神将名 */
  yuejiang_names: Record<string, string>;
  /** 十干寄宫：日干 -> 地支 */
  jigong: Record<string, string>;
  /** 日干 -> [昼贵, 夜贵] */
  guiren: Record<string, string[]>;
  /** 适用昼贵的占时支 */
  daytime_zhi: string[];
  /** 十二天将，按布将顺序 */
  tianjiang_order: string[];
  tianjiang_jixiong: Record<string, string>;
  /** 九宗门，按判定优先级 */
  jiuzongmen: string[];
  jiuzongmen_note: Record<string, string>;
  uncertainties: string[];
}

export interface LiurenCastRequest {
  /**
   * 本地时刻（ISO 8601）。六壬以**月将加时**起课 ——
   * 同一日不同时辰是完全不同的课，只给日期排不出课。
   */
  dt: string;
  school?: string;
}
// ======================================================================
// 太乙神数（三式之三）
// ======================================================================

/**
 * 太乙落宫。
 *
 * 🔴 太乙宫号与洛书**逐宫错位**（乾1 离2 艮3 震4 兑6 坤7 坎8 巽9），
 * 不要套用奇门的九宫 —— 前端摆位必须用独立的表，绝不能复用 `QIMEN_GRID`。
 * `li`（理天 / 理地 / 理人）由「入宫第几年」导出：太乙每 3 年移一宫，
 * 第 1 年理天、第 2 年理地、第 3 年理人。
 */
export interface TaiyiTaiyi {
  /** 太乙宫号（1~9，永不为 5） */
  palace: number;
  /** 八卦名（太乙口径，与洛书错位） */
  gua: string;
  direction: string;
  yinyang: 'yin' | 'yang';
  /** 入宫第几年（1~3） */
  ru_gong_year: number;
  /** 理天 / 理地 / 理人 */
  li: string;
}

/** 一个十六神位上的「目」（文昌 / 始击 / 定目）。 */
export interface TaiyiMu {
  /** 十六神位（子丑寅… 含四维乾坤巽艮） */
  pos: string;
  /** 神名（地主 / 阳德 / 武德 …） */
  name: string;
  palace: number;
  gua: string;
  direction: string;
  /** 是否八正神（正宫）；间神（间辰）不落正宫 */
  is_zheng: boolean;
}

/** 计神：只在十二支（不含四维）上起。 */
export interface TaiyiJishen {
  zhi: string;
}

/** 五元六纪。 */
export interface TaiyiEpoch {
  /** 元序（0~4，对应甲子元…壬子元） */
  wuyuan_index: number;
  wuyuan: string;
  /** 元内局数 */
  ju: number;
  ju_label: string;
  /** 纪序（1~6） */
  ji_number: number;
  /** 纪内第几年 */
  ji_year: number;
}

/** 值事八门。 */
export interface TaiyiBamen {
  zhishi: string;
  zhishi_jixiong: string;
  layout: TaiyiBamenLayout[];
}

/** 一算（主算 / 客算 / 定算）。 */
export interface TaiyiSuan {
  name: string;
  source_label: string;
  source_pos: string;
  source_name: string;
  source_palace: number;
  source_palace_gua: string;
  /** 算数（和数） */
  value: number;
  /** 长 / 短 */
  length: string;
  /** 三才判定（无天 / 无地 / 无人 等，可为空） */
  san_cai: string[];
  he_class: string | null;
  gu_class: string | null;
  /** 大将落宫号 */
  da_jiang: number;
  da_jiang_gua: string;
  /** 参将落宫号 */
  can_jiang: number;
  can_jiang_gua: string;
}

/** 值事八门中的一门落宫。 */
export interface TaiyiBamenLayout {
  palace: number;
  gua: string;
  door: string;
  /** 门自身的固有吉凶属性，不是对所问之事的结论 */
  jixiong: string;
}

/**
 * 一张太乙年局盘。
 *
 * 与奇门 / 六壬一样是**扁平结构**：积年、五元六纪、太乙落宫、三目、
 * 主客定三算、八门都在顶层，不分 facts / tradition 两层 ——
 * 年局当前只有确定性的盘面事实。
 */
export interface TaiyiChart {
  year: number;
  year_ganzhi: string;
  /** 太乙积年（取决于流派） */
  jiyan: number;
  school: string;
  school_name: string;
  jiyan_base: number;
  /** 五元六纪 */
  epoch: TaiyiEpoch;
  tai_sui: string;
  /** 合神 */
  he_shen: string;
  taiyi: TaiyiTaiyi;
  wenchang: TaiyiMu;
  jishen: TaiyiJishen;
  shiji: TaiyiMu;
  dingmu: TaiyiMu;
  sansuan: TaiyiSuan[];
  bamen: TaiyiBamen;
  warnings: string[];
  /** 本版**未覆盖项**，界面应如实展示，不得省略 */
  uncertainties: string[];
}

export interface TaiyiSchool {
  id: string;
  name: string;
  jiyan_base: number;
  note: string;
}

/**
 * 起局界面需要的静态元数据。
 *
 * 宫号表 / 十六神落宫 / 文昌序列 / 值事八门都由接口返回而**不是前端自己算**：
 * 它们是领域数据（RULE-005），前端存一份必然与内核漂移。
 * 🔴 尤其 `palace_gua` —— 太乙宫号与洛书逐宫错位，若前端自己抄一份洛书
 * 必然整盘转 45°，且不报错。
 */
export interface TaiyiMetaResponse {
  schools: TaiyiSchool[];
  jiyan_base: number;
  /** 宫号 -> 卦名（太乙口径，🔴≠洛书） */
  palace_gua: Record<string, string>;
  palace_direction: Record<string, string>;
  palace_door_name: Record<string, string>;
  palace_fenye: Record<string, string>;
  palace_qi: Record<string, string>;
  /** 十六神位 -> 神名 */
  shen_names: Record<string, string>;
  /** 八正神 -> 宫号 */
  shen_palace: Record<string, number>;
  zheng_shen: string[];
  jian_shen: string[];
  /** 文昌十八年行宫序列 */
  wenchang_seq: string[];
  jishen_rule: string;
  bamen_order: string[];
  bamen_benwei: Record<string, string>;
  bamen_jixiong: Record<string, string>;
  /** 太乙行宫序列（跳过中五） */
  taiyi_xun_gong: number[];
  years_per_palace: number;
  cycle_years: number;
  wenchang_cycle_years: number;
  bamen_switch_years: number;
  bamen_cycle_years: number;
  wuyuan_names: string[];
  uncertainties: string[];
}

export interface TaiyiCastRequest {
  /**
   * 公元年份。太乙是**年局** —— 最小单位就是年，
   * 不接受日期或时刻（与奇门 / 六壬相反）。
   */
  year: number;
  school?: string;
}
