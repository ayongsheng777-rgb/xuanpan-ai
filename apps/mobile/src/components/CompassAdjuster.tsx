/**
 * 罗盘调节台 —— 盘面 + **逐项手动调节**。
 *
 * 解决的实际问题（用户实测反馈）：
 *   识别出来的坐向落到盘面上之后，**常常与手里罗盘的读数差一点**。
 *   差一点往往是因为：拍摄有透视变形、罗盘本身磁偏角未校准、或照片里
 *   鱼丝线只测到直线而两端需人工判坐向。这些都不是算法能定死的，
 *   所以必须让用户能**逐项**把盘面调到与实物一致。
 *
 * 三个可调项，各自独立（改一个不影响另一个）：
 *   1. **盘体旋转** rotation —— 粗调 15°（一格山）/ 中调 1° / 精调 0.5°
 *   2. **坐山** sitting —— 直接点盘面，或用 ◀▶ 逐格微调
 *   3. **一键对齐** —— 把实测角转到 12 点方向，便于肉眼比对实物
 *
 * 为什么不用滑杆：滑杆在 15° 一格这种"离散 + 精细"混合的场景下很难给准，
 * 而按钮的每一次点击都是确定的增量，用户能数着自己按了几下。
 */

import React, { useCallback } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import {
  NUDGE_STEPS,
  normalizeSigned,
  rotationToAlign,
} from '@/lib/compassDial';
import {
  MOUNTAIN_COUNT,
  nameOfIndex,
  oppositeIndex,
} from '@/lib/ring24';
import { alpha, colors, font, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';
import { CompassDial } from './CompassDial';

/** 实测角校准步长（度）。分金 3° 一格，故用亚度级微调逼近现场读数 */
const CALIBRATION_STEPS = [-0.5, -0.1, 0.1, 0.5] as const;

export interface CompassAdjusterProps {
  /** 坐山索引（盘面角）；null = 未选 */
  sitting: number | null;
  /** 盘体旋转量（度） */
  rotation: number;
  /** 实测角度（盘面角）；null = 该盘无实测支持 */
  measuredDegree?: number | null;
  onChangeSitting: (sitting: number | null) => void;
  onChangeRotation: (rotation: number) => void;
  /**
   * 手工校准实测角。**传了才显示校准行** —— 因为只有"有实测角且要拿它做分金精算"
   * 的场景（确认坐向页）才需要；纯展示场景给了它反而会诱导用户去改一个不产生作用的数。
   *
   * 校准**不会**丢掉识别原值：调用方应把原值另存留痕（RULE-008）。
   */
  onChangeMeasuredDegree?: (degree: number) => void;
  /** 盘面外径 */
  size?: number;
  disabled?: boolean;
}

export function CompassAdjuster({
  sitting,
  rotation,
  measuredDegree = null,
  onChangeSitting,
  onChangeRotation,
  onChangeMeasuredDegree,
  size = 300,
  disabled = false,
}: CompassAdjusterProps): React.JSX.Element {
  const facing = sitting === null ? null : oppositeIndex(sitting);
  const canCalibrate = onChangeMeasuredDegree !== undefined && measuredDegree !== null;

  const nudgeRotation = useCallback(
    (delta: number) => {
      if (disabled) return;
      onChangeRotation(rotation + delta);
    },
    [disabled, onChangeRotation, rotation],
  );

  const stepMountain = useCallback(
    (delta: number) => {
      if (disabled) return;
      const next = sitting === null ? 0 : (sitting + delta + MOUNTAIN_COUNT) % MOUNTAIN_COUNT;
      onChangeSitting(next);
    },
    [disabled, onChangeSitting, sitting],
  );

  const alignToMeasured = useCallback(() => {
    if (disabled || measuredDegree === null) return;
    onChangeRotation(rotationToAlign(measuredDegree));
  }, [disabled, measuredDegree, onChangeRotation, rotation]);

  const resetRotation = useCallback(() => {
    if (disabled) return;
    onChangeRotation(0);
  }, [disabled, onChangeRotation]);

  return (
    <View>
      <CompassDial
        size={size}
        rotation={rotation}
        sitting={sitting}
        measuredDegree={measuredDegree}
        interactive={!disabled}
        onRotate={onChangeRotation}
        onSelectMountain={onChangeSitting}
      />

      {/* ---------- 读数 ---------- */}
      <View style={styles.readout}>
        <View style={styles.readoutMain}>
          <AppText size="xl" weight="bold" color={sitting === null ? colors.muted : colors.primary}>
            {sitting === null ? '未选坐山' : `坐 ${nameOfIndex(sitting)}`}
          </AppText>
          <AppText size="md" color={colors.textSecondary} style={styles.readoutSub}>
            {facing === null ? '点盘面选择' : `向 ${nameOfIndex(facing)}`}
          </AppText>
        </View>
        <View style={styles.readoutSide}>
          <AppText size="xs" color={colors.textSecondary} style={styles.metricLabel}>
            盘面旋转
          </AppText>
          <AppText size="md" weight="semibold" color={colors.primary}>
            {normalizeSigned(rotation).toFixed(1)}°
          </AppText>
          <AppText size="xs" color={colors.muted} style={styles.metricLabel}>
            {measuredDegree === null ? '无实测角' : `实测 ${measuredDegree.toFixed(2)}°`}
          </AppText>
        </View>
      </View>

      {/* ---------- 盘体旋转微调 ---------- */}
      <SectionLabel text="盘体旋转（对齐实物罗盘）" />
      <View style={styles.btnRow}>
        {NUDGE_STEPS.map((step) => (
          <NudgeButton
            key={`r-${step}`}
            label={`−${step}°`}
            disabled={disabled}
            onPress={() => nudgeRotation(-step)}
          />
        ))}
      </View>
      <View style={styles.btnRow}>
        {[...NUDGE_STEPS].reverse().map((step) => (
          <NudgeButton
            key={`l-${step}`}
            label={`+${step}°`}
            disabled={disabled}
            onPress={() => nudgeRotation(step)}
          />
        ))}
      </View>

      {/* ---------- 坐山逐格微调 ---------- */}
      <SectionLabel text="坐山逐格微调（每格 15°）" />
      <View style={styles.btnRow}>
        <NudgeButton label="◀ 前一山" wide disabled={disabled} onPress={() => stepMountain(-1)} />
        <NudgeButton label="后一山 ▶" wide disabled={disabled} onPress={() => stepMountain(1)} />
      </View>

      {/* ---------- 实测角手工校准（仅当调用方允许） ---------- */}
      {canCalibrate ? (
        <>
          <SectionLabel text="实测角手工校准（该值决定分金格位）" />
          <View style={styles.btnRow}>
            {CALIBRATION_STEPS.map((d) => (
              <NudgeButton
                key={`cal-${d}`}
                label={`${d > 0 ? '+' : '−'}${Math.abs(d)}°`}
                disabled={disabled}
                onPress={() => onChangeMeasuredDegree?.(measuredDegree + d)}
              />
            ))}
          </View>
        </>
      ) : null}

      {/* ---------- 动作 ---------- */}
      <View style={styles.btnRow}>
        <NudgeButton
          label="对齐实测角"
          wide
          tone="primary"
          disabled={disabled || measuredDegree === null}
          onPress={alignToMeasured}
        />
        <NudgeButton
          label="旋转归零"
          wide
          tone="ghost"
          disabled={disabled || normalizeSigned(rotation) === 0}
          onPress={resetRotation}
        />
      </View>

      <AppText size="xs" color={colors.muted} style={styles.hint}>
        盘面正上方恒为真北（磁针不随盘转动）。识别与实物有偏差时，用上面的按钮把盘面调到与
        手里罗盘一致 —— 这一步调的是「视角」，不会改变你选中的坐山。
      </AppText>
    </View>
  );
}

// ==========================================================================
// 小组件
// ==========================================================================

function SectionLabel({ text }: { text: string }): React.JSX.Element {
  return (
    <AppText size="xs" color={colors.textSecondary} weight="medium" style={styles.sectionLabel}>
      {text}
    </AppText>
  );
}

function NudgeButton({
  label,
  onPress,
  disabled = false,
  wide = false,
  tone = 'default',
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  wide?: boolean;
  tone?: 'default' | 'primary' | 'ghost';
}): React.JSX.Element {
  const bg =
    tone === 'primary'
      ? colors.primary
      : tone === 'ghost'
        ? colors.surface
        : colors.surfaceAlt;
  const fg =
    tone === 'primary' ? colors.onPrimary : disabled ? colors.muted : colors.primary;
  const border = tone === 'primary' ? colors.primary : colors.border;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [
        styles.btn,
        wide ? styles.btnWide : styles.btnNarrow,
        { backgroundColor: bg, borderColor: border },
        disabled && styles.btnDisabled,
        pressed && !disabled && styles.btnPressed,
      ]}
    >
      <AppText
        size={wide ? 'sm' : 'md'}
        weight="semibold"
        color={fg}
        center
        numberOfLines={1}
      >
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  readout: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space[3],
    paddingHorizontal: space[2],
  },
  readoutMain: { flex: 1 },
  readoutSub: { marginTop: 2 },
  readoutSide: { alignItems: 'flex-end' },
  metricLabel: { marginTop: 2 },
  sectionLabel: { marginTop: space[3], marginBottom: space[2] },
  btnRow: { flexDirection: 'row', gap: space[2], marginBottom: space[2] },
  btn: {
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: space[2],
  },
  btnNarrow: { flex: 1, minWidth: 0 },
  btnWide: { flex: 1, minWidth: 0 },
  btnDisabled: { opacity: 0.45 },
  btnPressed: { backgroundColor: alpha.primarySoft },
  hint: { marginTop: space[2], lineHeight: font.lineHeight.xs },
});
