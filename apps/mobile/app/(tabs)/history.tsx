/**
 * 历史 —— 会话列表。
 *
 * 每张卡片显示"这次用了哪些术式"与"有几份报告"，而不是标题一句话。
 * 原因：用户回想"上周那次问事业用的是六爻还是八字"时，
 * 术式标签比标题更能定位；而报告数提示了这条记录有没有解读可以回看。
 */

import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useRouter } from 'expo-router';
import React, { useCallback } from 'react';
import { FlatList, Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { SessionSummary } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, EmptyState } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { useAsync } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

/** 模块名 → 中文标签 */
const MODULE_LABEL: Record<string, string> = {
  compass: '罗盘',
  bazi: '八字',
  liuyao: '六爻',
  qian: '灵签',
  naming: '姓名',
};

export default function HistoryScreen(): React.JSX.Element {
  const router = useRouter();

  const load = useCallback(async () => {
    const page = await getApiClient().listSessions(50, 0);
    return page.items;
  }, []);

  const { data, loading, error, reload } = useAsync(load, []);

  // 从详情页返回到这里时自动刷新（否则删除后列表还显示旧项）
  useFocusEffect(
    useCallback(() => {
      reload();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []),
  );

  if (error) {
    return (
      <Screen>
        <Banner tone="error" title="加载失败">
          {error}
        </Banner>
        <Button label="重试" variant="ghost" onPress={reload} />
      </Screen>
    );
  }

  return (
    <Screen padded={false}>
      <FlatList
        data={data ?? []}
        keyExtractor={(item) => item.session_id}
        contentContainerStyle={styles.list}
        refreshing={loading}
        onRefresh={reload}
        ListEmptyComponent={
          loading ? null : (
            <EmptyState
              title="还没有任何记录"
              hint="拍一张罗盘照片，或在命盘 / 占测页录入信息后会出现在这里"
              action={<Button label="去拍罗盘" onPress={() => router.push('/scan')} />}
            />
          )
        }
        renderItem={({ item }) => (
          <SessionCard item={item} onPress={() => router.push(`/session/${item.session_id}`)} />
        )}
      />
    </Screen>
  );
}

function SessionCard({
  item,
  onPress,
}: {
  item: SessionSummary;
  onPress: () => void;
}): React.JSX.Element {
  const flags: [boolean, string][] = [
    [item.has_compass === 1, MODULE_LABEL['compass']!],
    [item.has_bazi === 1, MODULE_LABEL['bazi']!],
    [item.has_liuyao === 1, MODULE_LABEL['liuyao']!],
    [item.has_qian === 1, MODULE_LABEL['qian']!],
    [item.has_naming === 1, MODULE_LABEL['naming']!],
  ];
  const modules = flags.filter(([on]) => on).map(([, label]) => label);

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.cardWrap, pressed && styles.pressed]}>
      <Card style={styles.card}>
        <View style={styles.cardHead}>
          <AppText size="md" weight="semibold" color="primary" numberOfLines={1} style={styles.title}>
            {item.title || '未命名'}
          </AppText>
          {item.report_count > 0 ? (
            <View style={styles.reportBadge}>
              <Ionicons name="sparkles" size={11} color={colors.primary} />
              <AppText size="xs" color="primary" style={styles.reportBadgeText}>
                {item.report_count}
              </AppText>
            </View>
          ) : null}
        </View>

        <View style={styles.chips}>
          {modules.length > 0 ? (
            modules.map((m) => (
              <View key={m} style={styles.chip}>
                <AppText size="xs" color="textSecondary">
                  {m}
                </AppText>
              </View>
            ))
          ) : (
            <AppText size="xs" color="muted">
              尚未录入
            </AppText>
          )}
          {item.question_category ? (
            <View style={[styles.chip, styles.chipQuestion]}>
              <AppText size="xs" color="primary">
                问{item.question_category}
              </AppText>
            </View>
          ) : null}
        </View>

        {item.question_text ? (
          <AppText size="sm" color="textSecondary" numberOfLines={1} style={styles.question}>
            {item.question_text}
          </AppText>
        ) : null}

        <AppText size="xs" color="muted" style={styles.time}>
          {formatTime(item.updated_at)}
        </AppText>
      </Card>
    </Pressable>
  );
}

/** 便捷时间：今天显示时分，其余显示月-日 */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  if (sameDay) return `今天 ${hh}:${mm}`;
  return `${d.getMonth() + 1}月${d.getDate()}日 ${hh}:${mm}`;
}

const styles = StyleSheet.create({
  list: { padding: space[4], paddingTop: space[3] },
  cardWrap: { marginBottom: 0 },
  pressed: { opacity: 0.9 },
  card: { marginBottom: space[3] },
  cardHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  title: { flex: 1, marginRight: space[2] },
  reportBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: alpha.primarySoft,
    borderRadius: radius.pill,
    paddingHorizontal: space[2],
    paddingVertical: 2,
  },
  reportBadgeText: { marginLeft: 3 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1], marginTop: space[2] },
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    paddingHorizontal: space[2],
    paddingVertical: 2,
  },
  chipQuestion: { backgroundColor: alpha.goldSoft },
  question: { marginTop: space[2] },
  time: { marginTop: space[2] },
});
