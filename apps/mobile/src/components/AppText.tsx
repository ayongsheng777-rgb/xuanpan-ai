/**
 * 统一的文字组件。
 *
 * 为什么不让各处直接写 `<Text style={{fontSize: 15}}>`：
 * 中文正文在 RN 里默认行高偏紧（英文行高比例套中文会显得挤），
 * 字号与行高必须成对使用。集中在这里，才能保证「同层级的字到处长得一样」。
 */

import React from 'react';
import { StyleSheet, Text, type TextProps, type TextStyle } from 'react-native';

import { colors, font } from '@/theme/tokens';

export type TextSize = keyof typeof font.size;
export type TextWeight = keyof typeof font.weight;
export type TextColor = keyof typeof colors;

export interface AppTextProps extends TextProps {
  size?: TextSize;
  weight?: TextWeight;
  color?: TextColor | string;
  /** 行高倍率；默认按字号查表 */
  lineHeightRatio?: number;
  center?: boolean;
}

export function AppText({
  size = 'md',
  weight = 'regular',
  color = 'text',
  lineHeightRatio,
  center,
  style,
  ...rest
}: AppTextProps): React.JSX.Element {
  const fontSize = font.size[size];
  const lineHeight = font.lineHeight[size] * (lineHeightRatio ?? 1);
  const resolved = resolveColor(color);

  const base: TextStyle = {
    fontSize,
    lineHeight,
    fontWeight: font.weight[weight],
    color: resolved,
    textAlign: center ? 'center' : 'auto',
  };

  return <Text {...rest} style={[base, style]} />;
}

/** 支持传 Token 名（推荐）或任意色值（特殊情况） */
function resolveColor(color: TextColor | string): string {
  const v = (colors as Record<string, string>)[color as string];
  return typeof v === 'string' ? v : color;
}

/** 章节标题：小号、加粗、字距略开，用于分区标题 */
export function SectionTitle({
  children,
  style,
  ...rest
}: AppTextProps): React.JSX.Element {
  return (
    <AppText
      size="sm"
      weight="semibold"
      color="textSecondary"
      style={[styles.sectionTitle, style]}
      {...rest}
    >
      {children}
    </AppText>
  );
}

const styles = StyleSheet.create({
  sectionTitle: { letterSpacing: 0.6, marginBottom: 8 },
});

export const textStyles = styles;
