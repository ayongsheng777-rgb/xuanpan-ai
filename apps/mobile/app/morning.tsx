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
 */

import { Ionicons } from '@expo/vector-icons';
import { Stack, useRouter } from 'expo-router';
import React, { useCallback } from 'react';
import { StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { AlmanacDay, DailyFortune } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, Divider, KeyValueRow } from '@/components/Card';
import { Tag } from '@/components/Chip';
import { helpHeaderRight } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
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

export default function MorningScreen(): React.JSX.Element {
  const router = useRouter();

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
    <Screen scroll onRefresh={reload} refreshing={loading && data !== null}>
      <Stack.Screen options={{ title: '每日早报', headerRight: helpHeaderRight('morning') }} />

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
          {data.fortune ? (
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
          <AlmanacPanel almanac={data.almanac} />
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
// 报头：日期 + 打卡连击
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
    <Card highlight>
      <View style={styles.headerRow}>
        <View style={styles.headerMain}>
          <AppText size="xs" color="textSecondary" track="wide">
            DAILY BRIEFING · {weekdayLabel(today)}
          </AppText>
          <AppText size="xl" weight="bold" style={styles.dateTitle}>
            {today.slice(5).replace('-', '月')}日
            {nickname ? `，${nickname}` : ''}，早安
          </AppText>
          <AppText size="sm" color="textSecondary">
            农历{lunar}
          </AppText>
        </View>
        <View style={styles.streakBadge}>
          <Ionicons name="flame" size={26} color={colors.cinnabar} />
          <AppText size="lg" weight="bold" color="cinnabar">
            {streak}
          </AppText>
          <AppText size="xs" color="muted">
            连击天
          </AppText>
        </View>
      </View>
      {alreadyRead ? (
        <AppText size="xs" color="muted" style={styles.readHint}>
          今日已打卡 —— 运程每天只算一次，明早再来
        </AppText>
      ) : null}
    </Card>
  );
}

// ============================================================================
// 个人运程：开局 + 五宫 + BUFF
// ============================================================================

function FortunePanel({ fortune }: { fortune: DailyFortune }): React.JSX.Element {
  const f = fortune.facts;
  return (
    <>
      <Card title={`今日开局 · ${f.day_ganzhi}日`}>
        <AppText size="sm" style={styles.summary}>
          {fortune.tradition.summary}
        </AppText>
        <View style={styles.focusRow}>
          <Ionicons name="checkmark-circle" size={18} color={colors.jade} />
          <AppText size="sm" weight="medium" style={styles.focusText}>
            {f.focus_yi}
          </AppText>
        </View>
        <View style={styles.focusRow}>
          <Ionicons name="alert-circle" size={18} color={colors.cinnabar} />
          <AppText size="sm" weight="medium" style={styles.focusText}>
            {f.focus_ji}
          </AppText>
        </View>
        <AppText size="xs" color="muted" style={styles.calcNote}>
          日主{f.day_master}（{f.day_master_element}）· 日干{f.stem_shishen} · 日支藏{f.branch_shishen}
        </AppText>
      </Card>

      <Card title="五宫运程">
        {f.domains.map((d, i) => (
          <View key={d.name}>
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
              <Tag label={d.tag} tone={d.tag === '宜' ? 'good' : d.tag === '慎' ? 'bad' : 'neutral'} />
            </View>
            <AppText size="xs" color="muted" style={styles.domainReason}>
              {d.reason}
            </AppText>
            {i < f.domains.length - 1 ? <Divider /> : null}
          </View>
        ))}
      </Card>

      <Card title="今日 BUFF">
        <KeyValueRow label="幸运色" value={`${f.lucky.color}（${f.lucky.color_element}）`} />
        <KeyValueRow label="幸运数" value={f.lucky.numbers.join(' · ')} />
        <KeyValueRow label="吉方" value={f.lucky.direction} />
        <KeyValueRow label="吉时" value={f.lucky.hours.join('、')} last />
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
      <KeyValueRow
        label="值日"
        value={`${f.tian_shen.name}（${f.tian_shen.type}）`}
      />
      <KeyValueRow label="冲煞" value={`${f.chong.desc} · 煞${f.chong.sha_direction}`} last />
    </Card>
  );
}

const styles = StyleSheet.create({
  cardIntro: { marginBottom: space[3], lineHeight: 20 },
  disclaimer: { marginTop: space[2], marginBottom: space[4] },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  headerMain: { flex: 1 },
  dateTitle: { marginTop: space[1], marginBottom: space[1] },
  streakBadge: {
    alignItems: 'center',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.lg,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    minWidth: 76,
  },
  readHint: { marginTop: space[2] },
  summary: { lineHeight: 22, marginBottom: space[3] },
  focusRow: { flexDirection: 'row', alignItems: 'center', gap: space[2], marginBottom: space[2] },
  focusText: { flex: 1 },
  calcNote: { marginTop: space[2] },
  domainRow: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  domainName: { width: 44 },
  stars: { flex: 1, letterSpacing: 2 },
  domainReason: { marginTop: space[1], marginBottom: space[2] },
  yijiRow: { flexDirection: 'row', gap: space[4] },
  yijiCol: { flex: 1 },
  yijiTitle: { marginBottom: space[1] },
  yijiItem: { lineHeight: 22 },
});
