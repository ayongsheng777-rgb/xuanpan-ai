/**
 * 我的信息 —— 每日运程用的个人信息设置。
 *
 * 只存四样：昵称、性别、出生日期、出生时辰。全部落在**手机本地**
 * （AsyncStorage），不上服务端 —— 出生日期没必要离开设备。
 *
 * 每日运程只用到「出生日期」定日主；时辰不影响日主，未知可留空。
 * 性别目前仅作展示与将来扩展用，不参与任何计算（避免无依据的性别推断）。
 *
 * ## 单屏做法（2026-10-09）
 *
 * 表单本身就是一屏内容，不再滚动：标题栏 `PageHeader`（带返回 + 问号）+
 * 唯一的弹性区 `FitSlot weight={1}` 承载表单卡，底部按钮固定。
 */

import { useRouter } from 'expo-router';
import React, { useCallback, useEffect, useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';

import { AppText } from '@/components/AppText';
import { Banner } from '@/components/Banner';
import { Button, Card } from '@/components/Card';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import {
  Gender,
  clearProfile,
  isValidBirthDate,
  loadProfile,
  saveProfile,
} from '@/lib/profile';
import { useAsync, useSubmit } from '@/lib/useAsync';
import { colors, radius, space } from '@/theme/tokens';

const GENDER_ITEMS = [
  { key: 'unknown', label: '不填' },
  { key: 'male', label: '男' },
  { key: 'female', label: '女' },
] as const;

export default function ProfileScreen(): React.JSX.Element {
  const router = useRouter();
  const [nickname, setNickname] = useState('');
  const [gender, setGender] = useState<Gender>('unknown');
  const [year, setYear] = useState('');
  const [month, setMonth] = useState('');
  const [day, setDay] = useState('');
  const [hour, setHour] = useState('');
  const [savedTick, setSavedTick] = useState(0);

  const load = useCallback(async () => loadProfile(), []);
  const { data: existing, loading } = useAsync(load, []);

  // 读到已存信息 → 回填表单
  useEffect(() => {
    if (!existing) return;
    setNickname(existing.nickname);
    setGender(existing.gender);
    const [y, m, d] = existing.birthDate.split('-');
    setYear(y ?? '');
    setMonth(m ?? '');
    setDay(d ?? '');
    setHour(existing.birthHour === null ? '' : String(existing.birthHour));
  }, [existing]);

  const saver = useSubmit(async () => {
    const birthDate = `${year.padStart(4, '0')}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
    if (!isValidBirthDate(birthDate)) {
      throw new Error('出生日期不正确，请检查年月日（注意闰年与每月天数）');
    }
    let birthHour: number | null = null;
    if (hour.trim() !== '') {
      const h = Number(hour);
      if (!Number.isInteger(h) || h < 0 || h > 23) {
        throw new Error('出生时辰填 0–23 的整数，填的是几点就写几；不知道就留空');
      }
      birthHour = h;
    }
    await saveProfile({ nickname: nickname.trim(), gender, birthDate, birthHour });
    setSavedTick((t) => t + 1);
  });

  const clearer = useSubmit(async () => {
    await clearProfile();
    setNickname('');
    setGender('unknown');
    setYear('');
    setMonth('');
    setDay('');
    setHour('');
    setSavedTick((t) => t + 1);
  });

  return (
    <Screen>
      <PageHeader title="我的信息" back helpTopic="profile" tone="light" />

      {/* 唯一弹性区：表单卡，高度自适应屏幕 */}
      <FitSlot weight={1}>
        <Card title="基本信息">
          <AppText size="xs" color="muted" style={styles.note}>
            只存手机本地，不上传。每日运程用「出生日期」排出你的日主，再看当天的干支；时辰不影响日主，不知道可以留空。
          </AppText>

          <AppText size="sm" color="textSecondary" style={styles.label}>
            昵称（可空，早报里会这样叫你）
          </AppText>
          <TextInput
            value={nickname}
            onChangeText={setNickname}
            placeholder="比如：阿勇"
            placeholderTextColor={colors.muted}
            maxLength={20}
            style={styles.input}
          />

          <AppText size="sm" color="textSecondary" style={styles.label}>
            性别（可不填，目前只做展示）
          </AppText>
          <SegmentedTabs
            items={GENDER_ITEMS.map((g) => ({ key: g.key, label: g.label }))}
            value={gender}
            onChange={(k) => setGender(k as Gender)}
          />

          <AppText size="sm" color="textSecondary" style={styles.label}>
            出生日期（公历）*
          </AppText>
          <View style={styles.dateRow}>
            <TextInput
              value={year}
              onChangeText={setYear}
              keyboardType="number-pad"
              placeholder="年"
              placeholderTextColor={colors.muted}
              maxLength={4}
              style={[styles.input, styles.dateCell]}
            />
            <TextInput
              value={month}
              onChangeText={setMonth}
              keyboardType="number-pad"
              placeholder="月"
              placeholderTextColor={colors.muted}
              maxLength={2}
              style={[styles.input, styles.dateCell]}
            />
            <TextInput
              value={day}
              onChangeText={setDay}
              keyboardType="number-pad"
              placeholder="日"
              placeholderTextColor={colors.muted}
              maxLength={2}
              style={[styles.input, styles.dateCell]}
            />
          </View>

          <AppText size="sm" color="textSecondary" style={styles.label}>
            出生时辰（可空，填 0–23）
          </AppText>
          <TextInput
            value={hour}
            onChangeText={setHour}
            keyboardType="number-pad"
            placeholder="不知道就留空"
            placeholderTextColor={colors.muted}
            maxLength={2}
            style={styles.input}
          />
        </Card>
      </FitSlot>

      {saver.error ? (
        <Banner tone="error" title="没保存">
          {saver.error}
        </Banner>
      ) : null}
      {savedTick > 0 && !saver.error ? (
        <Banner tone="success" title="已保存">
          信息只在你的手机上，去「每日早报」看看今天的运程吧。
        </Banner>
      ) : null}

      <Button
        label={loading ? '读取中…' : '保存'}
        loading={saver.loading}
        onPress={() => saver.run()}
        style={styles.saveBtn}
      />
      <Button label="去看每日早报" variant="secondary" onPress={() => router.push('/morning')} />
      <Button
        label="清除本地信息"
        variant="ghost"
        loading={clearer.loading}
        onPress={() => clearer.run()}
        style={styles.clearBtn}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  note: { marginBottom: space[2], lineHeight: 18 },
  label: { marginTop: space[3], marginBottom: space[1] },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: space[3],
    paddingVertical: space[2],
    fontSize: 16,
    color: colors.text,
    backgroundColor: colors.surface,
  },
  dateRow: { flexDirection: 'row', gap: space[2] },
  dateCell: { flex: 1, textAlign: 'center' },
  saveBtn: { marginTop: space[3] },
  clearBtn: { marginTop: space[2] },
});
