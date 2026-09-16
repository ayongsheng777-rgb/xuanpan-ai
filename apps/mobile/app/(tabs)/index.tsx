/**
 * 罗盘（首页）—— 基线规范 §1.1。
 *
 * 结构：标题栏 → 罗盘视觉 → 主 CTA → 快捷入口 → 今日状态。
 *
 * 关于"后端没起来"：这是本地/自建部署最常见的第一次体验问题。
 * 页面**不隐藏**这个状态，而是给出端口与排查方向 ——
 * 静默失败会让用户以为 App 坏了，而这其实是最容易自查的一类问题。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getApiClient, resolveBaseUrl } from '@/api/client';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, EmptyState } from '@/components/Card';
import { HeroCompass } from '@/components/HeroCompass';
import { Screen } from '@/components/Screen';
import { useAsync } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

interface HomeStats {
  total: number;
  latestTitle: string | null;
}

export default function CompassHomeScreen(): React.JSX.Element {
  const router = useRouter();

  const load = useCallback(async (): Promise<HomeStats> => {
    const page = await getApiClient().listSessions(1, 0);
    return { total: page.total, latestTitle: page.items[0]?.title ?? null };
  }, []);

  const { data, loading, error, reload } = useAsync(load, []);

  return (
    <Screen scroll onRefresh={reload} refreshing={loading && data !== null}>
      <View style={styles.headerRow}>
        <View>
          <AppText size="xxl" weight="bold" color="primary">
            玄盘 AI
          </AppText>
          <AppText size="xs" color="muted" style={styles.subtitle}>
            确定性计算 · AI 解读
          </AppText>
        </View>
        <Pressable
          onPress={() => router.push('/mine')}
          accessibilityLabel="设置"
          hitSlop={10}
          style={styles.gear}
        >
          <Ionicons name="settings-outline" size={22} color={colors.textSecondary} />
        </Pressable>
      </View>

      {error ? <BackendHint message={error} onRetry={reload} /> : null}

      <View style={styles.hero}>
        <HeroCompass size={228} />
        <AppText size="md" color="textSecondary" style={styles.tagline}>
          一盘入局 · AI 解读你的盘面
        </AppText>
      </View>

      <Card highlight style={styles.ctaCard}>
        <Button
          label="拍摄罗盘 —— AI 自动识别坐山向山"
          size="lg"
          icon={<Ionicons name="compass" size={20} color={colors.onPrimary} />}
          onPress={() => router.push('/scan')}
        />
        <AppText size="xs" color="muted" center style={styles.ctaHint}>
          也可从相册选择已拍好的照片；识别结果须经你确认后才进入计算
        </AppText>
      </Card>

      <View style={styles.quickRow}>
        <QuickEntry label="八字" icon="calendar-outline" onPress={() => router.push('/chart')} />
        <QuickEntry label="六爻" icon="git-branch-outline" onPress={() => router.push('/divine')} />
        <QuickEntry label="灵签" icon="book-outline" onPress={() => router.push('/divine')} />
      </View>

      <Card title="今日状态">
        {loading && data === null ? (
          <AppText size="sm" color="muted">
            读取中…
          </AppText>
        ) : data && data.total > 0 ? (
          <>
            <AppText size="lg" weight="semibold" color="primary">
              已保存 {data.total} 个盘面
            </AppText>
            {data.latestTitle ? (
              <AppText size="sm" color="textSecondary" style={styles.latest}>
                最近：{data.latestTitle}
              </AppText>
            ) : null}
            <Button
              label="查看历史"
              variant="ghost"
              style={styles.historyBtn}
              onPress={() => router.push('/history')}
            />
          </>
        ) : (
          <EmptyState title="还没有记录" hint="上传一张罗盘照片，或在命盘 / 占测页录入信息" />
        )}
      </Card>

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        以上内容属于传统文化娱乐/学习参考
      </AppText>
    </Screen>
  );
}

/** 后端不可达提示 —— 给出端口与排查方向，而不是只说"网络错误" */
function BackendHint({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}): React.JSX.Element {
  return (
    <Banner tone="error" title="无法连接后端服务">
      <AppText size="sm">{message}</AppText>
      <AppText size="sm" style={styles.hintBody}>
        请确认后端已启动（当前地址 {resolveBaseUrl()}）。真机调试时需把 app.json 里的
        apiBaseUrl 改成本机局域网 IP。
      </AppText>
      <Button label="重试" variant="ghost" style={styles.retry} onPress={onRetry} />
    </Banner>
  );
}

function QuickEntry({
  label,
  icon,
  onPress,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.quick, pressed && styles.quickPressed]}>
      <Ionicons name={icon} size={20} color={colors.primary} />
      <AppText size="sm" weight="medium" color="primary" style={styles.quickLabel}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  headerRow: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between' },
  subtitle: { marginTop: 2 },
  gear: { padding: space[2], borderRadius: radius.pill, backgroundColor: colors.surface },
  hero: { alignItems: 'center', marginTop: space[5], marginBottom: space[4] },
  tagline: { marginTop: space[3] },
  ctaCard: { marginBottom: space[4] },
  ctaHint: { marginTop: space[2] },
  quickRow: { flexDirection: 'row', gap: space[3], marginBottom: space[4] },
  quick: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[3],
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  quickPressed: { backgroundColor: alpha.primarySoft },
  quickLabel: { marginTop: space[1] },
  latest: { marginTop: space[1] },
  historyBtn: { marginTop: space[3] },
  disclaimer: { marginTop: space[4] },
  hintBody: { marginTop: space[1] },
  retry: { marginTop: space[3] },
});
