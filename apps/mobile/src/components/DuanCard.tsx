/**
 * 断卦结果 —— 六爻与八字**共用**的展示层。
 *
 * ## 为什么必须共用一个组件
 *
 * 两个术式的 `DuanResponse` 结构相同（verdict / reasons / school /
 * uncertainties / detail），若各画一套，迟早出现"六爻页显示依据、
 * 八字页只显示一个等级词"这种不一致 —— 而依据与流派标注是本产品
 * 能否被信任的关键，不能因页面而异。
 *
 * ## verdict 的语义差异（本组件存在的核心理由）
 *
 * | 术式 | verdict 取值 | 语义 |
 * |---|---|---|
 * | 六爻 | 偏吉 / 中平 / 偏凶 | **吉凶倾向** |
 * | 八字 | 身强 / 身弱 | **日主状态，与吉凶无关** |
 *
 * 所以着色必须**按语义分派**：只有吉凶倾向才用墨绿 / 朱红；
 * 「身强 / 身弱」用中性主色。
 *
 * 把「身弱」染成朱红，等于把一个中性的盘面事实渲染成凶兆 ——
 * 用户会读到"我的命不好"，而计算层从来没说过这句话。
 * 那是 RULE-008（不得为了看起来合理而修饰数据）在界面层的对应物。
 *
 * ## 调用方职责
 *
 * `verdictLabel` 是**必填**：等级词单独出现时，用户不知道它在度量什么。
 * 「偏吉」是吉凶，「身强」是状态，两者都必须由调用方声明语义。
 */

import React, { type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import type { DuanResponse } from '@/api/types';
import { alpha, colors, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';
import { UncertaintyList } from './Banner';
import { Card, Divider } from './Card';

export interface DuanCardProps {
  duan: DuanResponse;
  /** verdict 的语义标签，如「吉凶倾向」「日主状态」 */
  verdictLabel: string;
  title?: string;
  /** 术式专属细节（六爻的取用神依据 / 八字的大运逐运倾向） */
  children?: ReactNode;
}

/** 吉凶着色档 */
export type VerdictTone = 'good' | 'bad' | 'neutral';

/**
 * verdict → 吉凶档。
 *
 * 用**白名单**（只认吉凶词）而不是"默认吉色、特判凶词"的黑名单：
 * 后者会让一个未预料的新 verdict 被默认染成吉色 ——
 * 一个不认识的词被渲染成"好"，比渲染成中性更糟。
 *
 * 导出供调用方复用：八字页要把「大运逐运倾向」也染成同一套色，
 * 两处各写一份判定迟早会分叉。
 */
export function verdictTone(verdict: string): VerdictTone {
  if (verdict === '偏吉') return 'good';
  if (verdict === '偏凶') return 'bad';
  // 中平 / 身强 / 身弱 / 其它 —— 中性，不着吉凶色
  return 'neutral';
}

const VERDICT_PALETTE: Record<VerdictTone, { bg: string; fg: string; border: string }> = {
  good: { bg: colors.jade, fg: colors.onPrimary, border: colors.jade },
  bad: { bg: colors.cinnabar, fg: colors.onPrimary, border: colors.cinnabar },
  neutral: { bg: alpha.primarySoft, fg: colors.primary, border: alpha.primaryBorder },
};

export function DuanCard({
  duan,
  verdictLabel,
  title = '断卦',
  children,
}: DuanCardProps): React.JSX.Element {
  const tone = VERDICT_PALETTE[verdictTone(duan.verdict)];

  return (
    <Card title={title}>
      <View style={styles.headline}>
        <View style={[styles.badge, { backgroundColor: tone.bg, borderColor: tone.border }]}>
          <AppText size="xl" weight="bold" color={tone.fg}>
            {duan.verdict}
          </AppText>
        </View>
        <View style={styles.headlineMeta}>
          <AppText size="xs" color="muted">
            {verdictLabel}
          </AppText>
          <AppText size="sm" color="textSecondary" style={styles.school}>
            {duan.school}
          </AppText>
        </View>
      </View>

      {duan.reasons.length > 0 ? (
        <>
          <Divider style={styles.divider} />
          <AppText size="xs" color="textSecondary">
            依据
          </AppText>
          <View style={styles.reasons}>
            {duan.reasons.map((r, i) => (
              <View key={`${i}-${r.slice(0, 8)}`} style={styles.reasonRow}>
                <AppText size="sm" color="muted" style={styles.bullet}>
                  ·
                </AppText>
                <AppText size="sm" style={styles.reasonText}>
                  {r}
                </AppText>
              </View>
            ))}
          </View>
        </>
      ) : null}

      {children}

      {/* 不确定性由本组件统一渲染 —— 若交给各调用方自己记得画，
          总有一个页面会忘，而"没显示不确定性"与"没有不确定性"在界面上
          长得一模一样。 */}
      <UncertaintyList items={duan.uncertainties} />
    </Card>
  );
}

const styles = StyleSheet.create({
  headline: { flexDirection: 'row', alignItems: 'center' },
  badge: {
    paddingHorizontal: space[5],
    paddingVertical: space[2],
    borderRadius: radius.md,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 92,
  },
  headlineMeta: { flex: 1, marginLeft: space[4] },
  school: { marginTop: space[1] },
  divider: { marginVertical: space[3] },
  reasons: { gap: space[1], marginTop: space[2] },
  reasonRow: { flexDirection: 'row', alignItems: 'flex-start' },
  bullet: { width: 10, lineHeight: 20 },
  reasonText: { flex: 1 },
});
