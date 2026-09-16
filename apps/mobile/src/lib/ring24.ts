/**
 * 二十四山环形选择器的几何内核 —— **纯函数，无 React / RN 依赖**，可直接单测。
 *
 * 角度约定（与 `fortune_core.mountain24`、`xuanpan_vision` **完全一致**）：
 *   - 0° = 正北 = 子，**顺时针**递增
 *   - 每山 15°，山心角 = index × 15°
 *   - 屏幕坐标：x 向右、y 向下 → 0° 指向**屏幕正上方**
 *
 * 为什么把几何单独抽出来：环形选择器是"用户手动修正坐向"的唯一入口
 * （基线规范 §4.1 明确禁止让用户输入角度数值），点错一格就是坐向错 15°，
 * 后续所有结论都跟着错。这种地方必须能被测试钉死，而不是靠肉眼看界面。
 */

/** 二十四山顺序（自 子 起顺时针）。这是固定盘式布局。 */
export const MOUNTAIN_NAMES = [
  '子', '癸', '丑', '艮', '寅', '甲', '卯', '乙',
  '辰', '巽', '巳', '丙', '午', '丁', '未', '坤',
  '申', '庚', '酉', '辛', '戌', '乾', '亥', '壬',
] as const;

export type MountainName = (typeof MOUNTAIN_NAMES)[number];

/** 每山张角 */
export const SPAN_DEGREE = 15;
/** 半山张角（用于角度 ↔ 山的边界判定） */
export const HALF_SPAN = SPAN_DEGREE / 2;

export const MOUNTAIN_COUNT = MOUNTAIN_NAMES.length;

/** 把任意角度归一到 [0, 360) */
export function normalizeDeg(deg: number): number {
  const r = deg % 360;
  return r < 0 ? r + 360 : r;
}

/** 索引 → 山心角 */
export function indexToDegree(index: number): number {
  return normalizeDeg(index * SPAN_DEGREE);
}

/** 角度 → 索引（四舍五入到最近的山心；边界取顺时针一侧） */
export function degreeToIndex(deg: number): number {
  return Math.floor((normalizeDeg(deg) + HALF_SPAN) / SPAN_DEGREE) % MOUNTAIN_COUNT;
}

/** 索引 → 山名 */
export function nameOfIndex(index: number): MountainName {
  return MOUNTAIN_NAMES[((index % MOUNTAIN_COUNT) + MOUNTAIN_COUNT) % MOUNTAIN_COUNT]!;
}

/** 山名 → 索引；非法名返回 -1（**不抛异常**：UI 需要能容忍脏数据） */
export function indexOfName(name: string): number {
  const i = MOUNTAIN_NAMES.indexOf(name as MountainName);
  return i;
}

/** 对宫索引（±180° = 12 位） */
export function oppositeIndex(index: number): number {
  return (index + MOUNTAIN_COUNT / 2) % MOUNTAIN_COUNT;
}

/** 两索引是否互为对宫 */
export function isOppositeIndex(a: number, b: number): boolean {
  return oppositeIndex(a) === ((b % MOUNTAIN_COUNT) + MOUNTAIN_COUNT) % MOUNTAIN_COUNT;
}

/** 两索引之间的最小角距（单位：格，0..12） */
export function indexDistance(a: number, b: number): number {
  const d = Math.abs(a - b) % MOUNTAIN_COUNT;
  return Math.min(d, MOUNTAIN_COUNT - d);
}

// ==========================================================================
// 坐标
// ==========================================================================

export interface Point {
  x: number;
  y: number;
}

/**
 * 极坐标 → 屏幕坐标。
 *
 * 注意 `sin/cos` 的用法：因为 0° 指向屏幕**上方**且顺时针，
 *   x = cx + r·sin(θ)，y = cy − r·cos(θ)
 * 若误写成常规数学系（x = cx + r·cosθ, y = cy − r·sinθ），
 * 整个环会旋转 90°，且"子"会跑到屏幕右侧。
 */
export function pointOnCircle(center: Point, radius: number, deg: number): Point {
  const t = (normalizeDeg(deg) * Math.PI) / 180;
  return {
    x: center.x + radius * Math.sin(t),
    y: center.y - radius * Math.cos(t),
  };
}

/**
 * 屏幕坐标 → 二十四山索引。不在环带内返回 `null`。
 *
 * 返回 null 而不是"最近的格子"，是为了让"点到了环外空白"成为
 * 明确的无操作，而不是悄悄选中一个用户没想选的格子。
 */
export function pointToIndex(
  center: Point,
  innerRadius: number,
  outerRadius: number,
  point: Point,
): number | null {
  const dx = point.x - center.x;
  const dy = point.y - center.y;
  const dist = Math.hypot(dx, dy);
  if (dist < innerRadius || dist > outerRadius) return null;
  // atan2(dx, -dy)：以"屏幕上方"为 0、顺时针为正
  const deg = normalizeDeg((Math.atan2(dx, -dy) * 180) / Math.PI);
  return degreeToIndex(deg);
}

