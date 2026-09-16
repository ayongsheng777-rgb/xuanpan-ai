/**
 * 二十四山环形选择器 —— 手动修正坐向的**唯一**入口。
 *
 * 基线规范 §4.1 明确：**禁止让用户输入角度数值**，只能点环选山。
 * 理由：普通用户不知道"177.03°"意味着什么，但知道罗盘上"午"在哪；
 * 而角度输错（如 17.7 与 177 混淆）会静默产生完全错误的结论。
 *
 * 交互规则（几何由 `lib/ring24` 提供，纯函数、已单测）：
 *   - 点格子 → 选中坐山，**向山自动取对宫**（不允许单独选向山造出非法组合）
 *   - 再点同一格 → 取消选择
 *   - 中心常驻显示「坐 / 向」，以及**实测角度**（若有，用于分金精算）
 *
 * 配色遵循 Token：坐山用主色（最重的视觉），向山用金（辅色），其余为米底。
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Circle, G, Path, Text as SvgText } from 'react-native-svg';

import { alpha, colors, font, space } from '@/theme/tokens';

import {
  MOUNTAIN_COUNT,
  MOUNTAIN_NAMES,
  indexToDegree,
  nameOfIndex,
  oppositeIndex,
  pointToIndex,
  sectorPathOfIndex,
} from '@/lib/ring24';

import { AppText } from './AppText';

export interface MountainRingProps {
  /** 坐山索引；null = 未选 */
  sitting: number | null;
  /** 选择变化（传 null 表示取消） */
  onChange: (sitting: number | null) => void;
  /** 外径（含标签环）。默认 320 */
  size?: number;
  /**
   * 实测角度（识别而来）。仅用于在中心显示与在环上打一个刻度点 ——
   * **不改写选择**，用户没动的话提交时仍应回传这个角度。
   */
  measuredDegree?: number | null;
  disabled?: boolean;
}

/** 环带厚度占半径的比例 */
const BAND_RATIO = 0.34;
/** 相邻格视觉缝隙（角度） */
const GAP_DEG = 0.8;

