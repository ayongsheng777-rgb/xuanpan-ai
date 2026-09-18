/**
 * 按压反馈 —— **全 App 唯一的实现**。
 *
 * ## 为什么必须只有一份
 *
 * 改之前全仓有三种写法并存：
 *
 * | 位置 | 原来的反馈 |
 * |---|---|
 * | `Button` | `opacity 0.86` |
 * | 首页「去测盘」 | 底色换成 `surfaceAlt` |
 * | 首页「已保存 N 个盘面」 | **完全没有** |
 * | `Chip` | `opacity 0.7` |
 * | `SegmentedTabs` | **完全没有** |
 *
 * 同一个手势在不同地方给出不同回应，用户读到的不是"风格差异"，
 * 而是"有的地方坏了、有的地方迟钝"——这种不一致最终会被归因成"这个 App 很粗糙"，
 * 而它不会在任何一个测试里失败。
 *
 * ## 为什么是 scale
 *
 * 缩放会把**文字和图标一起带走**，读起来是"整块被按下去"；
 * 只改底色的话图标纹丝不动，看着像背景闪了一下。
 *
 * ## 为什么用 core `Animated` 而不是 Reanimated
 *
 * 项目**没有装 `react-native-reanimated`**（见 `apps/mobile/package.json`），
 * 引它要动 babel 配置 + 新架构开关，成本远超收益（按 AGENTS.md：引新依赖须先说明成本）。
 * `transform` 走 `useNativeDriver` 已经跑在原生线程上，对这个 120ms 的反馈足够。
 * 真要换成弹簧物理时，只需要改这一个文件。
 *
 * 🔴 `useNativeDriver` 在 web 上不存在 —— 不判断平台的话，每次按压都会打一条
 *    RN Web 的告警，污染离线渲染探针的 console 采集（`errors=[]` 会不再为真）。
 */

import React from 'react';
import { Animated, Platform } from 'react-native';

import { interaction } from '@/theme/tokens';

export interface PressScale {
  /** 交给 `Animated.View` 的 `transform: [{ scale }]` */
  scale: Animated.Value;
  onPressIn: () => void;
  onPressOut: () => void;
}

export function usePressScale(): PressScale {
  const scale = React.useRef(new Animated.Value(1)).current;

  const to = React.useCallback(
    (value: number) => {
      Animated.timing(scale, {
        toValue: value,
        duration: interaction.pressDuration,
        useNativeDriver: Platform.OS !== 'web',
      }).start();
    },
    [scale],
  );

  return {
    scale,
    onPressIn: React.useCallback(() => to(interaction.pressedScale), [to]),
    onPressOut: React.useCallback(() => to(1), [to]),
  };
}
