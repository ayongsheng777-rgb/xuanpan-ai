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
 *
 * ## 单屏（2026-10-09 用户要求：一屏显示完、不滑动）
 *
 * 「查黄历 / 择吉日」用页面分段标签切换，同一时刻只渲染一边。
 * 每边内部再分段，把一屏装不下的部分拆开：
 *
 *   查黄历：盘面 / 宜忌 / 神煞 / 说明
 *   择吉日：条件 / 结果
 *
 * 候选日**数量由数据决定**，页内只放前 1 条（候选卡较高），其余走
 * `FoldList` 的「更多」浮层；长说明（流派口径、被排除的原因、不确定性）
 * 收进 `InfoPopup`。数据一字不改。
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
import { FoldList } from '@/components/FoldList';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, FitSlots, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { isToday, rangeFrom, shiftDays, todayISODate, weekdayLabel } from '@/lib/date';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type Mode = 'almanac' | 'zeri';
/** 查黄历内部分段 */
type AlmanacTab = 'pan' | 'yiji' | 'shen' | 'note';
/** 择吉日内部分段 */
type ZeriTab = 'cond' | 'result';

const ZODIAC = ['鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'] as const;

// ==========================================================================
// 页面
// ==========================================================================

export default function AlmanacScreen(): React.JSX.Element {
  const [mode, setMode] = useState<Mode>('almanac');

  return (
    <Screen>
      <PageHeader title="黄历择日" back helpTopic="almanac" tone="light" />

      <SegmentedTabs<Mode>
        items={[
          { key: 'almanac', label: '查黄历' },
          { key: 'zeri', label: '择吉日' },
        ]}
        value={mode}
        onChange={setMode}
      />

      <FitSlot weight={1}>{mode === 'almanac' ? <AlmanacPane /> : <ZeriPane />}</FitSlot>

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
  const [tab, setTab] = useState<AlmanacTab>('pan');
  const [popup, setPopup] = useState<'note' | null>(null);

  const load = useCallback((): Promise<AlmanacDay> => getApiClient().almanacDay(date), [date]);
  const { data, loading, error, reload } = useAsync(load, [date]);

  return (
    <FitSlots>
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

      <FitSlot weight={1} style={styles.col}>
        {data ? (
          <>
            <SegmentedTabs<AlmanacTab>
              items={[
                { key: 'pan', label: '盘面' },
                { key: 'yiji', label: '宜忌' },
                { key: 'shen', label: '神煞' },
                { key: 'note', label: '说明' },
              ]}
              value={tab}
              onChange={setTab}
              variant="underline"
            />

            <FitSlot weight={1}>
              {tab === 'pan' ? <PanCard day={data} /> : null}
              {tab === 'yiji' ? <YiJiCard day={data} /> : null}
              {tab === 'shen' ? <ShenShaCard day={data} /> : null}
              {tab === 'note' ? <NoteCard day={data} onOpenNote={() => setPopup('note')} /> : null}
            </FitSlot>
          </>
        ) : loading ? (
          <EmptyState title="计算中…" hint="正在从服务端取这一天的黄历" />
        ) : (
          <EmptyState title="还没有结果" hint="选好日期后会自动查询" />
        )}
      </FitSlot>

      {data ? (
        <InfoPopup
          visible={popup === 'note'}
          onClose={() => setPopup(null)}
          title="说明与不确定性"
          subtitle="流派口径 · 本版未覆盖项"
        >
          <AppText size="sm" color={colors.text} style={styles.popupBody}>
            {data.tradition.summary}
          </AppText>
          <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
            {data.tradition.note}
          </AppText>
          {/* 建除十二神在交节日存在口径差，内核会留一条说明 —— 属于已知差异，
              必须展示，否则用户会以为是算错了。 */}
          {data.facts.rule_consistency.map((line) => (
            <AppText key={line} size="sm" color={colors.textSecondary} style={styles.popupBody}>
              · {line}
            </AppText>
          ))}
          <UncertaintyList items={data.tradition.uncertainties} />
        </InfoPopup>
      ) : null}
    </FitSlots>
  );
}

function PanCard({ day }: { day: AlmanacDay }): React.JSX.Element {
  const f = day.facts;
  return (
    <Card title="盘面">
      <KeyValueRow label="公历" value={f.solar_date} />
      <KeyValueRow label="农历" value={f.lunar} />
      <KeyValueRow
        label="干支"
        value={`${f.gan_zhi.year}年 ${f.gan_zhi.month}月 ${f.gan_zhi.day}日`}
      />
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
      <KeyValueRow label="冲煞" value={`${f.chong.desc} · 煞${f.chong.sha_direction}`} last />
    </Card>
  );
}

/** 宜 / 忌 —— 成对呈现，语义等价（一侧有淡底、另一侧只有描边会被读成"轻重不同"） */
function YiJiCard({ day }: { day: AlmanacDay }): React.JSX.Element {
  const f = day.facts;
  return (
    <Card title="宜 · 忌">
      <AppText size="xs" color="textSecondary" style={styles.cloudLabel}>
        宜
      </AppText>
      {f.yi.length ? (
        <WordCloud words={f.yi} tone="good" />
      ) : (
        <AppText size="sm" color="muted">
          （无）
        </AppText>
      )}
      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary" style={styles.cloudLabel}>
        忌
      </AppText>
      {f.ji.length ? (
        <WordCloud words={f.ji} tone="bad" />
      ) : (
        <AppText size="sm" color="muted">
          （无）
        </AppText>
      )}
    </Card>
  );
}

function ShenShaCard({ day }: { day: AlmanacDay }): React.JSX.Element {
  const f = day.facts;
  if (!f.ji_shen.length && !f.xiong_sha.length) {
    return (
      <Card title="吉神 · 凶煞">
        <AppText size="sm" color="muted">
          本日无吉神凶煞记载
        </AppText>
      </Card>
    );
  }
  return (
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
      <KeyValueRow label="彭祖百忌" value={`${f.peng_zu.gan} · ${f.peng_zu.zhi}`} last />
    </Card>
  );
}

function NoteCard({
  day,
  onOpenNote,
}: {
  day: AlmanacDay;
  onOpenNote: () => void;
}): React.JSX.Element {
  return (
    <Card title="说明">
      <AppText size="sm" style={styles.summaryText}>
        {day.tradition.summary}
      </AppText>
      <AppText size="xs" color="muted" style={styles.note}>
        {day.tradition.note}
      </AppText>
      {day.facts.rule_consistency.length ? (
        <View style={styles.consistency}>
          {day.facts.rule_consistency.map((line) => (
            <AppText key={line} size="xs" color="muted">
              · {line}
            </AppText>
          ))}
        </View>
      ) : null}
      {day.tradition.uncertainties.length ? (
        <Button
          label={`不确定性说明（${day.tradition.uncertainties.length} 条）`}
          variant="ghost"
          style={styles.paneBtn}
          onPress={onOpenNote}
        />
      ) : null}
    </Card>
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
  const [tab, setTab] = useState<ZeriTab>('cond');
  const [popup, setPopup] = useState<'rules' | null>(null);

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
    if (r) {
      setResult(r);
      // 筛选成功 → 跳到「结果」段
      setTab('result');
    }
  }, [submit, event, start, end, zodiac]);

  const items = useMemo(
    () =>
      (events.data?.events ?? []).map((e) => ({ key: e.event, label: e.label })),
    [events.data],
  );

  const schools = events.data?.schools ?? [];
  const unverified = schools.flatMap((s) => s.unverified ?? []);

  return (
    <FitSlots>
      <SegmentedTabs<ZeriTab>
        items={[
          { key: 'cond', label: '条件' },
          { key: 'result', label: '结果' },
        ]}
        value={tab}
        onChange={setTab}
        variant="underline"
      />

      <FitSlot weight={1} style={styles.col}>
        {tab === 'cond' ? (
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
          </>
        ) : result ? (
          <ZeriResultView result={result} onOpenRules={() => setPopup('rules')} />
        ) : (
          <EmptyState title="还没有筛选结果" hint="到「条件」段选好事项与区间，点「开始筛选」" />
        )}
      </FitSlot>

      {result ? (
        <InfoPopup
          visible={popup === 'rules'}
          onClose={() => setPopup(null)}
          title="规则说明 · 被排除的原因"
          subtitle={`共排除 ${result.facts.excluded_count} 天`}
        >
          {Object.keys(result.facts.excluded_reasons).length ? (
            <>
              <AppText size="xs" color="muted" style={styles.popupBody}>
                同一日可命中多项，故各项之和会大于「排除」的天数。
              </AppText>
              {Object.entries(result.facts.excluded_reasons)
                .sort((a, b) => b[1] - a[1])
                .map(([kind, n]) => (
                  <KeyValueRow key={kind} label={kind} value={`${n} 天`} />
                ))}
            </>
          ) : (
            <AppText size="sm" color="muted" style={styles.popupBody}>
              没有被排除的日子。
            </AppText>
          )}

          <Divider style={styles.divider} />
          <AppText size="xs" color="textSecondary">
            规则说明
          </AppText>
          <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
            {result.tradition.note}
          </AppText>

          {unverified.length ? (
            <Banner tone="info" title="本版未覆盖">
              <AppText size="sm">{unverified.join('；')}</AppText>
            </Banner>
          ) : null}

          <UncertaintyList items={result.tradition.uncertainties} />
        </InfoPopup>
      ) : null}
    </FitSlots>
  );
}

