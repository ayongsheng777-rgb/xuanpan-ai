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
import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Card';
import { InfoPopup } from '@/components/InfoPopup';
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
 * 术式入口。顺序按「用得最多 → 最少」排（八字 > 六爻灵签 > 灵签机 > 黄历 > 三式），
 * 不按学科体系排 —— 这是给人点的列表，第一项应当是最常用的那个。
 */
const ENTRIES: readonly Entry[] = [
  {
    key: 'bazi',
    icon: 'planet',
    title: '八字命盘',
    desc: '录入出生时间，排出四柱、大运与流年',
    bound: '旺衰与用神由计算层给出，本页不自造流派判词',
    href: '/chart',
  },
  {
    key: 'divine',
    icon: 'sparkles',
    title: '六爻 · 灵签',
    desc: '登记实际摇出的结果，或抽取可复现的签文',
    bound: '不提供「帮我摇一卦」—— 摇卦结果必须由你实际摇出',
    href: '/divine',
  },
  {
    key: 'qianji',
    icon: 'game-controller',
    title: '灵签机',
    desc: '街机式抽签：按住摇签筒、开奖看签文，再解签',
    bound: '签号由种子唯一确定，动画只是表现层；签库为演示样例',
    href: '/qianji',
  },
  {
    key: 'almanac',
    icon: 'calendar',
    title: '黄历择日',
    desc: '查某天宜忌，或为某件事挑日子',
    bound: '流派差异与未覆盖项会在结果里显式列出，不装作唯一答案',
    href: '/almanac',
  },
  {
    key: 'sanshi',
    icon: 'grid',
    title: '三式排盘',
    desc: '奇门遁甲 / 大六壬 / 太乙神数',
    bound: '太乙本版只做年局，月/日/时局未实现（结果中已注明）',
    href: '/sanshi',
  },
];

export default function AnalysisScreen(): React.JSX.Element {
  const router = useRouter();

  return (
    <Screen style={styles.root}>
      {/*
        一屏布局（2026-10-08 用户要求 BUG 6）：不滚动、积木式宫格。
        读盘报告 + 5 个术式做成 2 列积木块；每块的说明（desc/bound）
        收进弹出框 —— 页面只留"点哪个"的决策信息。
      */}
      <AppText size="md" weight="medium" color={colors.text} style={styles.lead}>
        排盘与解读都在这里
      </AppText>

      <View style={styles.grid}>
        <EntryBlock
          icon="document-text"
          title="读盘报告"
          desc="从历史记录里选一条已确认的盘面，看它的报告。"
          bound="报告分三标签：盘面事实 / 传统分析 / AI 解读。只有你确认过坐向的盘面才有报告。"
          onPress={() => router.push('/history' as never)}
        />
        {ENTRIES.map((e) => (
          <EntryBlock
            key={e.key}
            icon={e.icon}
            title={e.title}
            desc={e.desc}
            bound={e.bound}
            onPress={() => router.push(e.href as never)}
          />
        ))}
      </View>

      <AppText size="xs" color={colors.muted} style={styles.footLine}>
        盘面全部由确定性代码计算，AI 只负责讲成人话，不参与计算、也不得修改结果。
      </AppText>
    </Screen>
  );
}

/** 积木块：图标 + 标题，点块进入；点问号弹出"这是什么、能干什么"。 */
function EntryBlock({
  icon,
  title,
  desc,
  bound,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  desc: string;
  bound: string;
  onPress: () => void;
}): React.JSX.Element {
  const [infoOpen, setInfoOpen] = useState(false);
  return (
    <>
      <Pressable
        onPress={onPress}
        accessibilityRole="button"
        accessibilityLabel={`${title}：${desc}`}
        style={({ pressed }) => [styles.block, pressed && styles.blockPressed]}
      >
        <View style={styles.blockIcon}>
          <Ionicons name={icon} size={24} color={colors.primary} />
        </View>
        <AppText size="sm" weight="semibold" color={colors.text} center style={styles.blockTitle}>
          {title}
        </AppText>
        <Pressable
          onPress={() => setInfoOpen(true)}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={`${title}的详细说明`}
          style={styles.blockInfo}
        >
          <Ionicons name="information-circle-outline" size={18} color={colors.muted} />
        </Pressable>
      </Pressable>
      <InfoPopup visible={infoOpen} onClose={() => setInfoOpen(false)} title={title} subtitle="选之前先看看">
        <AppText size="sm" color={colors.text} style={styles.popupBody}>
          {desc}
        </AppText>
        <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
          注意：{bound}
        </AppText>
        <Button label={`进入${title}`} onPress={() => { setInfoOpen(false); onPress(); }} />
      </InfoPopup>
    </>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: colors.bg },
  lead: { lineHeight: 22, marginBottom: space[2] },
  /* 积木宫格：2 列，一屏放下 6 块（2026-10-08 用户反馈：必须真一屏，不滚动） */
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  block: {
    width: '48%',
    flexGrow: 1,
    alignItems: 'center',
    gap: space[1],
    paddingVertical: space[2],
    minHeight: 104,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  blockPressed: { backgroundColor: colors.surfaceAlt },
  blockIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceAlt,
  },
  blockTitle: { lineHeight: 20 },
  blockInfo: { position: 'absolute', top: space[1], right: space[1], padding: space[1] },
  popupBody: { lineHeight: 24 },
  footLine: { marginTop: space[2], lineHeight: 16 },
});
