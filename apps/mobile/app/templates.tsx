/**
 * 我的罗盘（模板库）—— 参考图第 6 屏。
 *
 * 模板 = 一套「盘式 + 默认坐向」的命名预设。它解决的重复劳动很具体：
 * 风水师手里的盘是固定的那几面，每次测盘都要重选盘式、重设坐向基准。
 *
 * 三条语义约定：
 *   1. **层数是查出来的，不是存的。** 列表要显示「三元三合综合盘 · 18 层」，
 *      但接口里没有层数字段 —— 层数由 `DIAL_STYLES[style].statedLayers` 查得。
 *      后端存层数会导致「列表写 18 层、打开画出 6 层」而两边都不报错。
 *   2. **未知盘式回落，不崩。** 接口的 `style` 声明成 string 而非联合类型，
 *      因为后端刻意不校验枚举（删掉某个盘式后旧模板仍要能读出来）。
 *      故此处一律过 `coerceDialStyle`。
 *   3. **删除要二次确认，且用内联确认而不是弹窗。**
 *      `Alert.alert` 在 web/部分安卓定制系统上不可靠，且模板是用户手工积累的，
 *      误删一个用了很久的预设没有撤销路径。
 */

import { Ionicons } from '@expo/vector-icons';
import { Stack, useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { CompassTemplate } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button } from '@/components/Card';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { DIAL_STYLES, DIAL_STYLE_ORDER, coerceDialStyle, type DialStyleId } from '@/lib/dialStyle';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { instrument, radius, space } from '@/theme/tokens';

