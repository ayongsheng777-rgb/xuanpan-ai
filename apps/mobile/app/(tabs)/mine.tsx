/**
 * 我的 —— 设置与说明（2026-10-09 单屏重设计）。
 *
 * ⚠️ **本页不提供模型 API Key 的录入**（AGENTS.md §5.5 红线：密钥不进 APK、
 * 不写死在 JS、不返回前端）。模型能力与可用性一律从服务端
 * `/meta/ai-providers` 读取后**只读展示** ——
 * 客户端只负责告诉用户"服务端现在能用什么"，密钥始终留在服务端。
 *
 * ## 单屏做法：分段标签替代滚动
 *
 * 本页原有 6 张卡（AI 模型 / 我的信息 / 网络线路 / 隐私与数据 / 数据管理 / 关于），
 * 竖排下来要滚两屏多。现在收进三个分段标签：
 *
 *   模型 —— 服务端可用模型（只读）+ 配置入口
 *   我的 —— 我的信息（本地）+ 网络线路（后端地址）
 *   关于 —— 隐私与数据 + 版本与底线
 *
 * 同一时刻只显示一组，**没有一组需要滚动**。分段的划分依据是"用户来找什么"：
 * 想知道"AI 现在能用哪个"去模型，想改地址/生日去我的，其余归关于。
 *
 * ## 🔴 2026-10-10 用户反馈修正
 *
 * 之前默认 `section='model'` —— 但底栏文案是「我的」而不是「模型」，
 * 用户进"我的"页面只看得到一张 AI 模型卡，找不到「我的信息」「网络线路」，
 * 以为页面只剩这一张卡。**默认分段改成 `mine`**，让用户一眼看到自己的内容；
 * 模型与关于分段保留可切换入口。
 */

import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { Linking, Pressable, StyleSheet, TextInput, View } from 'react-native';

import {
  ApiClient,
  getApiClient,
  resetApiBaseUrl,
  resolveBaseUrl,
  setApiBaseUrl,
} from '@/api/client';
import { loadApiBaseUrlOverride } from '@/api/baseUrlStore';
import type { AiProvidersResponse, CapabilitiesResponse } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, Divider, KeyValueRow } from '@/components/Card';
import { FoldList } from '@/components/FoldList';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { colors, radius, space, tint } from '@/theme/tokens';

const APP_VERSION = '0.1.0';

type Section = 'model' | 'mine' | 'about';

const SECTIONS = [
  { key: 'model' as const, label: '模型' },
  { key: 'mine' as const, label: '我的' },
  { key: 'about' as const, label: '关于' },
];

export default function MineScreen(): React.JSX.Element {
  const router = useRouter();
  // 2026-10-10: 默认 `mine` —— 底栏文案是「我的」，进页先看到「我的信息 + 网络线路」，
  // 与用户预期一致；模型 / 关于仍可通过顶部分段切换进入。
  const [section, setSection] = useState<Section>('mine');

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
    <Screen>
      <PageHeader
        title="我的"
        helpTopic="mine"
        tone="light"
        onRefresh={reload}
        refreshing={loading && data !== null}
      />

      <SegmentedTabs items={SECTIONS} value={section} onChange={setSection} />

      {error ? (
        <Banner tone="error" title="无法读取服务端配置">
          <AppText size="sm">{error}</AppText>
        </Banner>
      ) : null}

      {section === 'model' ? <AiModelCard data={data?.providers ?? null} /> : null}

      {section === 'mine' ? (
        <>
          <ProfileCard onGoProfile={() => router.push('/profile')} />
          <NetworkCard onApplied={reload} />
        </>
      ) : null}

      {section === 'about' ? (
        <>
          <PrivacyCard caps={data?.caps ?? null} />
          <DataCard onGoHistory={() => router.push('/history')} />
          <AboutCard disclaimer={data?.disclaimer ?? null} />
        </>
      ) : null}
    </Screen>
  );
}

// ==========================================================================
// AI 模型（只读）
// ==========================================================================

function AiModelCard({ data }: { data: AiProvidersResponse | null }): React.JSX.Element {
  const router = useRouter();
  const providers = data?.providers ?? [];

  return (
    <Card title="AI 模型">
      <AppText size="xs" color="muted" style={styles.note}>
        密钥保存在服务端，不进入本 App。此处只展示服务端当前能用什么。
      </AppText>

      {data === null ? (
        <AppText size="sm" color="muted">
          读取中…
        </AppText>
      ) : (
        <FoldList
          items={providers}
          max={3}
          keyOf={(p) => p.id}
          moreTitle="全部模型"
          renderItem={(p) => (
            <View style={styles.providerRow}>
              <View style={styles.providerHead}>
                <AppText size="md" weight="medium" numberOfLines={1} style={styles.providerName}>
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
              <AppText size="xs" color="textSecondary" numberOfLines={1} style={styles.providerDesc}>
                {p.description} · 成本：{p.cost}
              </AppText>
            </View>
          )}
        />
      )}
      <Button label="配置模型" onPress={() => router.push('/ai-model')} />
    </Card>
  );
}

// ==========================================================================
// 我的信息（每日运程用，只存本地）
// ==========================================================================

function ProfileCard({ onGoProfile }: { onGoProfile: () => void }): React.JSX.Element {
  return (
    <Card title="我的信息">
      <AppText size="xs" color="muted" style={styles.note}>
        出生日期用来排出你的日主，是「每日早报」里个人运程的依据。只存手机本地，不上传。
      </AppText>
      <Button label="设置我的信息" variant="secondary" onPress={onGoProfile} />
    </Card>
  );
}

// ==========================================================================
// 网络线路
// ==========================================================================

