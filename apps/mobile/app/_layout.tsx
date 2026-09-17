/**
 * 根布局。
 *
 * 与"在 App.tsx 里堆 Provider"相比，这里只做两件事：
 * 安全区上下文 + 路由栈。业务状态一律走各页面的 `useAsync`，
 * 不放全局 store —— 会话数据在服务端，客户端不需要缓存真相。
 */

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { helpHeaderRight } from '@/components/HelpButton';
import { colors, font } from '@/theme/tokens';

export default function RootLayout(): React.JSX.Element {
  return (
    <SafeAreaProvider>
      {/* 底色为米调，状态栏用深色字（light 主题） */}
      <StatusBar style="dark" backgroundColor={colors.bg} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerShadowVisible: false,
          headerTintColor: colors.primary,
          headerTitleStyle: { fontSize: font.size.lg, fontWeight: font.weight.semibold as '600' },
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="scan" options={{ title: '罗盘识向', headerRight: helpHeaderRight('scan') }} />
        <Stack.Screen
          name="almanac"
          options={{ title: '黄历择日', headerRight: helpHeaderRight('almanac') }}
        />
        <Stack.Screen
          name="confirm/[sessionId]"
          options={{ title: '确认坐向', headerRight: helpHeaderRight('confirm') }}
        />
        <Stack.Screen
          name="report/[sessionId]"
          options={{ title: 'AI 解读报告', headerRight: helpHeaderRight('report') }}
        />
        <Stack.Screen
          name="session/[sessionId]"
          options={{ title: '会话详情', headerRight: helpHeaderRight('session') }}
        />
      </Stack>
    </SafeAreaProvider>
  );
}
