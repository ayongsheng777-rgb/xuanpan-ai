/**
 * 「操作与运作讲解」入口 —— 每页标题栏右上角的那个问号。
 *
 * 为什么放在标题栏而不是页面里：
 *   1. 讲解是**随时可查**的，用户卡在某一步时才想看，此时不应让他先滚回页顶找入口
 *   2. 不占用正文空间 —— 这类内容一旦常驻页面就会把操作流冲散
 *   3. 位置统一，用户第二次就形成肌肉记忆
 *
 * 内容来源是 `content/help.ts`，与页面实现各自独立维护；
 * 文案与实现不一致比没有文案更糟，改流程时务必同步。
 *
 * 交互：点开是**底部抽屉**而不是新页面 —— 用户往往需要边看讲解边看当前界面，
 * 跳页会让他丢掉上下文（尤其是填了一半的表单）。
 */

import { Ionicons } from '@expo/vector-icons';
import React, { useCallback, useState } from 'react';
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { helpTopicOf, type HelpSection, type HelpTopicId } from '@/content/help';
import { alpha, colors, font, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';

export interface HelpButtonProps {
  topic: HelpTopicId;
  /** 图标颜色（默认次级文字色） */
  color?: string;
}

export function HelpButton({ topic, color = colors.textSecondary }: HelpButtonProps): React.JSX.Element | null {
  const [open, setOpen] = useState(false);
  const insets = useSafeAreaInsets();
  const content = helpTopicOf(topic);

  const close = useCallback(() => setOpen(false), []);

  // 未登记的 topic 直接不渲染入口 —— 一个点了没反应的按钮比没有按钮更糟
  if (!content) return null;

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel={`${content.title}：操作与运作讲解`}
        style={({ pressed }) => [styles.trigger, pressed && styles.triggerPressed]}
      >
        <Ionicons name="help-circle-outline" size={22} color={color} />
      </Pressable>

      <Modal
        visible={open}
        transparent
        animationType="slide"
        onRequestClose={close}
        statusBarTranslucent
      >
        {/* 遮罩：点空白处关闭。做成可点即关，是因为这类内容用户多半只是扫一眼 */}
        <Pressable style={styles.backdrop} onPress={close} accessibilityLabel="关闭讲解" />

        <View style={[styles.sheet, { paddingBottom: insets.bottom + space[4] }]}>
          <View style={styles.handle} />

          <View style={styles.header}>
            <View style={styles.headerText}>
              <AppText size="lg" weight="bold" color={colors.primary}>
                {content.title}
              </AppText>
              <AppText size="xs" color={colors.textSecondary} style={styles.headerSub}>
                操作与运作讲解
              </AppText>
            </View>
            <Pressable
              onPress={close}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel="关闭"
              style={styles.closeBtn}
            >
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>

          <ScrollView
            style={styles.body}
            contentContainerStyle={styles.bodyContent}
            showsVerticalScrollIndicator={false}
          >
            <View style={styles.summary}>
              <AppText size="sm" color={colors.primary}>
                {content.summary}
              </AppText>
            </View>

            <Section section={content.steps} ordered />
            <Section section={content.how} />
            {content.notes ? <Section section={content.notes} tone="warn" /> : null}
          </ScrollView>
        </View>
      </Modal>
    </>
  );
}

/**
 * 生成导航器的 `headerRight` 回调。
 *
 * 存在的意义是**统一**：入口若由各页自行挂载，迟早出现"有的页有、有的页漏了"，
 * 而用户会把不一致当成缺陷。布局文件里只写 `headerRight: helpHeaderRight('chart')`。
 */
export function helpHeaderRight(topic: HelpTopicId) {
  return function HeaderHelp(): React.JSX.Element | null {
    return <HelpButton topic={topic} />;
  };
}

function Section({
  section,
  ordered = false,
  tone = 'default',
}: {
  section: HelpSection;
  ordered?: boolean;
  tone?: 'default' | 'warn';
}): React.JSX.Element {
  return (
    <View style={styles.section}>
      <View style={styles.sectionTitleRow}>
        {tone === 'warn' ? (
          <Ionicons name="alert-circle-outline" size={14} color={colors.warning} style={styles.sectionIcon} />
        ) : null}
        <AppText
          size="md"
          weight="semibold"
          color={tone === 'warn' ? colors.warning : colors.primary}
        >
          {section.title}
        </AppText>
      </View>

      {section.items.map((item, i) => (
        <View key={i} style={styles.item}>
          <AppText size="sm" color={tone === 'warn' ? colors.textSecondary : colors.primary} style={styles.bullet}>
            {ordered ? `${i + 1}.` : '·'}
          </AppText>
          <AppText size="sm" color={colors.text} style={styles.itemText}>
            {item}
          </AppText>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  trigger: { padding: space[2], borderRadius: radius.pill },
  triggerPressed: { backgroundColor: alpha.primarySoft },

  backdrop: { flex: 1, backgroundColor: alpha.scrim },

  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    maxHeight: '82%',
    paddingHorizontal: space[4],
  },
  handle: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.border,
    marginTop: space[2],
    marginBottom: space[2],
  },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: space[2],
  },
  headerText: { flex: 1 },
  headerSub: { marginTop: 2 },
  closeBtn: { padding: space[1], borderRadius: radius.pill },

  body: { flexGrow: 0 },
  bodyContent: { paddingBottom: space[4] },

  summary: {
    backgroundColor: alpha.primarySoft,
    borderRadius: radius.md,
    padding: space[3],
    marginBottom: space[2],
  },

  section: { marginTop: space[4] },
  sectionTitleRow: { flexDirection: 'row', alignItems: 'center', marginBottom: space[2] },
  sectionIcon: { marginRight: space[1] },

  item: { flexDirection: 'row', marginBottom: space[2] },
  bullet: { width: 18, lineHeight: font.lineHeight.sm },
  itemText: { flex: 1, lineHeight: font.lineHeight.sm },
});
