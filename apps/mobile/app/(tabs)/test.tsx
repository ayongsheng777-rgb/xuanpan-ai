/**
 * 测盘 —— 单屏道具阵（2026-10-09 重设计）。
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
 *
 * ## 单屏做法
 *
 * 五块按「2×2 + 1 居中」排（玄学科技风规范的原话），三行**等高平分**剩余高度：
 * 行用 `flex: 1` 而不是固定高度，屏幕高时块自己长高，不留大片空白；
 * 屏幕矮时也不会溢出（块内文字固定两行、图标固定 44）。
 * 详细说明（desc/caveat）收进每块右上角的问号弹层，页面只留"选哪个"的决策信息。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { InstrumentBlock } from '@/components/InstrumentBlock';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { instrument, space } from '@/theme/tokens';

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

  /** 前四块按 2×2 排，第五块单独一行居中 —— 见文件头注释 */
  const firstFour = SOURCES.slice(0, 4);
  const last = SOURCES[4]!;

  const renderBlock = (s: Source) => (
    <InstrumentBlock
      key={s.key}
      title={s.title}
      desc={s.desc}
      bound={s.caveat}
      width="auto"
      minHeight={0}
      fill
      icon={<Ionicons name={s.icon} size={26} color={instrument.accent} />}
      onPress={() => router.push(s.href as never)}
    />
  );

  return (
    <Screen style={styles.root}>
      <PageHeader title="测盘" subtitle="请选择数据来源" helpTopic="test" />

      {/* 道具阵：2×2 + 1 居中，三行等高平分剩余高度 */}
      <FitSlot weight={1}>
        <View style={styles.grid}>
          <View style={styles.row}>
            <View style={styles.cell}>{renderBlock(firstFour[0]!)}</View>
            <View style={styles.cell}>{renderBlock(firstFour[1]!)}</View>
          </View>
          <View style={styles.row}>
            <View style={styles.cell}>{renderBlock(firstFour[2]!)}</View>
            <View style={styles.cell}>{renderBlock(firstFour[3]!)}</View>
          </View>
          {/* 第五块居中，宽度与上面四块一致（48% ≈ 半宽减间隙） */}
          <View style={styles.rowCenter}>
            <View style={styles.cellHalf}>{renderBlock(last)}</View>
          </View>
        </View>
      </FitSlot>

      <AppText size="xs" color={instrument.muted} numberOfLines={2} style={styles.foot}>
        五条来源最终都汇入同一条确认管线 —— 坐向必须经你确认才会进入计算。
      </AppText>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  grid: { flex: 1, gap: space[2] },
  row: { flexDirection: 'row', flex: 1, gap: space[2] },
  rowCenter: { flexDirection: 'row', flex: 1, justifyContent: 'center' },
  cell: { flex: 1 },
  cellHalf: { width: '48%' },
  foot: { lineHeight: 16 },
});