function NetworkCard({ onApplied }: { onApplied: () => void }): React.JSX.Element {
  // 输入框初始值：优先显示用户上次手设并已存住的地址，没有才显示构建默认值。
  // 读存储是异步的，先给空字符串，读回来再填 —— 避免一闪而过显示错地址。
  const [value, setValue] = useState('');
  const [applied, setApplied] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void (async () => {
      const override = await loadApiBaseUrlOverride(AsyncStorage);
      if (!alive) return;
      setValue(override ?? resolveBaseUrl());
    })();
    return () => {
      alive = false;
    };
  }, []);

  const apply = useSubmit(async (url: string) => {
    const trimmed = url.trim().replace(/\/+$/, '');
    if (!/^https?:\/\//.test(trimmed)) {
      throw new Error('地址需以 http:// 或 https:// 开头');
    }
    // 先用**临时客户端**探活，成功了再切换全局地址 ——
    // 否则用户改了个错地址，界面会立刻变成"全部请求都失败"，连改回来的入口都难找
    const probe = new ApiClient({ baseUrl: trimmed });
    await probe.health();
    // setApiBaseUrl 内部已持久化到手机本地：下次打开 App 仍然用这个地址
    setApiBaseUrl(trimmed);
    setApplied(trimmed);
    return trimmed;
  });

  const reset = useSubmit(async () => {
    const url = await resetApiBaseUrl();
    setValue(url);
    setApplied(null);
    return url;
  });

  return (
    <Card title="网络线路">
      <AppText size="xs" color="muted" style={styles.note}>
        后端服务地址。默认 {resolveBaseUrl()}。真机需改成运行后端那台机器的地址。
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
        <AppText size="sm" color="success" numberOfLines={1} style={styles.applyMsg}>
          ✓ 已保存并连接到 {applied}，下次打开 App 仍然用这个地址
        </AppText>
      ) : null}

      <View style={styles.networkBtnRow}>
        <Button
          label="恢复默认"
          variant="ghost"
          loading={reset.loading}
          onPress={() => reset.run()}
          style={styles.networkBtn}
        />
        <Button label="刷新服务端状态" variant="ghost" onPress={onApplied} style={styles.networkBtn} />
      </View>
      {reset.error ? (
        <AppText size="sm" color="danger" style={styles.applyMsg}>
          {reset.error}
        </AppText>
      ) : null}
    </Card>
  );
}

// ==========================================================================
// 隐私
// ==========================================================================

function PrivacyCard({ caps }: { caps: CapabilitiesResponse | null }): React.JSX.Element {
  const [open, setOpen] = useState(false);
  return (
    <Card title="隐私与数据">
      <KeyValueRow label="原图留存" value="默认不留存（识别后即从内存释放）" />
      <KeyValueRow
        label="数据外流"
        value="照片上传服务端识别；AI 只接收结构化结果"
        last
      />
      <KeyValueRow
        label="分金规则表"
        value={caps ? (caps.fenjin_table_available ? '已就绪' : '未提供（分金仅输出几何格位）') : '读取中…'}
        last
      />
      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel="隐私细节说明"
        style={styles.link}
      >
        <Ionicons name="information-circle-outline" size={15} color={colors.primary} />
        <AppText size="sm" color="primary" style={styles.linkText}>
          隐私细节
        </AppText>
      </Pressable>
      <InfoPopup visible={open} onClose={() => setOpen(false)} title="隐私与数据" subtitle="细节说明">
        <AppText size="sm" color={colors.text} style={styles.popupBody}>
          罗盘照片仅用于识别，分析完成后默认不保留原图；生辰信息仅用于排盘，可随时一键删除全部记录。
        </AppText>
        <AppText size="sm" color={colors.textSecondary} style={styles.popupBody}>
          罗盘照片会上传到服务端完成识别；AI 解读只接收结构化结果，不接收原图与原始生辰文本。
        </AppText>
      </InfoPopup>
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
        删除在历史页逐条进行。批量清空需要服务端提供对应接口，当前版本未实现，不做假按钮。
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
  const [open, setOpen] = useState(false);
  return (
    <Card title="关于">
      <KeyValueRow label="版本" value={APP_VERSION} />
      <KeyValueRow label="产品" value="玄盘 AI" last />

      <Pressable
        onPress={() => setOpen(true)}
        accessibilityRole="button"
        accessibilityLabel="本产品坚持的几条底线"
        style={styles.link}
      >
        <Ionicons name="shield-checkmark-outline" size={15} color={colors.primary} />
        <AppText size="sm" color="primary" style={styles.linkText}>
          本产品坚持的几条底线
        </AppText>
      </Pressable>

      <InfoPopup
        visible={open}
        onClose={() => setOpen(false)}
        title="本产品坚持的底线"
        subtitle="四条不可让步的规则"
      >
        {RULES.map((r) => (
          <AppText key={r} size="sm" color={colors.text} style={styles.popupBody}>
            · {r}
          </AppText>
        ))}
      </InfoPopup>

      <Divider />
      <AppText size="sm" color="textSecondary" numberOfLines={2}>
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
  providerRow: { paddingVertical: space[1] },
  providerHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  providerName: { flex: 1, marginRight: space[2] },
  statusPill: { borderRadius: radius.pill, paddingHorizontal: space[2], paddingVertical: 2 },
  providerDesc: { marginTop: 2 },
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
  networkBtnRow: { flexDirection: 'row', gap: space[2], marginTop: space[3] },
  networkBtn: { flex: 1 },
  link: { flexDirection: 'row', alignItems: 'center', marginTop: space[3] },
  linkText: { marginLeft: space[2] },
  popupBody: { lineHeight: 22 },
});
