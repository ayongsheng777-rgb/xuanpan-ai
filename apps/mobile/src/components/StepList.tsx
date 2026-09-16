/**
 * 识别过程步骤列表 —— 对应基线规范 §4.2。
 *
 * **必须展示测量过程，不得显示"AI 正在思考"。**
 *
 * 为什么这不是文案层面的讲究：识别是"几何测量"，用户能理解"检测边界、
 * 定位天池、校正透视"这些可验证的动作；而"AI 正在思考"把不确定性藏起来了 ——
 * 一旦结果不对，用户无从判断是哪一步出了问题，也无法据此改进拍摄。
 * 展示步骤同时给了"重拍"的心理预期：还没轮到的步骤打灰，而不是转圈等待。
 */

import React from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { colors, space } from '@/theme/tokens';

import { AppText } from './AppText';

export type StepState = 'done' | 'active' | 'pending' | 'failed';

export interface Step {
  /** 固定 7 步，见 `SCAN_STEPS` */
  id: string;
  label: string;
  state: StepState;
  /** 失败原因（failed 时必填，直接展示用户可执行的信息） */
  detail?: string;
}

/** 识别管线的固定步骤（顺序与 `xuanpan_vision` 的实际链路一致） */
export const SCAN_STEPS: readonly { id: string; label: string }[] = [
  { id: 'quality', label: '图像质量检测' },
  { id: 'boundary', label: '检测罗盘边界' },
  { id: 'pond', label: '定位天池' },
  { id: 'perspective', label: '校正透视' },
  { id: 'mountains', label: '分析二十四山' },
  { id: 'orientation', label: '判断坐山 / 向山' },
  { id: 'fenjin', label: '计算分金' },
  { id: 'report', label: '生成解读' },
] as const;

/**
 * 把一次识别结果映射到"进行到哪一步 / 卡在哪一步"。
 *
 * 为什么要做这个映射而不是随便推进动画：识别是**一次性服务端处理**，
 * 客户端拿不到中间态。若按定时器自嗨式推进，会出现"显示「分析二十四山 ✓」
 * 但结果显示未识别"的矛盾 —— 那是在编造过程。
 * 这里只根据**服务端真实返回**判断停在哪一步，如实呈现。
 */
export function failureStepOf(qualityPassed: boolean): number {
  // 质检不过 → 第 0 步；质检过了但仍未识别出 → 卡在边界检测
  return qualityPassed ? 1 : 0;
}

/** 由"当前进行到第几步"生成完整步骤状态 */
export function stepsUpTo(activeIndex: number, failedAt?: number, detail?: string): Step[] {
  return SCAN_STEPS.map((s, i) => {
    if (failedAt !== undefined && i === failedAt) {
      return { ...s, state: 'failed' as const, detail };
    }
    if (failedAt !== undefined && i > failedAt) return { ...s, state: 'pending' as const };
    if (i < activeIndex) return { ...s, state: 'done' as const };
    if (i === activeIndex) return { ...s, state: 'active' as const };
    return { ...s, state: 'pending' as const };
  });
}

const MARK: Record<StepState, { glyph: string; color: string }> = {
  done: { glyph: '✓', color: colors.success },
  active: { glyph: '●', color: colors.primary },
  pending: { glyph: '○', color: colors.muted },
  failed: { glyph: '✕', color: colors.danger },
};

export function StepList({ steps }: { steps: readonly Step[] }): React.JSX.Element {
  return (
    <View style={styles.wrap}>
      {steps.map((s) => {
        const m = MARK[s.state];
        const dim = s.state === 'pending';
        return (
          <View key={s.id} style={styles.row}>
            <View style={styles.marker}>
              {s.state === 'active' ? (
                <ActivityIndicator size="small" color={colors.primary} />
              ) : (
                <AppText size="sm" color={m.color} weight="semibold">
                  {m.glyph}
                </AppText>
              )}
            </View>
            <View style={styles.textCol}>
              <AppText size="sm" color={dim ? 'muted' : 'text'} weight={s.state === 'active' ? 'semibold' : 'regular'}>
                {s.label}
              </AppText>
              {s.detail ? (
                <AppText size="xs" color="danger" style={styles.detail}>
                  {s.detail}
                </AppText>
              ) : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: space[2], paddingVertical: space[1] },
  row: { flexDirection: 'row', alignItems: 'center' },
  marker: { width: 24, alignItems: 'center', justifyContent: 'center' },
  textCol: { flex: 1, marginLeft: space[2] },
  detail: { marginTop: 2 },
});