export default function TemplatesScreen(): React.JSX.Element {
  const router = useRouter();
  const api = getApiClient();

  const load = useCallback(() => api.templates(), [api]);
  const { data, error, reload, loading } = useAsync(load, []);

  /** 正在内联确认删除的模板 id —— 只允许一个，避免多个确认条同时展开 */
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);
  /** 新建面板是否展开 */
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [newStyle, setNewStyle] = useState<DialStyleId>('zonghe');

  const toggleFavorite = useSubmit(
    useCallback(
      (tpl: CompassTemplate) => api.updateTemplate(tpl.template_id, { is_favorite: !tpl.is_favorite }),
      [api],
    ),
  );
  const remove = useSubmit(
    useCallback(
      async (id: string) => {
        await api.deleteTemplate(id);
        setPendingDelete(null);
      },
      [api],
    ),
  );
  const create = useSubmit(
    useCallback(
      async (payload: { name: string; style: DialStyleId }) => {
        await api.createTemplate(payload);
        setNewName('');
        setCreating(false);
      },
      [api],
    ),
  );
  // 命名刻意不叫 `use` —— 那会与 React 的 `use()` 撞名，读代码的人会以为调了 hook
  const applyTemplate = useSubmit(
    useCallback(
      // 先记一次使用（影响排序），再带着模板参数进手动调节页
      (tpl: CompassTemplate) => api.useTemplate(tpl.template_id),
      [api],
    ),
  );

  const items = data?.items ?? [];

  const onUse = useCallback(
    async (tpl: CompassTemplate) => {
      const res = await applyTemplate.run(tpl);
      if (!res) return;
      // 手工拼接而非 URLSearchParams：后者在 RN/Hermes 上的实现不完整，
      // 属于"tsc 全绿、一打包才知道"的那类依赖（本项目已踩过一次）。
      const parts = [
        `template=${encodeURIComponent(res.template_id)}`,
        `style=${encodeURIComponent(res.style)}`,
      ];
      if (res.sitting) parts.push(`sitting=${encodeURIComponent(res.sitting)}`);
      if (res.degree !== null) parts.push(`degree=${res.degree}`);
      router.push(`/adjust?${parts.join('&')}`);
    },
    [router, applyTemplate],
  );

  return (
    <Screen scroll bottomInsetExtra={space[8]} style={styles.root}>
      {/* 标题栏自绘（headerShown:false）：深色域页面顶上压一条浅色标题栏会割裂，
          与 index / test 同一处理。 */}
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.head}>
        <AppText size="xl" weight="bold" color={instrument.text}>
          我的罗盘
        </AppText>
        <View style={styles.headActions}>
          <HelpButton topic="templates" color={instrument.textSecondary} />
          <Pressable
            onPress={() => setCreating((v) => !v)}
            accessibilityRole="button"
            accessibilityLabel={creating ? '收起新建面板' : '新建模板'}
            style={styles.addBtn}
          >
            <Ionicons
              name={creating ? 'close' : 'add'}
              size={22}
              color={instrument.accent}
            />
          </Pressable>
        </View>
      </View>

      <AppText size="xs" color={instrument.textSecondary} style={styles.lead}>
        保存常用的盘式与默认坐向，测盘时一键带出。模板不产生任何术数结论，
        只记住「用哪面盘、从哪个基准开始」。
      </AppText>

      {creating ? (
        <View style={styles.createPanel}>
          <AppText size="sm" weight="medium" color={instrument.text}>
            新建模板
          </AppText>
          <TextInput
            value={newName}
            onChangeText={setNewName}
            placeholder="例如：李师傅三元盘"
            placeholderTextColor={instrument.muted}
            maxLength={32}
            style={styles.input}
            accessibilityLabel="模板名称"
          />
          <AppText size="xs" color={instrument.textSecondary} style={styles.pickLabel}>
            盘式
          </AppText>
          <View style={styles.styleRow}>
            {DIAL_STYLE_ORDER.map((sid) => {
              const on = sid === newStyle;
              return (
                <Pressable
                  key={sid}
                  onPress={() => setNewStyle(sid)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: on }}
                  style={[styles.styleChip, on && styles.styleChipOn]}
                >
                  <AppText
                    size="xs"
                    weight={on ? 'semibold' : 'regular'}
                    color={on ? instrument.bg : instrument.textSecondary}
                  >
                    {DIAL_STYLES[sid].name}
                  </AppText>
                  <AppText size="xs" color={on ? instrument.bg : instrument.muted}>
                    {DIAL_STYLES[sid].statedLayers} 层
                  </AppText>
                </Pressable>
              );
            })}
          </View>
          {create.error ? (
            <Banner tone="error" title="创建失败" style={styles.panelBanner}>
              {create.error}
            </Banner>
          ) : null}
          <Button
            label="保存模板"
            loading={create.loading}
            disabled={newName.trim().length === 0}
            onPress={() => void create.run({ name: newName.trim(), style: newStyle })}
            style={styles.panelBtn}
          />
        </View>
      ) : null}

      {error ? (
        <Banner tone="error" title="无法读取模板" style={styles.banner}>
          <AppText size="sm">{error}</AppText>
          <Button label="重试" variant="ghost" style={styles.panelBtn} onPress={reload} />
        </Banner>
      ) : null}

      {toggleFavorite.error ? (
        <Banner tone="warning" title="未能修改常用标记" style={styles.banner}>
          {toggleFavorite.error}
        </Banner>
      ) : null}
      {remove.error ? (
        <Banner tone="error" title="删除失败" style={styles.banner}>
          {remove.error}
        </Banner>
      ) : null}
      {applyTemplate.error ? (
        <Banner tone="warning" title="无法使用该模板" style={styles.banner}>
          {applyTemplate.error}
        </Banner>
      ) : null}

      {loading && items.length === 0 ? (
        <AppText size="sm" color={instrument.textSecondary} center style={styles.loading}>
          正在读取模板…
        </AppText>
      ) : null}

      {!loading && !error && items.length === 0 && !creating ? (
        /* 深色域自绘空态：Card 的 EmptyState 用的是浅色 token（textSecondary
           #6B6154），压在 instrument.bg #0A1626 上对比度不足 —— 空的页面
           加上看不见的说明，等于告诉用户"这里坏了"。 */
        <View style={styles.empty}>
          <Ionicons name="albums-outline" size={28} color={instrument.muted} />
          <AppText size="md" weight="medium" color={instrument.text} center style={styles.emptyTitle}>
            还没有模板
          </AppText>
          <AppText size="xs" color={instrument.textSecondary} center style={styles.emptyHint}>
            点右上角「+」把当前常用的盘式存下来，下次测盘就能一键带出。
          </AppText>
        </View>
      ) : null}

      {items.map((tpl) => (
        <TemplateRow
          key={tpl.template_id}
          tpl={tpl}
          pendingDelete={pendingDelete === tpl.template_id}
          busy={toggleFavorite.loading || remove.loading || applyTemplate.loading}
          onUse={() => void onUse(tpl)}
          onToggleFavorite={() => void toggleFavorite.run(tpl)}
          onAskDelete={() => setPendingDelete(tpl.template_id)}
          onCancelDelete={() => setPendingDelete(null)}
          onConfirmDelete={() => void remove.run(tpl.template_id)}
        />
      ))}

      <AppText size="xs" color={instrument.muted} center style={styles.footnote}>
        模板只保存盘式与坐向参数，不含任何测量数据；删除模板不会影响历史记录。
      </AppText>
    </Screen>
  );
}

