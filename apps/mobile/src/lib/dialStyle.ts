/**
 * 盘式定义 —— 「盘面由哪些环带构成、每环占多少半径」。
 *
 * 单独成模块的理由：`compassDial.ts` 管的是**几何与盘式规则**（角度、刻度体系、
 * 角色配色），而「这一个盘有几层、每层多宽」是**盘式**问题。两者会各自演化 ——
 * 三元盘与三合盘的层数差别很大，但共用同一套角度换算与配色规则。
 *
 * 🔴 **本文件只放"画得出来"的层，不放"编得出来"的层。**
 * 真实罗盘还有七十二龙、六十四卦、二十八宿等环带，但仓库里**没有这些层的数据表**
 * （`data/` 只有康熙笔画与择日事件两张表）。宁可不画，也不为了"看着像真罗盘"
 * 而凭空编造术数内容 —— 那是 RULE-008（不得为"看起来合理"而修正/伪造数据）
 * 在视觉层的同一个错误。要加这些层，先补数据表。
 *
 * `[已确认]` 二十四山顺序与山心角、后天八卦方位、先天八卦方位、分金 3° 分格。
 * `[待验证]` 各盘式的**层数与层宽比例**：真实罗盘各版尺寸不一，这里的比例
 * 是按「层数越多、每层越窄」的常见形制拟定的视觉比例，只影响观感，
 * 不参与任何术数计算。
 */

// ⚠️ 显式 `.ts` 后缀：本文件被 scripts/dial_style_probe.ts 以
// `node --experimental-strip-types` 直接执行，Node 的 ESM 载入器要求相对导入含扩展名。
import { DIAL_RATIOS } from './compassDial.ts';

// ==========================================================================
// 层的种类
// ==========================================================================

export type DialLayerId =
  /** 一百二十分金：3° 一格，共 120 格 */
  | 'fenjin'
  /** 二十四山：15° 一山，有真实数据 */
  | 'mountain24'
  /** 后天八卦（洛书九宫）：坎北 艮东北 震东 巽东南 离南 坤西南 兑西 乾西北 */
  | 'houtian'
  /** 先天八卦（伏羲八卦）：乾南 坤北 离东 坎西 震东北 巽西南 艮西北 兑东南 */
  | 'xiantian'
  /** 内圈细分刻度：只画线不写字（无对应术数数据表，故不着字） */
  | 'dragon'
  /** 天池：中心圆，承载磁针 */
  | 'pool';

export interface DialLayer {
  id: DialLayerId;
  /** 外径（相对整体半径 0..1） */
  outer: number;
  /** 内径（相对整体半径 0..1） */
  inner: number;
}

export type DialStyleId = 'simple' | 'sanhe' | 'zonghe';

export interface DialStyle {
  id: DialStyleId;
  /** 盘式名（真实罗盘行业的叫法） */
  name: string;
  /** 罗盘行业口径的「层数」。含本实现未渲染的细分层，故 ≥ 可渲染层数 */
  statedLayers: number;
  /** 一句话说明，用于选择器副标题 */
  blurb: string;
  /** 由外向内排列 */
  layers: readonly DialLayer[];
}

// ==========================================================================
// 先天八卦方位
// ==========================================================================

/**
 * 先天八卦（伏羲八卦）方位与卦符。
 *
 * 与后天八卦（洛书九宫）的关系：**先天为体、后天为用**，两者方位不同 ——
 * 先天卦相对后天卦整体错位。常见的错法是"直接把后天方位套给先天"，
 * 那样画出来的盘面是错的、而且看起来很正常（RULE-008 同类风险）。
 *
 * 方位（角度制与全仓一致：0° = 正北 = 子，顺时针递增）：
 *   乾南 180 · 兑东南 135 · 离东 90 · 震东北 45
 *   巽西南 225 · 坎西 270 · 艮西北 315 · 坤北 0
 */
export const TRIGRAM_XIANTIAN = [
  { name: '坤', centerDegree: 0, yao: [0, 0, 0] },
  { name: '震', centerDegree: 45, yao: [1, 0, 0] },
  { name: '离', centerDegree: 90, yao: [1, 0, 1] },
  { name: '兑', centerDegree: 135, yao: [1, 1, 0] },
  { name: '乾', centerDegree: 180, yao: [1, 1, 1] },
  { name: '巽', centerDegree: 225, yao: [0, 1, 1] },
  { name: '坎', centerDegree: 270, yao: [0, 1, 0] },
  { name: '艮', centerDegree: 315, yao: [0, 0, 1] },
] as const;

// ==========================================================================
// 盘式表
// ==========================================================================

/**
 * 简化盘 —— 既有盘面的几何，**必须与 `DIAL_RATIOS` 逐项相等**。
 *
 * 为什么不让它引用 DIAL_RATIOS 就算了：这里的层是「按 id 取用」的，
 * 而 DIAL_RATIOS 的字段名（mountainOuter…）是给旧渲染路径用的两套命名。
 * 两者一旦漂移，同一个 size 会算出两个不同的盘 —— 故有
 * `tests/mobile/test_dial_style.py` 断言它们逐项相等。
 */
