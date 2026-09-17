/**
 * 后端候选地址探针 —— 把 `src/lib/apiCandidates.ts` 的**真实输出**导成 JSON，
 * 供 `tests/mobile/test_api_candidates.py` 校验。
 *
 * ## 为什么必须真跑
 *
 * 这段逻辑决定「APP 能不能连上后端」。扫源码只能证明"文件里写了去重"，
 * 证明不了"三个网段的候选表合出来还是有序的、且探活不会卡死"。
 *
 * ## 为什么连 `app.config.js` 一起测
 *
 * 候选表的规范化规则存在**两份**实现：一份在本探针导入的 TS 模块（运行期），
 * 一份在 `app.config.js`（构建期，CommonJS，无法共享模块）。两份漂移的后果是
 * 「构建期注入了 4 个地址，运行期只认 1 个」—— 不报错，只是换网段不生效。
 * 所以这里把构建期那份也真 require 进来跑，逐项比对。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/api_candidates_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除。
 */

import { createRequire } from 'node:module';

import {
  mergeCandidateSources,
  normalizeCandidateUrls,
  pickFirstReachable,
} from '../src/lib/apiCandidates.ts';

// ==========================================================================
// 1. 规范化：一串文本 → 规范地址表
// ==========================================================================

const normalize_cases = [
  { name: 'plain', input: 'http://a:8360' },
  { name: 'comma', input: 'http://a:8360,http://b:8360' },
  { name: 'spaces', input: '  http://a:8360 ,  http://b:8360  ' },
  { name: 'trailing_slash', input: 'http://a:8360///' },
  { name: 'dedupe', input: 'http://a:8360,http://a:8360,http://b:8360' },
  { name: 'dedupe_after_normalize', input: 'http://a:8360/,http://a:8360' },
  { name: 'drop_non_http', input: 'http://a:8360,ftp://b:8360,hello' },
  { name: 'drop_empty', input: 'http://a:8360,,  ,http://b:8360' },
  { name: 'https_kept', input: 'https://a.example.com:8360' },
  { name: 'all_invalid', input: 'ftp://a,not-a-url,  ' },
  { name: 'empty', input: '' },
  { name: 'undefined', input: undefined },
  { name: 'null', input: null },
].map((c) => ({
  ...c,
  // JSON 里 undefined 会整个丢掉，显式记成 null 才能让 pytest 分清
  // "输入是 undefined" 与 "这条用例根本没跑"
  input: c.input === undefined ? null : c.input,
  output: normalizeCandidateUrls(c.input),
}));

// ==========================================================================
// 2. 合并：多来源按优先级 + 去重 + 保序
// ==========================================================================

const merge_cases = [
  {
    name: 'priority_order',
    sources: ['http://first:8360', 'http://second:8360'],
  },
  {
    name: 'cross_source_dedupe',
    // second 里重复了 first 的地址：保留它在**先出现**的位置，不得后移
    sources: ['http://a:8360,http://b:8360', 'http://b:8360,http://c:8360'],
  },
  {
    name: 'array_source',
    sources: [null, ['http://arr1:8360', 'http://arr2:8360']],
  },
  {
    name: 'array_and_string_mixed',
    sources: [['http://arr:8360'], 'http://str:8360,http://arr:8360'],
  },
  {
    name: 'skips_falsy',
    sources: [undefined, null, '', 'http://only:8360', undefined],
  },
  {
    name: 'array_with_invalid_items',
    sources: [['http://ok:8360', 'garbage', '', 'ftp://no:8360']],
  },
  {
    name: 'empty_sources',
    sources: [undefined, null, ''],
  },
].map((c) => ({ ...c, output: mergeCandidateSources(c.sources) }));

// ==========================================================================
// 3. 探活：并发取第一个回应，全失败不卡死
// ==========================================================================

