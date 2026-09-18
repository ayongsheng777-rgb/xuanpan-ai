/**
 * 基础容器与按钮。
 *
 * 所有视觉值取自 `theme/tokens`，本文件内**不出现任何硬编码色值/字号**
 * （对应基线规范 §2 的落地要求：五色必须固化为 token，禁止散落）。
 *
 * ## 三个表面原语，别再多造第四个
 *
 * | 原语 | 域 | 用途 |
 * |---|---|---|
 * | `Card` | 浅色（纸面） | 命盘 / 占测 / 历史 / 我的 等阅读型页面 |
 * | `Panel` | **深色（仪器）** | 首页 / 测盘 / 手动调节 / 传感器 / 校准 / 我的罗盘 |
 * | `PressableCard` | 浅色 | 整卡可点（进详情、跳转） |
 *
 * 🔴 **`Panel` 是补上来的** —— 原先只有浅色 `Card`，深色页用不了，于是 6 个深色页
 *    各自把「surface 底 + 1px 边框 + radius.lg + padding」抄了一遍（同一组样式重复 17 次）。
 *    散落的不是色值而是样式组合，所以 tsc、lint、任何测试**都不会报错** ——
 *    只有在改圆角/改边框色时才会发现"改了一页，另外五页没跟上"。
 */

