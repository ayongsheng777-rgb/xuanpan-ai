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
 * 三条边界（都在界面上明写，不藏在注释里）：
 *   1. 校准参数（照片的旋转/缩放/平移）**只作用于本页视图**，不写入服务端。
 *      本版没有"保存校准"这张表 —— 与其假装存了，不如说清没存。
 *   2. 照片只是**对位参考**，不参与任何计算。读数始终来自矢量盘的几何。
 *   3. 读数不构成坐向结论 —— 坐向必须回到「确认坐向」页由用户确认（RULE-004）。
 *
 * 深色仪器风：本页属罗盘域（见《V2 评估与实施路线》冲突 2 裁决）。
 */

import { Ionicons } from '@expo/vector-icons';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { Button, Card, KeyValueRow } from '@/components/Card';
import { CompassDial, DIAL_DARK, type CompassPhoto } from '@/components/CompassDial';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { azimuthAtTop } from '@/lib/compassDial';
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

  /** 初始方位：有 degree 就按它把盘转到该读数朝上，否则从 0 开始 */
  const initialRotation = useMemo(() => {
    if (params.degree === undefined || params.degree === '') return 0;
    const d = Number(params.degree);
    return Number.isFinite(d) ? -d : 0;
  }, [params.degree]);

  const [rotation, setRotation] = useState(initialRotation);
  const [photo, setPhoto] = useState(DEFAULT_PHOTO);
  const [vectorOpacity, setVectorOpacity] = useState<number>(1);

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
    <>
      <Stack.Screen
        options={{
          title: '罗盘校准与还原',
          headerStyle: { backgroundColor: instrument.bg },
          headerTintColor: instrument.text,
          headerShadowVisible: false,
          headerRight: () => (
            <HelpButton topic="calibrate" color={instrument.textSecondary} />
          ),
        }}
      />
      <Screen scroll style={styles.root}>
        {/* ---------- 盘面：照片打底 + 矢量叠加 ---------- */}
        <View style={styles.dialWrap}>
          <CompassDial
            size={320}
            palette={DIAL_DARK}
            style={dialStyle}
            rotation={rotation}
            interactive
            onRotate={setRotation}
            photo={composedPhoto}
            vectorOpacity={vectorOpacity}
          />
        </View>

        {photoUri ? null : (
          <Card title="没有照片">
            <AppText size="sm" color={instrument.textSecondary} style={styles.hintLine}>
              本页没有拿到照片，只显示矢量盘。要对着实物罗盘校准，请从
              「测盘 → 拍摄真实罗盘 / 导入照片」进入，识别完成后点「校准与还原」。
            </AppText>
          </Card>
        )}

        {/* ---------- 读数 ---------- */}
        <Card title="还原出的读数" highlight>
          <View style={styles.azimuthRow}>
            <AppText size="display" weight="bold" color={instrument.accent} style={styles.azimuth}>
              {azimuth.toFixed(2)}°
            </AppText>
            <AppText size="lg" weight="semibold" color={instrument.text}>
              {mountain}
            </AppText>
          </View>
          <KeyValueRow label="读法" value="屏幕正上方那一格（0° 为正北，顺时针）" />
          <KeyValueRow
            label="盘面旋转"
            value={`${rotation.toFixed(1)}°`}
            last
          />
        </Card>

        {/* ---------- 照片对位 ---------- */}
        <Card title="照片对位">
          <AppText size="xs" color={instrument.textSecondary} style={styles.hintLine}>
            把照片里罗盘的**外圈**对到矢量盘的外缘、**鱼丝线**对到同一条直线上。
            照片只是参照，读数始终来自矢量盘。
          </AppText>

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

          <StepRow
            label="水平平移"
            value={photo.x.toFixed(2)}
            steps={[
              { key: 'l', text: '←', onPress: () => nudgePhoto({ x: photo.x - PHOTO_SHIFT_STEP }) },
              { key: 'r', text: '→', onPress: () => nudgePhoto({ x: photo.x + PHOTO_SHIFT_STEP }) },
            ]}
          />

          <StepRow
            label="垂直平移"
            value={photo.y.toFixed(2)}
            steps={[
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

          <Button label="重置对位" variant="ghost" style={styles.resetBtn} onPress={reset} />
        </Card>

        {/* ---------- 盘面读数调节（与 /adjust 同一口径） ---------- */}
        <Card title="盘面读数">
          <AppText size="xs" color={instrument.textSecondary} style={styles.hintLine}>
            直接拖动盘面即可改变读数；也可用下面的步进。它等价于「手动调节」页。
          </AppText>
          <StepRow
            label="方位"
            value={`${azimuth.toFixed(2)}°`}
            steps={[
              { key: '-1', text: '−1°', onPress: () => setRotation((r) => r + 1) },
              { key: '-01', text: '−0.1°', onPress: () => setRotation((r) => r + 0.1) },
              { key: '+01', text: '+0.1°', onPress: () => setRotation((r) => r - 0.1) },
              { key: '+1', text: '+1°', onPress: () => setRotation((r) => r - 1) },
            ]}
          />
        </Card>

        {/* ---------- 交棒给确认页 ---------- */}
        {sessionId ? (
          <Button
            label="用这个读数去确认坐向"
            icon={<Ionicons name="arrow-forward" size={18} color={instrument.bg} />}
            style={styles.confirmBtn}
            onPress={() =>
              router.push({
                pathname: '/confirm/[sessionId]',
                params: { sessionId, degree: azimuth.toFixed(2) },
              })
            }
          />
        ) : (
          <Card title="无法进入确认">
            <AppText size="sm" color={instrument.textSecondary} style={styles.hintLine}>
              本页没有关联的会话，所以不能把读数交给「确认坐向」。请从测盘流程
              进入，或在「分析 → 读盘报告」里打开一条已有记录。
            </AppText>
          </Card>
        )}

        <View style={styles.foot}>
          <AppText size="xs" color={instrument.muted} style={styles.footLine}>
            校准参数（照片的旋转 / 缩放 / 平移）只作用于本页视图，**不写入服务端** ——
            本版没有保存校准的记录表，与其假装存了，不如说清没存。
          </AppText>
          <AppText size="xs" color={instrument.muted} style={styles.footLine}>
            照片只是对位参照，不参与计算；读数由矢量盘几何给出，且不构成坐向结论 ——
            坐向必须回到「确认坐向」页由你确认（RULE-004）。
          </AppText>
        </View>
      </Screen>
    </>
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
  dialWrap: { alignItems: 'center', marginBottom: space[3] },
  hintLine: { lineHeight: 19 },
  azimuthRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: space[3],
    marginBottom: space[2],
  },
  azimuth: { fontVariant: ['tabular-nums'] },
  stepRow: { marginTop: space[3] },
  stepHead: { flexDirection: 'row', justifyContent: 'space-between' },
  stepValue: { fontVariant: ['tabular-nums'] },
  stepBtns: { flexDirection: 'row', gap: space[2], marginTop: space[2] },
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
  pickLabel: { marginTop: space[4] },
  chipRow: { flexDirection: 'row', gap: space[2], marginTop: space[2] },
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
  resetBtn: { marginTop: space[3] },
  confirmBtn: { marginTop: space[5] },
  foot: { marginTop: space[5], gap: space[2] },
  footLine: { lineHeight: 18 },
});
