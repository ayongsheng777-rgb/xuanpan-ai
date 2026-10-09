/**
 * 罗盘校准与还原 —— 参考图第 5 屏。
 *
 * 这一页解决的问题很具体：**照片里的实体罗盘，怎么在界面上"摆正"**。
 *
 * 识别层只给出鱼丝线的几何方向（`ScanResult`），它无法知道：
 *   - 照片是斜着拍的（透视变形会让测出的角度整体偏掉几度）
 *   - 盘体在画面里没居中、没占满（于是盘面与外圈无法直接比对）
 * 用户手里的实物罗盘能一眼看出"对没对上"，程序不能。所以这一页把
 * **照片打底 + 矢量盘叠加**，让用户用眼睛把两者对正，再把对正后的读数
 * 交给确认页。这就是"在界面还原导入的数据"。
 *
 * 三条边界（都在讲解里明写，不藏在注释里）：
 *   1. 校准参数（照片的旋转/缩放/平移）**只作用于本页视图**，不写入服务端。
 *      本版没有"保存校准"这张表 —— 与其假装存了，不如说清没存。
 *   2. 照片只是**对位参考**，不参与任何计算。读数始终来自矢量盘的几何。
 *   3. 读数不构成坐向结论 —— 坐向必须回到「确认坐向」页由用户确认（RULE-004）。
 *
 * ## 单屏做法（2026-10-09）
 *
 * 盘面是本页唯一的弹性区（`FitSlot weight={1}` + `onLayout` 实测尺寸）；
 * 读数压成一行常驻；照片对位的 6 组步进按用途拆进「对位 / 读数」两个分段标签
 * （同一时刻只显示一组），平移的横纵两轴合并成一行 —— 于是最长的标签也只有 4 行。
 * 两条边界说明收进标题栏的问号旁弹层。
 *
 * 浅金仪器风：本页属罗盘域（见《V2 评估与实施路线》冲突 2 裁决）。
 */

import { Ionicons } from '@expo/vector-icons';
import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';

import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, KeyValueRow } from '@/components/Card';
import { CompassDial, DIAL_LIGHT, type CompassPhoto } from '@/components/CompassDial';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { azimuthAtTop, initialRotationFor } from '@/lib/compassDial';
import { coerceDialStyle } from '@/lib/dialStyle';
import { degreeToIndex, nameOfIndex } from '@/lib/ring24';
import { instrument, radius, space } from '@/theme/tokens';

/** 照片对位的步长。粗档用来快速拉近，细档用来最后咬合。 */
const PHOTO_ROT_STEPS = [-5, -1, 1, 5] as const;
const PHOTO_SCALE_STEP = 0.05;
const PHOTO_SHIFT_STEP = 0.03;

/** 矢量盘透明度三档 —— 不给人连续滑块，因为这里只有三种意图 */
const VECTOR_OPACITIES = [
  { value: 0.2, label: '看照片' },
  { value: 0.55, label: '对照' },
  { value: 1, label: '看盘面' },
] as const;

const DEFAULT_PHOTO = { rotation: 0, scale: 1, x: 0, y: 0, opacity: 0.55 };

type AlignTab = 'align' | 'read';

