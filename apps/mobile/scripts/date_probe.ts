/**
 * 本地日期探针 —— 把 `src/lib/date.ts` 的**真实输出**导成 JSON，供
 * `tests/mobile/test_local_date.py` 校验。
 *
 * ## 为什么必须真跑，而不是扫源码
 *
 * 扫源码只能证明"文件里没出现 `toISOString`"，证明不了"凌晨 0:30 算出来还是今天"。
 * 而后者正是这个模块存在的**全部理由**。所以这里真调它，把结果交给 pytest。
 *
 * ## 为什么连"错误写法"一起导出
 *
 * 陷阱是否真的存在，**取决于运行时区**：在 UTC 或西半球，
 * `toISOString().slice(0,10)` 并不会退到前一天，这个 bug 也就测不出来 ——
 * 测试会变成一句永远为真的空话（假绿）。
 *
 * 所以本探针同时导出两种写法的结果，让 pytest 能断言
 * **"本环境下错误写法确实会算错"**。若某天这个前提不成立了，
 * 测试会明确失败并提示"当前时区无法验证该陷阱"，而不是悄悄放过。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   TZ=Asia/Shanghai node --experimental-strip-types apps/mobile/scripts/date_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除。
 */

import {
  SHICHEN,
  fromISODate,
  hourOfShichen,
  isToday,
  momentOf,
  rangeFrom,
  shichenOfHour,
  shichenRangeLabel,
  shiftDays,
  todayISODate,
  toISODate,
  weekdayLabel,
} from '../src/lib/date.ts';

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

// ==========================================================================
// 1. 时区自检 —— 陷阱能否复现的前提
// ==========================================================================

const now = new Date();
const tz_offset_minutes = -now.getTimezoneOffset(); // UTC+8 → 480
const tz_name = Intl.DateTimeFormat().resolvedOptions().timeZone;

// ==========================================================================
// 2. 凌晨时刻：lib 的写法 vs toISOString 的写法
// ==========================================================================

/**
 * 逐条列出"本地某时刻"的两种算法结果。
 *
 * 选取的锚点是**凌晨 0:00–8:00**（东八区下这段时间的 UTC 表示还在前一天），
 * 以及 23:xx（西半球/跨年边界才出问题，这里一并留样）。
 */
function probeAt(y: number, mo: number, d: number, h: number, mi: number) {
  const dt = new Date(y, mo - 1, d, h, mi);
  const expected = `${y}-${pad2(mo)}-${pad2(d)}`;
  return {
    label: `${expected} ${pad2(h)}:${pad2(mi)}`,
    expected,
    via_lib: toISODate(dt),
    via_toisostring: dt.toISOString().slice(0, 10),
  };
}

const midnight_cases = [
  probeAt(2026, 9, 17, 0, 0),
  probeAt(2026, 9, 17, 0, 30),
  probeAt(2026, 9, 17, 7, 59),
  probeAt(2026, 9, 17, 8, 0), // 8:00 之后 UTC 落到当天 —— 边界另一侧
  probeAt(2026, 9, 17, 12, 0),
  probeAt(2026, 9, 17, 23, 30),
  probeAt(2026, 1, 1, 1, 0), // 跨年
  probeAt(2026, 12, 31, 23, 0),
];

// ==========================================================================
// 3. 解析往返：`YYYY-MM-DD` → Date → `YYYY-MM-DD` 必须回到自身
// ==========================================================================

const roundtrip_dates = [
  '2026-01-01', '2026-02-28', '2026-03-01', '2026-06-30',
  '2026-09-17', '2026-12-31', '2024-02-29', '2000-02-29', '1999-12-31',
];

const roundtrip = roundtrip_dates.map((iso) => {
  const back = toISODate(fromISODate(iso));
  return {
    iso,
    back,
    ok: back === iso,
    // 顺带记下按 UTC 解析会得到什么（`new Date(iso).getDate()` 的陷阱）
    naive_getdate: new Date(iso).getDate(),
  };
});

// ==========================================================================
// 4. 跨月 / 跨年 / 闰年位移
// ==========================================================================

const shifts = [
  { iso: '2026-09-17', days: 1, expected: '2026-09-18' },
  { iso: '2026-09-17', days: -1, expected: '2026-09-16' },
  { iso: '2026-09-30', days: 1, expected: '2026-10-01' },
  { iso: '2026-01-01', days: -1, expected: '2025-12-31' },
  { iso: '2026-12-31', days: 1, expected: '2027-01-01' },
  { iso: '2024-02-28', days: 1, expected: '2024-02-29' }, // 闰年
  { iso: '2026-02-28', days: 1, expected: '2026-03-01' }, // 平年
  { iso: '2024-02-29', days: 1, expected: '2024-03-01' },
  { iso: '2026-09-17', days: 0, expected: '2026-09-17' },
  { iso: '2026-09-17', days: 60, expected: '2026-11-16' },
].map((c) => ({ ...c, got: shiftDays(c.iso, c.days) }));

