/**
 * 黄历与择日 —— 从「查某天宜忌」到「为某件事挑日子」。
 *
 * 两件事放同一页的理由：它们是同一个问题的正反两面。用户要么先有日子
 * （「这天行不行」），要么先有事（「哪几天行」）。分开做成两个入口，
 * 会逼用户在两个页面之间来回跳，而它们共享全部上下文（日期、事件、属相）。
 *
 * **本页不做任何吉凶判断**：一切都是服务端算出来的，这里只负责如实呈现，
 * 并把 `uncertainties`（流派差异、本版未覆盖项）一并显示。
 * 对应 RULE-001 / RULE-005 —— 界面不藏规则，也不自造规则。
 */

import { Ionicons } from '@expo/vector-icons';
import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { AlmanacDay, ZeriEventsResponse, ZeriResultResponse } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, Divider, EmptyState, KeyValueRow } from '@/components/Card';
import { Chip } from '@/components/Chip';
import { Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { isToday, rangeFrom, shiftDays, todayISODate, weekdayLabel } from '@/lib/date';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type Mode = 'almanac' | 'zeri';

const ZODIAC = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'] as const;

// ==========================================================================
// 页面
// ==========================================================================

export default function AlmanacScreen(): React.JSX.Element {
  const [mode, setMode] = useState<Mode>('almanac');

  return (
    <Screen scroll>
      <SegmentedTabs<Mode>
        items={[
          { key: 'almanac', label: '查黄历' },
          { key: 'zeri', label: '择吉日' },
        ]}
        value={mode}
        onChange={setMode}
        variant="underline"
      />

      <View style={styles.body}>
        {mode === 'almanac' ? <AlmanacPane /> : <ZeriPane />}
      </View>

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        黄历与择日属传统民俗规则，各历书口径存在差异；此处仅供参考
      </AppText>
    </Screen>
  );
}

// ==========================================================================
// 一、查黄历
// ==========================================================================

function AlmanacPane(): React.JSX.Element {
  const [date, setDate] = useState(todayISODate());

  const load = useCallback((): Promise<AlmanacDay> => getApiClient().almanacDay(date), [date]);
  const { data, loading, error, reload } = useAsync(load, [date]);

  return (
    <>
      <Card title="选择日期">
        <View style={styles.stepper}>
          <Stepper label="−1 天" onPress={() => setDate((d) => shiftDays(d, -1))} />
          <View style={styles.stepperValue}>
            <AppText size="lg" weight="semibold" color="primary">
              {date}
            </AppText>
            <AppText size="xs" color="muted">
              {weekdayLabel(date)}
            </AppText>
          </View>
          <Stepper label="+1 天" onPress={() => setDate((d) => shiftDays(d, 1))} />
        </View>
        <View style={styles.quickRow}>
          <Chip label="今天" onPress={() => setDate(todayISODate())} active={isToday(date)} />
          <Chip label="明天" onPress={() => setDate(shiftDays(todayISODate(), 1))} />
          <Chip label="+7 天" onPress={() => setDate(shiftDays(date, 7))} />
          <Chip label="+30 天" onPress={() => setDate(shiftDays(date, 30))} />
        </View>
      </Card>

      {error ? (
        <Banner tone="error" title="查询失败">
          <AppText size="sm">{error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={reload} />
        </Banner>
      ) : null}

      {loading && !data ? (
        <Card>
          <AppText size="sm" color="muted">
            计算中…
          </AppText>
        </Card>
      ) : null}

      {data ? <AlmanacResult day={data} /> : null}
    </>
  );
}

function AlmanacResult({ day }: { day: AlmanacDay }): React.JSX.Element {
  const f = day.facts;
  const tradeoffs = day.tradition.uncertainties;

  return (
    <>
      <Card title="盘面">
        <KeyValueRow label="公历" value={f.solar_date} />
        <KeyValueRow label="农历" value={f.lunar} />
        <KeyValueRow
          label="干支"
          value={`${f.gan_zhi.year}年 ${f.gan_zhi.month}月 ${f.gan_zhi.day}日`}
        />
        <Divider style={styles.divider} />
        <KeyValueRow label="建除" value={f.jian_chu} />
        <KeyValueRow label="二十八宿" value={`${f.xiu.name}（${f.xiu.luck}）`} />
        <KeyValueRow
          label="值日天神"
          value={
            <AppText size="md" color={f.tian_shen.is_huang_dao ? 'jade' : 'cinnabar'}>
              {`${f.tian_shen.name}（${f.tian_shen.type}·${f.tian_shen.luck}）`}
            </AppText>
          }
        />
        <KeyValueRow label="冲煞" value={`${f.chong.desc} · 煞${f.chong.sha_direction}`} />
      </Card>

      <Card title="宜">
        {f.yi.length ? (
          <WordCloud words={f.yi} tone="good" />
        ) : (
          <AppText size="sm" color="muted">
            （无）
          </AppText>
        )}
      </Card>

      <Card title="忌">
        {f.ji.length ? (
          <WordCloud words={f.ji} tone="bad" />
        ) : (
          <AppText size="sm" color="muted">
            （无）
          </AppText>
        )}
      </Card>

      {f.ji_shen.length || f.xiong_sha.length ? (
        <Card title="吉神 · 凶煞">
          {f.ji_shen.length ? (
            <KeyValueRow
              label="吉神"
              value={
                <AppText size="md" color="jade">
                  {f.ji_shen.join('、')}
                </AppText>
              }
            />
          ) : null}
          {f.xiong_sha.length ? (
            <KeyValueRow
              label="凶煞"
              value={
                <AppText size="md" color="cinnabar">
                  {f.xiong_sha.join('、')}
                </AppText>
              }
            />
          ) : null}
          <Divider style={styles.divider} />
          <KeyValueRow label="彭祖百忌" value={`${f.peng_zu.gan} · ${f.peng_zu.zhi}`} />
        </Card>
      ) : null}

      <Card title="说明">
        <AppText size="sm">{day.tradition.summary}</AppText>
        <AppText size="xs" color="muted" style={styles.note}>
          {day.tradition.note}
        </AppText>
        {/* 建除十二神在交节日存在口径差，内核会留一条说明 —— 属于已知差异，
            必须展示，否则用户会以为是算错了。 */}
        {f.rule_consistency.length ? (
          <View style={styles.consistency}>
            {f.rule_consistency.map((line) => (
              <AppText key={line} size="xs" color="muted">
                · {line}
              </AppText>
            ))}
          </View>
        ) : null}
      </Card>

      <UncertaintyList items={tradeoffs} />
    </>
  );
}

// ==========================================================================
// 二、择吉日
// ==========================================================================

function ZeriPane(): React.JSX.Element {
  const client = getApiClient();
  const loadEvents = useCallback((): Promise<ZeriEventsResponse> => client.zeriEvents(), [client]);
  const events = useAsync(loadEvents, []);

  const [event, setEvent] = useState<string>('jiaqu');
  const [zodiac, setZodiac] = useState<string | null>(null);

  // 区间锚点**只取一次**「今天」。分两处各取一次，两次之间存在一个跨天窗口
  // （极窄但存在），一旦跨过去就会得到一个起始属旧日、结束属新日的区间 ——
  // 而界面上完全看不出哪里不对。
  const initialRange = useMemo(() => rangeFrom(todayISODate(), 60), []);
  const [start, setStart] = useState(initialRange[0]);
  const [end, setEnd] = useState(initialRange[1]);

  /** 快捷区间：同样只取一次锚点 */
  const applyRange = useCallback((days: number) => {
    const [s, e] = rangeFrom(todayISODate(), days);
    setStart(s);
    setEnd(e);
  }, []);

  const submit = useSubmit(client.zeriSelect);
  const [result, setResult] = useState<ZeriResultResponse | null>(null);

  const run = useCallback(async () => {
    const r = await submit.run({
      event,
      start,
      end,
      limit: 10,
      shengxiao: zodiac,
    });
    if (r) setResult(r);
  }, [submit, event, start, end, zodiac]);

  const items = useMemo(
    () =>
      (events.data?.events ?? []).map((e) => ({ key: e.event, label: e.label })),
    [events.data],
  );

  const schools = events.data?.schools ?? [];
  const unverified = schools.flatMap((s) => s.unverified ?? []);

  return (
    <>
      <Card title="要择什么事">
        {events.loading && !events.data ? (
          <AppText size="sm" color="muted">
            读取事件清单…
          </AppText>
        ) : events.error ? (
          <Banner tone="error" title="读取失败">
            <AppText size="sm">{events.error}</AppText>
          </Banner>
        ) : (
          <SegmentedTabs<string>
            items={items}
            value={event}
            onChange={setEvent}
            variant="underline"
          />
        )}
      </Card>

      <Card title="日期区间">
        <DateRow label="起始" value={start} onChange={setStart} />
        <DateRow label="结束" value={end} onChange={setEnd} />
        <View style={styles.quickRow}>
          <Chip label="未来 30 天" onPress={() => applyRange(30)} />
          <Chip label="未来 90 天" onPress={() => applyRange(90)} />
          <Chip label="未来 180 天" onPress={() => applyRange(180)} />
        </View>
      </Card>

      <Card title="当事人属相（可选）">
        <AppText size="xs" color="muted" style={styles.note}>
          填了会排除冲该属相的日子；不填则不按属相筛。
        </AppText>
        <View style={styles.quickRow}>
          <Chip label="不限" onPress={() => setZodiac(null)} active={zodiac === null} />
          {ZODIAC.map((z) => (
            <Chip key={z} label={z} onPress={() => setZodiac(z)} active={zodiac === z} />
          ))}
        </View>
      </Card>

      <Button
        label={submit.loading ? '筛选中…' : '开始筛选'}
        size="lg"
        disabled={submit.loading}
        onPress={run}
      />

      {submit.error ? (
        <Banner tone="error" title="筛选失败">
          <AppText size="sm">{submit.error}</AppText>
        </Banner>
      ) : null}

      {result ? <ZeriResultView result={result} /> : null}

      {unverified.length ? (
        <Banner tone="info" title="本版未覆盖">
          <AppText size="sm">{unverified.join('；')}</AppText>
        </Banner>
      ) : null}
    </>
  );
}

function ZeriResultView({ result }: { result: ZeriResultResponse }): React.JSX.Element {
  const { facts, tradition } = result;

  return (
    <>
      <Card title="筛选结果">
        <AppText size="md" weight="semibold" color="primary">
          {tradition.summary}
        </AppText>
        <Divider style={styles.divider} />
        <KeyValueRow label="事件" value={facts.event_label} />
        <KeyValueRow
          label="区间"
          value={`${facts.range.start} ~ ${facts.range.end}（${facts.range.days_scanned} 天）`}
        />
        <KeyValueRow
          label="候选"
          value={
            <AppText size="md" color="jade">
              {`${facts.candidate_count} 天`}
            </AppText>
          }
        />
        <KeyValueRow label="排除" value={`${facts.excluded_count} 天`} />
        <KeyValueRow label="流派" value={tradition.school_name} />
      </Card>

      {facts.candidates.length ? (
        facts.candidates.map((c, i) => (
          // 排在第一位的即「首选」—— 用下标判定，避免再取一次 candidates[0]
          // （noUncheckedIndexedAccess 下那次取值本身就要处理"可能为空"，
          //  而此刻已在 length 分支内，多一次取值只会多一处要解释的假分支）
          <Card key={c.solar_date} highlight={i === 0}>
            <View style={styles.candHead}>
              <View>
                <AppText size="lg" weight="bold" color="primary">
                  {c.solar_date}
                </AppText>
                <AppText size="xs" color="muted">
                  {c.weekday} · {c.lunar}
                </AppText>
              </View>
              <View style={[styles.grade, gradeStyle(c.grade)]}>
                <AppText size="sm" weight="semibold" color="onPrimary">
                  {c.grade} · {c.score} 分
                </AppText>
              </View>
            </View>
            <Divider style={styles.divider} />
            <KeyValueRow
              label="日辰"
              value={`${c.day_gan_zhi}日 · ${c.jian_chu}日 · ${c.xiu.name}宿（${c.xiu.luck}）`}
            />
            <KeyValueRow
              label="值日"
              value={
                <AppText size="md" color={c.tian_shen.type === '黄道' ? 'jade' : 'cinnabar'}>
                  {`${c.tian_shen.name}（${c.tian_shen.type}）`}
                </AppText>
              }
            />
            <KeyValueRow label="冲煞" value={`冲${c.chong_shengxiao} · 煞${c.sha_direction}`} />
            {c.matched_yi.length ? (
              <KeyValueRow
                label="命中宜项"
                value={
                  <AppText size="md" color="jade">
                    {c.matched_yi.join('、')}
                  </AppText>
                }
              />
            ) : null}
          </Card>
        ))
      ) : (
        <Card>
          <EmptyState
            title="本区间没有候选日"
            hint="这是筛选结果，不等于「绝无吉日」。可放宽区间或换一件事再试。"
          />
        </Card>
      )}

      {Object.keys(facts.excluded_reasons).length ? (
        <Card title="被排除的原因">
          <AppText size="xs" color="muted" style={styles.note}>
            同一日可命中多项，故各项之和会大于「排除」的天数。
          </AppText>
          {Object.entries(facts.excluded_reasons)
            .sort((a, b) => b[1] - a[1])
            .map(([kind, n]) => (
              <KeyValueRow key={kind} label={kind} value={`${n} 天`} />
            ))}
        </Card>
      ) : null}

      <Card title="规则说明">
        <AppText size="xs" color="muted">
          {tradition.note}
        </AppText>
      </Card>

      <UncertaintyList items={tradition.uncertainties} />
    </>
  );
}

// ==========================================================================
// 小组件
// ==========================================================================

function Stepper({ label, onPress }: { label: string; onPress: () => void }): React.JSX.Element {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.stepBtn, pressed && styles.pressed]}>
      <AppText size="sm" weight="medium" color="primary">
        {label}
      </AppText>
    </Pressable>
  );
}

function DateRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}): React.JSX.Element {
  return (
    <View style={styles.dateRow}>
      <AppText size="sm" color="textSecondary" style={styles.dateLabel}>
        {label}
      </AppText>
      <Pressable onPress={() => onChange(shiftDays(value, -7))} style={styles.dateBtn}>
        <Ionicons name="remove" size={14} color={colors.primary} />
      </Pressable>
      <View style={styles.dateValue}>
        <AppText size="sm" weight="medium">
          {value}
        </AppText>
      </View>
      <Pressable onPress={() => onChange(shiftDays(value, 7))} style={styles.dateBtn}>
        <Ionicons name="add" size={14} color={colors.primary} />
      </Pressable>
    </View>
  );
}

function WordCloud({
  words,
  tone,
}: {
  words: readonly string[];
  tone: 'good' | 'bad';
}): React.JSX.Element {
  return (
    <View style={styles.cloud}>
      {words.map((w) => (
        <View key={w} style={[styles.word, tone === 'good' ? styles.wordGood : styles.wordBad]}>
          <AppText size="sm" color={tone === 'good' ? 'jade' : 'cinnabar'}>
            {w}
          </AppText>
        </View>
      ))}
    </View>
  );
}

function gradeStyle(grade: string): { backgroundColor: string } {
  if (grade === '吉') return { backgroundColor: colors.jade };
  if (grade === '次吉') return { backgroundColor: colors.primary };
  if (grade === '平') return { backgroundColor: colors.muted };
  return { backgroundColor: colors.cinnabar };
}

