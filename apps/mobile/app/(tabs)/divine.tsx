/**
 * 占测 —— 六爻与灵签。
 *
 * 两条铁律在本页的体现：
 *
 * 1. **不使用随机数**（RULE-001）。六爻的每一爻由用户**实际摇出的结果**决定，
 *    界面只提供"登记结果"的输入，不提供"帮我摇一卦"——那会变成程序在替天意掷骰子。
 * 2. **抽签结果可复现**。seed 由用户抽签那一刻确定并**显示出来**，
 *    同一 seed 永远得到同一签；用户可改用自己心仪的数字。这不是装饰，
 *    而是"这个结果是怎么来的"必须可追溯。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { DuanResponse, LayerPreview, QuestionCategoriesResponse } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, Divider, EmptyState, KeyValueRow } from '@/components/Card';
import { Chip } from '@/components/Chip';
import { DuanCard } from '@/components/DuanCard';
import { FactList } from '@/components/FactList';
import { Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { isToday, shiftDays, todayISODate, weekdayLabel } from '@/lib/date';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type Mode = 'liuyao' | 'qian';

/** 四象：数值 → 名称与图形。数值含义见计算层约定（3背=9 老阳 …） */
const YAO_KINDS = [
  { value: 6, name: '老阴', glyph: '▬▬  ×', hint: '0 背（三字）', moving: true },
  { value: 7, name: '少阳', glyph: '▬▬▬', hint: '1 背', moving: false },
  { value: 8, name: '少阴', glyph: '▬ ▬', hint: '2 背', moving: false },
  { value: 9, name: '老阳', glyph: '▬▬▬ ○', hint: '3 背', moving: true },
] as const;

export default function DivineScreen(): React.JSX.Element {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('liuyao');

  return (
    <Screen scroll>
      <SegmentedTabs
        items={[
          { key: 'liuyao', label: '六爻' },
          { key: 'qian', label: '灵签' },
        ]}
        value={mode}
        onChange={(k) => setMode(k as Mode)}
      />
      <View style={styles.spacer} />
      {mode === 'liuyao' ? <LiuyaoPanel onOpenReport={(id) => router.push(`/report/${id}`)} /> : null}
      {mode === 'qian' ? <QianPanel onOpenReport={(id) => router.push(`/report/${id}`)} /> : null}

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        以上内容属于传统文化娱乐/学习参考
      </AppText>
    </Screen>
  );
}

// ==========================================================================
// 六爻
// ==========================================================================

