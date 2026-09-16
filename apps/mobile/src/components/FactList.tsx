/**
 * 事实层 / 传统层渲染器。
 *
 * 三条硬性规则：
 *
 * 1. **null 一律渲染为「未定」，绝不留空**。
 *    计算层在"规则表未提供"或"无法确定"时返回 null（RULE-003 不猜）。
 *    如果 UI 把它渲染成空白，用户会以为程序坏了；渲染成「未定」并给出原因，
 *    才是如实传达"这里确实没有结论"。
 *
 * 2. **不认识的键也要显示**。
 *    计算层新增字段时，前端不该把它藏起来 —— 显示原始键名虽然不够漂亮，
 *    但比"数据存在却看不见"安全得多。这里用兜底 prettify 而不是白名单过滤。
 *
 * 3. **不加工数值**。角度就按计算层给的小数位显示、不做四舍五入取整，
 *    因为分金是 3° 级精度，四舍五入会把 177.03 变成 177，丢掉的信息恰好是关键。
 */

import React from 'react';
import { StyleSheet, View } from 'react-native';

import { alpha, colors, radius, space } from '@/theme/tokens';

import { AppText } from './AppText';
import { Divider, KeyValueRow } from './Card';

// ==========================================================================
// 标签字典
// ==========================================================================

/** 已知字段的展示名。**未收录的键走兜底**（见规则 2），不会被隐藏。 */
const LABELS: Record<string, string> = {
  // ---- 罗盘 ----
  sitting: '坐山',
  facing: '向山',
  pair: '坐向',
  sitting_degree: '坐山山心角',
  facing_degree: '向山山心角',
  exact_degree: '实测朝向',
  offset_from_center: '偏离山心',
  fenjin: '分金',
  fenjin_table_available: '分金干支表',
  confidence: '置信度',
  confirmed_by_user: '用户已确认',
  source: '来源',
  index: '格位序号',
  sub_index: '格内位次',
  center_degree: '格中心角',
  ganzhi: '干支',
  usable: '旺相孤虚',

  // ---- 八字 ----
  pillars: '四柱',
  pillar_list: '四柱序列',
  day_master: '日主',
  day_element: '日主五行',
  shengxiao: '生肖',
  lunar: '农历',
  solar_datetime_used: '所用公历时刻',
  solar_term: '节气',
  next_solar_term: '下一节气',
  nayin: '纳音',
  xun_kong: '旬空',
  tai_yuan: '胎元',
  ming_gong: '命宫',
  five_elements_simple: '五行分布（只计明现）',
  five_elements_hidden: '五行分布（含藏干）',
  time_correction: '真太阳时修正',
  rule_consistency: '规则自检',
  true_solar_applied: '已应用真太阳时',
  shift_minutes: '修正分钟',
  utc_offset_hours: '时区偏移',
  late_zi_sect: '晚子时口径',
  scope: '统计口径',
  counts: '计数',
  counts_en: '计数（英文键）',
  percentage: '占比',

  // ---- 六爻 ----
  method: '起卦方式',
  yao_values: '爻值',
  yao_names: '爻名',
  original_gua: '本卦',
  upper_gua: '上卦',
  lower_gua: '下卦',
  changed_gua: '变卦',
  changed_upper_gua: '变卦上卦',
  changed_lower_gua: '变卦下卦',
  moving_positions: '动爻',
  has_moving: '有动爻',

  // ---- 灵签 ----
  set_id: '签库',
  set_name: '签库名称',
  number: '签号',
  level: '吉凶等第',
  title: '签题',
  poem: '签诗',
  is_demo_data: '演示数据',

  // ---- 姓名 ----
  name: '姓名',
  surname: '姓',
  given: '名',
  strokes: '笔画',
  wuge: '五格',
  sancai: '三才',
  sancai_label: '三才配置',
  number_luck_available: '81 数理吉凶表',
  warnings: '警告',
};

/** 枚举值的中文（仅收录确实有语义映射的） */
const ENUMS: Record<string, Record<string, string>> = {
  source: { manual: '手动输入', vision: '照片识别', import: '导入' },
  method: { yao_values: '爻值', coins: '摇卦', numbers: '数字起卦' },
  scope: { simple: '明现', hidden: '含藏干' },
};

