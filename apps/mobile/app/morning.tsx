/**
 * 每日早报 —— 每天早上看一眼：黄历宜忌 + 按你生日算的当日运程。
 *
 * 街机式的「每日登录奖励」感：打开即打卡，连续天数累积；
 * 五宫星级像游戏属性面板，开运物是「今日 BUFF」。
 *
 * 数据：
 * - 黄历：`almanacDay()`（服务端定"今天"，与客户端时区无关）
 * - 个人运程：`dailyFortune({birth_date, birth_hour})` —— 需要先在「我的信息」填出生日期
 * - 打卡：只记本地（日期 + 连续天数），不上传
 *
 * ## 单屏做法（2026-10-09）
 *
 * 黄历与运程本是**两段互不相关的信息**，竖排下来要两屏多。
 * 现用 `SegmentedTabs` 分段（黄历 / 运程），同一时刻只显示一段；
 * 段内容放唯一的弹性区 `FitSlot weight={1}`，不再滚动。
 * 五宫运程条目多，用 `FoldList`（页内 3 条 + 「更多」浮层看全部）；
 * 推算依据这类长说明收进 `InfoPopup`，不占版面。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { AlmanacDay, DailyFortune } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, Divider, KeyValueRow } from '@/components/Card';
import { Tag } from '@/components/Chip';
import { FoldList } from '@/components/FoldList';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { todayISODate, weekdayLabel } from '@/lib/date';
import { loadCheckin, loadProfile, markMorningRead } from '@/lib/profile';
import { useAsync } from '@/lib/useAsync';
import { colors, radius, space } from '@/theme/tokens';

interface MorningData {
  today: string;
  almanac: AlmanacDay;
  fortune: DailyFortune | null;
  nickname: string;
  streak: number;
  alreadyRead: boolean;
}

type Segment = 'almanac' | 'fortune';

const SEGMENTS = [
  { key: 'almanac' as const, label: '黄历' },
  { key: 'fortune' as const, label: '运程' },
];

export default function MorningScreen(): React.JSX.Element {
  const router = useRouter();
  const [segment, setSegment] = useState<Segment>('fortune');

  const load = useCallback(async (): Promise<MorningData> => {
    const client = getApiClient();
    const today = todayISODate();
    const [almanac, profile, prevCheckin] = await Promise.all([
      client.almanacDay(),
      loadProfile(),
      loadCheckin(),
    ]);
    const fortune = profile
      ? await client.dailyFortune({
          birth_date: profile.birthDate,
          birth_hour: profile.birthHour,
        })
      : null;
    const checkin = await markMorningRead(today);
    return {
      today,
      almanac,
      fortune,
      nickname: profile?.nickname ?? '',
      streak: checkin.streak,
      alreadyRead: prevCheckin.lastDate === today,
    };
  }, []);

  const { data, loading, error, reload } = useAsync(load, []);

  return (
    <Screen>
      <PageHeader
        title="每日早报"
        back
        helpTopic="morning"
        tone="light"
        onRefresh={reload}
        refreshing={loading && data !== null}
      />

      {error ? (
        <Banner tone="error" title="早报没取到">
          {error}
        </Banner>
      ) : null}

      {data ? (
        <>
          <BriefingHeader
            today={data.today}
            lunar={data.almanac.facts.lunar}
            nickname={data.nickname}
            streak={data.streak}
            alreadyRead={data.alreadyRead}
          />

          <SegmentedTabs items={SEGMENTS} value={segment} onChange={setSegment} />

          {/* 唯一弹性区：黄历 / 运程 二选一，同一时刻只占一份空间 */}
          <FitSlot weight={1}>
            {segment === 'almanac' ? (
              <AlmanacPanel almanac={data.almanac} />
            ) : data.fortune ? (
              <FortunePanel fortune={data.fortune} />
            ) : (
              <Card title="个人运程未解锁">
                <AppText size="sm" color="textSecondary" style={styles.cardIntro}>
                  填一下出生日期，早报就能按你的日主算当日运程（只存手机本地）。
                </AppText>
                <Button
                  label="去设置我的信息"
                  variant="secondary"
                  onPress={() => router.push('/profile')}
                />
              </Card>
            )}
          </FitSlot>

          <AppText size="xs" color="muted" center style={styles.disclaimer}>
            黄历与运程属传统文化娱乐参考，不构成决策建议
          </AppText>
        </>
      ) : loading ? (
        <Card title="正在生成早报…">
          <AppText size="sm" color="muted">
            排黄历、算运程，马上就好。
          </AppText>
        </Card>
      ) : null}
    </Screen>
  );
}

