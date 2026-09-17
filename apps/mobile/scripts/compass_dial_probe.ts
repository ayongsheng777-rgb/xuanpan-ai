/**
 * 罗盘盘面探针 —— 把 `lib/compassDial.ts` 的盘式数据与几何结果导出成 JSON，
 * 供 Python 侧与 `fortune_core` 做**跨语言一致性校验**
 * （见 `tests/mobile/test_compass_dial_parity.py`）。
 *
 * 为什么需要这道校验：盘面上有三处"同一规则存在两处实现"，一旦漂移就会
 * **静默错位**（用户看不出盘面画错了，只会觉得"这 App 的罗盘不对劲"）：
 *
 *   1. **后天八卦方位** —— 前端画卦符，后端 `GUA_HOUTIAN_DEGREE` 算方位
 *   2. **一百二十分金分格** —— 前端画 3° 刻度，后端 `fenjin120` 算分金归属
 *   3. **二十四山的干支/维分类** —— 前端决定朱红/主色/墨，后端 `MOUNTAINS[].kind`
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/compass_dial_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除，避免 tsc 报
 * "import path can only end with .ts when allowImportingTsExtensions is enabled"。
 */

import {
  FENJIN_COUNT,
  FENJIN_SPAN_DEGREE,
  TRIGRAM_HOUTIAN,
  buildTicks,
  dialDegreeAt,
  dialLayout,
  displayedDegree,
  mountainRole,
  normalizeSigned,
  pointerAngle,
  rotationToAlign,
  snapTo,
} from '../src/lib/compassDial.ts';
import {
  MOUNTAIN_COUNT,
  MOUNTAIN_NAMES,
  degreeToIndex,
  indexToDegree,
} from '../src/lib/ring24.ts';

// ==========================================================================
// 盘式数据
// ==========================================================================

const trigrams = TRIGRAM_HOUTIAN.map((t) => ({
  name: t.name,
  center_degree: t.centerDegree,
  yao: [...t.yao],
}));

const mountain_roles = MOUNTAIN_NAMES.map((name, i) => ({
  index: i,
  name,
  center_degree: indexToDegree(i),
  role: mountainRole(i),
}));

const ticks = buildTicks();

/** 0..359 每个整度所属山 —— 与 ring24 探针同源，用于核对"旋转后取山"是否仍正确 */
const degree_to_index = Array.from({ length: 360 }, (_, d) => ({
  degree: d,
  name: MOUNTAIN_NAMES[degreeToIndex(d)]!,
}));

// ==========================================================================
// 自检（与后端无关、纯前端几何自己就该成立）
// ==========================================================================

/** 1) 旋转往返：盘面角 → 屏幕角 → 反解盘面角，必须回到自身 */
const rotation_roundtrip_errors: string[] = [];
for (let d = 0; d < 360; d += 5) {
  for (const r of [-180, -37.5, 0, 12.5, 90, 181.5]) {
    const back = dialDegreeAt(displayedDegree(d, r), r);
    if (Math.abs(normalizeSigned(back - d)) > 1e-9) {
      rotation_roundtrip_errors.push(`d=${d} r=${r} → ${back}`);
    }
  }
}

/** 2) 一键对齐：对齐后该角度必须正好落在屏幕 0°（12 点） */
const align_errors: string[] = [];
for (let d = 0; d < 360; d += 1) {
  const shown = displayedDegree(d, rotationToAlign(d));
  if (Math.abs(normalizeSigned(shown)) > 1e-9) align_errors.push(`d=${d} → ${shown}`);
}

/** 3) 旋转不改变"哪座山"：同一盘面角在不同旋转下反解出同一座山 */
const rotation_select_errors: string[] = [];
for (let i = 0; i < MOUNTAIN_COUNT; i += 1) {
  const deg = indexToDegree(i);
  for (const r of [0, 7.5, 90, -123.4, 270]) {
    const screen = displayedDegree(deg, r);
    const backIndex = degreeToIndex(dialDegreeAt(screen, r));
    if (backIndex !== i) rotation_select_errors.push(`index=${i} r=${r} → ${backIndex}`);
  }
}