interface PickCase {
  name: string;
  candidates: string[];
  got: string | null;
  /** 实际被尝试过的地址（去重后排序，避免受并发完成顺序影响） */
  tried: string[];
  /** 从调用到 resolve 的耗时（毫秒）—— 用来证明"全失败也不会卡" */
  elapsed_ms: number;
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** 构造一个「按给定延迟与成败表应答」的探针 */
function makeProbe(
  tried: string[],
  plan: Record<string, { ok: boolean; delayMs: number }>,
): (url: string) => Promise<unknown> {
  return async (url: string) => {
    tried.push(url);
    const step = plan[url] ?? { ok: false, delayMs: 0 };
    await delay(step.delayMs);
    if (!step.ok) throw new Error(`probe failed: ${url}`);
    return url;
  };
}

const pick_cases: PickCase[] = [];

async function runPick(
  name: string,
  candidates: string[],
  plan: Record<string, { ok: boolean; delayMs: number }>,
): Promise<void> {
  const tried: string[] = [];
  const t0 = Date.now();
  const got = await pickFirstReachable(candidates, makeProbe(tried, plan));
  pick_cases.push({
    name,
    candidates,
    got,
    tried: [...new Set(tried)].sort(),
    elapsed_ms: Date.now() - t0,
  });
}

// 首个候选即可用：应立刻返回它，且**不必等**慢的那个
await runPick('first_ok', ['http://a', 'http://b'], {
  'http://a': { ok: true, delayMs: 0 },
  'http://b': { ok: false, delayMs: 50 },
});

// 靠前的候选很慢、靠后的很快：应返回**先回应的**那个（b），而不是死等 a
await runPick('fast_later_wins', ['http://slow', 'http://fast'], {
  'http://slow': { ok: true, delayMs: 80 },
  'http://fast': { ok: true, delayMs: 0 },
});

// 只有一个可用，且在中间
await runPick('middle_ok', ['http://a', 'http://b', 'http://c'], {
  'http://a': { ok: false, delayMs: 0 },
  'http://b': { ok: true, delayMs: 0 },
  'http://c': { ok: false, delayMs: 0 },
});

// 全部失败 → null（且必须 settle，不能挂住）
await runPick('all_fail', ['http://a', 'http://b', 'http://c'], {
  'http://a': { ok: false, delayMs: 0 },
  'http://b': { ok: false, delayMs: 10 },
  'http://c': { ok: false, delayMs: 20 },
});

// 空表 → null
{
  const t0 = Date.now();
  const tried: string[] = [];
  const got = await pickFirstReachable([], makeProbe(tried, {}));
  pick_cases.push({
    name: 'empty',
    candidates: [],
    got,
    tried: [],
    elapsed_ms: Date.now() - t0,
  });
}

// 并发性自检：最慢的那个失败也要试到，且总耗时**明显小于**串行累加。
// 串行 = 30+60+90 = 180ms；并发应 ≈ 90ms。取 150ms 作判据留出余量。
await runPick('concurrent_not_serial', ['http://a', 'http://b', 'http://c'], {
  'http://a': { ok: false, delayMs: 30 },
  'http://b': { ok: false, delayMs: 60 },
  'http://c': { ok: false, delayMs: 90 },
});

// ==========================================================================
// 4. 构建期那份实现（app.config.js）—— 与运行期逐项比对
// ==========================================================================

const require_ = createRequire(import.meta.url);
// eslint-disable-next-line @typescript-eslint/no-var-requires
const appConfigFn = require_('../app.config.js') as (arg: {
  config: Record<string, unknown>;
}) => { extra: Record<string, unknown> };

/**
 * 以给定环境变量跑一次构建期配置，取回它算出的候选表。
 *
 * 每次都先把两个变量清空再按需设置 —— 否则上一轮的残留会让下一轮
 * 得到"看起来对"的结果（这正是构建期注入最容易出错的地方）。
 */
function runAppConfig(urls?: string, single?: string): string[] {
  delete process.env.XUANPAN_API_BASE_URLS;
  delete process.env.XUANPAN_API_BASE_URL;
  if (urls !== undefined) process.env.XUANPAN_API_BASE_URLS = urls;
  if (single !== undefined) process.env.XUANPAN_API_BASE_URL = single;

  const out = appConfigFn({ config: { extra: { apiBaseUrl: 'http://fallback:8360' } } });
  return out.extra.apiBaseUrls as string[];
}

const app_config_cases = [
  {
    name: 'list_only',
    urls: 'http://a:8360,http://b:8360',
    single: undefined,
    output: runAppConfig('http://a:8360,http://b:8360', undefined),
  },
  {
    name: 'single_only',
    urls: undefined,
    single: 'http://solo:8360',
    output: runAppConfig(undefined, 'http://solo:8360'),
  },
  {
    name: 'both_list_wins',
    // list 存在时以 list 为准，single 只是"首选"语义
    urls: 'http://a:8360,http://b:8360',
    single: 'http://solo:8360',
    output: runAppConfig('http://a:8360,http://b:8360', 'http://solo:8360'),
  },
  {
    name: 'neither_falls_back',
    urls: undefined,
    single: undefined,
    output: runAppConfig(undefined, undefined),
  },
  {
    name: 'dedupe_and_trim',
    urls: ' http://a:8360 , http://a:8360 , http://b:8360/ ',
    single: undefined,
    output: runAppConfig(' http://a:8360 , http://a:8360 , http://b:8360/ ', undefined),
  },
  {
    name: 'all_invalid_falls_back',
    // 全部非法时不能得到空表 —— 空表会让"首选地址"与"候选表"指两个后端
    urls: 'ftp://x,garbage',
    single: undefined,
    output: runAppConfig('ftp://x,garbage', undefined),
  },
];

// 交叉一致性：同样的输入，构建期与运行期的**规范化结果**必须逐项相同。
//
// ⚠️ 不能直接比 `build == runtime`：两者职责本就不同 ——
// `normalizeCandidateUrls` 是纯规范化（输入全非法就该得到空表），
// 而 `app.config.js` 还要保证**表非空**（空表会让"首选地址"与"候选表"
// 指向两个不同的后端）。所以构建期结果 = 运行期结果 + 可能的一项兜底。
// 比对时把兜底那项剥离，否则比的是两种不同职责的产物，属测试设计错误。
const CROSS_FALLBACK = 'http://fallback:8360';

const cross_consistency = [
  'http://a:8360,http://b:8360',
  ' http://a:8360 , http://a:8360 , http://b:8360/ ',
  'http://only:8360',
  'ftp://x,garbage',
].map((raw) => {
  const runtime = normalizeCandidateUrls(raw);
  const build = runAppConfig(raw, undefined);
  return {
    raw,
    runtime,
    build,
    build_without_fallback: build.filter((u) => u !== CROSS_FALLBACK),
    /** 构建期是否恰好"运行期结果 + 兜底"——这才是两边应有的关系 */
    build_is_runtime_plus_fallback:
      build.filter((u) => u !== CROSS_FALLBACK).join(',') === runtime.join(','),
  };
});

process.stdout.write(
  JSON.stringify({
    normalize_cases,
    merge_cases,
    pick_cases,
    app_config_cases,
    cross_consistency,
  }),
);
