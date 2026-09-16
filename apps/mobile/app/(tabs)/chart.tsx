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
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { BaziInput, LayerPreview } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, KeyValueRow } from '@/components/Card';
import { FactList } from '@/components/FactList';
import { Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { useSubmit } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type Gender = 'male' | 'female';
type Calendar = 'solar' | 'lunar';

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

  const calc = useSubmit(getApiClient().calcBazi);
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
    }
  }, [buildInput, calc]);

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
    <Screen scroll onRefresh={onCalc} refreshing={calc.loading}>
      <SegmentedTabs
        items={[
          { key: 'solar', label: '公历' },
          { key: 'lunar', label: '农历' },
        ]}
        value={calendar}
        onChange={(k) => setCalendar(k as Calendar)}
      />

      <Card title="出生信息" style={styles.formCard}>
        <Row>
          <NumField label="年" value={year} onChange={setYear} width={96} />
          <NumField label="月" value={month} onChange={setMonth} />
          <NumField label="日" value={day} onChange={setDay} />
        </Row>
        <Row>
          <NumField label="时" value={hour} onChange={setHour} />
          <NumField label="分" value={minute} onChange={setMinute} />
          <NumField label="出生地经度" value={longitude} onChange={setLongitude} width={104} />
        </Row>

        <AppText size="xs" color="muted" style={styles.fieldHint}>
          经度用于真太阳时修正（东八区标准经线 120°）。留空则不修正 ——
          不修正会在临近时辰边界时引入误差，报告里会如实标注。
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

      {preview ? (
        <>
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
          </Card>

          <Card title="盘面事实 · 只读">
            <FactList data={preview.facts['bazi'] ?? {}} omit={['pillars', 'warnings']} />
          </Card>

          <Card title="传统分析 · 只读">
            <FactList data={preview.tradition['bazi'] ?? {}} omit={['warnings']} />
          </Card>

          {preview.uncertainties.length > 0 ? (
            <Banner tone="warning" title={`不确定性说明（${preview.uncertainties.length} 条）`}>
              {preview.uncertainties.map((u, i) => (
                <AppText key={i} size="sm" style={styles.uncertainty}>
                  · {u}
                </AppText>
              ))}
            </Banner>
          ) : null}

          {savedSessionId ? (
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
          )}
        </>
      ) : null}

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        以上内容属于传统文化娱乐/学习参考
      </AppText>
    </Screen>
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
  formCard: { marginTop: space[3] },
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
  fieldHint: { marginTop: space[1], lineHeight: 18 },
  genderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: space[3],
  },
  genderToggle: { flex: 1, marginLeft: space[3], maxWidth: 160 },
  submit: { marginTop: space[4] },
  pillars: { marginBottom: space[3], letterSpacing: 2 },
  uncertainty: { marginTop: 2 },
  aiBtn: { marginTop: space[3] },
  disclaimer: { marginTop: space[5] },
});
