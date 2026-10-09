/**
 * AI 模型中心 —— 我的 → AI 模型。
 *
 * 设计规范（docs/玄盘 AI — UI、模型配置与网络线路设计规范.md §七/§八）：
 * 按**能力**而非品牌组织 —— Vision（看图）、Reasoning（解读）、
 * Fast（快问快答）、Fallback（备用）。换模型不用改 App。
 *
 * 安全边界（AGENTS.md §5.5）：
 * - App 只选"用哪个模型"，**密钥永不进 App**。
 * - 密钥在服务端管理台（/admin）或环境变量里配。
 * - 选模型调 POST /meta/ai-model-selection，后端只接受 model/capability，
 *   拒绝 api_key/base_url，从接口层就堵死。
 */

import { useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import { useAsync } from '@/lib/useAsync';
import { AppText } from '@/components/AppText';
import { Button, Card } from '@/components/Card';
import { InfoPopup } from '@/components/InfoPopup';
import { Screen } from '@/components/Screen';
import type { AiProvidersResponse, ProviderInfo } from '@/api/types';
import { colors, radius, space } from '@/theme/tokens';

/** 能力白话：用户看到的是"用来干嘛"，不是英文单词。 */
const CAPABILITY_PLAIN: Record<string, { title: string; desc: string }> = {
  vision: { title: '看图识别', desc: '看罗盘照片，认出盘面和角度' },
  reasoning: { title: '智能解读', desc: '把算出来的盘讲成人话' },
  fast: { title: '快速问答', desc: '日常问答，速度快、便宜' },
  fallback: { title: '备用线路', desc: '主线路坏了顶上去，保证不断' },
  embedding: { title: '文本向量', desc: '高级功能用，平时用不到' },
};

export default function AiModelScreen(): React.JSX.Element {
  const router = useRouter();
  const { data, loading, error, reload } = useAsync(
    useCallback(() => getApiClient().aiProviders(), []),
  );
  const [selecting, setSelecting] = useState<ProviderInfo | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const doSelect = async (p: ProviderInfo) => {
    setSaving(true);
    setSaveMsg(null);
    try {
      await getApiClient().setAiModelSelection(p.id, p.capability);
      setSaveMsg(`已切换为「${p.name}」`);
      setSelecting(null);
      void reload();
    } catch (e) {
      setSaveMsg(e instanceof Error ? `切换失败：${e.message}` : '切换失败');
    } finally {
      setSaving(false);
    }
  };

  // 按能力分组
  const byCap = new Map<string, ProviderInfo[]>();
  for (const p of data?.providers ?? []) {
    const list = byCap.get(p.capability) ?? [];
    list.push(p);
    byCap.set(p.capability, list);
  }

  return (
    <Screen style={styles.root}>
      <AppText size="xl" weight="bold" color={colors.text} style={styles.title}>
        AI 模型
      </AppText>
      <AppText size="sm" color={colors.textSecondary} style={styles.lead}>
        按用途选模型，不用记品牌。密钥保存在服务端，不进手机。
      </AppText>

      {loading && <AppText color={colors.muted}>读取中…</AppText>}
      {error && (
        <Card title="连不上后端">
          <AppText size="sm" color={colors.textSecondary}>
            读不到模型列表：{error}。先检查「我的 → 网络线路」。
          </AppText>
          <Button label="重试" onPress={() => void reload()} />
        </Card>
      )}

      {[...byCap.entries()].map(([cap, providers]) => {
        const plain = CAPABILITY_PLAIN[cap] ?? { title: cap, desc: '' };
        return (
          <Card key={cap} title={plain.title}>
            <AppText size="xs" color={colors.muted} style={styles.capDesc}>
              {plain.desc}
            </AppText>
            {providers.map((p) => (
              <Pressable
                key={p.id}
                onPress={() => setSelecting(p)}
                style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
              >
                <View style={styles.rowMain}>
                  <AppText size="md" weight="medium" color={colors.text}>
                    {p.name}
                  </AppText>
                  <AppText size="xs" color={colors.muted} numberOfLines={1}>
                    {p.description}
                  </AppText>
                </View>
                <View
                  style={[
                    styles.pill,
                    { backgroundColor: p.available ? '#E8F5E9' : colors.surfaceAlt },
                  ]}
                >
                  <AppText size="xs" color={p.available ? 'success' : 'muted'}>
                    {p.available ? '可用' : p.requires_api_key ? '未配密钥' : '不可用'}
                  </AppText>
                </View>
              </Pressable>
            ))}
          </Card>
        );
      })}

      <Card title="密钥在哪配">
        <AppText size="sm" color={colors.textSecondary} style={styles.note}>
          模型密钥在服务端管理台配（/admin，需令牌），不经过手机。
          App 里只能选"用哪个"，选完即时生效。
        </AppText>
        <Button label="返回" onPress={() => router.back()} />
      </Card>

      {/* 选模型确认框 */}
      <InfoPopup
        visible={selecting !== null}
        onClose={() => setSelecting(null)}
        title="切换模型"
        subtitle={selecting ? CAPABILITY_PLAIN[selecting.capability]?.title ?? '' : ''}
      >
        {selecting && (
          <>
            <AppText size="md" color={colors.text} style={styles.popupBody}>
              换成「{selecting.name}」？
            </AppText>
            <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
              {selecting.description}
            </AppText>
            {!selecting.available && (
              <AppText size="sm" color={colors.warning} style={styles.popupBody}>
                注意：该模型当前{selecting.requires_api_key ? '未配置密钥' : '不可用'}，
                切换后相关功能可能无法使用。
              </AppText>
            )}
            {saveMsg && (
              <AppText size="sm" color={colors.text} style={styles.popupBody}>
                {saveMsg}
              </AppText>
            )}
            <Button
              label={saving ? '切换中…' : `确认为${CAPABILITY_PLAIN[selecting.capability]?.title ?? ''}用此模型`}
              onPress={() => void doSelect(selecting)}
            />
          </>
        )}
      </InfoPopup>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: colors.bg },
  title: { marginBottom: space[1] },
  lead: { marginBottom: space[3], lineHeight: 20 },
  capDesc: { marginBottom: space[2] },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: space[2],
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: space[2],
  },
  rowPressed: { backgroundColor: colors.surfaceAlt },
  rowMain: { flex: 1, gap: 2 },
  pill: { paddingHorizontal: space[2], paddingVertical: 4, borderRadius: radius.pill },
  note: { lineHeight: 22, marginBottom: space[2] },
  popupBody: { lineHeight: 24, marginBottom: space[2] },
});
