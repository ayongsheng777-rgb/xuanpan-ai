/**
 * 传感器质量探针 —— 把 `lib/sensorQuality.ts` 的计算结果导出成 JSON，
 * 供 Python 侧做跨语言一致性校验（见 `tests/mobile/test_sensor_quality.py`）。
 *
 * 校验动机与 compass_dial_probe 同源：质量评分是纯规则，
 * 「磁场异常时 overall 必须被压低」「方位波动用圆统计」这类规则
 * 一旦在前端被改坏（比如把圆标准差换成算术标准差），
 * 用户在模拟器上根本看不出来 —— 必须有锚点测试兜底。
 *
 * 运行方式（Node ≥ 22.6）：
 *   node --experimental-strip-types apps/mobile/scripts/sensor_quality_probe.ts
 */

import {
  EARTH_FIELD_MAX_UT,
  EARTH_FIELD_MIN_UT,
  assessQuality,
  azimuthOf,
  circularStdevOf,
  magnitudeOf,
  stdevOf,
  tiltOf,
} from '../src/lib/sensorQuality.ts';

const out = {
  constants: {
    EARTH_FIELD_MIN_UT,
    EARTH_FIELD_MAX_UT,
  },
  // 基础量锚点
  magnitude: {
    zero: magnitudeOf({ x: 0, y: 0, z: 0 }),
    unit_x: magnitudeOf({ x: 1, y: 0, z: 0 }),
    v345: magnitudeOf({ x: 3, y: 4, z: 0 }), // = 5
    typical: magnitudeOf({ x: 12.3, y: -45.7, z: 8.1 }),
  },
  azimuth: {
    // 平放、y 轴正对磁北 → 0°
    north: azimuthOf({ x: 0, y: 40, z: 0 }),
    // 磁北在设备右侧（x 正向）→ atan2(-x, y) = -90 → 270°
    east_side: azimuthOf({ x: 40, y: 0, z: 0 }),
    // 磁北在设备后方 → 180°
    south: azimuthOf({ x: 0, y: -40, z: 0 }),
    // 磁北在设备左侧 → 90°
    west_side: azimuthOf({ x: -40, y: 0, z: 0 }),
    typical: azimuthOf({ x: 12.3, y: -45.7, z: 8.1 }),
  },
  tilt: {
    flat: tiltOf({ x: 0, y: 0, z: -9.81 }),
    nose_down_30: tiltOf({ x: 0, y: 4.905, z: -8.496 }), // 顶边下压 30° → roll ≈ 30°
    right_down_45: tiltOf({ x: 6.936, y: 0, z: -6.936 }), // 右边下压 45° → pitch ≈ -45°
  },
  stdev: {
    empty: stdevOf([]),
    single: stdevOf([5]),
    constant: stdevOf([3, 3, 3, 3]),
    spread: stdevOf([1, 2, 3, 4, 5]),
  },
  // 圆统计锚点：347° 与 2° 的波动必须很小（算术标准差会给 ~172°）
  circularStdev: {
    empty: circularStdevOf([]),
    wrap_around: circularStdevOf([347, 2, 355, 359]),
    opposite: circularStdevOf([0, 180]),
    tight: circularStdevOf([100, 101, 99, 100]),
  },
  quality: {
    // 理想：地磁区间 + 无波动 + 水平 + 方位稳定 → 优
    ideal: assessQuality({
      magneticMagnitudes: [48.5, 48.6, 48.7, 48.7, 48.6],
      tilts: [
        { pitch: 0.5, roll: -0.4 },
        { pitch: 0.6, roll: -0.3 },
      ],
      azimuths: [347.2, 347.3, 347.2, 347.3],
    }),
    // 磁干扰：强度超区间 → magnetic ≤ 30 且带提示
    interference: assessQuality({
      magneticMagnitudes: [120, 125, 118, 122],
      tilts: [{ pitch: 0.5, roll: 0.4 }],
      azimuths: [10, 11, 10],
    }),
    // 倾斜：pitch 12° → level 低 + 提示
    tilted: assessQuality({
      magneticMagnitudes: [48.5, 48.6, 48.7],
      tilts: [{ pitch: 12, roll: 1 }],
      azimuths: [100, 100.5, 99.5],
    }),
    // 抖动：方位圆标准差大 → stability 低
    shaky: assessQuality({
      magneticMagnitudes: [48.5, 48.6, 48.7],
      tilts: [{ pitch: 0.5, roll: 0.4 }],
      azimuths: [10, 40, 350, 80, 300],
    }),
    // 空样本：全 0 + 传感器不可用提示
    empty: assessQuality({
      magneticMagnitudes: [],
      tilts: [],
      azimuths: [],
    }),
  },
};

process.stdout.write(JSON.stringify(out));
