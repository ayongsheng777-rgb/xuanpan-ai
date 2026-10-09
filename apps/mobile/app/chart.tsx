/**
 * 命盘 —— 八字排盘。
 *
 * 流程：录入出生信息 → 实时排盘（`/calc/bazi` 预览）→ 落库 → 生成 AI 解读。
 *
 * 为什么"先预览再落库"：排盘是纯计算、无成本、可反复试，
 * 而落库会产生一个会话记录。让用户先在屏幕上看到四柱对不对，
 * 再决定要不要存 —— 这比"录完即存、存错了再删"省事得多。
 *
 * **本页不做任何旺衰/用神判断**：那些属流派规则，由计算层给出，
 * 此处只负责把结构化结果如实画出来（对应 RULE-001/005）。
 *
 * ## 单屏（2026-10-09 用户要求：一屏显示完、不滑动）
 *
 * 输入区固定在上方（高度恒定），结果收进分段标签：
 *   四柱 / 事实 / 传统 / 断卦 —— 同一时刻只显示一段，故一屏放得下。
 *
 * 其中「盘面事实」「传统分析」是**由数据决定长度**的长列表，
 * 「断卦」还带依据与不确定性清单 —— 三者一律收进 `InfoPopup` 点开看，
 * 不把版面拉长。四柱是本页唯一的"盘面"，作为弹性区。
 *
 * 数据一字不改：没算出来仍是「未定 / —」，不编造（RULE-003）。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useMemo, useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { BaziInput, DuanResponse, LayerPreview } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, Divider, EmptyState, KeyValueRow } from '@/components/Card';
import { Tag } from '@/components/Chip';
import { DuanCard, verdictTone } from '@/components/DuanCard';
import { FactList } from '@/components/FactList';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { useSubmit } from '@/lib/useAsync';
import { colors, radius, space } from '@/theme/tokens';

type Gender = 'male' | 'female';
type Calendar = 'solar' | 'lunar';

/** 结果分段 —— 同一时刻只渲染一段，是一屏装得下的关键 */
type ResultTab = 'pillars' | 'facts' | 'tradition' | 'duan';

const RESULT_TABS = [
  { key: 'pillars' as const, label: '四柱' },
  { key: 'facts' as const, label: '事实' },
  { key: 'tradition' as const, label: '传统' },
  { key: 'duan' as const, label: '断卦' },
];

/** 长内容浮层 —— 由数据决定长度的列表一律点开看，不占版面 */
type Popup = 'facts' | 'tradition' | 'duan' | 'uncertain' | null;

