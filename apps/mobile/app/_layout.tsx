/**
 * 根布局。
 *
 * 与"在 App.tsx 里堆 Provider"相比，这里只做两件事：
 * 安全区上下文 + 路由栈。业务状态一律走各页面的 `useAsync`，
 * 不放全局 store —— 会话数据在服务端，客户端不需要缓存真相。
 */

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as Font from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { initBaseUrl } from '@/api/client';
import { helpHeaderRight } from '@/components/HelpButton';
import { colors, font } from '@/theme/tokens';

export default function RootLayout(): React.JSX.Element {
  // 启动时确定后端地址：优先用用户手设的（已持久化），没有才自动探活选线。
  //
  // 为什么放在根布局而不是各页面：候选表来自构建期注入，与具体页面无关；
  // 而越早定下来，用户点进任意页面时地址就已经是对的了。
  //
  // 刻意不 await、也不处理"全都不通"：启动期连不上是常态（后端没起、
  // 手机不在同一网段），把它变成红屏会让用户连「我的 → 网络线路」
  // 这个手改入口都进不去。失败时保持原地址，后续请求自然报错并给指引。
  React.useEffect(() => {
    void initBaseUrl();
  }, []);

  // 显式预加载 Ionicons 字体（2026-10-08 用户反馈：分析/传感器页图标空白）。
  // @expo/vector-icons 在 EAS 生产构建中有时字体就绪滞后，图标先空白。
  // 这里主动加载一次，不阻塞渲染；失败也不抛错，最坏与之前一致。
  React.useEffect(() => {
    void Font.loadAsync({ ...Ionicons.font }).catch(() => undefined);
  }, []);

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
          name="sanshi"
          options={{ title: '三式排盘', headerRight: helpHeaderRight('sanshi') }}
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
