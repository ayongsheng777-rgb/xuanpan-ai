/**
 * 传感器测量 `/sensors` —— V2 演示图第 3 屏。
 *
 * 布局：磁北指示 → 深色盘面 → 方位角大字 → 综合质量 → 三张指标卡 →
 *       可操作提示 → 磁场强度曲线 → 原始三轴数据表。
 *
 * 与相邻两页的职责分工（V2 §30「一页一事」，别混起来）：
 *   - `/`（罗盘首页）：仿真模式，盘面只由手指拖动，**不读传感器**；
 *   - `/adjust`：调角度、上锁，盘面可由磁力计驱动，但不做质量判断；
 *   - `/sensors`（本页）：**只做测量与可信度判断**，不可拖、不可选山、不算术数。
 *
 * 🔴 三条必须守住的语义（错了就会给出"看起来正常"的假结论）：
 *
 * 1. **传感器无数据是一等状态** —— 模拟器/无磁力计设备上显示「—」+ 可操作提示，
 *    **不转圈等、更不编造数值**（V2 §63、RULE-008 同精神）。
 *    盘面在这一态下**不渲染**：画一个 0° 的静止盘面会被读成"当前方位是 0°"。
 * 2. **读数是相对磁北，不是真北** —— 本页未做磁偏角改正（需经纬度与地磁模型），
 *    所以盘面山格只能作方向参考，**不构成坐向结论**。页面与讲解里都写明了这一点。
 * 3. **「磁场质量」≠ 角度精度** —— 那个 0~100 分衡量的是"强度是否在地磁正常区间、
 *    波动是否小"，是工程经验评分（阈值见 `lib/sensorQuality.ts`）。
 *    叫成"精度"会让人以为它在保证角度准确性，而本页做不到那个承诺。
 */

import { Ionicons } from '@expo/vector-icons';
import { Stack } from 'expo-router';
import React, { useId } from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Defs, LinearGradient, Line, Path, Stop } from 'react-native-svg';

import { AppText } from '@/components/AppText';
import { CompassDial, DIAL_DARK } from '@/components/CompassDial';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { stdevOf, type Grade, type Vector3 } from '@/lib/sensorQuality';
import {
  DEFAULT_MIN_SPAN,
  DEFAULT_SPARKLINE_HEIGHT,
  DEFAULT_SPARKLINE_WIDTH,
  buildSparkline,
} from '@/lib/sparkline';
import { useSensorSnapshot } from '@/services/useSensors';
import { instrument, radius, space } from '@/theme/tokens';

/** 质量等级的配色 —— 这是**仪器质量**的绿/红，不是术数吉凶，两者不要互相套用 */
function gradeColor(grade: Grade): string {
  if (grade === '优') return instrument.ok;
  if (grade === '良') return instrument.accent;
  if (grade === '中') return instrument.warn;
  return instrument.danger;
}

