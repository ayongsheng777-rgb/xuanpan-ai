/**
 * 灵签机 —— 街机式抽签。
 *
 * 游戏感来自三处，不是花架子：
 * 1. **签筒是真的在"摇"**：按住红色大按钮，签枝抖动；松手，一支签弹出来。
 *    动画只是表现层 —— 签号在按下瞬间已由种子唯一确定（确定性引擎），
 *    不是动画"摇"出来的。help 里写明了这一点。
 * 2. **开奖仪式感**：签号像老虎机一样滚动后定格，等级配街机配色与喝彩词。
 * 3. **每日一票**：「今日一签」每天只有一支（种子 = 当天日期），天然可复现；
 *    「随意一签」每次取当前时刻为种子。
 *
 * 解签两条路：传统签解（引擎自带的签文解读）与 AI 解签
 *（保存为会话 → 走报告流程，与占测页同一链路）。
 *
 * ## 单屏做法（2026-10-09）
 *
 * 街机主交互（签筒舞台）放**唯一弹性区** `FitSlot weight={1}`；
 * 选签库 / 选模式只在待机时占位，摇签与开奖时让位给结果。
 * 摇签大按钮**固定在弹性区下方、始终可见**（见下方 ⚠️ 说明）。
 * 签文与解签较长，收进 `InfoPopup`，页面只留等级、签号与签题。
 *
 * ## ⚠️ 摇签按钮为什么必须常驻（BUG 2a，2026-10-08 用户实报）
 *
 * 原来 `phase==='idle'` 才渲染 Pressable：手指按住 → onPressIn 把 phase 置为
 * shaking → Pressable 被卸载 → 松手时 onPressOut 永远收不到 → 签筒卡在"摇签中"。
 * 现在按钮一直在，只是非 idle 时禁用按压、只换文案；onPressIn/onPressOut 内部仍有
 * phase 守卫。改造版面时**务必保持它不被条件卸载**。
 */

