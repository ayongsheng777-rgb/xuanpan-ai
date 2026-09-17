/**
 * 本地日期工具 —— 「用户看到的那一天」与「字符串里的那一天」之间的唯一转换点。
 *
 * ## 为什么必须有这个模块
 *
 * 黄历、择日、补录起卦日都以 `YYYY-MM-DD` 与后端交互，而 JS 的日期有两个陷阱：
 *
 * 1. **`toISOString()` 会先把本地时间转成 UTC**。东八区凌晨 0:00–8:00 构造的
 *    `Date`，其 UTC 表示还在**前一天** ——
 *    `new Date(2026, 8, 17, 0, 30).toISOString().slice(0, 10)` 得到的是
 *    **`'2026-09-16'`**（本机已实测复现）。
 *    用户明明点的是「今天」，查到的是昨天的黄历，而**页面不会有任何异常迹象** ——
 *    这类错误的危险正在于此：结果看起来完全正常。
 * 2. **`new Date('2026-09-17')` 按 UTC 解析**。ISO 日期串只带日期部分时，
 *    JS 规范规定按 UTC 处理，于是 `getDate()` 在 UTC+8 又退成 16 号。
 *    故反向解析必须用分量构造，不能用字符串构造。
 *
 * 正确做法是**全程按本地分量手工拼装**，不经过任何 UTC 转换。本模块就是那个
 * 唯一实现点 —— 散落在各页面里，迟早会有一处写成 `toISOString()`，
 * 而它只在凌晨八小时内出错，几乎不可能被测出来。
 *
 * 为什么这算「计算」而非「界面细节」：日期归属是**确定性事实**，
 * 不该由每一处界面各自发挥（RULE-001 的同一精神）。
 *
 * 回归守卫：`tests/mobile/test_local_date.py` 会在 `TZ=Asia/Shanghai` 下
 * 真实执行本文件，钉住"凌晨不倒退一天"。改动本文件时务必跑它。
 */

/** 星期名 —— 索引与 `Date.getDay()` 一致（0 = 周日） */
export const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'] as const;

/** `YYYY-MM-DD` 的严格形状；不匹配即视为编程错误，直接抛 */
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** 两位补零 */
function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

/**
 * 本地 `Date` → `YYYY-MM-DD`。
 *
 * **不使用 `toISOString()`**，理由见文件头。用 `getFullYear/getMonth/getDate`
 * 这些本地分量方法直接拼装，任何时区下都得到「用户表盘上的那一天」。
 */
export function toISODate(d: Date): string {
  if (Number.isNaN(d.getTime())) {
    throw new RangeError('toISODate 收到了 Invalid Date —— 上游构造日期时出错了');
  }
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/**
 * `YYYY-MM-DD` → 本地 `Date`（当天 00:00）。
 *
 * **不使用 `new Date(iso)`** —— 那条路径按 UTC 解析，在 UTC+8 会退一天。
 * 这里用分量构造 `new Date(y, m - 1, d)`，得到的是本地零点。
 */
export function fromISODate(iso: string): Date {
  if (!ISO_DATE.test(iso)) {
    throw new RangeError(`fromISODate 需要 YYYY-MM-DD 形状的日期串，收到 "${iso}"`);
  }
  const parts = iso.split('-').map((x) => Number(x));
  const [y, m, d] = [parts[0]!, parts[1]!, parts[2]!];
  const out = new Date(y, m - 1, d);
  // 分量构造会把非法日期"顺延"（如 2 月 30 日 → 3 月 2 日）而不是报错。
  // 静默顺延等于接受了一个不存在的日期，故回读核对。
  if (out.getFullYear() !== y || out.getMonth() !== m - 1 || out.getDate() !== d) {
    throw new RangeError(`fromISODate 收到不存在的日期："${iso}"`);
  }
  return out;
}

/** 在 `YYYY-MM-DD` 上加减天数，返回新的 `YYYY-MM-DD`（跨月/跨年/闰年交给 Date 处理） */
export function shiftDays(iso: string, days: number): string {
  const d = fromISODate(iso);
  d.setDate(d.getDate() + days);
  return toISODate(d);
}

/** 今天的本地日期 `YYYY-MM-DD` */
export function todayISODate(): string {
  return toISODate(new Date());
}

/** 星期几（`周日` … `周六`） */
export function weekdayLabel(iso: string): string {
  const day = WEEKDAYS[fromISODate(iso).getDay()];
  if (day === undefined) {
    // 不可达：getDay() 的值域恒为 0..6，而 WEEKDAYS 正好 7 项。
    // 真走到这里说明 WEEKDAYS 被改短了 —— 宁可抛，也不要静默返回空串
    // 让界面上那一格无声地空掉。
    throw new RangeError('WEEKDAYS 的项数与 Date.getDay() 的值域（0..6）不符');
  }
  return day;
}

/**
 * `YYYY-MM-DD` 是否是今天。
 *
 * 供「今天」这类快捷按钮的高亮态使用 —— 高亮判据必须与取日期的口径同源，
 * 否则会出现"按钮看着是选中的、查的却是昨天"。
 */
export function isToday(iso: string): boolean {
  return iso === todayISODate();
}

/** 以某天为锚的区间：`from` 起 `days` 天（含首日），返回 `[start, end]` 两个日期串。
 *
 * 单独给函数而不是让调用方连写两次 `shiftDays(今天, n)`：那会**取两次"今天"**，
 * 午夜前后分别调用就可能得到跨天的一对区间（start 属旧日、end 属新日）。
 * 这里只在入口取一次锚点，保证区间两端同源。
 */
export function rangeFrom(anchor: string, days: number): [string, string] {
  return [anchor, shiftDays(anchor, days)];
}