import React, { type ReactNode } from 'react';
import {
  ActivityIndicator,
  Animated,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import {
  alpha,
  colors,
  elevation,
  instrument,
  interaction,
  layout,
  radius,
  space,
  tint,
} from '@/theme/tokens';

import { AppText, SectionTitle } from './AppText';
import { usePressScale } from './usePressScale';

// ==========================================================================
// 卡片（浅色域）
// ==========================================================================

/**
 * 表面档位
 *
 * - `default` 静置卡片：白底 + 极淡投影，贴近纸面
 * - `quiet` 次级分区：**去掉投影和边框，只用底色差**。
 *   理由：一屏里若每块都是"白底 + 描边 + 阴影"，用户无法判断谁是主体；
 *   quiet 用来承载"同一条信息的下一层"（表单里的字段组、列表里的子项）。
 */
export type SurfaceVariant = 'default' | 'quiet';

export interface CardProps {
  children: ReactNode;
  title?: string;
  /** 标题右侧的动作区（如"查看全部"） */
  action?: ReactNode;
  /** 表面档位，见 `SurfaceVariant` */
  variant?: SurfaceVariant;
  /** 强调卡：主色描边，用于"下一步该做什么" */
  highlight?: boolean;
  /** 朱红描边：用于错误/警示卡 */
  danger?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function Card({
  children,
  title,
  action,
  variant = 'default',
  highlight,
  danger,
  style,
}: CardProps): React.JSX.Element {
  const border = danger
    ? { borderColor: alpha.primaryBorder, borderWidth: 1 }
    : highlight
      ? { borderColor: colors.primary, borderWidth: 1.5 }
      : null;

  return (
    <View
      style={[
        styles.card,
        variant === 'quiet' && styles.cardQuiet,
        border,
        danger && styles.cardDanger,
        style,
      ]}
    >
      {(title || action) && (
        <View style={styles.cardHead}>
          {title ? <SectionTitle style={styles.cardTitle}>{title}</SectionTitle> : <View />}
          {action}
        </View>
      )}
      {children}
    </View>
  );
}

/** 整卡可点 —— 与 `Card` 同视觉，但会给出按下反馈 */
export function PressableCard({
  children,
  onPress,
  accessibilityLabel,
  variant = 'default',
  style,
}: {
  children: ReactNode;
  onPress: () => void;
  accessibilityLabel?: string;
  variant?: SurfaceVariant;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  const press = usePressScale();
  return (
    <Pressable
      onPress={onPress}
      onPressIn={press.onPressIn}
      onPressOut={press.onPressOut}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      /* 手指滑出几像素不该取消用户明明想按的那一下 */
      pressRetentionOffset={12}
      style={style}
    >
      <Animated.View
        style={[
          styles.card,
          variant === 'quiet' && styles.cardQuiet,
          { transform: [{ scale: press.scale }] },
        ]}
      >
        {children}
      </Animated.View>
    </Pressable>
  );
}

// ==========================================================================
// 面板（深色仪器域）
// ==========================================================================

export type PanelTone = 'surface' | 'quiet' | 'ok' | 'warn' | 'danger';

export interface PanelProps {
  children: ReactNode;
  title?: string;
  action?: ReactNode;
  /** `quiet` 用于页内次级分区（输入槽、进度槽） */
  tone?: PanelTone;
  style?: StyleProp<ViewStyle>;
}

/**
 * 深色仪器域的卡片。**深色页一律用它，不要再手写那组样式。**
 *
 * 与 `Card` 的差别不只是颜色：仪器域**不用投影**（深底上的投影看不见，
 * 只会让边缘发脏），层级靠「底差 + 1px 描边」表达 —— 这是深色 UI 的通行做法，
 * 也是它当初没能复用 `Card` 的真正原因（不只是色值不同）。
 */
export function Panel({ children, title, action, tone = 'surface', style }: PanelProps): React.JSX.Element {
  const t = PANEL_TONE[tone];
  return (
    <View
      style={[
        styles.panel,
        { backgroundColor: t.bg, borderColor: t.border, borderWidth: t.borderWidth },
        style,
      ]}
    >
      {(title || action) && (
        <View style={styles.cardHead}>
          {title ? <SectionTitle style={[styles.cardTitle, styles.onDark]}>{title}</SectionTitle> : <View />}
          {action}
        </View>
      )}
      {children}
    </View>
  );
}

/** 整块可点 —— 首页「去测盘」「已保存 N 个盘面」原来两种反馈写法，现在统一 */
export function PressablePanel({
  children,
  onPress,
  accessibilityLabel,
  style,
  contentStyle,
}: {
  children: ReactNode;
  onPress: () => void;
  accessibilityLabel?: string;
  /** 外框定位（margin、宽度） */
  style?: StyleProp<ViewStyle>;
  /** 内面板布局（flexDirection、gap）—— 面板自身还有 padding 与圆角，别写在外框上 */
  contentStyle?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  const press = usePressScale();
  return (
    <Pressable
      onPress={onPress}
      onPressIn={press.onPressIn}
      onPressOut={press.onPressOut}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel}
      pressRetentionOffset={12}
      style={style}
    >
      <Animated.View
        style={[
          styles.panel,
          styles.panelInteractive,
          contentStyle,
          { transform: [{ scale: press.scale }] },
        ]}
      >
        {children}
      </Animated.View>
    </Pressable>
  );
}

const PANEL_TONE: Record<PanelTone, { bg: string; border: string; borderWidth: number }> = {
  surface: { bg: instrument.surface, border: instrument.border, borderWidth: 1 },
  quiet: { bg: instrument.surfaceAlt, border: instrument.border, borderWidth: 0 },
  /* 状态面板：描边用状态色本身，不用中性边框 —— 深底上中性边框看不出语义 */
  ok: { bg: instrument.surface, border: instrument.ok, borderWidth: 1 },
  warn: { bg: instrument.surface, border: instrument.warn, borderWidth: 1 },
  danger: { bg: instrument.surface, border: instrument.danger, borderWidth: 1 },
};

// ==========================================================================
// 按钮
// ==========================================================================

export interface ButtonProps {
  label: string;
  onPress?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'md' | 'lg';
  loading?: boolean;
  disabled?: boolean;
  /** 左侧图标/emoji */
  icon?: ReactNode;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  icon,
  style,
  testID,
}: ButtonProps): React.JSX.Element {
  const isDisabled = disabled || loading;
  const palette = PALETTE[variant];
  const press = usePressScale();

  return (
    <Pressable
      testID={testID}
      onPress={isDisabled ? undefined : onPress}
      onPressIn={isDisabled ? undefined : press.onPressIn}
      onPressOut={isDisabled ? undefined : press.onPressOut}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      pressRetentionOffset={12}
      style={style}
    >
      <Animated.View
        style={[
          styles.btn,
          size === 'lg' && styles.btnLg,
          {
            backgroundColor: palette.bg,
            borderColor: palette.border,
            borderWidth: palette.borderWidth,
            /* 按下时投影同时收紧 = 物理下沉；只有 scale 会像"整块缩了一下" */
            ...elevation[variant === 'primary' || variant === 'danger' ? 'card' : 'none'],
            transform: [{ scale: isDisabled ? 1 : press.scale }],
            opacity: isDisabled ? 0.5 : 1,
          },
        ]}
      >
        {loading ? (
          <ActivityIndicator color={palette.fg} size="small" />
        ) : (
          <>
            {icon}
            <AppText
              size={size === 'lg' ? 'lg' : 'md'}
              weight="semibold"
              color={palette.fg}
              style={icon ? styles.btnLabelWithIcon : undefined}
            >
              {label}
            </AppText>
          </>
        )}
      </Animated.View>
    </Pressable>
  );
}

const PALETTE = {
  primary: { bg: colors.primary, fg: colors.onPrimary, border: colors.primary, borderWidth: 0 },
  secondary: { bg: colors.surface, fg: colors.primary, border: colors.primary, borderWidth: 1.5 },
  ghost: { bg: 'transparent', fg: colors.primary, border: colors.border, borderWidth: 1 },
  danger: { bg: colors.cinnabar, fg: colors.onPrimary, border: colors.cinnabar, borderWidth: 0 },
} as const;

// ==========================================================================
// 空态
// ==========================================================================

/**
 * 空态 —— 「无数据」在木产品里是一等状态（见记忆里的同名规则）。
 *
 * 加 `icon` 的理由：只有两行灰字的空态与"渲染失败"在视觉上无法区分。
 * 一个图形锚点就能把"这里本来就该是空的"和"这里坏了"分开。
 * **但仍不得画会被误读的替代图形** —— 图标只表达"空"，不许暗示任何数值。
 */
export function EmptyState({
  title,
  hint,
  icon,
  action,
}: {
  title: string;
  hint?: string;
  icon?: ReactNode;
  action?: ReactNode;
}): React.JSX.Element {
  return (
    <View style={styles.empty}>
      {icon ? <View style={styles.emptyIcon}>{icon}</View> : null}
      <AppText size="md" weight="medium" color="textSecondary" center>
        {title}
      </AppText>
      {hint ? (
        <AppText size="sm" color="muted" center style={styles.emptyHint}>
          {hint}
        </AppText>
      ) : null}
      {action ? <View style={styles.emptyAction}>{action}</View> : null}
    </View>
  );
}

// ==========================================================================
// 键值行
// ==========================================================================

export function KeyValueRow({
  label,
  value,
  emphasized,
  last,
}: {
  label: string;
  value: ReactNode;
  emphasized?: boolean;
  last?: boolean;
}): React.JSX.Element {
  return (
    <View style={[styles.kvRow, last && styles.kvRowLast]}>
      <AppText size="sm" color="textSecondary" style={styles.kvLabel}>
        {label}
      </AppText>
      <View style={styles.kvValue}>
        {typeof value === 'string' || typeof value === 'number' ? (
          <AppText
            size={emphasized ? 'lg' : 'md'}
            weight={emphasized ? 'semibold' : 'regular'}
            color={emphasized ? 'primary' : 'text'}
          >
            {String(value)}
          </AppText>
        ) : (
          value
        )}
      </View>
    </View>
  );
}

/** 分割线 */
export function Divider({ style }: { style?: StyleProp<ViewStyle> }): React.JSX.Element {
  return <View style={[styles.divider, style]} />;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: space[4],
    marginBottom: space[3],
    ...elevation.card,
  },
  /** 次级分区：无投影、无边框，只用底色差 —— 见 `SurfaceVariant` 注释 */
  cardQuiet: {
    backgroundColor: colors.surfaceAlt,
    ...elevation.none,
  },
  cardDanger: { backgroundColor: tint.dangerCard },
  cardHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 22,
  },
  cardTitle: { marginBottom: 0 },
  onDark: { color: instrument.text },

  panel: {
    borderRadius: radius.lg,
    padding: space[3],
    marginBottom: space[3],
  },
  panelInteractive: {
    backgroundColor: instrument.surface,
    borderColor: instrument.border,
    borderWidth: 1,
  },

  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    paddingVertical: space[3],
    paddingHorizontal: space[4],
    /* 44 是 iOS 最小触达边长；Android 要 48dp，主按钮本来就更高，副按钮靠这里兜底 */
    minHeight: interaction.minTouchTarget,
  },
  btnLg: { minHeight: 54, borderRadius: radius.lg },
  btnLabelWithIcon: { marginLeft: space[2] },

  empty: {
    paddingVertical: space[10],
    paddingHorizontal: space[4],
    alignItems: 'center',
    width: '100%',
    maxWidth: layout.maxContentWidth,
    alignSelf: 'center',
  },
  emptyIcon: { marginBottom: space[4], opacity: 0.5 },
  emptyHint: { marginTop: space[2] },
  emptyAction: { marginTop: space[5], width: '100%' },

  kvRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: space[2] + 1,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  kvRowLast: { borderBottomWidth: 0 },
  /** 84px 是按最长的两字标签 + 4 字标签（"出生地经度"）定的，改标签文案前先看这里 */
  kvLabel: { width: 84, flexShrink: 0 },
  kvValue: { flex: 1 },

  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
    marginVertical: space[3],
  },
});
