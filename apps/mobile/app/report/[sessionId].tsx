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
 *
 * ## 2026-10-09 单屏化
 *
 * 三标签保留、顺序不变（规范约定），但改 `variant="fill"` 让三段等宽更好点。
 * 一屏放不下的内容按三条出路走：
 *   1. **分段** —— 三标签同一时刻只显示一段，放进 `FitSlot`（唯一弹性区）；
 *   2. **折叠** —— 段落 / 模块列表用 `FoldList`（前 N 条 + 「更多」浮层）；
 *   3. **压缩** —— 正文 `numberOfLines` 限行、其余进「展开全文」浮层；
 *      「依据 / 不确定性 / 规则来源 / 追问」这类辅助信息收进 `InfoPopup`。
 * 生成表单在**还没有报告**时就是主内容；已有报告时收进标题栏「重新生成」浮层。
 * 业务逻辑（生成 / 追问 / 数据流）一字未动。
 */

import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { Report, ReportRequest, ReportSection, Turn } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, EmptyState } from '@/components/Card';
import { FactList } from '@/components/FactList';
import { FoldList } from '@/components/FoldList';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { alpha, colors, font, radius, space } from '@/theme/tokens';

type ReportTab = 'facts' | 'tradition' | 'ai';
type Mode = 'auto' | 'cost' | 'quality';

/**
 * AI 解读内的**文体**切换。
 *
 * 与上面的 `ReportTab` 是两回事，别看混：`ReportTab` 分的是**层**
 * （盘面事实 / 传统分析 / AI 解读），`RegisterTab` 分的是 AI 解读层内部的**深浅**
 * —— 同一批数据的两种讲法。两者的控件样式也不同（下划线 vs 填充块），
 * 就是为了让人一眼看出"这是两个层级的切换"。
 */
type RegisterTab = 'expert' | 'plain';

const REGISTER_LABEL: Record<RegisterTab, string> = {
  expert: '专业分析',
  plain: '白话讲解',
};

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
  /**
   * AI 解读的文体。
   *
   * 默认「专业分析」：这一页的主用户是带着问题来对盘的人，先给准确术语；
   * 看不懂的人切一下就有白话版。反过来默认白话版，懂行的人每次都要多切一次。
   */
  const [register, setRegister] = useState<RegisterTab>('expert');
  const [mode, setMode] = useState<Mode>('auto');
  const [offline, setOffline] = useState(false);

  const [category, setCategory] = useState<string | null>(null);
  const [questionText, setQuestionText] = useState('');
  const [questionSeeded, setQuestionSeeded] = useState(false);

  const [report, setReport] = useState<Report | null>(null);
  const [reportId, setReportId] = useState<string | null>(null);

  const [followUp, setFollowUp] = useState('');
  const [localTurns, setLocalTurns] = useState<Turn[]>([]);

  /** 生成表单浮层 —— 已有报告时，重新生成的入口收进标题栏 */
  const [openForm, setOpenForm] = useState(false);

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
    <Screen bottomInsetExtra={space[3]}>
      <PageHeader
        title="AI 解读报告"
        back
        helpTopic="report"
        tone="light"
        action={
          report ? (
            <Pressable
              onPress={() => setOpenForm(true)}
              accessibilityRole="button"
              accessibilityLabel="重新生成报告"
              style={styles.headerAction}
            >
              <Ionicons name="refresh" size={14} color={colors.primary} />
              <AppText size="sm" color="primary" style={styles.headerActionText}>
                重新生成
              </AppText>
            </Pressable>
          ) : undefined
        }
      />

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

      {report ? (
        <>
          <SegmentedTabs<ReportTab>
            variant="fill"
            value={tab}
            onChange={setTab}
            items={[
              { key: 'facts', label: '盘面事实' },
              { key: 'tradition', label: '传统分析' },
              { key: 'ai', label: 'AI 解读' },
            ]}
          />

          <FitSlot weight={1}>
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
              <AiTab
                report={report}
                register={register}
                onChangeRegister={setRegister}
                followUp={followUp}
                onChangeFollowUp={setFollowUp}
                onAsk={() => void onAsk()}
                askLoading={ask.loading}
                askError={ask.error}
                askFixable={ask.fixable}
                allTurns={allTurns}
              />
            ) : null}
          </FitSlot>
        </>
      ) : (
        <FitSlot weight={1}>
          <GenerateForm
            categories={categories.data?.categories ?? []}
            sensitive={categories.data?.sensitive ?? {}}
            category={category}
            onChangeCategory={setCategory}
            questionText={questionText}
            onChangeQuestion={setQuestionText}
            mode={mode}
            onChangeMode={setMode}
            offline={offline}
            onToggleOffline={() => setOffline((v) => !v)}
            loading={generate.loading}
            disabled={noInput}
            onGenerate={() => void onGenerate()}
            reportExists={false}
          />
        </FitSlot>
      )}

      {generate.error ? (
        <Banner tone={generate.fixable ? 'warning' : 'error'} title={generate.fixable ? '输入需要调整' : '生成失败'}>
          {generate.error}
        </Banner>
      ) : null}

      {/* 免责声明固定在标签之外：它属于整份报告，不该随标签切换而消失 */}
      <View style={styles.disclaimer}>
        <AppText size="xs" color="muted" center numberOfLines={1}>
          {disclaimer}
        </AppText>
        {reportId ? (
          <AppText size="xs" color="muted" center numberOfLines={1} style={styles.reportId}>
            报告编号 {reportId}
          </AppText>
        ) : null}
      </View>

      {/* 浮层：重新生成（有报告时，生成表单收进这里） */}
      <InfoPopup
        visible={openForm}
        onClose={() => setOpenForm(false)}
        title="重新生成报告"
        subtitle="会覆盖当前展示的解读"
      >
        <GenerateForm
          categories={categories.data?.categories ?? []}
          sensitive={categories.data?.sensitive ?? {}}
          category={category}
          onChangeCategory={setCategory}
          questionText={questionText}
          onChangeQuestion={setQuestionText}
          mode={mode}
          onChangeMode={setMode}
          offline={offline}
          onToggleOffline={() => setOffline((v) => !v)}
          loading={generate.loading}
          disabled={noInput}
          onGenerate={() => void onGenerate()}
          reportExists
        />
      </InfoPopup>
    </Screen>
  );
}

