/**
 * 玄机 HUD 装饰原语 —— 玄学科技风的**结构与质感**，浅金配色。
 *
 * 2026-10-09 用户裁定「浅金科技」：不照搬深色玄学规范的玄黑底与青色全息
 * （那会撞上 `test_instrument_theme_is_light_and_golden` 这条用户自己定的守卫），
 * 只取它三样**与颜色无关**的东西：
 *
 *   1. 回纹 / 榫卯倒角 —— 卡片不再是普通圆角方块，四角有 L 形饰线（`CornerFrame`）
 *   2. HUD 刻度 —— 分隔线是一排刻度而不是一根实线（`HudRule`）
 *   3. 星宿连线底纹 —— 极淡的连线阵列，给空白处一点"在运转"的暗示（`Constellation`）
 *
 * ⚠️ 全部是**纯装饰**，因此：
 *   · 一律 `pointerEvents="none"`，绝不抢触摸事件；
 *   · 不承载任何信息 —— 没有它们界面照样能读（`accessibilityElementsHidden`）；
 *   · 底纹透明度不超过 0.12，否则会与文字争对比度。
 */

import React from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import Svg, { Circle, Line } from 'react-native-svg';

import { hud, radius } from '@/theme/tokens';

// ==========================================================================
// 刻度分隔线
// ==========================================================================

/**
 * 刻度分隔线 —— 一根细线 + 中央菱形 + 两端收头。
 *
 * 与普通 `Divider` 的区别：它读起来像"仪表面板的接缝"而不是"段落分隔"。
 * 用于标题栏下方、卡片之间，不用于卡片内部（内部要安静）。
 */
export function HudRule({
  color = hud.frame,
  style,
}: {
  color?: string;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  return (
    <View style={[styles.ruleRow, style]} pointerEvents="none" accessibilityElementsHidden>
      <View style={[styles.ruleLine, { backgroundColor: color }]} />
      <View style={[styles.ruleDiamond, { backgroundColor: color }]} />
      <View style={[styles.ruleLine, { backgroundColor: color }]} />
    </View>
  );
}

// ==========================================================================
// 回纹 / 榫卯角花
// ==========================================================================

/**
 * 道具化卡片的四角饰线。
 *
 * 用法：**父容器必须是 `position: relative`**（RN 默认即是），且不要 `overflow: hidden`
 * 之外的处理 —— 角线画在内侧 `inset` 处，圆角越大越要把 inset 加大。
 */
export function CornerFrame({
  color = hud.frame,
  inset = 3,
  size = 10,
  thickness = 1.5,
}: {
  color?: string;
  inset?: number;
  size?: number;
  thickness?: number;
}): React.JSX.Element {
  const base = { position: 'absolute' as const, width: size, height: size, borderColor: color };
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" accessibilityElementsHidden>
      <View
        style={[
          base,
          { top: inset, left: inset, borderTopWidth: thickness, borderLeftWidth: thickness },
        ]}
      />
      <View
        style={[
          base,
          { top: inset, right: inset, borderTopWidth: thickness, borderRightWidth: thickness },
        ]}
      />
      <View
        style={[
          base,
          { bottom: inset, left: inset, borderBottomWidth: thickness, borderLeftWidth: thickness },
        ]}
      />
      <View
        style={[
          base,
          { bottom: inset, right: inset, borderBottomWidth: thickness, borderRightWidth: thickness },
        ]}
      />
    </View>
  );
}

// ==========================================================================
// 星宿连线底纹
// ==========================================================================

/**
 * 固定的星点阵 —— **不能用 `Math.random()`**。
 *
 * 随机点阵会在每次重渲染时重新排布（传感器页每秒刷好几次），
 * 底纹就会持续跳动，读起来像"界面在闪"。
 * 这里用一张手写的固定表：四个象限各一组，避让中央内容区。
 */
