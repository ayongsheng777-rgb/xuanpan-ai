/**
 * 我的 —— 设置与说明。
 *
 * ⚠️ **本页不提供模型 API Key 的录入**（AGENTS.md §5.5 红线：密钥不进 APK、
 * 不写死在 JS、不返回前端）。模型能力与可用性一律从服务端
 * `/meta/ai-providers` 读取后**只读展示** ——
 * 客户端只负责告诉用户"服务端现在能用什么"，密钥始终留在服务端。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { Linking, Pressable, StyleSheet, TextInput, View } from 'react-native';

import { ApiClient, getApiClient, resolveBaseUrl, setApiBaseUrl } from '@/api/client';
import type { AiProvidersResponse, CapabilitiesResponse } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, Divider, KeyValueRow } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { colors, radius, space, tint } from '@/theme/tokens';

const APP_VERSION = '0.1.0';

export default function MineScreen(): React.JSX.Element {
  const router = useRouter();

  const load = useCallback(async () => {
    const client = getApiClient();
    const [providers, caps, disclaimer] = await Promise.all([
      client.aiProviders(),
      client.capabilities(),
      client.disclaimer(),
    ]);
    return { providers, caps, disclaimer: disclaimer.disclaimer };
  }, []);

  const { data, loading, error, reload } = useAsync(load, []);

  return (
    <Screen scroll onRefresh={reload} refreshing={loading && data !== null}>
      {error ? (
        <Banner tone="error" title="无法读取服务端配置">
          {error}
        </Banner>
      ) : null}

      <AiModelCard data={data?.providers ?? null} />
      <NetworkCard onApplied={reload} />
      <PrivacyCard caps={data?.caps ?? null} />
      <DataCard onGoHistory={() => router.push('/history')} />
      <AboutCard disclaimer={data?.disclaimer ?? null} />
    </Screen>
  );
}

// ==========================================================================
// AI 模型（只读）
// ==========================================================================

function AiModelCard({ data }: { data: AiProvidersResponse | null }): React.JSX.Element {
  return (
    <Card title="AI 模型（由服务端配置）">
      <AppText size="xs" color="muted" style={styles.note}>
        密钥保存在服务端，不进入本 App。此处只展示服务端当前**能用什么**。
      </AppText>

      {data === null ? (
        <AppText size="sm" color="muted">
          读取中…
        </AppText>
      ) : (
        data.providers.map((p, i, arr) => (
          <View key={p.id} style={styles.providerRow}>
            <View style={styles.providerHead}>
              <AppText size="md" weight="medium">
                {p.name}
              </AppText>
              <View
                style={[
                  styles.statusPill,
                  { backgroundColor: p.available ? tint.jadePill : colors.surfaceAlt },
                ]}
              >
                <AppText size="xs" color={p.available ? 'success' : 'muted'}>
                  {p.available ? '可用' : p.requires_api_key ? '未配置密钥' : '不可用'}
                </AppText>
              </View>
            </View>
            <AppText size="xs" color="textSecondary" style={styles.providerDesc}>
              {p.description}
            </AppText>
            <AppText size="xs" color="muted" style={styles.providerCost}>
              成本：{p.cost}
              {i === arr.length - 1 ? '' : ''}
            </AppText>
            {i < arr.length - 1 ? <Divider /> : null}
          </View>
        ))
      )}
    </Card>
  );
}

// ==========================================================================
// 网络线路
// ==========================================================================

function NetworkCard({ onApplied }: { onApplied: () => void }): React.JSX.Element {
  const [value, setValue] = useState(resolveBaseUrl());
  const [applied, setApplied] = useState<string | null>(null);

  const apply = useSubmit(async (url: string) => {
    const trimmed = url.trim().replace(/\/+$/, '');
    if (!/^https?:\/\//.test(trimmed)) {
      throw new Error('地址需以 http:// 或 https:// 开头');
    }
    // 先用**临时客户端**探活，成功了再切换全局地址 ——
    // 否则用户改了个错地址，界面会立刻变成"全部请求都失败"，连改回来的入口都难找
    const probe = new ApiClient({ baseUrl: trimmed });
    await probe.health();
    setApiBaseUrl(trimmed);
    setApplied(trimmed);
    return trimmed;
  });

  return (
    <Card title="网络线路">
      <AppText size="xs" color="muted" style={styles.note}>
        后端服务地址。默认 {resolveBaseUrl()}。
        真机调试需改成运行后端那台机器的局域网 IP（如 http://192.168.1.10:8360）。
      </AppText>

      <TextInput
        value={value}
        onChangeText={setValue}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        placeholder="http://127.0.0.1:8360"
        placeholderTextColor={colors.muted}
        style={styles.input}
      />

      <Button
        label="测试并应用"
        variant="secondary"
        loading={apply.loading}
        onPress={() => apply.run(value)}
        style={styles.applyBtn}
      />

      {apply.error ? (
        <AppText size="sm" color="danger" style={styles.applyMsg}>
          {apply.error}
        </AppText>
      ) : null}
      {applied ? (
        <AppText size="sm" color="success" style={styles.applyMsg}>
          ✓ 已连接到 {applied}
        </AppText>
      ) : null}

      <AppText size="xs" color="muted" style={styles.note}>
        注：地址目前仅在本次运行内生效。持久化需要引入本地存储依赖，
        按 AGENTS.md §5.4 需先说明成本与替代方案后再引入，故暂未加入。
      </AppText>
      <Button label="刷新服务端状态" variant="ghost" onPress={onApplied} style={styles.refreshBtn} />
    </Card>
  );
}

// ==========================================================================
// 隐私
// ==========================================================================

function PrivacyCard({ caps }: { caps: CapabilitiesResponse | null }): React.JSX.Element {
  return (
    <Card title="隐私与数据">
      <AppText size="sm" style={styles.privacyLine}>
        罗盘照片**仅用于识别**，分析完成后默认不保留原图；生辰信息仅用于排盘，
        可随时一键删除全部记录。
      </AppText>
      <Divider />
      <KeyValueRow
        label="原图留存"
        value="默认不留存（识别后即从内存释放）"
      />
      <KeyValueRow
        label="数据外流"
        value="罗盘照片会上传到服务端完成识别；AI 解读只接收结构化结果，不接收原图与原始生辰文本"
      />
      <KeyValueRow
        label="分金规则表"
        value={caps ? (caps.fenjin_table_available ? '已就绪' : '未提供（分金仅输出几何格位）') : '读取中…'}
        last
      />
    </Card>
  );
}

// ==========================================================================
// 数据管理
// ==========================================================================

function DataCard({ onGoHistory }: { onGoHistory: () => void }): React.JSX.Element {
  return (
    <Card title="数据管理">
      <AppText size="xs" color="muted" style={styles.note}>
        删除在历史页逐条进行（长按或进入详情页）。批量清空需要服务端提供对应接口，
        当前版本未实现，不做假按钮。
      </AppText>
      <Button label="打开历史，管理记录" variant="ghost" onPress={onGoHistory} />
    </Card>
  );
}

// ==========================================================================
// 关于
// ==========================================================================

const RULES = [
  '所有数值由确定性代码计算，AI 不参与计算、不得修改计算结果',
  '识别结果必须经你确认后才进入计算',
  '看不清 / 无法确定时返回「未定」，不做猜测',
  '规则变更必须同步测试；规则不散落在界面里',
] as const;

function AboutCard({ disclaimer }: { disclaimer: string | null }): React.JSX.Element {
  return (
    <Card title="关于">
      <KeyValueRow label="版本" value={APP_VERSION} />
      <KeyValueRow label="产品" value="玄盘 AI" last />

      <Divider />
      <AppText size="sm" weight="semibold" color="textSecondary">
        本产品坚持的几条底线
      </AppText>
      <View style={styles.rules}>
        {RULES.map((r) => (
          <AppText key={r} size="sm" style={styles.rule}>
            · {r}
          </AppText>
        ))}
      </View>

      <Divider />
      <AppText size="sm" color="textSecondary">
        {disclaimer ?? '以上内容属于传统文化娱乐/学习参考'}
      </AppText>

      <Pressable
        onPress={() => void Linking.openURL('https://www.workbuddy.cn/docs/workbuddy/Overview')}
        style={styles.link}
      >
        <Ionicons name="open-outline" size={16} color={colors.primary} />
        <AppText size="sm" color="primary" style={styles.linkText}>
          查看接口文档（服务端 /docs）
        </AppText>
      </Pressable>
    </Card>
  );
}

const styles = StyleSheet.create({
  note: { lineHeight: 18, marginBottom: space[3] },
  providerRow: { paddingVertical: space[2] },
  providerHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  statusPill: { borderRadius: radius.pill, paddingHorizontal: space[2], paddingVertical: 2 },
  providerDesc: { marginTop: space[1], lineHeight: 18 },
  providerCost: { marginTop: 2 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.bg,
    paddingHorizontal: space[3],
    paddingVertical: space[2] + 1,
    fontSize: 15,
    color: colors.text,
  },
  applyBtn: { marginTop: space[3] },
  applyMsg: { marginTop: space[2] },
  refreshBtn: { marginTop: space[3] },
  privacyLine: { lineHeight: 22 },
  rules: { gap: space[1], marginTop: space[2] },
  rule: { lineHeight: 20 },
  link: { flexDirection: 'row', alignItems: 'center', marginTop: space[4] },
  linkText: { marginLeft: space[2] },
});
