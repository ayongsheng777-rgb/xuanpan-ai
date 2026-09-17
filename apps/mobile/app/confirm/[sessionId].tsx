/**
 * 确认坐向 —— RULE-004 的**唯一**放行点。
 *
 * 为什么识别完了还要用户点一下，而不是"识别置信度够高就自动采用"：
 * 几何识别能测出鱼丝线在哪，但**测不出哪一端是坐山** —— 鱼丝线是一条直线，
 * 两端在几何上完全对称，"坐"与"向"的区别是建筑朝向的语义，不在图像里。
 * 这是盘面本身的信息缺失，不是算法不够好。所以让模型猜 = 50% 概率把坐向搞反，
 * 而整份报告都建立在这个前提上。
 *
 * 四条设计约束：
 *   1. 手动修正的入口是**盘面本身**（拖动旋转 + 点按选山 + 逐项微调按钮），
 *      不给角度输入框（基线规范 §4.1）—— 用户不知道 177.03° 是什么，
 *      但知道罗盘上"午"在哪；而输入框会让人把 17.7 与 177 写混。
 *   2. 向山**永远由坐山推导**（±180°），不提供独立选择：坐向是一条直线，
 *      独立选会造出"坐午向巳"这种几何上不成立的状态
 *   3. 实测角度只在选中同一座山时回传。用户改选了别的山，原实测角就失效了 ——
 *      此时若仍回传旧角度，计算层会因"角度与坐山不符"抛错（RULE-008 不静默纠正）
 *   4. **盘体旋转是视角、不是数据**。用户旋转盘面是为了让画面与手里罗盘对齐，
 *      它不进 `CompassConfirmRequest`，也绝不影响坐山与实测角 ——
 *      把"看起来对齐了"当成"数据变了"是这一层最容易犯的错。
 */

import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { CompassConfirmRequest, LayerPreview, MountainCandidate } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, EmptyState } from '@/components/Card';
import { CompassAdjuster } from '@/components/CompassAdjuster';
import { FactList } from '@/components/FactList';
import { Screen } from '@/components/Screen';
import { indexOfName, nameOfIndex, oppositeIndex } from '@/lib/ring24';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { colors, font, radius, space } from '@/theme/tokens';

