/**
 * 首页的罗盘装饰（纯视觉，不可交互）。
 *
 * 与 `MountainRing` 的区别：那个是**输入控件**（点击选山），这个是**图形**。
 * 刻意不复用同一组件 —— 一个看起来可点却点不动的罗盘会误导用户
 * （Affordance 错位），比"多写 60 行绘图"代价更高。
 *
 * 画法：24 道刻度 + 三层同心环，全部用 SVG，颜色取自 Token。
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';
import Svg, { Circle, G, Line, Path } from 'react-native-svg';

import { alpha, brand, colors } from '@/theme/tokens';

import { indexToDegree, MOUNTAIN_COUNT, pointOnCircle } from '@/lib/ring24';

export interface HeroCompassProps {
  size?: number;
}

export function HeroCompass({ size = 240 }: HeroCompassProps): React.JSX.Element {
  const r = size / 2;
  const center = { x: r, y: r };

  // 三层环半径
  const rOuter = r - 2;
  const rMid = r * 0.74;
  const rInner = r * 0.46;

  // 八卦位（每 45°，共 8 条长刻度）
  const guaTicks = Array.from({ length: 8 }, (_, i) => i * 45);

  return (
    <View style={[styles.wrap, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        {/* 底色圆盘 */}
        <Circle cx={center.x} cy={center.y} r={rOuter} fill={colors.surface} />

        {/* 外环（金） */}
        <Circle cx={center.x} cy={center.y} r={rOuter} stroke={brand.gold} strokeWidth={2} fill="none" />
        <Circle cx={center.x} cy={center.y} r={rMid} stroke={alpha.primaryBorder} strokeWidth={1} fill="none" />
        <Circle cx={center.x} cy={center.y} r={rInner} stroke={brand.gold} strokeWidth={1} fill="none" />

        {/* 24 道刻度：地支位（每 30°）长、其余短 */}
        <G>
          {Array.from({ length: MOUNTAIN_COUNT }, (_, i) => {
            const deg = indexToDegree(i);
            const isBranch = i % 2 === 0;
            const from = pointOnCircle(center, isBranch ? r * 0.86 : r * 0.9, deg);
            const to = pointOnCircle(center, rOuter - 1, deg);
            return (
              <Line
                key={`tick-${i}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={isBranch ? brand.primary : colors.muted}
                strokeWidth={isBranch ? 1.6 : 0.8}
                strokeLinecap="round"
              />
            );
          })}
        </G>

        {/* 八卦位加粗刻度 */}
        <G>
          {guaTicks.map((deg) => {
            const from = pointOnCircle(center, rInner, deg);
            const to = pointOnCircle(center, r * 0.62, deg);
            return (
              <Line
                key={`gua-${deg}`}
                x1={from.x}
                y1={from.y}
                x2={to.x}
                y2={to.y}
                stroke={brand.jade}
                strokeWidth={1.2}
                strokeLinecap="round"
                opacity={0.55}
              />
            );
          })}
        </G>

        {/* 天池：中心圆 + 磁针意象（一半朱红一半深蓝） */}
        <Circle cx={center.x} cy={center.y} r={r * 0.17} fill={colors.bg} stroke={brand.gold} strokeWidth={1} />
        <Path
          d={`M ${center.x} ${center.y - r * 0.14} L ${center.x + r * 0.045} ${center.y} L ${center.x - r * 0.045} ${center.y} Z`}
          fill={colors.cinnabar}
        />
        <Path
          d={`M ${center.x} ${center.y + r * 0.14} L ${center.x + r * 0.045} ${center.y} L ${center.x - r * 0.045} ${center.y} Z`}
          fill={brand.primary}
        />
        <Circle cx={center.x} cy={center.y} r={2.5} fill={brand.gold} />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