const SIMPLE: DialStyle = {
  id: 'simple',
  name: '简化盘',
  statedLayers: 8,
  blurb: '只保留识向所需的四层，格子宽、看得清',
  layers: [
    { id: 'mountain24', outer: DIAL_RATIOS.mountainOuter, inner: DIAL_RATIOS.mountainInner },
    { id: 'houtian', outer: DIAL_RATIOS.trigramOuter, inner: DIAL_RATIOS.trigramInner },
    { id: 'fenjin', outer: DIAL_RATIOS.tickOuter, inner: DIAL_RATIOS.tickInner },
    { id: 'pool', outer: DIAL_RATIOS.pool, inner: 0 },
  ],
};

const SANHE: DialStyle = {
  id: 'sanhe',
  name: '三合盘',
  statedLayers: 12,
  blurb: '十二层，含先后天八卦与内圈细分刻度',
  layers: [
    { id: 'fenjin', outer: 0.995, inner: 0.945 },
    { id: 'mountain24', outer: 0.945, inner: 0.795 },
    { id: 'houtian', outer: 0.795, inner: 0.685 },
    { id: 'dragon', outer: 0.685, inner: 0.605 },
    { id: 'xiantian', outer: 0.605, inner: 0.5 },
    { id: 'pool', outer: 0.26, inner: 0 },
  ],
};

const ZONGHE: DialStyle = {
  id: 'zonghe',
  name: '三元三合综合盘',
  statedLayers: 18,
  blurb: '十八层，层最密，接近实物综合盘的观感',
  layers: [
    { id: 'fenjin', outer: 0.998, inner: 0.952 },
    { id: 'mountain24', outer: 0.952, inner: 0.806 },
    { id: 'houtian', outer: 0.806, inner: 0.708 },
    { id: 'dragon', outer: 0.708, inner: 0.638 },
    { id: 'xiantian', outer: 0.638, inner: 0.538 },
    { id: 'pool', outer: DIAL_RATIOS.pool, inner: 0 },
  ],
};

export const DIAL_STYLES: Record<DialStyleId, DialStyle> = {
  simple: SIMPLE,
  sanhe: SANHE,
  zonghe: ZONGHE,
};

/** 选择器展示顺序：由简到繁 */
export const DIAL_STYLE_ORDER: readonly DialStyleId[] = ['simple', 'sanhe', 'zonghe'];

export const DEFAULT_DIAL_STYLE: DialStyleId = 'zonghe';

/** 合法盘式判定（容忍脏数据：UI 会从存档里读到旧值） */
export function isDialStyleId(v: unknown): v is DialStyleId {
  return typeof v === 'string' && v in DIAL_STYLES;
}

/** 归一盘式：非法值回落到默认盘，**不抛异常**（存档里的旧盘式名不应让页面崩） */
export function coerceDialStyle(v: unknown): DialStyleId {
  return isDialStyleId(v) ? v : DEFAULT_DIAL_STYLE;
}

export function layersOf(id: DialStyleId): readonly DialLayer[] {
  return DIAL_STYLES[id].layers;
}

export function styleOf(id: DialStyleId): DialStyle {
  return DIAL_STYLES[id];
}

/** 取某一层；该盘式不含此层时返回 null（调用方据此决定要不要画） */
export function layerOf(id: DialStyleId, layer: DialLayerId): DialLayer | null {
  return DIAL_STYLES[id].layers.find((l) => l.id === layer) ?? null;
}

/** 该盘式是否含某一层 */
export function hasLayer(id: DialStyleId, layer: DialLayerId): boolean {
  return layerOf(id, layer) !== null;
}

export interface LayerRadius {
  outer: number;
  inner: number;
  /** 环带中线半径 —— 写字/画卦符用 */
  mid: number;
}

/**
 * 层 → 实际半径（像素）。
 *
 * `size` 是**整体外径**，半径 = size / 2，与 `compassDial.dialLayout` 同口径。
 */
export function layerRadius(
  id: DialStyleId,
  layer: DialLayerId,
  size: number,
): LayerRadius | null {
  const l = layerOf(id, layer);
  if (!l) return null;
  const r = size / 2;
  return { outer: l.outer * r, inner: l.inner * r, mid: ((l.outer + l.inner) / 2) * r };
}

/**
 * 盘式 → 全部可渲染层（带半径），由外向内。
 *
 * 天池恒为最后一层（最后画 = 盖在最上面），故本函数把 pool 排到末尾 ——
 * 盘式表里它本就在末尾，这里再显式保证一次。
 */
export function renderLayers(
  id: DialStyleId,
  size: number,
): readonly { layer: DialLayer; radius: LayerRadius }[] {
  const r = size / 2;
  const out = DIAL_STYLES[id].layers.map((layer) => ({
    layer,
    radius: { outer: layer.outer * r, inner: layer.inner * r, mid: ((layer.outer + layer.inner) / 2) * r },
  }));
  return out.sort((a, b) => (a.layer.id === 'pool' ? 1 : 0) - (b.layer.id === 'pool' ? 1 : 0));
}

// ==========================================================================
// 盘式切换（首页/调节页的盘式选择器要用）
// ==========================================================================

/** 盘式在列表里的位置，找不到返回 0 —— 选择器要能渲染任意脏数据 */
export function styleIndex(id: DialStyleId): number {
  const i = DIAL_STYLE_ORDER.indexOf(id);
  return i < 0 ? 0 : i;
}

/** 按步进切换盘式（可循环）。dir > 0 向下一个 */
export function stepStyle(id: DialStyleId, dir: number): DialStyleId {
  const n = DIAL_STYLE_ORDER.length;
  const i = ((styleIndex(id) + dir) % n + n) % n;
  return DIAL_STYLE_ORDER[i]!;
}