// ============================================================================
// 报头：日期 + 打卡连击（紧凑单行，给下方分段让出高度）
// ============================================================================

function BriefingHeader({
  today,
  lunar,
  nickname,
  streak,
  alreadyRead,
}: {
  today: string;
  lunar: string;
  nickname: string;
  streak: number;
  alreadyRead: boolean;
}): React.JSX.Element {
  return (
    <View style={styles.briefRow}>
      <View style={styles.briefMain}>
        <AppText size="xs" color="textSecondary" track="wide">
          DAILY BRIEFING · {weekdayLabel(today)}
        </AppText>
        <AppText size="lg" weight="bold" numberOfLines={1} style={styles.briefTitle}>
          {today.slice(5).replace('-', '月')}日
          {nickname ? `，${nickname}` : ''}，早安
        </AppText>
        <AppText size="xs" color="textSecondary" numberOfLines={1}>
          农历{lunar}
          {alreadyRead ? ' · 今日已打卡' : ''}
        </AppText>
      </View>
      <View style={styles.streakBadge}>
        <Ionicons name="flame" size={22} color={colors.cinnabar} />
        <AppText size="lg" weight="bold" color="cinnabar">
          {streak}
        </AppText>
        <AppText size="xs" color="muted">
          连击天
        </AppText>
      </View>
    </View>
  );
}

// ============================================================================
// 个人运程：开局 + 五宫 + BUFF
// ============================================================================

function FortunePanel({ fortune }: { fortune: DailyFortune }): React.JSX.Element {
  const f = fortune.facts;
  const [open, setOpen] = useState(false);

  return (
    <>
      <Card title={`今日开局 · ${f.day_ganzhi}日`}>
        <AppText size="sm" numberOfLines={3} style={styles.summary}>
          {fortune.tradition.summary}
        </AppText>
        <View style={styles.focusRow}>
          <Ionicons name="checkmark-circle" size={18} color={colors.jade} />
          <AppText size="sm" weight="medium" numberOfLines={1} style={styles.focusText}>
            {f.focus_yi}
          </AppText>
        </View>
        <View style={styles.focusRow}>
          <Ionicons name="alert-circle" size={18} color={colors.cinnabar} />
          <AppText size="sm" weight="medium" numberOfLines={1} style={styles.focusText}>
            {f.focus_ji}
          </AppText>
        </View>

        {/* 推算依据（日主/十神）不长，但属"解释性"内容 —— 收进弹层不占版面 */}
        <Pressable
          onPress={() => setOpen(true)}
          accessibilityRole="button"
          accessibilityLabel="运程的推算依据"
          style={styles.link}
        >
          <Ionicons name="information-circle-outline" size={15} color={colors.primary} />
          <AppText size="sm" color="primary" style={styles.linkText}>
            推算依据
          </AppText>
        </Pressable>
        <InfoPopup
          visible={open}
          onClose={() => setOpen(false)}
          title="运程怎么算"
          subtitle="日主 × 当日干支"
        >
          <AppText size="sm" color={colors.text} style={styles.popupBody}>
            日主{f.day_master}（{f.day_master_element}）· 日干{f.stem_shishen} · 日支藏
            {f.branch_shishen}
          </AppText>
          <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
            五宫星级 = 3 ＋ 天干命中 ＋ 地支命中 － 受制，钳制 1–5；规则写死在计算层，可复现。
          </AppText>
        </InfoPopup>
      </Card>

      <Card title="五宫运程">
        <FoldList
          items={f.domains}
          max={3}
          keyOf={(d) => d.name}
          moreTitle="五宫运程"
          tone="light"
          renderItem={(d) => (
            <View>
              <View style={styles.domainRow}>
                <AppText size="sm" weight="medium" style={styles.domainName}>
                  {d.name}
                </AppText>
                <AppText size="sm" color="cinnabar" style={styles.stars}>
                  {'★'.repeat(d.stars)}
                  <AppText size="sm" color="muted">
                    {'☆'.repeat(5 - d.stars)}
                  </AppText>
                </AppText>
                <Tag
                  label={d.tag}
                  tone={d.tag === '宜' ? 'good' : d.tag === '慎' ? 'bad' : 'neutral'}
                />
              </View>
              <AppText size="xs" color="muted" numberOfLines={1} style={styles.domainReason}>
                {d.reason}
              </AppText>
            </View>
          )}
        />
      </Card>

      <Card title="今日 BUFF">
        <View style={styles.buffGrid}>
          <AppText size="sm">
            幸运色 {f.lucky.color}（{f.lucky.color_element}）
          </AppText>
          <AppText size="sm">幸运数 {f.lucky.numbers.join(' · ')}</AppText>
          <AppText size="sm">吉方 {f.lucky.direction}</AppText>
          <AppText size="sm">吉时 {f.lucky.hours.join('、')}</AppText>
        </View>
      </Card>
    </>
  );
}