import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Animated, Pressable, StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type { LayerPreview } from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card, KeyValueRow } from '@/components/Card';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { QianSetPicker } from '@/components/QianSetPicker';
import { FitSlot, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import { todayISODate } from '@/lib/date';
import { useSubmit } from '@/lib/useAsync';
import { colors, radius, space } from '@/theme/tokens';

type Phase = 'idle' | 'shaking' | 'revealing';
type DrawMode = 'daily' | 'free';

const STICK_COUNT = 16;
const MIN_SHAKE_MS = 700;
const ROLL_MS = 900;

/** 等级 → 街机配色与喝彩词（观音签库三个等级全覆盖） */
const LEVEL_STYLE: Record<string, { color: string; cheer: string }> = {
  上上: { color: '#C9A227', cheer: '大吉大利！' },
  上吉: { color: '#D97B29', cheer: '上吉之签！' },
  中吉: { color: colors.jade, cheer: '中吉' },
  中平: { color: colors.textSecondary, cheer: '平签，稳中求进' },
  中凶: { color: '#5B7A99', cheer: '中凶，宜守不宜攻' },
  下下: { color: colors.muted, cheer: '宜静不宜动' },
};

/** 默认签库：观音灵签一百签（第三方来源，2026-10-07 用户指定引入） */
const DEFAULT_SET_ID = 'guanyin';

interface Stick {
  id: number;
  dx: number;
  dy: number;
  rot: string;
}

function makeSticks(): Stick[] {
  return Array.from({ length: STICK_COUNT }, (_, i) => ({
    id: i,
    dx: (i - STICK_COUNT / 2) * 7,
    dy: 0,
    rot: `${((i * 37) % 11) - 5}deg`,
  }));
}

function jitterSticks(): Stick[] {
  return Array.from({ length: STICK_COUNT }, (_, i) => ({
    id: i,
    dx: (i - STICK_COUNT / 2) * 7 + (Math.random() * 14 - 7),
    dy: -(Math.random() * 26),
    rot: `${Math.random() * 24 - 12}deg`,
  }));
}

function dailySeed(): number {
  return Number(todayISODate().replace(/-/g, ''));
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

export default function QianjiScreen(): React.JSX.Element {
  const router = useRouter();
  const [mode, setMode] = useState<DrawMode>('daily');
  const [setId, setSetId] = useState(DEFAULT_SET_ID);
  const [phase, setPhase] = useState<Phase>('idle');
  const [sticks, setSticks] = useState<Stick[]>(makeSticks);
  const [signTotal, setSignTotal] = useState(100);
  const [rollNumber, setRollNumber] = useState<number | null>(null);
  const [preview, setPreview] = useState<LayerPreview | null>(null);
  const [seedUsed, setSeedUsed] = useState<number | null>(null);
  const [showTradition, setShowTradition] = useState(false);

  const calc = useSubmit(getApiClient().calcQian);
  const create = useSubmit(getApiClient().createSession);
  const patch = useSubmit(getApiClient().patchInputs);

  const shakeTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  /** 看门狗：onPressOut 因任何原因没触发时（如切后台），60 秒后强制收尾 */
  const shakeWatchdog = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pressStart = useRef(0);
  const popY = useRef(new Animated.Value(0)).current;
  const revealScale = useRef(new Animated.Value(0.6)).current;

  // 跑马灯：10 盏灯依次明灭
  const lamps = useRef(Array.from({ length: 10 }, () => new Animated.Value(0.25))).current;
  useEffect(() => {
    const loops = lamps.map((v, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.delay(i * 140),
          Animated.timing(v, { toValue: 1, duration: 280, useNativeDriver: true }),
          Animated.timing(v, { toValue: 0.25, duration: 280, useNativeDriver: true }),
        ]),
      ),
    );
    loops.forEach((l) => l.start());
    return () => loops.forEach((l) => l.stop());
  }, [lamps]);

  // 当前签库的签数（老虎机滚动上限），取不到就用 100 兜底 —— 只影响滚动动画的数字范围
  useEffect(() => {
    getApiClient()
      .qianSets()
      .then((r) => {
        // `total` 不在 QianSet 的声明字段里（走索引签名 → unknown），这里做类型收窄
        const total: unknown = r.sets.find((s) => s.set_id === setId)?.total;
        if (typeof total === 'number' && total > 0) setSignTotal(total);
      })
      .catch(() => {});
  }, [setId]);

  useEffect(
    () => () => {
      if (shakeTimer.current) clearInterval(shakeTimer.current);
      if (shakeWatchdog.current) clearTimeout(shakeWatchdog.current);
    },
    [],
  );

  const stopShakeVisual = useCallback(() => {
    if (shakeTimer.current) {
      clearInterval(shakeTimer.current);
      shakeTimer.current = null;
    }
    if (shakeWatchdog.current) {
      clearTimeout(shakeWatchdog.current);
      shakeWatchdog.current = null;
    }
    setSticks(makeSticks());
  }, []);

  /** 按住开始摇：签枝抖动 + 后台请求签文（两条线并行） */
  const onPressIn = useCallback(() => {
    if (phase !== 'idle') return;
    pressStart.current = Date.now();
    setPhase('shaking');
    setShowTradition(false);
    setPreview(null);
    setRollNumber(null);
    popY.setValue(0);
    revealScale.setValue(0.6);
    shakeTimer.current = setInterval(() => setSticks(jitterSticks()), 100);
    // 兜底：onPressOut 因任何原因没触发时，60 秒后强制回到 idle，
    // 签筒永不卡在"摇签中…"。正常松手会在 onPressOut 里清掉它。
    if (shakeWatchdog.current) clearTimeout(shakeWatchdog.current);
    shakeWatchdog.current = setTimeout(() => {
      stopShakeVisual();
      setPhase((p) => (p === 'shaking' ? 'idle' : p));
    }, 60_000);
  }, [phase, popY, revealScale, stopShakeVisual]);

  /** 松手：保证最短摇晃时长 → 停抖 → 弹签 → 老虎机定格 → 开奖 */
  const onPressOut = useCallback(async () => {
    if (phase !== 'shaking') return;
    const seed = mode === 'daily' ? dailySeed() : Date.now();
    setSeedUsed(seed);

    const elapsed = Date.now() - pressStart.current;
    const [result] = await Promise.all([calc.run({ seed, set_id: setId }), sleep(Math.max(0, MIN_SHAKE_MS - elapsed))]);
    stopShakeVisual();
    if (!result) {
      setPhase('idle');
      return;
    }
    setPreview(result);
    setPhase('revealing');

    // 弹签
    Animated.spring(popY, { toValue: -150, friction: 5, tension: 60, useNativeDriver: true }).start();

    // 老虎机滚动后定格
    const actual = Number(result.facts['qian']?.['number'] ?? 1);
    const rollTimer = setInterval(() => {
      setRollNumber(1 + Math.floor(Math.random() * signTotal));
    }, 70);
    await sleep(ROLL_MS);
    clearInterval(rollTimer);
    setRollNumber(actual);
    Animated.spring(revealScale, { toValue: 1, friction: 6, tension: 80, useNativeDriver: true }).start();
  }, [phase, mode, setId, calc, signTotal, stopShakeVisual, popY, revealScale]);

  const onSaveAi = useCallback(async () => {
    if (seedUsed === null || !preview) return;
    const created = await create.run({ title: `灵签 · 第${preview.facts['qian']?.['number']}签` });
    if (!created) return;
    const ok = await patch.run(created.session_id, { qian: { seed: seedUsed, set_id: setId } });
    if (ok) {
      router.push(`/report/${created.session_id}`);
    }
  }, [seedUsed, preview, create, patch, router, setId]);

  const reset = useCallback(() => {
    setPhase('idle');
    setPreview(null);
    setRollNumber(null);
    setSeedUsed(null);
    setShowTradition(false);
    popY.setValue(0);
    revealScale.setValue(0.6);
  }, [popY, revealScale]);

  const facts = preview?.facts['qian'] ?? {};
  const tradition = preview?.tradition['qian'] ?? {};
  const level = String(facts['level'] ?? '');
  const levelStyle = LEVEL_STYLE[level] ?? { color: colors.textSecondary, cheer: level };
  const err = calc.error ?? create.error ?? patch.error;
  const poem = Array.isArray(facts['poem']) ? (facts['poem'] as string[]) : [];

  return (
    <Screen>
      <PageHeader title="灵签机" back helpTopic="qianji" tone="light" />

      {/* ---------- 街机招牌 ---------- */}
      <View style={styles.marquee}>
        <View style={styles.lampRow}>
          {lamps.map((v, i) => (
            <Animated.View key={i} style={[styles.lamp, { opacity: v }]} />
          ))}
        </View>
        <AppText size="lg" weight="bold" center color="primary" track="wide">
          灵 签 机
        </AppText>
        <AppText size="xs" color="muted" center style={styles.marqueeSub}>
          {mode === 'daily' ? '今日一签 · 每天一支' : '随意一签 · 每次不同'}
        </AppText>
      </View>

      {/* ---------- 选签库 / 选模式：仅待机时占位（摇签与开奖时让位给结果） ---------- */}
      {phase === 'idle' ? (
        <View>
          <QianSetPicker
            value={setId}
            onChange={(id) => {
              if (phase === 'idle' && id !== setId) {
                setSetId(id);
                reset();
              }
            }}
          />
          <SegmentedTabs
            items={[
              { key: 'daily', label: '今日一签' },
              { key: 'free', label: '随意一签' },
            ]}
            value={mode}
            onChange={(k) => {
              if (phase === 'idle') {
                setMode(k as DrawMode);
                reset();
              }
            }}
          />
        </View>
      ) : null}

      {/* ---------- 签筒舞台（唯一弹性区） ---------- */}
      {/* overflow 放开：弹出的那支签要越过弹性区上边界，被裁掉就看不到"出签"了 */}
      <FitSlot weight={1} center style={styles.stageSlot}>
        <View style={styles.stage}>
          <View style={styles.sticksArea}>
            {sticks.map((s) => (
              <View
                key={s.id}
                style={[
                  styles.stick,
                  { transform: [{ translateX: s.dx }, { translateY: s.dy }, { rotate: s.rot }] },
                ]}
              />
            ))}
            {/* 弹出的那支签 */}
            {phase === 'revealing' ? (
              <Animated.View style={[styles.popStick, { transform: [{ translateY: popY }] }]}>
                <AppText size="md" weight="bold" center color="primary">
                  {rollNumber ?? '·'}
                </AppText>
              </Animated.View>
            ) : null}
          </View>
          <View style={styles.tube}>
            <View style={styles.tubeRim} />
            <AppText size="lg" weight="bold" center style={styles.tubeText}>
              签
            </AppText>
          </View>
        </View>
      </FitSlot>

      {/* ---------- 大按钮：常驻（见文件头 ⚠️） ---------- */}
      <Pressable
        onPressIn={onPressIn}
        onPressOut={onPressOut}
        disabled={phase !== 'idle'}
        accessibilityRole="button"
        accessibilityLabel="按住摇签，松手出签"
        style={({ pressed }) => [
          phase === 'idle' ? styles.bigButton : styles.bigButtonBusy,
          pressed && phase === 'idle' && styles.bigButtonPressed,
        ]}
      >
        {phase === 'idle' ? (
          <>
            <AppText size="lg" weight="bold" center style={styles.bigButtonText}>
              按住摇签
            </AppText>
            <AppText size="xs" center style={styles.bigButtonSub}>
              松手出签
            </AppText>
          </>
        ) : (
          <AppText size="md" weight="semibold" center color="textSecondary">
            {phase === 'shaking' ? '摇签中…' : '开奖！'}
          </AppText>
        )}
      </Pressable>

      {err ? (
        <Banner tone="error" title="请求失败">
          {err}
        </Banner>
      ) : null}

      {/* ---------- 开奖摘要（签文与解签收进弹层） ---------- */}
      {phase === 'revealing' && preview ? (
        <Card title={levelStyle.cheer}>
          <AppText size="lg" weight="bold" center style={[styles.levelText, { color: levelStyle.color }]}>
            第 {rollNumber} 签 · {level}
          </AppText>
          <AppText size="md" weight="semibold" center color="primary" numberOfLines={1}>
            {String(facts['title'] ?? '')}
          </AppText>
        </Card>
      ) : null}

      {phase === 'revealing' && preview ? (
        <>
          <Button
            label="看签文与解签"
            variant="secondary"
            icon={<Ionicons name="book-outline" size={18} color={colors.primary} />}
            onPress={() => setShowTradition(true)}
          />
          <Button
            label="保存并 AI 解签"
            icon={<Ionicons name="sparkles" size={18} color={colors.onPrimary} />}
            loading={create.loading || patch.loading}
            onPress={onSaveAi}
          />
          {mode === 'daily' ? (
            <AppText size="xs" color="muted" center style={styles.dailyNote}>
              今日一签已摇出 —— 同一种子永远同一支签，明天再来
            </AppText>
          ) : (
            <Button label="再来一签" variant="ghost" onPress={reset} />
          )}
        </>
      ) : null}

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        签文解签属传统文化娱乐参考
      </AppText>

      {/* ---------- 签文与解签（长内容收进弹层） ---------- */}
      <InfoPopup
        visible={showTradition}
        onClose={() => setShowTradition(false)}
        title="签文与解签"
        subtitle={rollNumber === null ? '' : `第 ${rollNumber} 签 · ${level}`}
      >
        {poem.map((line, i) => (
          <AppText key={i} size="md" center style={styles.poemLine}>
            {line}
          </AppText>
        ))}
        <KeyValueRow
          label="种子"
          value={seedUsed === null ? '' : `${seedUsed}${mode === 'daily' ? '（今日一签，可复现）' : ''}`}
        />
        <KeyValueRow label="签库" value={String(facts['set_name'] ?? '')} last />
        {String(tradition['source_note'] ?? '') ? (
          <AppText size="xs" color="muted" style={styles.sourceNote}>
            {String(tradition['source_note'])}
          </AppText>
        ) : null}
        <AppText size="sm" style={styles.interp}>
          {String(tradition['interpretation'] ?? '暂无')}
        </AppText>
        <AppText size="sm" color="textSecondary" style={styles.advice}>
          建议：{String(tradition['advice'] ?? '暂无')}
        </AppText>
      </InfoPopup>
    </Screen>
  );
}

