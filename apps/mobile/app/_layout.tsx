/**
 * 根布局。
 *
 * 与"在 App.tsx 里堆 Provider"相比，这里只做两件事：
 * 安全区上下文 + 路由栈。业务状态一律走各页面的 `useAsync`，
 * 不放全局 store —— 会话数据在服务端，客户端不需要缓存真相。
 *
 * ## 🔴 2026-10-09：全站 `headerShown: false`，标题栏由页面自画
 *
 * 原先只有 6 个页面在根栈里显式声明了标题（scan / almanac / sanshi /
 * confirm / report / session），其余 11 个二级页拿到的是**原生默认标题**——
 * 于是 `adjust` 页顶上是英文路由名 "adjust"，`calibrate` 页顶上是 "calibrate"。
 * 更糟的是返回入口：那 6 页有原生返回箭头，另外 11 页的箭头样式随平台变，
 * 用户实测反馈"不能返回"（BUG 3）。
 *
 * 现在统一：栈不画标题栏，每个页面用 `PageHeader` 画 ——
 * 标题是中文、返回按钮**带文字**、刷新与讲解位置固定。
 * 由 `tests/mobile/test_app_wiring.py` 的「出入口守卫」钉住：
 * 每个非 tab 路由页必须有 `PageHeader` 且带 `back`。
 */

import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import * as Font from 'expo-font';
import { Ionicons } from '@expo/vector-icons';
import React from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { initBaseUrl } from '@/api/client';
import { colors } from '@/theme/tokens';

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
          headerShown: false,
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="(tabs)" />
      </Stack>
    </SafeAreaProvider>
  );
}
