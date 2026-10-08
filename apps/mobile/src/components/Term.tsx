/**
 * 术语 —— 行内显示专业术语，点一下弹白话讲解。
 *
 * 2026-10-08 用户要求（BUG 5）："每个功能、术语增加白话讲解"。
 * 用法：在句子里直接包术语：
 *
 *   <AppText>本次测得<AppText>…</AppText></AppText>  ← 别这么写，嵌套麻烦
 *
 *   推荐写法（独立行或段落里混排）：
 *     读数为 <Term name="磁北" />，未做 <Term name="磁偏角" /> 改正。
 *
 * 没收录的术语：点开后显示"暂无白话讲解"，并给出去 help 页的提示 ——
 * 不编造（RULE-008 同精神：不知道就说不知道）。
 */

import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import { plainOf } from '@/content/plainTerms';
import { colors, space } from '@/theme/tokens';

import { AppText } from './AppText';
import { InfoPopup } from './InfoPopup';

export function Term({
  name,
  size = 'sm',
}: {
  /** 术语原文，必须与 plainTerms.ts 里的 key 一致 */
  name: string;
  size?: 'xs' | 'sm' | 'md';
}): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const entry = plainOf(name);

  return (
    <>
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel={`${name}，点我看大白话讲解`}
        style={({ pressed }) => [styles.term, pressed && styles.termPressed]}
      >
        <AppText size={size} weight="medium" color={colors.primary}>
          {name}
        </AppText>
        <Ionicons name="help-circle-outline" size={14} color={colors.primary} style={styles.q} />
      </Pressable>

      <InfoPopup
        visible={open}
        onClose={() => setOpen(false)}
        title={name}
        subtitle="大白话讲解"
      >
        {entry ? (
          <>
            <AppText size="md" style={styles.plain}>
              {entry.plain}
            </AppText>
            {entry.note ? (
              <AppText size="sm" color={colors.textSecondary} style={styles.note}>
                {entry.note}
              </AppText>
            ) : null}
          </>
        ) : (
          <AppText size="sm" color={colors.textSecondary}>
            这个术语还没写大白话讲解。请点右上角问号看整页的操作讲解，或告诉我们补上。
          </AppText>
        )}
      </InfoPopup>
    </>
  );
}

const styles = StyleSheet.create({
  term: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: space[1],
    borderRadius: 4,
    backgroundColor: 'rgba(218, 179, 125, 0.18)',
  },
  termPressed: { backgroundColor: 'rgba(218, 179, 125, 0.35)' },
  q: { marginLeft: 1 },
  plain: { lineHeight: 26 },
  note: { lineHeight: 22 },
});
