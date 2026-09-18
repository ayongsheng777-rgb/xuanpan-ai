/**
 * 罗盘盘面的几何与盘式规则 —— **纯函数，无 React / RN 依赖**，可直接单测。
 *
 * 与 `ring24.ts` 的分工：
 *   - `ring24`   只管「角度 ↔ 山」的换算与扇形路径（交互命中的基础）
 *   - `compassDial` 管「真实罗盘该长什么样」：层次划分、刻度体系、盘面角色配色
 *
 * 角度约定与工程全体一致：0° = 正北 = 子，顺时针递增，0° 指向屏幕上方。
 *
 * ⚠️ 盘式相关标注（AGENTS.md §2.3 约定）：
 *   - `[已确认]` 二十四山顺序与山心角、后天八卦方位、一百二十分金的 3° 分格
 *   - `[待验证]` 红/蓝/墨的**盘面角色配色**：真实罗盘的朱/墨分色各版不同
 *     （有只红四正的，有红四正四维的，有四阳卦皆红的），
 *     本文件采用「四正朱红 · 四维主色 · 余墨」一制，仅供视觉识别，不参与任何计算。
 */

// ⚠️ 这里**必须**写显式 `.ts` 后缀：本文件被 `scripts/compass_dial_probe.ts`
// 以 `node --experimental-strip-types` 直接执行，而 Node 的 ESM 载入器要求
// 相对导入含扩展名（否则 ERR_MODULE_NOT_FOUND）。tsconfig 已为此开启
// `allowImportingTsExtensions`。全仓仅此一处这样写，其余源码保持免后缀风格。
import {
  MOUNTAIN_COUNT,
  MOUNTAIN_NAMES,
  SPAN_DEGREE,
  normalizeDeg,
  type Point,
} from './ring24.ts';

// ==========================================================================
// 盘式层次
// ==========================================================================

/** 一百二十分金：每格 3°，共 120 格（与 `fortune_core.fenjin120` 同制） */
export const FENJIN_SPAN_DEGREE = 3;
export const FENJIN_COUNT = 360 / FENJIN_SPAN_DEGREE; // 120

/** 后天八卦：每卦辖 45° */
export const TRIGRAM_SPAN_DEGREE = 45;

/**
 * 后天八卦方位（洛书九宫）：坎北、艮东北、震东、巽东南、离南、坤西南、兑西、乾西北。
 *
 * `yao` 为自下而上的三爻（1=阳 0=阴），用于**自绘卦符**而不是打 Unicode 字符
 * （☰☱… 在部分 Android 字体上缺字会渲染成豆腐块，而三根短线永远画得出来）。
 */
export const TRIGRAM_HOUTIAN = [
  { name: '坎', centerDegree: 0, yao: [0, 1, 0] },
  { name: '艮', centerDegree: 45, yao: [0, 0, 1] },
  { name: '震', centerDegree: 90, yao: [1, 0, 0] },
  { name: '巽', centerDegree: 135, yao: [0, 1, 1] },
  { name: '离', centerDegree: 180, yao: [1, 0, 1] },
  { name: '坤', centerDegree: 225, yao: [0, 0, 0] },
  { name: '兑', centerDegree: 270, yao: [1, 1, 0] },
  { name: '乾', centerDegree: 315, yao: [1, 1, 1] },
] as const;

/** 各圈在半径上的占比（相对整体半径）。由外向内。 */
export const DIAL_RATIOS = {
  /** 外框装饰环 */
  rim: 1.0,
  /** 二十四山环：外径 / 内径 */
  mountainOuter: 0.97,
  mountainInner: 0.78,
  /** 八卦环：外径 / 内径 */
  trigramOuter: 0.78,
  trigramInner: 0.62,
  /** 分金刻度环：外径 / 内径 */
  tickOuter: 0.62,
  tickInner: 0.45,
  /** 天池（中心圆） */
  pool: 0.28,
} as const;

