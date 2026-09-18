/**
 * 罗盘识向 —— 基线规范 §4。
 *
 * 双入口（拍摄识别 / 相册选择），汇入**同一条**识别管线。
 *
 * 三条硬性要求（规范原文）：
 *   1. 无论来自相机还是相册，都必须先过质量检测 —— 所以两个入口调**同一个** `api.scan()`
 *   2. 识别结果必须经用户确认方可进入计算（RULE-004）→ 本页只负责识别，确认在下一页
 *   3. 不得显示"AI 正在思考"，必须展示**测量过程**（见 `StepList`）
 *
 * 关于相机：定位是「专业测量仪器」，不是扫码框。因此取景是**沉浸式**的 ——
 * 全宽出血、参考圈 + 四角对位标记、控制条压在取景画面上，而不是把相机
 * 塞进一张卡片里（卡片自己的边框会与参考圈争夺"哪条线才是对齐基准"）。
 * 相册作为第二入口也放在控制条上，与快门共用同一条识别管线。
 */

import { Ionicons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useRef, useState } from 'react';
import { Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';

import { getApiClient, resolveBaseUrl } from '@/api/client';
import type { ScanResult } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card } from '@/components/Card';
import { Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { StepList, failureStepOf, stepsUpTo, type Step } from '@/components/StepList';
import { useSubmit } from '@/lib/useAsync';
import { alpha, brand, colors, layout, radius, space } from '@/theme/tokens';

type Entry = 'camera' | 'library';
export default function ScanScreen(): React.JSX.Element {
  const router = useRouter();
  const params = useLocalSearchParams<{ entry?: string }>();

  const [entry, setEntry] = useState<Entry>(params.entry === 'library' ? 'library' : 'camera');
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView | null>(null);

  const [steps, setSteps] = useState<Step[] | null>(null);
  const [result, setResult] = useState<ScanResult | null>(null);
  // ApiClient 的公开方法是箭头函数属性，天生绑定 this，可直接传引用
  const scan = useSubmit(getApiClient().scan);

  /** 识别完成后：能识别 → 直接进确认页；不能 → 展示卡在哪一步与原因 */
  const runScan = useCallback(
    async (uri: string, filename: string) => {
      setResult(null);
      // 进行中：全部标为 pending，第一格 active —— 不假装已经完成了哪一步
      setSteps(stepsUpTo(0));

      const res = await scan.run(uri, filename);
      if (!res) {
        setSteps(null);
        return;
      }
      setResult(res);

      if (res.compass_detected) {
        // 前 6 步（质检→判断坐向）已完成；分金与解读在确认后才发生
        setSteps(stepsUpTo(6));
      } else {
        const qualityPassed = res.quality?.passed ?? false;
        const reason = res.uncertain_regions[0] ?? '未能识别出罗盘';
        setSteps(stepsUpTo(0, failureStepOf(qualityPassed), reason));
      }
    },
    [scan],
  );

  const takePicture = useCallback(async () => {
    const cam = cameraRef.current;
    if (!cam) return;
    try {
      const shot = await cam.takePictureAsync({ quality: 0.9, skipProcessing: false });
      if (shot?.uri) await runScan(shot.uri, 'compass.jpg');
    } catch {
      // 拍照失败（权限/硬件）不做特殊处理，用户可直接改用相册
      setSteps(null);
    }
  }, [runScan]);

  const pickFromLibrary = useCallback(async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return;
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.9,
      allowsEditing: false,
    });
    if (picked.canceled || picked.assets.length === 0) return;
    const asset = picked.assets[0]!;
    await runScan(asset.uri, asset.fileName ?? 'compass.jpg');
  }, [runScan]);

  return (
    <Screen scroll bottomInsetExtra={space[8]}>
      <SegmentedTabs
        items={[
          { key: 'camera', label: '拍摄识别' },
          { key: 'library', label: '相册选择' },
        ]}
        value={entry}
        onChange={(k) => setEntry(k as Entry)}
      />
      <View style={styles.spacer} />

      {entry === 'camera' ? (
        <CameraEntry
          permissionGranted={permission?.granted ?? false}
          permissionCanAsk={permission?.canAskAgain ?? true}
          onRequest={() => void requestPermission()}
          cameraRef={cameraRef}
          onShoot={takePicture}
          onPick={pickFromLibrary}
          shooting={scan.loading}
        />
      ) : (
        <LibraryEntry onPick={pickFromLibrary} picking={scan.loading} />
      )}

      {scan.error ? (
        <Banner tone={scan.fixable ? 'warning' : 'error'} title={scan.fixable ? '照片需要更换' : '识别失败'}>
          {scan.error}
        </Banner>
      ) : null}

      {steps ? (
        <Card title="识别过程">
          <StepList steps={steps} />
        </Card>
      ) : null}

      {result ? (
        result.compass_detected ? (
          <DetectedCard result={result} onConfirm={() => router.push(`/confirm/${result.session_id}`)} />
        ) : (
          <NotDetectedCard
            result={result}
            onManual={() => router.push(`/confirm/${result.session_id}`)}
          />
        )
      ) : null}

      <Card title="拍摄要点">
        {[
          '让罗盘完整进入画面，尽量占满取景区',
          '正面俯拍，避免大角度斜拍（透视校正有上限）',
          '避开直射光与反光，盘面文字清晰可辨',
          '确保鱼丝线（贯通盘面的细线）可见',
        ].map((t) => (
          <AppText key={t} size="sm" style={styles.tip}>
            · {t}
          </AppText>
        ))}
      </Card>

      <AppText size="xs" color="muted" center style={styles.note}>
        照片会上传到 {resolveBaseUrl()} 完成识别；默认不保留原图。
        {'\n'}识别结果须经你确认后才进入计算。
      </AppText>
    </Screen>
  );
}

