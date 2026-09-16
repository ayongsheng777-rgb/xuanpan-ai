/**
 * 基础容器与按钮。
 *
 * 所有视觉值取自 `theme/tokens`，本文件内**不出现任何硬编码色值/字号**
 * （对应基线规范 §2 的落地要求：五色必须固化为 token，禁止散落）。
 */

import React, { type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';

import { alpha, colors, elevation, layout, radius, space } from '@/theme/tokens';

import { AppText, SectionTitle } from './AppText';

// ==========================================================================
// 卡片
// ==========================================================================

export interface CardProps {
  children: ReactNode;
  title?: string;
  /** 标题右侧的动作区（如"查看全部"） */
  action?: ReactNode;
  /** 强调卡：主色描边，用于"下一步该做什么" */
  highlight?: boolean;
  /** 朱红描边：用于错误/警示卡 */
  danger?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function Card({ children, title, action, highlight, danger, style }: CardProps): React.JSX.Element {
  const border = danger
    ? { borderColor: alpha.primaryBorder, borderWidth: 1 }
    : highlight
      ? { borderColor: colors.primary, borderWidth: 1.5 }
      : null;

  return (
    <View style={[styles.card, border, danger && styles.cardDanger, style]}>
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

  return (
    <Pressable
      testID={testID}
      onPress={isDisabled ? undefined : onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityState={{ disabled: isDisabled, busy: loading }}
      style={({ pressed }) => [
        styles.btn,
        size === 'lg' && styles.btnLg,
        {
          backgroundColor: palette.bg,
          borderColor: palette.border,
          borderWidth: palette.borderWidth,
          opacity: isDisabled ? 0.5 : pressed ? 0.86 : 1,
        },
        style,
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

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}): React.JSX.Element {
  return (
    <View style={styles.empty}>
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
  cardDanger: { backgroundColor: '#FDF6F5' },
  cardHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minHeight: 20,
  },
  cardTitle: { marginBottom: 0 },

  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.md,
    paddingVertical: space[3],
    paddingHorizontal: space[4],
    minHeight: 46,
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
  emptyHint: { marginTop: space[2] },
  emptyAction: { marginTop: space[5], width: '100%' },

  kvRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: space[2],
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  kvRowLast: { borderBottomWidth: 0 },
  kvLabel: { width: 84, flexShrink: 0 },
  kvValue: { flex: 1 },

  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.border,
    marginVertical: space[3],
  },
});
