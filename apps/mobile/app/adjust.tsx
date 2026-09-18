/**
 * 手动调节罗盘 `/adjust` —— 参考图第 2 屏。
 *
 * 布局：大罗盘 → 角度调节（步进 + 当前角度）→ 锁定开关 → 底部模式栏。
 *
 * 两个模式的语义（**都真实生效，不放占位按钮**）：
 *   - 仿真模式：用户手动拖盘 / 步进调节方位角（默认）。
 *   - 真实磁针：盘面由手机磁力计驱动 —— 转动手机，盘面跟着转。
 *     传感器无数据时退回仿真并明示（不能转圈等数据）。
 *
 * 两个锁的语义（V2 §6.3 的子集，本轮先做与调节直接相关的两个）：
 *   - 锁定天池：禁止拖动盘面（防止误触改变已调好的角度）。
 *   - 锁定北向：强制盘面 0°（子）对正屏幕上方真北，角度归零。
 *
 * 演示图底部还有「自动水平 / 盘体跟随」两个模式，本轮**不做**：
 *   前者要持续姿态驱动 UI（Phase 2 后续），后者要校准工作台（Phase 4）。
 *   放两个点了没反应的按钮，比没有这两个按钮更糟（sanshi.tsx 注释的既有判断）。
 *
 * 本页也是「我的罗盘」模板的落地页，故接受 4 个查询参数：
 *   `template`（id，仅用于说明）、`name`、`style`（盘式）、`sitting`/`degree`（初始坐向/角度）。
 *   🔴 这四个参数**必须真的被读取**：模板的全部意义就是带出盘式与基准，
 *   参数不落地等于该功能不存在，而界面看起来完全正常。
 */

import { Ionicons } from '@expo/vector-icons';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Switch, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { CompassDial, DIAL_DARK } from '@/components/CompassDial';
import { HelpButton } from '@/components/HelpButton';
import { Screen } from '@/components/Screen';
import { normalizeSigned } from '@/lib/compassDial';
import { DIAL_STYLES, coerceDialStyle } from '@/lib/dialStyle';
import { indexOfName, indexToDegree, oppositeIndex } from '@/lib/ring24';
import { useSensorSnapshot } from '@/services/useSensors';
import { instrument, radius, space } from '@/theme/tokens';

/** 角度调节步长（V2 §6.2：±1° / ±0.1°；±10° 用拖盘完成，不需要按钮） */
const ANGLE_STEPS = [-1, -0.1, 0.1, 1] as const;

type Mode = 'simulation' | 'sensor';