function LiuyaoPanel({ onOpenReport }: { onOpenReport: (id: string) => void }): React.JSX.Element {
  // 自下而上第 1..6 爻；默认全部少阳（不移动），由用户逐爻改正为自己摇出的结果
  const [yao, setYao] = useState<number[]>([7, 7, 7, 7, 7, 7]);
  const [preview, setPreview] = useState<LayerPreview | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);

  // ---- 断卦所需的上下文：占问类别 / 性别 / 起卦日 ----
  const [topic, setTopic] = useState<string | null>(null);
  const [gender, setGender] = useState<'male' | 'female' | null>(null);
  const [castDate, setCastDate] = useState(todayISODate());
  const [duanResult, setDuanResult] = useState<DuanResponse | null>(null);

  const calc = useSubmit(getApiClient().calcLiuyao);
  const create = useSubmit(getApiClient().createSession);
  const patch = useSubmit(getApiClient().patchInputs);
  const duan = useSubmit(getApiClient().duanLiuyao);

  // 类别清单取自服务端，**不在界面里硬编码** —— RULE-005「规则不散落」的落点。
  // 硬编码的后果很实在：内核将来新增一个类别，界面永远看不到它。
  const loadCategories = useCallback(
    (): Promise<QuestionCategoriesResponse> => getApiClient().questionCategories(),
    [],
  );
  const categories = useAsync(loadCategories, []);

  // 类别 / 性别 / 起卦日 / 卦象任一变化，上一次的倾向就不再对应当前输入 —— 必须作废。
  // 留着旧结果比留空更糟：它看起来仍然有效（RULE-008 的界面侧）。
  useEffect(() => {
    setDuanResult(null);
  }, [topic, gender, castDate, yao]);

  const setOne = (index: number, value: number): void => {
    setYao((prev) => prev.map((v, i) => (i === index ? value : v)));
    setPreview(null);
    setSavedId(null);
  };

  const onCalc = useCallback(async () => {
    const r = await calc.run({ method: 'yao', yao_values: yao });
    if (r) {
      setPreview(r);
      setSavedId(null);
    }
  }, [calc, yao]);

  const onDuan = useCallback(async () => {
    const r = await duan.run({
      method: 'yao',
      yao_values: yao,
      topic,
      gender,
      cast_date: castDate,
    });
    if (r) setDuanResult(r);
  }, [duan, yao, topic, gender, castDate]);

  // 敏感类别的额外免责（RULE-010）：健康 / 财运由服务端标注，界面照原样展示。
  const sensitiveNote = topic ? (categories.data?.sensitive?.[topic] ?? null) : null;

  const onSave = useCallback(async () => {
    const created = await create.run({ title: '六爻占测', question_text: null });
    if (!created) return;
    const ok = await patch.run(created.session_id, { liuyao: { method: 'yao', yao_values: yao } });
    if (ok) setSavedId(created.session_id);
  }, [create, patch, yao]);

  const movingCount = yao.filter((v) => v === 6 || v === 9).length;
  const err = calc.error ?? create.error ?? patch.error;

  return (
    <>
      <Card title="登记摇卦结果（自下而上）">
        <AppText size="sm" color="textSecondary" style={styles.cardIntro}>
          请先实际摇卦，再把每一爻的结果登记在这里。程序**不会**替你摇 ——
          随机数不构成占测，且结果无法复现。
        </AppText>

        {yao.map((value, index) => (
          <View key={index} style={styles.yaoRow}>
            <AppText size="sm" color="textSecondary" style={styles.yaoLabel}>
              {['初', '二', '三', '四', '五', '上'][index]}
            </AppText>
            <View style={styles.yaoOptions}>
              {YAO_KINDS.map((k) => {
                const active = k.value === value;
                return (
                  <Pressable
                    key={k.value}
                    onPress={() => setOne(index, k.value)}
                    style={[styles.yaoOption, active && styles.yaoOptionActive]}
                    accessibilityRole="radio"
                    accessibilityState={{ selected: active }}
                  >
                    <AppText
                      size="xs"
                      weight={active ? 'semibold' : 'regular'}
                      color={active ? 'primary' : 'textSecondary'}
                    >
                      {k.glyph}
                    </AppText>
                    <AppText size="xs" color={active ? 'primary' : 'muted'}>
                      {k.name}
                    </AppText>
                  </Pressable>
                );
              })}
            </View>
          </View>
        ))}

        <AppText size="xs" color="muted" style={styles.movingHint}>
          {movingCount === 0 ? '六爻皆不动（静卦）' : `有 ${movingCount} 个动爻（老阴/老阳）`}
        </AppText>

        <Button label="起卦" onPress={onCalc} loading={calc.loading} style={styles.submitBtn} />
      </Card>

      {err ? <Banner tone="error" title="请求失败">{err}</Banner> : null}

      {preview ? (
        <>
          <Card title="卦象 · 只读">
            <KeyValueRow label="本卦" emphasized value={s(preview.facts['liuyao']?.['original_gua'])} />
            <KeyValueRow
              label="上下卦"
              value={`${s(preview.facts['liuyao']?.['upper_gua'])} / ${s(preview.facts['liuyao']?.['lower_gua'])}`}
            />
            <KeyValueRow label="变卦" emphasized value={s(preview.facts['liuyao']?.['changed_gua'])} />
            <KeyValueRow
              label="动爻"
              value={
                Array.isArray(preview.facts['liuyao']?.['moving_positions']) &&
                (preview.facts['liuyao']?.['moving_positions'] as number[]).length > 0
                  ? (preview.facts['liuyao']?.['moving_positions'] as number[]).join('、')
                  : '无（静卦）'
              }
              last
            />
          </Card>

          <Card title="卦象明细">
            <FactList data={preview.facts['liuyao'] ?? {}} omit={['original_gua', 'changed_gua', 'upper_gua', 'lower_gua', 'moving_positions']} />
          </Card>

          <Card title="传统分析 · 只读">
            <FactList data={preview.tradition['liuyao'] ?? {}} />
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

          {/* ---- 断卦：吉凶倾向 ---- */}
          <Card title="断卦 · 吉凶倾向">
            <AppText size="sm" color="textSecondary" style={styles.cardIntro}>
              断卦要先知道「所问何事」—— 用神由占问类别决定，类别不同，判断的着力点就不同。
              不选类别也能断，但那只是整体卦象的参照，不等于针对某件事的结论。
            </AppText>

            <AppText size="xs" color="textSecondary">
              占问类别
            </AppText>
            {categories.error ? (
              <AppText size="xs" color="cinnabar" style={styles.inlineHint}>
                类别清单读取失败：{categories.error}
              </AppText>
            ) : categories.loading && !categories.data ? (
              <AppText size="xs" color="muted" style={styles.inlineHint}>
                读取类别…
              </AppText>
            ) : (
              <View style={styles.chipRow}>
                <Chip label="不指定" onPress={() => setTopic(null)} active={topic === null} />
                {(categories.data?.categories ?? []).map((c) => (
                  <Chip key={c} label={c} onPress={() => setTopic(c)} active={topic === c} />
                ))}
              </View>
            )}

            {sensitiveNote ? (
              <Banner tone="warning" title="这类问题有额外边界" style={styles.sensitive}>
                {sensitiveNote}
              </Banner>
            ) : null}

            <AppText size="xs" color="textSecondary" style={styles.fieldLabel}>
              当事人性别（婚姻类需要：男占妻看妻财、女占夫看官鬼）
            </AppText>
            <View style={styles.chipRow}>
              <Chip label="不填" onPress={() => setGender(null)} active={gender === null} />
              <Chip label="男" onPress={() => setGender('male')} active={gender === 'male'} />
              <Chip label="女" onPress={() => setGender('female')} active={gender === 'female'} />
            </View>

            <AppText size="xs" color="textSecondary" style={styles.fieldLabel}>
              起卦日（决定日辰与月令）
            </AppText>
            <CastDateRow value={castDate} onChange={setCastDate} />
            {!isToday(castDate) ? (
              <AppText size="xs" color="warning" style={styles.inlineHint}>
                只有补录隔夜的卦才需要改这里。若仍按今天算，旺衰结论会「看似正常、依据全错」。
              </AppText>
            ) : null}

            <Button
              label="断卦"
              icon={<Ionicons name="analytics-outline" size={18} color={colors.onPrimary} />}
              onPress={onDuan}
              loading={duan.loading}
              style={styles.submitBtn}
            />

            {duan.error ? (
              <Banner tone="error" title="断卦失败" style={styles.sensitive}>
                {duan.error}
              </Banner>
            ) : null}
          </Card>

          {duanResult ? (
            <DuanCard duan={duanResult} verdictLabel="吉凶倾向" title="断卦结果">
              <DuanBasis duan={duanResult} />
            </DuanCard>
          ) : null}

          {savedId ? (
            <Card highlight>
              <AppText size="sm" weight="semibold" color="success">
                ✓ 已保存
              </AppText>
              <Button
                label="生成 AI 解读"
                icon={<Ionicons name="sparkles" size={18} color={colors.onPrimary} />}
                style={styles.submitBtn}
                onPress={() => onOpenReport(savedId)}
              />
            </Card>
          ) : (
            <Button label="保存并生成 AI 解读" variant="secondary" onPress={onSave} />
          )}
        </>
      ) : null}
    </>
  );
}

