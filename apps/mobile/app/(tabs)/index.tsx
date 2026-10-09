/**
 * 罗盘（首页）—— 单屏主控台（2026-10-09 重设计）。
 *
 * ## 布局：一屏三段，罗盘是唯一可伸缩的那一段
 *
 *   标题栏（含设置入口）        —— 内容自适应
 *   核心：天池罗盘 + HUD 刻度环  —— **flex 1**（唯一弹性区，按剩余高度自适应）
 *   读数：当前方位 + 磁场强度    —— 内容自适应
 *   快捷：去测盘 / 每日早报 / 灵签机 —— 内容自适应
 *   脚注：已存盘面 + 免责一行    —— 内容自适应
 *
 * 为什么只让罗盘伸缩：其余各段都是"文字高度固定"的内容，
 * 一旦也参与伸缩就会在窄屏被压扁到不可读。罗盘是唯一"大一点小一点都成立"的元素 ——
 * 所以把全部弹性预算给它，其余按内容排。这样从 640 到 940 的屏高都不用滚动，
 * 也不需要写死任何像素。
 *
 * 盘面尺寸用 `onLayout` 实测容器，而不是 `useWindowDimensions` 算：
 * 容器高度已经扣掉了安全区、标题栏、读数区，比屏幕高度更接近真实可用空间。
 *
 * ## 语义约定（与改造前一致，未动）
 *
 *   - 本页罗盘是**实时磁针**：有磁力计数据时盘面跟着手机转（rotation = −方位角）；
 *     无数据时回退手拖并明示，不编造方位。
 *   - 磁场卡的数据来自传感器；无数据时显示「—」占位，**不编造数值**。
 *   - 本页不放「扫描/传感器/手动」三个入口，只留一个「去测盘」（入口只留一处）。
 *
 * ## 玄机科技风（2026-10-09 用户裁定「浅金科技」）
 *
 * 罗盘外圈加一圈 HUD 激光刻度环（`HudTickRing`），盘面尺寸随之让出 24px 环带。
 * 刻度是**纯装饰**：不参与读数、不接收触摸，去掉它界面照样能用。
 * 配色仍是浅金域（`instrument`），不引入深色玄学底 —— 见 tokens 的 `hud` 注释。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';

import { getApiClient } from '@/api/client';
import { AppText, Label, Metric } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Panel } from '@/components/Card';
import { CompassDial, DIAL_LIGHT } from '@/components/CompassDial';
import { HudTickRing } from '@/components/Hud';
import { InstrumentBlock } from '@/components/InstrumentBlock';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { azimuthAtTop } from '@/lib/compassDial';
import { useAsync } from '@/lib/useAsync';
import { useSensorSnapshot } from '@/services/useSensors';
import { hud, instrument, radius, space } from '@/theme/tokens';

interface HomeStats {
  total: number;
  latestTitle: string | null;
}

/** HUD 刻度环占用的环带宽度 —— 盘面尺寸从可用空间里让出这么多 */
const RING_BAND = 24;

