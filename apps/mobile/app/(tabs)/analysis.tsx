/**
 * 分析 —— 术式排盘与解读的聚合入口（2026-10-09 单屏重设计）。
 *
 * 为什么把八字 / 六爻灵签 / 黄历 / 三式放到同一个内页，而不是各自占一个底栏：
 * 底栏位置是**用户最高频动作**的预算。测盘（拍盘、对盘、存盘）是每天要做的，
 * 而排盘是"想起来才做一次"的。把四个低频入口摊在底栏，会把高频的测盘挤掉。
 *
 * 但收进来不等于藏起来 —— 本页必须一眼看全「有哪些术式、各自解决什么问题」，
 * 所以每个入口都带一句**它到底算什么**的说明（收在问号弹层里），而不是只留一个名字。
 *
 * 🔴 本页**浅色域**，不是罗盘仪器域。深色仪器风只用于罗盘域（V2 冲突 2 裁决），
 * 而这里通向的四页（chart / divine / almanac / sanshi）全部是浅色 ——
 * 入口比目标页更"重"会让人以为进错了地方。
 *
 * 🔴 本页不产生任何术数结论，只做分流。所有盘面由确定性内核算出，
 * AI 只解释（RULE-001 / RULE-002）。
 *
 * ## 单屏做法
 *
 * 6 块 = 读盘报告 + 5 个术式，按 2×3 排，三行 `flex: 1` 等高平分剩余高度。
 * 图标 26px：一屏紧凑与「图标为空看不清」（BUG 4）的折中 ——
 * 低于 26 会触发 `test_app_wiring` 的守卫，高于 26 会在矮屏把标题挤出格。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { InstrumentBlock } from '@/components/InstrumentBlock';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { colors, space } from '@/theme/tokens';

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

/** 读盘报告 —— 不在 `ENTRIES` 里：它的目标页是历史列表，不是独立术式页 */
const REPORT: Entry = {
  key: 'report',
  icon: 'document-text',
  title: '读盘报告',
  desc: '从历史记录里选一条已确认的盘面，看它的报告。',
  bound: '报告分三标签：盘面事实 / 传统分析 / AI 解读。只有你确认过坐向的盘面才有报告。',
  href: '/history',
};

export default function AnalysisScreen(): React.JSX.Element {
  const router = useRouter();
  const all = [REPORT, ...ENTRIES];

  return (
    <Screen>
      <PageHeader
        title="分析"
        subtitle="排盘与解读都在这里"
        helpTopic="analysis"
        tone="light"
      />

      {/* 六宫阵：2×3，三行等高平分剩余高度 */}
      <FitSlot weight={1}>
        <View style={styles.grid}>
          {[0, 1, 2].map((r) => (
            <View key={r} style={styles.row}>
              <View style={styles.cell}>
                <EntryBlock entry={all[r * 2]!} onPress={() => router.push(all[r * 2]!.href as never)} />
              </View>
              <View style={styles.cell}>
                <EntryBlock
                  entry={all[r * 2 + 1]!}
                  onPress={() => router.push(all[r * 2 + 1]!.href as never)}
                />
              </View>
            </View>
          ))}
        </View>
      </FitSlot>

      <AppText size="xs" color={colors.muted} numberOfLines={2} style={styles.foot}>
        盘面全部由确定性代码计算，AI 只负责讲成人话，不参与计算、也不得修改结果。
      </AppText>
    </Screen>
  );
}

/** 积木块：图标 + 标题，点块进入；点问号弹出"这是什么、能干什么"。 */
function EntryBlock({ entry, onPress }: { entry: Entry; onPress: () => void }): React.JSX.Element {
  const { icon, title, desc, bound } = entry;
  return (
    <InstrumentBlock
      tone="light"
      width="auto"
      minHeight={0}
      fill
      title={title}
      desc={desc}
      bound={bound}
      icon={
        /* 26px：一屏紧凑（用户反馈「必须真一屏」）与「图标为空看不清」（BUG 4）的折中 ——
           比原先 30/56 小一圈仍够大，低于 26 会触发 test_app_wiring 的守卫。 */
        <Ionicons name={icon} size={26} color={colors.primary} />
      }
      onPress={onPress}
    />
  );
}

const styles = StyleSheet.create({
  grid: { flex: 1, gap: space[2] },
  row: { flexDirection: 'row', flex: 1, gap: space[2] },
  cell: { flex: 1 },
  foot: { lineHeight: 16 },
});
