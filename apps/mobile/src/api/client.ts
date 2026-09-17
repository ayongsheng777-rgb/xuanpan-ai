/**
 * 后端 API 客户端。
 *
 * 三条设计原则：
 *
 * 1. **错误必须带可读原因**。后端已经把"谁的错"分成了 400/404/413/422/503，
 *    这里把 `{"detail": "..."}` 抽出来包成 `ApiError`，让界面能直接显示
 *    「坐山「戊」不是二十四山之一；可用值：…」。若只抛 `Request failed: 400`，
 *    用户看到的是一句没有信息量的红字。
 *
 * 2. **只读与写分离**。所有写操作（确认坐向、生成报告）都是显式方法，
 *    不做"自动重试" —— 生成报告要花钱，重试会把账单翻倍。
 *
 * 3. **不在客户端持有任何模型密钥**（AGENTS.md §5.5 红线）：
 *    provider 的能力与可用性一律从 `/meta/ai-providers` 读服务端状态，
 *    客户端只负责**展示**，不负责录入 key。
 *
 * ## 为什么公开方法写成箭头函数属性，而不是普通类方法
 *
 * 普通类方法依赖调用时的接收者。一旦把它当值传出去 ——
 * 例如 `useSubmit(getApiClient().scan)` —— 就丢了 `this`，
 * 方法内部 `this.request` 抛 `TypeError: Cannot read properties of undefined`。
 *
 * 这个坑**不会在编译期暴露**：类型完全合法，只在用户真的按下按钮时才炸。
 * 本次开发中它一次性出现在 9 个调用点上（八字页、占测页各若干），
 * 说明问题不在调用方粗心，而在 API 形状本身 —— 一个"必须先 bind 才能用"
 * 的对象是易误用的接口。所以根治方式是让它天生可传：
 * 公开方法一律写成箭头函数属性（词法捕获 `this`），
 * 调用方无论怎么传都不会丢接收者。
 *
 * 私有的 `request` / `json` 保持普通方法 —— 它们从不被单独传出去，
 * 且每次调用都显式写成 `this.request(...)`。
 */

import Constants from 'expo-constants';

import {
  mergeCandidateSources,
  normalizeCandidateUrls,
  pickFirstReachable,
} from '../lib/apiCandidates';

import type {
  AiProvidersResponse,
  AlmanacDay,
  AlmanacRange,
  AskRequest,
  BaziInput,
  CapabilitiesResponse,
  CompassConfirmRequest,
  CompassInput,
  DeletedResponse,
  DuanLiuyaoRequest,
  DuanResponse,
  InputPatch,
  LayerPreview,
  LiurenCastRequest,
  LiurenChart,
  LiurenMetaResponse,
  LiuyaoInput,
  MountainsResponse,
  NamingInput,
  QianInput,
  QianSet,
  QuestionCategoriesResponse,
  QimenCastRequest,
  QimenChart,
  QimenMetaResponse,
  RecognitionSnapshot,
  ReportMeta,
  ReportRequest,
  ReportResponse,
  ScanResult,
  SessionCreated,
  SessionDetail,
  SessionListResponse,
  Turn,
  VisionProvidersResponse,
  ZeriDayResponse,
  ZeriEventsResponse,
  ZeriResultResponse,
  ZeriSelectRequest,
} from './types';

// ==========================================================================
// 错误
// ==========================================================================

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly code?: string;

  constructor(status: number, detail: string, code?: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.code = code;
  }

  /** 是否为"用户输入不成立"类错误（可直接把 detail 展示给用户） */
  get isUserFixable(): boolean {
    return this.status === 400 || this.status === 413 || this.status === 422;
  }
}

/** 网络层失败（断网、后端没起、超时）—— 与"后端返回错误"是两回事 */
export class NetworkError extends Error {
  // `override` 是必需的：`cause` 在 ES2022 的 `Error` 上已存在，
  // 漏写会被 tsc 判为 TS4115（tsconfig 的 lib 含 ESNext，故该成员可见）。
  constructor(message: string, override readonly cause?: unknown) {
    super(message);
    this.name = 'NetworkError';
  }
}

// ==========================================================================
// 客户端
// ==========================================================================

export interface ApiClientOptions {
  baseUrl: string;
  /** 超时（毫秒）。识别与报告都要跑模型，给得比普通请求宽 */
  timeoutMs?: number;
  /** 注入用（测试/自定义 fetch） */
  fetchImpl?: typeof fetch;
}

