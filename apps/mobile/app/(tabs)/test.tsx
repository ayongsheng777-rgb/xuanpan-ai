/**
 * 测盘 —— 参考图第 7 屏「请选择数据来源」。
 *
 * 这一页存在的意义是**把五条来源摆在一起**，而不是让用户在首页猜。
 * 五条来源的产物是同一样东西（一份坐向数据），但可信度与代价差别很大：
 *
 *   拍摄真实罗盘  → 有照片为证，但需识别 + 人工确认（RULE-004）
 *   导入照片      → 同上，只是照片来自相册
 *   手机传感器    → 现场实测，但有磁偏角与设备误差，只给"方向读得准不准"
 *   手动输入      → 零外部依赖，精度取决于用户手里的盘
 *   我的罗盘      → 复用已存的盘式预设，省去重选
 *
 * 三条来源（拍摄 / 导入 / 手动）最终都汇到**同一条确认管线**，
 * 故此处只负责分流，不复制任何业务逻辑。
 *
 * 🔴 本页不显示任何"当前方位/磁场"读数。那是传感器页的职责（一页一事）——
 * 在这里显示一个读数为 0° 的静态罗盘，会被读成"方位就是 0°"。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { Button, PressablePanel } from '@/components/Card';
import { HelpButton } from '@/components/HelpButton';
import { InfoPopup } from '@/components/InfoPopup';
import { Screen } from '@/components/Screen';
import { colors, instrument, radius, space } from '@/theme/tokens';

type SourceKey = 'camera' | 'library' | 'sensor' | 'manual' | 'template';

interface Source {
  key: SourceKey;
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  desc: string;
  /** 该来源产出的数据可信度提示 —— 用户需要知道自己在选什么 */
  caveat?: string;
  href: string;
}

/**
 * 五条来源。顺序按**推荐度**排（最可靠的在前），不按字母或时间 ——
 * 这个列表是给人按顺序往下选的，第一项应当是"最该用的那个"。
 */
const SOURCES: readonly Source[] = [
  {
    key: 'camera',
    icon: 'camera',
    title: '拍摄真实罗盘',
    desc: '通过相机识别罗盘并还原',
    caveat: '需保持盘面完整、避开反光；识别结果须经你确认',
    href: '/scan',
  },
  {
    key: 'library',
    icon: 'images',
    title: '导入照片',
    desc: '从相册选择罗盘图片',
    caveat: '旧照片同样先过质量检测，模糊或反光会被拒绝并说明原因',
    href: '/scan?entry=library',
  },
  {
    key: 'sensor',
    icon: 'radio',
    title: '手机传感器',
    desc: '使用磁力计、陀螺仪等数据',
    caveat: '读数为磁北、未做磁偏角改正；只回答「方向读得准不准」',
    href: '/sensors',
  },
  {
    key: 'manual',
    icon: 'create',
    title: '手动输入',
    desc: '手动设置坐向、角度等参数',
    caveat: '不依赖照片与传感器，精度取决于你手里罗盘的读数',
    href: '/adjust',
  },
  {
    key: 'template',
    icon: 'albums',
    title: '我的罗盘',
    desc: '从模板库选择已保存的罗盘',
    caveat: '复用已存的盘式与默认坐向，不代替本次实测',
    href: '/templates',
  },
];

export default function TestScreen(): React.JSX.Element {
  const router = useRouter();

  return (
    <Screen style={styles.root}>
      {/*
        一屏布局（2026-10-08 用户要求 BUG 6）：不滚动、积木式宫格。
        五个来源做成 2 列积木块，一屏放下；每块的详细说明（desc/caveat）
        收进弹出框，点右上角小问号看 —— 页面只留"选哪个"的决策信息。
      */}
      <View style={styles.headerRow}>
        <AppText size="xl" weight="bold" color={instrument.text} track="tight">
          测盘
        </AppText>
        <HelpButton topic="test" color={instrument.textSecondary} />
      </View>

      <AppText size="md" weight="medium" color={instrument.text} style={styles.sectionLead}>
        请选择数据来源
      </AppText>

      <View style={styles.grid}>
        {SOURCES.map((s) => (
          <SourceBlock key={s.key} source={s} onPress={() => router.push(s.href as never)} />
        ))}
      </View>

      <AppText size="xs" color={instrument.muted} style={styles.footLine}>
        五条来源最终都汇入同一条确认管线 —— 坐向必须经你确认才会进入计算。
      </AppText>
    </Screen>
  );
}

/**
 * 积木块：图标 + 标题，点块进入；点右上角小问号弹出详细说明。
 * 一块只做一件事，字越少越好 —— 详情在弹出框里。
 */
function SourceBlock({ source, onPress }: { source: Source; onPress: () => void }): React.JSX.Element {
  const [infoOpen, setInfoOpen] = useState(false);
  return (
    <>
      <PressablePanel
        onPress={onPress}
        accessibilityLabel={`${source.title}：${source.desc}`}
        style={styles.blockWrap}
        contentStyle={styles.block}
      >
        <View style={styles.blockIcon}>
          <Ionicons name={source.icon} size={24} color={instrument.accent} />
        </View>
        <AppText size="sm" weight="semibold" color={instrument.text} center style={styles.blockTitle}>
          {source.title}
        </AppText>
        <Pressable
          onPress={() => setInfoOpen(true)}
          hitSlop={10}
          accessibilityRole="button"
          accessibilityLabel={`${source.title}的详细说明`}
          style={styles.blockInfo}
        >
          <Ionicons name="information-circle-outline" size={18} color={instrument.muted} />
        </Pressable>
      </PressablePanel>

      <InfoPopup
        visible={infoOpen}
        onClose={() => setInfoOpen(false)}
        title={source.title}
        subtitle="选之前先看看"
      >
        <AppText size="sm" color={colors.text} style={styles.popupBody}>
          {source.desc}
        </AppText>
        {source.caveat ? (
          <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
            注意：{source.caveat}
          </AppText>
        ) : null}
        <Button label={`进入${source.title}`} onPress={() => { setInfoOpen(false); onPress(); }} />
      </InfoPopup>
    </>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionLead: { marginTop: space[2], marginBottom: space[2] },
  /* 积木宫格：2 列，一屏放下 5 块（2026-10-08 用户反馈：必须真一屏，不滚动） */
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  blockWrap: { width: '48%', flexGrow: 1 },
  block: {
    alignItems: 'center',
    gap: space[1],
    paddingVertical: space[2],
    minHeight: 104,
  },
  blockIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: instrument.surfaceAlt,
  },
  blockTitle: { lineHeight: 20 },
  blockInfo: { position: 'absolute', top: space[1], right: space[1], padding: space[1] },
  popupBody: { lineHeight: 24 },
  footLine: { marginTop: space[2], lineHeight: 16 },
});
