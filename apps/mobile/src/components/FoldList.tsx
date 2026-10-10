/**
 * 折叠列表 —— 「前 N 条 + 更多浮层」，让列表页也能一屏显示完。
 *
 * ## 为什么必须有它（而不是让列表页继续滚）
 *
 * 用户 2026-10-09 的要求是「每个界面保持全部显示在手机屏幕上，不需滑动浏览」，
 * 且明确选了**全部绝对一屏**（连历史/会话/报告也不许滚）。
 * 但列表长度由真实数据决定 —— 存了 50 个盘面就是 50 条，硬塞进一屏会挤成马赛克。
 *
 * 解法：页面本体只放**最近 N 条**（一屏放得下、看得清），
 * 其余收进「更多」浮层。这样：
 *   · 打开 App 第一眼永远是一屏，符合要求；
 *   · 数据一条不少，点一下就能看到全部；
 *   · 浮层是 `Modal`（覆盖层），不是页面滚动 —— 与"页面不滚"不冲突。
 *
 * ⚠️ `max` 不要各页自己拍。默认取 `fit.listPreviewMax`；
 *    页面若要覆盖，必须是因为"该页卡片明显更矮/更高"，并在注释里写清原因。
 */

import { Ionicons } from '@expo/vector-icons';
import React, { type ReactNode, useState } from 'react';
import { Pressable, StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import { AppText } from '@/components/AppText';
import { InfoPopup } from '@/components/InfoPopup';
import { colors, fit, instrument, radius, space } from '@/theme/tokens';

export interface FoldListProps<T> {
  items: readonly T[];
  /** 一屏可见条数，默认 `fit.listPreviewMax` */
  max?: number;
  /** 单条渲染。**同一个渲染函数**会被用在页内预览与浮层里，保证两处长得一样 */
  renderItem: (item: T, index: number) => ReactNode;
  keyOf: (item: T, index: number) => string;
  /** 「更多」浮层标题，如「全部记录」 */
  moreTitle: string;
  /** 浮层副标题，如「共 37 条」 */
  moreSubtitle?: string;
  /** 数据为空时显示的内容 */
  empty?: ReactNode;
  /** 页内条目之间的间距 */
  gap?: number;
  style?: StyleProp<ViewStyle>;
  /** 色域：与所在页面一致 */
  tone?: 'instrument' | 'light';
}

export function FoldList<T>({
  items,
  max = fit.listPreviewMax,
  renderItem,
  keyOf,
  moreTitle,
  moreSubtitle,
  empty,
  gap = space[2],
  style,
  tone = 'light',
}: FoldListProps<T>): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const preview = items.slice(0, max);
  const hidden = items.length - preview.length;

  if (items.length === 0 && empty) {
    return <View style={[styles.flex, style]}>{empty}</View>;
  }

  return (
    <View style={[styles.flex, style]}>
      <View style={{ gap }}>
        {preview.map((item, i) => (
          <View key={keyOf(item, i)}>{renderItem(item, i)}</View>
        ))}
      </View>

      {hidden > 0 ? (
        <MoreButton
          label={`更多 ${hidden} 条`}
          tone={tone}
          onPress={() => setOpen(true)}
          style={styles.more}
        />
      ) : null}

      <InfoPopup
        visible={open}
        onClose={() => setOpen(false)}
        title={moreTitle}
        subtitle={moreSubtitle ?? `共 ${items.length} 条`}
      >
        <View style={{ gap }}>
          {items.map((item, i) => (
            <View key={keyOf(item, i)}>{renderItem(item, i)}</View>
          ))}
        </View>
      </InfoPopup>
    </View>
  );
}

/** 单开一个组件是因为 `useState` 不能写在条件分支里 */
function MoreButton({
  label,
  tone,
  onPress,
  style,
}: {
  label: string;
  tone: 'instrument' | 'light';
  onPress: () => void;
  style?: StyleProp<ViewStyle>;
}): React.JSX.Element {
  const c = MORE_TONE[tone];
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${label}，展开查看全部`}
      style={({ pressed }) => [styles.moreBtn, { backgroundColor: c.bg }, pressed && styles.pressed, style]}
    >
      <AppText size="sm" weight="semibold" color={c.fg}>
        {label}
      </AppText>
      <Ionicons name="chevron-forward" size={14} color={c.fg} />
    </Pressable>
  );
}

const MORE_TONE = {
  instrument: { bg: instrument.surfaceAlt, fg: instrument.accent },
  light: { bg: colors.surfaceAlt, fg: colors.primary },
} as const;

const styles = StyleSheet.create({
  flex: { flexGrow: 0, flexShrink: 1 },
  more: { marginTop: space[2] },
  moreBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space[1],
    borderRadius: radius.pill,
    paddingVertical: space[2],
  },
  pressed: { opacity: 0.6 },
});