export default function CalibrateScreen(): React.JSX.Element {
  const router = useRouter();
  const params = useLocalSearchParams<{
    session?: string;
    photo?: string;
    style?: string;
    degree?: string;
  }>();

  const sessionId = params.session ?? '';
  const photoUri = params.photo ?? '';
  const dialStyle = useMemo(() => coerceDialStyle(params.style), [params.style]);

  /**
   * 初始旋转：有 `degree` 就把它转到盘面正上方，否则从 0° 起步。
   *
   * 走 `initialRotationFor`（唯一实现）而不是自己写 `-d`：这个换算少一个
   * 负号时界面完全正常，只是把方位转反（见 `lib/compassDial.azimuthAtTop` 注释）。
   * 口径是**坐山角** —— `degree` 来自 scan 页的坐山候选（见该页的传参注释）。
   */
  const initialRotation = useMemo(() => {
    if (params.degree === undefined || params.degree === '') return 0;
    const d = Number(params.degree);
    return Number.isFinite(d) ? initialRotationFor({ degree: d }) : 0;
  }, [params.degree]);

  const [rotation, setRotation] = useState(initialRotation);
  const [photo, setPhoto] = useState(DEFAULT_PHOTO);
  const [vectorOpacity, setVectorOpacity] = useState<number>(1);
  const [tab, setTab] = useState<AlignTab>('align');
  const [notesOpen, setNotesOpen] = useState(false);
  /** 盘面实测边长（px）—— 由 onLayout 给出，未测到前不渲染盘面 */
  const [dialBox, setDialBox] = useState(0);

  /** 顶部读数 = 屏幕正上方那一格的盘面角（见 lib/compassDial.azimuthAtTop） */
  const azimuth = azimuthAtTop(rotation);
  const mountain = nameOfIndex(degreeToIndex(azimuth));

  const nudgePhoto = useCallback((patch: Partial<typeof DEFAULT_PHOTO>) => {
    setPhoto((p) => ({ ...p, ...patch }));
  }, []);

  const reset = useCallback(() => {
    setPhoto(DEFAULT_PHOTO);
    setRotation(initialRotation);
    setVectorOpacity(1);
  }, [initialRotation]);

  const onDialLayout = useCallback((e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setDialBox(Math.min(width, height));
  }, []);

  const composedPhoto: CompassPhoto | null = photoUri
    ? {
        uri: photoUri,
        rotation: photo.rotation,
        scale: photo.scale,
        offsetX: photo.x,
        offsetY: photo.y,
        opacity: photo.opacity,
      }
    : null;

  return (
    <Screen style={styles.root}>
      <PageHeader
        title="罗盘校准与还原"
        subtitle="把照片里的罗盘摆正，再取读数"
        back
        helpTopic="calibrate"
        action={
          <Pressable
            onPress={() => setNotesOpen(true)}
            accessibilityRole="button"
            accessibilityLabel="校准的边界说明"
            hitSlop={10}
            style={styles.headAction}
          >
            <Ionicons name="information-circle-outline" size={20} color={instrument.accent} />
          </Pressable>
        }
      />

      {/* ---------- 盘面：照片打底 + 矢量叠加（唯一弹性区） ---------- */}
      <FitSlot weight={1} center>
        <View style={styles.dialBox} onLayout={onDialLayout}>
          {dialBox > 0 ? (
            <CompassDial
              size={dialBox}
              palette={DIAL_LIGHT}
              style={dialStyle}
              rotation={rotation}
              interactive
              onRotate={setRotation}
              photo={composedPhoto}
              vectorOpacity={vectorOpacity}
            />
          ) : null}
        </View>
      </FitSlot>

      {photoUri ? null : (
        <Banner tone="warning" title="没有照片">
          本页没有拿到照片，只显示矢量盘 —— 详见右上角说明。
        </Banner>
      )}

      {/* ---------- 读数：一行常驻 ---------- */}
      <View style={styles.azimuthRow}>
        <AppText size="xxl" weight="bold" color={instrument.accent} style={styles.azimuth}>
          {azimuth.toFixed(2)}°
        </AppText>
        <AppText size="lg" weight="semibold" color={instrument.text}>
          {mountain}
        </AppText>
        <AppText size="xs" color={instrument.muted} style={styles.azimuthHint}>
          屏幕正上方那一格
        </AppText>
      </View>

      {/* ---------- 对位 / 读数：分段替代长页面 ---------- */}
      <SegmentedTabs
        items={[
          { key: 'align', label: '照片对位' },
          { key: 'read', label: '读数与浓淡' },
        ]}
        value={tab}
        onChange={(k) => setTab(k as AlignTab)}
      />

      {tab === 'align' ? (
        <View style={styles.card}>
          <StepRow
            label="照片旋转"
            value={`${photo.rotation}°`}
            steps={PHOTO_ROT_STEPS.map((d) => ({
              key: String(d),
              text: d > 0 ? `+${d}°` : `−${Math.abs(d)}°`,
              onPress: () => nudgePhoto({ rotation: photo.rotation + d }),
            }))}
          />

          <StepRow
            label="照片缩放"
            value={`${photo.scale.toFixed(2)}×`}
            steps={[
              { key: 'out', text: '−', onPress: () => nudgePhoto({ scale: photo.scale - PHOTO_SCALE_STEP }) },
              { key: 'in', text: '+', onPress: () => nudgePhoto({ scale: photo.scale + PHOTO_SCALE_STEP }) },
            ]}
          />

          {/* 横纵两轴合并成一行 —— 同一动作的两个方向，占一行的按钮位 */}
          <StepRow
            label="照片平移"
            value={`${photo.x.toFixed(2)} / ${photo.y.toFixed(2)}`}
            steps={[
              { key: 'l', text: '←', onPress: () => nudgePhoto({ x: photo.x - PHOTO_SHIFT_STEP }) },
              { key: 'r', text: '→', onPress: () => nudgePhoto({ x: photo.x + PHOTO_SHIFT_STEP }) },
              { key: 'u', text: '↑', onPress: () => nudgePhoto({ y: photo.y - PHOTO_SHIFT_STEP }) },
              { key: 'd', text: '↓', onPress: () => nudgePhoto({ y: photo.y + PHOTO_SHIFT_STEP }) },
            ]}
          />

          <StepRow
            label="照片浓淡"
            value={`${Math.round(photo.opacity * 100)}%`}
            steps={[
              { key: '-', text: '−', onPress: () => nudgePhoto({ opacity: Math.max(0.05, photo.opacity - 0.1) }) },
              { key: '+', text: '+', onPress: () => nudgePhoto({ opacity: Math.min(1, photo.opacity + 0.1) }) },
            ]}
          />
        </View>
      ) : (
        <View style={styles.card}>
          <StepRow
            label="盘面方位"
            value={`${azimuth.toFixed(2)}°`}
            steps={[
              { key: '-1', text: '−1°', onPress: () => setRotation((r) => r + 1) },
              { key: '-01', text: '−0.1°', onPress: () => setRotation((r) => r + 0.1) },
              { key: '+01', text: '+0.1°', onPress: () => setRotation((r) => r - 0.1) },
              { key: '+1', text: '+1°', onPress: () => setRotation((r) => r - 1) },
            ]}
          />

          <AppText size="xs" color={instrument.textSecondary} style={styles.pickLabel}>
            矢量盘浓淡
          </AppText>
          <View style={styles.chipRow}>
            {VECTOR_OPACITIES.map((o) => {
              const on = Math.abs(vectorOpacity - o.value) < 1e-6;
              return (
                <Pressable
                  key={o.label}
                  onPress={() => setVectorOpacity(o.value)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: on }}
                  style={[styles.chip, on && styles.chipOn]}
                >
                  <AppText
                    size="xs"
                    weight={on ? 'semibold' : 'regular'}
                    color={on ? instrument.bg : instrument.textSecondary}
                  >
                    {o.label}
                  </AppText>
                </Pressable>
              );
            })}
          </View>

          <KeyValueRow label="读法" value="屏幕正上方那一格（0° 为正北，顺时针）" />
          <KeyValueRow label="盘面旋转" value={`${rotation.toFixed(1)}°`} last />
        </View>
      )}

      {/* ---------- 重置对位 ---------- */}
      <Button label="重置对位" variant="ghost" onPress={reset} />

      {/* ---------- 交棒给确认页 ---------- */}
      {sessionId ? (
        <Button
          label="用这个读数去确认坐向"
          icon={<Ionicons name="arrow-forward" size={18} color={instrument.bg} />}
          onPress={() =>
            router.push({
              pathname: '/confirm/[sessionId]',
              params: { sessionId, degree: azimuth.toFixed(2) },
            })
          }
        />
      ) : (
        <Banner tone="warning" title="无法进入确认">
          本页没有关联的会话，不能把读数交给「确认坐向」—— 详见右上角说明。
        </Banner>
      )}

      <InfoPopup
        visible={notesOpen}
        onClose={() => setNotesOpen(false)}
        title="校准的边界"
        subtitle="这一页做什么、不做什么"
      >
        <AppText size="sm" color={instrument.text} style={styles.popupBody}>
          把照片里罗盘的外圈对到矢量盘的外缘、鱼丝线对到同一条直线上。照片只是参照，
          读数始终来自矢量盘。
        </AppText>
        <AppText size="sm" color={instrument.text} style={styles.popupBody}>
          校准参数（照片的旋转 / 缩放 / 平移）只作用于本页视图，不写入服务端 ——
          本版没有保存校准的记录表，与其假装存了，不如说清没存。
        </AppText>
        <AppText size="sm" color={instrument.textSecondary} style={styles.popupBody}>
          照片只是对位参照，不参与计算；读数由矢量盘几何给出，且不构成坐向结论 ——
          坐向必须回到「确认坐向」页由你确认（RULE-004）。
        </AppText>
        <AppText size="sm" color={instrument.textSecondary} style={styles.popupBody}>
          本页没有拿到照片时，只显示矢量盘。要对着实物罗盘校准，请从
          「测盘 → 拍摄真实罗盘 / 导入照片」进入，识别完成后点「校准与还原」。
        </AppText>
        <AppText size="sm" color={instrument.textSecondary} style={styles.popupBody}>
          没有关联会话时不能交棒给「确认坐向」。请从测盘流程进入，
          或在「分析 → 读盘报告」里打开一条已有记录。
        </AppText>
      </InfoPopup>
    </Screen>
  );
}

