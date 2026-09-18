/**
 * 盘式探针 —— 把 `dialStyle.ts` **算出来**的结果以 JSON 打到 stdout。
 *
 * 为什么走探针而不是让 Python 正则扫源码：扫源码只能证明"字面量看起来一样"，
 * 证明不了"算出来一样"。盘式的层比例、先天八卦方位、盘式回落这几件事
 * 都要经过真实的函数调用才算数。
 *
 * 运行：node --experimental-strip-types scripts/dial_style_probe.ts
 */

import { DIAL_RATIOS, TRIGRAM_HOUTIAN } from '../src/lib/compassDial.ts';
import {
  DIAL_STYLES,
  DIAL_STYLE_ORDER,
  TRIGRAM_XIANTIAN,
  coerceDialStyle,
  hasLayer,
  isDialStyleId,
  layerRadius,
  layersOf,
  renderLayers,
  stepStyle,
  styleOf,
} from '../src/lib/dialStyle.ts';
import type { DialLayer, DialStyleId } from '../src/lib/dialStyle.ts';

const ALL: DialStyleId[] = ['simple', 'sanhe', 'zonghe'];

// ==========================================================================
// 自检一：层的几何必须自洽
// ==========================================================================

/** 层必须由外向内不重叠：第 k 层的内径 ≥ 第 k+1 层的外径 */
const layer_overlap_errors: string[] = [];
for (const id of ALL) {
  const ls = layersOf(id);
  for (let i = 0; i < ls.length - 1; i += 1) {
    const a = ls[i] as DialLayer;
    const b = ls[i + 1] as DialLayer;
    if (a.inner < b.outer - 1e-9) {
      overlap_over(a, b);
    }
  }
}
function overlap_over(a: DialLayer, b: DialLayer): void {
  layer_overlap_errors.push(
    `${a.id}(${a.outer}~${a.inner}) 与 ${b.id}(${b.outer}~${b.inner}) 之间有空隙或重叠`,
  );
}

/** 层必须在 (0,1] 内，且外径严格大于内径 */
const layer_range_errors: string[] = [];
for (const id of ALL) {
  for (const l of layersOf(id)) {
    if (l.outer > 1 + 1e-9) layer_range_errors.push(`${id}.${l.id} 外径 ${l.outer} > 1`);
    if (l.inner < -1e-9) layer_range_errors.push(`${id}.${l.id} 内径 ${l.inner} < 0`);
    if (l.outer <= l.inner) layer_range_errors.push(`${id}.${l.id} 外径 ${l.outer} 未大于内径 ${l.inner}`);
  }
}

/** 天池必须排在渲染列表末尾 —— 它是最后画的，即盖在最上面 */
const pool_last_errors: string[] = [];
for (const id of ALL) {
  const rendered = renderLayers(id, 300);
  const last = rendered[rendered.length - 1];
  if (!last || last.layer.id !== 'pool') {
    pool_last_errors.push(`${id} 的最后一层是 ${last?.layer.id ?? '(空)'}，应为 pool`);
  }
}

// ==========================================================================
// 自检二：先天八卦**不得**与后天八卦同方位
// ==========================================================================

/**
 * 这是本文件最重要的一条自检。
 *
 * 先天（伏羲）与后天（洛书）是两套方位，八个卦没有一个落在相同方位上。
 * 但两者都是「45° 一格、八个卦」，**把后天表复制给先天，画出来仍然是一圈
 * 像模像样的八卦**，只是每个卦都错位了 —— 属于典型的静默错误。
 * 故在此强制断言：逐卦比对，任一卦方位相同即报错。
 */
const xiantian_matches_houtian_errors: string[] = [];
const houtianByName = new Map(TRIGRAM_HOUTIAN.map((t) => [t.name, t.centerDegree]));
for (const t of TRIGRAM_XIANTIAN) {
  const h = houtianByName.get(t.name);
  if (h === undefined) {
    xiantian_matches_houtian_errors.push(`先天八卦含后天没有的卦名：${t.name}`);
  } else if (Math.abs(h - t.centerDegree) < 1e-9) {
    xiantian_matches_houtian_errors.push(
      `${t.name} 在先后天两表中都是 ${t.centerDegree}° —— 疑似把后天表复制给了先天`,
    );
  }
}

/** 先天八卦自身：8 个卦、方位互不相同、均为 45° 的整数倍 */
const xiantian_geometry_errors: string[] = [];
if (TRIGRAM_XIANTIAN.length !== 8) {
  xiantian_geometry_errors.push(`先天八卦应有 8 卦，实为 ${TRIGRAM_XIANTIAN.length}`);
}
const xiDegrees = TRIGRAM_XIANTIAN.map((t) => t.centerDegree);
if (new Set(xiDegrees).size !== xiDegrees.length) {
  xiantian_geometry_errors.push(`先天八卦方位有重复：${JSON.stringify(xiDegrees)}`);
}
for (const d of xiDegrees) {
  if (d % 45 !== 0) xiantian_geometry_errors.push(`先天八卦方位 ${d}° 不是 45° 的整数倍`);
}

// ==========================================================================
// 自检三：脏数据归一（存档里可能存着旧盘式名）
// ==========================================================================

const coerce_errors: string[] = [];
for (const junk of ['', 'nope', null, undefined, 42, {}, [], 'SIMPLE']) {
  const got = coerceDialStyle(junk);
  if (got !== 'zonghe') coerce_errors.push(`coerceDialStyle(${JSON.stringify(junk)}) = ${got}，应回落 zonghe`);
}
for (const good of ALL) {
  if (coerceDialStyle(good) !== good) coerce_errors.push(`合法盘式 ${good} 被改写`);
  if (!isDialStyleId(good)) coerce_errors.push(`isDialStyleId(${good}) 判为 false`);
}
if (isDialStyleId('nope') || isDialStyleId(null)) coerce_errors.push('isDialStyleId 对脏数据判为 true');