const DEFAULT_TIMEOUT = 20_000;
const HEAVY_TIMEOUT = 90_000;

/**
 * 后端默认地址。
 *
 * 刻意**不是 8352** —— 该端口被同机另一个服务（SysCenter）占用，
 * 用它会让"后端没起"与"端口被别的东西占了"这两种故障长得一模一样。
 */
export const DEFAULT_BASE_URL = 'http://127.0.0.1:8360';

export class ApiClient {
  readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(opts: ApiClientOptions) {
    this.baseUrl = opts.baseUrl.replace(/\/+$/, '');
    this.timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT;
    // RN 全局有 fetch；绑定到 globalThis 避免 "Illegal invocation"
    this.fetchImpl = opts.fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  // ------------------------------------------------------------------ 内部

  private async request<T>(
    path: string,
    init: RequestInit & { timeoutMs?: number } = {},
  ): Promise<T> {
    const { timeoutMs, ...rest } = init;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs ?? this.timeoutMs);

    let res: Response;
    try {
      res = await this.fetchImpl(`${this.baseUrl}${path}`, {
        ...rest,
        signal: controller.signal,
        headers: { Accept: 'application/json', ...(rest.headers ?? {}) },
      });
    } catch (err) {
      // AbortError 也要区分出来：超时与"后端没起"对用户的指引完全不同
      if (err instanceof Error && err.name === 'AbortError') {
        throw new NetworkError('请求超时，请检查后端服务是否可用', err);
      }
      throw new NetworkError('无法连接后端服务，请检查地址与网络', err);
    } finally {
      clearTimeout(timer);
    }

    const text = await res.text();
    const body = text ? safeJson(text) : null;

    if (!res.ok) {
      const detail =
        (body && typeof body === 'object' && 'detail' in body
          ? String((body as { detail: unknown }).detail)
          : null) ?? `请求失败（HTTP ${res.status}）`;
      const code =
        body && typeof body === 'object' && 'error' in body
          ? String((body as { error: unknown }).error)
          : undefined;
      throw new ApiError(res.status, detail, code);
    }

    return body as T;
  }

  private json<T>(path: string, method: string, payload?: unknown, timeoutMs?: number): Promise<T> {
    return this.request<T>(path, {
      method,
      headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      timeoutMs,
    });
  }

  // ------------------------------------------------------------------ 运维

  health = (): Promise<{ status: string; db: string; ai_mode: string; keep_photos: boolean }> =>
    this.request('/healthz');

  // ------------------------------------------------------------------ 元信息

  mountains = (): Promise<MountainsResponse> => this.request('/api/v1/meta/mountains');

  questionCategories = (): Promise<QuestionCategoriesResponse> =>
    this.request('/api/v1/meta/question-categories');

  aiProviders = (): Promise<AiProvidersResponse> => this.request('/api/v1/meta/ai-providers');

  visionProviders = (): Promise<VisionProvidersResponse> =>
    this.request('/api/v1/meta/vision-providers');

  qianSets = (): Promise<{ sets: QianSet[] }> => this.request('/api/v1/meta/qian-sets');

  capabilities = (): Promise<CapabilitiesResponse> => this.request('/api/v1/meta/capabilities');

  disclaimer = (): Promise<{ disclaimer: string }> => this.request('/api/v1/meta/disclaimer');

  // ------------------------------------------------------------------ 识别

  /**
   * 上传罗盘照片识别。
   *
   * 相机与相册在客户端是两个入口，但**走同一个方法** —— 基线规范 §4.1
   * 要求"相册里的旧照片同样必须先过质量检测"，分两个方法迟早有人只给相机加质检。
   */
  scan = async (uri: string, filename = 'compass.jpg'): Promise<ScanResult> => {
    const form = new FormData();
    // RN 的 FormData 接受 {uri, name, type} 这种"文件对象"
    form.append('image', {
      uri,
      name: filename,
      type: guessMime(filename),
    } as unknown as Blob);

    return this.request<ScanResult>('/api/v1/scan?provider=classical', {
      method: 'POST',
      body: form,
      timeoutMs: HEAVY_TIMEOUT,
    });
  };

  // ------------------------------------------------------------------ 会话