// ==========================================================================
// 灵签
// ==========================================================================

function QianPanel({ onOpenReport }: { onOpenReport: (id: string) => void }): React.JSX.Element {
  const [seedText, setSeedText] = useState('');
  const [preview, setPreview] = useState<LayerPreview | null>(null);
  const [savedId, setSavedId] = useState<string | null>(null);
  const [demoWarning, setDemoWarning] = useState<string | null>(null);

  const calc = useSubmit(getApiClient().calcQian);
  const create = useSubmit(getApiClient().createSession);
  const patch = useSubmit(getApiClient().patchInputs);

  const draw = useCallback(async () => {
    // 未填种子 → 用"此刻"作为种子，并把它显示出来（可复现、可追溯）
    const seed = seedText.trim() === '' ? Date.now() : Number(seedText);
    if (!Number.isFinite(seed)) return;

    const r = await calc.run({ seed, set_id: 'demo_guanyin' });
    if (!r) return;
    setSeedText(String(seed));
    setPreview(r);
    setSavedId(null);
    // 演示签库必须显著提示，不能让人误以为抽到了传世签文
    setDemoWarning(r.facts['qian']?.['is_demo_data'] === true ? '当前使用演示签库（自撰样例），非传世签文' : null);
  }, [calc, seedText]);

  const onSave = useCallback(async () => {
    const seed = Number(seedText);
    if (!Number.isFinite(seed)) return;
    const created = await create.run({ title: '灵签' });
    if (!created) return;
    const ok = await patch.run(created.session_id, { qian: { seed, set_id: 'demo_guanyin' } });
    if (ok) setSavedId(created.session_id);
  }, [create, patch, seedText]);

  const qianFacts = preview?.facts['qian'] ?? {};
  const err = calc.error ?? create.error ?? patch.error;

  return (
    <>
      <Card title="抽签">
        <AppText size="sm" color="textSecondary" style={styles.cardIntro}>
          留空则以点击那一刻的时间为种子；也可填入你心仪的数字。
          种子会记录下来 —— 同一个种子永远得到同一支签，结果可复现。
        </AppText>
        <View style={styles.seedRow}>
          <AppText size="sm" color="textSecondary">
            种子
          </AppText>
          <TextInput
            value={seedText}
            onChangeText={setSeedText}
            keyboardType="number-pad"
            placeholder="留空 = 以当前时刻"
            placeholderTextColor={colors.muted}
            style={styles.seedInput}
          />
        </View>
        <Button
          label="抽签"
          icon={<Ionicons name="book-outline" size={18} color={colors.onPrimary} />}
          onPress={draw}
          loading={calc.loading}
          style={styles.submitBtn}
        />
      </Card>

      {demoWarning ? (
        <Banner tone="warning" title="演示数据">
          {demoWarning}
        </Banner>
      ) : null}

      {err ? <Banner tone="error" title="请求失败">{err}</Banner> : null}

      {preview ? (
        <>
          <Card title={`第 ${s(qianFacts['number'])} 签 · ${s(qianFacts['level'])}`}>
            <AppText size="xl" weight="bold" color="primary" center style={styles.qianTitle}>
              {s(qianFacts['title'])}
            </AppText>
            <View style={styles.poem}>
              {(Array.isArray(qianFacts['poem']) ? (qianFacts['poem'] as string[]) : []).map((line, i) => (
                <AppText key={i} size="md" center style={styles.poemLine}>
                  {line}
                </AppText>
              ))}
            </View>
            <KeyValueRow label="签库" value={s(qianFacts['set_name'])} last />
          </Card>

          {Object.keys(preview.tradition['qian'] ?? {}).length > 0 ? (
            <Card title="传统分析 · 只读">
              <FactList data={preview.tradition['qian'] ?? {}} />
            </Card>
          ) : null}

          {savedId ? (
            <Card highlight>
              <AppText size="sm" weight="semibold" color="success">
                ✓ 已保存
              </AppText>
              <Button
                label="生成 AI 解读"
                icon={<Ionicons name="sparkles" size={18} color={colors.onPrimary} />}
                style={styles.submitBtn}
                onPress={() => onOpenReport(savedId)}
              />
            </Card>
          ) : (
            <Button label="保存并生成 AI 解读" variant="secondary" onPress={onSave} />
          )}
        </>
      ) : (
        <EmptyState title="还没有签" hint="点击「抽签」抽取，或填入种子后抽取" />
      )}
    </>
  );
}

