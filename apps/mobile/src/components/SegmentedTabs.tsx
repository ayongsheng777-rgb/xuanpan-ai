/**
 * 分段控件 —— 用于"拍摄识别 / 相册选择"双入口与报告的"三标签"。
 *
 * 为什么两处共用一个组件：它们在视觉上是同一种东西（互斥切换），
 * 若各写一套，会出现"扫描页的选中态是下划线、报告页是填充块"的观感割裂。
 * 这里用同一个填充块样式，语义差别只体现在 `variant`。
 */

import React from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { alpha, colors, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';

export interface SegmentedTabItem<T extends string> {
  key: T;
  label: string;
  /** 右上角小角标（如未读/数量） */
  badge?: string;
}

export interface SegmentedTabsProps<T extends string> {
  items: readonly SegmentedTabItem<T>[];
  value: T;
  onChange: (key: T) => void;
  /**
   * `fill` 各占等宽（如双入口）
   * `underline` 文字型，横向可滚动（如三标签，标签较长时）
   */
  variant?: 'fill' | 'underline';
  style?: StyleSheet.NamedStyles<unknown> | object;
}

export function SegmentedTabs<T extends string>({
  items,
  value,
  onChange,
  variant = 'fill',
}: SegmentedTabsProps<T>): React.JSX.Element {
  if (variant === 'underline') {
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.underlineRow}
      >
        {items.map((it) => {
          const active = it.key === value;
          return (
            <Pressable
              key={it.key}
              onPress={() => onChange(it.key)}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              style={[styles.underlineItem, active && styles.underlineItemActive]}
            >
              <AppText size="md" weight={active ? 'semibold' : 'regular'} color={active ? 'primary' : 'textSecondary'}>
                {it.label}
              </AppText>
            </Pressable>
          );
        })}
      </ScrollView>
    );
  }

  return (
    <View style={styles.fillTrack}>
      {items.map((it) => {
        const active = it.key === value;
        return (
          <Pressable
            key={it.key}
            onPress={() => onChange(it.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            style={[styles.fillItem, active && styles.fillItemActive]}
          >
            <AppText
              size="md"
              weight={active ? 'semibold' : 'regular'}
              color={active ? 'primary' : 'textSecondary'}
            >
              {it.label}
            </AppText>
            {it.badge ? (
              <View style={styles.badge}>
                <AppText size="xs" color="onPrimary">
                  {it.badge}
                </AppText>
              </View>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  fillTrack: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: 3,
    gap: 3,
  },
  fillItem: {
    flex: 1,
    paddingVertical: space[2] + 1,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  fillItemActive: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: alpha.primaryBorder,
  },
  badge: {
    marginLeft: space[1],
    backgroundColor: colors.cinnabar,
    borderRadius: radius.pill,
    paddingHorizontal: 5,
    paddingVertical: 1,
    minWidth: 16,
    alignItems: 'center',
  },

  underlineRow: { flexDirection: 'row', gap: space[5] },
  underlineItem: {
    paddingVertical: space[2],
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  underlineItemActive: { borderBottomColor: colors.primary },
});
