/**
 * 签库选择器 —— 抽签页共用。
 *
 * 签库列表来自服务端 `/api/v1/meta/qian-sets`（读的是 `data/qian/` 目录，
 * 后端加文件、前端自动多一项，无需改代码）。
 *
 * 演示签库（自撰样例）挂「演示」角标；第三方/真实签库显示签数。
 * 选中态用主色边框 —— 与 Chip 的 active 语义一致（互斥单选）。
 */

import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { QianSet } from '@/api/types';
import { AppText } from '@/components/AppText';
import { colors, radius, space } from '@/theme/tokens';

function setTotal(s: QianSet): number | null {
  // 后端字段叫 `total`，TS 类型里只有 `count?` + 索引签名 → 收窄后取
  const v: unknown = (s as { total?: unknown }).total ?? s.count;
  return typeof v === 'number' && v > 0 ? v : null;
}

export function QianSetPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (setId: string) => void;
}): React.JSX.Element {
  const [sets, setSets] = useState<QianSet[] | null>(null);

  useEffect(() => {
    let alive = true;
    getApiClient()
      .qianSets()
      .then((r) => {
        if (alive) setSets(r.sets);
      })
      .catch(() => {
        if (alive) setSets([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (sets === null) {
    return (
      <AppText size="xs" color="muted" style={styles.hint}>
        签库加载中…
      </AppText>
    );
  }
  if (sets.length === 0) {
    return (
      <AppText size="xs" color="muted" style={styles.hint}>
        暂无可用签库
      </AppText>
    );
  }

  return (
    <View style={styles.row}>
      {sets.map((s) => {
        const active = s.set_id === value;
        const total = setTotal(s);
        return (
          <Pressable
            key={s.set_id}
            onPress={() => onChange(s.set_id)}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            style={[styles.item, active && styles.itemActive]}
          >
            <AppText size="sm" weight={active ? 'semibold' : 'regular'} color={active ? 'primary' : 'text'}>
              {s.name ?? s.set_id}
            </AppText>
            <AppText size="xs" color="muted">
              {s.demo ? '演示样例' : total !== null ? `${total} 支` : ''}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  hint: { marginBottom: space[2] },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginBottom: space[3] },
  item: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    backgroundColor: colors.surface,
    gap: 2,
  },
  itemActive: { borderColor: colors.primary, borderWidth: 2 },
});