const TUBE_W = 120;

const styles = StyleSheet.create({
  marquee: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: space[2],
  },
  lampRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: space[2],
    marginBottom: space[1],
  },
  lamp: { width: 8, height: 8, borderRadius: 4, backgroundColor: '#E0A92E' },
  marqueeSub: { marginTop: 1 },
  stageSlot: { overflow: 'visible' },
  stage: { alignItems: 'center' },
  sticksArea: {
    width: TUBE_W + 90,
    height: 120,
    alignItems: 'center',
    justifyContent: 'flex-end',
    flexDirection: 'row',
  },
  stick: {
    position: 'absolute',
    bottom: 6,
    width: 9,
    height: 96,
    borderRadius: 4,
    backgroundColor: '#E8DCC3',
    borderWidth: 1,
    borderColor: '#C9B98F',
  },
  popStick: {
    position: 'absolute',
    bottom: 100,
    width: 34,
    height: 60,
    borderRadius: 6,
    backgroundColor: '#F5EDD8',
    borderWidth: 2,
    borderColor: '#C9A227',
    alignItems: 'center',
    justifyContent: 'center',
  },
  tube: {
    width: TUBE_W,
    height: 130,
    borderRadius: 14,
    backgroundColor: '#7A4A21',
    borderWidth: 2,
    borderColor: '#5A3517',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -8,
  },
  tubeRim: {
    position: 'absolute',
    top: -8,
    width: TUBE_W - 16,
    height: 16,
    borderRadius: 8,
    backgroundColor: '#8F5A2B',
    borderWidth: 2,
    borderColor: '#5A3517',
  },
  tubeText: { color: '#F5EDD8', fontSize: 40 },
  bigButton: {
    marginTop: space[2],
    backgroundColor: '#C0392B',
    borderRadius: 999,
    paddingVertical: space[3],
    borderBottomWidth: 6,
    borderBottomColor: '#7E241A',
  },
  bigButtonPressed: { transform: [{ scale: 0.96 }], borderBottomWidth: 2 },
  bigButtonBusy: {
    marginTop: space[2],
    borderRadius: 999,
    paddingVertical: space[3],
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bigButtonText: { color: '#FFFFFF' },
  bigButtonSub: { color: '#F5CBA7', marginTop: 2 },
  levelText: { marginBottom: space[2], letterSpacing: 2 },
  poemLine: { lineHeight: 28 },
  interp: { lineHeight: 22 },
  advice: { lineHeight: 22, marginTop: space[2] },
  dailyNote: { marginTop: space[2] },
  sourceNote: { lineHeight: 18 },
  disclaimer: { marginTop: space[1] },
});
