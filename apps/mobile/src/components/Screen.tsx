/** 页面骨架：安全区 + 统一底色 + 横向留白 + 可选滚动。 */

import React, { type ReactNode } from 'react';
import {
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, layout, space } from '@/theme/tokens';

export interface ScreenProps {
  children: ReactNode;
  /** 是否可滚动。表单页/长列表用 true */
  scroll?: boolean;
  /** 是否应用横向留白（全宽图表类页面可关掉） */
  padded?: boolean;
  /** 底部额外留白（如页面底部有固定按钮条） */
  bottomInsetExtra?: number;
  /** 下拉刷新回弹时是否显示转圈 */
  refreshing?: boolean;
  /** 提供即启用下拉刷新（仅 `scroll` 时有效） */
  onRefresh?: () => void;
  style?: StyleProp<ViewStyle>;
  contentStyle?: StyleProp<ViewStyle>;
}

export function Screen({
  children,
  scroll = false,
  padded = true,
  bottomInsetExtra = 0,
  refreshing = false,
  onRefresh,
  style,
  contentStyle,
}: ScreenProps): React.JSX.Element {
  const insets = useSafeAreaInsets();
  const pad = padded ? { paddingHorizontal: layout.gutter } : null;

  if (scroll) {
    return (
      <View style={[styles.root, style]}>
        <ScrollView
          style={styles.flex}
          contentContainerStyle={[
            pad,
            { paddingTop: space[4], paddingBottom: insets.bottom + space[6] + bottomInsetExtra },
            contentStyle,
          ]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          refreshControl={
            onRefresh ? (
              <RefreshControl
                refreshing={refreshing}
                onRefresh={onRefresh}
                tintColor={colors.primary}
                colors={[colors.primary]}
              />
            ) : undefined
          }
        >
          {children}
        </ScrollView>
      </View>
    );
  }

  return (
    <View style={[styles.root, pad, style]}>
      <View style={[styles.flex, contentStyle]}>{children}</View>
    </View>
  );
}

/** 居中容器：平板/横屏时避免内容拉得过宽 */
export function Centered({ children }: { children: ReactNode }): React.JSX.Element {
  return <View style={styles.centered}>{children}</View>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  flex: { flex: 1 },
  centered: { width: '100%', maxWidth: layout.maxContentWidth, alignSelf: 'center' },
});
