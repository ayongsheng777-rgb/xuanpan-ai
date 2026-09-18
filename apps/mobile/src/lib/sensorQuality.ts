/**
 * 手机传感器测量与质量评估 —— **纯函数，无 React / RN 依赖**，可直接单测。
 *
 * 对应 V2 规范 §7（SensorFusion）、§8（传感器质量判断）：
 *   「不能简单读取手机磁力计就认为数据可信」—— 必须实时检测磁场、水平、稳定性。
 *
 * 三个质量维度（对应演示图第 3 屏右侧三张指标卡）：
 *   1. 磁场：强度是否在地球磁场正常区间、波动是否小
 *   2. 水平：设备俯仰/横滚是否接近水平
 *   3. 稳定：方位角读数是否随时间稳定（圆统计，过 360° 边界不跳变）
 *
 * ⚠️ 角度是**圆量**：347° 与 2° 实际只差 15°，但算术平均会算出 174.5°。
 *    方位角的波动必须用圆统计（方向向量平均），这是本文件最容易写错的地方。
 *
 * 标注约定（AGENTS.md §4）：
 *   - `[已确认]` 地球磁场强度典型区间 25~65 μT（NOAA 公开数据）
 *   - `[推测]` 各评分阈值（σ、倾角容忍度）为工程经验值，真机走查后可调
 */

// ==========================================================================
// 基础量
// ==========================================================================

export interface Vector3 {
  x: number;
  y: number;
  z: number;
}

/** 地球磁场强度典型区间（μT）`[已确认]` */
export const EARTH_FIELD_MIN_UT = 25;
export const EARTH_FIELD_MAX_UT = 65;

/** 三轴矢量的模（磁场强度 μT / 加速度 m/s²） */
export function magnitudeOf(v: Vector3): number {
  return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
}

/**
 * 简易方位角（度，0=磁北，顺时针递增）。
 *
 * 成立前提：**设备近似水平**（屏幕朝上平放）。expo-sensors 的磁力计
 * 返回设备坐标系三轴：x 向右、y 向屏幕上方、z 垂直屏幕向外。
 * 平放时磁北方向 = atan2(-x, y)。
 *
 * 大倾角下未做倾角补偿（需要旋转矩阵），所以质量评估里
 * 「水平」不合格时，方位角读数也不应被采信 —— 两者是联动的。
 */
export function azimuthOf(mag: Vector3): number {
  const deg = (Math.atan2(-mag.x, mag.y) * 180) / Math.PI;
  return ((deg % 360) + 360) % 360;
}

/**
 * 由重力加速度求设备姿态（度）。
 *
 * 平放静止时加速度计读数 ≈ (0, 0, -9.81)（z 轴垂直屏幕向外，重力向下）。
 * pitch：俯仰（绕 x 轴）；roll：横滚（绕 y 轴）。
 * roll 用 `atan2(y, -z)` 而不是 `atan2(y, z)` —— 后者会把
 * 「平放」算成 180° 而不是 0°（z 平放时为负）。
 */
export function tiltOf(accel: Vector3): { pitch: number; roll: number } {
  const pitch = (Math.atan2(-accel.x, Math.sqrt(accel.y * accel.y + accel.z * accel.z)) * 180) / Math.PI;
  const roll = (Math.atan2(accel.y, -accel.z) * 180) / Math.PI;
  return { pitch, roll };
}

// ==========================================================================
// 统计
// ==========================================================================

/** 算术标准差 */
export function stdevOf(values: readonly number[]): number {
  if (values.length < 2) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) * (b - mean), 0) / values.length;
  return Math.sqrt(variance);
}

/**
 * 圆标准差（度）—— 方位角专用。
 *
 * 把每个角度当成单位向量求合向量，合向量长度 R∈(0,1] 越接近 1 方向越集中。
 * 圆标准差 = sqrt(-2·ln R)，换算回角度。
 * 空样本或方向完全均匀（R=0）时返回 180（最大不确定性）。
 */
export function circularStdevOf(degrees: readonly number[]): number {
  if (degrees.length < 2) return 180;
  let sin = 0;
  let cos = 0;
  for (const d of degrees) {
    sin += Math.sin((d * Math.PI) / 180);
    cos += Math.cos((d * Math.PI) / 180);
  }
  const r = Math.sqrt(sin * sin + cos * cos) / degrees.length;
  // R→0 时 -2·ln(R) 发散（对顶样本算出几百度的假值），截断到最大不确定度 180°
  if (r < 1e-9) return 180;
  return Math.min(180, (Math.sqrt(-2 * Math.log(r)) * 180) / Math.PI);
}

