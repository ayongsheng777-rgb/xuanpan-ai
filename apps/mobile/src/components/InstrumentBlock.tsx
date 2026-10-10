/**
 * 道具化宫格块 —— 全站宫格入口的**唯一**实现。
 *
 * ## 为什么收成一个组件
 *
 * 「测盘」的 5 张来源卡与「分析」的 6 个术式卡原本是两份**各写一遍**的代码：
 * 都是"图标容器 + 标题 + 右上角问号 + 点开 InfoPopup"，但两边的
 * 圆角、图标容器尺寸、按下反馈、问号位置各不相同（一边 44px 一边 46px，
 * 一边用 `PressablePanel` 一边用裸 `Pressable`）。用户看不出这是同一个东西，
 * 只会在两个页面之间感到"哪里不太一样"。
 *
 * 2026-10-09 单屏改造时统一：**玄机道具化**外观（回纹角花 + HUD 底刻度）由
 * 本组件提供，页面只负责给图标与文案。
 *
 * ## 图标为什么由调用方传入
 *
 * 因为守卫 `test_submenu_icons_are_solid_and_large` 按**源码数值**查
 * `<Ionicons name={icon} size={N}` 且要求 N ≥ 26 —— 把图标渲染收进本组件
 * 会让那条守卫扫不到数值，从而变成假绿。所以图标节点由页面渲染、尺寸由页面负责，
 * 本组件只提供容器（`iconBox`）。
 */

import { Ionicons } from '@expo/vector-icons';
import React, { type ReactNode, useState } from 'react';
import {
  Animated,
  Pressable,
  StyleSheet,
  View,
  type DimensionValue,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Card';
import { CornerFrame, HudRule } from '@/components/Hud';
import { InfoPopup } from '@/components/InfoPopup';
import { usePressScale } from '@/components/usePressScale';
import { colors, hud, instrument, radius, space } from '@/theme/tokens';

export type BlockTone = 'instrument' | 'light';

export interface InstrumentBlockProps {
  title: string;
  /** 图标节点（由调用方渲染，见文件头注释） */
  icon: ReactNode;
  /** 弹层正文：这个东西是干什么的 */
  desc: string;
  /** 弹层补充：本版的边界 / 注意事项 */
  bound?: string;
  /** 弹层主按钮文案，默认「进入{title}」 */
  ctaLabel?: string;
  onPress: () => void;
  /** 是否显示右上角问号（默认显示） */
  info?: boolean;
  tone?: BlockTone;
  /** 宽度，默认 '48%'（2 列宫格） */
  width?: DimensionValue;
  /** 块最小高度 */
  minHeight?: number;
  /** 图标容器边长 */
  iconBox?: number;
  /** 底部是否画一条 HUD 刻度（道具底座感） */
  base?: boolean;
  /**
   * 是否撑满父容器高度。
   *
   * 单屏布局里宫格的每一行都是 `flex: 1`（等高平分剩余高度），
   * 而块本身默认是"内容高度"——不撑满就会出现"行被撑开了、块还缩在顶部"的空档。
   * 传 true 让块跟着行一起长高（内容仍居中）。
   */
  fill?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function InstrumentBlock({
  title,
  icon,
  desc,
  bound,
  ctaLabel,
  onPress,
  info = true,
  tone = 'instrument',
  width = '48%',
  minHeight = 96,
  iconBox = 44,
  base = true,
  fill = false,
  style,
}: InstrumentBlockProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const press = usePressScale();
  const c = BLOCK_TONE[tone];

  return (
    <>
      <Pressable
        onPress={onPress}
        onPressIn={press.onPressIn}
        onPressOut={press.onPressOut}
        accessibilityRole="button"
        accessibilityLabel={`${title}：${desc}`}
        pressRetentionOffset={12}
        style={[{ width }, fill && styles.fill, style]}
      >
        <Animated.View
          style={[
            styles.block,
            {
              backgroundColor: c.bg,
              borderColor: c.border,
              minHeight,
              transform: [{ scale: press.scale }],
            },
            fill && styles.fill,
          ]}
        >
          {/* 回纹角花 —— 道具化的关键一笔（普通圆角方块 → 玄机金匮） */}
          <CornerFrame color={c.corner} />

          <View
            style={[
              styles.iconBox,
              { width: iconBox, height: iconBox, backgroundColor: c.iconBg },
            ]}
          >
            {icon}
          </View>

          <AppText
            size="sm"
            weight="semibold"
            color={c.title}
            center
            numberOfLines={2}
            style={styles.title}
          >
            {title}
          </AppText>

          {base ? <HudRule color={c.corner} style={styles.base} /> : null}

          {info ? (
            <Pressable
              onPress={() => setOpen(true)}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel={`${title}的详细说明`}
              style={styles.infoBtn}
            >
              <Ionicons name="information-circle-outline" size={18} color={c.muted} />
            </Pressable>
          ) : null}
        </Animated.View>
      </Pressable>

      {info ? (
        <InfoPopup
          visible={open}
          onClose={() => setOpen(false)}
          title={title}
          subtitle="选之前先看看"
        >
          <AppText size="sm" color={colors.text} style={styles.popupBody}>
            {desc}
          </AppText>
          {bound ? (
            <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
              注意：{bound}
            </AppText>
          ) : null}
          <Button
            label={ctaLabel ?? `进入${title}`}
            onPress={() => {
              setOpen(false);
              onPress();
            }}
          />
        </InfoPopup>
      ) : null}
    </>
  );
}

/**
 * 宫格容器 —— 2 列自适应换行。
 *
 * 单独给出来是为了让"块与块之间的间距"全站一致：原来 `test.tsx` 给 `gap: space[2]`，
 * `analysis.tsx` 也给 `space[2]`，但一个用 `width: '48%'` 另一个用 `width: '48%' + flexGrow`，
 * 于是两页的块宽其实不一样（一页撑满、一页不撑）。
 */
export function BlockGrid({
  children,
  gap = space[2],
  style,
}: {
  children: ReactNode;
  gap?: number;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  return <View style={[styles.grid, { gap }, style]}>{children}</View>;
}

const BLOCK_TONE = {
  instrument: {
    bg: instrument.surface,
    border: instrument.border,
    corner: hud.frame,
    iconBg: instrument.surfaceAlt,
    title: instrument.text,
    muted: instrument.muted,
  },
  light: {
    bg: colors.surface,
    border: colors.border,
    corner: hud.frame,
    iconBg: colors.surfaceAlt,
    title: colors.text,
    muted: colors.muted,
  },
} as const;

const styles = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', alignContent: 'flex-start' },
  fill: { flex: 1 },
  block: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: space[1],
    borderRadius: radius.lg,
    borderWidth: 1,
    paddingVertical: space[3],
    paddingHorizontal: space[2],
  },
  iconBox: {
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: { lineHeight: 20 },
  base: { alignSelf: 'stretch', marginTop: space[1] },
  infoBtn: { position: 'absolute', top: space[1], right: space[1], padding: space[1] },
  popupBody: { lineHeight: 24 },
});