  createSession = (
    payload: {
      question_category?: string | null;
      question_text?: string | null;
      title?: string | null;
    } = {},
  ): Promise<SessionCreated> => this.json('/api/v1/sessions', 'POST', payload);

  listSessions = (limit = 50, offset = 0): Promise<SessionListResponse> =>
    this.request(`/api/v1/sessions?limit=${limit}&offset=${offset}`);

  getSession = (sessionId: string): Promise<SessionDetail> =>
    this.request(`/api/v1/sessions/${encodeURIComponent(sessionId)}`);

  patchInputs = (
    sessionId: string,
    patch: InputPatch,
  ): Promise<{
    session_id: string;
    updated: string[];
    previews: Record<string, LayerPreview>;
  }> => this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}/inputs`, 'PATCH', patch);

  /** 确认坐向 —— 识别链路进入计算链路的**唯一**放行点（RULE-004） */
  confirmCompass = (sessionId: string, payload: CompassConfirmRequest): Promise<LayerPreview> =>
    this.json(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/compass/confirm`,
      'POST',
      payload,
    );

  deleteSession = (sessionId: string): Promise<DeletedResponse> =>
    this.json(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, 'DELETE');

  // ------------------------------------------------------------------ 计算预览

  calcCompass = (input: CompassInput): Promise<LayerPreview> =>
    this.json('/api/v1/calc/compass', 'POST', input);

  calcBazi = (input: BaziInput): Promise<LayerPreview> =>
    this.json('/api/v1/calc/bazi', 'POST', input);

  calcLiuyao = (input: LiuyaoInput): Promise<LayerPreview> =>
    this.json('/api/v1/calc/liuyao', 'POST', input);

  calcQian = (input: QianInput): Promise<LayerPreview> =>
    this.json('/api/v1/calc/qian', 'POST', input);

  calcNaming = (input: NamingInput): Promise<LayerPreview> =>
    this.json('/api/v1/calc/naming', 'POST', input);

  // ------------------------------------------------------------------ 日历域

  /**
   * 单日黄历。
   *
   * `date` 省略则由**服务端**定"今天"。不让客户端自己算日期：
   * 客户端时区与服务器时区不一致时，同一时刻会得到不同的"今天"，
   * 而用户看到的日期与后端算的黄历就会对不上。
   */
  almanacDay = (date?: string): Promise<AlmanacDay> =>
    this.request(`/api/v1/almanac/day${date ? `?date=${encodeURIComponent(date)}` : ''}`);

  almanacRange = (start: string, end: string): Promise<AlmanacRange> =>
    this.request(
      `/api/v1/almanac/range?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
    );

  zeriEvents = (): Promise<ZeriEventsResponse> => this.request('/api/v1/zeri/events');

  zeriEvaluate = (
    event: string,
    date: string,
    options: { shengxiao?: string | null; school?: string } = {},
  ): Promise<ZeriDayResponse> => {
    const params = new URLSearchParams({ event, date });
    if (options.shengxiao) params.set('shengxiao', options.shengxiao);
    if (options.school) params.set('school', options.school);
    return this.request(`/api/v1/zeri/evaluate?${params.toString()}`);
  };

  zeriSelect = (input: ZeriSelectRequest): Promise<ZeriResultResponse> =>
    this.json('/api/v1/zeri/select', 'POST', input);

  // ------------------------------------------------------------------ 断卦

  /**
   * 六爻断卦（起卦 → 装卦 → 断，三步齐全）。
   *
   * `topic` 决定取哪个六亲为用神 —— 不传就只能给整体卦象倾向，
   * 界面上应当提示用户补选，而不是把"没取用神"的中平当成结论展示。
   */
  duanLiuyao = (input: DuanLiuyaoRequest): Promise<DuanResponse> =>
    this.json('/api/v1/duan/liuyao', 'POST', input);

  duanBazi = (input: BaziInput): Promise<DuanResponse> =>
    this.json('/api/v1/duan/bazi', 'POST', input);

  // ------------------------------------------------------------------ 三式 · 奇门

  /**
   * 奇门排盘的静态元数据（局数表 / 流派 / 未覆盖项）。
   *
   * 界面的「这一局是怎么来的」面板读它，**不自己维护一份局数表** ——
   * 局数表是领域数据（RULE-005），前端存一份必然与内核漂移，
   * 而漂移的表现是「界面显示的局数与实排不符」，不报错、只静默不一致。
   */
  qimenMeta = (): Promise<QimenMetaResponse> => this.request('/api/v1/qimen/meta');

  /**
   * 奇门排盘。
   *
   * `dt` 必须是**本地时刻**且含时分 —— 奇门以时辰起局，
   * 只给日期排不出盘（内核不会替你猜时辰）。
   */
  qimenPan = (input: QimenCastRequest): Promise<QimenChart> =>
    this.json('/api/v1/qimen/pan', 'POST', input);

  // ---------------------------------------------------------------- 大六壬

  /**
   * 六壬元数据：月将表 / 十干寄宫 / 十二天将 / 九宗门。
   *
   * 「这一课是怎么来的」面板读它，**不自己维护一份月将表** ——
   * 月将表是领域数据（RULE-005），前端存一份必然与内核漂移，
   * 而漂移的表现是「界面显示的月将与实排不符」，不报错、只静默不一致。
   */
  liurenMeta = (): Promise<LiurenMetaResponse> => this.request('/api/v1/liuren/meta');

  /**
   * 大六壬起课。
   *
   * `dt` 必须是**本地时刻**且含时分 —— 六壬以月将加时起课，
   * 同一个日子的不同时辰是完全不同的课，只给日期排不出课。
   */
  liurenCast = (input: LiurenCastRequest): Promise<LiurenChart> =>
    this.json('/api/v1/liuren/cast', 'POST', input);

  // ------------------------------------------------------------------ 报告

  /** 生成报告（写操作，**不自动重试** —— 要花钱） */
  generateReport = (sessionId: string, req: ReportRequest = {}): Promise<ReportResponse> =>
    this.json(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/report`,
      'POST',
      req,
      HEAVY_TIMEOUT,
    );

  ask = (sessionId: string, req: AskRequest): Promise<ReportResponse> =>
    this.json(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/ask`,
      'POST',
      req,
      HEAVY_TIMEOUT,
    );

  listReports = (sessionId: string): Promise<{ items: ReportMeta[] }> =>
    this.request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/reports`);

  listTurns = (sessionId: string): Promise<{ items: Turn[] }> =>
    this.request(`/api/v1/sessions/${encodeURIComponent(sessionId)}/turns`);

  getReport = (
    reportId: string,
  ): Promise<{
    report_id: string;
    session_id: string;
    created_at: string;
    question: string | null;
    payload: Record<string, unknown>;
  }> => this.request(`/api/v1/reports/${encodeURIComponent(reportId)}`);
}

