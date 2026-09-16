/**
 * 会话详情 —— **记录视角**，回答"这次是怎么算出来的"。
 *
 * 与报告页（`report/[sessionId]`，结论视角）刻意分开：
 *   - 详情页展示**依据**：识别快照、确认状态、你当初填了什么
 *   - 报告页展示**结论**：三层分离的渲染
 * 把两者混在一页，用户就没法回答"结论不对时，是输入错了还是解读错了"。
 *
 * 一个容易被忽略但必须显示的东西：`build_error`。内核升级后旧输入可能不再成立
 * （例如某个字段的取值被收紧），此时后端的做法是**如实报"算不出来"**而不是返回空结果。
 * 界面必须显式呈现它 —— 否则用户看到的是"盘面空了一格"，会以为是自己没填。
 */

import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useMemo } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { ModuleName, SessionDetail } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, EmptyState, KeyValueRow } from '@/components/Card';
import { FactList } from '@/components/FactList';
import { Screen } from '@/components/Screen';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

const MODULE_LABEL: Record<string, string> = {
  compass: '罗盘坐向',
  bazi: '八字命盘',
  liuyao: '六爻卦象',
  qian: '灵签',
  name: '姓名分析',
};

const INPUT_LABEL: Record<string, string> = {
  compass_input: '坐向输入',
  bazi_input: '生辰输入',
  liuyao_input: '起卦输入',
  qian_input: '抽签输入',
  naming_input: '姓名输入',
};

const ORIGIN_LABEL: Record<string, string> = {
  scan: '拍照识别',
  manual: '手动录入',
  import: '导入',
};

