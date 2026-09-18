/**
 * 分段控件 —— 用于"拍摄识别 / 相册选择"双入口与报告的"三标签"。
 *
 * 为什么两处共用一个组件：它们在视觉上是同一种东西（互斥切换），
 * 若各写一套，会出现"扫描页的选中态是下划线、报告页是填充块"的观感割裂。
 * 这里用同一个填充块样式，语义差别只体现在 `variant`。
 *
 * 按压反馈与 `Button` / `Card` / `Chip` 共用 `usePressScale` ——
 * 这里原来**一点反馈都没有**，点下去像点在静态文字上。
 */

import React from 'react';
import { Animated, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { alpha, colors, elevation, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';
import { usePressScale } from './usePressScale';

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
        {items.map((it) => (
          <SegmentedItem
            key={it.key}
            item={it}
            active={it.key === value}
            variant="underline"
            onPress={() => onChange(it.key)}
          />
        ))}
      </ScrollView>
    );
  }

  return (
    <View style={styles.fillTrack}>
      {items.map((it) => (
        <SegmentedItem
          key={it.key}
          item={it}
          active={it.key === value}
          variant="fill"
          onPress={() => onChange(it.key)}
        />
      ))}
    </View>
  );
}

/**
 * 单项 —— 拆成组件而不是在 `map` 里内联，因为 `usePressScale` 是 Hook，
 * 在循环里调用会破坏 Hook 顺序（React 会直接抛错，但只在切换标签时才炸）。
 */
function SegmentedItem<T extends string>({
  item,
  active,
  variant,
  onPress,
}: {
  item: SegmentedTabItem<T>;
  active: boolean;
  variant: 'fill' | 'underline';
  onPress: () => void;
}): React.JSX.Element {
  const press = usePressScale();

  return (
    <Pressable
      onPress={onPress}
      onPressIn={press.onPressIn}
      onPressOut={press.onPressOut}
      accessibilityRole="tab"
      accessibilityState={{ selected: active }}
      pressRetentionOffset={10}
      style={variant === 'fill' ? styles.fillPress : undefined}
    >
      <Animated.View
        style={[
          variant === 'fill' ? styles.fillItem : styles.underlineItem,
          active && (variant === 'fill' ? styles.fillItemActive : styles.underlineItemActive),
          { transform: [{ scale: press.scale }] },
        ]}
      >
        <AppText
          size="md"
          weight={active ? 'semibold' : 'regular'}
          color={active ? 'primary' : 'textSecondary'}
        >
          {item.label}
        </AppText>
        {item.badge ? (
          <View style={styles.badge}>
            <AppText size="xs" color="onPrimary">
              {item.badge}
            </AppText>
          </View>
        ) : null}
      </Animated.View>
    </Pressable>
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
  fillPress: { flex: 1 },
  fillItem: {
    flex: 1,
    paddingVertical: space[2] + 1,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  /**
   * 选中块加一层浅投影 —— 让它"从轨道里浮起来"。
   * 原来只有描边，选中块与轨道是同一平面，切换时视觉上"只是换了个浅色方块"。
   */
  fillItemActive: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: alpha.primaryBorder,
    ...elevation.pressed,
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