export default function ChartScreen(): React.JSX.Element {
  const router = useRouter();

  const [calendar, setCalendar] = useState<Calendar>('solar');
  const [gender, setGender] = useState<Gender>('male');
  const [year, setYear] = useState('1981');
  const [month, setMonth] = useState('9');
  const [day, setDay] = useState('14');
  const [hour, setHour] = useState('8');
  const [minute, setMinute] = useState('0');
  const [longitude, setLongitude] = useState('114.3');

  const [preview, setPreview] = useState<LayerPreview | null>(null);
  const [savedSessionId, setSavedSessionId] = useState<string | null>(null);
  /** 旺衰与运程倾向 —— 与排盘同批取回，见 onCalc 的说明 */
  const [duanResult, setDuanResult] = useState<DuanResponse | null>(null);
  /** 纯版面状态：结果分段与浮层，不影响任何计算 */
  const [tab, setTab] = useState<ResultTab>('pillars');
  const [popup, setPopup] = useState<Popup>(null);

  const calc = useSubmit(getApiClient().calcBazi);
  const duan = useSubmit(getApiClient().duanBazi);
  const save = useSubmit(getApiClient().patchInputs);
  const createSession = useSubmit(getApiClient().createSession);

  /** 组装请求体；数值校验放在这里，避免把 'abc' 发给后端换回一个 422 */
  const buildInput = useCallback((): BaziInput | null => {
    const y = Number(year);
    const mo = Number(month);
    const d = Number(day);
    const h = Number(hour);
    const mi = Number(minute || '0');
    if (![y, mo, d, h, mi].every(Number.isFinite)) return null;
    const lon = longitude.trim() === '' ? null : Number(longitude);
    return {
      year: y,
      month: mo,
      day: d,
      hour: h,
      minute: mi,
      calendar,
      gender,
      timezone: 'Asia/Shanghai',
      longitude: lon !== null && Number.isFinite(lon) ? lon : null,
    };
  }, [calendar, day, gender, hour, longitude, minute, month, year]);

  const onCalc = useCallback(async () => {
    const input = buildInput();
    if (!input) {
      calc.reset();
      return;
    }
    const result = await calc.run(input);
    if (result) {
      setPreview(result);
      setSavedSessionId(null);
      // 新盘面回到第一段，避免停在上一盘的"断卦"段看到空内容
      setTab('pillars');
      setPopup(null);
    }

    // 旺衰与运程倾向**与排盘一起**取回：两者都是本地确定性计算、零成本，
    // 而"排完盘还得再点一次，才知道这步运好不好"是没必要的额外一步 ——
    // 大运倾向正是排盘之后用户最想看到的那个结论。
    //
    // 与排盘**互相独立**：断卦失败只让那张卡片不出现，不影响四柱与盘面事实。
    // 若把两者绑成"全成全败"，一个次要能力的抖动会连带把主结果一起吞掉。
    const d = await duan.run(input);
    setDuanResult(d ?? null);
  }, [buildInput, calc, duan]);

  /** 落库：先建会话再写入八字输入，两步都成功才算成功 */
  const onSave = useCallback(async () => {
    const input = buildInput();
    if (!input) return;
    const created = await createSession.run({
      title: `${input.year}-${String(input.month).padStart(2, '0')}-${String(input.day).padStart(2, '0')} 命盘`,
    });
    if (!created) return;
    const patched = await save.run(created.session_id, { bazi: input });
    if (patched) setSavedSessionId(created.session_id);
  }, [buildInput, createSession, save]);

  const pillars = useMemo(() => {
    const b = preview?.facts?.['bazi'] as Record<string, unknown> | undefined;
    const p = b?.['pillars'] as Record<string, string> | undefined;
    if (!p) return null;
    return `${p['year'] ?? '—'} ${p['month'] ?? '—'} ${p['day'] ?? '—'} ${p['hour'] ?? '—'}`;
  }, [preview]);

  const busy = calc.loading || save.loading || createSession.loading;
  const err = calc.error ?? save.error ?? createSession.error;

  return (
    <Screen>
      <PageHeader
        title="八字命盘"
        back
        helpTopic="chart"
        tone="light"
        onRefresh={onCalc}
        refreshing={calc.loading}
      />

      {/* ---------- 输入区：固定高度，一屏内的恒定部分 ---------- */}
      <Card title="出生信息">
        <Row>
          <NumField label="年" value={year} onChange={setYear} width={96} />
          <NumField label="月" value={month} onChange={setMonth} />
          <NumField label="日" value={day} onChange={setDay} />
        </Row>
        <Row>
          <NumField label="时" value={hour} onChange={setHour} />
          <NumField label="分" value={minute} onChange={setMinute} />
          <NumField label="经度" value={longitude} onChange={setLongitude} width={104} />
        </Row>

        <AppText size="xs" color="muted" numberOfLines={1} style={styles.fieldHint}>
          经度用于真太阳时修正；留空则不修正
        </AppText>

        <View style={styles.genderRow}>
          <AppText size="sm" color="textSecondary">
            性别
          </AppText>
          <View style={styles.genderToggle}>
            <SegmentedTabs
              items={[
                { key: 'male', label: '男' },
                { key: 'female', label: '女' },
              ]}
              value={gender}
              onChange={(k) => setGender(k as Gender)}
            />
          </View>
        </View>

        <Button label="排盘" onPress={onCalc} loading={calc.loading} style={styles.submit} />
      </Card>

      {err ? (
        <Banner tone={calc.fixable ? 'warning' : 'error'} title={calc.fixable ? '输入需要修正' : '请求失败'}>
          {err}
        </Banner>
      ) : null}

      {/* ---------- 结果区：分段标签 + 唯一的弹性区 ---------- */}
      <FitSlot weight={1} style={styles.col}>
        {preview ? (
          <>
            <SegmentedTabs items={RESULT_TABS} value={tab} onChange={setTab} />

            <FitSlot weight={1}>
              {tab === 'pillars' ? (
                <Card title="四柱">
                  <AppText size="xl" weight="bold" color="primary" center style={styles.pillars}>
                    {pillars ?? '—'}
                  </AppText>
                  <KeyValueRow
                    label="日主"
                    emphasized
                    value={String((preview.facts['bazi']?.['day_master'] as string) ?? '未定')}
                  />
                  <KeyValueRow
                    label="节气"
                    value={String((preview.facts['bazi']?.['solar_term'] as string) ?? '未定')}
                    last
                  />

                  {preview.uncertainties.length > 0 ? (
                    <Button
                      label={`不确定性说明（${preview.uncertainties.length} 条）`}
                      variant="ghost"
                      onPress={() => setPopup('uncertain')}
                      style={styles.paneBtn}
                    />
                  ) : null}
                </Card>
              ) : null}

              {tab === 'facts' ? (
                <LongPane
                  title="盘面事实 · 只读"
                  hint="四柱、纳音、旬空、胎元命宫、五行分布、真太阳时等，由确定性代码算出。"
                  onOpen={() => setPopup('facts')}
                />
              ) : null}

              {tab === 'tradition' ? (
                <LongPane
                  title="传统分析 · 只读"
                  hint="十神、旺衰、喜用忌神等派生规则 —— 属流派规则，结论不唯一。"
                  onOpen={() => setPopup('tradition')}
                />
              ) : null}

              {tab === 'duan' ? (
                duanResult ? (
                  <Card title="断卦 · 旺衰与运程倾向">
                    {/* verdict 是「身强 / 身弱」，属**日主状态**而非吉凶，
                        故用中性主色，不染朱红 —— 把它说成凶兆等于替计算层下结论。 */}
                    <View style={styles.verdictRow}>
                      <AppText size="xxl" weight="bold" color="primary">
                        {duanResult.verdict}
                      </AppText>
                      <AppText size="xs" color="muted" style={styles.verdictLabel}>
                        日主状态 · {duanResult.school}
                      </AppText>
                    </View>
                    <Button
                      label="查看依据与大运倾向"
                      variant="secondary"
                      onPress={() => setPopup('duan')}
                      style={styles.paneBtn}
                    />
                  </Card>
                ) : (
                  <EmptyState
                    title="还没有断卦结果"
                    hint="点右上角刷新重新排盘，旺衰与运程倾向会与四柱一起取回"
                  />
                )
              ) : null}
            </FitSlot>
          </>
        ) : (
          <EmptyState title="还没有盘面" hint="填好出生信息，点「排盘」先在屏幕上核对四柱" />
        )}
      </FitSlot>

      {/* ---------- 底部动作 ---------- */}
      {preview ? (
        savedSessionId ? (
          <Card highlight>
            <AppText size="sm" weight="semibold" color="success">
              ✓ 已保存
            </AppText>
            <Button
              label="生成 AI 解读"
              icon={<Ionicons name="sparkles" size={18} color={colors.onPrimary} />}
              style={styles.aiBtn}
              onPress={() => router.push(`/report/${savedSessionId}`)}
            />
          </Card>
        ) : (
          <Button
            label="保存并生成 AI 解读"
            variant="secondary"
            onPress={onSave}
            loading={busy}
          />
        )
      ) : null}

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        以上内容属于传统文化娱乐/学习参考
      </AppText>

      {/* ---------- 长内容浮层（数据一字不改，只是换个地方看） ---------- */}
      {preview ? (
        <>
          <InfoPopup
            visible={popup === 'facts'}
            onClose={() => setPopup(null)}
            title="盘面事实 · 只读"
            subtitle="由确定性代码算出，AI 不得修改"
          >
            <FactList data={preview.facts['bazi'] ?? {}} omit={['pillars', 'warnings']} />
          </InfoPopup>

          <InfoPopup
            visible={popup === 'tradition'}
            onClose={() => setPopup(null)}
            title="传统分析 · 只读"
            subtitle="固定规则派生，不经手 AI"
          >
            <FactList data={preview.tradition['bazi'] ?? {}} omit={['warnings']} />
          </InfoPopup>

          <InfoPopup
            visible={popup === 'uncertain'}
            onClose={() => setPopup(null)}
            title="不确定性说明"
            subtitle={`${preview.uncertainties.length} 条`}
          >
            {preview.uncertainties.map((u, i) => (
              <AppText key={i} size="sm" color={colors.text} style={styles.popupBody}>
                · {u}
              </AppText>
            ))}
          </InfoPopup>
        </>
      ) : null}

      <InfoPopup
        visible={popup === 'duan'}
        onClose={() => setPopup(null)}
        title="断卦 · 旺衰与运程倾向"
        subtitle="依据、喜用忌神与大运逐运倾向"
      >
        {duanResult ? (
          <DuanCard duan={duanResult} verdictLabel="日主状态" title="断卦 · 旺衰与运程倾向">
            <BaziDuanDetail duan={duanResult} />
          </DuanCard>
        ) : null}
      </InfoPopup>
    </Screen>
  );
}