export default function SensorsScreen(): React.JSX.Element {
  // 进入页面即订阅、离开即退订（磁力计高频采样耗电，见 useSensors 注释）
  const sensor = useSensorSnapshot(true);
  const { quality } = sensor;

  const azimuth = sensor.azimuth;
  const magnitude = sensor.magneticMagnitude;
  const hasAzimuth = azimuth !== null;

  const maxTilt = sensor.tilt
    ? Math.max(Math.abs(sensor.tilt.pitch), Math.abs(sensor.tilt.roll))
    : null;

  /**
   * 渐变 id 必须唯一 —— 与 CompassDial 同一条理由：同页若出现两条曲线而共用 id，
   * 后渲染的那条会把前一条的面积填充也改成自己的。
   */
  const areaGradientId = `ml-area-${useId().replace(/[^a-zA-Z0-9]/g, '')}`;

  // 曲线几何在纯函数里算（含恒定信号的除零保护，见 lib/sparkline）
  const curve = buildSparkline(sensor.magneticSeries, {
    width: DEFAULT_SPARKLINE_WIDTH,
    height: DEFAULT_SPARKLINE_HEIGHT,
  });
  const sigma = sensor.magneticSeries.length >= 2 ? stdevOf(sensor.magneticSeries) : null;

  return (
    <>
      <Stack.Screen
        options={{
          title: '传感器测量',
          headerStyle: { backgroundColor: instrument.bg },
          headerTintColor: instrument.text,
          headerShadowVisible: false,
          headerRight: () => <HelpButton topic="sensors" color={instrument.textSecondary} />,
        }}
      />
      <Screen scroll style={styles.root}>
        {/* ---------- 无数据态：先说清楚，别让用户对着「—」猜 ---------- */}
        {!sensor.available ? (
          <View style={[styles.card, styles.warnCard]}>
            <Ionicons name="alert-circle-outline" size={18} color={instrument.warn} />
            <AppText size="sm" color={instrument.text} style={styles.warnText}>
              未收到任何传感器数据。Android 模拟器通常不提供磁力计与加速度计 ——
              请在真机上测量，不必反复刷新本页。
            </AppText>
          </View>
        ) : null}

        {/* ---------- 磁北指示 + 盘面 ---------- */}
        <View style={styles.northRow}>
          <AppText size="xs" color={instrument.textSecondary}>
            磁北 0°
          </AppText>
          <View style={styles.northArrow} />
        </View>
        <View style={styles.dialWrap}>
          {hasAzimuth ? (
            // rotation = -方位角：让当前朝向的刻度转到屏幕正上方（磁针不随盘转）
            <CompassDial
              size={280}
              palette={DIAL_DARK}
              style="zonghe"
              rotation={-(azimuth ?? 0)}
            />
          ) : (
            <View style={styles.dialPlaceholder}>
              <Ionicons name="compass-outline" size={40} color={instrument.muted} />
              <AppText size="sm" color={instrument.muted} center style={styles.placeholderText}>
                没有方位数据，盘面不显示{'\n'}
                （画个静止的盘面会被误读成 0°）
              </AppText>
            </View>
          )}
        </View>

        {/* ---------- 方位角大字 ---------- */}
        <View style={styles.card}>
          <AppText size="xs" color={instrument.textSecondary}>
            方位角（相对磁北）
          </AppText>
          <AppText size="display" weight="bold" color={instrument.accent} center style={styles.bigNumber}>
            {azimuth === null ? '—' : `${azimuth.toFixed(2)}°`}
          </AppText>
          <AppText size="xs" color={instrument.muted} center>
            {hasAzimuth ? '未做磁偏角改正：真北与磁北约差数度，随地区而变' : '等待磁力计数据'}
          </AppText>
        </View>

        {/* ---------- 综合质量 ---------- */}
        <View style={styles.card}>
          <View style={styles.qualityHead}>
            <View>
              <AppText size="xs" color={instrument.textSecondary}>
                综合质量
              </AppText>
              <AppText size="xs" color={instrument.muted} style={styles.weightNote}>
                磁场 40% · 水平 30% · 稳定 30%
              </AppText>
            </View>
            {sensor.available ? (
              <View style={styles.gradeRow}>
                <AppText
                  size="xxl"
                  weight="bold"
                  color={gradeColor(quality.grade)}
                  style={styles.gradeValue}
                >
                  {quality.overall}%
                </AppText>
                <View style={[styles.gradeChip, { backgroundColor: gradeColor(quality.grade) }]}>
                  <AppText size="xs" weight="semibold" color={instrument.bg}>
                    {quality.grade}
                  </AppText>
                </View>
              </View>
            ) : (
              <AppText size="xxl" weight="bold" color={instrument.muted}>
                —
              </AppText>
            )}
          </View>
          {/* 把三个分项摊开 —— 只给一个总分会让用户不知道是哪一项不合格 */}
          <View style={styles.breakdown}>
            <BreakdownItem label="磁场" score={quality.magnetic} available={sensor.available} />
            <BreakdownItem label="水平" score={quality.level} available={sensor.available} />
            <BreakdownItem label="稳定" score={quality.stability} available={sensor.available} />
          </View>
        </View>

        {/* ---------- 三张指标卡 ---------- */}
        <View style={styles.metricRow}>
          <MetricCard
            label="磁场强度"
            value={magnitude === null ? '—' : magnitude.toFixed(1)}
            unit="μT"
            sub={sigma === null ? '无数据' : `波动 ${sigma.toFixed(2)}`}
          />
          <MetricCard
            label="设备水平"
            value={maxTilt === null ? '—' : maxTilt.toFixed(1)}
            unit="°"
            sub={maxTilt === null ? '无数据' : quality.levelLabel}
          />
          <MetricCard
            label="磁场质量"
            value={magnitude === null ? '—' : `${quality.magnetic}`}
            unit="分"
            sub={magnitude === null ? '无数据' : quality.magneticLabel}
          />
        </View>

        {/* ---------- 可操作提示（V2 §8.4） ---------- */}
        {quality.hints.length > 0 ? (
          <View style={[styles.card, styles.hintCard]}>
            <AppText size="sm" weight="semibold" color={instrument.warn} style={styles.hintTitle}>
              当前读数不可直接采信
            </AppText>
            {quality.hints.map((hint) => (
              <AppText key={hint} size="sm" color={instrument.text} style={styles.hintItem}>
                · {hint}
              </AppText>
            ))}
          </View>
        ) : null}
        {sensor.available && quality.hints.length === 0 ? (
          <View style={[styles.card, styles.okCard]}>
            <AppText size="sm" weight="semibold" color={instrument.ok}>
              ✓ 磁场稳定 · 设备水平 · 方向稳定
            </AppText>
            <AppText size="xs" color={instrument.textSecondary} style={styles.okNote}>
              可以开始测量。请保持手机平放，读数会实时刷新。
            </AppText>
          </View>
        ) : null}

        {/* ---------- 磁场强度曲线 ---------- */}
        <View style={styles.card}>
          <View style={styles.curveHead}>
            <AppText size="xs" color={instrument.textSecondary}>
              磁场强度变化
            </AppText>
            <AppText size="xs" color={instrument.muted}>
              {sensor.magneticSeries.length} 个采样
            </AppText>
          </View>
          {curve ? (
            <>
              <Svg
                width="100%"
                height={DEFAULT_SPARKLINE_HEIGHT}
                viewBox={`0 0 ${DEFAULT_SPARKLINE_WIDTH} ${DEFAULT_SPARKLINE_HEIGHT}`}
              >
                {/* 面积渐变 —— 衬在折线之下，给波形一点"体积"。
                    顶部淡金、底部全透明，越往下越沉，因此不会抢折线本身。 */}
                <Defs>
                  <LinearGradient id={areaGradientId} x1="0" y1="0" x2="0" y2="1">
                    <Stop offset="0" stopColor={instrument.curveFill} stopOpacity={0.28} />
                    <Stop offset="1" stopColor={instrument.curveFill} stopOpacity={0} />
                  </LinearGradient>
                </Defs>
                {/* 单点时 areaD 为 null（一个点围不出面积），故先判空 */}
                {curve.areaD ? <Path d={curve.areaD} fill={`url(#${areaGradientId})`} /> : null}
                {/* 量程中线：没有它，一段被跨度保护压平的曲线看不出站在哪个刻度上。
                    必须画在面积之上，否则会被填充盖住。 */}
                <Line
                  x1={0}
                  y1={DEFAULT_SPARKLINE_HEIGHT / 2}
                  x2={DEFAULT_SPARKLINE_WIDTH}
                  y2={DEFAULT_SPARKLINE_HEIGHT / 2}
                  stroke={instrument.border}
                  strokeWidth={1}
                />
                <Path
                  d={curve.d}
                  stroke={instrument.accent}
                  strokeWidth={2}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </Svg>
              <AppText size="xs" color={instrument.muted} style={styles.curveNote}>
                纵轴 {curve.lo}~{curve.hi} μT · 虚线为量程中点。
                纵轴保留最小跨度 {DEFAULT_MIN_SPAN} μT，否则静止时 0.3 μT 的噪声会被画成剧烈起伏。
              </AppText>
            </>
          ) : (
            <AppText size="sm" color={instrument.muted} style={styles.curveEmpty}>
              尚未收到磁场数据
            </AppText>
          )}
        </View>

        {/* ---------- 原始三轴数据 ---------- */}
        <View style={styles.card}>
          <AppText size="xs" color={instrument.textSecondary} style={styles.tableTitle}>
            原始三轴数据
          </AppText>
          <View style={styles.tableRow}>
            <View style={styles.cellName} />
            {['X', 'Y', 'Z'].map((axis) => (
              <AppText key={axis} size="xs" color={instrument.muted} center style={styles.cell}>
                {axis}
              </AppText>
            ))}
          </View>
          <AxisRow name="磁力计" unit="μT" v={sensor.magnetometer} digits={2} />
          <AxisRow name="加速度计" unit="m/s²" v={sensor.accelerometer} digits={2} />
          <AxisRow name="陀螺仪" unit="rad/s" v={sensor.gyroscope} digits={3} />
        </View>

        <AppText size="xs" color={instrument.muted} center style={styles.note}>
          读数全部来自手机传感器、在设备本地计算，不上传，也不产生任何术数计算结果。
          需要坐向结论请用「扫描真实罗盘」，本页只回答「这个方向读得准不准」。
        </AppText>
      </Screen>
    </>
  );
}

