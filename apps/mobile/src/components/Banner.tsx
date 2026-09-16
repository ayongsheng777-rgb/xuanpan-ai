/**
 * 提示条 —— 承载三类信息，**语义不同、颜色不同、措辞要求也不同**。
 *
 * | 类型 | 用途 | 措辞要求 |
 * |---|---|---|
 * | `info` | 使用说明、口径说明 | 平述 |
 * | `warning` | 不确定性（识别可疑、流派差异、未确认） | **必须说清"哪一步不确定、影响什么"** |
 * | `error` | 失败与阻断原因 | **必须给出可执行的下一步** |
 *
 * 为什么单独抽组件并强制标题：后端返回的 `uncertain_regions` / `warnings`
 * 往往是一句完整的中文，若直接用裸 Text 渲染，会与正文混在一起被略过。
 * 不确定性必须**看起来像不确定性**，否则等于没告知。
 */

import React, { type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { colors, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';

export type BannerTone = 'info' | 'warning' | 'error' | 'success';

export interface BannerProps {
  tone?: BannerTone;
  title?: string;
  children: ReactNode;
  style?: object;
}

const TONE: Record<BannerTone, { bg: string; border: string; fg: string; icon: string }> = {
  info: { bg: '#F1F5F8', border: '#C9D6DE', fg: colors.info, icon: 'ⓘ' },
  warning: { bg: '#FDF7EC', border: '#E8D5AC', fg: colors.warning, icon: '⚠' },
  error: { bg: '#FDF4F3', border: '#EFC9C5', fg: colors.danger, icon: '✕' },
  success: { bg: '#F2F7F5', border: '#C6DCD5', fg: colors.success, icon: '✓' },
};

export function Banner({ tone = 'info', title, children, style }: BannerProps): React.JSX.Element {
  const t = TONE[tone];
  return (
    <View style={[styles.wrap, { backgroundColor: t.bg, borderColor: t.border }, style]}>
      <View style={styles.head}>
        <AppText size="sm" color={t.fg} weight="semibold">
          {t.icon}
        </AppText>
        {title ? (
          <AppText size="sm" weight="semibold" color={t.fg} style={styles.title}>
            {title}
          </AppText>
        ) : null}
      </View>
      <View style={styles.body}>
        {typeof children === 'string' ? (
          <AppText size="sm" color="text" lineHeightRatio={1.15}>
            {children}
          </AppText>
        ) : (
          children
        )}
      </View>
    </View>
  );
}

/**
 * 不确定性清单 —— 报告与确认页**必须**原样展示的一项。
 *
 * 后端把这批文案当作"系统保证"写入报告，模型改不了（见 `xuanpan_ai/report.py`）。
 * 前端也不得改写或折叠隐藏：这是用户判断结论可靠性的唯一依据。
 */
export function UncertaintyList({ items }: { items: readonly string[] }): React.JSX.Element | null {
  if (items.length === 0) return null;
  return (
    <Banner tone="warning" title={`不确定性说明（${items.length} 条）`}>
      <View style={styles.list}>
        {items.map((u, i) => (
          <View key={`${i}-${u.slice(0, 8)}`} style={styles.listItem}>
            <AppText size="sm" color="warning" style={styles.bullet}>
              ·
            </AppText>
            <AppText size="sm" color="text" lineHeightRatio={1.15} style={styles.listText}>
              {u}
            </AppText>
          </View>
        ))}
      </View>
    </Banner>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: radius.md,
    borderWidth: 1,
    padding: space[3],
    marginBottom: space[3],
  },
  head: { flexDirection: 'row', alignItems: 'center', marginBottom: space[1] },
  title: { marginLeft: space[2] },
  body: {},
  list: { gap: space[1] },
  listItem: { flexDirection: 'row', alignItems: 'flex-start' },
  bullet: { width: 10, lineHeight: 20 },
  listText: { flex: 1 },
});