// ==========================================================================
// 结果分段：长列表入口
// ==========================================================================

/**
 * 「由数据决定长度」的分段 —— 页内只放一句话说明与入口，
 * 完整列表在 `InfoPopup` 里看。这样一屏的高度与数据条数**无关**。
 */
function LongPane({
  title,
  hint,
  onOpen,
}: {
  title: string;
  hint: string;
  onOpen: () => void;
}): React.JSX.Element {
  return (
    <Card title={title}>
      <AppText size="xs" color="muted" style={styles.paneHint}>
        {hint}
      </AppText>
      <Button label="点开查看完整列表" variant="secondary" onPress={onOpen} style={styles.paneBtn} />
    </Card>
  );
}

// ==========================================================================
// 断卦细节
// ==========================================================================

/** 从 detail 里取字符串数组；非数组或元素类型不符一律丢弃 */
function strList(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [];
}

/** 从 detail 里取「干支 → 倾向」映射（保持后端给的次序） */
function verdictMap(v: unknown): [string, string][] {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return [];
  return Object.entries(v as Record<string, unknown>).filter(
    (e): e is [string, string] => typeof e[1] === 'string',
  );
}

/**
 * 断卦细节：喜用 / 忌神 + 大运**逐运**倾向。
 *
 * 这是本页接入断卦的**唯一增量** —— 四柱、旺衰、喜用其实已经在「传统分析」里
 * 由通用渲染器画出来了（`day_master_strength` + `summary`）。真正缺的是
 * 「每一步大运分别偏吉还是偏凶」，也就是把一张静态的大运表变成能读的运程。
 *
 * 大运倾向是**相对日主喜忌**而言的，不等于"这十年一定如何"。
 * 这一点在 DuanCard 的不确定性清单里已如实交代，此处只负责呈现。
 */
