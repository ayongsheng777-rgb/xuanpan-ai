/**
 * 底部导航 —— 固定 5 栏，顺序不可调换（基线规范 §1，裁定 1「方案 A」）。
 *
 *   罗盘 ｜ 命盘 ｜ 占测 ｜ 历史 ｜ 我的
 *
 * 图标用 `@expo/vector-icons` 的 Ionicons（随 Expo 内置，无需额外字体文件）。
 * 激活色用主色（深蓝），未激活用 muted —— 不用朱红：朱红在本产品里
 * 承载"印章/焦点"语义（见 Token 注释），做成导航选中色会削弱它的表意。
 */

import { Ionicons } from '@expo/vector-icons';
import { Tabs } from 'expo-router';
import React from 'react';
import { StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, font, layout, space } from '@/theme/tokens';

type IconName = keyof typeof Ionicons.glyphMap;

function tabIcon(focused: IconName, unfocused: IconName) {
  return function TabIcon({
    focused: isFocused,
    color,
    size,
  }: {
    focused: boolean;
    color: string;
    size: number;
  }): React.JSX.Element {
    return <Ionicons name={isFocused ? focused : unfocused} size={size} color={color} />;
  };
}

export default function TabsLayout(): React.JSX.Element {
  const insets = useSafeAreaInsets();

  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerShadowVisible: false,
        headerTintColor: colors.primary,
        headerTitleStyle: { fontSize: font.size.lg, fontWeight: font.weight.semibold as '600' },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          height: layout.tabBarHeight + insets.bottom,
          paddingBottom: insets.bottom,
          paddingTop: space[1],
        },
        tabBarLabelStyle: { fontSize: font.size.xs, fontWeight: font.weight.medium as '500' },
        sceneStyle: { backgroundColor: colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: '罗盘',
          headerShown: false,
          tabBarIcon: tabIcon('compass', 'compass-outline'),
        }}
      />
      <Tabs.Screen
        name="chart"
        options={{
          title: '命盘',
          headerTitle: '命盘',
          tabBarIcon: tabIcon('planet', 'planet-outline'),
        }}
      />
      <Tabs.Screen
        name="divine"
        options={{
          title: '占测',
          headerTitle: '占测',
          tabBarIcon: tabIcon('sparkles', 'sparkles-outline'),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: '历史',
          headerTitle: '历史',
          tabBarIcon: tabIcon('time', 'time-outline'),
        }}
      />
      <Tabs.Screen
        name="mine"
        options={{
          title: '我的',
          headerTitle: '我的',
          tabBarIcon: tabIcon('person', 'person-outline'),
        }}
      />
    </Tabs>
  );
}

export const styles = StyleSheet.create({
  // 供其它页面复用的标题样式
  screenTitle: { color: colors.primary, fontSize: font.size.lg },
});
