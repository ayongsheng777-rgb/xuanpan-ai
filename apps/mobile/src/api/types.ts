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
  sections: ReportSection[];
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