// ==========================================================================
// 5. 星期
// ==========================================================================

const weekdays = [
  '2026-09-14', '2026-09-15', '2026-09-16', '2026-09-17',
  '2026-09-18', '2026-09-19', '2026-09-20',
].map((iso) => ({ iso, label: weekdayLabel(iso) }));

// ==========================================================================
// 6. 区间 + 今天 + 守卫（非法输入必须抛，不得静默顺延）
// ==========================================================================

const range_30 = rangeFrom('2026-09-17', 30);
const range_0 = rangeFrom('2026-09-17', 0);

/** 收下一个调用：记录它是否抛错、抛的什么、返回了什么 */
function guard<T>(fn: () => T): { threw: boolean; error: string | null; value: T | null } {
  try {
    return { threw: false, error: null, value: fn() };
  } catch (e) {
    return { threw: true, error: e instanceof Error ? e.name : 'Unknown', value: null };
  }
}

const guards = {
  // 形状不对 → 必须抛（否则会算出一个"看着像日期"的东西）
  bad_shape: guard(() => fromISODate('2026/09/17')),
  short_shape: guard(() => fromISODate('2026-9-17')),
  empty: guard(() => fromISODate('')),
  // 不存在的日期 → 必须抛，不能被 Date 静默顺延成 3 月 2 日
  nonexistent: guard(() => fromISODate('2026-02-30')),
  nonexistent_31: guard(() => fromISODate('2026-04-31')),
  // 合法输入 → 不该抛
  valid: guard(() => fromISODate('2026-02-28')),
  // Invalid Date 不得被 toISODate 悄悄接受
  invalid_date: guard(() => toISODate(new Date('nonsense'))),
};

// ==========================================================================
// 7. 时辰（十二时辰）—— 奇门以时辰起局，映射错了整个盘就错了
// ==========================================================================

/**
 * 逐小时导出「该小时属于哪个时辰」，以及双向换算的往返结果。
 *
 * 这里刻意把**每个小时**都过一遍而不是抽样：子时的边界（23 与 0）
 * 与其余时辰的公式不同，抽样很容易漏掉 h=0 或 h=23 那两条。
 */
const shichen = {
  names: SHICHEN,
  /** 时辰索引 -> 代表小时 / 区间说明 */
  index_to_hour: SHICHEN.map((name, i) => ({
    index: i,
    name,
    hour: hourOfShichen(i),
    range: shichenRangeLabel(i),
    /** 往返：代表小时再换算回时辰索引，必须回到自身 */
    roundtrip: shichenOfHour(hourOfShichen(i)),
  })),
  /** 每小时 -> 时辰索引 */
  hour_to_index: Array.from({ length: 24 }, (_, h) => ({
    hour: h,
    index: shichenOfHour(h),
    name: SHICHEN[shichenOfHour(h)],
    /** 该小时是否就是所属时辰的代表小时 */
    is_representative: hourOfShichen(shichenOfHour(h)) === h,
  })),
  /** 时刻串样例（后端要的形式） */
  moments: [
    { date: '2026-09-17', shichen: 0, moment: momentOf('2026-09-17', 0) },
    { date: '2026-09-17', shichen: 6, moment: momentOf('2026-09-17', 6) },
    { date: '2026-09-17', shichen: 11, moment: momentOf('2026-09-17', 11) },
  ],
  /** 越界输入必须抛，不得静默取模 */
  guards: {
    shichen_negative: guard(() => hourOfShichen(-1)),
    shichen_too_big: guard(() => hourOfShichen(12)),
    shichen_fraction: guard(() => hourOfShichen(1.5)),
    hour_negative: guard(() => shichenOfHour(-1)),
    hour_too_big: guard(() => shichenOfHour(24)),
    hour_fraction: guard(() => shichenOfHour(3.5)),
    bad_date: guard(() => momentOf('2026-02-30', 0)),
    bad_date_shape: guard(() => momentOf('2026/09/17', 0)),
  },
};

const report = {
  tz_offset_minutes,
  tz_name,
  midnight_cases,
  roundtrip,
  shifts,
  weekdays,
  range_30,
  range_0,
  today: todayISODate(),
  is_today_self: isToday(todayISODate()),
  is_today_other: isToday('1999-01-01'),
  guards,
  shichen,
};

process.stdout.write(JSON.stringify(report));