export default function ConfirmOrientationScreen(): React.JSX.Element {
  const router = useRouter();
  const { sessionId } = useLocalSearchParams<{ sessionId?: string }>();
  const id = sessionId ?? '';

  const api = useMemo(() => getApiClient(), []);
  const session = useAsync(
    useCallback(() => api.getSession(id), [api, id]),
    [id],
  );

  const [sitting, setSitting] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [preview, setPreview] = useState<LayerPreview | null>(null);
  const [seeded, setSeeded] = useState(false);
  /** 盘体旋转量 —— 纯**视角**，只影响盘面怎么画，不进计算、不上传 */
  const [rotation, setRotation] = useState(0);
  /**
   * 用户对实测角的手工校准（RULE-004：识别结果必须允许用户修正）。
   *
   * 为什么单独存一个覆盖值而不去改候选：候选是**识别层的原始输出**，
   * 必须原样留痕以备追溯（RULE-008 不得改写用户/识别数据）。
   * 用户的修正另立一处，提交时才由它顶替 —— 原始识别值与人工修正值互不污染。
   */
  const [degreeOverride, setDegreeOverride] = useState<number | null>(null);

  const detail = session.data;
  const recognition = detail?.recognition ?? null;
  const confirmState = detail?.confirm_state ?? null;

  /**
   * 候选列表只取坐山端。
   *
   * 后端返回的 `mountain_candidates` 与 `direction_candidates` 是**同一组**
   * 鱼丝线两端（角度完全相同），只是 `end` 标注不同。取其一即可，
   * 两处都取会在 `find` 时拿到两个同名项，反而要额外判重。
   */
  const candidates: readonly MountainCandidate[] = recognition?.mountain_candidates ?? [];

  // 初始选择：已确认过 → 沿用用户上次的选择；否则 → 识别首选候选。
  // 只在数据首次到达时执行一次，避免用户改选后被刷新覆盖。
  useEffect(() => {
    if (seeded || !detail) return;
    const name = confirmState?.sitting ?? candidates[0]?.name ?? null;
    if (name) {
      const idx = indexOfName(name);
      if (idx >= 0) setSitting(idx);
    }
    setSeeded(true);
  }, [seeded, detail, confirmState, candidates]);

  /**
   * 选中山的实测角。
   *
   * 用**山名**匹配而不是用索引匹配：候选来自识别层，其顺序与环形选择器的
   * 固定盘式顺序无关（前者按置信度排，后者是罗盘固定布局）。
   * 用索引比会出现"选了午却套上未的角度"这种静默错位。
   */
  const selectedCandidate = useMemo(() => {
    if (sitting === null) return null;
    const name = nameOfIndex(sitting);
    return candidates.find((c) => c.name === name) ?? null;
  }, [sitting, candidates]);

  /** 最终采用的实测角：用户手工校准优先于识别值 */
  const measuredDegree = degreeOverride ?? selectedCandidate?.angle ?? null;

  const facing = sitting === null ? null : oppositeIndex(sitting);

  /** 换坐山 = 换了一条鱼丝线，原有的实测角与新坐山不再同源，必须作废 */
  const handleSelectSitting = useCallback((next: number | null) => {
    setSitting(next);
    setDegreeOverride(null);
  }, []);

  const submit = useSubmit(
    useCallback(
      (payload: CompassConfirmRequest) => api.confirmCompass(id, payload),
      [api, id],
    ),
  );

  const onConfirm = useCallback(async () => {
    if (sitting === null) return;
    const body: CompassConfirmRequest = {
      sitting: nameOfIndex(sitting),
      facing: facing === null ? null : nameOfIndex(facing),
      // 有实测角就带上：分金是 3° 级精度，用山心角会让分金永远落在正中格
      degree: measuredDegree,
      note: note.trim() || null,
    };
    const res = await submit.run(body);
    if (res) setPreview(res);
  }, [facing, measuredDegree, note, sitting, submit]);

  // 已确认但本次未重新提交 → 用会话里已存的两层结果做预览，避免看起来"没确认过"
  const shownPreview: LayerPreview | null =
    preview ??
    (confirmState?.confirmed && detail
      ? {
          facts: { compass: detail.facts['compass'] ?? {} },
          tradition: { compass: detail.tradition['compass'] ?? {} },
          uncertainties: detail.uncertainties,
        }
      : null);

  if (!id) {
    return (
      <Screen>
        <EmptyState title="缺少会话标识" hint="请从「罗盘识向」页重新发起识别。" />
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

  const alreadyConfirmed = confirmState?.confirmed === true;

  return (
    <Screen scroll bottomInsetExtra={space[10]}>
      {recognition ? (
        <Banner tone="warning" title="识别结果需要你确认">
          照片只能测出鱼丝线的位置，无法判断哪一端是坐山 —— 这是盘面本身缺少的信息。
          请核对下方的坐向，必要时直接点环修正。
        </Banner>
      ) : (
        <Banner tone="info" title="手动录入坐向">
          该会话没有可用的识别结果，你可以直接点环选择坐山 —— 手动录入与照片识别
          在计算层走的是同一条链路，结论精度完全一致。
        </Banner>
      )}

      {alreadyConfirmed && !preview ? (
        <Banner tone="success" title="已确认">
          坐 {confirmState?.sitting} ／ 向 {confirmState?.facing}
          {confirmState?.user_note ? `；备注：${confirmState.user_note}` : ''}
          。重新提交会覆盖上一次的确认结果，识别原件仍会保留以备追溯。
        </Banner>
      ) : null}

      {recognition ? <RecognitionCard candidates={candidates} recognition={recognition} /> : null}

      <Card title="确认坐向 · 盘面可逐项微调">
        <CompassAdjuster
          sitting={sitting}
          rotation={rotation}
          measuredDegree={measuredDegree}
          onChangeSitting={handleSelectSitting}
          onChangeRotation={setRotation}
          onChangeMeasuredDegree={setDegreeOverride}
          size={300}
        />

        {selectedCandidate ? (
          <AppText size="xs" color="muted" center style={styles.candMeta}>
            该山由照片实测支持，置信度 {(selectedCandidate.confidence * 100).toFixed(0)}%；
            {degreeOverride === null
              ? `实测角 ${selectedCandidate.angle.toFixed(2)}° 将用于分金精算`
              : `已手工校准为 ${degreeOverride.toFixed(2)}°（识别原值 ${selectedCandidate.angle.toFixed(2)}° 仍留存）`}
          </AppText>
        ) : sitting !== null ? (
          <AppText size="xs" color="muted" center style={styles.candMeta}>
            该山没有照片实测支持，将以山心角计算 —— 分金只能落到正中格
          </AppText>
        ) : null}
      </Card>

      <Card title="备注（可选）">
        <TextInput
          value={note}
          onChangeText={setNote}
          placeholder="例如：现场实测罗盘读数、与照片的差异"
          placeholderTextColor={colors.muted}
          style={styles.input}
          multiline
          maxLength={200}
          accessibilityLabel="确认备注"
        />
        <AppText size="xs" color="muted" style={styles.noteHint}>
          备注会与确认结果一起留存，便于日后核对当时依据。
        </AppText>
      </Card>

      {submit.error ? (
        <Banner tone={submit.fixable ? 'warning' : 'error'} title={submit.fixable ? '输入需要调整' : '确认失败'}>
          {submit.error}
        </Banner>
      ) : null}

      {shownPreview ? (
        <ConfirmedResult
          preview={shownPreview}
          onNext={() => router.push(`/report/${id}`)}
        />
      ) : (
        <Button
          label={sitting === null ? '请先选择坐山' : '确认坐向'}
          size="lg"
          loading={submit.loading}
          disabled={sitting === null}
          icon={<Ionicons name="checkmark" size={18} color={colors.onPrimary} />}
          onPress={() => void onConfirm()}
        />
      )}
    </Screen>
  );
}

// ==========================================================================
// 识别结果概要
// ==========================================================================

function RecognitionCard({
  candidates,
  recognition,
}: {
  candidates: readonly MountainCandidate[];
  recognition: { provider: string; uncertain_regions: string[]; warnings: string[] };
}): React.JSX.Element {
  const names = candidates.map((c) => c.name);
  return (
    <Card title="识别到了什么">
      <AppText size="sm" color="textSecondary">
        检测到 {names.length} 处候选（互为对宫）：{names.join(' ／ ') || '—'}
      </AppText>
      <AppText size="xs" color="muted" style={styles.provider}>
        识别通道：{recognition.provider}
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

      {recognition.warnings.length > 0 ? (
        <View style={styles.regionBlock}>
          {recognition.warnings.map((w, i) => (
            <AppText key={i} size="xs" color="muted" style={styles.regionLine}>
              {w}
            </AppText>
          ))}
        </View>
      ) : null}
    </Card>
  );
}

// ==========================================================================
// 确认后的两层结果
// ==========================================================================

function ConfirmedResult({
  preview,
  onNext,
}: {
  preview: LayerPreview;
  onNext: () => void;
}): React.JSX.Element {
  const facts = (preview.facts['compass'] ?? {}) as Record<string, unknown>;
  const tradition = (preview.tradition['compass'] ?? {}) as Record<string, unknown>;

  return (
    <>
      <Card highlight title="盘面事实（只读）">
        <FactList data={facts} />
        <AppText size="xs" color="muted" style={styles.layerNote}>
          本区块由确定性计算产出，AI 无法改写 —— 这是防幻觉污染盘面的机制。
        </AppText>
      </Card>

      <Card title="传统分析（只读）">
        <FactList data={tradition} />
      </Card>

      <UncertaintyList items={preview.uncertainties} />

      <Button
        label="生成 AI 解读报告"
        size="lg"
        icon={<Ionicons name="arrow-forward" size={18} color={colors.onPrimary} />}
        onPress={onNext}
      />
    </>
  );
}

const styles = StyleSheet.create({
  loadingText: { marginTop: space[10] },
  candMeta: { marginTop: space[2], lineHeight: 16 },
  provider: { marginTop: space[1] },
  regionBlock: { marginTop: space[2], gap: 2 },
  regionLine: { lineHeight: 17 },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    minHeight: 64,
    color: colors.text,
    fontSize: font.size.md,
    lineHeight: font.lineHeight.md,
    textAlignVertical: 'top',
    backgroundColor: colors.surfaceAlt,
  },
  noteHint: { marginTop: space[2], lineHeight: 16 },
  layerNote: { marginTop: space[2], lineHeight: 16 },
});