export default function SessionDetailScreen(): React.JSX.Element {
  const router = useRouter();
  const { sessionId } = useLocalSearchParams<{ sessionId?: string }>();
  const id = sessionId ?? '';

  const api = useMemo(() => getApiClient(), []);
  const session = useAsync(useCallback(() => api.getSession(id), [api, id]), [id]);

  const remove = useSubmit(useCallback(() => api.deleteSession(id), [api, id]));

  const onDelete = useCallback(() => {
    Alert.alert(
      '删除这条记录？',
      '会一并删除它生成的全部报告与追问记录。此操作不可撤销。',
      [
        { text: '取消', style: 'cancel' },
        {
          text: '删除',
          style: 'destructive',
          onPress: () => {
            void (async () => {
              const res = await remove.run();
              if (res?.deleted) router.back();
            })();
          },
        },
      ],
      { cancelable: true },
    );
  }, [remove, router]);

  if (!id) {
    return (
      <Screen>
        <EmptyState title="缺少会话标识" hint="请从「历史」列表进入。" />
      </Screen>
    );
  }

  if (session.loading && !session.data) {
    return (
      <Screen>
        <AppText size="sm" color="textSecondary" center style={styles.loadingText}>
          正在读取记录…
        </AppText>
      </Screen>
    );
  }

  if (session.error && !session.data) {
    return (
      <Screen>
        <Banner tone="error" title="无法读取记录">
          {session.error}
        </Banner>
        <Button label="重试" variant="secondary" onPress={session.reload} />
      </Screen>
    );
  }

  const d = session.data;
  if (!d) {
    return (
      <Screen>
        <EmptyState title="记录不存在" hint="它可能已被删除。" />
      </Screen>
    );
  }

  const hasReport = d.report_count > 0;

  return (
    <Screen scroll bottomInsetExtra={space[10]}>
      <Card title="记录">
        <AppText size="lg" weight="semibold" color="primary">
          {d.title || '未命名'}
        </AppText>
        <View style={styles.chipRow}>
          {d.modules.length > 0 ? (
            d.modules.map((m: ModuleName) => (
              <View key={m} style={styles.chip}>
                <AppText size="xs" color="textSecondary">
                  {MODULE_LABEL[m] ?? m}
                </AppText>
              </View>
            ))
          ) : (
            <AppText size="xs" color="muted">
              尚未录入任何信息
            </AppText>
          )}
          {hasReport ? (
            <View style={[styles.chip, styles.chipReport]}>
              <AppText size="xs" color="primary">
                {d.report_count} 份报告
              </AppText>
            </View>
          ) : null}
        </View>

        <View style={styles.kvBlock}>
          {d.question.category ? (
            <KeyValueRow label="所问类别" value={d.question.category} />
          ) : null}
          {d.question.text ? <KeyValueRow label="问题" value={d.question.text} /> : null}
          <KeyValueRow label="来源" value={ORIGIN_LABEL[d.origin] ?? d.origin} />
          <KeyValueRow label="创建时间" value={formatStamp(d.created_at)} />
          <KeyValueRow label="最近更新" value={formatStamp(d.updated_at)} last />
        </View>
      </Card>

      {d.build_error ? (
        <Banner tone="error" title="这份记录当前算不出来">
          {d.build_error}
          {'\n'}这通常意味着录入的内容在内核升级后不再成立。原始输入仍完整保留在下方，
          可以据此重新录入。
        </Banner>
      ) : null}

      {d.confirm_state ? (
        <Card title="坐向确认">
          <AppText size="xl" weight="bold" color="primary" style={styles.confirmMain}>
            坐 {d.confirm_state.sitting} 山 ／ 向 {d.confirm_state.facing} 山
          </AppText>
          {d.confirm_state.degree !== null ? (
            <AppText size="sm" color="textSecondary" style={styles.confirmSub}>
              提交角度 {d.confirm_state.degree.toFixed(2)}°
            </AppText>
          ) : (
            <AppText size="sm" color="muted" style={styles.confirmSub}>
              未提交实测角度，分金按山心角计算
            </AppText>
          )}
          {d.confirm_state.user_note ? (
            <AppText size="sm" color="textSecondary" style={styles.confirmNote}>
              备注：{d.confirm_state.user_note}
            </AppText>
          ) : null}
          <AppText size="xs" color="muted" style={styles.confirmHint}>
            已由你确认（RULE-004）。照片识别原件单独保留在下方，便于核对当时依据。
          </AppText>
        </Card>
      ) : d.recognition?.compass_detected ? (
        <Banner tone="warning" title="识别结果尚未确认">
          这张照片识别出了候选坐向，但还没有经过你的确认，因此不计入计算。
        </Banner>
      ) : null}

      {d.recognition ? <RecognitionBlock recognition={d.recognition} /> : null}

      {d.modules.length > 0 ? (
        <Card title="已录入的原始输入">
          {Object.entries(d.inputs).map(([column, value]) => {
            if (!value || Object.keys(value).length === 0) return null;
            return (
              <View key={column} style={styles.inputBlock}>
                <AppText size="sm" weight="semibold" color="primary">
                  {INPUT_LABEL[column] ?? column}
                </AppText>
                <View style={styles.inputInner}>
                  <FactList data={value} />
                </View>
              </View>
            );
          })}
          <AppText size="xs" color="muted" style={styles.storageNote}>
            这里存的是你输入的原文，不是计算结果 —— 计算结果每次打开都按当前内核重算，
            所以内核升级后不会出现"库里一份、内核一份"的两套数据。
          </AppText>
        </Card>
      ) : null}

      {Object.keys(d.facts).length > 0 ? (
        <Card title="盘面事实（只读，重算结果）">
          {Object.entries(d.facts).map(([key, value]) => (
            <View key={key} style={styles.inputBlock}>
              <AppText size="sm" weight="semibold" color="primary">
                {MODULE_LABEL[key] ?? key}
              </AppText>
              <View style={styles.inputInner}>
                <FactList data={value} />
              </View>
            </View>
          ))}
        </Card>
      ) : null}

      {Object.keys(d.tradition).length > 0 ? (
        <Card title="传统分析（只读）">
          {Object.entries(d.tradition).map(([key, value]) => (
            <View key={key} style={styles.inputBlock}>
              <AppText size="sm" weight="semibold" color="primary">
                {MODULE_LABEL[key] ?? key}
              </AppText>
              <View style={styles.inputInner}>
                <FactList data={value} />
              </View>
            </View>
          ))}
        </Card>
      ) : null}

      <UncertaintyList items={d.uncertainties} />

      <Button
        label={hasReport ? '查看 / 重新生成报告' : '生成 AI 解读报告'}
        size="lg"
        disabled={d.modules.length === 0}
        icon={<Ionicons name="sparkles" size={18} color={colors.onPrimary} />}
        onPress={() => router.push(`/report/${id}`)}
      />

      {remove.error ? (
        <Banner tone="error" title="删除失败" style={styles.delErr}>
          {remove.error}
        </Banner>
      ) : null}

      <Pressable
        onPress={onDelete}
        disabled={remove.loading}
        accessibilityRole="button"
        style={styles.deleteRow}
      >
        <AppText size="sm" color="danger">
          {remove.loading ? '正在删除…' : '删除这条记录'}
        </AppText>
        <AppText size="xs" color="muted" style={styles.delHint}>
          会一并删除全部报告与追问记录，不可撤销
        </AppText>
      </Pressable>
    </Screen>
  );
}

