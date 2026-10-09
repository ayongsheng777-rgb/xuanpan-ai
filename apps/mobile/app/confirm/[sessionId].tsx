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
 *
 * ## 2026-10-09 单屏化
 *
 * 本页内容最多（识别依据 + 盘面调节台 + 备注 + 确认结果），原先要滚好几屏。
 * 现在：盘面调节台作为**唯一弹性区**（`FitSlot`），其余全部收进浮层 ——
 * 识别依据（候选列表走 `FoldList`）、备注、确认结果各自一个 `InfoPopup`，
 * 入口固定在标题下方的状态行里。业务逻辑一字未动，只重排版面。
 */

import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, TextInput, useWindowDimensions, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { CompassConfirmRequest, LayerPreview, MountainCandidate } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, EmptyState } from '@/components/Card';
import { CompassAdjuster } from '@/components/CompassAdjuster';
import { FactList } from '@/components/FactList';
import { FoldList } from '@/components/FoldList';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { degreeToIndex, indexOfName, nameOfIndex, oppositeIndex } from '@/lib/ring24';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { colors, font, radius, space } from '@/theme/tokens';

export default function ConfirmOrientationScreen(): React.JSX.Element {
  const router = useRouter();
  const { sessionId, degree: degreeParam } = useLocalSearchParams<{
    sessionId?: string;
    /** 由「罗盘校准与还原」页带过来的读数 */
    degree?: string;
  }>();
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

  /** 三个浮层开关 —— 识别依据 / 备注 / 确认结果 */
  const [openRecog, setOpenRecog] = useState(false);
  const [openNote, setOpenNote] = useState(false);
  const [openResult, setOpenResult] = useState(false);

  /**
   * 盘面外径 —— 同时受**屏宽**与**可用高度**约束。
   *
   * 2026-10-09 单屏改造后补的高度约束：原先只按屏宽算（`width - 96`，封顶 260），
   * 在 390×844 上盘面 260px，而调节台剩下的按钮区（读数 + 4 排按钮 + 提示）
   * 实测约 393px —— 两者相加 716px，超过分区实得的 644px，**底部提示被裁掉 72px**
   * （`test_page_has_no_clipped_content` 抓到的就是这个）。
   *
   * 改法：量出分区实得高度 `slotH`，把非盘面部分（`ADJUSTER_CHROME_H`）扣掉，
   * 剩下的全部给盘面。这样屏幕矮时盘面自动变小、屏幕高时变大，都不溢出。
   * 那个常量是"读数 + 4 排按钮 + 提示"的实测高度，改调节台控件时需同步。
   */
  const { width } = useWindowDimensions();
  const [slotH, setSlotH] = useState(0);
  const dialSize =
    slotH > 0
      ? Math.max(140, Math.min(width - 96, slotH - ADJUSTER_CHROME_H - 24))
      : Math.min(260, Math.max(180, width - 96));

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

  /**
   * 从「校准与还原」页带来的读数 —— 只作为**初始值**灌进 degreeOverride。
   *
   * 为什么是灌进 override 而不是另立一个状态：override 的语义就是
   * "用户对实测角的手工修正"，而对齐照片后得到的读数正是这样一个修正值。
   * 另立状态会让"改选坐山要不要作废"这条规则出现两个版本。
   *
   * 只灌一次（`degreeSeeded`）：灌完就归 override 管，避免重新渲染把用户
   * 在本页的手工微调覆盖掉。
   */
  const degreeSeeded = React.useRef(false);
  /** 当前这个人工校准值是"从校准页带过来的"还是"在本页调出来的" —— 影响文案归属 */
  const [degreeFromCalibrate, setDegreeFromCalibrate] = useState(false);
  React.useEffect(() => {
    if (degreeSeeded.current) return;
    if (degreeParam === undefined || degreeParam === '') return;
    const d = Number(degreeParam);
    if (!Number.isFinite(d)) return;
    degreeSeeded.current = true;
    setDegreeOverride(d);
    setDegreeFromCalibrate(true);
  }, [degreeParam]);

  /** 本页手工调过之后，这个值就不再"来自校准页"了 */
  const onManualDegree = useCallback((d: number | null) => {
    setDegreeOverride(d);
    setDegreeFromCalibrate(false);
  }, []);

  const facing = sitting === null ? null : oppositeIndex(sitting);

  /**
   * 换坐山时，只有**换了一条鱼丝线**才作废实测角。
   *
   * 规则原文是"换坐山 = 换了一条鱼丝线 → 实测角作废"，但坐与向是**同一条线
   * 的两端**：把"坐午"改成"向午"仍然指着同一条线，实测方向同源，不该丢掉。
   *
   * 🔴 原实现对此不作区分，一律清空 —— 于是从「校准与还原」页带过来的读数
   *    会在用户点对宫那一格时被静默丢掉（那恰恰是 RULE-004 要求他做的那一步）。
   */
  const handleSelectSitting = useCallback((next: number | null) => {
    setSitting(next);
    setDegreeOverride((prev) => {
      if (prev === null) return null; // 本来就没有人工校准值
      if (next === null) return prev; // 取消选择：实测角还在，只是暂无坐山
      const measured = degreeToIndex(prev);
      return next === measured || next === oppositeIndex(measured) ? prev : null;
    });
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
    <Screen bottomInsetExtra={space[4]}>
      <PageHeader title="确认坐向" back helpTopic="confirm" tone="light" />

      {/* ---------- 状态行：一行说清来源，其余入口挂在这里 ---------- */}
      <View style={styles.statusRow}>
        <AppText size="xs" color="textSecondary" numberOfLines={1} style={styles.statusText}>
          {recognition
            ? `识别到 ${candidates.length} 处候选（互为对宫）`
            : '无识别结果，手动点环选择坐山'}
        </AppText>

        {recognition ? (
          <Pressable
            onPress={() => setOpenRecog(true)}
            accessibilityRole="button"
            accessibilityLabel="查看识别依据"
            style={styles.link}
          >
            <Ionicons name="information-circle-outline" size={14} color={colors.primary} />
            <AppText size="xs" color="primary" style={styles.linkText}>
              识别依据
            </AppText>
          </Pressable>
        ) : null}

        <Pressable
          onPress={() => setOpenNote(true)}
          accessibilityRole="button"
          accessibilityLabel="编辑备注"
          style={styles.link}
        >
          <Ionicons name="create-outline" size={14} color={colors.primary} />
          <AppText size="xs" color="primary" style={styles.linkText}>
            备注{note.trim() ? ' ·已填' : ''}
          </AppText>
        </Pressable>

        {shownPreview ? (
          <Pressable
            onPress={() => setOpenResult(true)}
            accessibilityRole="button"
            accessibilityLabel="查看确认结果"
            style={styles.link}
          >
            <Ionicons name="checkmark-circle-outline" size={14} color={colors.primary} />
            <AppText size="xs" color="primary" style={styles.linkText}>
              确认结果
            </AppText>
          </Pressable>
        ) : null}
      </View>

      {alreadyConfirmed && !preview ? (
        <AppText size="xs" color="success" numberOfLines={1} style={styles.confirmedLine}>
          已确认：坐 {confirmState?.sitting} ／ 向 {confirmState?.facing}
          {confirmState?.user_note ? `；备注：${confirmState.user_note}` : ''}
        </AppText>
      ) : null}

      {/* ---------- 唯一弹性区：盘面调节台 ---------- */}
      <FitSlot weight={1}>
        <View
          style={styles.fill}
          onLayout={(e) => setSlotH(e.nativeEvent.layout.height)}
        >
          <Card title="确认坐向 · 盘面可逐项微调">
            <CompassAdjuster
              sitting={sitting}
              rotation={rotation}
              measuredDegree={measuredDegree}
              onChangeSitting={handleSelectSitting}
              onChangeRotation={setRotation}
              onChangeMeasuredDegree={onManualDegree}
              size={dialSize}
            />
          </Card>
        </View>
      </FitSlot>

      {submit.error ? (
        <Banner
          tone={submit.fixable ? 'warning' : 'error'}
          title={submit.fixable ? '输入需要调整' : '确认失败'}
        >
          {submit.error}
        </Banner>
      ) : null}

      {shownPreview ? (
        <Button
          label="生成 AI 解读报告"
          size="lg"
          icon={<Ionicons name="arrow-forward" size={18} color={colors.onPrimary} />}
          onPress={() => router.push(`/report/${id}`)}
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

      {/* ---------- 浮层 1：识别依据（候选列表走 FoldList） ---------- */}
      {recognition ? (
        <InfoPopup
          visible={openRecog}
          onClose={() => setOpenRecog(false)}
          title="识别依据"
          subtitle={`识别通道：${recognition.provider}`}
        >
          <AppText size="sm" color={colors.text}>
            照片只能测出鱼丝线的位置，无法判断哪一端是坐山 —— 这是盘面本身缺少的信息，
            请核对下方的坐向，必要时直接点环修正。
          </AppText>

          <FoldList
            items={candidates}
            keyOf={(c) => c.name}
            moreTitle="全部候选"
            moreSubtitle={`共 ${candidates.length} 处`}
            tone="light"
            renderItem={(c) => (
              <View style={styles.candRow}>
                <AppText size="md" weight="semibold" color="primary">
                  {c.name}
                </AppText>
                <AppText size="xs" color="textSecondary">
                  {c.angle.toFixed(2)}° · 置信度 {(c.confidence * 100).toFixed(0)}%
                </AppText>
              </View>
            )}
            empty={
              <AppText size="sm" color="muted">
                本次没有可用的候选。
              </AppText>
            }
          />

          {selectedCandidate ? (
            <AppText size="xs" color="muted" style={styles.candMeta}>
              已选「{selectedCandidate.name}」由照片实测支持，置信度{' '}
              {(selectedCandidate.confidence * 100).toFixed(0)}%；
              {degreeOverride === null
                ? `实测角 ${selectedCandidate.angle.toFixed(2)}° 将用于分金精算`
                : `${
                    degreeFromCalibrate ? '由「校准与还原」对齐照片后带入' : '已手工校准为'
                  } ${degreeOverride.toFixed(2)}°（识别原值 ${selectedCandidate.angle.toFixed(2)}° 仍留存）`}
            </AppText>
          ) : sitting !== null ? (
            <AppText size="xs" color="muted" style={styles.candMeta}>
              已选「{nameOfIndex(sitting)}」没有照片实测支持，将以山心角计算 ——
              分金只能落到正中格
            </AppText>
          ) : null}

          {recognition.uncertain_regions.length > 0 ? (
            <View style={styles.popupBlock}>
              {recognition.uncertain_regions.map((r, i) => (
                <AppText key={i} size="xs" color="warning" style={styles.regionLine}>
                  · {r}
                </AppText>
              ))}
            </View>
          ) : null}

          {recognition.warnings.length > 0 ? (
            <View style={styles.popupBlock}>
              {recognition.warnings.map((w, i) => (
                <AppText key={i} size="xs" color="muted" style={styles.regionLine}>
                  {w}
                </AppText>
              ))}
            </View>
          ) : null}
        </InfoPopup>
      ) : null}

      {/* ---------- 浮层 2：备注 ---------- */}
      <InfoPopup
        visible={openNote}
        onClose={() => setOpenNote(false)}
        title="备注（可选）"
        subtitle="会与确认结果一起留存"
      >
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
      </InfoPopup>

      {/* ---------- 浮层 3：确认结果 ---------- */}
      {shownPreview ? (
        <InfoPopup
          visible={openResult}
          onClose={() => setOpenResult(false)}
          title="确认结果"
          subtitle="盘面事实 / 传统分析 / 不确定性"
        >
          <ConfirmedResult preview={shownPreview} onNext={() => router.push(`/report/${id}`)} />
        </InfoPopup>
      ) : null}
    </Screen>
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

/**
 * `CompassAdjuster` 里**除盘面之外**的部分占用的高度（px）：
 * 坐山/向山读数 + 盘体旋转 2 排按钮 + 坐山逐格微调 1 排 + 对齐/归零 1 排 + 底部提示。
 *
 * 2026-10-09 在 390×844 实测：盘面 260 时整卡 716px，故非盘面部分 ≈ 456。
 * ⚠️ 改 `CompassAdjuster` 的控件行数或按钮尺寸时必须同步这个数，
 *    否则盘面尺寸会算错（大了就裁、小了就浪费）——
 *    `test_page_has_no_clipped_content` 会兜住"裁"的那一半。
 */
const ADJUSTER_CHROME_H = 456;

const styles = StyleSheet.create({
  loadingText: { marginTop: space[10] },
  /** 让 Card 在弹性分区里拿到实测高度（`onLayout` 要用它算盘面尺寸） */
  fill: { flex: 1 },

  statusRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: space[3] },
  statusText: { flexShrink: 1 },
  link: { flexDirection: 'row', alignItems: 'center' },
  linkText: { marginLeft: 2 },
  confirmedLine: { lineHeight: 16 },

  candRow: { paddingVertical: space[1] },
  candMeta: { lineHeight: 16 },
  popupBlock: { gap: 2 },
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
  noteHint: { lineHeight: 16 },
  layerNote: { marginTop: space[2], lineHeight: 16 },
});
