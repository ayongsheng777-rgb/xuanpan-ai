/**
 * 分析 —— 术式排盘与解读的聚合入口（参考图裁定：术式收进内页）。
 *
 * 为什么把八字 / 六爻灵签 / 黄历 / 三式放到同一个内页，而不是各自占一个底栏：
 * 底栏位置是**用户最高频动作**的预算。测盘（拍盘、对盘、存盘）是每天要做的，
 * 而排盘是"想起来才做一次"的。把四个低频入口摊在底栏，会把高频的测盘挤掉。
 *
 * 但收进来不等于藏起来 —— 本页必须一眼看全「有哪些术式、各自解决什么问题」，
 * 所以每个入口都带一句**它到底算什么**的说明，而不是只留一个名字。
 *
 * 🔴 本页**浅色域**，不是罗盘深色域。深色仪器风只用于罗盘域（V2 冲突 2 裁决），
 * 而这里通向的四页（chart / divine / almanac / sanshi）全部是浅色 ——
 * 入口比目标页更"重"会让人以为进错了地方。
 *
 * 🔴 本页不产生任何术数结论，只做分流。所有盘面由确定性内核算出，
 * AI 只解释（RULE-001 / RULE-002）。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { Screen } from '@/components/Screen';
import { colors, radius, space } from '@/theme/tokens';

interface Entry {
  key: string;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  /** 这个术式**解决什么问题** —— 只写名字等于没写入口 */
  desc: string;
  /** 该术式在本版的边界，避免用户期待本版没有的能力 */
  bound: string;
  href: string;
}

/**
 * 术式入口。顺序按「用得最多 → 最少」排（八字 > 六爻灵签 > 黄历 > 三式），
 * 不按学科体系排 —— 这是给人点的列表，第一项应当是最常用的那个。
 */
const ENTRIES: readonly Entry[] = [
  {
    key: 'bazi',
    icon: 'planet-outline',
    title: '八字命盘',
    desc: '录入出生时间，排出四柱、大运与流年',
    bound: '旺衰与用神由计算层给出，本页不自造流派判词',
    href: '/chart',
  },
  {
    key: 'divine',
    icon: 'sparkles-outline',
    title: '六爻 · 灵签',
    desc: '登记实际摇出的结果，或抽取可复现的签文',
    bound: '不提供「帮我摇一卦」—— 摇卦结果必须由你实际摇出',
    href: '/divine',
  },
  {
    key: 'almanac',
    icon: 'calendar-outline',
    title: '黄历择日',
    desc: '查某天宜忌，或为某件事挑日子',
    bound: '流派差异与未覆盖项会在结果里显式列出，不装作唯一答案',
    href: '/almanac',
  },
  {
    key: 'sanshi',
    icon: 'grid-outline',
    title: '三式排盘',
    desc: '奇门遁甲 / 大六壬 / 太乙神数',
    bound: '太乙本版只做年局，月/日/时局未实现（结果中已注明）',
    href: '/sanshi',
  },
];

export default function AnalysisScreen(): React.JSX.Element {
  const router = useRouter();

  return (
    <Screen scroll style={styles.root}>
      <AppText size="xs" color={colors.textSecondary} style={styles.lead}>
        排盘与解读都在这里。盘面全部由确定性代码计算，AI 只负责把它讲成人话 ——
        计算过程 AI 既不参与，也没有权限修改结果。
      </AppText>

      {/* ---------- 读盘报告 ---------- */}
      <AppText size="sm" weight="semibold" color={colors.textSecondary} style={styles.sectionTitle}>
        读盘报告
      </AppText>

      <Pressable
        onPress={() => router.push('/history')}
        accessibilityRole="button"
        accessibilityLabel="从历史记录打开一份读盘报告"
        style={({ pressed }) => [styles.reportCard, pressed && styles.cardPressed]}
      >
        <View style={styles.reportIcon}>
          <Ionicons name="document-text-outline" size={22} color={colors.primary} />
        </View>
        <View style={styles.body}>
          <AppText size="md" weight="medium" color={colors.text}>
            打开已确认盘面的报告
          </AppText>
          <AppText size="xs" color={colors.textSecondary} style={styles.desc}>
            从历史记录里选一条。报告分三标签：盘面事实 / 传统分析 / AI 解读
          </AppText>
          <AppText size="xs" color={colors.muted} style={styles.bound}>
            只有你确认过坐向的盘面才有报告 —— 未经确认的数据不进计算
          </AppText>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </Pressable>

      {/* ---------- 术式排盘 ---------- */}
      <AppText size="sm" weight="semibold" color={colors.textSecondary} style={styles.sectionTitle}>
        术式排盘
      </AppText>

      {ENTRIES.map((e) => (
        <Pressable
          key={e.key}
          onPress={() => router.push(e.href as never)}
          accessibilityRole="button"
          accessibilityLabel={`${e.title}：${e.desc}`}
          style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
        >
          <View style={styles.iconWrap}>
            <Ionicons name={e.icon} size={22} color={colors.primary} />
          </View>
          <View style={styles.body}>
            <AppText size="md" weight="medium" color={colors.text}>
              {e.title}
            </AppText>
            <AppText size="xs" color={colors.textSecondary} style={styles.desc}>
              {e.desc}
            </AppText>
            <AppText size="xs" color={colors.muted} style={styles.bound}>
              {e.bound}
            </AppText>
          </View>
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </Pressable>
      ))}

      <View style={styles.foot}>
        <AppText size="xs" color={colors.muted} style={styles.footLine}>
          本 App 提供的是传统文化研究与自省参考，不构成医疗、投资或法律建议。
          涉及健康、财务、诉讼等决策，请咨询相应领域的专业人士。
        </AppText>
        <AppText size="xs" color={colors.muted} style={styles.footLine}>
          遇流派分歧时给出并列口径，不替用户择一。
        </AppText>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: colors.bg },
  lead: { lineHeight: 19, marginBottom: space[4] },
  sectionTitle: { letterSpacing: 0.6, marginBottom: space[2] },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    marginBottom: space[2],
    padding: space[3],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  cardPressed: { backgroundColor: colors.surfaceAlt },
  reportCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    marginBottom: space[5],
    padding: space[3],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  reportIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceAlt,
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceAlt,
  },
  body: { flex: 1 },
  desc: { marginTop: 2, lineHeight: 17 },
  bound: { marginTop: space[1], lineHeight: 16 },
  foot: { marginTop: space[5], gap: space[2] },
  footLine: { lineHeight: 18 },
});