// ==========================================================================
// 识别快照
// ==========================================================================

function RecognitionBlock({
  recognition,
}: {
  recognition: NonNullable<SessionDetail['recognition']>;
}): React.JSX.Element {
  const sitting = recognition.mountain_candidates.map((c) => c.name);
  const facing = recognition.direction_candidates.map((c) => c.name);

  return (
    <Card title="照片识别原件（只读）">
      <AppText size="sm" color="textSecondary">
        坐山候选：{sitting.join(' ／ ') || '—'}
      </AppText>
      <AppText size="sm" color="textSecondary" style={styles.recogLine}>
        向山候选：{facing.join(' ／ ') || '—'}
      </AppText>
      <AppText size="xs" color="muted" style={styles.recogLine}>
        识别通道：{recognition.provider}；整体置信度{' '}
        {recognition.confidence.toFixed(2)}
      </AppText>

      {recognition.uncertain_regions.length > 0 ? (
        <View style={styles.regionBlock}>
          {recognition.uncertain_regions.map((r, i) => (
            <AppText key={i} size="xs" color="warning" style={styles.regionLine}>
              · {r}
            </AppText>
          ))}
        </View>
      ) : null}

      <AppText size="xs" color="muted" style={styles.recogNote}>
        识别原件不被你的确认结果覆盖 —— 这样"当时机器看到了什么"与"你最终怎么定"
        永远是两条独立可核对的记录。
      </AppText>
    </Card>
  );
}

// ==========================================================================
// 工具
// ==========================================================================

/** 绝对时间戳（详情页要能被引用核对，所以不用"今天 14:03"这种相对表述） */
function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

const styles = StyleSheet.create({
  loadingText: { marginTop: space[10] },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space[1], marginTop: space[2] },
  chip: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    paddingHorizontal: space[2],
    paddingVertical: 2,
  },
  chipReport: { backgroundColor: alpha.primarySoft },
  kvBlock: { marginTop: space[3] },

  confirmMain: { marginBottom: space[1] },
  confirmSub: {},
  confirmNote: { marginTop: space[2] },
  confirmHint: { marginTop: space[2], lineHeight: 16 },

  recogLine: { marginTop: space[1] },
  recogNote: { marginTop: space[3], lineHeight: 16 },
  regionBlock: { marginTop: space[2], gap: 2 },
  regionLine: { lineHeight: 17 },

  inputBlock: { marginTop: space[3] },
  inputInner: { marginTop: space[1] },
  storageNote: { marginTop: space[3], lineHeight: 16 },

  delErr: { marginTop: space[3] },
  deleteRow: { alignItems: 'center', paddingVertical: space[5] },
  delHint: { marginTop: space[1] },
});