// ==========================================================================
// 工具
// ==========================================================================

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function guessMime(filename: string): string {
  const lower = filename.toLowerCase();
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  if (lower.endsWith('.heic')) return 'image/heic';
  return 'image/jpeg';
}

/** 供 `RecognitionSnapshot` 类型收窄用（后端返回的识别快照） */
export type { RecognitionSnapshot };

// ==========================================================================
// 默认实例
// ==========================================================================

/**
 * 从构建期注入或 Expo 配置读后端地址。
 *
 * 默认 `http://127.0.0.1:8360`（**不是 8352** —— 该端口被本机 SysCenter 占用）。
 * 真机调试时改为局域网 IP，例如 `http://192.168.57.10:8360`。
 *
 * 三级优先级，越靠前越"离构建现场越近"：
 *
 * 1. `EXPO_PUBLIC_API_BASE_URL` —— babel-preset-expo 打包时内联为字面量。
 *    真机包走这条：地址随构建命令给出，不必改任何受版本控制的文件。
 * 2. `app.json` 的 `extra.apiBaseUrl`（可被 `app.config.js` 覆盖）。
 * 3. 兜底常量，与 app.json 里的值保持一致。
 *
 * 为什么不只留第 2 条：`extra` 要经 expo-constants 从原生侧取回，
 * 链路长且失败时**静默退回默认值** —— 用户看到的只是"连不上"，
 * 而看不出是地址根本没进包。第 1 条是官方文档化的内联机制，行为确定。
 */
export function resolveBaseUrl(): string {
  const injected = process.env.EXPO_PUBLIC_API_BASE_URL;
  if (injected) return injected.replace(/\/+$/, '');

  // 静态导入而非 require()：本工程 tsconfig 的 `types` 只放行 react-native，
  // Node 的 `require` 全局并不在其中，用 require 会报 "Cannot find name"。
  const cfg = Constants.expoConfig;
  return cfg?.extra?.apiBaseUrl ?? DEFAULT_BASE_URL;
}