const STARS: readonly { x: number; y: number }[] = [
  { x: 8, y: 12 },
  { x: 26, y: 6 },
  { x: 18, y: 30 },
  { x: 44, y: 18 },
  { x: 62, y: 9 },
  { x: 78, y: 22 },
  { x: 92, y: 14 },
  { x: 12, y: 62 },
  { x: 30, y: 78 },
  { x: 52, y: 88 },
  { x: 70, y: 70 },
  { x: 88, y: 84 },
  { x: 96, y: 52 },
  { x: 6, y: 88 },
];

/** 连线（星宿）—— 只连相邻两颗，形成"星图"而不是乱麻 */
const LINKS: readonly [number, number][] = [
  [0, 2],
  [1, 3],
  [3, 4],
  [4, 5],
  [5, 6],
  [7, 8],
  [8, 9],
  [9, 10],
  [10, 11],
  [11, 12],
  [2, 7],
  [3, 10],
  [6, 12],
];

/**
 * 星宿连线底纹 —— 铺满父容器的一层极淡星图。
 *
 * 用百分比坐标（viewBox 0 0 100 100 + preserveAspectRatio="none"），
 * 这样任何尺寸的容器都能铺满，不必按屏算像素。
 */
export function Constellation({
  color = hud.constellation,
  dotColor,
  style,
}: {
  color?: string;
  dotColor?: string;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  return (
    <View
      style={[StyleSheet.absoluteFill, styles.clip, style]}
      pointerEvents="none"
      accessibilityElementsHidden
    >
      <Svg width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
        {LINKS.map(([a, b], i) => (
          <Line
            key={i}
            x1={STARS[a]!.x}
            y1={STARS[a]!.y}
            x2={STARS[b]!.x}
            y2={STARS[b]!.y}
            stroke={color}
            strokeWidth={0.25}
          />
        ))}
        {STARS.map((s, i) => (
          <Circle key={i} cx={s.x} cy={s.y} r={0.55} fill={dotColor ?? color} />
        ))}
      </Svg>
    </View>
  );
}

// ==========================================================================
// HUD 刻度环
// ==========================================================================

/**
 * HUD 刻度环 —— 罗盘外圈那圈激光刻度。
 *
 * 为什么用 SVG 而不是堆 View：48 根刻度若各是一个 View，
 * 每次罗盘旋转都要重排 48 个节点；SVG 一次成型，旋转交给外层 transform。
 */
export function HudTickRing({
  size,
  color = hud.tick,
  majorColor = hud.tickMajor,
  /** 总刻度数（建议 24 / 48 / 72，与二十四山成整数倍关系） */
  count = 48,
  /** 每几根一个长刻度 */
  majorEvery = 8,
  inset = 2,
  style,
}: {
  size: number;
  color?: string;
  majorColor?: string;
  count?: number;
  majorEvery?: number;
  inset?: number;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  const c = size / 2;
  const rOuter = c - inset;
  const ticks = Array.from({ length: count }, (_, i) => {
    const major = i % majorEvery === 0;
    const rInner = rOuter - (major ? 9 : 5);
    const a = (i / count) * Math.PI * 2;
    const cos = Math.cos(a);
    const sin = Math.sin(a);
    return (
      <Line
        key={i}
        x1={c + cos * rInner}
        y1={c + sin * rInner}
        x2={c + cos * rOuter}
        y2={c + sin * rOuter}
        stroke={major ? majorColor : color}
        strokeWidth={major ? 1.4 : 0.8}
      />
    );
  });

  return (
    <View
      style={[StyleSheet.absoluteFill, styles.clip, style]}
      pointerEvents="none"
      accessibilityElementsHidden
    >
      <Svg width={size} height={size}>
        {ticks}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  ruleRow: { flexDirection: 'row', alignItems: 'center', height: 6 },
  ruleLine: { flex: 1, height: StyleSheet.hairlineWidth * 2 },
  ruleDiamond: {
    width: 5,
    height: 5,
    marginHorizontal: 6,
    borderRadius: radius.xs / 2,
    transform: [{ rotate: '45deg' }],
  },
  clip: { overflow: 'hidden' },
});