export interface DialLayout {
  /** 各环半径（单位与入参 size 一致） */
  rim: number;
  mountainOuter: number;
  mountainInner: number;
  trigramOuter: number;
  trigramInner: number;
  tickOuter: number;
  tickInner: number;
  pool: number;
  /** 山名所在的半径（环带中线） */
  labelRadius: number;
  /** 卦符所在半径 */
  trigramRadius: number;
  /** 圆心 */
  center: Point;
}

/** 由外径算出各环半径。传「直径」，返回以中心为原点的半径表。 */
export function dialLayout(size: number): DialLayout {
  const r = size / 2;
  const at = (ratio: number): number => r * ratio;
  return {
    rim: at(DIAL_RATIOS.rim),
    mountainOuter: at(DIAL_RATIOS.mountainOuter),
    mountainInner: at(DIAL_RATIOS.mountainInner),
    trigramOuter: at(DIAL_RATIOS.trigramOuter),
    trigramInner: at(DIAL_RATIOS.trigramInner),
    tickOuter: at(DIAL_RATIOS.tickOuter),
    tickInner: at(DIAL_RATIOS.tickInner),
    pool: at(DIAL_RATIOS.pool),
    labelRadius: (at(DIAL_RATIOS.mountainOuter) + at(DIAL_RATIOS.mountainInner)) / 2,
    trigramRadius: (at(DIAL_RATIOS.trigramOuter) + at(DIAL_RATIOS.trigramInner)) / 2,
    center: { x: r, y: r },
  };
}

// ==========================================================================
// 盘面角色与配色 —— [待验证] 属盘式流派，仅视觉
// ==========================================================================

/** 二十四山的盘面角色 */
export type MountainRole = 'cardinal' | 'corner' | 'stem' | 'branch';

const CARDINAL = '子午卯酉'; // 四正
const CORNER = '乾坤艮巽'; // 四维
const STEM = '甲乙丙丁庚辛壬癸'; // 八天干（戊己不入二十四山）

/**
 * 判定某山的盘面角色。四正 → 朱红；四维 → 主色；八天干 → 墨；其余地支 → 墨。
 *
 * >>> mountainRole(0)   // 子
 * 'cardinal'
 * >>> mountainRole(4)   // 艮
 * 'corner'
 * >>> mountainRole(1)   // 癸
 * 'stem'
 * >>> mountainRole(2)   // 丑
 * 'branch'
 */
export function mountainRole(index: number): MountainRole {
  const name = MOUNTAIN_NAMES[((index % MOUNTAIN_COUNT) + MOUNTAIN_COUNT) % MOUNTAIN_COUNT]!;
  if (CARDINAL.includes(name)) return 'cardinal';
  if (CORNER.includes(name)) return 'corner';
  if (STEM.includes(name)) return 'stem';
  return 'branch';
}

/** 角色 → Token key（由组件映射到实际色值，本文件不引入主题） */
export const ROLE_COLOR_KEY: Record<MountainRole, 'cinnabar' | 'primary' | 'text'> = {
  cardinal: 'cinnabar',
  corner: 'primary',
  stem: 'text',
  branch: 'text',
};

// ==========================================================================
// 刻度体系
// ==========================================================================

/** 刻度等级：0=主（八卦位 45°）/ 1=中（山界 15°）/ 2=细（分金 3°） */
export type TickLevel = 0 | 1 | 2;

export interface Tick {
  degree: number;
  level: TickLevel;
}

/**
 * 生成一整圈刻度。
 *
 * 三级叠加：每 3° 细刻度（一百二十分金格）、每 15° 中刻度（山界）、
 * 每 45° 主刻度（八卦位）。同角度只保留最高等级，避免叠画。
 */
export function buildTicks(): Tick[] {
  const map = new Map<number, TickLevel>();
  for (let d = 0; d < 360; d += FENJIN_SPAN_DEGREE) map.set(d, 2);
  for (let d = 0; d < 360; d += SPAN_DEGREE) map.set(d, 1);
  for (let d = 0; d < 360; d += TRIGRAM_SPAN_DEGREE) map.set(d, 0);
  return [...map.entries()]
    .map(([degree, level]) => ({ degree, level }))
    .sort((a, b) => a.degree - b.degree);
}

