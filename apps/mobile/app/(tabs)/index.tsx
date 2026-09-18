/**
 * 罗盘（首页）—— 参考图第 1 屏「数字罗盘 · 仿真模式」。
 *
 * 布局（核心数据优先，V2 §31）：
 *   标题栏 → 真北指示 → 深色大罗盘（可拖动）→
 *   当前方位（大字）+ 磁场强度卡 → 去测盘 → 已存盘面
 *
 * 语义约定：
 *   - 本页罗盘是**仿真模式**：用户拖出的方向就是「当前方位」，
 *     不读取传感器（传感器测量在 /sensors 页，职责分离，V2 §30「一页一事」）。
 *   - 磁场卡的数据来自传感器；设备无磁力计/数据未到时显示「—」占位，
 *     **不编造数值**（RULE-008 同精神：没有就是没有）。
 *
 * 🔴 本页**不再放「扫描/传感器/手动」三个入口**，改为一个「去测盘」。
 *    理由：底栏新增了「测盘」tab，那三条来源属于测盘流程；两处都放，
 *    用户会以为它们是两套不同的功能，而其中一套（首页那三个）没有
 *    模板库与档案详情。入口只留一处，职责边界才清楚。
 *
 * 深色仪器风（instrument 色域）仅用于罗盘域 —— 见《V2 评估与实施路线》冲突 2 裁决。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card } from '@/components/Card';
import { CompassDial, DIAL_DARK } from '@/components/CompassDial';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { azimuthAtTop } from '@/lib/compassDial';
import { useAsync } from '@/lib/useAsync';
import { useSensorSnapshot } from '@/services/useSensors';
import { instrument, radius, space } from '@/theme/tokens';

interface HomeStats {
  total: number;
  latestTitle: string | null;
}

export default function CompassHomeScreen(): React.JSX.Element {
  const router = useRouter();
  /** 仿真模式的盘面旋转量（度）。用户拖出来的「当前方位」 */
  const [rotation, setRotation] = useState(0);
  /** 磁场卡需要传感器 —— 首页也订阅（进入即开始，离开即停止，见 useSensors 注释） */
  const sensor = useSensorSnapshot(true);

  const load = useCallback(async (): Promise<HomeStats> => {
    const page = await getApiClient().listSessions(1, 0);
    return { total: page.total, latestTitle: page.items[0]?.title ?? null };
  }, []);
  const { data, error, reload } = useAsync(load, []);

  // 方位按 0..360 显示（负角如 -12.72° 显示为 347.28°，与实物罗盘读法一致）。
  //
  // 🔴 必须走 `azimuthAtTop`：顶部读数 = **−rotation**。原先写的是 `+rotation`，
  //    于是把盘拖到东边读数显示西边 —— 界面一切正常，且在 0°/180° 上看起来还对。
  const azimuth = azimuthAtTop(rotation);

  return (
    <Screen scroll style={styles.root} onRefresh={reload} refreshing={false}>
      {/* ---------- 标题栏 ---------- */}
      <View style={styles.headerRow}>
        <AppText size="xl" weight="bold" color={instrument.text}>
          玄盘 AI
        </AppText>
        <View style={styles.headerActions}>
          <HelpButton topic="compass-home" color={instrument.textSecondary} />
          <Pressable
            onPress={() => router.push('/mine')}
            accessibilityLabel="设置"
            hitSlop={10}
            style={styles.gear}
          >
            <Ionicons name="settings-outline" size={20} color={instrument.textSecondary} />
          </Pressable>
        </View>
      </View>

      {error ? (
        <Banner tone="error" title="无法连接后端服务" style={styles.banner}>
          <AppText size="sm">{error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={reload} />
        </Banner>
      ) : null}

      {/* ---------- 真北指示 ---------- */}
      <View style={styles.northRow}>
        <AppText size="xs" color={instrument.textSecondary}>
          真北 0°
        </AppText>
        <View style={styles.northArrow} />
      </View>

      {/* ---------- 深色大罗盘（仿真：可拖动） ----------
          盘式取「三元三合综合盘」：实物综合盘就是这个层数密度。
          层数越多越接近用户手里的盘面，而"一眼看出排位是否一致"
          正是这个组件存在的理由（见 CompassDial 文件头注释）。 */}
      <View style={styles.dialWrap}>
        <CompassDial
          size={320}
          palette={DIAL_DARK}
          style="zonghe"
          rotation={rotation}
          interactive
          onRotate={setRotation}
        />
      </View>

      {/* ---------- 核心读数 ---------- */}
      <View style={styles.readoutRow}>
        <View style={[styles.readoutCard, styles.readoutMain]}>
          <AppText size="xs" color={instrument.textSecondary}>
            当前方位（仿真）
          </AppText>
          <AppText size="display" weight="bold" color={instrument.accent} style={styles.azimuth}>
            {azimuth.toFixed(2)}°
          </AppText>
          <AppText size="xs" color={instrument.muted}>
            拖动罗盘改变方向
          </AppText>
        </View>
        <View style={styles.readoutCard}>
          <AppText size="xs" color={instrument.textSecondary}>
            磁场强度
          </AppText>
          <AppText size="xl" weight="bold" color={instrument.text} style={styles.magValue}>
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
            <AppText size="xs" color={instrument.textSecondary}>
              {sensor.magneticMagnitude === null ? '无数据' : `磁场${sensor.quality.magneticLabel}`}
            </AppText>
          </View>
        </View>
      </View>

      {/* ---------- 去测盘（本页唯一的采集入口） ----------
          五条数据来源统一收在「测盘」tab，此处只跳转、不重复列出。
          故意**不在这里显示任何读数**：那属于测盘流程（一页一事）。 */}
      <Pressable
        onPress={() => router.push('/test')}
        accessibilityRole="button"
        accessibilityLabel="去测盘，选择数据来源"
        style={({ pressed }) => [styles.cta, pressed && styles.ctaPressed]}
      >
        <View style={styles.ctaIcon}>
          <Ionicons name="locate" size={22} color={instrument.accent} />
        </View>
        <View style={styles.ctaBody}>
          <AppText size="md" weight="medium" color={instrument.text}>
            去测盘
          </AppText>
          <AppText size="xs" color={instrument.textSecondary} style={styles.ctaDesc}>
            拍摄真实罗盘 / 导入照片 / 手机传感器 / 手动输入 / 我的罗盘
          </AppText>
        </View>
        <Ionicons name="chevron-forward" size={18} color={instrument.muted} />
      </Pressable>

      {/* ---------- 今日状态 ---------- */}
      {data && data.total > 0 ? (
        <Pressable onPress={() => router.push('/history')} style={styles.statsCard}>
          <AppText size="sm" weight="semibold" color={instrument.text}>
            已保存 {data.total} 个盘面
          </AppText>
          {data.latestTitle ? (
            <AppText size="xs" color={instrument.textSecondary} style={styles.latest}>
              最近：{data.latestTitle}
            </AppText>
          ) : null}
        </Pressable>
      ) : null}

      <AppText size="xs" color={instrument.muted} center style={styles.disclaimer}>
        仿真模式仅用于熟悉盘面；实测请到「测盘」选择数据来源
      </AppText>
    </Screen>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: space[1] },
  gear: { padding: space[2], borderRadius: radius.pill, backgroundColor: instrument.surface },
  banner: { marginTop: space[3] },
  retry: { marginTop: space[2] },
  northRow: { alignItems: 'center', marginTop: space[4], gap: 2 },
  northArrow: {
    width: 0,
    height: 0,
    borderLeftWidth: 5,
    borderRightWidth: 5,
    borderBottomWidth: 8,
    borderLeftColor: 'transparent',
    borderRightColor: 'transparent',
    borderBottomColor: instrument.needle,
  },
  dialWrap: { alignItems: 'center', marginTop: space[1] },
  readoutRow: { flexDirection: 'row', gap: space[3], marginTop: space[4] },
  readoutCard: {
    backgroundColor: instrument.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    padding: space[3],
  },
  readoutMain: { flex: 1.4 },
  azimuth: { marginTop: space[1], fontVariant: ['tabular-nums'] },
  magValue: { marginTop: space[2], fontVariant: ['tabular-nums'] },
  magStatus: { flexDirection: 'row', alignItems: 'center', gap: space[1], marginTop: space[1] },
  dot: { width: 6, height: 6, borderRadius: 3 },
  cta: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    marginTop: space[4],
    padding: space[3],
    borderRadius: radius.lg,
    backgroundColor: instrument.surface,
    borderWidth: 1,
    borderColor: instrument.border,
  },
  ctaPressed: { backgroundColor: instrument.surfaceAlt },
  ctaIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: instrument.surfaceAlt,
  },
  ctaBody: { flex: 1 },
  ctaDesc: { marginTop: 2, lineHeight: 17 },
  statsCard: {
    marginTop: space[4],
    backgroundColor: instrument.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    padding: space[3],
  },
  latest: { marginTop: 2 },
  disclaimer: { marginTop: space[4] },
});