/** 安全取值：null/undefined 显示占位（默认「未定」，RULE-003 的 UI 落点） */
function s(v: unknown, fallback = '未定'): string {
  if (v === null || v === undefined) return fallback;
  return String(v);
}

/**
 * 起卦日 —— 逐日 ±1。
 *
 * 与黄历页的区间选择器**刻意不同**：这里回答的是"哪一天起的这一卦"，
 * 取值通常就是今天或昨天，按天微调比按周跳更顺手；而黄历选的是查询/筛选区间，
 * 按周跳才有意义。两个控件都是日期，但操作意图不同，所以不强行统一。
 */
function CastDateRow({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}): React.JSX.Element {
  return (
    <View style={styles.castRow}>
      <Pressable
        onPress={() => onChange(shiftDays(value, -1))}
        style={styles.castBtn}
        accessibilityLabel="起卦日往前一天"
      >
        <Ionicons name="remove" size={16} color={colors.primary} />
      </Pressable>
      <View style={styles.castValue}>
        <AppText size="sm" weight="medium">
          {value}
        </AppText>
        <AppText size="xs" color="muted">
          {weekdayLabel(value)}
        </AppText>
      </View>
      <Pressable
        onPress={() => onChange(shiftDays(value, 1))}
        style={styles.castBtn}
        accessibilityLabel="起卦日往后一天"
      >
        <Ionicons name="add" size={16} color={colors.primary} />
      </Pressable>
      {isToday(value) ? null : (
        <Pressable onPress={() => onChange(todayISODate())} style={styles.castToday}>
          <AppText size="xs" color="primary">
            回到今天
          </AppText>
        </Pressable>
      )}
    </View>
  );
}