/** 刻度等级 → 伸入环内的长度占比（1 = 占满整个刻度环） */
export const TICK_LENGTH_RATIO: Record<TickLevel, number> = {
  0: 1,
  1: 0.68,
  2: 0.34,
};

// ==========================================================================
// 旋转与吸附
// ==========================================================================

/** 角度归一化到 (−180, 180]，用于显示「盘面转了多少度」这种有方向的量 */
export function normalizeSigned(deg: number): number {
  const d = normalizeDeg(deg);
  return d > 180 ? d - 360 : d;
}

/** 吸附到最近的 step 度（step ≤ 0 时原样返回） */
export function snapTo(deg: number, step: number): number {
  if (step <= 0) return deg;
  return Math.round(deg / step) * step;
}

/**
 * 指针位置 → 相对屏幕正上方的角度（0..360，顺时针）。
 *
 * 与 `ring24.pointToIndex` 的区别：那个要判「是否落在环带内」，
 * 这个**不判**——拖动旋转时手指可能跑到环外，但旋转仍应继续跟手。
 */
export function pointerAngle(center: Point, point: Point): number {
  const dx = point.x - center.x;
  const dy = point.y - center.y;
  if (dx === 0 && dy === 0) return 0;
  return normalizeDeg((Math.atan2(dx, -dy) * 180) / Math.PI);
}

/**
 * 计算「让某个盘面角度对准屏幕上方」所需的旋转量。
 *
 * 用于导入实测数据后**一键对齐**：把实测方向转到 12 点方向，
 * 用户一眼就能看出识别结果与手里罗盘是否一致（不一致再手动微调）。
 */
export function rotationToAlign(degree: number): number {
  return normalizeSigned(-degree);
}

/** 微调步长（度）。用户「不能完全对齐」时按这些档位逐步逼近。 */
export const NUDGE_STEPS = [15, 1, 0.5] as const;
export type NudgeStep = (typeof NUDGE_STEPS)[number];

/**
 * 在给定旋转量下，某盘面角度出现在屏幕上的实际角度。
 *
 * `rotation` 为盘面顺时针旋转量；盘面角度 θ 的显示位置 = θ + rotation。
 */
export function displayedDegree(mountainDegree: number, rotation: number): number {
  return normalizeDeg(mountainDegree + rotation);
}

/**
 * 反解：屏幕上某个方向对应的**盘面角度**（用于点击选山）。
 */
export function dialDegreeAt(screenDegree: number, rotation: number): number {
  return normalizeDeg(screenDegree - rotation);
}

/**
 * 「当前方位」= 屏幕正上方（12 点方向）那一格对应的盘面角。
 *
 * 🔴 凡是要把 `rotation` 显示成**方位读数**的地方，必须走这个函数。
 *
 * 为什么单独抽一个函数，而不是各处自己写一遍：
 * 这个换算很容易写成 `normalizeDeg(rotation)`（**少一个负号**），
 * 而错了以后界面完全正常 —— 只是拖盘到东边读数显示西边，
 * 且在 0°/180° 两个点上"看起来是对的"，肉眼抽查极易放过。
 * 本项目已实测发生过：`index.tsx` 用的是 `+rotation`（反的），
 * 而 `adjust.tsx` / `CompassAdjuster` 用的是 `-rotation`（对的）。
 *
 * 几何依据：盘面角 θ 显示在屏幕角 `θ + rotation`（`displayedDegree`）。
 * 令其等于 0 得 θ = −rotation。等价于 `dialDegreeAt(0, rotation)`。
 *
 * ⚠️ `CompassAdjuster` 里那个标着「盘面旋转」的读数**不该**用本函数 ——
 * 它显示的就是旋转量本身，语义不同（那是"盘转了多少"，不是"朝哪边"）。
 */
export function azimuthAtTop(rotation: number): number {
  return dialDegreeAt(0, rotation);
}
