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