// ============================================================================
// 黄历
// ============================================================================

function AlmanacPanel({ almanac }: { almanac: AlmanacDay }): React.JSX.Element {
  const f = almanac.facts;
  return (
    <Card title="今日黄历">
      <View style={styles.yijiRow}>
        <View style={styles.yijiCol}>
          <AppText size="sm" weight="semibold" color="jade" style={styles.yijiTitle}>
            宜
          </AppText>
          {f.yi.slice(0, 6).map((y) => (
            <AppText key={y} size="sm" style={styles.yijiItem}>
              · {y}
            </AppText>
          ))}
        </View>
        <View style={styles.yijiCol}>
          <AppText size="sm" weight="semibold" color="cinnabar" style={styles.yijiTitle}>
            忌
          </AppText>
          {f.ji.slice(0, 6).map((j) => (
            <AppText key={j} size="sm" style={styles.yijiItem}>
              · {j}
            </AppText>
          ))}
        </View>
      </View>
      <Divider />
      <KeyValueRow label="干支" value={`${f.gan_zhi.year} ${f.gan_zhi.month} ${f.gan_zhi.day}`} />
      <KeyValueRow label="值日" value={`${f.tian_shen.name}（${f.tian_shen.type}）`} />
      <KeyValueRow label="冲煞" value={`${f.chong.desc} · 煞${f.chong.sha_direction}`} last />
    </Card>
  );
}

const styles = StyleSheet.create({
  cardIntro: { marginBottom: space[3], lineHeight: 20 },
  disclaimer: { marginTop: space[2] },
  briefRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.primary,
    padding: space[3],
    marginBottom: space[2],
  },
  briefMain: { flex: 1 },
  briefTitle: { marginTop: 1, marginBottom: 1 },
  streakBadge: {
    alignItems: 'center',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.lg,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    minWidth: 64,
  },
  summary: { lineHeight: 20, marginBottom: space[2] },
  focusRow: { flexDirection: 'row', alignItems: 'center', gap: space[2], marginBottom: space[2] },
  focusText: { flex: 1 },
  link: { flexDirection: 'row', alignItems: 'center', marginTop: space[1] },
  linkText: { marginLeft: space[2] },
  popupBody: { lineHeight: 22 },
  domainRow: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  domainName: { width: 44 },
  stars: { flex: 1, letterSpacing: 2 },
  domainReason: { marginTop: 2 },
  buffGrid: { gap: space[2] },
  yijiRow: { flexDirection: 'row', gap: space[4] },
  yijiCol: { flex: 1 },
  yijiTitle: { marginBottom: space[1] },
  yijiItem: { lineHeight: 22 },
});