// ==========================================================================
// 相机入口
// ==========================================================================

function CameraEntry({
  permissionGranted,
  permissionCanAsk,
  onRequest,
  cameraRef,
  onShoot,
  onPick,
  shooting,
}: {
  permissionGranted: boolean;
  permissionCanAsk: boolean;
  onRequest: () => void;
  cameraRef: React.MutableRefObject<CameraView | null>;
  onShoot: () => void;
  onPick: () => void;
  shooting: boolean;
}): React.JSX.Element {
  const { height } = useWindowDimensions();

  /**
   * 取景高度：视口高约 62%，夹在 260~560 之间。
   *
   * 上限的理由：参考圈是**圆**的，取景区再高也不会更好对位，
   * 只会把控制条顶出屏幕。下限的理由：矮屏上取景区不能矮于参考圈本身，
   * 否则圈被裁掉一半 —— 而"让罗盘外圈与参考圈贴合"正是这一屏的全部意义。
   */
  const viewfinderH = Math.min(560, Math.max(260, Math.round(height * 0.62)));

  if (!permissionGranted) {
    return (
      <Card title="需要相机权限">
        <AppText size="sm" color="textSecondary">
          开启相机权限后即可拍摄罗盘。若已拒绝且不再询问，请到系统设置中手动开启。
        </AppText>
        {permissionCanAsk ? (
          <Button label="开启相机权限" onPress={onRequest} style={styles.permBtn} />
        ) : (
          <Banner tone="warning" style={styles.permBtn}>
            系统已不再询问相机权限，请到「设置 → 应用 → 玄盘 AI」中手动开启。
          </Banner>
        )}
      </Card>
    );
  }

  return (
    /* 沉浸式取景 —— 全宽出血、不套 Card 外壳。
       理由：取景框套在卡片里时，卡片自己的边框会与参考圈争夺"哪条线才是对齐基准"，
       而这个动作的全部意义就是对齐。 */
    <View style={[styles.viewfinder, { height: viewfinderH }]}>
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing="back" />

      {/* 参考圈 + 四角对位标记。相机在本产品里是「测量仪器」，不是扫码框。 */}
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.alignRing}>
          <View style={[styles.bracket, styles.bracketTL]} />
          <View style={[styles.bracket, styles.bracketTR]} />
          <View style={[styles.bracket, styles.bracketBL]} />
          <View style={[styles.bracket, styles.bracketBR]} />
        </View>
        <AppText size="sm" weight="medium" color={colors.onPrimary} center style={styles.vfHint}>
          请保持罗盘平稳，尽量正对拍摄
        </AppText>
      </View>

      {shooting ? (
        <View style={styles.statusChip} pointerEvents="none">
          <AppText size="xs" color={colors.onPrimary}>
            正在识别…
          </AppText>
        </View>
      ) : null}

      {/* 底部控制条。相册是**第二入口**，与拍照走同一条识别管线
          （基线规范裁定：双入口同管线，不复制业务逻辑）。 */}
      <View style={styles.controlBar}>
        <Pressable
          onPress={onPick}
          disabled={shooting}
          accessibilityRole="button"
          accessibilityLabel="从相册选择照片"
          style={({ pressed }) => [styles.sideBtn, pressed && styles.sideBtnPressed]}
        >
          <Ionicons name="images-outline" size={22} color={colors.onPrimary} />
          <AppText size="xs" color={colors.onPrimary} style={styles.sideLabel}>
            相册
          </AppText>
        </Pressable>

        <Pressable
          onPress={onShoot}
          disabled={shooting}
          accessibilityRole="button"
          accessibilityLabel="拍照"
          style={({ pressed }) => [styles.shutter, pressed && styles.shutterPressed]}
        >
          <View style={styles.shutterInner} />
        </Pressable>

        {/* 占位块：只为让快门保持在正中。
            不在这里补一个"点了没反应的按钮" —— 那比缺一个位置更糟。 */}
        <View style={styles.sideBtn} />
      </View>
    </View>
  );
}

// ==========================================================================
// 相册入口
// ==========================================================================

function LibraryEntry({ onPick, picking }: { onPick: () => void; picking: boolean }): React.JSX.Element {
  return (
    <Card title="相册选择">
      <AppText size="sm" color="textSecondary" style={styles.libHint}>
        选择一张已拍摄的罗盘照片。相册里的旧照片同样会先过质量检测 ——
        模糊或反光的照片会被拒绝并提示原因。
      </AppText>
      <Button label="从相册选择照片" onPress={onPick} loading={picking} />
    </Card>
  );
}

