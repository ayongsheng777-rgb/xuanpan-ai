/**
 * 底部导航 —— 固定 5 栏，顺序不可调换。
 *
 *   罗盘 ｜ 测盘 ｜ 分析 ｜ 历史 ｜ 我的
 *
 * 与初版（罗盘 / 命盘 / 占测 / 历史 / 我的）相比，把「命盘」「占测」并入了「分析」：
 * 底栏是给**高频动作**留的位置。测盘（拍盘 / 对盘 / 存盘）天天要做，
 * 而排盘是"想起来才做一次"的。四个低频谱术式摊在底栏，会把高频的测盘挤掉。
 * 术式入口一个都没少，只是搬进 `analysis.tsx` 这一层内页（见该文件注释）。
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

import { helpHeaderRight } from '@/components/HelpButton';
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
      {/* 测盘：深色域页面，标题栏由页面自己画（与 index 一致）。
          用 tab 的浅色标题栏压在一个深色页面上，会出现"浅色顶 + 深色身"的割裂。 */}
      <Tabs.Screen
        name="test"
        options={{
          title: '测盘',
          headerShown: false,
          /* `scan`（取景框）而不是原来的 `locate`（准星）——
             原图标与「罗盘」的 `compass` 都是"圆 + 十字"家族，5 栏里两栏长得像亲戚，
             扫一眼分不出哪个是哪个。取景框直指本页的真实动作（拍盘 / 导图）。 */
          tabBarIcon: tabIcon('scan', 'scan-outline'),
        }}
      />
      <Tabs.Screen
        name="analysis"
        options={{
          title: '分析',
          headerTitle: '分析',
          headerRight: helpHeaderRight('analysis'),
          /* `shapes`（多种形状）而不是 `sparkles`（✨）——
             星芒在 2026 年已经是"这是 AI 生成的内容"的通用符号，
             而本 tab 装的是六爻 / 八字 / 三式等**确定性术式**，不是生成式内容。
             用星芒既误导（用户会以为是 AI 现编的），又削弱了"计算层是真源"这个核心承诺。 */
          tabBarIcon: tabIcon('shapes', 'shapes-outline'),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: '历史',
          headerTitle: '历史',
          headerRight: helpHeaderRight('history'),
          tabBarIcon: tabIcon('time', 'time-outline'),
        }}
      />
      <Tabs.Screen
        name="mine"
        options={{
          title: '我的',
          headerTitle: '我的',
          headerRight: helpHeaderRight('mine'),
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
