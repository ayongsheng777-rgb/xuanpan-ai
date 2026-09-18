/**
 * 传感器订阅 Hook —— 把 expo-sensors 的三路订阅汇成一份实时快照。
 *
 * 对应 V2 §7 SensorService / SensorFusion。设计要点：
 *
 * 1. **环形缓冲**：只保留最近 WINDOW 个样本，质量评估需要「最近 N 次」
 *    的波动，全量存会无限增长。
 * 2. **订阅生命周期随组件**：进入页面订阅、离开页面退订 ——
 *    磁力计高频采样很耗电，不能后台常开。
 * 3. **不可用是一等状态**（V2 §63）：模拟器/无磁力计设备上 `available=false`，
 *    页面据此显示「传感器不可用」而不是转圈等到天荒地老。
 * 4. 计算全部委托给 `lib/sensorQuality.ts` 纯函数，本文件只做订阅与缓冲。
 */

import { Accelerometer, Gyroscope, Magnetometer } from 'expo-sensors';
import { useEffect, useMemo, useRef, useState } from 'react';

import {
  assessQuality,
  azimuthOf,
  magnitudeOf,
  tiltOf,
  type QualityResult,
  type Vector3,
} from '@/lib/sensorQuality';

/** 采样间隔（ms）。磁力计 10Hz 足够人眼读数，再快只是耗电 */
const SAMPLE_INTERVAL_MS = 100;
/** 质量评估窗口：最近 4 秒（40 个样本） */
const WINDOW = 40;

export interface SensorSnapshot {
  /** 方位角（度，0=磁北）。无数据时为 null */
  azimuth: number | null;
  /** 磁场强度（μT） */
  magneticMagnitude: number | null;
  /** 姿态（度） */
  tilt: { pitch: number; roll: number } | null;
  /** 原始三轴（展示用） */
  magnetometer: Vector3 | null;
  accelerometer: Vector3 | null;
  gyroscope: Vector3 | null;
  /** 磁场强度时间序列（画曲线用，新值在尾） */
  magneticSeries: readonly number[];
  /** 质量评估（空样本时 overall=0 + 提示） */
  quality: QualityResult;
  /** 是否有任何一路传感器出过数 */
  available: boolean;
}

function pushWindow<T>(buf: T[], item: T): T[] {
  buf.push(item);
  if (buf.length > WINDOW) buf.shift();
  return buf;
}

export function useSensorSnapshot(enabled: boolean): SensorSnapshot {
  const [mag, setMag] = useState<Vector3 | null>(null);
  const [acc, setAcc] = useState<Vector3 | null>(null);
  const [gyro, setGyro] = useState<Vector3 | null>(null);
  const magSeriesRef = useRef<number[]>([]);
  const azSeriesRef = useRef<number[]>([]);
  const tiltSeriesRef = useRef<{ pitch: number; roll: number }[]>([]);
  const [, forceTick] = useState(0);

  useEffect(() => {
    if (!enabled) return undefined;

    // 订阅动作本身可能在该平台不可用 —— expo web 产物里 expo-sensors 没有 web 实现，
    // `addListener` 会抛 `this._nativeModule.addListener is not a function`。
    // 必须在**这里**兜住：未捕获异常会让整页白屏，用户看到的是「APP 坏了」，
    // 而真实情况只是这个平台没有这类传感器。兜住后即回到本文件第 10 行承诺的
    // 「不可用是一等状态」—— available 保持 false，由页面显示提示文案。
    //
    // 注意判据不能写成 `typeof Magnetometer.addListener === 'function'`：
    // 在 web 上它**确实是**个函数，抛错发生在它内部的 _nativeModule 上。
    // 只有真调用一次才能判定平台是否支持，所以只能 try/catch。
    let magSub: { remove: () => void } | null = null;
    let accSub: { remove: () => void } | null = null;
    let gyroSub: { remove: () => void } | null = null;

    try {
      Magnetometer.setUpdateInterval(SAMPLE_INTERVAL_MS);
      Accelerometer.setUpdateInterval(SAMPLE_INTERVAL_MS);
      Gyroscope.setUpdateInterval(SAMPLE_INTERVAL_MS);

      magSub = Magnetometer.addListener((v) => {
        setMag(v);
        pushWindow(magSeriesRef.current, magnitudeOf(v));
        pushWindow(azSeriesRef.current, azimuthOf(v));
      });
      accSub = Accelerometer.addListener((v) => {
        setAcc(v);
        pushWindow(tiltSeriesRef.current, tiltOf(v));
      });
      gyroSub = Gyroscope.addListener(setGyro);
    } catch {
      // 可能只订成功了一部分，先拆干净再退回不可用状态，避免退订时二次抛错
      magSub?.remove();
      accSub?.remove();
      gyroSub?.remove();
      return undefined;
    }

    // 序列缓冲在 ref 里，组件不重渲染也想拿到新样本 —— 用轻量 tick 驱动
    const ticker = setInterval(() => forceTick((n) => n + 1), SAMPLE_INTERVAL_MS * 2);

    return () => {
      magSub?.remove();
      accSub?.remove();
      gyroSub?.remove();
      clearInterval(ticker);
      magSeriesRef.current = [];
      azSeriesRef.current = [];
      tiltSeriesRef.current = [];
    };
  }, [enabled]);

  return useMemo<SensorSnapshot>(() => {
    const magneticSeries = magSeriesRef.current;
    const azimuths = azSeriesRef.current;
    const tilts = tiltSeriesRef.current;
    return {
      azimuth: mag === null ? null : azimuthOf(mag),
      magneticMagnitude: mag === null ? null : magnitudeOf(mag),
      tilt: acc === null ? null : tiltOf(acc),
      magnetometer: mag,
      accelerometer: acc,
      gyroscope: gyro,
      magneticSeries,
      quality: assessQuality({
        magneticMagnitudes: magneticSeries,
        tilts,
        azimuths,
      }),
      available: mag !== null || acc !== null,
    };
    // forceTick 驱动的重渲染会重算；mag/acc/gyro 变化本身也是依赖
  }, [mag, acc, gyro]);
}
