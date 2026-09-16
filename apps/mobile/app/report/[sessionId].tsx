/**
 * AI 解读报告 —— 基线规范 §3 的三标签页。
 *
 * ```
 * 【盘面事实】【传统分析】【AI 解读】
 * ```
 *
 * 三个标签**顺序不可调换**（规范原文），且内容在数据层必须物理分离 ——
 * 它们对应后端 `report.facts` / `report.tradition` / `report.interpretation`
 * 三个并列字段，前端这里不做任何合并渲染，也不把 facts 塞进 AI 文本里。
 *
 * 关于默认落在哪个标签：规范固定的是**顺序**，不是初始视图。生成报告是一次
 * 用户主动触发的、可能花钱的动作，落点是"读结论"而非"读输入摘要"，
 * 所以初始停在 AI 解读；盘面事实永远只差一次点击，且不会被折叠或隐藏。
 *
 * 免责声明固定在**标签之外**的页面底部：它属于整份报告，不属于某个标签，
 * 跟着标签切换而消失等于没有附。
 */

import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { Report, ReportRequest, Turn } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, EmptyState } from '@/components/Card';
import { FactList } from '@/components/FactList';
import { Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { alpha, colors, font, radius, space } from '@/theme/tokens';

type ReportTab = 'facts' | 'tradition' | 'ai';
type Mode = 'auto' | 'cost' | 'quality';

/** facts / tradition 的顶层键 → 展示名。未收录的键走兜底，不会被隐藏。 */
const MODULE_TITLES: Record<string, string> = {
  compass: '罗盘坐向',
  bazi: '八字命盘',
  liuyao: '六爻卦象',
  qian: '灵签',
  name: '姓名分析',
};

const MODES: readonly { key: Mode; label: string; hint: string }[] = [
  { key: 'auto', label: '自动', hint: '报告按能力优先，追问按成本优先' },
  { key: 'cost', label: '省钱', hint: '优先使用便宜/本地模型' },
  { key: 'quality', label: '高质量', hint: '优先使用能力最强的模型' },
];

export default function ReportScreen(): React.JSX.Element {
  const { sessionId } = useLocalSearchParams<{ sessionId?: string }>();
  const id = sessionId ?? '';

  const api = useMemo(() => getApiClient(), []);

  const session = useAsync(useCallback(() => api.getSession(id), [api, id]), [id]);
  const categories = useAsync(useCallback(() => api.questionCategories(), [api]), []);
  const disclaimerMeta = useAsync(useCallback(() => api.disclaimer(), [api]), []);

  const [tab, setTab] = useState<ReportTab>('ai');
  const [mode, setMode] = useState<Mode>('auto');
  const [offline, setOffline] = useState(false);

  const [category, setCategory] = useState<string | null>(null);
  const [questionText, setQuestionText] = useState('');
  const [questionSeeded, setQuestionSeeded] = useState(false);

  const [report, setReport] = useState<Report | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);

  const [followUp, setFollowUp] = useState('');
  const [localTurns, setLocalTurns] = useState<Turn[]>([]);

  const detail = session.data;

  // 已有报告才拉历史对话（避免无谓请求）
  const turns = useAsync(
    useCallback(() => api.listTurns(id), [api, id]),
    [id],
    { auto: (detail?.report_count ?? 0) > 0 },
  );

  // 用会话里存的问题预填，只在首次到达时执行一次（用户改过之后不再覆盖）
  useEffect(() => {
    if (questionSeeded || !detail) return;
    if (detail.question.category) setCategory(detail.question.category);
    if (detail.question.text) setQuestionText(detail.question.text);
    setQuestionSeeded(true);
  }, [questionSeeded, detail]);

  const generate = useSubmit(
    useCallback(
      (req: ReportRequest) => api.generateReport(id, req),
      [api, id],
    ),
  );

  const ask = useSubmit(
    useCallback(
      (text: string) => api.ask(id, { question_text: text, mode, force_template: offline }),
      [api, id, mode, offline],
    ),
  );

  const onGenerate = useCallback(async () => {
    const req: ReportRequest = {
      question_category: category,
      question_text: questionText.trim() || null,
      mode,
      force_template: offline,
    };
    const res = await generate.run(req);
    if (res) {
      setReport(res.report);
      setReportId(res.report_id);
      setTab('ai');
      // 生成后刷新对话留痕（后端把问题与结论都写进了 turns）
      turns.reload();
    }
  }, [category, generate, offline, mode, questionText, turns]);

  const onAsk = useCallback(async () => {
    const text = followUp.trim();
    if (!text) return;
    const res = await ask.run(text);
    if (!res) return;
    // 追问不改变 facts / tradition，所以主区域展示的报告保持不变，
    // 新的一问一答追加到对话区 —— 避免用户正在读的报告被整段替换掉
    setLocalTurns((prev) => [
      ...prev,
      { id: -(prev.length * 2 + 1), report_id: res.report_id, created_at: res.report.generated_at, role: 'user', content: text },
      { id: -(prev.length * 2 + 2), report_id: res.report_id, created_at: res.report.generated_at, role: 'assistant', content: res.report.interpretation.raw_text },
    ]);
    setFollowUp('');
  }, [ask, followUp]);

  const allTurns = useMemo(
    () => [...(turns.data?.items ?? []), ...localTurns],
    [turns.data, localTurns],
  );

  if (!id) {
    return (
      <Screen>
        <EmptyState title="缺少会话标识" hint="请从「历史」或「罗盘识向」进入。" />
      </Screen>
    );
  }

  if (session.loading && !detail) {
    return (
      <Screen>
        <AppText size="sm" color="textSecondary" center style={styles.loadingText}>
          正在读取会话…
        </AppText>
      </Screen>
    );
  }

  if (session.error && !detail) {
    return (
      <Screen>
        <Banner tone="error" title="无法读取会话">
          {session.error}
        </Banner>
        <Button label="重试" variant="secondary" onPress={session.reload} />
      </Screen>
    );
  }

  const noInput = (detail?.modules.length ?? 0) === 0;
  const disclaimer = report?.disclaimer ?? disclaimerMeta.data?.disclaimer ?? '以上内容属于传统文化娱乐/学习参考';

  return (
    <Screen scroll bottomInsetExtra={space[12]}>
      {detail?.build_error ? (
        <Banner tone="error" title="这份会话当前算不出来">
          {detail.build_error}
        </Banner>
      ) : null}

      {noInput ? (
        <Banner tone="info" title="还没有可计算的输入">
          请先在「罗盘识向」页识别或手动选择坐山，再到本页生成报告。
        </Banner>
      ) : null}

      <Card title={report ? '重新生成' : '生成报告'}>
        <AppText size="sm" color="textSecondary" style={styles.fieldLabel}>
          想了解什么（可选）
        </AppText>
        <CategoryChips
          categories={categories.data?.categories ?? []}
          sensitive={categories.data?.sensitive ?? {}}
          value={category}
          onChange={setCategory}
        />

        <TextInput
          value={questionText}
          onChangeText={setQuestionText}
          placeholder="例如：今年适合换工作吗"
          placeholderTextColor={colors.muted}
          style={styles.input}
          multiline
          maxLength={200}
          accessibilityLabel="问题内容"
        />

        <AppText size="sm" color="textSecondary" style={styles.fieldLabel}>
          模型偏好
        </AppText>
        <View style={styles.modeRow}>
          {MODES.map((m) => {
            const active = m.key === mode;
            return (
              <Pressable
                key={m.key}
                onPress={() => setMode(m.key)}
                accessibilityRole="radio"
                accessibilityState={{ selected: active }}
                style={[styles.modeItem, active && styles.modeItemActive]}
              >
                <AppText size="sm" weight={active ? 'semibold' : 'regular'} color={active ? 'primary' : 'textSecondary'}>
                  {m.label}
                </AppText>
              </Pressable>
            );
          })}
        </View>
        <AppText size="xs" color="muted" style={styles.modeHint}>
          {MODES.find((m) => m.key === mode)?.hint}
        </AppText>

        <Pressable
          onPress={() => setOffline((v) => !v)}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: offline }}
          style={styles.offlineRow}
        >
          <View style={[styles.checkbox, offline && styles.checkboxOn]}>
            {offline ? <Ionicons name="checkmark" size={12} color={colors.onPrimary} /> : null}
          </View>
          <View style={styles.offlineText}>
            <AppText size="sm">离线模式（零成本、结果可复现）</AppText>
            <AppText size="xs" color="muted">
              不调用任何外部模型，只复述计算层的确定性结果
            </AppText>
          </View>
        </Pressable>

        {category && categories.data?.sensitive[category] ? (
          <Banner tone="warning" title="敏感类别提示" style={styles.sensitive}>
            {categories.data.sensitive[category]}
          </Banner>
        ) : null}

        <Button
          label={report ? '重新生成报告' : '生成报告'}
          size="lg"
          loading={generate.loading}
          disabled={noInput}
          style={styles.genBtn}
          onPress={() => void onGenerate()}
        />
      </Card>

      {generate.error ? (
        <Banner tone={generate.fixable ? 'warning' : 'error'} title={generate.fixable ? '输入需要调整' : '生成失败'}>
          {generate.error}
        </Banner>
      ) : null}

      {report ? (
        <>
          <View style={styles.tabsWrap}>
            <SegmentedTabs<ReportTab>
              variant="underline"
              value={tab}
              onChange={setTab}
              items={[
                { key: 'facts', label: '盘面事实' },
                { key: 'tradition', label: '传统分析' },
                { key: 'ai', label: 'AI 解读' },
              ]}
            />
          </View>

          {tab === 'facts' ? (
            <LayerTab
              data={report.facts}
              emptyHint="本次没有可展示的确定性计算结果。"
              footnote="本标签内容来自 Fortune Core 的确定性计算，AI 没有写入通道，因此不存在被幻觉改写的可能。"
            />
          ) : null}

          {tab === 'tradition' ? (
            <LayerTab
              data={report.tradition}
              emptyHint="本次没有可展示的传统规则派生结果。"
              footnote="本标签由流派规则表派生。规则表未就绪的条目会显示为「未定」，而不是省略 —— 省略会让人误以为没有这一项。"
            />
          ) : null}

          {tab === 'ai' ? (
            <>
              {report.interpretation.degraded ? (
                <Banner tone="warning" title="本次已降级生成">
                  {report.interpretation.attempts
                    .map((a) => `${a.ok ? '✓' : '✕'} ${a.provider}/${a.model}：${a.detail}`)
                    .join('\n')}
                </Banner>
              ) : null}

              {report.interpretation.sections.map((s) => (
                <Card key={s.title} title={s.title}>
                  <AppText size="md" lineHeightRatio={1.2}>
                    {s.body}
                  </AppText>
                </Card>
              ))}

              <UncertaintyList items={report.uncertainties} />

              {report.interpretation.warnings.length > 0 ? (
                <Banner tone="info" title="生成过程提示">
                  {report.interpretation.warnings.join('\n')}
                </Banner>
              ) : null}

              <AppText size="xs" color="muted" center style={styles.provenance}>
                由 {report.interpretation.provider} / {report.interpretation.model} 生成
                {report.interpretation.usage
                  ? `，消耗 ${report.interpretation.usage.total_tokens} tokens`
                  : ''}
              </AppText>

              <Card title="继续追问">
                <TextInput
                  value={followUp}
                  onChangeText={setFollowUp}
                  placeholder="就这份盘面继续问，例如：那明年呢"
                  placeholderTextColor={colors.muted}
                  style={styles.input}
                  multiline
                  maxLength={200}
                  accessibilityLabel="追问内容"
                />
                {ask.error ? (
                  <Banner tone={ask.fixable ? 'warning' : 'error'} title="追问失败" style={styles.askErr}>
                    {ask.error}
                  </Banner>
                ) : null}
                <Button
                  label="追问"
                  variant="secondary"
                  loading={ask.loading}
                  disabled={followUp.trim().length === 0}
                  style={styles.askBtn}
                  onPress={() => void onAsk()}
                />
                <AppText size="xs" color="muted" style={styles.askHint}>
                  追问不会改动盘面事实与传统分析 —— 计算层结果与问题无关。
                </AppText>

                <ThreadView turns={allTurns} />
              </Card>
            </>
          ) : null}
        </>
      ) : (
        <EmptyState
          title="还没有报告"
          hint="先确认坐向并录入所需信息，再回到本页生成。报告会一并保存到历史记录。"
        />
      )}

      {/* 免责声明固定在标签之外：它属于整份报告，不该随标签切换而消失 */}
      <View style={styles.disclaimer}>
        <AppText size="xs" color="muted" center>
          {disclaimer}
        </AppText>
        {reportId ? (
          <AppText size="xs" color="muted" center style={styles.reportId}>
            报告编号 {reportId}
          </AppText>
        ) : null}
      </View>
    </Screen>
  );
}