function BaziDuanDetail({ duan }: { duan: DuanResponse }): React.JSX.Element {
  const favorable = strList(duan.detail['favorable']);
  const unfavorable = strList(duan.detail['unfavorable']);
  const daYun = verdictMap(duan.detail['da_yun_verdicts']);

  return (
    <>
      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        喜用 · 忌神
      </AppText>
      {favorable.length || unfavorable.length ? (
        <View style={styles.tagRow}>
          {favorable.map((e) => (
            <Tag key={`xi-${e}`} label={`喜 ${e}`} tone="good" />
          ))}
          {unfavorable.map((e) => (
            <Tag key={`ji-${e}`} label={`忌 ${e}`} tone="bad" />
          ))}
        </View>
      ) : (
        <AppText size="sm" color="muted" style={styles.emptyNote}>
          （未给出）
        </AppText>
      )}

      {daYun.length ? (
        <>
          <Divider style={styles.divider} />
          <AppText size="xs" color="textSecondary">
            大运倾向（按喜用 / 忌神五行）
          </AppText>
          <View style={styles.daYunGrid}>
            {daYun.map(([gz, v]) => (
              <View key={gz} style={styles.daYunItem}>
                <AppText size="sm" weight="medium">
                  {gz}
                </AppText>
                <Tag label={v} tone={verdictTone(v)} />
              </View>
            ))}
          </View>
        </>
      ) : null}
    </>
  );
}

// ==========================================================================
// 表单零件
// ==========================================================================

function Row({ children }: { children: React.ReactNode }): React.JSX.Element {
  return <View style={styles.row}>{children}</View>;
}

function NumField({
  label,
  value,
  onChange,
  width,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  width?: number;
}): React.JSX.Element {
  return (
    <View style={[styles.field, width ? { width } : undefined]}>
      <AppText size="xs" color="textSecondary">
        {label}
      </AppText>
      <TextInput
        value={value}
        onChangeText={onChange}
        keyboardType="numbers-and-punctuation"
        style={styles.input}
        placeholderTextColor={colors.muted}
        accessibilityLabel={label}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', gap: space[3], marginBottom: space[3] },
  field: { flex: 1 },
  input: {
    marginTop: space[1],
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.bg,
    paddingHorizontal: space[3],
    paddingVertical: space[2] + 1,
    fontSize: 16,
    color: colors.text,
  },
  fieldHint: { marginTop: space[1], lineHeight: 16 },
  genderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: space[3],
  },
  genderToggle: { flex: 1, marginLeft: space[3], maxWidth: 160 },
  submit: { marginTop: space[3] },
  pillars: { marginBottom: space[3], letterSpacing: 2 },

  // ---- 结果分段 ----
  col: { gap: space[2] },
  paneHint: { lineHeight: 18, marginBottom: space[3] },
  paneBtn: { marginTop: space[3] },
  verdictRow: { flexDirection: 'row', alignItems: 'baseline', gap: space[3] },
  verdictLabel: { flex: 1 },
  popupBody: { lineHeight: 22 },

  // ---- 断卦细节 ----
  divider: { marginVertical: space[3] },
  tagRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginTop: space[2] },
  emptyNote: { marginTop: space[2] },
  daYunGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginTop: space[3] },
  daYunItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    minWidth: 138,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.sm,
    backgroundColor: colors.bg,
  },

  aiBtn: { marginTop: space[3] },
  disclaimer: { marginTop: space[1] },
});