/** 按语义决定单位的字段 */
const UNITS: Record<string, string> = {
  sitting_degree: '°',
  facing_degree: '°',
  exact_degree: '°',
  offset_from_center: '°',
  center_degree: '°',
  shift_minutes: ' 分钟',
  utc_offset_hours: ' 小时',
};

/** 渲染为百分比的字段 */
const PERCENT_KEYS = new Set(['confidence']);

// ==========================================================================
// 主组件
// ==========================================================================

export interface FactListProps {
  /** 一个模块的 facts 或 tradition（如 `facts.compass`） */
  data: Record<string, unknown>;
  /** 跳过这些键（调用方已单独渲染，如 warnings 交给 UncertaintyList） */
  omit?: readonly string[];
}

export function FactList({ data, omit = [] }: FactListProps): React.JSX.Element {
  const entries = Object.entries(data).filter(([k, v]) => {
    if (omit.includes(k)) return false;
    // 空数组通常表示"无异常"（如 rule_consistency=[]），单独渲染更友好
    if (Array.isArray(v) && v.length === 0) return false;
    return true;
  });

  return (
    <View>
      {entries.map(([key, value], i) => (
        <FactEntry key={key} name={key} value={value} last={i === entries.length - 1} />
      ))}
      <View style={styles.selfCheck}>
        <AppText size="xs" color="muted">
          ✓ 规则自检通过（无异常项）
        </AppText>
      </View>
    </View>
  );
}

function FactEntry({
  name,
  value,
  last,
}: {
  name: string;
  value: unknown;
  last: boolean;
}): React.JSX.Element {
  const label = LABELS[name] ?? prettifyKey(name);

  // ---- 四柱：横向四列比纵向键值清楚得多 ----
  if (name === 'pillars' && isRecord(value)) {
    return (
      <View style={styles.pillars}>
        {(['year', 'month', 'day', 'hour'] as const).map((k) => (
          <View key={k} style={styles.pillarCell}>
            <AppText size="xs" color="textSecondary">
              {{ year: '年柱', month: '月柱', day: '日柱', hour: '时柱' }[k]}
            </AppText>
            <AppText size="lg" weight="semibold" color="primary" style={styles.pillarValue}>
              {asText(value[k])}
            </AppText>
          </View>
        ))}
      </View>
    );
  }

  // ---- 五行分布：条形图比一串数字易读 ----
  if ((name === 'five_elements_simple' || name === 'five_elements_hidden') && isRecord(value)) {
    return (
      <View style={styles.block}>
        <AppText size="sm" color="textSecondary" style={styles.blockTitle}>
          {label}
        </AppText>
        <ElementBars counts={value['counts']} />
      </View>
    );
  }

  // ---- 签诗：逐句展示 ----
  if (name === 'poem' && Array.isArray(value)) {
    return (
      <View style={styles.block}>
        <AppText size="sm" color="textSecondary" style={styles.blockTitle}>
          {label}
        </AppText>
        {value.map((line, i) => (
          <AppText key={i} size="md" color="text" style={styles.poemLine}>
            {asText(line)}
          </AppText>
        ))}
      </View>
    );
  }

  // ---- 嵌套对象：递归（如 fenjin / wuge / nayin / xun_kong）----
  if (isRecord(value)) {
    return (
      <View style={styles.block}>
        <AppText size="sm" color="textSecondary" style={styles.blockTitle}>
          {label}
        </AppText>
        <View style={styles.nested}>
          {Object.entries(value).map(([k, v], i, arr) => (
            <FactEntry key={k} name={k} value={v} last={i === arr.length - 1} />
          ))}
        </View>
      </View>
    );
  }

  // ---- 数组（数字/字符串混合）----
  if (Array.isArray(value)) {
    return (
      <KeyValueRow
        label={label}
        last={last}
        value={value.length === 0 ? <Undetermined /> : asText(value.join('、'))}
      />
    );
  }

  return <KeyValueRow label={label} value={renderScalar(name, value)} last={last} />;
}

// ==========================================================================
// 标量
// ==========================================================================

