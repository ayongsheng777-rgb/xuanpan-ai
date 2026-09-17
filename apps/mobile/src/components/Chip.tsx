/**
 * 小标签 / 筛选项 —— 黄历的快捷日期、择日的属相、断卦的占问类别都用它。
 *
 * 为什么必须抽成组件而不是各页各写一个：这类"小圆角块"最容易出现
 * "黄历页 padding 是 12/6、占测页是 10/4"的观感漂移，而它小到没人会注意到、
 * 又大到一眼能看出来。与色彩 token 是同一条理由：一个语义 = 一处实现。
 */

import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { alpha, colors, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';

export interface ChipProps {
  label: string;
  onPress: () => void;
  /** 选中态：填充主色。用于互斥选项（同组 chip 里至多一个 active） */
  active?: boolean;
}

export function Chip({ label, onPress, active = false }: ChipProps): React.JSX.Element {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [styles.chip, active && styles.chipActive, pressed && styles.pressed]}
    >
      <AppText
        size="xs"
        weight={active ? 'semibold' : 'regular'}
        color={active ? 'onPrimary' : 'primary'}
      >
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: space[3],
    paddingVertical: space[1] + 2,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  pressed: { opacity: 0.7 },

  tag: {
    paddingHorizontal: space[2] + 2,
    paddingVertical: space[1],
    borderRadius: radius.sm,
    borderWidth: 1,
  },
});

/** 只读标签的语义档 —— 与吉凶同构，但不叫 吉/凶：后者是结论，前者只是着色 */
export type TagTone = 'neutral' | 'good' | 'bad';

const TAG_PALETTE: Record<TagTone, { bg: string; border: string; fg: string }> = {
  neutral: { bg: colors.surfaceAlt, border: colors.border, fg: colors.textSecondary },
  good: { bg: alpha.jadeSoft, border: colors.jade, fg: colors.jade },
  bad: { bg: alpha.cinnabarSoft, border: colors.cinnabar, fg: colors.cinnabar },
};

/**
 * 只读标签 —— 与 `Chip` 同一视觉家族，但**不可点**。
 *
 * 为什么单独给一个组件而不是复用 Chip：可点与不可点的东西长得一模一样时，
 * 用户会去点它 —— 点了没反应，就会以为界面坏了。
 * 所以只读态统一去掉 Pressable，并把内边距略收，让它明显"不是控件"。
 */
export function Tag({
  label,
  tone = 'neutral',
}: {
  label: string;
  tone?: TagTone;
}): React.JSX.Element {
  const p = TAG_PALETTE[tone];
  return (
    <View style={[styles.tag, { backgroundColor: p.bg, borderColor: p.border }]}>
      <AppText size="xs" weight="medium" color={p.fg}>
        {label}
      </AppText>
    </View>
  );
}
