/**
 * ring24 几何探针 —— 把选择器的几何结果导出成 JSON，供 Python 侧与
 * `fortune_core.mountain24` 做**跨语言一致性校验**（见
 * `tests/mobile/test_ring24_parity.py`）。
 *
 * 为什么需要这样一道校验：
 * `ring24.ts` 内嵌了山名与顺序（环必须能同步渲染，不能等网络），
 * 而后端也有一份二十四山标准表 —— **同一个规则存在两处**。
 * 一旦其中一处被改动而另一处没跟，环形选择器会静默错位，
 * 后果是"用户点了午，算出的是未"。这类错误不会报错，只会给出错误结论。
 *
 * `ring24.ts` 里的 `validateMountainOrder` 只能在运行时、等到接口返回才炸；
 * 本探针让它在 `pytest` 阶段就炸掉。两道防线都要有。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/ring24_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除，避免 tsc 报
 * "import path can only end with .ts when allowImportingTsExtensions is enabled"。
 */

import {
  HALF_SPAN,
  MOUNTAIN_COUNT,
  MOUNTAIN_NAMES,
  SPAN_DEGREE,
  degreeToIndex,
  indexToDegree,
  isOppositeIndex,
  nameOfIndex,
  oppositeIndex,
  pointOnCircle,
  pointToIndex,
  sectorPathOfIndex,
} from '../src/lib/ring24.ts';

/** 每座山的静态属性 */
const mountains = MOUNTAIN_NAMES.map((name, i) => ({
  index: i,
  name,
  center_degree: indexToDegree(i),
  opposite_index: oppositeIndex(i),
  opposite_name: nameOfIndex(oppositeIndex(i)),
}));

/**
 * 对 0..359 的每个整度求所属山。
 *
 * 用整度而不是浮点采样：整度已能覆盖每个山内 15 个取值，
 * 且结果是整数便于 Python 侧逐项比对（浮点会引入"到底该归哪边"的争议）。
 */
const degree_to_index = Array.from({ length: 360 }, (_, d) => ({
  degree: d,
  index: degreeToIndex(d),
  name: nameOfIndex(degreeToIndex(d)),
}));

/** 环带命中判定的往返一致性：由索引 → 角度 → 再算回索引，必须回到自身 */
const roundtrip_errors: string[] = [];
for (let i = 0; i < MOUNTAIN_COUNT; i += 1) {
  const deg = indexToDegree(i);
  const back = degreeToIndex(deg);
  if (back !== i) roundtrip_errors.push(`index ${i} → ${deg}° → ${back}`);
}

/**
 * 与屏幕坐标的往返：取每座山山心角方向、环带中线上的一点，
 * 反算回索引必须一致。
 *
 * 半径取 1.0 与 2.0 构成的环带，中心取 (0,0) —— 与真实布局无关，
 * 只验证几何本身；真实布局只需线性缩放，不改变角度。
 */
const center = { x: 0, y: 0 };
const coord_errors: string[] = [];
for (let i = 0; i < MOUNTAIN_COUNT; i += 1) {
  const deg = indexToDegree(i);
  const p = pointOnCircle(center, 1.5, deg);
  const hit = pointToIndex(center, 1.0, 2.0, p);
  if (hit !== i) coord_errors.push(`index ${i} @ ${deg}° → (${p.x},${p.y}) → ${hit}`);
}

/**
 * 对宫关系必须是对称的：a 的对宫是 b ⟺ b 的对宫是 a。
 * 非对称会造出"坐午向子"但"坐子向午"两条不一致的路径。
 */
const opposite_errors: string[] = [];
for (let i = 0; i < MOUNTAIN_COUNT; i += 1) {
  const j = oppositeIndex(i);
  if (!isOppositeIndex(j, i)) opposite_errors.push(`opposite not symmetric: ${i} ↔ ${j}`);
  if (j === i) opposite_errors.push(`opposite equals self: ${i}`);
}

/** 扇区路径：24 格各自非空，且不得有两条路径完全相同（说明有格子重叠/丢失） */
const sector_paths = MOUNTAIN_NAMES.map((_, i) =>
  sectorPathOfIndex(center, 1.0, 2.0, i, 0.8),
);
const sector_unique = new Set(sector_paths).size;

const report = {
  mountain_count: MOUNTAIN_COUNT,
  span_degree: SPAN_DEGREE,
  half_span: HALF_SPAN,
  mountains,
  degree_to_index,
  checks: {
    roundtrip_errors,
    coord_errors,
    opposite_errors,
    sector_paths_unique: sector_unique,
    sector_paths_total: sector_paths.length,
    any_sector_empty: sector_paths.some((p) => p.length === 0),
  },
};

process.stdout.write(JSON.stringify(report));
