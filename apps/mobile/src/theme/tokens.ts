/**
 * 设计 Token —— 全 App 唯一的色值/字号/间距真源。
 *
 * 五色来源：《产品基线规范》§2，由演示图**逐像素中位数取样**实测提取
 * （`y=120`，圆心 x = 731/768/804/840/877）。不是随手挑的色板。
 *
 * 铁律（对应 RULE-005「规则不散落」）：**组件内禁止出现硬编码色值**，
 * 一律引用本文件。理由与术数规则同源 —— 同一个语义在两处写死，
 * 改一处忘一处就会出现"主色在这里是 #013A6C、在那里是 #01366C"的漂移。
 *
 * 用法：
 *   import { colors, space, type as t } from '@/theme/tokens';
 *   <View style={{ backgroundColor: colors.sand, padding: space[4] }} />
 */

// ==========================================================================
// 色彩
// ==========================================================================

/** 演示图实测五色（品牌色板，勿改） */
export const brand = {
  /** 主色 · 深蓝 —— 主按钮、标题、选中态、导航激活 */
  primary: '#013A6C',
  /** 金 · 辅色 —— 强调描边、勋章、等级、点缀 */
  gold: '#DAB37D',
  /** 米 · 底色 —— 卡片底、分区背景、留白填充 */
  sand: '#E5D7C7',
  /** 墨绿 · 辅色 —— 传统纹样、辅助图形、次强调 */
  jade: '#3C7066',
  /** 朱红 · 强调 —— 印章、吉凶提示、关键警示 */
  cinnabar: '#B93E35',
} as const;

/**
 * 派生中性阶。
 *
 * 为什么派生而不是直接给一堆灰：五色里没有中性色，
 * 而界面的 90% 面积其实是文字、分隔线、卡片底这些"无色"元素。
 * 以 sand(#E5D7C7) 为暖调基准派生，整屏色温才统一（纯灰会显脏）。
 */
export const neutral = {
  /** 页面最底层背景 */
  bg: '#FBF8F3',
  /** 卡片 / 分区背景 */
  surface: '#FFFFFF',
  /** 次级分区（比 sand 更淡） */
  surfaceAlt: '#F5EFE6',
  /** 细边框、分隔线 */
  border: '#E0D5C4',
  /** 禁用态、占位符 */
  muted: '#A79B8A',
  /** 次级文字 */
  textSecondary: '#6B6154',
  /** 主文字（暖黑，直接用纯黑会显生硬） */
  text: '#2C2416',
  /** 反白文字（用于深色底上） */
  onPrimary: '#FFFFFF',
} as const;

/** 语义色 —— 状态与提示 */
export const semantic = {
  success: brand.jade,
  warning: '#A8722B',
  danger: brand.cinnabar,
  /** 信息提示，不用纯蓝以免与主色混淆 */
  info: '#4A6572',
} as const;

export const colors = { ...brand, ...neutral, ...semantic } as const;

/** 半透明层（避免在组件里手写 rgba） */
export const alpha = {
  primarySoft: 'rgba(1, 58, 108, 0.08)',
  primaryBorder: 'rgba(1, 58, 108, 0.20)',
  scrim: 'rgba(44, 36, 22, 0.45)',
  goldSoft: 'rgba(218, 179, 125, 0.18)',
  /** 朱红淡底 —— 罗盘四正山格的底纹 */
  cinnabarSoft: 'rgba(185, 62, 53, 0.10)',
  /** 朱红中底 —— 罗盘上需要比淡底更明确但仍不夺字的一档 */
  cinnabarTint: 'rgba(185, 62, 53, 0.22)',
  /**
   * 墨绿淡底 —— 与 cinnabarSoft 对称。
   *
   * 黄历里「宜」与「忌」是**成对**出现的：一侧有淡底、另一侧只有描边，
   * 视觉上就成了"宜是次要信息、忌才是正经内容"，而语义上两者等价。
   */
  jadeSoft: 'rgba(60, 112, 102, 0.10)',
} as const;

// ==========================================================================
// 间距（8pt 栅格）
// ==========================================================================

export const space = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
  10: 40,
  12: 48,
} as const;

export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
  xl: 20,
  pill: 999,
} as const;

// ==========================================================================
// 字体
// ==========================================================================

export const font = {
  size: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 17,
    xl: 20,
    xxl: 26,
    display: 32,
  },
  weight: {
    regular: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
  },
  /** 行高按字号 ≈1.5 倍给，中文比英文需要更宽的行距 */
  lineHeight: {
    xs: 16,
    sm: 20,
    md: 23,
    lg: 26,
    xl: 30,
    xxl: 36,
    display: 42,
  },
} as const;

// ==========================================================================
// 阴影（iOS shadow* / Android elevation 同时给，保证两端一致）
// ==========================================================================

export const elevation = {
  none: {},
  card: {
    shadowColor: '#2C2416',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 4,
    elevation: 2,
  },
  raised: {
    shadowColor: '#2C2416',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.1,
    shadowRadius: 10,
    elevation: 5,
  },
} as const;

/** 布局常量 */
export const layout = {
  /** 页面横向留白 */
  gutter: space[4],
  /** 底部导航可见高度（不含安全区） */
  tabBarHeight: 58,
  /** 内容最大宽度（平板/横屏时避免一行拉太宽） */
  maxContentWidth: 560,
} as const;

export const theme = {
  brand, neutral, semantic, colors, alpha, space, radius, font, elevation, layout,
} as const;

export type Colors = typeof colors;
export type Space = typeof space;