/**
 * 本盘实际采用的日辰 / 月令 / 用神 —— 倾向的**可回溯依据**。
 *
 * 后端把这几项随断卦结果一并返回，就是为了让任何一条倾向都能被追溯。
 * 只给一个「偏吉」而不给依据，等于让用户无条件相信一个黑盒。
 *
 * 「占问」与「用神」为空时的措辞与「未定」区别开：那是**本次没取**，
 * 不是"算不出来" —— 说成"未定"会让用户以为卦里有什么玄机。
 */
function DuanBasis({ duan }: { duan: DuanResponse }): React.JSX.Element | null {
  const raw = duan.detail['basis'];
  if (!raw || typeof raw !== 'object') return null;
  const b = raw as Record<string, unknown>;

  return (
    <>
      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        本盘依据
      </AppText>
      <KeyValueRow label="起卦日" value={s(b['cast_date'])} />
      <KeyValueRow label="日辰" value={s(b['day_pillar'])} />
      <KeyValueRow label="月令" value={s(b['month_pillar'])} />
      <KeyValueRow label="占问" value={s(b['topic'], '未指定')} />
      <KeyValueRow label="用神" emphasized value={s(b['yongshen'], '本次未取')} last />
    </>
  );
}

const styles = StyleSheet.create({
  spacer: { height: space[3] },
  cardIntro: { marginBottom: space[3], lineHeight: 20 },

  // ---- 断卦控制区 ----
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginTop: space[2] },
  fieldLabel: { marginTop: space[4] },
  inlineHint: { marginTop: space[2], lineHeight: 18 },
  sensitive: { marginTop: space[3], marginBottom: 0 },
  divider: { marginVertical: space[3] },
  castRow: { flexDirection: 'row', alignItems: 'center', gap: space[2], marginTop: space[2] },
  castBtn: {
    width: 32,
    height: 32,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  castValue: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[2],
    borderRadius: radius.sm,
    backgroundColor: alpha.primarySoft,
  },
  castToday: { paddingHorizontal: space[2], paddingVertical: space[2] },

  yaoRow: { flexDirection: 'row', alignItems: 'center', marginBottom: space[2] },
  yaoLabel: { width: 28 },
  yaoOptions: { flex: 1, flexDirection: 'row', gap: space[2] },
  yaoOption: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[2],
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  yaoOptionActive: {
    borderColor: colors.primary,
    backgroundColor: alpha.primarySoft,
  },
  movingHint: { marginTop: space[2] },
  submitBtn: { marginTop: space[4] },
  uncertainty: { marginTop: 2 },
  disclaimer: { marginTop: space[5] },

  seedRow: { flexDirection: 'row', alignItems: 'center', marginBottom: space[3] },
  seedInput: {
    flex: 1,
    marginLeft: space[3],
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.bg,
    paddingHorizontal: space[3],
    paddingVertical: space[2] + 1,
    fontSize: 16,
    color: colors.text,
  },
  qianTitle: { marginBottom: space[3], letterSpacing: 1 },
  poem: { gap: space[1], marginBottom: space[3] },
  poemLine: { lineHeight: 26 },
});
