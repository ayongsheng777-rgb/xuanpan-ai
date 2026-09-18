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
import React from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { PressablePanel } from '@/components/Card';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { instrument, radius, space } from '@/theme/tokens';

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
    <Screen scroll bottomInsetExtra={space[8]} style={styles.root}>
      {/* 标题栏由页面自己画 —— tab 的浅色标题栏压在这个深色页面上会割裂。
          故 _layout.tsx 把本 tab 的 header 关掉（与首页同一处理）。 */}
      <View style={styles.headerRow}>
        <AppText size="xl" weight="bold" color={instrument.text} track="tight">
          测盘
        </AppText>
        <HelpButton topic="test" color={instrument.textSecondary} />
      </View>

      <AppText size="md" weight="medium" color={instrument.text} style={styles.sectionLead}>
        请选择数据来源
      </AppText>
      <AppText size="xs" color={instrument.textSecondary} style={styles.lead}>
        五条来源最终都汇入同一条确认管线 —— 无论从哪来，坐向都必须经你确认
        才会进入计算。
      </AppText>

      {SOURCES.map((s) => (
        <SourceCard key={s.key} source={s} onPress={() => router.push(s.href as never)} />
      ))}

      <View style={styles.foot}>
        <AppText size="xs" color={instrument.muted} style={styles.footLine}>
          所有数值由确定性代码计算，AI 只负责解释，不参与计算、也不得修改结果。
        </AppText>
        <AppText size="xs" color={instrument.muted} style={styles.footLine}>
          罗盘照片会上传到服务端完成识别（默认不保留原图）；传感器读数在设备本地计算，不上传。
        </AppText>
      </View>
    </Screen>
  );
}

function SourceCard({ source, onPress }: { source: Source; onPress: () => void }): React.JSX.Element {
  return (
    <PressablePanel
      onPress={onPress}
      accessibilityLabel={`${source.title}：${source.desc}`}
      style={styles.cardWrap}
      contentStyle={styles.card}
    >
      <View style={styles.iconWrap}>
        <Ionicons name={source.icon} size={22} color={instrument.accent} />
      </View>
      <View style={styles.body}>
        <AppText size="md" weight="semibold" color={instrument.text}>
          {source.title}
        </AppText>
        <AppText size="xs" color={instrument.textSecondary} style={styles.desc}>
          {source.desc}
        </AppText>
        {source.caveat ? (
          <AppText size="xs" color={instrument.muted} style={styles.caveat}>
            {source.caveat}
          </AppText>
        ) : null}
      </View>
      <Ionicons name="chevron-forward" size={18} color={instrument.muted} />
    </PressablePanel>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sectionLead: { marginTop: space[4] },
  lead: { marginTop: space[2], marginBottom: space[3] },
  /* 外框只管定位；底/边/圆角/内边距由 `PressablePanel` 给 —— 见 Card.tsx「三个表面原语」 */
  cardWrap: { marginTop: space[2] },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    marginBottom: 0,
  },
  iconWrap: {
    width: 40,
    height: 40,
    /* 内嵌图形用 radius.sm，比外层容器的 lg 紧一档 */
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: instrument.surfaceAlt,
  },
  body: { flex: 1 },
  desc: { marginTop: 2, lineHeight: 17 },
  caveat: { marginTop: space[1], lineHeight: 16 },
  foot: { marginTop: space[5], gap: space[1] },
  footLine: { lineHeight: 17 },
});
