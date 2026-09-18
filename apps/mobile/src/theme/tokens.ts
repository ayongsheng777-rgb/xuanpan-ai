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

/** 语义色 —— 状态与提示（只有前景色；底色/描边见下方 `tone`） */
export const semantic = {
  success: brand.jade,
  warning: '#A8722B',
  danger: brand.cinnabar,
  /** 信息提示，不用纯蓝以免与主色混淆 */
  info: '#4A6572',
} as const;

/**
 * 语义色三件套（前景 / 淡底 / 描边）。
 *
 * 为什么必须成组给：`Banner` 原先在组件里手写 4 组 `{bg, border}` 共 8 个色值，
 * 而 `semantic` 里另有 4 个前景色 —— 同一个语义的色值被拆在两个文件里，
 * 改一处忘一处就会出现"警示条描边变了、小圆点没变"，且**没有任何检查会报错**
 * （都是合法色值）。成组后 `tone[danger].fg` 恒等于 `colors.danger`。
 */
export const tone = {
  info: { fg: '#4A6572', bg: '#F1F5F8', border: '#C9D6DE' },
  warning: { fg: '#A8722B', bg: '#FDF7EC', border: '#E8D5AC' },
  danger: { fg: brand.cinnabar, bg: '#FDF4F3', border: '#EFC9C5' },
  success: { fg: brand.jade, bg: '#F2F7F5', border: '#C6DCD5' },
} as const;

export type ToneName = keyof typeof tone;

/**
 * 实底淡色面 —— **不是半透明**（半透明的在 `alpha`）。
 *
 * 用途是小面积状态底：状态药丸、警示卡。与 `tone[].bg` 的区别是它们会被
 * 用在需要"比提示条更实"的地方（药丸压在卡片上，若用半透明会透出卡底色）。
 */
export const tint = {
  /** 警示卡整卡底色（比 tone.danger.bg 更浅，整卡铺开才不会显脏） */
  dangerCard: '#FDF6F5',
  /** 「可用 / 通过」药丸底色 */
  jadePill: '#EAF3EF',
} as const;

/**
 * 五行本色 —— 命盘五行条专用。
 *
 * 归入 token 而不是留在 `FactList` 里的理由：木火土金水是**领域常量**，
 * 和「山名/卦名」同性质 —— 它在任何页面、任何流派里都该是同一个颜色。
 * 留在组件里，下一个要画五行环的页面就会自己再挑一遍色。
 */
export const element = {
  木: '#4A7C59',
  火: brand.cinnabar,
  土: '#A8722B',
  金: brand.gold,
  水: brand.primary,
} as const;

export const colors = { ...brand, ...neutral, ...semantic } as const;

/**
 * 深色仪器色域 —— **仅用于罗盘域页面**（罗盘首页 / 手动调节 / 传感器测量）。
 *
 * 来源：V2 演示图（8 屏）+ V2 规范 §37「深色专业仪器风」。
 * 与既有暖色中性阶**双轨并存**：命盘/占测/历史/我的等页面仍用浅色，
 * 待真机走查两轨效果后由阿勇决定是否全局深色化
 * （见《V2 评估与实施路线》冲突 2 裁决）。
 *
 * 取色原则：深藏青底（仪器感）+ 金（罗盘刻度）+ 朱红（磁针/北向）。
 * 不引入五色之外的新色相，只是把它们放到深色底上重新分配明暗。
 */
export const instrument = {
  /** 页面最底层背景（深藏青） */
  bg: '#0A1626',
  /** 卡片 / 分区背景（比底略亮一档） */
  surface: '#12223A',
  /** 次级分区（输入框、进度槽） */
  surfaceAlt: '#1B3050',
  /** 细边框 */
  border: '#24395C',
  /** 罗盘盘体底色（深墨青，区别于页面底） */
  dialBody: '#0D1B2E',
  /** 罗盘盘体金环/刻度 */
  dialGold: brand.gold,
  /** 磁针红（北向）—— 与五色朱红同源，深底下略提亮 */
  needle: '#E05548',
  /** 主文字 */
  text: '#F2EDE4',
  /** 次级文字 */
  textSecondary: '#9AA8BC',
  /** 弱化 / 占位 */
  muted: '#5C6C84',
  /** 强调金（读数大字、激活态） */
  accent: brand.gold,
  /** 状态：良好（墨绿提亮到深底可读） */
  ok: '#5FB89A',
  /** 状态：警告 */
  warn: '#D9A441',
  /** 状态：异常（朱红提亮） */
  danger: '#E05548',
  /**
   * 盘体径向渐变（由内向外三档）—— **只给深色盘用**，浅色盘不设。
   *
   * 为什么需要它：单色平涂的盘体在深底上是"一整块均匀色块"，
   * 二十四山的分层感只能靠描边硬撑，看上去是平的。径向渐变让中心
   * （天池）自然成为视觉焦点，边缘自然退后 —— 这是仪器类界面的通行做法，
   * 也是它比纯色填充更接近实物盘的原因。
   *
   * 三档取**同一色相的不同明度**（不是三个新颜色），与 `dialBody` 同族，
   * 因此不与五色体系冲突：深色域本来就在做"把五色放到深底上重新分配明暗"。
   */
  dialBodyGradient: ['#16294A', '#0D1B2E', '#08111F'],
  /**
   * 曲线面积填充的顶色 —— 传感器磁场波形用。
   *
   * 与 `accent` 同色，只调透明度：面积是**衬在折线下面的体积感**，
   * 不该比折线本身更抢眼。透明度在组件里给（见 sensors 页），
   * 这里只固定色相，避免"每个用曲线的页面自己挑一个蓝"。
   */
  curveFill: '#DAB37D',
} as const;

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
  /**
   * 金系半透明 —— 罗盘盘面与取景器用。
   *
   * 三档对应三种"金在暗底上的存在感"：`goldRing` 取景对准环（要看清但别抢主体）、
   * `goldDim` 先天八卦层（与后天的亮金分色）、`goldFaint` 角落山格底纹（几乎只是暗示）。
   */
  goldRing: 'rgba(218, 179, 125, 0.55)',
  goldDim: 'rgba(218, 179, 125, 0.62)',
  goldFaint: 'rgba(218, 179, 125, 0.14)',
  /** 磁针红淡底 —— 盘面四正格 */
  needleSoft: 'rgba(224, 85, 72, 0.16)',
  /** 白系半透明 —— 取景器快门内芯 */
  whiteSoft: 'rgba(255, 255, 255, 0.22)',
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
  /** 内嵌小元素（标签、徽标）—— 与外层容器拉开一档，"内紧外松" */
  xs: 4,
  sm: 6,
  md: 10,
  lg: 14,
  xl: 20,
  pill: 999,
} as const;