function ZeriResultView({
  result,
  onOpenRules,
}: {
  result: ZeriResultResponse;
  onOpenRules: () => void;
}): React.JSX.Element {
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
        <KeyValueRow label="排除" value={`${facts.excluded_count} 天`} last />
      </Card>

      {/* 候选卡较高（含日辰/值日/冲煞/命中宜项），故页内只放 1 条；
          其余走「更多」浮层。数据一条不少。 */}
      {facts.candidates.length ? (
        <FoldList
          items={facts.candidates}
          max={1}
          keyOf={(c) => c.solar_date}
          moreTitle="全部候选日"
          renderItem={(c, i) => <CandidateCard candidate={c} first={i === 0} />}
        />
      ) : (
        <Card>
          <EmptyState
            title="本区间没有候选日"
            hint="这是筛选结果，不等于「绝无吉日」。可放宽区间或换一件事再试。"
          />
        </Card>
      )}

      <Button label="规则说明 · 被排除的原因" variant="ghost" onPress={onOpenRules} />
    </>
  );
}

function CandidateCard({
  candidate: c,
  first,
}: {
  candidate: ZeriResultResponse['facts']['candidates'][number];
  first: boolean;
}): React.JSX.Element {
  return (
    <Card highlight={first}>
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
          last
        />
      ) : null}
    </Card>
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
  col: { gap: space[2] },
  disclaimer: { marginTop: space[1] },
  divider: { marginVertical: space[2] },
  note: { marginTop: space[1], marginBottom: space[2] },
  retry: { marginTop: space[3] },
  consistency: { marginTop: space[2] },
  summaryText: { lineHeight: 22 },
  popupBody: { lineHeight: 22 },
  paneBtn: { marginTop: space[3] },
  cloudLabel: { marginBottom: space[2] },

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