export function MountainRing({
  sitting,
  onChange,
  size = 320,
  measuredDegree = null,
  disabled = false,
}: MountainRingProps): React.JSX.Element {
  // 用实际测量到的宽高，避免容器与 SVG 尺寸不一致时点击坐标错位
  const [measured, setMeasured] = useState<number>(size);
  const onLayout = useCallback((e: LayoutChangeEvent) => {
    const w = e.nativeEvent.layout.width;
    if (w > 0) setMeasured(w);
  }, []);

  const box = measured;
  const center = useMemo(() => ({ x: box / 2, y: box / 2 }), [box]);

  const outerRadius = box / 2;
  const innerRadius = outerRadius * (1 - BAND_RATIO);
  /** 标签所在半径（环带中线） */
  const labelRadius = (innerRadius + outerRadius) / 2;

  const facing = sitting === null ? null : oppositeIndex(sitting);

  const handlePress = useCallback(
    (e: { nativeEvent: { locationX: number; locationY: number } }) => {
      if (disabled) return;
      const { locationX, locationY } = e.nativeEvent;
      const hit = pointToIndex(center, innerRadius, outerRadius, { x: locationX, y: locationY });
      if (hit === null) return;
      // 再点同一格 = 取消
      onChange(hit === sitting ? null : hit);
    },
    [center, disabled, innerRadius, onChange, outerRadius, sitting],
  );

  return (
    <View onLayout={onLayout} style={[styles.wrap, { width: size, height: size }]}>
      <Svg width={box} height={box}>
        {/* 外圈装饰环 —— 罗盘形制，纯视觉 */}
        <Circle
          cx={center.x}
          cy={center.y}
          r={outerRadius - 1}
          stroke={colors.gold}
          strokeWidth={1.5}
          fill="none"
        />
        <Circle
          cx={center.x}
          cy={center.y}
          r={innerRadius - 2}
          stroke={alpha.primaryBorder}
          strokeWidth={1}
          fill={colors.surface}
        />

        {MOUNTAIN_NAMES.map((_, i) => {
          const isSitting = i === sitting;
          const isFacing = i === facing;
          const fill = isSitting ? colors.primary : isFacing ? colors.gold : colors.sand;
          return (
            <Path
              key={`sector-${i}`}
              d={sectorPathOfIndex(center, innerRadius, outerRadius, i, GAP_DEG)}
              fill={fill}
              stroke={colors.surface}
              strokeWidth={0.8}
            />
          );
        })}

        {/* 山名：随格旋转，字头指向环外（真实罗盘的排布方式） */}
        {MOUNTAIN_NAMES.map((name, i) => {
          const deg = indexToDegree(i);
          const rad = (deg * Math.PI) / 180;
          const x = center.x + labelRadius * Math.sin(rad);
          const y = center.y - labelRadius * Math.cos(rad);
          const isSitting = i === sitting;
          const isFacing = i === facing;
          // 地支山（子丑寅卯…）是罗盘主刻度，字号略大
          const isBranch = i % 2 === 0;
          return (
            <G key={`label-${i}`} transform={`rotate(${deg} ${x} ${y})`}>
              <SvgText
                x={x}
                y={y}
                fill={isSitting ? colors.onPrimary : isFacing ? colors.primary : colors.text}
                fontSize={isBranch ? 13 : 11}
                fontWeight={isSitting || isBranch ? '600' : '400'}
                textAnchor="middle"
                alignmentBaseline="central"
              >
                {name}
              </SvgText>
            </G>
          );
        })}

        {/* 实测角度刻度 —— 只作视觉提示，不参与选择 */}
        {measuredDegree !== null && <MeasuredTick center={center} radius={outerRadius} degree={measuredDegree} inner={innerRadius} />}
      </Svg>

      {/* 覆盖层：用自有几何做命中判定，而不是依赖 SVG 元素的点击 */}
      <Pressable
        onPress={handlePress}
        disabled={disabled}
        style={StyleSheet.absoluteFill}
        accessibilityRole="adjustable"
        accessibilityLabel="二十四山选择器"
      />

      {/* 中心读数 —— 放在 Pressable 之上，避免被拦点击（pointerEvents none） */}
      <View style={styles.centerReadout} pointerEvents="none">
        <AppText size="xxl" weight="bold" color={sitting === null ? colors.muted : colors.primary}>
          {sitting === null ? '未选' : `${nameOfIndex(sitting)}山`}
        </AppText>
        <AppText size="sm" color={colors.textSecondary} style={styles.centerSub}>
          {facing === null ? '点击外环选择坐山' : `向 ${nameOfIndex(facing)}`}
        </AppText>
        {measuredDegree !== null && (
          <AppText size="xs" color={colors.muted} style={styles.centerSub}>
            实测 {measuredDegree.toFixed(1)}°
          </AppText>
        )}
      </View>
    </View>
  );
}

/** 在环上标出实测角度的位置（一条细刻度） */
function MeasuredTick({
  center,
  radius,
  inner,
  degree,
}: {
  center: { x: number; y: number };
  radius: number;
  inner: number;
  degree: number;
}): React.JSX.Element {
  const t = (degree * Math.PI) / 180;
  const sin = Math.sin(t);
  const cos = Math.cos(t);
  const r1 = radius - 2;
  const r2 = inner + 2;
  return (
    <Path
      d={`M ${center.x + r1 * sin} ${center.y - r1 * cos} L ${center.x + r2 * sin} ${center.y - r2 * cos}`}
      stroke={colors.cinnabar}
      strokeWidth={2}
      strokeLinecap="round"
    />
  );
}

/** 未选择时的空态提示文案（供调用方复用，避免各处自己编） */
export function ringHint(sitting: number | null): string {
  if (sitting === null) return '点击外环选择坐山，向山会自动取对宫';
  return `已选坐${nameOfIndex(sitting)}向${nameOfIndex(oppositeIndex(sitting))}；点击同一格可取消`;
}

export { MOUNTAIN_COUNT };

const styles = StyleSheet.create({
  wrap: { alignSelf: 'center', justifyContent: 'center', alignItems: 'center' },
  centerReadout: {
    position: 'absolute',
    width: '46%',
    alignItems: 'center',
    justifyContent: 'center',
  },
  centerSub: { marginTop: space[1], textAlign: 'center' },
});
