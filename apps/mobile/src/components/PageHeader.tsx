/**
 * 页面统一标题栏 —— 标题 + **显眼的返回入口** + 右侧动作。
 *
 * ## 为什么要统一（而不是各页自己画）
 *
 * 2026-10-09 用户要求「所有功能都可以进入退出」。在此之前全仓的状态是：
 *   · 底栏 5 页把标题栏关掉（`headerShown: false`）自己画，7 个页面各画各的；
 *   · 二级页靠**原生标题栏左上角那个小箭头**返回，用户实测反馈"不能返回"（BUG 3）；
 *   · `sensors.tsx` 单独补了一个「返回测盘」按钮，其它 15 个二级页没有。
 *
 * 于是同一个动作在 22 个页面里有三种形态，其中一种用户根本找不到。
 * 这里把它收成一个组件：**带文字的返回按钮**（不是只有一个箭头），
 * 固定在最左侧、固定尺寸、固定文案（可覆盖为"返回测盘"这类更明确的目标名）。
 *
 * ## 为什么刷新按钮在这里
 *
 * 单屏页没有滚动，也就没有下拉刷新（见 `Screen.tsx` 注释）。原来靠下拉刷新的
 * 页面（首页 / 我的 / 报告 / 会话）必须有替代入口，统一挂到标题栏右侧 ——
 * 位置固定、带转圈反馈，比"往下拉"更好发现。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { type ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { HelpButton } from '@/components/HelpButton';
import { HudRule } from '@/components/Hud';
import type { HelpTopicId } from '@/content/help';
import { colors, font, instrument, interaction, radius, space, tracking } from '@/theme/tokens';

import { AppText } from './AppText';

/** 色域 —— 罗盘系（浅金仪器）用 `instrument`，阅读型页面用品牌浅色 */
export type HeaderTone = 'instrument' | 'light';

export interface PageHeaderProps {
  title: string;
  /** 一行副标题（可选）。超过一行会被截断 —— 它只是定位，不是内容 */
  subtitle?: string;
  /** 是否显示返回按钮。二级页必须为 true（守卫会查） */
  back?: boolean;
  /** 返回按钮文案，默认「返回」。更明确的目标名更好，如「返回测盘」 */
  backLabel?: string;
  /** 讲解主题 —— 有值才渲染右上角问号 */
  helpTopic?: HelpTopicId;
  /** 刷新回调 —— 单屏页没有下拉刷新，刷新入口挂这里 */
  onRefresh?: () => void;
  refreshing?: boolean;
  /** 右侧额外动作（如"全部"、"清空"） */
  action?: ReactNode;
  tone?: HeaderTone;
  /** 是否显示底部刻度分隔线（默认显示，HUD 质感的一部分） */
  rule?: boolean;
}

export function PageHeader({
  title,
  subtitle,
  back = false,
  backLabel = '返回',
  helpTopic,
  onRefresh,
  refreshing = false,
  action,
  tone = 'instrument',
  rule = true,
}: PageHeaderProps): React.JSX.Element {
  const router = useRouter();
  const c = TONE[tone];

  return (
    <View>
      <View style={styles.row}>
        {/* ---------- 返回（带文字，不只是一个箭头） ---------- */}
        {back ? (
          <Pressable
            onPress={() => router.back()}
            accessibilityRole="button"
            accessibilityLabel={backLabel}
            hitSlop={8}
            style={({ pressed }) => [
              styles.back,
              { backgroundColor: c.chip, borderColor: c.border },
              pressed && styles.pressed,
            ]}
          >
            <Ionicons name="chevron-back" size={16} color={c.accent} />
            <AppText size="sm" weight="semibold" color={c.accent} style={styles.backLabel}>
              {backLabel}
            </AppText>
          </Pressable>
        ) : null}

        {/* ---------- 标题 ---------- */}
        <View style={styles.titleWrap}>
          <AppText size="xl" weight="bold" color={c.text} track="tight" numberOfLines={1}>
            {title}
          </AppText>
          {subtitle ? (
            <AppText size="xs" color={c.textSecondary} numberOfLines={1} style={styles.subtitle}>
              {subtitle}
            </AppText>
          ) : null}
        </View>

        {/* ---------- 右侧动作 ---------- */}
        <View style={styles.actions}>
          {action}
          {onRefresh ? (
            <Pressable
              onPress={onRefresh}
              accessibilityRole="button"
              accessibilityLabel="刷新"
              hitSlop={10}
              style={({ pressed }) => [
                styles.iconBtn,
                { backgroundColor: c.chip },
                pressed && styles.pressed,
              ]}
            >
              {refreshing ? (
                <ActivityIndicator size="small" color={c.accent} />
              ) : (
                <Ionicons name="refresh" size={18} color={c.accent} />
              )}
            </Pressable>
          ) : null}
          {helpTopic ? <HelpButton topic={helpTopic} color={c.accent} /> : null}
        </View>
      </View>

      {rule ? <HudRule color={c.border} style={styles.rule} /> : null}
    </View>
  );
}

const TONE = {
  instrument: {
    text: instrument.text,
    textSecondary: instrument.textSecondary,
    accent: instrument.accent,
    chip: instrument.surfaceAlt,
    border: instrument.border,
  },
  light: {
    text: colors.text,
    textSecondary: colors.textSecondary,
    accent: colors.primary,
    chip: colors.surfaceAlt,
    border: colors.border,
  },
} as const;

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 40,
    gap: space[2],
  },
  back: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingLeft: space[1],
    paddingRight: space[3],
    /* 触达边长兜底：视觉可以小，手指要够得着 */
    minHeight: interaction.minTouchTarget - 8,
    paddingVertical: space[1],
  },
  backLabel: { marginLeft: 2 },
  pressed: { opacity: 0.6 },
  titleWrap: { flex: 1, justifyContent: 'center' },
  subtitle: { marginTop: 1 },
  actions: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  rule: { marginTop: space[2] },
});

export const headerTitleStyle = {
  fontSize: font.size.xl,
  letterSpacing: tracking.tight,
} as const;