const styles = StyleSheet.create({
  body: { marginTop: space[4] },
  disclaimer: { marginTop: space[4] },
  divider: { marginVertical: space[2] },
  note: { marginTop: space[1], marginBottom: space[2] },
  retry: { marginTop: space[3] },
  consistency: { marginTop: space[2] },

  stepper: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  stepperValue: { alignItems: 'center', flex: 1 },
  stepBtn: {
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },

  quickRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginTop: space[3] },
  pressed: { opacity: 0.7 },

  dateRow: { flexDirection: 'row', alignItems: 'center', gap: space[2], marginBottom: space[2] },
  dateLabel: { width: 36 },
  dateBtn: {
    width: 30,
    height: 30,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  dateValue: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[1] + 2,
    borderRadius: radius.sm,
    backgroundColor: alpha.primarySoft,
  },

  cloud: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2] },
  word: {
    paddingHorizontal: space[3],
    paddingVertical: space[1] + 2,
    borderRadius: radius.sm,
    borderWidth: 1,
  },
  wordGood: { borderColor: colors.jade, backgroundColor: alpha.jadeSoft },
  wordBad: { borderColor: colors.cinnabar, backgroundColor: alpha.cinnabarSoft },

  candHead: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  grade: { paddingHorizontal: space[3], paddingVertical: space[1], borderRadius: radius.pill },
});