// ==========================================================================
// SVG 路径
// ==========================================================================

/**
 * 生成一段圆环扇区（annulus sector）的 SVG path。
 *
 * @param startDeg 起始角（顺时针方向）
 * @param endDeg   结束角（必须 > startDeg，允许 > 360）
 * @param gapDeg   相邻格之间的缝隙（视觉分隔用；0 = 无缝贴合）
 */
export function sectorPath(
  center: Point,
  innerRadius: number,
  outerRadius: number,
  startDeg: number,
  endDeg: number,
  gapDeg = 0,
): string {
  const s = startDeg + gapDeg / 2;
  const e = endDeg - gapDeg / 2;
  if (e <= s) return '';

  const p1 = pointOnCircle(center, outerRadius, s);
  const p2 = pointOnCircle(center, outerRadius, e);
  const p3 = pointOnCircle(center, innerRadius, e);
  const p4 = pointOnCircle(center, innerRadius, s);

  const largeArc = e - s > 180 ? 1 : 0;
  // 外弧顺时针 → sweep=1；内弧反向 → sweep=0
  return [
    `M ${p1.x} ${p1.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${p2.x} ${p2.y}`,
    `L ${p3.x} ${p3.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${p4.x} ${p4.y}`,
    'Z',
  ].join(' ');
}

/** 某一格在其所在环带上的路径 */
export function sectorPathOfIndex(
  center: Point,
  innerRadius: number,
  outerRadius: number,
  index: number,
  gapDeg = 0,
): string {
  const start = index * SPAN_DEGREE;
  return sectorPath(center, innerRadius, outerRadius, start, start + SPAN_DEGREE, gapDeg);
}

// ==========================================================================
// 坐向联动（核心交互规则）
// ==========================================================================

export interface OrientationSelection {
  /** 坐山索引；null = 未选 */
  sitting: number | null;
  /**
   * 向山索引。**永远由坐山推导**（±180°），不接受独立设置。
   *
   * 为什么不做成"两个独立可选"：坐向是一条直线，向山必然是坐山的对宫。
   * 允许独立选择会造出"坐午向巳"这种几何上不成立的状态，
   * 而计算层会直接抛错 —— 与其让用户走到报错，不如在交互层就约束住。
   */
  facing: number | null;
}

/** 选坐山 → 自动带出向山 */
export function selectSitting(sitting: number | null): OrientationSelection {
  if (sitting === null) return { sitting: null, facing: null };
  return { sitting, facing: oppositeIndex(sitting) };
}

/** 选向山 → 反向带出坐山（用户也可能先想到"朝哪边"） */
export function selectFacing(facing: number | null): OrientationSelection {
  if (facing === null) return { sitting: null, facing: null };
  return { facing, sitting: oppositeIndex(facing) };
}

/**
 * 由"实测角度"初始化选择。
 *
 * 用于识别结果回填：识别给出的是角度（如 177.03°），
 * 选择器需要把它落到格子上，同时**保留原角度**用于分金精算 ——
 * 若用户没有改动选择，提交时应回传原角度而不是山心角，否则
 * 3° 级的分金精度就白测了（对应 services/vision 保留实测角的设计）。
 */
export function selectionFromDegree(deg: number): OrientationSelection {
  return selectSitting(degreeToIndex(deg));
}

// ==========================================================================
// 与后端山表的一致性校验
// ==========================================================================

export interface MountainFromApi {
  index: number;
  name: string;
  center_degree: number;
}

/**
 * 校验后端 `/meta/mountains` 与本文件的顺序是否一致。
 *
 * 为什么要校验：本文件嵌入了山名与顺序（环要能**同步渲染**，不能等网络），
 * 而属性（五行/卦/三元龙）一律走接口。于是"顺序"存在两处 ——
 * 一旦后端顺序变了而这里没跟，整个环会静默错位。
 * 与其靠约定，不如在数据到达时**立刻炸掉**：错位是灾难性的，不值得容错。
 *
 * @returns 不一致的说明文本；一致则返回 null
 */
export function validateMountainOrder(apiMountains: readonly MountainFromApi[]): string | null {
  if (apiMountains.length !== MOUNTAIN_COUNT) {
    return `后端返回 ${apiMountains.length} 座山，应为 ${MOUNTAIN_COUNT} 座`;
  }
  const sorted = [...apiMountains].sort((a, b) => a.index - b.index);
  for (let i = 0; i < MOUNTAIN_COUNT; i += 1) {
    const m = sorted[i]!;
    if (m.name !== MOUNTAIN_NAMES[i]) {
      return `第 ${i} 位应为「${MOUNTAIN_NAMES[i]}」，后端给的是「${m.name}」`;
    }
    if (Math.abs(normalizeDeg(m.center_degree) - indexToDegree(i)) > 1e-6) {
      return `「${m.name}」山心角应为 ${indexToDegree(i)}°，后端给的是 ${m.center_degree}°`;
    }
  }
  return null;
}