// ==========================================================================
// 自检四：盘式切换可循环
// ==========================================================================

const step_errors: string[] = [];
for (const id of ALL) {
  const fwd = stepStyle(id, 1);
  const back = stepStyle(id, -1);
  if (stepStyle(fwd, -1) !== id) step_errors.push(`${id} 前进再后退未回到原位（得到 ${stepStyle(fwd, -1)}）`);
  if (stepStyle(back, 1) !== id) step_errors.push(`${id} 后退再前进未回到原位（得到 ${stepStyle(back, 1)}）`);
}
// 转满一圈必须回到起点
let cur: DialStyleId = DIAL_STYLE_ORDER[0] as DialStyleId;
for (let i = 0; i < DIAL_STYLE_ORDER.length; i += 1) cur = stepStyle(cur, 1);
if (cur !== DIAL_STYLE_ORDER[0]) step_errors.push(`转满一圈回到 ${cur}，应为 ${DIAL_STYLE_ORDER[0]}`);

// ==========================================================================
// 自检五：simple 盘式必须与 DIAL_RATIOS 逐项相等
// ==========================================================================

/**
 * `simple` 是既有盘面的几何。它若与 `DIAL_RATIOS` 漂移，
 * 同一 size 会算出两个不同的盘 —— 一个走旧渲染路径、一个走新盘式路径。
 */
const simple_vs_ratios: Record<string, { ts: number; py: number; ok: boolean }> = {
  mountainOuter: cmp(layerRadius('simple', 'mountain24', 100)!.outer, DIAL_RATIOS.mountainOuter * 50),
  mountainInner: cmp(layerRadius('simple', 'mountain24', 100)!.inner, DIAL_RATIOS.mountainInner * 50),
  trigramOuter: cmp(layerRadius('simple', 'houtian', 100)!.outer, DIAL_RATIOS.trigramOuter * 50),
  trigramInner: cmp(layerRadius('simple', 'houtian', 100)!.inner, DIAL_RATIOS.trigramInner * 50),
  tickOuter: cmp(layerRadius('simple', 'fenjin', 100)!.outer, DIAL_RATIOS.tickOuter * 50),
  tickInner: cmp(layerRadius('simple', 'fenjin', 100)!.inner, DIAL_RATIOS.tickInner * 50),
  pool: cmp(layerRadius('simple', 'pool', 100)!.outer, DIAL_RATIOS.pool * 50),
};
function cmp(a: number, b: number): { ts: number; py: number; ok: boolean } {
  return { ts: a, py: b, ok: Math.abs(a - b) < 1e-9 };
}

const simple_ratio_errors = Object.entries(simple_vs_ratios)
  .filter(([, v]) => !v.ok)
  .map(([k, v]) => `${k}: simple 层算得 ${v.ts}，DIAL_RATIOS 算得 ${v.py}`);

// ==========================================================================
// 自检六：层存在性判定
// ==========================================================================

const has_layer_errors: string[] = [];
if (hasLayer('simple', 'xiantian')) has_layer_errors.push('simple 不应含先天八卦层');
for (const id of ['sanhe', 'zonghe'] as DialStyleId[]) {
  for (const lid of ['fenjin', 'mountain24', 'houtian', 'xiantian', 'pool'] as const) {
    if (!hasLayer(id, lid)) has_layer_errors.push(`${id} 缺少层 ${lid}`);
  }
}
if (layerRadius('simple', 'xiantian', 300) !== null) has_layer_errors.push('simple 取先天八卦半径应得 null');

// ==========================================================================
// 输出
// ==========================================================================

const radius_at: Record<string, Record<string, number>> = {};
for (const id of ALL) {
  radius_at[id] = {};
  for (const { layer, radius } of renderLayers(id, 280)) {
    radius_at[id]![layer.id] = Number(radius.outer.toFixed(4));
  }
}

process.stdout.write(
  JSON.stringify(
    {
      order: DIAL_STYLE_ORDER,
      styles: Object.fromEntries(
        ALL.map((id) => {
          const s = styleOf(id);
          return [
            id,
            {
              id: s.id,
              name: s.name,
              statedLayers: s.statedLayers,
              blurb: s.blurb,
              layers: s.layers.map((l) => ({ id: l.id, outer: l.outer, inner: l.inner })),
            },
          ];
        }),
      ),
      simple_layers: layersOf('simple').map((l) => ({ id: l.id, outer: l.outer, inner: l.inner })),
      dial_ratios: { ...DIAL_RATIOS },
      simple_vs_ratios,
      radius_at,
      xiantian: TRIGRAM_XIANTIAN.map((t) => ({ name: t.name, center_degree: t.centerDegree, yao: [...t.yao] })),
      houtian: TRIGRAM_HOUTIAN.map((t) => ({ name: t.name, center_degree: t.centerDegree, yao: [...t.yao] })),
      coerce: { default: coerceDialStyle('nope') },
      checks: {
        layer_overlap_errors,
        layer_range_errors,
        pool_last_errors,
        xiantian_matches_houtian_errors,
        xiantian_geometry_errors,
        coerce_errors,
        step_errors,
        simple_ratio_errors,
        has_layer_errors,
      },
    },
    null,
    1,
  ),
);