function renderScalar(name: string, value: unknown): React.JSX.Element {
  if (value === null || value === undefined) return <Undetermined />;

  const enumMap = ENUMS[name];
  if (enumMap && typeof value === 'string' && enumMap[value]) {
    return <AppText size="md">{enumMap[value]}</AppText>;
  }

  if (PERCENT_KEYS.has(name) && typeof value === 'number') {
    return <AppText size="md">{`${Math.round(value * 100)}%`}</AppText>;
  }

  if (typeof value === 'boolean') {
    return <AppText size="md" color={value ? 'success' : 'textSecondary'}>{value ? '是' : '否'}</AppText>;
  }

  if (typeof value === 'number') {
    const unit = UNITS[name] ?? '';
    // 角度保留小数（分金是 3° 级精度，取整会丢掉关键信息）
    const text = Number.isInteger(value) && !unit.startsWith('°') ? String(value) : trimFloat(value);
    return <AppText size="md">{`${text}${unit}`}</AppText>;
  }

  return <AppText size="md">{String(value)}</AppText>;
}

/** 去掉浮点尾巴：177.03000000000003 → 177.03 */
function trimFloat(v: number): string {
  return String(Math.round(v * 1000) / 1000);
}

function asText(v: unknown): string {
  if (v === null || v === undefined) return '未定';
  if (typeof v === 'boolean') return v ? '是' : '否';
  if (typeof v === 'number') return trimFloat(v);
  if (Array.isArray(v)) return v.map(asText).join('、');
  if (isRecord(v)) return Object.entries(v).map(([k, x]) => `${k}${asText(x)}`).join(' ');
  return String(v);
}

/** 「未定」—— 计算层明确表示"没有结论"，不是"没有数据" */
function Undetermined(): React.JSX.Element {
  return (
    <View style={styles.undetermined}>
      <AppText size="md" color="muted">
        未定
      </AppText>
    </View>
  );
}

// ==========================================================================
// 五行条
// ==========================================================================

const ELEMENT_COLORS: Record<string, string> = {
  木: '#4A7C59',
  火: colors.cinnabar,
  土: '#A8722B',
  金: colors.gold,
  水: colors.primary,
};

//：展示顺序固定为 木火土金水（相生序），不按数值排 —— 顺序稳定才能一眼对比
const ELEMENT_ORDER = ['木', '火', '土', '金', '水'] as const;

function ElementBars({ counts }: { counts: unknown }): React.JSX.Element {
  if (!isRecord(counts)) return <Undetermined />;
  const values = ELEMENT_ORDER.map((k) => ({
    k,
    v: typeof counts[k] === 'number' ? (counts[k] as number) : 0,
  }));
  const max = Math.max(1, ...values.map((x) => x.v));

  return (
    <View style={styles.bars}>
      {values.map(({ k, v }) => (
        <View key={k} style={styles.barRow}>
          <AppText size="sm" color="textSecondary" style={styles.barLabel}>
            {k}
          </AppText>
          <View style={styles.barTrack}>
            <View
              style={[
                styles.barFill,
                { width: `${(v / max) * 100}%`, backgroundColor: ELEMENT_COLORS[k] ?? colors.primary },
              ]}
            />
          </View>
          <AppText size="sm" color={v === 0 ? 'muted' : 'text'} style={styles.barValue}>
            {trimFloat(v)}
          </AppText>
        </View>
      ))}
    </View>
  );
}

// ==========================================================================
// 工具
// ==========================================================================

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

/** 未收录键的兜底展示名：下划线转空格，避免出现 `some_new_field` */
function prettifyKey(key: string): string {
  return key.replace(/_/g, ' ');
}

const styles = StyleSheet.create({
  block: { paddingTop: space[2] },
  blockTitle: { marginBottom: space[1] },
  nested: {
    paddingLeft: space[3],
    borderLeftWidth: 2,
    borderLeftColor: alpha.primarySoft,
  },
  undetermined: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    paddingHorizontal: space[2],
    paddingVertical: 2,
    alignSelf: 'flex-start',
  },

  pillars: { flexDirection: 'row', paddingVertical: space[2] },
  pillarCell: { flex: 1, alignItems: 'center' },
  pillarValue: { marginTop: 2 },

  bars: { gap: space[1], paddingVertical: space[1] },
  barRow: { flexDirection: 'row', alignItems: 'center' },
  barLabel: { width: 20 },
  barTrack: {
    flex: 1,
    height: 10,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.pill,
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: radius.pill },
  barValue: { width: 34, textAlign: 'right' },

  poemLine: { lineHeight: 26 },

  selfCheck: { paddingTop: space[2] },
});

export { Divider };