// 地址规范化与探活是两个纯函数，落在 lib/apiCandidates 里以便被真跑测试
// （裸 node 无法 import 本文件 —— expo-constants 只在 RN 运行时存在）。
// 这里再导出一次，调用方不必知道它们搬过家。
export { normalizeCandidateUrls };

/**
 * 本次构建内可用的全部后端候选地址，**顺序即优先级**。
 *
 * 为什么要一张表而不是一个值：构建机常有多块网卡分属不同网段，每一块都能访问
 * 后端，而 APK 只能内联一个 —— 手机不在那个网段就连不上，现象只是"一直转圈"。
 * 实测本机同时存在 192.168.57.10 / 192.168.59.56 / 192.168.68.80 三个可用网段。
 *
 * 来源优先级与 `resolveBaseUrl` 同构：内联字面量 → extra → 兜底常量。
 * 内联的那条是官方文档化机制，行为确定；extra 要经 expo-constants 从原生侧
 * 取回，链路长，失败时**静默退回默认值**。
 */
export function candidateBaseUrls(): string[] {
  const cfg = Constants.expoConfig;
  // 来源顺序即优先级，合并与去重规则见 lib/apiCandidates。
  // 本函数只负责「去哪取」，不负责「怎么合」—— 后者才是有分支、需要测试的部分。
  return mergeCandidateSources([
    process.env.EXPO_PUBLIC_API_BASE_URLS,
    process.env.EXPO_PUBLIC_API_BASE_URL,
    cfg?.extra?.apiBaseUrls,
    cfg?.extra?.apiBaseUrl,
    DEFAULT_BASE_URL,
  ]);
}

/** 探活单个地址：能连上**且确实是玄盘后端**才算通过。 */
async function probeOne(
  url: string,
  timeoutMs: number,
  fetchImpl?: typeof fetch,
): Promise<string> {
  const probe = new ApiClient({ baseUrl: url, timeoutMs, fetchImpl });
  const h = await probe.health();
  // 光看"HTTP 200"不够：同一网段上别的服务也可能在该端口应答。
  // /healthz 的响应体形状才是后端身份的判据。
  if (!h || h.status !== 'ok') throw new Error(`非玄盘后端: ${url}`);
  return url;
}

/**
 * 并发探活候选表，返回第一个回应的可用地址；全都不通返回 null（不抛异常）。
 *
 * 并发与"取第一个成功"的取舍见 lib/apiCandidates 的 `pickFirstReachable`；
 * 本函数只补上"怎样才算一个可用的玄盘后端"（`probeOne` 的响应体校验）。
 */
export async function probeCandidates(
  candidates: string[],
  opts: { timeoutMs?: number; fetchImpl?: typeof fetch } = {},
): Promise<string | null> {
  const timeoutMs = opts.timeoutMs ?? 2500;
  return pickFirstReachable(candidates, (url) =>
    probeOne(url, timeoutMs, opts.fetchImpl),
  );
}

/**
 * 启动时自动选线：探活候选表，切到第一个可达的地址。
 *
 * 全都不通时**保持原地址不动**并返回 null —— 不抛异常。启动期的网络失败是
 * 常态（后端没起、手机不在同一网段），把它变成一个崩溃或红屏，会让用户
 * 连"我的 → 网络线路"这个手改入口都进不去。
 *
 * 返回最终生效的地址（探活失败则为当前地址）。
 */
export async function autoSelectBaseUrl(
  opts: { timeoutMs?: number; fetchImpl?: typeof fetch } = {},
): Promise<string | null> {
  const current = resolveBaseUrl();
  const ordered = [current, ...candidateBaseUrls().filter((u) => u !== current)];
  const picked = await probeCandidates(ordered, opts);
  if (picked && picked !== current) setApiBaseUrl(picked);
  return picked;
}

let _client: ApiClient | null = null;

export function getApiClient(): ApiClient {
  if (!_client) {
    _client = new ApiClient({ baseUrl: resolveBaseUrl() });
  }
  return _client;
}

/** 切换后端地址（「我的 → 网络线路」用） */
export function setApiBaseUrl(baseUrl: string): ApiClient {
  _client = new ApiClient({ baseUrl });
  return _client;
}