// ==========================================================================
// 字体
// ==========================================================================

/**
 * 字距阶梯。
 *
 * 中文没有大小写，**层级只能靠"字号 × 字重 × 字距"三件套**——
 * 少一件就会出现"字号变了但看起来还是同一层"。
 * 大字要负字距（否则字与字之间像被撑开），小字标签要正字距（否则挤成一团）。
 */
export const tracking = {
  /** 仪表读数大字：40px 以上必须收紧，否则数字之间漏风 */
  tighter: -0.8,
  tight: -0.4,
  normal: 0,
  /** 分区标题 / 小标签 */
  wide: 0.6,
  /** 全大写拉丁标签或极短的中文标签 */
  wider: 1.2,
} as const;

export const font = {
  size: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 17,
    xl: 20,
    xxl: 26,
    display: 32,
    /**
     * 仪表读数档 —— **一屏只有一个**。
     *
     * 为什么 display(32) 不够：方位角、磁场强度这类读数是页面的主角，
     * 32 与 xxl(26) 只差 1.23 倍，在一张卡片里区分不出"主角/配角"。
     * 40 与 26 差 1.54 倍，才真正拉出层次（原来的写法是让 display 兼职，
     * 结果首页的方位角和各页的大标题是同一个字号，主角感全靠颜色硬撑）。
     */
    metric: 40,
  },
  weight: {
    regular: '400',
    medium: '500',
    semibold: '600',
    bold: '700',
    /**
     * 特粗 —— 只给 `metric` 读数用。
     *
     * 中文字形在 800 档上多数系统字体没有独立字重（会回落到 bold，无副作用）；
     * 但读数主体是**阿拉伯数字与 °**，拉丁字形有真实 800 档，所以这里有实效。
     */
    heavy: '800',
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
    /** 读数不需要 1.5 倍 —— 它就一行，行高过大会在卡片里顶出空档 */
    metric: 46,
  },
} as const;

/**
 * 阴影阶梯（iOS shadow* / Android elevation 同时给，保证两端一致）。
 *
 * 三档对应三种"离页面多远"：静置卡片贴近纸面（范围大、极淡）、
 * 浮起元素离得远（范围更大更散）、按下态**收紧**（范围变小 = 物理下沉）。
 * 阴影色统一带底色暖调（`#2C2416`），不用纯黑 —— 纯黑投在暖白纸上会发脏。
 */
export const elevation = {
  none: {},
  /** 静置卡片：范围给大、透明度压低，看起来是"贴着纸"而不是"描了个边" */
  card: {
    shadowColor: '#2C2416',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 6,
    elevation: 2,
  },
  /** 浮起：弹层、主 CTA、被选中的卡 */
  raised: {
    shadowColor: '#2C2416',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.1,
    shadowRadius: 16,
    elevation: 6,
  },
  /** 按下：阴影收紧，与 `scale` 一起读作"被压下去" */
  pressed: {
    shadowColor: '#2C2416',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.07,
    shadowRadius: 3,
    elevation: 1,
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

/**
 * 交互常量 —— 按压反馈只许从这里取值。
 *
 * 为什么值得单开一节：全仓原先**三种按压写法并存** —— `Button` 用 `opacity 0.86`、
 * 首页「去测盘」用换底色、而「已保存 N 个盘面」这类同样可点的卡片**完全没有反馈**。
 * 同一个手势在不同页面给出不同回应，用户读到的不是"风格差异"，而是"有的地方坏了"。
 */
export const interaction = {
  /**
   * 按下缩放。0.985 是"肉眼几乎看不出、但手指能感到"的档位
   * （缩放会把文字和图标一起带走，这正是它读起来像"实体按钮"的原因）；
   * 再往下调就变成夸张的弹跳，与专业仪器风不符。
   */
  pressedScale: 0.985,
  /** 按下视觉变化的目标时长（ms）。100~150 是"按下即刻有回应"的上界，超了就迟钝 */
  pressDuration: 150,
  /** 最小触达边长。视觉可以更小，但必须用 `hitSlop` 补足 */
  minTouchTarget: 44,
} as const;

export const theme = {
  brand, neutral, semantic, colors, alpha, instrument,
  tone, tint, element, interaction,
  space, radius, font, tracking, elevation, layout,
} as const;

export type Colors = typeof colors;
export type Space = typeof space;
export type TrackName = keyof typeof tracking;