/** 4) 吸附：结果必须落在 step 的整数倍上，且偏移不超过半步 */
const snap_errors: string[] = [];
for (let d = -400; d <= 400; d += 0.5) {
  for (const step of [15, 1, 0.5]) {
    const s = snapTo(d, step);
    if (Math.abs(s % step) > 1e-9) snap_errors.push(`snapTo(${d},${step})=${s} 不在格点上`);
    if (Math.abs(s - d) > step / 2 + 1e-9) snap_errors.push(`snapTo(${d},${step})=${s} 偏移过大`);
  }
}

/** 5) 指针角：与 24 山归属一致（0° 在屏幕正上方、顺时针） */
const pointer_errors: string[] = [];
const pc = { x: 0, y: 0 };
for (let d = 0; d < 360; d += 1) {
  const rad = (d * Math.PI) / 180;
  const p = { x: Math.sin(rad) * 10, y: -Math.cos(rad) * 10 };
  const back = pointerAngle(pc, p);
  if (Math.abs(normalizeSigned(back - d)) > 1e-6) pointer_errors.push(`d=${d} → ${back}`);
}

/** 6) 归一化到 (−180, 180] */
const signed_errors: string[] = [];
for (let d = -720; d <= 720; d += 5) {
  const v = normalizeSigned(d);
  if (v <= -180.0000001 || v > 180.0000001) signed_errors.push(`normalizeSigned(${d})=${v}`);
}

/** 7) 刻度等级计数：45° 倍数 8 个主刻度、15° 倍数 16 个中刻度、其余 96 个细刻度 */
const tick_level_counts = { 0: 0, 1: 0, 2: 0 } as Record<number, number>;
for (const t of ticks) tick_level_counts[t.level] = (tick_level_counts[t.level] ?? 0) + 1;

/**
 * 8) 环半径的排布不变量。
 *
 * 注意这里**不能**要求"由外向内严格递减"：相邻两环是**紧贴共边**的
 * （二十四山环的内径 == 八卦环的外径），那是设计意图而不是缺陷 ——
 * 中间留白会让盘面看起来像几块分离的环，不像一个整盘。
 * 真正要守的是三条：
 *   a. 每一环自身有厚度（outer > inner）
 *   b. 由外向内不越界（前一环的内径 ≥ 后一环的外径）
 *   c. 天池落在最内环之内，且各环标签半径落在自己的环带里
 */
const L = dialLayout(300);
const radius_order_errors: string[] = [];

const rings: [string, number, number][] = [
  ['二十四山环', L.mountainOuter, L.mountainInner],
  ['八卦环', L.trigramOuter, L.trigramInner],
  ['分金刻度环', L.tickOuter, L.tickInner],
];

for (const [name, outer, inner] of rings) {
  if (!(outer > inner)) radius_order_errors.push(`${name} 无厚度：outer=${outer} inner=${inner}`);
}
if (!(L.rim > L.mountainOuter)) {
  radius_order_errors.push(`外框(${L.rim}) 未包住最外环(${L.mountainOuter})`);
}
for (let i = 1; i < rings.length; i += 1) {
  const [prevName, , prevInner] = rings[i - 1]!;
  const [curName, curOuter] = rings[i]!;
  if (!(prevInner >= curOuter)) {
    radius_order_errors.push(`${prevName}的内径(${prevInner}) 小于 ${curName}的外径(${curOuter})，两环会重叠`);
  }
}
if (!(L.tickInner > L.pool)) {
  radius_order_errors.push(`天池(${L.pool}) 越出刻度环内径(${L.tickInner})`);
}
if (L.labelRadius <= L.mountainInner || L.labelRadius >= L.mountainOuter) {
  radius_order_errors.push(`山名半径 ${L.labelRadius} 不在二十四山环带内`);
}
if (L.trigramRadius <= L.trigramInner || L.trigramRadius >= L.trigramOuter) {
  radius_order_errors.push(`卦符半径 ${L.trigramRadius} 不在八卦环带内`);
}

const report = {
  mountain_count: MOUNTAIN_COUNT,
  fenjin: { span_degree: FENJIN_SPAN_DEGREE, count: FENJIN_COUNT },
  trigrams,
  mountain_roles,
  ticks,
  degree_to_index,
  checks: {
    rotation_roundtrip_errors,
    align_errors,
    rotation_select_errors,
    snap_errors,
    pointer_errors,
    signed_errors,
    tick_level_counts,
    tick_total: ticks.length,
    radius_order_errors,
  },
};

process.stdout.write(JSON.stringify(report));