function BreakdownItem({
  label,
  score,
  available,
}: {
  label: string;
  score: number;
  available: boolean;
}): React.JSX.Element {
  return (
    <View style={styles.breakdownItem}>
      <AppText size="xs" color={instrument.muted}>
        {label}
      </AppText>
      <AppText size="md" weight="semibold" color={instrument.text} style={styles.breakdownScore}>
        {available ? score : '—'}
      </AppText>
    </View>
  );
}

function MetricCard({
  label,
  value,
  unit,
  sub,
}: {
  label: string;
  value: string;
  /** 值为「—」时不显示单位，避免出现「— μT」这种像是有量纲的读法 */
  unit: string;
  sub: string;
}): React.JSX.Element {
  const empty = value === '—';
  return (
    <View style={styles.metricCard}>
      <AppText size="xs" color={instrument.textSecondary}>
        {label}
      </AppText>
      <View style={styles.metricValueRow}>
        <AppText
          size="xl"
          weight="bold"
          color={empty ? instrument.muted : instrument.text}
          track="tight"
          numeric
        >
          {value}
        </AppText>
        {empty ? null : (
          <AppText size="xs" color={instrument.textSecondary} style={styles.metricUnit}>
            {unit}
          </AppText>
        )}
      </View>
      <AppText size="xs" color={empty ? instrument.muted : instrument.textSecondary}>
        {sub}
      </AppText>
    </View>
  );
}