// ==========================================================================
// 质量评估（V2 §8）
// ==========================================================================

export interface QualityInput {
  /** 最近 N 次磁场强度（μT） */
  magneticMagnitudes: readonly number[];
  /** 最近 N 次姿态（度） */
  tilts: readonly { pitch: number; roll: number }[];
  /** 最近 N 次方位角（度） */
  azimuths: readonly number[];
}

export type Grade = '优' | '良' | '中' | '差';

export interface QualityResult {
  /** 0-100 */
  magnetic: number;
  level: number;
  stability: number;
  overall: number;
  magneticLabel: '稳定' | '波动' | '异常';
  levelLabel: '水平' | '倾斜';
  grade: Grade;
  /** 给用户的可操作提示（V2 §8.4） */
  hints: string[];
}

/** 评分阈值 `[推测]`：工程经验值，真机走查后可调 */
const THRESHOLDS = {
  /** 磁场波动 σ（μT）：≤1 满分，≥8 零分 */
  magStdevFull: 1,
  magStdevZero: 8,
  /** 最大倾角（度）：≤3 满分，≥15 零分 */
  tiltFull: 3,
  tiltZero: 15,
  /** 方位圆标准差（度）：≤1 满分，≥10 零分 */
  azStdevFull: 1,
  azStdevZero: 10,
} as const;

/** 线性插值评分：value ≤ full → 100；≥ zero → 0 */
function scoreBetween(value: number, full: number, zero: number): number {
  if (value <= full) return 100;
  if (value >= zero) return 0;
  return Math.round(((zero - value) / (zero - full)) * 100);
}

function gradeOf(overall: number): Grade {
  if (overall >= 85) return '优';
  if (overall >= 70) return '良';
  if (overall >= 50) return '中';
  return '差';
}

/**
 * 综合质量评估。
 *
 * 空样本（传感器还没出数）返回全 0 + 一条提示，而不是假装 100 分 ——
 * 「没有数据」和「数据很好」是两回事（V2 §8 与 RULE-008 的同源要求）。
 */
export function assessQuality(input: QualityInput): QualityResult {
  const hints: string[] = [];

  if (input.magneticMagnitudes.length === 0) {
    return {
      magnetic: 0,
      level: 0,
      stability: 0,
      overall: 0,
      magneticLabel: '异常',
      levelLabel: '倾斜',
      grade: '差',
      hints: ['传感器暂无数据。请确认设备支持磁力计，或离开模拟器在真机上测量。'],
    };
  }

  // ---- 磁场 ----
  const magNow = input.magneticMagnitudes[input.magneticMagnitudes.length - 1]!;
  const magStdev = stdevOf(input.magneticMagnitudes);
  let magnetic = scoreBetween(magStdev, THRESHOLDS.magStdevFull, THRESHOLDS.magStdevZero);
  if (magNow < EARTH_FIELD_MIN_UT || magNow > EARTH_FIELD_MAX_UT) {
    // 强度超出地球磁场区间 = 必然有干扰或传感器异常，直接压到 40 以下
    magnetic = Math.min(magnetic, 30);
    hints.push(
      `当前磁场 ${magNow.toFixed(1)} μT，超出地磁正常区间（${EARTH_FIELD_MIN_UT}~${EARTH_FIELD_MAX_UT} μT）。` +
        '附近可能有电脑、音箱、磁铁或金属结构，建议移动 1~2 米后重新测量。',
    );
  } else if (magnetic < 70) {
    hints.push('磁场波动较大，请远离金属物体并保持手机平稳。');
  }

  // ---- 水平 ----
  const maxTilt = input.tilts.reduce((m, t) => Math.max(m, Math.abs(t.pitch), Math.abs(t.roll)), 0);
  const level = scoreBetween(maxTilt, THRESHOLDS.tiltFull, THRESHOLDS.tiltZero);
  if (level < 70) hints.push('手机未保持水平，方位角读数会偏差，请将手机放平。');

  // ---- 稳定 ----
  const azStdev = circularStdevOf(input.azimuths);
  const stability = scoreBetween(azStdev, THRESHOLDS.azStdevFull, THRESHOLDS.azStdevZero);
  if (stability < 70) hints.push('方向读数不稳定，请持稳手机片刻再读数。');

  const overall = Math.round(magnetic * 0.4 + level * 0.3 + stability * 0.3);

  return {
    magnetic,
    level,
    stability,
    overall,
    magneticLabel: magnetic >= 70 ? '稳定' : magnetic >= 40 ? '波动' : '异常',
    levelLabel: maxTilt < 5 ? '水平' : '倾斜',
    grade: gradeOf(overall),
    hints,
  };
}
