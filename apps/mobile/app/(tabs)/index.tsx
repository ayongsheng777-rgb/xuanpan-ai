/**
 * 罗盘（首页）—— 参考图第 1 屏「数字罗盘 · 仿真模式」。
 *
 * 布局（核心数据优先，V2 §31）：
 *   标题栏 → 真北指示 → 深色大罗盘（可拖动）→
 *   当前方位（大字）+ 磁场强度卡 → 去测盘 → 已存盘面
 *
 * 语义约定：
 *   - 本页罗盘是**实时磁针**：有磁力计数据时盘面跟着手机转（rotation = −方位角，
 *     与 /adjust「真实磁针」同一口径）；无数据时回退手拖并明示，不编造方位。
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
import { AppText, Label, Metric } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Panel, PressablePanel } from '@/components/Card';
import { CompassDial, DIAL_DARK } from '@/components/CompassDial';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { azimuthAtTop } from '@/lib/compassDial';
import { useAsync } from '@/lib/useAsync';
import { useSensorSnapshot } from '@/services/useSensors';
import { instrument, radius, space, tracking } from '@/theme/tokens';

interface HomeStats {
  total: number;
  latestTitle: string | null;
}

export default function CompassHomeScreen(): React.JSX.Element {
  const router = useRouter();
  /** 无传感器时的手动盘面旋转量（度）—— 仅回退用，有磁针数据时不生效 */
  const [manualRotation, setManualRotation] = useState(0);
  /** 首页订阅传感器：磁场卡与实时磁针都要它（进入即开始，离开即停止，见 useSensors 注释） */
  const sensor = useSensorSnapshot(true);

  /**
   * 实时磁针：有方位角数据 → 盘面由磁针驱动（rotation = −azimuth，
   * 顶部读数 = azimuthAtTop(rotation) = azimuth，见 lib/compassDial 注释）；
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
  //
  // 🔴 必须走 `azimuthAtTop`：顶部读数 = **−rotation**。原先写的是 `+rotation`，
  //    于是把盘拖到东边读数显示西边 —— 界面一切正常，且在 0°/180° 上看起来还对。
  const azimuth = azimuthAtTop(rotation);

  return (
    <Screen scroll style={styles.root} onRefresh={reload} refreshing={false}>
      {/* ---------- 标题栏 ---------- */}
      <View style={styles.headerRow}>
        <AppText size="xl" weight="bold" color={instrument.text} track="tight">
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
        <Label color={instrument.textSecondary}>真北 0°</Label>
        <View style={styles.northArrow} />
      </View>

      {/* ---------- 深色大罗盘（实时磁针；无数据时回退手拖） ----------
          盘式取「三元三合综合盘」：实物综合盘就是这个层数密度。
          层数越多越接近用户手里的盘面，而"一眼看出排位是否一致"
          正是这个组件存在的理由（见 CompassDial 文件头注释）。
          磁针驱动时禁止手拖：转的是手机，不是盘面 —— 拖盘面会制造
          "读数与手机朝向不一致"的假状态。 */}
      <View style={styles.dialWrap}>
        <CompassDial
          size={320}
          palette={DIAL_DARK}
          style="zonghe"
          rotation={rotation}
          interactive={!sensorDriven}
          onRotate={setManualRotation}
        />
      </View>

      {/* ---------- 核心读数 ----------
          「一屏一个主角」：整个首页只有方位角用 `Metric`（40px/特粗/等宽数字），
          磁场强度降一档到 xl —— 两块读数原本同为大字，用户看不出该先看哪个。
          `numberOfLines={1}` 兜住窄屏：读数宁可缩小也不能折行，
          折了行就不是"仪表"了。 */}
      <View style={styles.readoutRow}>
        <Panel style={[styles.readoutCard, styles.readoutMain]}>
          <Label color={instrument.textSecondary}>当前方位</Label>
          <Metric color={instrument.accent} numberOfLines={1} style={styles.azimuth}>
            {azimuth.toFixed(2)}°
          </Metric>
          <Label color={instrument.muted}>
            {sensorDriven ? '实时磁针 · 转动手机' : '无传感器数据 · 可拖动罗盘'}
          </Label>
        </Panel>
        <Panel style={styles.readoutCard}>
          <Label color={instrument.textSecondary}>磁场强度</Label>
          <AppText
            size="xl"
            weight="bold"
            color={instrument.text}
            numeric
            style={styles.magValue}
          >
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
            <Label color={instrument.textSecondary}>
              {sensor.magneticMagnitude === null ? '无数据' : `磁场${sensor.quality.magneticLabel}`}
            </Label>
          </View>
        </Panel>
      </View>

      {/* ---------- 去测盘（本页唯一的采集入口） ----------
          五条数据来源统一收在「测盘」tab，此处只跳转、不重复列出。
          故意**不在这里显示任何读数**：那属于测盘流程（一页一事）。 */}
      <PressablePanel
        onPress={() => router.push('/test')}
        accessibilityLabel="去测盘，选择数据来源"
        style={styles.ctaWrap}
        contentStyle={styles.ctaContent}
      >
        <View style={styles.ctaIcon}>
          <Ionicons name="locate" size={22} color={instrument.accent} />
        </View>
        <View style={styles.ctaBody}>
          <AppText size="md" weight="semibold" color={instrument.text}>
            去测盘
          </AppText>
          <AppText size="xs" color={instrument.textSecondary} style={styles.ctaDesc}>
            拍摄真实罗盘 / 导入照片 / 手机传感器 / 手动输入 / 我的罗盘
          </AppText>
        </View>
        <Ionicons name="chevron-forward" size={18} color={instrument.muted} />
      </PressablePanel>

      {/* ---------- 每日早报 & 灵签机 ----------
          高频轻量入口：早报是每天看一眼的东西，签机是游戏化的抽签。
          与「去测盘」同一视觉语言（PressablePanel + instrument 色域）。 */}
      <View style={styles.dailyRow}>
        <PressablePanel
          onPress={() => router.push('/morning')}
          accessibilityLabel="打开每日早报"
          style={styles.dailyCard}
          contentStyle={styles.dailyContent}
        >
          <View style={styles.ctaIcon}>
            <Ionicons name="sunny" size={22} color={instrument.accent} />
          </View>
          <View style={styles.ctaBody}>
            <AppText size="md" weight="semibold" color={instrument.text}>
              每日早报
            </AppText>
            <AppText size="xs" color={instrument.textSecondary} style={styles.ctaDesc}>
              黄历宜忌 + 按你生日算的当日运程
            </AppText>
          </View>
          <Ionicons name="chevron-forward" size={18} color={instrument.muted} />
        </PressablePanel>
        <PressablePanel
          onPress={() => router.push('/qianji')}
          accessibilityLabel="打开灵签机"
          style={styles.dailyCard}
          contentStyle={styles.dailyContent}
        >
          <View style={styles.ctaIcon}>
            <Ionicons name="game-controller" size={22} color={instrument.accent} />
          </View>
          <View style={styles.ctaBody}>
            <AppText size="md" weight="semibold" color={instrument.text}>
              灵签机
            </AppText>
            <AppText size="xs" color={instrument.textSecondary} style={styles.ctaDesc}>
              摇签筒、开奖、解签，街机式抽签
            </AppText>
          </View>
          <Ionicons name="chevron-forward" size={18} color={instrument.muted} />
        </PressablePanel>
      </View>

      {/* ---------- 今日状态 ---------- */}
      {data && data.total > 0 ? (
        <PressablePanel
          onPress={() => router.push('/history')}
          accessibilityLabel={`查看已保存的 ${data.total} 个盘面`}
          style={styles.statsWrap}
          contentStyle={styles.statsContent}
        >
          <View style={styles.statsInner}>
            <View style={styles.statsText}>
              <AppText size="sm" weight="semibold" color={instrument.text}>
                已保存 {data.total} 个盘面
              </AppText>
              {data.latestTitle ? (
                <AppText size="xs" color={instrument.textSecondary} style={styles.latest}>
                  最近：{data.latestTitle}
                </AppText>
              ) : null}
            </View>
            <Ionicons name="chevron-forward" size={18} color={instrument.muted} />
          </View>
        </PressablePanel>
      ) : null}

      <AppText size="xs" color={instrument.muted} center style={styles.disclaimer}>
        {sensorDriven
          ? '实时磁针：读数为磁北，未做磁偏角改正；要存档请到「测盘」采集'
          : '无传感器数据时可拖动罗盘熟悉盘面；实测请到「测盘」选择数据来源'}
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
  /* 面板的底/边/圆角/内边距一律由 `Panel` 给，这里只留布局 —— 见 Card.tsx 的「三个表面原语」 */
  readoutCard: { flex: 1, marginBottom: 0 },
  readoutMain: { flex: 1.5 },
  azimuth: { marginTop: space[2], marginBottom: space[1] },
  magValue: { marginTop: space[2] },
  magStatus: { flexDirection: 'row', alignItems: 'center', gap: space[1], marginTop: space[2] },
  dot: { width: 6, height: 6, borderRadius: 3 },

  dailyRow: { marginTop: space[4], gap: space[3] },
  dailyCard: { marginBottom: 0 },
  dailyContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    marginBottom: 0,
  },
  ctaWrap: { marginTop: space[4] },
  ctaContent: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space[3],
    marginBottom: 0,
  },
  ctaIcon: {
    width: 40,
    height: 40,
    /* 内嵌图形用 radius.sm，比外层容器的 lg 紧一档（内紧外松） */
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: instrument.surfaceAlt,
  },
  ctaBody: { flex: 1 },
  ctaDesc: { marginTop: 2 },

  statsWrap: { marginTop: space[3] },
  statsContent: { marginBottom: 0 },
  statsInner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space[2],
  },
  statsText: { flex: 1 },
  latest: { marginTop: 2 },
  disclaimer: { marginTop: space[4], letterSpacing: tracking.normal },
});