function AxisRow({
  name,
  unit,
  v,
  digits,
}: {
  name: string;
  unit: string;
  v: Vector3 | null;
  digits: number;
}): React.JSX.Element {
  const fmt = (n: number): string => (v === null ? '—' : n.toFixed(digits));
  return (
    <View style={styles.tableRow}>
      <View style={styles.cellName}>
        <AppText size="sm" color={instrument.text}>
          {name}
        </AppText>
        <AppText size="xs" color={instrument.muted}>
          {unit}
        </AppText>
      </View>
      <AppText size="sm" color={v === null ? instrument.muted : instrument.text} center style={styles.cell}>
        {fmt(v?.x ?? 0)}
      </AppText>
      <AppText size="sm" color={v === null ? instrument.muted : instrument.text} center style={styles.cell}>
        {fmt(v?.y ?? 0)}
      </AppText>
      <AppText size="sm" color={v === null ? instrument.muted : instrument.text} center style={styles.cell}>
        {fmt(v?.z ?? 0)}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  card: {
    marginTop: space[4],
    backgroundColor: instrument.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    padding: space[3],
  },
  warnCard: { flexDirection: 'row', alignItems: 'flex-start', borderColor: instrument.warn },
  warnText: { flex: 1, marginLeft: space[2] },
  northRow: { alignItems: 'center', marginTop: space[4], gap: 2 },
  northArrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 5,
    borderRightWidth: 5,
    borderBottomWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: instrument.needle,
  },
  dialWrap: { alignItems: 'center', marginTop: space[1] },
  dialPlaceholder: {
    width: 280,
    height: 280,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 140,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: instrument.border,
    backgroundColor: instrument.surface,
  },
  placeholderText: { marginTop: space[3] },
  bigNumber: { marginTop: space[1], fontVariant: ['tabular-nums'] },
  qualityHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  weightNote: { marginTop: 2 },
  gradeRow: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  gradeValue: { fontVariant: ['tabular-nums'] },
  gradeChip: {
    paddingHorizontal: space[2],
    paddingVertical: 2,
    borderRadius: radius.pill,
  },
  breakdown: {
    flexDirection: 'row',
    marginTop: space[3],
    paddingTop: space[3],
    borderTopWidth: 1,
    borderTopColor: instrument.border,
  },
  breakdownItem: { flex: 1, alignItems: 'center' },
  breakdownScore: { marginTop: 2, fontVariant: ['tabular-nums'] },
  metricRow: { flexDirection: 'row', gap: space[2], marginTop: space[4] },
  metricCard: {
    flex: 1,
    backgroundColor: instrument.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    paddingVertical: space[3],
    paddingHorizontal: space[2],
  },
  metricValueRow: { flexDirection: 'row', alignItems: 'flex-end', marginTop: space[2] },
  metricUnit: { marginLeft: 2, marginBottom: 3 },
  hintCard: { borderColor: instrument.warn },
  hintTitle: { marginBottom: space[2] },
  hintItem: { marginTop: space[1] },
  okCard: { borderColor: instrument.ok },
  okNote: { marginTop: space[1] },
  curveHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  curveNote: { marginTop: space[2] },
  curveEmpty: { marginTop: space[3] },
  tableTitle: { marginBottom: space[2] },
  tableRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: space[1] },
  cellName: { flex: 1.6 },
  cell: { flex: 1, fontVariant: ['tabular-nums'] },
  note: { marginTop: space[4] },
});