// ==========================================================================
// 生成表单（无报告时为主内容，有报告时进浮层）
// ==========================================================================

function GenerateForm({
  categories,
  sensitive,
  category,
  onChangeCategory,
  questionText,
  onChangeQuestion,
  mode,
  onChangeMode,
  offline,
  onToggleOffline,
  loading,
  disabled,
  onGenerate,
  reportExists,
}: {
  categories: readonly string[];
  sensitive: Record<string, string>;
  category: string | null;
  onChangeCategory: (v: string | null) => void;
  questionText: string;
  onChangeQuestion: (v: string) => void;
  mode: Mode;
  onChangeMode: (m: Mode) => void;
  offline: boolean;
  onToggleOffline: () => void;
  loading: boolean;
  disabled: boolean;
  onGenerate: () => void;
  reportExists: boolean;
}): React.JSX.Element {
  return (
    <Card title={reportExists ? '重新生成' : '生成报告'}>
      <AppText size="sm" color="textSecondary" style={styles.fieldLabel}>
        想了解什么（可选）
      </AppText>
      <CategoryChips
        categories={categories}
        sensitive={sensitive}
        value={category}
        onChange={onChangeCategory}
      />

      <TextInput
        value={questionText}
        onChangeText={onChangeQuestion}
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
              onPress={() => onChangeMode(m.key)}
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
        onPress={onToggleOffline}
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

      {category && sensitive[category] ? (
        <Banner tone="warning" title="敏感类别提示" style={styles.sensitive}>
          {sensitive[category]}
        </Banner>
      ) : null}

      <Button
        label={reportExists ? '重新生成报告' : '生成报告'}
        size="lg"
        loading={loading}
        disabled={disabled}
        style={styles.genBtn}
        onPress={onGenerate}
      />
    </Card>
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
  const [openFootnote, setOpenFootnote] = useState(false);
  const entries = Object.entries(data).filter(([, v]) => isRecord(v) && Object.keys(v).length > 0);

  if (entries.length === 0) {
    return <EmptyState title={emptyHint} />;
  }

  return (
    <>
      <FoldList
        items={entries}
        /* 每个模块块都比较高，一屏只放 2 块；其余进「更多」浮层（浮层可滚） */
        max={2}
        keyOf={([key]) => key}
        moreTitle="全部条目"
        tone="light"
        renderItem={([key, value]) => (
          <Card title={MODULE_TITLES[key] ?? key}>
            <FactList data={value} />
          </Card>
        )}
      />
      <Pressable
        onPress={() => setOpenFootnote(true)}
        accessibilityRole="button"
        accessibilityLabel="查看规则来源"
        style={styles.link}
      >
        <Ionicons name="information-circle-outline" size={14} color={colors.primary} />
        <AppText size="xs" color="primary" style={styles.linkText}>
          规则来源
        </AppText>
      </Pressable>
      <InfoPopup
        visible={openFootnote}
        onClose={() => setOpenFootnote(false)}
        title="规则来源"
        subtitle="这一层是怎么来的"
      >
        <AppText size="sm" color={colors.text}>
          {footnote}
        </AppText>
      </InfoPopup>
    </>
  );
}

// ==========================================================================
// AI 解读标签
// ==========================================================================

function AiTab({
  report,
  register,
  onChangeRegister,
  followUp,
  onChangeFollowUp,
  onAsk,
  askLoading,
  askError,
  askFixable,
  allTurns,
}: {
  report: Report;
  register: RegisterTab;
  onChangeRegister: (r: RegisterTab) => void;
  followUp: string;
  onChangeFollowUp: (v: string) => void;
  onAsk: () => void;
  askLoading: boolean;
  askError: string | null;
  askFixable: boolean;
  allTurns: readonly Turn[];
}): React.JSX.Element {
  const [openUncertainty, setOpenUncertainty] = useState(false);
  const [openWarnings, setOpenWarnings] = useState(false);
  const [openProvenance, setOpenProvenance] = useState(false);
  const [openAsk, setOpenAsk] = useState(false);
  const [fullSection, setFullSection] = useState<ReportSection | null>(null);

  const interp = report.interpretation;
  const sections = register === 'plain' ? interp.plain_sections : interp.sections;

  return (
    <>
      {interp.degraded ? (
        <Banner tone="warning" title="本次已降级生成">
          {interp.attempts
            .map((a) => `${a.ok ? '✓' : '✕'} ${a.provider}/${a.model}：${a.detail}`)
            .join('\n')}
        </Banner>
      ) : null}

      {/* ---------- 文体切换 ----------
          只在**真的有白话版**时才显示切换：
          没有白话版却显示一个切过去是空的按钮，比不显示更糟。 */}
      {interp.has_plain ? (
        <SegmentedTabs<RegisterTab>
          value={register}
          onChange={onChangeRegister}
          items={[
            { key: 'expert', label: REGISTER_LABEL.expert },
            { key: 'plain', label: REGISTER_LABEL.plain },
          ]}
        />
      ) : (
        <Banner tone="info" title="本篇只有专业分析">
          生成时没有产出白话版（通常是模型没按格式输出）。
          这里如实告诉你，而不是拿专业版冒充白话版 —— 若需要白话版，可重新生成一次。
        </Banner>
      )}

      {/* ---------- 正文：限行 + 「展开全文」浮层 ---------- */}
      <FoldList
        items={sections}
        /* 一段就是一屏里的一大块，只留一段；其余进「更多」浮层 */
        max={1}
        keyOf={(s, i) => `${register}-${i}-${s.title}`}
        moreTitle="全部解读段落"
        tone="light"
        renderItem={(s) => (
          <Card title={s.title}>
            <AppText size="md" lineHeightRatio={1.2} numberOfLines={4}>
              {s.body}
            </AppText>
            {s.body.length > 60 ? (
              <Pressable
                onPress={() => setFullSection(s)}
                accessibilityRole="button"
                accessibilityLabel={`展开${s.title}全文`}
                style={styles.link}
              >
                <Ionicons name="expand-outline" size={14} color={colors.primary} />
                <AppText size="xs" color="primary" style={styles.linkText}>
                  展开全文
                </AppText>
              </Pressable>
            ) : null}
          </Card>
        )}
      />

      {/* ---------- 依据 / 不确定性 / 过程提示 / 追问：一行入口，内容进浮层 ---------- */}
      <View style={styles.linkRow}>
        <LinkChip icon="shield-checkmark-outline" label="依据" onPress={() => setOpenProvenance(true)} />
        {report.uncertainties.length > 0 ? (
          <LinkChip
            icon="alert-circle-outline"
            label={`不确定性 ${report.uncertainties.length}`}
            onPress={() => setOpenUncertainty(true)}
          />
        ) : null}
        {interp.warnings.length > 0 ? (
          <LinkChip
            icon="information-circle-outline"
            label="过程提示"
            onPress={() => setOpenWarnings(true)}
          />
        ) : null}
        <LinkChip
          icon="chatbubble-ellipses-outline"
          label={allTurns.length > 0 ? `追问 ${allTurns.length}` : '追问'}
          onPress={() => setOpenAsk(true)}
        />
      </View>

      <InfoPopup
        visible={openProvenance}
        onClose={() => setOpenProvenance(false)}
        title="依据"
        subtitle="这一层是怎么来的"
      >
        <AppText size="sm" color={colors.text}>
          由 {interp.provider} / {interp.model} 生成
          {interp.usage ? `，消耗 ${interp.usage.total_tokens} tokens` : ''}。
        </AppText>
        <AppText size="sm" color={colors.textSecondary}>
          「盘面事实」「传统分析」来自确定性计算，AI 只读不改；本页文本才是模型写的。
        </AppText>
      </InfoPopup>

      {report.uncertainties.length > 0 ? (
        <InfoPopup
          visible={openUncertainty}
          onClose={() => setOpenUncertainty(false)}
          title="不确定性说明"
          subtitle={`共 ${report.uncertainties.length} 条`}
        >
          <UncertaintyList items={report.uncertainties} />
        </InfoPopup>
      ) : null}

      {interp.warnings.length > 0 ? (
        <InfoPopup
          visible={openWarnings}
          onClose={() => setOpenWarnings(false)}
          title="生成过程提示"
          subtitle={`共 ${interp.warnings.length} 条`}
        >
          {interp.warnings.map((w, i) => (
            <AppText key={i} size="sm" color={colors.text}>
              {w}
            </AppText>
          ))}
        </InfoPopup>
      ) : null}

      {fullSection ? (
        <InfoPopup
          visible={fullSection !== null}
          onClose={() => setFullSection(null)}
          title={fullSection.title}
          subtitle="全文"
        >
          <AppText size="md" lineHeightRatio={1.25}>
            {fullSection.body}
          </AppText>
        </InfoPopup>
      ) : null}

      {/* ---------- 继续追问：输入与留痕都收进浮层 ---------- */}
      <InfoPopup
        visible={openAsk}
        onClose={() => setOpenAsk(false)}
        title="继续追问"
        subtitle="不会改动盘面事实与传统分析"
      >
        <TextInput
          value={followUp}
          onChangeText={onChangeFollowUp}
          placeholder="就这份盘面继续问，例如：那明年呢"
          placeholderTextColor={colors.muted}
          style={styles.input}
          multiline
          maxLength={200}
          accessibilityLabel="追问内容"
        />
        {askError ? (
          <Banner tone={askFixable ? 'warning' : 'error'} title="追问失败">
            {askError}
          </Banner>
        ) : null}
        <Button
          label="追问"
          variant="secondary"
          loading={askLoading}
          disabled={followUp.trim().length === 0}
          onPress={onAsk}
        />
        <AppText size="xs" color="muted" style={styles.askHint}>
          追问不会改动盘面事实与传统分析 —— 计算层结果与问题无关。
        </AppText>

        <ThreadView turns={allTurns} />
      </InfoPopup>
    </>
  );
}

// ==========================================================================
// 行内入口（图标 + 文字）
// ==========================================================================

function LinkChip({
  icon,
  label,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={styles.linkChip}
    >
      <Ionicons name={icon} size={14} color={colors.primary} />
      <AppText size="xs" color="primary" style={styles.linkText}>
        {label}
      </AppText>
    </Pressable>
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

  headerAction: { flexDirection: 'row', alignItems: 'center' },
  headerActionText: { marginLeft: 2 },

  link: { flexDirection: 'row', alignItems: 'center', marginTop: space[2] },
  linkText: { marginLeft: 2 },
  linkRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: space[3] },
  linkChip: { flexDirection: 'row', alignItems: 'center' },

  askHint: { lineHeight: 16 },

  thread: { marginTop: space[2], gap: space[3] },
  turn: {
    borderRadius: radius.md,
    padding: space[3],
    borderWidth: 1,
    borderColor: colors.border,
  },
  turnUser: { backgroundColor: colors.surfaceAlt },
  turnAssistant: { backgroundColor: colors.surface },
  turnRole: { marginBottom: space[1] },

  disclaimer: { marginTop: space[3] },
  reportId: { marginTop: space[1] },
});