export default function CompassHomeScreen(): React.JSX.Element {
  const router = useRouter();
  /** 无传感器时的手动盘面旋转量（度）—— 仅回退用，有磁针数据时不生效 */
  const [manualRotation, setManualRotation] = useState(0);
  /** 首页订阅传感器：磁场卡与实时磁针都要它（进入即开始，离开即停止） */
  const sensor = useSensorSnapshot(true);
  /** 核心区实测可用边长（px）—— 由 onLayout 给出，未测到前不渲染盘面 */
  const [coreBox, setCoreBox] = useState(0);

  /**
   * 实时磁针：有方位角数据 → 盘面由磁针驱动（rotation = −azimuth，
   * 顶部读数 = azimuthAtTop(rotation) = azimuth）；
   * 无数据 → 回退手拖，并如实标注，不编造一个"看起来在转"的方位。
   */
  const sensorDriven = sensor.azimuth !== null;
  const rotation = sensorDriven ? -sensor.azimuth! : manualRotation;

  const load = useCallback(async (): Promise<HomeStats> => {
    const page = await getApiClient().listSessions(1, 0);
    return { total: page.total, latestTitle: page.items[0]?.title ?? null };
  }, []);
  const { data, error, reload } = useAsync(load, []);

  // 方位按 0..360 显示（负角如 -12.72° 显示为 347.28°，与实物罗盘读法一致）。
  // 🔴 必须走 `azimuthAtTop`：顶部读数 = **−rotation**。
  const azimuth = azimuthAtTop(rotation);

  const onCoreLayout = useCallback((e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setCoreBox(Math.min(width, height));
  }, []);

  const ringSize = coreBox;
  const dialSize = Math.max(0, ringSize - RING_BAND);

  return (
    <Screen style={styles.root}>
      <PageHeader
        title="玄盘 AI"
        subtitle={sensorDriven ? '真北 0° · 实时磁针' : '真北 0° · 无传感器，可拖动盘面'}
        helpTopic="compass-home"
        action={
          <Pressable
            onPress={() => router.push('/mine')}
            accessibilityLabel="设置"
            hitSlop={10}
            style={styles.gear}
          >
            <Ionicons name="settings-outline" size={18} color={instrument.accent} />
          </Pressable>
        }
      />

      {error ? (
        <Banner tone="error" title="无法连接后端服务">
          <AppText size="sm">{error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={reload} />
        </Banner>
      ) : null}

      {/* ---------- 核心：天池罗盘（唯一弹性区） ---------- */}
      <FitSlot weight={1} center style={styles.coreSlot}>
        <View style={styles.core} onLayout={onCoreLayout}>
          {ringSize > 0 ? (
            <>
              {/* HUD 激光刻度环 —— 纯装饰 */}
              <HudTickRing size={ringSize} count={48} majorEvery={8} inset={1} />
              {/* 真北标记：固定指屏幕上方（磁针恒指北，转的是盘体） */}
              <View style={styles.northMark} pointerEvents="none">
                <View style={styles.northArrow} />
              </View>
              <View style={[styles.dialInner, { width: dialSize, height: dialSize }]}>
                <CompassDial
                  size={dialSize}
                  palette={DIAL_LIGHT}
                  style="zonghe"
                  rotation={rotation}
                  interactive={!sensorDriven}
                  onRotate={setManualRotation}
                />
              </View>
            </>
          ) : null}
        </View>
      </FitSlot>

      {/* ---------- 读数：一屏一个主角 ----------
          「一屏一个主角」：整个首页只有方位角用 `Metric`（40px/特粗/等宽数字），
          磁场强度降一档 —— 两块读数原本同为大字，用户看不出该先看哪个。
          ⚠️ 这里必须是**普通 View**而不是 `FitSlots`：`FitSlots` 带 `flex: 1`，
          两块读数会跟罗盘平分剩余高度，把读数卡撑成两个空荡荡的大方块
          （2026-10-09 实测截图如此）。弹性预算只给罗盘一处。 */}
      <View style={styles.readoutRow}>
        <Panel style={[styles.readoutCard, styles.readoutMain]}>
          <Label color={instrument.textSecondary}>当前方位</Label>
          <Metric color={instrument.accent} numberOfLines={1} style={styles.azimuth}>
            {azimuth.toFixed(2)}°
          </Metric>
          <Label color={instrument.muted} numberOfLines={1}>
            {sensorDriven ? '实时磁针 · 转动手机' : '无传感器数据 · 可拖动罗盘'}
          </Label>
        </Panel>
        <Panel style={styles.readoutCard}>
          <Label color={instrument.textSecondary}>磁场强度</Label>
          <AppText size="xl" weight="bold" color={instrument.text} numeric style={styles.magValue}>
            {sensor.magneticMagnitude === null
              ? '—'
              : `${sensor.magneticMagnitude.toFixed(1)} μT`}
          </AppText>
          <View style={styles.magStatus}>
            <View
              style={[
                styles.dot,
                {
                  backgroundColor:
                    sensor.magneticMagnitude === null
                      ? instrument.muted
                      : sensor.quality.magnetic >= 70
                        ? instrument.ok
                        : instrument.warn,
                },
              ]}
            />
            <Label color={instrument.textSecondary} numberOfLines={1}>
              {sensor.magneticMagnitude === null ? '无数据' : `磁场${sensor.quality.magneticLabel}`}
            </Label>
          </View>
        </Panel>
      </View>

      {/* ---------- 快捷令旗：三块并排 ---------- */}
      <View style={styles.quickRow}>
        <View style={styles.quickItem}>
          <InstrumentBlock
            width="auto"
            info={false}
            base={false}
            minHeight={72}
            iconBox={36}
            title="去测盘"
            desc="选择数据来源"
            icon={<Ionicons name="locate" size={20} color={instrument.accent} />}
            onPress={() => router.push('/test')}
          />
        </View>
        <View style={styles.quickItem}>
          <InstrumentBlock
            width="auto"
            info={false}
            base={false}
            minHeight={72}
            iconBox={36}
            title="每日早报"
            desc="黄历宜忌 + 当日运程"
            icon={<Ionicons name="sunny" size={20} color={instrument.accent} />}
            onPress={() => router.push('/morning')}
          />
        </View>
        <View style={styles.quickItem}>
          <InstrumentBlock
            width="auto"
            info={false}
            base={false}
            minHeight={72}
            iconBox={36}
            title="灵签机"
            desc="摇签筒、开奖、解签"
            icon={<Ionicons name="game-controller" size={20} color={instrument.accent} />}
            onPress={() => router.push('/qianji')}
          />
        </View>
      </View>

      {/* ---------- 脚注：已存盘面（可点进历史）+ 免责 ---------- */}
      <View style={styles.foot}>
        {data && data.total > 0 ? (
          <Pressable
            onPress={() => router.push('/history')}
            accessibilityRole="button"
            accessibilityLabel={`查看已保存的 ${data.total} 个盘面`}
            style={({ pressed }) => [styles.statsRow, pressed && styles.statsPressed]}
          >
            <Ionicons name="albums-outline" size={13} color={instrument.textSecondary} />
            <AppText size="xs" color={instrument.textSecondary} numberOfLines={1} style={styles.statsText}>
              已存 {data.total} 个盘面
              {data.latestTitle ? ` · 最近：${data.latestTitle}` : ''}
            </AppText>
            <Ionicons name="chevron-forward" size={13} color={instrument.muted} />
          </Pressable>
        ) : null}
        <AppText size="xs" color={instrument.muted} center numberOfLines={2}>
          {sensorDriven
            ? '实时磁针：读数为磁北，未做磁偏角改正；要存档请到「测盘」采集'
            : '无传感器数据时可拖动罗盘熟悉盘面；实测请到「测盘」选择数据来源'}
        </AppText>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  gear: {
    width: 36,
    height: 36,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: instrument.surfaceAlt,
  },
  retry: { marginTop: space[2] },

  /* 核心区：容器铺满弹性段，盘面在其中居中 */
  coreSlot: { alignItems: 'center' },
  core: { flex: 1, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center' },
  dialInner: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  northMark: { position: 'absolute', top: -2, alignItems: 'center' },
  northArrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 4,
    borderRightWidth: 4,
    borderBottomWidth: 7,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: instrument.needle,
  },

  readoutRow: { flexDirection: 'row', gap: space[3] },
  /* 面板的底/边/圆角/内边距一律由 `Panel` 给，这里只留布局 */
  readoutCard: { flex: 1, marginBottom: 0 },
  readoutMain: { flex: 1.5 },
  azimuth: { marginTop: space[1] },
  magValue: { marginTop: space[2] },
  magStatus: { flexDirection: 'row', alignItems: 'center', gap: space[1], marginTop: space[2] },
  dot: { width: 6, height: 6, borderRadius: 3 },

  quickRow: { flexDirection: 'row', gap: space[2] },
  quickItem: { flex: 1 },

  foot: { gap: 2 },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space[1],
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  statsPressed: { backgroundColor: hud.activeBg },
  statsText: { flexShrink: 1 },
});