// ==========================================================================
// 两层只读标签
// ==========================================================================

function LayerTab({
  data,
  emptyHint,
  footnote,
}: {
  data: Record<string, Record<string, unknown>>;
  emptyHint: string;
  footnote: string;
}): React.JSX.Element {
  const entries = Object.entries(data).filter(([, v]) => isRecord(v) && Object.keys(v).length > 0);

  if (entries.length === 0) {
    return <EmptyState title={emptyHint} />;
  }

  return (
    <>
      {entries.map(([key, value]) => (
        <Card key={key} title={MODULE_TITLES[key] ?? key}>
          <FactList data={value} />
        </Card>
      ))}
      <AppText size="xs" color="muted" style={styles.footnote}>
        {footnote}
      </AppText>
    </>
  );
}

// ==========================================================================
// 类别选择
// ==========================================================================

function CategoryChips({
  categories,
  sensitive,
  value,
  onChange,
}: {
  categories: readonly string[];
  sensitive: Record<string, string>;
  value: string | null;
  onChange: (v: string | null) => void;
}): React.JSX.Element {
  if (categories.length === 0) {
    return (
      <AppText size="xs" color="muted" style={styles.chipEmpty}>
        类别清单尚未从服务端取得，不影响生成报告。
      </AppText>
    );
  }
  return (
    <View style={styles.chipRow}>
      {categories.map((c) => {
        const active = c === value;
        const isSensitive = Boolean(sensitive[c]);
        return (
          <Pressable
            key={c}
            onPress={() => onChange(active ? null : c)}
            accessibilityRole="radio"
            accessibilityState={{ selected: active }}
            style={[styles.chip, active && styles.chipActive]}
          >
            <AppText size="sm" color={active ? 'onPrimary' : isSensitive ? 'danger' : 'textSecondary'}>
              {c}
              {isSensitive ? ' ⚠' : ''}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

// ==========================================================================
// 追问记录
// ==========================================================================

function ThreadView({ turns }: { turns: readonly Turn[] }): React.JSX.Element | null {
  if (turns.length === 0) return null;
  return (
    <View style={styles.thread}>
      {turns.map((t) => (
        <View
          key={t.id}
          style={[styles.turn, t.role === 'user' ? styles.turnUser : styles.turnAssistant]}
        >
          <AppText size="xs" color="muted" style={styles.turnRole}>
            {t.role === 'user' ? '你问' : 'AI 答'}
          </AppText>
          <AppText size="sm" lineHeightRatio={1.15}>
            {t.content}
          </AppText>
        </View>
      ))}
    </View>
  );
}

// ==========================================================================
// 工具
// ==========================================================================

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

const styles = StyleSheet.create({
  loadingText: { marginTop: space[10] },
  fieldLabel: { marginBottom: space[2] },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    minHeight: 52,
    color: colors.text,
    fontSize: font.size.md,
    lineHeight: font.lineHeight.md,
    textAlignVertical: 'top',
    backgroundColor: colors.surfaceAlt,
    marginBottom: space[3],
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space[2], marginBottom: space[3] },
  chip: {
    paddingHorizontal: space[3],
    paddingVertical: space[1] + 2,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceAlt,
  },
  chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  chipEmpty: { marginBottom: space[3], lineHeight: 16 },

  modeRow: { flexDirection: 'row', gap: space[2] },
  modeItem: {
    flex: 1,
    paddingVertical: space[2],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    backgroundColor: colors.surfaceAlt,
  },
  modeItemActive: { borderColor: colors.primary, backgroundColor: alpha.primarySoft },
  modeHint: { marginTop: space[2], lineHeight: 16 },

  offlineRow: { flexDirection: 'row', alignItems: 'flex-start', marginTop: space[4] },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: radius.sm - 2,
    borderWidth: 1.5,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  checkboxOn: { backgroundColor: colors.primary, borderColor: colors.primary },
  offlineText: { flex: 1, marginLeft: space[2], gap: 2 },

  sensitive: { marginTop: space[3] },
  genBtn: { marginTop: space[4] },

  tabsWrap: { marginBottom: space[3] },
  footnote: { lineHeight: 16, marginBottom: space[3] },
  provenance: { marginBottom: space[3] },
  askErr: { marginTop: space[2] },
  askBtn: { marginTop: space[2] },
  askHint: { marginTop: space[2], lineHeight: 16 },

  thread: { marginTop: space[4], gap: space[3] },
  turn: {
    borderRadius: radius.md,
    padding: space[3],
    borderWidth: 1,
    borderColor: colors.border,
  },
  turnUser: { backgroundColor: colors.surfaceAlt },
  turnAssistant: { backgroundColor: colors.surface },
  turnRole: { marginBottom: space[1] },

  disclaimer: { marginTop: space[6] },
  reportId: { marginTop: space[1] },
});
