/**
 * 通用弹出信息框 —— 底部弹出的半屏卡片。
 *
 * 2026-10-08 用户要求（BUG 6）："弹出式信息框" —— 长篇的解释、详情
 * 不再堆在页面里拉长版面，点一下弹出来，看完关掉。
 *
 * 与 `HelpButton` 的区别：HelpButton 讲"这一页怎么用"（整页的操作讲解）；
 * InfoPopup 讲"任意一段内容"（术语白话、分析详情、提示说明），由调用方
 * 直接给标题和内容，更轻量。
 *
 * 用法：
 *   const [open, setOpen] = useState(false);
 *   <InfoPopup visible={open} onClose={() => setOpen(false)} title="坐山">
 *     <AppText>……</AppText>
 *   </InfoPopup>
 */

import { Ionicons } from '@expo/vector-icons';
import React, { type ReactNode } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';

export function InfoPopup({
  visible,
  onClose,
  title,
  subtitle,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  /** 副标题，如"大白话讲解" */
  subtitle?: string;
  children: ReactNode;
}): React.JSX.Element {
  const insets = useSafeAreaInsets();
  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      statusBarTranslucent
    >
      {/* 遮罩：点空白处关闭 */}
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="关闭" />
      <View style={[styles.sheet, { paddingBottom: insets.bottom + space[4] }]}>
        <View style={styles.handle} />
        <View style={styles.header}>
          <View style={styles.headerText}>
            <AppText size="lg" weight="bold" color={colors.primary}>
              {title}
            </AppText>
            {subtitle ? (
              <AppText size="xs" color={colors.textSecondary} style={styles.headerSub}>
                {subtitle}
              </AppText>
            ) : null}
          </View>
          <Pressable
            onPress={onClose}
            hitSlop={12}
            accessibilityRole="button"
            accessibilityLabel="关闭"
            style={styles.closeBtn}
          >
            <Ionicons name="close" size={22} color={colors.textSecondary} />
          </Pressable>
        </View>
        <ScrollView
          style={styles.body}
          contentContainerStyle={styles.bodyContent}
          showsVerticalScrollIndicator={false}
        >
          {children}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(44, 36, 22, 0.45)' },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingTop: space[2],
    paddingHorizontal: space[4],
    maxHeight: '70%',
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    alignSelf: 'center',
    marginBottom: space[2],
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', marginBottom: space[2] },
  headerText: { flex: 1 },
  headerSub: { marginTop: 2 },
  closeBtn: { padding: space[1] },
  body: { flexGrow: 0 },
  bodyContent: { paddingBottom: space[2], gap: space[2] },
});