// ==========================================================================
// 步进行
// ==========================================================================

interface StepSpec {
  key: string;
  text: string;
  onPress: () => void;
}

function StepRow({
  label,
  value,
  steps,
}: {
  label: string;
  value: string;
  steps: readonly StepSpec[];
}): React.JSX.Element {
  return (
    <View style={styles.stepRow}>
      <View style={styles.stepHead}>
        <AppText size="sm" color={instrument.textSecondary}>
          {label}
        </AppText>
        <AppText size="sm" weight="semibold" color={instrument.text} style={styles.stepValue}>
          {value}
        </AppText>
      </View>
      <View style={styles.stepBtns}>
        {steps.map((s) => (
          <Pressable
            key={s.key}
            onPress={s.onPress}
            accessibilityRole="button"
            accessibilityLabel={`${label} ${s.text}`}
            style={({ pressed }) => [styles.stepBtn, pressed && styles.stepBtnPressed]}
          >
            <AppText size="sm" weight="semibold" color={instrument.text}>
              {s.text}
            </AppText>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  headAction: { padding: space[1] },
  dialBox: { flex: 1, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center' },
  azimuthRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: space[3],
  },
  azimuth: { fontVariant: ['tabular-nums'] },
  azimuthHint: { flexShrink: 1 },
  card: {
    backgroundColor: instrument.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    padding: space[3],
  },
  stepRow: { marginTop: space[2] },
  stepHead: { flexDirection: 'row', justifyContent: 'space-between' },
  stepValue: { fontVariant: ['tabular-nums'] },
  stepBtns: { flexDirection: 'row', gap: space[2], marginTop: space[1] },
  stepBtn: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[2],
    borderRadius: radius.md,
    backgroundColor: instrument.surfaceAlt,
    borderWidth: 1,
    borderColor: instrument.border,
  },
  stepBtnPressed: { borderColor: instrument.accent },
  pickLabel: { marginTop: space[3] },
  chipRow: { flexDirection: 'row', gap: space[2], marginTop: space[1] },
  chip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[2],
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: instrument.border,
    backgroundColor: instrument.surfaceAlt,
  },
  chipOn: { backgroundColor: instrument.accent, borderColor: instrument.accent },
  popupBody: { lineHeight: 22 },
});
