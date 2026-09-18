/**
 * 磁场曲线几何探针 —— 把 `lib/sparkline.ts` 的结果导出成 JSON，
 * 供 Python 侧做锚点校验（见 `tests/mobile/test_sparkline.py`）。
 *
 * 校验动机：归一化写错**不会报错**，只会让曲线看起来"有点怪"或干脆消失。
 * 且有两类错误在真机上完全看不出来 ——
 *   1. 恒定读数（手机静止）时除零 → NaN path → 整条线静默消失；
 *   2. 上下颠倒（y 轴方向写反）→ 仍是"一条像样的曲线"，只是强弱反了。
 * Python 侧直接解析本文件输出的 `d` 字符串，验的是**真的画出来的坐标**，不是源码。
 *
 * 运行方式（Node ≥ 22.6）：
 *   node --experimental-strip-types apps/mobile/scripts/sparkline_probe.ts
 */

import {
  DEFAULT_MIN_SPAN,
  DEFAULT_SPARKLINE_HEIGHT,
  DEFAULT_SPARKLINE_WIDTH,
  buildSparkline,
} from '../src/lib/sparkline.ts';

const OPTIONS = {
  width: DEFAULT_SPARKLINE_WIDTH,
  height: DEFAULT_SPARKLINE_HEIGHT,
  minSpan: DEFAULT_MIN_SPAN,
};

/** 各用例的采样序列 */
const SERIES = {
  /** 单点 */
  single: [45],
  /** 恒定（手机静止平放的真实情形）—— 最危险的一个 */
  constant: [45, 45, 45, 45, 45],
  /** 单调上升：用来验 y 方向（值大必须在上） */
  rising: [40, 41, 42, 43, 44],
  /** 窄幅真实波动（跨度 0.5 μT < 最小跨度 4）：曲线应接近水平 */
  narrow: [45.0, 45.2, 45.5, 45.3, 45.1],
  /** 宽幅波动（跨度 37 μT > 最小跨度）：应铺满绘图区 */
  wide: [30, 48, 62, 25, 55],
  /** 两点 */
  twoPoint: [40, 44],
} as const;

const geometry: Record<string, unknown> = {};
for (const [name, values] of Object.entries(SERIES)) {
  geometry[name] = buildSparkline(values, OPTIONS);
}

const out = {
  options: OPTIONS,
  /** 这些用例**必须**返回 null —— 直接序列化会与"算出了 null 字段"混淆，故显式转成布尔 */
  nullCases: {
    empty: buildSparkline([]) === null,
    allNonFinite: buildSparkline([Number.NaN, Number.POSITIVE_INFINITY]) === null,
  },
  /** 脏数据里只要还有有限值，就应当照样画出来 */
  survivesDirtyData: buildSparkline([40, Number.NaN, 42]) !== null,
  /** 脏数据被剔除后剩下的点数（应为 2） */
  dirtyPointCount: buildSparkline([40, Number.NaN, 42])?.d.split('L').length ?? 0,
  /**
   * 单点围不出面积 → `areaD` 必须是 `null`，**不能是空字符串**。
   * 空串会被调用方的 `? :` 判成"有值"，从而渲染一条看不见的零宽路径。
   */
  areaNullForSingle: buildSparkline([45], OPTIONS)?.areaD === null,
  geometry,
};

console.log(JSON.stringify(out));