// ==========================================================================
// 结果卡片
// ==========================================================================

function DetectedCard({
  result,
  onConfirm,
}: {
  result: ScanResult;
  onConfirm: () => void;
}): React.JSX.Element {
  const names = result.mountain_candidates.map((c) => c.name);
  return (
    <Card highlight title="识别完成">
      <AppText size="sm" color="textSecondary">
        检测到 {names.length} 个对宫候选：{names.join(' / ') || '—'}
      </AppText>
      <AppText size="xs" color="muted" style={styles.detectedNote}>
        几何识别无法判断鱼丝线哪一端为坐山 —— 这是盘面本身的信息缺失，
        不是算法不足，所以必须由你确认。
      </AppText>
      <Button
        label="前往确认坐向"
        icon={<Ionicons name="arrow-forward" size={18} color={colors.onPrimary} />}
        onPress={onConfirm}
        style={styles.confirmBtn}
      />
    </Card>
  );
}

function NotDetectedCard({
  result,
  onManual,
}: {
  result: ScanResult;
  onManual: () => void;
}): React.JSX.Element {
  const reasons = result.uncertain_regions.filter(Boolean);
  return (
    <Card danger title="未能识别">
      {reasons.length > 0 ? (
        reasons.map((r, i) => (
          <AppText key={i} size="sm" color="danger" style={styles.reason}>
            {r}
          </AppText>
        ))
      ) : (
        <AppText size="sm" color="danger">
          未能识别出罗盘，请调整拍摄后重试。
        </AppText>
      )}

      {result.warnings.length > 0 ? (
        <View style={styles.warnBlock}>
          {result.warnings.map((w, i) => (
            <AppText key={i} size="xs" color="textSecondary" style={styles.warn}>
              {w}
            </AppText>
          ))}
        </View>
      ) : null}

      <AppText size="sm" color="textSecondary" style={styles.fallbackHint}>
        识别失败不影响使用：可以直接手动选择坐山 ——
        「确认坐向」页提供二十四山环形选择器，无需依赖照片。
      </AppText>
      <Button
        label="手动选择坐向"
        variant="secondary"
        style={styles.confirmBtn}
        onPress={onManual}
      />
    </Card>
  );
}

const styles = StyleSheet.create({
  spacer: { height: space[3] },
  /* 取景器：横向负 margin 抵消 Screen 的页面留白 —— 取景区必须贴到屏幕两侧，
     否则"沉浸"只是把卡片换成另一块矩形。 */
  viewfinder: {
    marginHorizontal: -layout.gutter,
    marginBottom: space[3],
    overflow: 'hidden',
    backgroundColor: '#000',
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
  },
  alignRing: {
    width: 230,
    height: 230,
    borderRadius: 115,
    borderWidth: 1,
    borderColor: 'rgba(218, 179, 125, 0.55)',
  },
  bracket: { position: 'absolute', width: 26, height: 26, borderColor: brand.gold },
  bracketTL: { top: -1, left: -1, borderTopWidth: 3, borderLeftWidth: 3 },
  bracketTR: { top: -1, right: -1, borderTopWidth: 3, borderRightWidth: 3 },
  bracketBL: { bottom: -1, left: -1, borderBottomWidth: 3, borderLeftWidth: 3 },
  bracketBR: { bottom: -1, right: -1, borderBottomWidth: 3, borderRightWidth: 3 },
  /* 提示落在控制条上方 —— 压在控制条上会被快门挡住 */
  vfHint: { position: 'absolute', bottom: 78 },
  statusChip: {
    position: 'absolute',
    top: space[3],
    alignSelf: 'center',
    paddingHorizontal: space[3],
    paddingVertical: space[1],
    borderRadius: radius.pill,
    backgroundColor: alpha.scrim,
  },
  controlBar: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    paddingVertical: space[3],
    paddingHorizontal: space[4],
    backgroundColor: alpha.scrim,
  },
  sideBtn: { width: 56, alignItems: 'center', gap: 2 },
  sideBtnPressed: { opacity: 0.6 },
  sideLabel: { marginTop: 2 },
  shutter: {
    width: 68,
    height: 68,
    borderRadius: 34,
    borderWidth: 3,
    borderColor: brand.gold,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.22)',
  },
  shutterPressed: { backgroundColor: alpha.goldSoft },
  shutterInner: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.surface,
  },
  libHint: { marginBottom: space[3], lineHeight: 20 },
  permBtn: { marginTop: space[3] },
  detectedNote: { marginTop: space[2], lineHeight: 18 },
  confirmBtn: { marginTop: space[3] },
  reason: { marginBottom: space[1] },
  warnBlock: { marginTop: space[2], gap: 2 },
  warn: { lineHeight: 18 },
  fallbackHint: { marginTop: space[3], lineHeight: 20 },
  tip: { lineHeight: 20 },
  note: { marginTop: space[4], lineHeight: 18 },
});
