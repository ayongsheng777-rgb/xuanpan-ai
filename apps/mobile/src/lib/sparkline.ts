/**
 * 曲线几何 —— 把一串采样值折成 SVG 折线路径。**纯函数，无 React / RN 依赖**，可直接单测。
 *
 * 为什么不写在页面里，而要单独成模块：
 *
 * 归一化那三行代码有一个**在真机上必然遇到**的坑 —— 手机静止平放时磁场读数几乎恒定，
 * `max - min ≈ 0`，拿它当分母会得到 `NaN`，整条曲线**静默消失**：不报错、不崩溃、
 * 只是画不出来。而"数据明明有、界面却空白"这种故障最难定位。
 *
 * 所以这里主动做三件页面里不容易想周全的事：
 *
 * 1. **空样本返回 `null`**（而不是空字符串）—— 调用方必须显式处理"没有数据"，
 *    不能拿到一个"看起来画过了"的空路径。与 RULE-008 同精神：没有就是没有。
 * 2. **先剔除非有限值** —— 混进一个 `NaN` 不该毁掉整条线。
 * 3. **最小跨度保护** —— 见 `DEFAULT_MIN_SPAN`。这一条防的不是崩溃，而是**误导**。
 *
 * 另一条容易写反的约定：**磁场越强，曲线越高**。y 轴在 SVG 里是向下增长的，
 * 写成 `(v - lo) / span` 会把整条曲线上下颠倒 —— 而颠倒的曲线看上去仍然"像条曲线"。
 */

/** 默认绘图区宽度（用户单位，与 viewBox 一致，实际渲染由 SVG 缩放） */
export const DEFAULT_SPARKLINE_WIDTH = 300;
/** 默认绘图区高度（像素） */
export const DEFAULT_SPARKLINE_HEIGHT = 72;

/** 纵向内边距（像素）：曲线不贴上下边，否则极值点会被边框压住看不清 */
const DEFAULT_PADDING_Y = 6;

/**
 * 值域最小跨度（μT）`[推测]` —— 工程经验值，真机走查后可调。
 *
 * 为什么必须有这个保护：地磁正常区间是 25~65 μT，而手机静止平放时相邻数秒的
 * 读数波动通常只有 0.1~0.5 μT。若直接按 `min`/`max` 归一化，这 0.3 μT 的噪声
 * 会被拉满整个绘图区，**看起来像剧烈波动** —— 用户据此判定"磁场不稳、测量无效"，
 * 而实际上磁场稳得很。固定一个最小跨度后，静止时曲线接近水平，与事实一致。
 */
export const DEFAULT_MIN_SPAN = 4;

export interface SparklineGeometry {
  /** SVG path 的 `d` 属性（`M x y L x y …`） */
  d: string;
  /** 数据自身的最小值 */
  min: number;
  /** 数据自身的最大值 */
  max: number;
  /** 纵轴下界（= 值域中点 − 跨度/2；可能低于 `min`） */
  lo: number;
  /** 纵轴上界（= 值域中点 + 跨度/2；可能高于 `max`） */
  hi: number;
}

export interface SparklineOptions {
  width?: number;
  height?: number;
  paddingY?: number;
  minSpan?: number;
}

/** 保留两位小数，避免 path 字符串被浮点尾巴撑长 */
function round2(v: number): number {
  return Math.round(v * 100) / 100;
}

/**
 * 把采样序列折成折线路径。
 *
 * - 空序列、或全部为非有限值 → 返回 `null`（调用方需自行处理"无数据"态）
 * - 单点 → 返回一个零长度线段（`M x y L x y`），配合 `strokeLinecap="round"` 显示为点
 * - x 轴均匀铺满 `[0, width]`，y 轴按值域映射，**值大在上**
 *
 * `lo` / `hi` 一并返回，供界面标注纵轴量程 —— 用户看到曲线时应当能知道它站在哪个刻度上，
 * 否则一段被最小跨度保护压平的曲线与一段真实平稳的曲线长得一模一样。
 */
export function buildSparkline(
  values: readonly number[],
  options: SparklineOptions = {},
): SparklineGeometry | null {
  const width = options.width ?? DEFAULT_SPARKLINE_WIDTH;
  const height = options.height ?? DEFAULT_SPARKLINE_HEIGHT;
  const paddingY = options.paddingY ?? DEFAULT_PADDING_Y;
  const minSpan = options.minSpan ?? DEFAULT_MIN_SPAN;

  const finite = values.filter((v) => Number.isFinite(v));
  if (finite.length === 0) return null;

  const min = Math.min(...finite);
  const max = Math.max(...finite);

  // 跨度下限保护：span 恒 ≥ minSpan > 0，因此下面 (hi - lo) 永不可能是 0，
  // 从结构上消除了"恒定读数 → 除零 → NaN"这条路。
  const span = Math.max(max - min, minSpan);
  const center = (min + max) / 2;
  const lo = center - span / 2;
  const hi = center + span / 2;

  const innerH = Math.max(1, height - paddingY * 2);
  const xOf = (i: number): number =>
    finite.length === 1 ? width / 2 : (i / (finite.length - 1)) * width;
  // y 轴向下增长，故用 (hi - v)：值越大 y 越小 → 曲线越高
  const yOf = (v: number): number => paddingY + ((hi - v) / (hi - lo)) * innerH;

  const pts = finite.map((v, i) => [round2(xOf(i)), round2(yOf(v))] as const);
  const d =
    pts.length === 1
      ? `M ${pts[0]![0]} ${pts[0]![1]} L ${pts[0]![0]} ${pts[0]![1]}`
      : pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'} ${x} ${y}`).join(' ');

  return { d, min, max, lo: round2(lo), hi: round2(hi) };
}
