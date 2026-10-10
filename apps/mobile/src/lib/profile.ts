/**
 * 用户信息与每日打卡的本地存储。
 *
 * 存手机本地（AsyncStorage），不上服务端 —— 出生日期这类个人信息
 * 没必要离开设备；每日运程的计算本来就只需要把出生日期发给**你自己的后端**。
 *
 * 键名带版本号（`xuanpan.profile.v1`）：将来字段结构变化时，
 * 旧版本数据可被识别并迁移，而不是静默读出一份半残的对象。
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import { shiftDays } from './date';

export type Gender = 'male' | 'female' | 'unknown';

export interface UserProfile {
  /** 昵称（可空，只用于界面称呼） */
  nickname: string;
  gender: Gender;
  /** 出生公历日期 YYYY-MM-DD —— 每日运程只用它定日主 */
  birthDate: string;
  /** 出生小时 0..23；null = 未知（服务端按午时排盘，不影响日主） */
  birthHour: number | null;
  updatedAt: string;
}

const PROFILE_KEY = 'xuanpan.profile.v1';
const CHECKIN_KEY = 'xuanpan.morning.v1';

/** YYYY-MM-DD 形状 + 真实存在（含闰年）的日期 */
export function isValidBirthDate(s: string): boolean {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s.trim());
  if (!m) return false;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (y < 1900 || y > 2100 || mo < 1 || mo > 12 || d < 1 || d > 31) return false;
  const dt = new Date(y, mo - 1, d);
  return dt.getFullYear() === y && dt.getMonth() === mo - 1 && dt.getDate() === d;
}

function sanitize(raw: unknown): UserProfile | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.birthDate !== 'string' || !isValidBirthDate(r.birthDate)) return null;
  const gender: Gender = r.gender === 'male' || r.gender === 'female' ? r.gender : 'unknown';
  const birthHour =
    typeof r.birthHour === 'number' && Number.isInteger(r.birthHour) && r.birthHour >= 0 && r.birthHour <= 23
      ? r.birthHour
      : null;
  return {
    nickname: typeof r.nickname === 'string' ? r.nickname.slice(0, 20) : '',
    gender,
    birthDate: r.birthDate,
    birthHour,
    updatedAt: typeof r.updatedAt === 'string' ? r.updatedAt : new Date().toISOString(),
  };
}

export async function loadProfile(): Promise<UserProfile | null> {
  try {
    const raw = await AsyncStorage.getItem(PROFILE_KEY);
    if (!raw) return null;
    return sanitize(JSON.parse(raw));
  } catch {
    // 读坏了就当没存过 —— 本地缓存不值得让页面崩溃
    return null;
  }
}

export async function saveProfile(p: Omit<UserProfile, 'updatedAt'>): Promise<void> {
  const full: UserProfile = { ...p, updatedAt: new Date().toISOString() };
  await AsyncStorage.setItem(PROFILE_KEY, JSON.stringify(full));
}

export async function clearProfile(): Promise<void> {
  await AsyncStorage.removeItem(PROFILE_KEY);
}

// ============================================================================
// 每日早报打卡：连续天数（街机式的「连续登录奖励」）
// ============================================================================

export interface MorningCheckin {
  /** 上次阅读早报的日期 YYYY-MM-DD（本地时区） */
  lastDate: string | null;
  /** 连续天数 */
  streak: number;
}

export async function loadCheckin(): Promise<MorningCheckin> {
  try {
    const raw = await AsyncStorage.getItem(CHECKIN_KEY);
    if (!raw) return { lastDate: null, streak: 0 };
    const r = JSON.parse(raw) as Partial<MorningCheckin>;
    return {
      lastDate: typeof r.lastDate === 'string' ? r.lastDate : null,
      streak: typeof r.streak === 'number' && r.streak >= 0 ? Math.floor(r.streak) : 0,
    };
  } catch {
    return { lastDate: null, streak: 0 };
  }
}

/**
 * 标记今日已读早报，返回更新后的打卡状态。
 * 规则：昨天读过 → streak+1；否则重计为 1；今天已读过 → 不变。
 */
export async function markMorningRead(today: string): Promise<MorningCheckin> {
  const cur = await loadCheckin();
  let next: MorningCheckin;
  if (cur.lastDate === today) {
    next = cur;
  } else if (cur.lastDate === shiftDays(today, -1)) {
    next = { lastDate: today, streak: cur.streak + 1 };
  } else {
    next = { lastDate: today, streak: 1 };
  }
  await AsyncStorage.setItem(CHECKIN_KEY, JSON.stringify(next));
  return next;
}