export default function AdjustCompassScreen(): React.JSX.Element {
  const router = useRouter();
  /**
   * 模板库带出的参数。
   *
   * 🔴 这些参数原先**没有被读取** —— 用户点模板落到本页，什么都没生效，
   *    而界面看起来完全正常。模板的全部意义就是"带出盘式与默认坐向"，
   *    参数不落地等于该功能不存在。
   */
  const params = useLocalSearchParams<{
    template?: string;
    name?: string;
    style?: string;
    sitting?: string;
    degree?: string;
  }>();

  /** 盘式：未知值一律回落（后端刻意不校验枚举，见 dialStyle.ts） */
  const [dialStyle, setDialStyle] = useState(() => coerceDialStyle(params.style));

  /**
   * 模板的初始角度。口径按**优先级**取，不做加权或折中：
   *   1. `degree` —— 显式的实测朝向角，直接就是「当前方位」
   *   2. `sitting` —— 只有坐山时取**对宫**：坐午则向子，界面读数应为向
   *   3. 都没有 → 0（不假装有个默认坐向）
   */
  const templateManual = useMemo(() => {
    if (params.degree !== undefined && params.degree !== '') {
      const d = Number(params.degree);
      if (Number.isFinite(d)) return d;
    }
    if (params.sitting) {
      const i = indexOfName(params.sitting);
      if (i >= 0) return indexToDegree(oppositeIndex(i));
    }
    return null;
  }, [params.degree, params.sitting]);

  const [mode, setMode] = useState<Mode>('simulation');
  /**
   * 仿真模式的**方位角**（不是盘面旋转量）。
   *
   * 存方位角而非旋转量是刻意的：用户在这一页做的是"把读数调到我要的值"，
   * 状态与目标同向，步进按钮也就直接 +delta。
   * 盘面旋转量由 `rotation = −方位角` 推出（顶部读数 = −rotation，
   * 见 `lib/compassDial.ts` 的 `azimuthAtTop`）。
   */
  const [manualAzimuth, setManualAzimuth] = useState(templateManual ?? 0);
  const [lockPool, setLockPool] = useState(false);
  const [lockNorth, setLockNorth] = useState(false);

  /** 模板是否真的带出了东西 —— 决定要不要显示那张"已按模板带出"的说明 */
  const fromTemplate = params.template !== undefined || templateManual !== null;

  // 只有真实磁针模式才订阅传感器（省电，见 useSensors 注释）
  const sensor = useSensorSnapshot(mode === 'sensor');
  const sensorDriven = mode === 'sensor' && sensor.azimuth !== null;

  // 显示方位：锁北 → 0；真实磁针 → 传感器方位；否则手工方位角
  const azimuth = lockNorth
    ? 0
    : sensorDriven
      ? sensor.azimuth!
      : ((normalizeSigned(manualAzimuth) % 360) + 360) % 360;
  // 盘面旋转量：让盘面角 = azimuth 的刻度转到屏幕上方 → rotation = -azimuth
  const rotation = -azimuth;

  const locked = lockPool || lockNorth || sensorDriven;

  const nudge = useCallback(
    (delta: number) => {
      if (locked) return;
      setManualAzimuth((m) => m + delta);
    },
    [locked],
  );

  return (
    <>
      <Stack.Screen
        options={{
          title: '手动调节',
          headerStyle: { backgroundColor: instrument.bg },
          headerTintColor: instrument.text,
          headerShadowVisible: false,
          headerRight: () => (
            <View style={styles.headerActions}>
              <HelpButton topic="adjust" color={instrument.textSecondary} />
              <Pressable onPress={() => router.back()} hitSlop={10}>
                <AppText size="md" weight="semibold" color={instrument.accent}>
                  完成
                </AppText>
              </Pressable>
            </View>
          ),
        }}
      />
      <Screen scroll style={styles.root}>
        {/* ---------- 大罗盘 ---------- */}
        <View style={styles.northRow}>
          <AppText size="xs" color={instrument.textSecondary}>
            北 0°
          </AppText>
          <View style={styles.northArrow} />
        </View>
        <View style={styles.dialWrap}>
          <CompassDial
            size={320}
            palette={DIAL_DARK}
            style={dialStyle}
            rotation={rotation}
            interactive={!locked}
            onRotate={(r) => setManualAzimuth(-r)}
          />
        </View>

        {/* ---------- 模板带出说明 ----------
            必须有这张卡：参数生效与否在盘面上"看不出来是模板带来的"，
            用户点完模板会以为没反应。 */}
        {fromTemplate ? (
          <View style={styles.card}>
            <AppText size="sm" weight="medium" color={instrument.text}>
              已按模板带出
            </AppText>
            <AppText size="xs" color={instrument.textSecondary} style={styles.templateLine}>
              {params.name ? `模板：${params.name}　` : ''}
              盘式：{DIAL_STYLES[dialStyle].name}
              {params.sitting ? `　坐${params.sitting}` : ''}
            </AppText>
            <View style={styles.styleRow}>
              {(['simple', 'sanhe', 'zonghe'] as const).map((sid) => {
                const on = sid === dialStyle;
                return (
                  <Pressable
                    key={sid}
                    onPress={() => setDialStyle(sid)}
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
            <AppText size="xs" color={instrument.muted} style={styles.templateNote}>
              模板只带出「用哪面盘、从哪个基准开始」，不代替本次实测。
            </AppText>
          </View>
        ) : null}

        {/* ---------- 角度调节 ---------- */}
        <View style={styles.card}>
          <AppText size="xs" color={instrument.textSecondary}>
            角度调节
          </AppText>
          <AppText size="display" weight="bold" color={instrument.text} center style={styles.angle}>
            {azimuth.toFixed(2)}°
          </AppText>
          <View style={styles.stepRow}>
            {ANGLE_STEPS.map((d) => (
              <Pressable
                key={d}
                disabled={locked}
                onPress={() => nudge(d)}
                accessibilityRole="button"
                accessibilityLabel={`${d > 0 ? '加' : '减'}${Math.abs(d)}度`}
                style={({ pressed }) => [
                  styles.stepBtn,
                  locked && styles.stepBtnDisabled,
                  pressed && !locked && styles.stepBtnPressed,
                ]}
              >
                <AppText size="sm" weight="semibold" color={instrument.text}>
                  {d > 0 ? `+${d}°` : `−${Math.abs(d)}°`}
                </AppText>
              </Pressable>
            ))}
          </View>
        </View>

        {/* ---------- 锁定 ---------- */}
        <View style={styles.card}>
          <LockRow
            label="锁定天池"
            hint="禁止拖动盘面，防止误触"
            value={lockPool}
            onChange={(v) => setLockPool(v)}
          />
          <View style={styles.divider} />
          <LockRow
            label="锁定北向"
            hint="盘面 0°（子）强制对正真北，角度归零"
            value={lockNorth}
            onChange={(v) => {
              setLockNorth(v);
              if (v) setManualAzimuth(0);
            }}
          />
        </View>

        {mode === 'sensor' && sensor.azimuth === null ? (
          <View style={styles.card}>
            <AppText size="sm" color={instrument.warn}>
              传感器暂无数据 —— 已退回手动调节。模拟器通常没有磁力计，请在真机上使用真实磁针。
            </AppText>
          </View>
        ) : null}

        {/* ---------- 底部模式栏 ---------- */}
        <View style={styles.modeBar}>
          <ModeItem
            label="仿真模式"
            icon="color-wand-outline"
            active={mode === 'simulation'}
            onPress={() => setMode('simulation')}
          />
          <ModeItem
            label="真实磁针"
            icon="navigate-outline"
            active={mode === 'sensor'}
            onPress={() => setMode('sensor')}
          />
        </View>

        <AppText size="xs" color={instrument.muted} center style={styles.note}>
          盘面正上方恒为真北（磁针不随盘转）。调节的是视角，不产生任何术数计算结果
        </AppText>
      </Screen>
    </>
  );
}

function LockRow({
  label,
  hint,
  value,
  onChange,
}: {
  label: string;
  hint: string;
  value: boolean;
  onChange: (v: boolean) => void;
}): React.JSX.Element {
  return (
    <View style={styles.lockRow}>
      <View style={styles.lockText}>
        <AppText size="md" weight="medium" color={instrument.text}>
          {label}
        </AppText>
        <AppText size="xs" color={instrument.textSecondary} style={styles.lockHint}>
          {hint}
        </AppText>
      </View>
      <Switch
        value={value}
        onValueChange={onChange}
        trackColor={{ false: instrument.surfaceAlt, true: instrument.accent }}
        thumbColor={instrument.text}
      />
    </View>
  );
}

function ModeItem({
  label,
  icon,
  active,
  onPress,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  active: boolean;
  onPress: () => void;
}): React.JSX.Element {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: active }}
      style={({ pressed }) => [
        styles.modeItem,
        active && styles.modeItemActive,
        pressed && styles.modeItemPressed,
      ]}
    >
      <Ionicons name={icon} size={20} color={active ? instrument.bg : instrument.textSecondary} />
      <AppText
        size="xs"
        weight={active ? 'semibold' : 'regular'}
        color={active ? instrument.bg : instrument.textSecondary}
        center
        style={styles.modeLabel}
      >
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { backgroundColor: instrument.bg },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: space[2] },
  northRow: { alignItems: 'center', gap: 2 },
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
  card: {
    marginTop: space[4],
    backgroundColor: instrument.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: instrument.border,
    padding: space[3],
  },
  angle: { marginTop: space[1], fontVariant: ['tabular-nums'] },
  templateLine: { marginTop: space[1], lineHeight: 17 },
  templateNote: { marginTop: space[2], lineHeight: 16 },
  styleRow: { flexDirection: 'row', gap: space[2], marginTop: space[3] },
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
  stepRow: { flexDirection: 'row', gap: space[2], marginTop: space[3] },
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
  stepBtnDisabled: { opacity: 0.4 },
  lockRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  lockText: { flex: 1, paddingRight: space[3] },
  lockHint: { marginTop: 2 },
  divider: { height: 1, backgroundColor: instrument.border, marginVertical: space[3] },
  modeBar: { flexDirection: 'row', gap: space[3], marginTop: space[4] },
  modeItem: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: space[3],
    borderRadius: radius.lg,
    backgroundColor: instrument.surface,
    borderWidth: 1,
    borderColor: instrument.border,
  },
  modeItemActive: { backgroundColor: instrument.accent, borderColor: instrument.accent },
  modeItemPressed: { opacity: 0.8 },
  modeLabel: { marginTop: space[1] },
  note: { marginTop: space[4] },
});
