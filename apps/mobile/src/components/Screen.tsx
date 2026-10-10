/**
 * 页面骨架 —— 安全区 + 统一底色 + 横向留白 + **单屏分区**。
 *
 * ## 🔴 2026-10-09 用户要求：每个界面必须一屏显示完，不需要滑动浏览
 *
 * 所以本组件**不再提供 `scroll` 开关**。原来的 `scroll` 是"页面自己选"，
 * 结果是 21 个路由页里有 18 个带页面级滚动容器（17 个走本组件的 `scroll`，
 * 1 个 `history.tsx` 用 `FlatList`）、只有 3 个没有 —— 同一个 App 里两种浏览
 * 方式并存，用户永远不知道这一页要不要往下拉。把它删掉，比留着再写一条守卫
 * 更彻底：**结构上不可能滚**，就不需要靠测试去提醒谁别滚。
 *
 * 那长内容怎么办？三条出路（都在本目录内）：
 *   1. 压缩 —— 长说明收进 `InfoPopup` / `HelpButton`（点开看，不占版面）；
 *   2. 折叠 —— 列表用 `FoldList`（前 N 条 + 「更多」浮层）；
 *   3. 分段 —— 多标签内容用 `SegmentedTabs` 切换（同一时刻只占一份空间）。
 *
 * 三条都做不到的内容，说明这一页承担的职责太多了，应当拆页 —— 而不是滚动。
 *
 * 顺带说明：下拉刷新也随之取消（没有滚动就没有下拉手势）。
 * 需要刷新的页面在 `PageHeader` 右侧挂一个刷新按钮，位置固定、更好找。
 */

import React, { type ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, fit, layout, space } from '@/theme/tokens';

export interface ScreenProps {
  children: ReactNode;
  /** 是否应用横向留白（全宽图表类页面可关掉） */
  padded?: boolean;
  /** 底部额外留白（如页面底部有固定按钮条） */
  bottomInsetExtra?: number;
  style?: StyleProp<ViewStyle>;
  contentStyle?: StyleProp<ViewStyle>;
}

export function Screen({
  children,
  padded = true,
  bottomInsetExtra = 0,
  style,
  contentStyle,
}: ScreenProps): React.JSX.Element {
  const insets = useSafeAreaInsets();
  const pad = padded ? { paddingHorizontal: layout.gutter } : null;

  return (
    <View style={[styles.root, style]}>
      <View
        style={[
          styles.flex,
          pad,
          { paddingTop: space[3], paddingBottom: insets.bottom + bottomInsetExtra },
          contentStyle,
        ]}
      >
        {children}
      </View>
    </View>
  );
}

// ==========================================================================
// 单屏分区
// ==========================================================================

/**
 * 分区容器 —— 把剩余高度按权重分给若干 `FitSlot`。
 *
 * 权重写在 `fit` 里（header 0.1 / core 0.52 / panel 0.26 / foot 0.12），
 * 页面不要自己发明比例 —— 每个页面各写一套，一屏节奏就散了。
 */
export function FitSlots({
  children,
  style,
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  return <View style={[styles.flex, style]}>{children}</View>;
}

export interface FitSlotProps {
  /** 相对权重，取 `fit` 里的档位；省略则按内容自适应（flexGrow 0） */
  weight?: number;
  /** 最小高度（px）—— 内容有硬下限时给，避免被压扁到不可读 */
  minHeight?: number;
  /** 内容是否垂直居中 */
  center?: boolean;
  style?: StyleProp<ViewStyle>;
  children: ReactNode;
}

/**
 * 单屏分区 —— 高度按权重弹性伸缩，**不产生滚动**。
 *
 * ⚠️ 子内容若比分配到的空间高，会被裁掉（`overflow: hidden`）。
 *    这是刻意的：宁可让人一眼看出"这里放不下、要换 FoldList / 收进弹层"，
 *    也不要悄悄溢出成一条谁也发现不了的滚动条。
 */
export function FitSlot({
  weight,
  minHeight,
  center,
  style,
  children,
}: FitSlotProps): React.JSX.Element {
  return (
    <View
      style={[
        weight !== undefined ? { flex: weight } : styles.auto,
        minHeight !== undefined ? { minHeight } : null,
        center ? styles.center : null,
        styles.clip,
        style,
      ]}
    >
      {children}
    </View>
  );
}

/** 段间距 —— 分区之间统一给 8，页面不要各写各的 */
export const fitGap = space[2];

/** 居中容器：平板/横屏时避免内容拉得过宽 */
export function Centered({ children }: { children: ReactNode }): React.JSX.Element {
  return <View style={styles.centered}>{children}</View>;
}

export { fit };

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1, gap: fitGap },
  auto: { flexGrow: 0, flexShrink: 1, flexBasis: 'auto' },
  center: { justifyContent: 'center' },
  clip: { overflow: 'hidden' },
  centered: { width: '100%', maxWidth: layout.maxContentWidth, alignSelf: 'center' },
});
