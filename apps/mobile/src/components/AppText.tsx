/**
 * 统一的文字组件。
 *
 * 为什么不让各处直接写 `<Text style={{fontSize: 15}}>`：
 * 中文正文在 RN 里默认行高偏紧（英文行高比例套中文会显得挤），
 * 字号与行高必须成对使用。集中在这里，才能保证「同层级的字到处长得一样」。
 *
 * ## 层级阶梯（改这里前先读）
 *
 * 一屏里只允许出现这四层，**字号 + 字重 + 颜色三者必须同向变化**：
 *
 * | 层 | 角色 | 记号 |
 * |---|---|---|
 * | 1 | 页面主标题 | `xl`(20) / `bold` / `text` |
 * | 2 | 分区标题、卡片标题 | `md`(15) / `semibold` / `text` |
 * | 3 | 正文 | `md`(15) / `regular` / `text` |
 * | 4 | 辅助说明、注释 | `sm`(13) 或 `xs`(11) / `regular` / `textSecondary` |
 * | 特 | 仪表读数（一屏一个） | `metric`(40) / `heavy` / 域强调色 |
 *
 * 🔴 **分区标题曾经是 `sm`(13) + `textSecondary` —— 比它自己的正文更小、更淡。**
 *    结果卡片标题读起来比卡片内容次要，整页失去层级，19 个页面全中。
 *    层级倒挂是"看着不丑、但说不上哪里不对"的典型来源，所以这里把它钉成规则：
 *    **同一容器内，标题的字号不得小于正文，颜色不得比正文更淡。**
 */

import React from 'react';
import { StyleSheet, Text, type TextProps, type TextStyle } from 'react-native';

import { colors, font, tracking, type TrackName } from '@/theme/tokens';

export type TextSize = keyof typeof font.size;
export type TextWeight = keyof typeof font.weight;
export type TextColor = keyof typeof colors;

export interface AppTextProps extends TextProps {
  size?: TextSize;
  weight?: TextWeight;
  color?: TextColor | string;
  /** 行高倍率；默认按字号查表 */
  lineHeightRatio?: number;
  /** 字距档位；默认不设（继承系统） */
  track?: TrackName;
  /**
   * 等宽数字（`tabular-nums`）—— **凡数值会原地变化的地方都要开**。
   *
   * 比例数字下每个字的宽度不同（"1" 比 "8" 窄），读数一跳，整行长度就跟着跳，
   * 旁边的单位、分隔线、右对齐的值全部左右抖动。等宽后位宽固定，布局不动。
   *
   * 手机上这一点尤其明显：传感器读数每秒刷好几次，抖动会被读成"界面在闪"。
   */
  numeric?: boolean;
  center?: boolean;
}

export function AppText({
  size = 'md',
  weight = 'regular',
  color = 'text',
  lineHeightRatio,
  track,
  numeric,
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
    letterSpacing: track ? tracking[track] : undefined,
    fontVariant: numeric ? ['tabular-nums'] : undefined,
  };

  return <Text {...rest} style={[base, style]} />;
}

/** 支持传 Token 名（推荐）或任意色值（特殊情况） */
function resolveColor(color: TextColor | string): string {
  const v = (colors as Record<string, string>)[color as string];
  return typeof v === 'string' ? v : color;
}

// ==========================================================================
// 语义化角色
// ==========================================================================

/**
 * 分区标题 / 卡片标题。
 *
 * 层级 2：`md`(15) + `semibold` + 主文字色。
 * 与正文**同字号、靠字重和颜色分层** —— 这是列表型界面的通行做法：
 * 字号拉开会让标题变成"另一个东西"，而同字号不同字重读起来是"同一条信息的主角"。
 */
export function SectionTitle({
  children,
  style,
  ...rest
}: AppTextProps): React.JSX.Element {
  return (
    <AppText
      size="md"
      weight="semibold"
      color="text"
      track="wide"
      style={[styles.sectionTitle, style]}
      {...rest}
    >
      {children}
    </AppText>
  );
}

/**
 * 仪表读数 —— **一屏只放一个**。
 *
 * 为什么必须成组件：读数需要四件事同时成立才像仪器 ——
 * 大字号（`metric` 40）+ 特粗（`heavy`）+ **等宽数字**（`tabular-nums`）+
 * 负字距（`tight`，40px 上不收紧会"漏风"）。
 * 之前这些散在各页，实测全仓只有 9 处加了 `tabular-nums`，
 * 于是数值每跳一次，整行宽度就抖一次。
 *
 * `tabular-nums` 的作用就在这：数字位宽固定后，读数变化时**布局不动**。
 */
export function Metric({
  children,
  color = 'primary',
  style,
  ...rest
}: AppTextProps): React.JSX.Element {
  return (
    <AppText
      size="metric"
      weight="heavy"
      color={color}
      track="tighter"
      style={[styles.metric, style]}
      {...rest}
    >
      {children}
    </AppText>
  );
}

/**
 * 小标签（全大写拉丁 / 极短中文）。
 *
 * `xs`(11) + `medium` + 次级色 + 正字距 —— 11px 下字与字会挤在一起，
 * 必须靠字距把它"撑成标签"。字重给 medium 而不是 semibold：
 * 11px + semibold 在 Android 的屏幕密度下会糊成一团实心块。
 */
export function Label({
  children,
  color = 'textSecondary',
  style,
  ...rest
}: AppTextProps): React.JSX.Element {
  return (
    <AppText size="xs" weight="medium" color={color} track="wider" style={style} {...rest}>
      {children}
    </AppText>
  );
}

const styles = StyleSheet.create({
  sectionTitle: { marginBottom: 8 },
  /** 读数本身已靠 `lineHeight.metric` 定行高，这里只补上下留白 */
  metric: { fontVariant: ['tabular-nums'] },
});

export const textStyles = styles;