// ==========================================================================
// 单条模板
// ==========================================================================

function TemplateRow({
  tpl,
  pendingDelete,
  busy,
  onUse,
  onToggleFavorite,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: {
  tpl: CompassTemplate;
  pendingDelete: boolean;
  busy: boolean;
  onUse: () => void;
  onToggleFavorite: () => void;
  onAskDelete: () => void;
  onCancelDelete: () => void;
  onConfirmDelete: () => void;
}): React.JSX.Element {
  // 接口的 style 可能是未知值（旧存档），故一律回落 —— 直接索引会得到 undefined 而崩
  const sid = coerceDialStyle(tpl.style);
  const style = DIAL_STYLES[sid];
  const unknownStyle = sid !== tpl.style;

  return (
    <View style={styles.row}>
      <Pressable
        onPress={onUse}
        disabled={pendingDelete}
        accessibilityRole="button"
        accessibilityLabel={`使用模板 ${tpl.name}`}
        style={({ pressed }) => [styles.rowMain, pressed && styles.rowPressed]}
      >
        <View style={styles.rowTop}>
          <AppText size="md" weight="medium" color={instrument.text} style={styles.rowName}>
            {tpl.name}
          </AppText>
          {tpl.is_favorite ? (
            <View style={styles.badge}>
              <AppText size="xs" color={instrument.bg}>
                常用
              </AppText>
            </View>
          ) : null}
        </View>

        <AppText size="xs" color={instrument.textSecondary} style={styles.rowMeta}>
          {style.name} · {style.statedLayers} 层
          {tpl.sitting ? ` · 坐${tpl.sitting}` : ''}
          {tpl.school !== 'default' ? ` · ${tpl.school}` : ''}
        </AppText>

        {/* 盘式名对不上时如实说明，而不是假装正常 —— 用户看到的是"18 层"
            却画出 6 层，比直接说"该盘式已不可用"更让人困惑 */}
        {unknownStyle ? (
          <AppText size="xs" color={instrument.warn} style={styles.rowWarn}>
            原盘式「{tpl.style}」已不可用，按「{style.name}」打开
          </AppText>
        ) : null}

        <AppText size="xs" color={instrument.muted} style={styles.rowMeta}>
          {tpl.last_used_at
            ? `上次使用：${tpl.last_used_at.slice(0, 10)}`
            : `创建于：${tpl.created_at.slice(0, 10)}`}
          {tpl.use_count > 0 ? ` · 共用 ${tpl.use_count} 次` : ''}
        </AppText>

        {tpl.note ? (
          <AppText size="xs" color={instrument.textSecondary} style={styles.rowNote}>
            {tpl.note}
          </AppText>
        ) : null}
      </Pressable>

      <View style={styles.rowActions}>
        <IconAction
          icon={tpl.is_favorite ? 'star' : 'star-outline'}
          label={tpl.is_favorite ? '取消常用' : '设为常用'}
          active={tpl.is_favorite}
          disabled={busy || pendingDelete}
          onPress={onToggleFavorite}
        />
        <IconAction
          icon="trash-outline"
          label="删除"
          disabled={busy || pendingDelete}
          onPress={onAskDelete}
        />
      </View>

      {pendingDelete ? (
        <View style={styles.confirmBar}>
          <AppText size="sm" color={instrument.text} style={styles.confirmText}>
            删除「{tpl.name}」？此操作不可撤销。
          </AppText>
          <View style={styles.confirmActions}>
            <Button label="取消" variant="ghost" onPress={onCancelDelete} />
            <Button label="删除" loading={busy} onPress={onConfirmDelete} />
          </View>
        </View>
      ) : null}
    </View>
  );
}

function IconAction({
  icon,
  label,
  active,
  disabled,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      style={({ pressed }) => [styles.iconBtn, pressed && styles.iconBtnPressed, disabled && styles.iconBtnOff]}
    >
      <Ionicons name={icon} size={18} color={active ? instrument.accent : instrument.textSecondary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  head: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headActions: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
  empty: { alignItems: 'center', gap: space[2], paddingVertical: space[8] },
  emptyTitle: { marginTop: space[1] },
  emptyHint: { lineHeight: 17 },
  addBtn: {
    padding: space[2],
    borderRadius: radius.pill,
    backgroundColor: instrument.surface,
  },
  lead: { marginTop: space[2], lineHeight: 18 },
  banner: { marginTop: space[3] },
  loading: { marginTop: space[8] },
  createPanel: {
    marginTop: space[3],
    padding: space[3],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    backgroundColor: instrument.surface,
  },
  input: {
    marginTop: space[2],
    borderWidth: 1,
    borderColor: instrument.border,
    borderRadius: radius.md,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    color: instrument.text,
    backgroundColor: instrument.surfaceAlt,
  },
  pickLabel: { marginTop: space[3] },
  styleRow: { flexDirection: 'row', gap: space[2], marginTop: space[2] },
  styleChip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[2],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: instrument.border,
    backgroundColor: instrument.surfaceAlt,
    gap: 2,
  },
  styleChipOn: { backgroundColor: instrument.accent, borderColor: instrument.accent },
  panelBanner: { marginTop: space[3] },
  panelBtn: { marginTop: space[3] },
  row: {
    marginTop: space[3],
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    backgroundColor: instrument.surface,
    overflow: 'hidden',
  },
  rowMain: { padding: space[3] },
  rowPressed: { backgroundColor: instrument.surfaceAlt },
  rowTop: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  rowName: { flexShrink: 1 },
  badge: {
    paddingHorizontal: space[2],
    paddingVertical: 1,
    borderRadius: radius.pill,
    backgroundColor: instrument.accent,
  },
  rowMeta: { marginTop: space[1] },
  rowWarn: { marginTop: space[1], lineHeight: 16 },
  rowNote: { marginTop: space[1], lineHeight: 16 },
  rowActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: space[1],
    paddingHorizontal: space[2],
    paddingBottom: space[2],
  },
  iconBtn: { padding: space[2], borderRadius: radius.md },
  iconBtnPressed: { backgroundColor: instrument.surfaceAlt },
  iconBtnOff: { opacity: 0.4 },
  confirmBar: {
    padding: space[3],
    borderTopWidth: 1,
    borderTopColor: instrument.border,
    backgroundColor: instrument.surfaceAlt,
  },
  confirmText: { lineHeight: 20 },
  confirmActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: space[2],
    marginTop: space[2],
  },
  footnote: { marginTop: space[5], lineHeight: 18 },
});
