/**
 * 三式排盘 —— 奇门遁甲 / 大六壬 / 太乙神数。
 *
 * 三式放同一页用分段控件切换：它们是**同一类东西**（以干支历法起局的盘），
 * 用户常常三式互参。做成三个入口会逼用户在三个页面之间来回跳，
 * 而它们共享全部上下文（起局时刻）。
 *
 * **本页不做任何吉凶判断**：盘面全部由服务端确定性内核算出，这里只负责
 * 如实呈现，并把 `uncertainties`（流派差异、本版未覆盖项）一并显示。
 * 对应 RULE-001 / RULE-005 —— 界面不藏规则，也不自造规则。
 *
 * 一个刻意的设计：**界面绝不"顺手"把宫位吉凶解读成结论**。
 * 八门/九星的吉凶是门、星**固有的传统属性**，与"你问的这件事怎么样"
 * 是两回事，故只作属性标注，不参与任何吉凶结论的呈现。
 *
 * ## 单屏（2026-10-09 用户要求：一屏显示完、不滑动）
 *
 * 三式用**页面分段标签**切换 —— 同一时刻只渲染一式（这正是它一屏放得下的
 * 前提：三张盘各自都放不下，更不用说堆在一页）。
 * 每式只保留**盘面**作为弹性区（九宫盘 / 十二宫方图 / 八宫盘）；
 * 起局时刻选择器压成"日期步进 + 十二时辰"两行；
 * 定局、值符值使、四课三传、三目三算、各张领域表（局数/月将/宫号）
 * 与不确定性一律收进 `InfoPopup` 点开看 —— 页内高度与数据条数无关。
 * 数据一字不改。
 */

import React, { useCallback, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { getApiClient } from '@/api/client';
import type {
  LiurenChart,
  LiurenMetaResponse,
  LiurenPalace,
  QimenChart,
  QimenMetaResponse,
  QimenPalace,
  TaiyiBamenLayout,
  TaiyiChart,
  TaiyiMetaResponse,
} from '@/api/types';
import { AppText } from '@/components/AppText';
import { Banner, UncertaintyList } from '@/components/Banner';
import { Button, Card, Divider, KeyValueRow } from '@/components/Card';
import { Chip, Tag, type TagTone } from '@/components/Chip';
import { InfoPopup } from '@/components/InfoPopup';
import { PageHeader } from '@/components/PageHeader';
import { FitSlot, FitSlots, Screen } from '@/components/Screen';
import { SegmentedTabs } from '@/components/SegmentedTabs';
import {
  SHICHEN,
  isToday,
  momentOf,
  shichenOfHour,
  shichenRangeLabel,
  shiftDays,
  todayISODate,
} from '@/lib/date';
import { QIMEN_GRID, QIMEN_GRID_DIRECTION } from '@/lib/qimenLayout';
import { LIUREN_GRID, LIUREN_GRID_COLUMNS } from '@/lib/liurenLayout';
import { TAIYI_GRID, TAIYI_GRID_DIRECTION } from '@/lib/taiyiLayout';
import { useAsync } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type SanshiKind = 'qimen' | 'liuren' | 'taiyi';
/** 每式内部再分「起局时刻 / 盘面」两段 —— 盘面自身就占大半屏，与选择器同屏会被裁 */
type SanshiStage = 'setup' | 'board';

/**
 * 已上线的术式。
 *
 * 三式齐全：奇门 / 六壬 / 太乙。太乙是**年局**，起局入参是年份而非时刻，
 * 所以它的 hint 与另外两式不同，并在页面里用独立的年份步进器。
 */
const KINDS: readonly { key: SanshiKind; label: string; hint: string }[] = [
  {
    key: 'qimen',
    label: '奇门遁甲',
    hint: '奇门以「时辰」起局，同一日的不同时辰可能落在不同局，所以要选到时辰而不只是日期。',
  },
  {
    key: 'liuren',
    label: '大六壬',
    hint: '六壬以「月将加时」起课，同一日的不同时辰是完全不同的课，所以必须选到时辰。',
  },
  {
    key: 'taiyi',
    label: '太乙神数',
    hint: '太乙是「年局」，以年为最小单位、随时辰不变，所以这里选年份、不选时刻。',
  },
];

// ==========================================================================
// 页面
// ==========================================================================

export default function SanshiScreen(): React.JSX.Element {
  const [kind, setKind] = useState<SanshiKind>('qimen');

  // 起局时刻由**本页**持有，两个术式共用同一份 —— 这正是把三式放同一页的
  // 理由：用户常三式互参，若各存一份，切一下标签时刻就重置，
  // 参出来的两张盘根本不是同一个时刻的。
  const initial = useMemo(defaultMoment, []);
  const [date, setDate] = useState(initial.date);
  const [shichen, setShichen] = useState(initial.shichen);
  const moment = momentOf(date, shichen);

  // 太乙年局：年份独立于「起局时刻」持有。三式里只有它按年走，
  // 与奇门/六壬共用 moment 不同 —— 年局若也绑 moment，切年份时会把
  // 另外两式的时刻一起重置，反过来又对不上「三式互参同一时刻」的设计。
  const [year, setYear] = useState(() => new Date().getFullYear());

  /** 纯版面状态：起局 / 盘面分段 */
  const [stage, setStage] = useState<SanshiStage>('board');

  const hint = KINDS.find((k) => k.key === kind)?.hint ?? '';

  return (
    <Screen>
      <PageHeader title="三式排盘" back helpTopic="sanshi" tone="light" />

      {/* 三式互斥：同一时刻只渲染一式 —— 三张盘堆在一页是放不下的 */}
      <SegmentedTabs<SanshiKind>
        items={KINDS.map((k) => ({ key: k.key, label: k.label }))}
        value={kind}
        onChange={setKind}
        variant="underline"
      />

      {/* 再分一层「起局 / 盘面」：盘面（九宫盘/十二宫方图/八宫盘）本身就占掉
          大半屏，与起局选择器同屏会把盘面挤出可视区（FitSlot 会裁掉它）。
          改时刻后切回「盘面」即重排 —— 盘面是纯函数式结果，改完立刻反映。 */}
      <SegmentedTabs<SanshiStage>
        items={[
          { key: 'setup', label: '起局' },
          { key: 'board', label: '盘面' },
        ]}
        value={stage}
        onChange={setStage}
        variant="underline"
      />

      <FitSlot weight={1} style={styles.col}>
        {stage === 'setup' ? (
          <>
            <AppText size="sm" color="textSecondary" style={styles.hint}>
              {hint}
            </AppText>
            {kind === 'taiyi' ? (
              <YearPicker year={year} onChange={setYear} />
            ) : (
              <MomentPicker date={date} shichen={shichen} onDate={setDate} onShichen={setShichen} />
            )}
          </>
        ) : kind === 'qimen' ? (
          <QimenPane moment={moment} />
        ) : kind === 'liuren' ? (
          <LiurenPane moment={moment} />
        ) : (
          <TaiyiPane year={year} />
        )}
      </FitSlot>

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        三式盘面由确定性内核算出，各流派取法存在差异；此处仅供参考
      </AppText>
    </Screen>
  );
}

// ==========================================================================
// 起局时刻（两式共用）
// ==========================================================================

/**
 * 起局时刻选择器。
 *
 * 之所以做成**受控组件 + 状态放在父级**：三式共用同一个时刻是本页存在的理由，
 * 各面板各存一份的话，切标签就会把用户刚选好的时刻丢掉。
 *
 * 单屏化后压成两行：日期步进 + 十二时辰。原本那段"为什么要选到时辰"的说明
 * 收进各式的详情浮层（每式的原因并不相同，写一句泛泛的"请选择时刻"等于没说）。
 */
function MomentPicker({
  date,
  shichen,
  onDate,
  onShichen,
}: {
  date: string;
  shichen: number;
  onDate: (next: string) => void;
  onShichen: (next: number) => void;
}): React.JSX.Element {
  return (
    <View style={styles.picker}>
      <View style={styles.stepper}>
        <Button label="−1 天" variant="ghost" style={styles.pickerBtn} onPress={() => onDate(shiftDays(date, -1))} />
        <View style={styles.stepperValue}>
          <AppText size="lg" weight="semibold" color="primary">
            {date}
          </AppText>
          <AppText size="xs" color="muted">
            {SHICHEN[shichen]}时 · {shichenRangeLabel(shichen)}
          </AppText>
        </View>
        <Button label="+1 天" variant="ghost" style={styles.pickerBtn} onPress={() => onDate(shiftDays(date, 1))} />
      </View>

      <View style={styles.shichenGrid}>
        {SHICHEN.map((name, i) => (
          <View key={name} style={styles.shichenCell}>
            <Chip label={name} onPress={() => onShichen(i)} active={i === shichen} />
          </View>
        ))}
      </View>

      <View style={styles.quickRow}>
        <Chip label="今天" onPress={() => onDate(todayISODate())} active={isToday(date)} />
        <Chip label="明天" onPress={() => onDate(shiftDays(todayISODate(), 1))} />
      </View>
    </View>
  );
}

/**
 * 太乙年局选择器。
 *
 * 与 `MomentPicker` 刻意分开：太乙以年为最小单位，不碰「时辰」概念。
 * 若复用 MomentPicker 会误导用户去选时辰（选了也不生效，年局不随时辰变）。
 * 这里只做「年份步进 + 今年/明年快捷」，输入是纯整数年份。
 */
function YearPicker({
  year,
  onChange,
}: {
  year: number;
  onChange: (next: number) => void;
}): React.JSX.Element {
  const thisYear = new Date().getFullYear();
  return (
    <View style={styles.picker}>
      <View style={styles.stepper}>
        <Button label="−1 年" variant="ghost" style={styles.pickerBtn} onPress={() => onChange(year - 1)} />
        <View style={styles.stepperValue}>
          <AppText size="xxl" weight="semibold" color="primary">
            {year}
          </AppText>
          <AppText size="xs" color="muted">
            公元年份（年局）
          </AppText>
        </View>
        <Button label="+1 年" variant="ghost" style={styles.pickerBtn} onPress={() => onChange(year + 1)} />
      </View>

      <View style={styles.quickRow}>
        <Chip label="今年" onPress={() => onChange(thisYear)} active={year === thisYear} />
        <Chip label="明年" onPress={() => onChange(thisYear + 1)} />
      </View>
    </View>
  );
}

// ==========================================================================
// 一、奇门遁甲
// ==========================================================================

function QimenPane({ moment }: { moment: string }): React.JSX.Element {
  const [open, setOpen] = useState(false);

  const metaLoader = useCallback((): Promise<QimenMetaResponse> => getApiClient().qimenMeta(), []);
  const meta = useAsync(metaLoader, []);

  // 时刻变则重排。之所以**不用按钮触发**：盘面是纯函数式的结果，
  // 用户改完时刻却看到旧盘，会以为是缓存或算错了。
  const panLoader = useCallback((): Promise<QimenChart> => {
    return getApiClient().qimenPan({ dt: moment, school: 'chaibu' });
  }, [moment]);
  const pan = useAsync(panLoader, [moment]);

  return (
    <FitSlots>
      {pan.error ? (
        <Banner tone="error" title="排盘失败">
          <AppText size="sm">{pan.error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={pan.reload} />
        </Banner>
      ) : null}

      <FitSlot weight={1}>
        {pan.data ? (
          <QimenBoard chart={pan.data} />
        ) : pan.loading ? (
          <Card>
            <AppText size="sm" color="muted">
              排盘中…
            </AppText>
          </Card>
        ) : null}
      </FitSlot>

      {pan.data || meta.data ? (
        <Button label="定局 · 值符值使 · 局数表 · 说明" variant="ghost" onPress={() => setOpen(true)} />
      ) : null}

      <InfoPopup
        visible={open}
        onClose={() => setOpen(false)}
        title="奇门 · 详情"
        subtitle="定局 / 值符值使 / 局数表 / 不确定性"
      >
        {pan.data ? <QimenDetails chart={pan.data} /> : null}
        {meta.data ? (
          <>
            <Divider style={styles.divider} />
            <AppText size="xs" color="textSecondary">
              局数表（节气 → 上/中/下元局数）
            </AppText>
            <AppText size="xs" color="muted" style={styles.popupBody}>
              由服务端返回，界面不自己维护一份 —— 局数表属领域数据，
              前端存副本必然与内核漂移，而漂移的表现是「显示的局数与实排不符」，不报错。
            </AppText>
            {Object.entries(meta.data.jushu_table).map(([jieqi, triple]) => (
              <KeyValueRow key={jieqi} label={jieqi} value={triple.join(' / ')} />
            ))}
          </>
        ) : null}
        <UncertaintyList items={pan.data?.uncertainties ?? meta.data?.uncertainties ?? []} />
      </InfoPopup>
    </FitSlots>
  );
}

/** 奇门盘面 —— 一屏只放这一张盘，作为弹性区 */
function QimenBoard({ chart }: { chart: QimenChart }): React.JSX.Element {
  const { dingju } = chart;
  const byGong = useMemo(() => {
    const m = new Map<number, QimenPalace>();
    chart.palaces.forEach((p) => m.set(p.gong, p));
    return m;
  }, [chart.palaces]);

  return (
    <Card>
      <View style={styles.boardHead}>
        <AppText size="lg" weight="bold" color="primary">
          {dingju.jushu_label}
        </AppText>
        <AppText size="xs" color="muted">
          九宫盘 · 南上北下
        </AppText>
      </View>
      <View style={styles.grid}>
        {QIMEN_GRID.map((gong, i) => {
          const palace = byGong.get(gong);
          return (
            <View key={gong} style={styles.gridCellWrap}>
              {palace ? (
                <PalaceCell
                  palace={palace}
                  position={QIMEN_GRID_DIRECTION[i] ?? ''}
                  isZhifuNow={gong === chart.zhifu_gong_now}
                  isZhishi={gong === chart.zhishi_gong}
                />
              ) : (
                // 不可达：服务端恒返回 1~9 九宫。真缺了也要显示出来，
                // 而不是让格子静默消失（缺格会让人以为洛书就长这样）。
                <View style={[styles.cell, styles.cellMissing]}>
                  <AppText size="xs" color="danger">
                    缺 {gong} 宫
                  </AppText>
                </View>
              )}
            </View>
          );
        })}
      </View>
    </Card>
  );
}

/** 奇门详情 —— 定局与值符值使（收进浮层，不占版面） */
function QimenDetails({ chart }: { chart: QimenChart }): React.JSX.Element {
  const { dingju, pillars } = chart;
  return (
    <>
      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        定局
      </AppText>
      <View style={styles.headline}>
        <AppText size="lg" weight="bold" color="primary">
          {dingju.jushu_label}
        </AppText>
        <Tag label={`${dingju.jieqi} · ${dingju.yuan_label}`} tone="neutral" />
      </View>
      <KeyValueRow label="交节时刻" value={dingju.jieqi_time} />
      <KeyValueRow label="节后天数" value={`第 ${dingju.days_after_jieqi} 天`} />
      <KeyValueRow label="起局时刻" value={dingju.solar_datetime} />
      <KeyValueRow
        label="四柱"
        value={`${pillars.year} ${pillars.month} ${pillars.day} ${pillars.hour}`}
        last
      />

      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        值符值使
      </AppText>
      <KeyValueRow label="旬首" value={chart.xunshou} />
      <KeyValueRow
        label="值符"
        value={`${chart.zhifu_star}（带${chart.zhifu_yi}）原居 ${chart.zhifu_gong} 宫`}
      />
      <KeyValueRow
        label="值符现落"
        value={`${chart.zhifu_gong_now} 宫 —— 天盘随之转，与上面「原居」不是一个宫`}
      />
      <KeyValueRow label="值使" value={`${chart.zhishi_door}（落 ${chart.zhishi_gong} 宫）`} />
      <KeyValueRow label="旬空" value={chart.xun_kong.join('、')} />
      <KeyValueRow label="驿马" value={chart.yima} last />
    </>
  );
}

/** 单宫 —— 信息密度最高的地方，顺序固定为 神 / 星 / 门 / 天盘干 / 地盘干 */
function PalaceCell({
  palace,
  position,
  isZhifuNow,
  isZhishi,
}: {
  palace: QimenPalace;
  position: string;
  isZhifuNow: boolean;
  isZhishi: boolean;
}): React.JSX.Element {
  const doorTone: TagTone =
    palace.door_jixiong === '吉' ? 'good' : palace.door_jixiong === '凶' ? 'bad' : 'neutral';

  return (
    <View
      style={[styles.cell, isZhifuNow && styles.cellZhifu, isZhishi && styles.cellZhishi]}
      accessibilityLabel={`${position}方 ${palace.gua}${palace.gong}宫，`
        + `地盘${palace.di_gan}，天盘${palace.tian_gan ?? '无'}，`
        + `${palace.star}，${palace.door ?? '无门'}，${palace.god ?? '无神'}`
        + `${palace.is_xun_kong ? '，空亡' : ''}${palace.is_yima ? '，驿马' : ''}`}
    >
      <View style={styles.cellTop}>
        <AppText size="xs" color="muted">
          {palace.gua}
          {palace.gong}
        </AppText>
        <AppText size="xs" color="muted">
          {position === '中' ? '中' : `${position}方`}
        </AppText>
      </View>

      <View style={styles.cellGodRow}>
        <AppText size="xs" color="jade" numberOfLines={1}>
          {palace.god ?? '—'}
        </AppText>
        {palace.star_jixiong ? (
          // 星/门的吉凶是**它们自身的固有属性**，不是对所求之事的结论，
          // 故只以文字标注，不参与任何"你这件事吉不吉"的呈现。
          <AppText size="xs" color="muted">
            {palace.star}
            {palace.star_jixiong}
          </AppText>
        ) : null}
      </View>

      <View style={styles.cellDoorRow}>
        <Tag label={palace.door ?? '无门'} tone={palace.door ? doorTone : 'neutral'} />
      </View>

      <View style={styles.cellGanRow}>
        <AppText size="xl" weight="semibold" color="primary">
          {palace.tian_gan ?? '—'}
        </AppText>
        <AppText size="sm" color="textSecondary">
          {palace.di_gan}
        </AppText>
      </View>

      {palace.is_xun_kong || palace.is_yima ? (
        <View style={styles.cellFlags}>
          {palace.is_xun_kong ? <AppText size="xs" color="danger">空</AppText> : null}
          {palace.is_yima ? <AppText size="xs" color="warning">马</AppText> : null}
        </View>
      ) : null}
    </View>
  );
}

// ==========================================================================
// 二、大六壬
// ==========================================================================

function LiurenPane({ moment }: { moment: string }): React.JSX.Element {
  const [open, setOpen] = useState(false);

  const metaLoader = useCallback(
    (): Promise<LiurenMetaResponse> => getApiClient().liurenMeta(),
    [],
  );
  const meta = useAsync(metaLoader, []);

  // 与奇门同口径：时刻变则重排，不用按钮触发。
  const castLoader = useCallback((): Promise<LiurenChart> => {
    return getApiClient().liurenCast({ dt: moment, school: 'default' });
  }, [moment]);
  const cast = useAsync(castLoader, [moment]);

  return (
    <FitSlots>
      {cast.error ? (
        <Banner tone="error" title="起课失败">
          <AppText size="sm">{cast.error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={cast.reload} />
        </Banner>
      ) : null}

      <FitSlot weight={1}>
        {cast.data ? (
          <LiurenBoard chart={cast.data} />
        ) : cast.loading ? (
          <Card>
            <AppText size="sm" color="muted">
              起课中…
            </AppText>
          </Card>
        ) : null}
      </FitSlot>

      {cast.data || meta.data ? (
        <Button label="课体 · 四课三传 · 月将表 · 说明" variant="ghost" onPress={() => setOpen(true)} />
      ) : null}

      <InfoPopup
        visible={open}
        onClose={() => setOpen(false)}
        title="六壬 · 详情"
        subtitle="课体 / 四课 / 三传 / 月将表 / 不确定性"
      >
        {cast.data ? <LiurenDetails chart={cast.data} /> : null}
        {meta.data ? (
          <>
            <Divider style={styles.divider} />
            <AppText size="xs" color="textSecondary">
              月将表（中气 → 月将）
            </AppText>
            <AppText size="xs" color="muted" style={styles.popupBody}>
              由服务端返回，界面不自己维护一份 —— 月将表属领域数据，
              前端存副本必然与内核漂移，而漂移的表现是「显示的月将与实排不符」，不报错。
              另注意换将以中气为界、不是节气：正月立春即建寅，但月将要到雨水才由神后换登明。
            </AppText>
            {Object.entries(meta.data.yuejiang_table).map(([zhongqi, zhi]) => (
              <KeyValueRow
                key={zhongqi}
                label={zhongqi}
                value={`${zhi}将（${meta.data?.yuejiang_names[zhi] ?? ''}）`}
              />
            ))}
          </>
        ) : null}
        <UncertaintyList items={cast.data?.uncertainties ?? meta.data?.uncertainties ?? []} />
      </InfoPopup>
    </FitSlots>
  );
}

/** 六壬盘面 —— 十二宫方图，一屏只放这一张盘 */
function LiurenBoard({ chart }: { chart: LiurenChart }): React.JSX.Element {
  const byGround = useMemo(() => {
    const m = new Map<string, LiurenPalace>();
    chart.palaces.forEach((p) => m.set(p.ground, p));
    return m;
  }, [chart.palaces]);

  return (
    <Card>
      <View style={styles.boardHead}>
        <AppText size="lg" weight="bold" color="primary">
          {chart.chuanke}
        </AppText>
        <AppText size="xs" color="muted">
          {chart.day_ganzhi}日 · {chart.hour_zhi}时 · 十二宫方图
        </AppText>
      </View>
      <View style={styles.grid}>
        {LIUREN_GRID.map((ground, i) => (
          <View key={i} style={styles.lrCellWrap}>
            {ground === null ? (
              // 中央 2×2 留白：不做成有边框的空盒子，否则看起来像"加载失败"。
              <View style={styles.lrCenter} />
            ) : (
              <LiurenCell palace={byGround.get(ground)} />
            )}
          </View>
        ))}
      </View>
    </Card>
  );
}

/** 六壬详情 —— 课体 / 四课 / 三传（收进浮层） */
function LiurenDetails({ chart }: { chart: LiurenChart }): React.JSX.Element {
  const { guiren } = chart;
  return (
    <>
      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        课体
      </AppText>
      <KeyValueRow label="月将" value={chart.month_general_label} />
      <KeyValueRow label="换将所依" value={`${chart.zhongqi}（${chart.zhongqi_time}）`} />
      <KeyValueRow
        label="贵人"
        value={`${guiren.kind}${guiren.zhi} · 临地盘${guiren.ground} · ${guiren.direction}`}
      />
      <KeyValueRow label="旬空" value={chart.xun_kong.join('、')} />
      <KeyValueRow label="驿马" value={chart.yima} />
      <AppText size="xs" color="muted" style={styles.popupBody}>
        {chart.chuanke_note}
      </AppText>

      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        四课
      </AppText>
      <AppText size="xs" color="muted" style={styles.popupBody}>
        每课「上神 / 下神」——上神取自天盘。第一课的下神位取日干寄宫，
        所以显示的是「日干本身」而非某个地支。标出记号的那一课是三传所出之处。
      </AppText>
      {chart.lessons.map((lesson) => (
        <View key={lesson.index} style={[styles.itemRow, lesson.is_ke && styles.itemRowMarked]}>
          <AppText size="xs" color="muted">
            {lesson.name}
          </AppText>
          <View style={styles.itemMain}>
            <AppText size="lg" weight="semibold" color="primary">
              {lesson.upper}
            </AppText>
            <AppText size="xs" color="muted">
              上 / 下
            </AppText>
            <AppText size="sm" color="textSecondary">
              {lesson.lower_label}
            </AppText>
          </View>
          <AppText size="xs" color="muted">
            {lesson.ke_kind ?? ''}
          </AppText>
        </View>
      ))}

      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        三传
      </AppText>
      {chart.chuan.map((c) => (
        <View key={c.position} style={styles.itemRow}>
          <AppText size="xs" color="muted">
            {c.position}
          </AppText>
          <View style={styles.itemMain}>
            <AppText size="xl" weight="bold" color="primary">
              {c.zhi}
            </AppText>
            <AppText size="sm" color="jade">
              {c.general ?? '—'}
            </AppText>
          </View>
          {/* 遁干为 null 是**旬空**信号，不是数据缺失 ——
              显示成「空」而不是留白，否则用户会以为这一格没算出来。 */}
          <AppText size="xs" color={c.dun_gan ? 'muted' : 'danger'}>
            {c.dun_gan ? `遁${c.dun_gan}` : '空（旬空）'}
          </AppText>
        </View>
      ))}
    </>
  );
}

/** 方图外圈一格 —— 天将 / 天盘支 / 地盘支，顺序固定。 */
function LiurenCell({ palace }: { palace: LiurenPalace | undefined }): React.JSX.Element {
  if (!palace) {
    // 不可达：服务端恒返回十二宫。真缺了也要显示出来，
    // 而不是让格子静默消失（缺格会让人以为盘就长这样）。
    return (
      <View style={[styles.cell, styles.cellMissing]}>
        <AppText size="xs" color="danger">
          缺宫
        </AppText>
      </View>
    );
  }

  return (
    <View
      style={[styles.cell, styles.lrCell, palace.is_guiren_ground && styles.cellGuiren]}
      accessibilityLabel={`地盘${palace.ground}，天盘${palace.heaven}，`
        + `${palace.general ?? '无天将'}`
        + `${palace.is_guiren_ground ? '，贵人临此宫' : ''}`}
    >
      {/* 天将的吉凶是它**自身的固有属性**，不是对所求之事的结论，
          故此处只显示将名，不显示吉凶 —— 显示吉凶会被读成断语。 */}
      <AppText size="xs" color="jade" numberOfLines={1}>
        {palace.general ?? '—'}
      </AppText>
      <AppText size="xl" weight="bold" color="primary">
        {palace.heaven}
      </AppText>
      <AppText size="xs" color="muted">
        地{palace.ground}
      </AppText>
    </View>
  );
}

// ==========================================================================
// 三、太乙神数（年局）
// ==========================================================================

function TaiyiPane({ year }: { year: number }): React.JSX.Element {
  const [open, setOpen] = useState(false);

  const metaLoader = useCallback(
    (): Promise<TaiyiMetaResponse> => getApiClient().taiyiMeta(),
    [],
  );
  const meta = useAsync(metaLoader, []);

  // 年份变则重排。与奇门/六壬同口径：盘面是纯函数式结果，
  // 不用按钮触发，改完年份立刻重排。
  const castLoader = useCallback((): Promise<TaiyiChart> => {
    return getApiClient().taiyiCast({ year, school: 'default' });
  }, [year]);
  const cast = useAsync(castLoader, [year]);

  return (
    <FitSlots>
      {cast.error ? (
        <Banner tone="error" title="起局失败">
          <AppText size="sm">{cast.error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={cast.reload} />
        </Banner>
      ) : null}

      <FitSlot weight={1}>
        {cast.data ? (
          <TaiyiBoard chart={cast.data} />
        ) : cast.loading ? (
          <Card>
            <AppText size="sm" color="muted">
              起局中…
            </AppText>
          </Card>
        ) : null}
      </FitSlot>

      {cast.data || meta.data ? (
        <Button label="局元 · 三目三算 · 宫号表 · 说明" variant="ghost" onPress={() => setOpen(true)} />
      ) : null}

      <InfoPopup
        visible={open}
        onClose={() => setOpen(false)}
        title="太乙 · 详情"
        subtitle="局元 / 太乙落宫 / 三目 / 三算 / 宫号表 / 不确定性"
      >
        {cast.data ? <TaiyiDetails chart={cast.data} /> : null}
        {meta.data ? (
          <>
            <Divider style={styles.divider} />
            <AppText size="xs" color="textSecondary">
              宫号表（🔴与洛书逐宫错位）
            </AppText>
            <AppText size="xs" color="muted" style={styles.popupBody}>
              由服务端返回，界面不自己维护一份 —— 宫号表是领域数据（RULE-005）。
              太乙宫号与洛书逐宫错位（乾1 离2 艮3 震4 兑6 坤7 坎8 巽9），
              前端若抄洛书必然整盘转 45°，且不报错。
            </AppText>
            {Object.entries(meta.data.palace_gua)
              .filter(([gong]) => gong !== '5')
              .map(([gong, gua]) => (
                <KeyValueRow
                  key={gong}
                  label={`${gong} 宫`}
                  value={`${gua} · ${meta.data!.palace_direction[gong] ?? ''} · ${meta.data!.palace_qi[gong] ?? ''}`}
                />
              ))}
          </>
        ) : null}
        <UncertaintyList items={cast.data?.uncertainties ?? meta.data?.uncertainties ?? []} />
      </InfoPopup>
    </FitSlots>
  );
}

/** 太乙盘面 —— 八宫盘，一屏只放这一张盘 */
function TaiyiBoard({ chart }: { chart: TaiyiChart }): React.JSX.Element {
  const byPalace = useMemo(() => {
    const m = new Map<number, TaiyiBamenLayout>();
    chart.bamen.layout.forEach((l) => m.set(l.palace, l));
    return m;
  }, [chart.bamen.layout]);

  const { epoch, bamen } = chart;

  return (
    <Card>
      <View style={styles.boardHead}>
        <AppText size="lg" weight="bold" color="primary">
          {epoch.ju_label}
        </AppText>
        <AppText size="xs" color="muted">
          {chart.year_ganzhi}年 · 值事门 {bamen.zhishi}
        </AppText>
      </View>
      <View style={styles.grid}>
        {TAIYI_GRID.map((gong, i) => (
          <View key={i} style={styles.gridCellWrap}>
            {gong === null ? (
              <View style={styles.tyCenter} />
            ) : (
              <TaiyiCell
                gong={gong}
                direction={TAIYI_GRID_DIRECTION[i] ?? ''}
                layout={byPalace.get(gong)}
                isZhishi={gong === byPalace.get(gong)?.palace && bamen.zhishi === byPalace.get(gong)?.door}
              />
            )}
          </View>
        ))}
      </View>
    </Card>
  );
}

/** 太乙详情 —— 局元 / 落宫 / 三目 / 三算（收进浮层） */
function TaiyiDetails({ chart }: { chart: TaiyiChart }): React.JSX.Element {
  const { taiyi, wenchang, shiji, dingmu, jishen, sansuan, epoch } = chart;

  return (
    <>
      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        局元
      </AppText>
      <KeyValueRow label="太乙积年" value={chart.jiyan} />
      <KeyValueRow label="积年基数（流派）" value={`${chart.school_name} · ${chart.jiyan_base}`} />
      <KeyValueRow label="纪元" value={`第 ${epoch.ji_number} 纪 · 纪内第 ${epoch.ji_year} 年`} />
      <KeyValueRow label="太岁 / 合神" value={`${chart.tai_sui} / ${chart.he_shen}`} last />

      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        太乙落宫
      </AppText>
      <View style={styles.headline}>
        <AppText size="lg" weight="bold" color="primary">
          {taiyi.gua} · {taiyi.palace} 宫
        </AppText>
        <Tag label={`${taiyi.direction} · ${taiyi.li}`} tone="good" />
      </View>
      <KeyValueRow label="入宫第几年" value={`第 ${taiyi.ru_gong_year} 年（${taiyi.li}）`} last />

      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        三目
      </AppText>
      <AppText size="xs" color="muted" style={styles.popupBody}>
        文昌 / 始击 / 定目都在十六神上走（含四维乾坤巽艮），计神只在十二支上走。
      </AppText>
      <KeyValueRow label="文昌天目" value={`${wenchang.pos}（${wenchang.name}）· ${wenchang.gua}${wenchang.palace}宫`} />
      <KeyValueRow label="计神" value={jishen.zhi} />
      <KeyValueRow label="始击客目" value={`${shiji.pos}（${shiji.name}）· ${shiji.gua}${shiji.palace}宫`} />
      <KeyValueRow label="定目" value={`${dingmu.pos}（${dingmu.name}）· ${dingmu.gua}${dingmu.palace}宫`} last />

      <Divider style={styles.divider} />
      <AppText size="xs" color="textSecondary">
        三算（主 / 客 / 定）
      </AppText>
      <AppText size="xs" color="muted" style={styles.popupBody}>
        算数是属性，不是吉凶结论；长短、和数孤数、三才同属属性。
        格局（掩迫囚击关格）与「利主利客」属上层解读（RULE-008），本页不做。
      </AppText>
      {sansuan.map((s) => (
        <View key={s.name} style={styles.itemRow}>
          <AppText size="xs" color="muted">
            {s.name}
          </AppText>
          <View style={styles.itemMain}>
            <AppText size="lg" weight="semibold" color="primary">
              {s.value}
            </AppText>
            <AppText size="xs" color="muted">
              {s.length} · {s.san_cai.length ? s.san_cai.join('') : '—'}
            </AppText>
          </View>
          <AppText size="xs" color="muted">
            大将 {s.da_jiang}{s.da_jiang_gua} · 参将 {s.can_jiang}{s.can_jiang_gua}
          </AppText>
        </View>
      ))}

      {chart.warnings.length ? (
        <Banner tone="warning" title="命中边界情形，请人工核对">
          {chart.warnings.map((w) => (
            <AppText key={w} size="sm">
              {w}
            </AppText>
          ))}
        </Banner>
      ) : null}
    </>
  );
}

/** 太乙八宫盘一格 —— 门（+自身吉凶），值事门以金框标出。 */
function TaiyiCell({
  gong,
  direction,
  layout,
  isZhishi,
}: {
  gong: number;
  direction: string;
  layout: TaiyiBamenLayout | undefined;
  isZhishi: boolean;
}): React.JSX.Element {
  if (!layout) {
    // 不可达：服务端恒返回八宫。真缺了也要显示出来，而不是让格子静默消失。
    return (
      <View style={[styles.cell, styles.cellMissing]}>
        <AppText size="xs" color="danger">
          缺 {gong} 宫
        </AppText>
      </View>
    );
  }

  const doorTone: TagTone =
    layout.jixiong.includes('吉') ? 'good' : layout.jixiong.includes('凶') ? 'bad' : 'neutral';

  return (
    <View
      style={[styles.cell, styles.tyCell, isZhishi && styles.cellZhishi]}
      accessibilityLabel={`${direction}方 ${layout.gua}${gong}宫，${layout.door}`
        + `${isZhishi ? '，值事门' : ''}`}
    >
      <View style={styles.cellTop}>
        <AppText size="xs" color="muted">
          {layout.gua}
          {gong}
        </AppText>
        <AppText size="xs" color="muted">
          {direction === '中' ? '中' : `${direction}方`}
        </AppText>
      </View>
      <View style={styles.cellDoorRow}>
        <Tag label={layout.door} tone={doorTone} />
      </View>
    </View>
  );
}

// ==========================================================================
// 工具
// ==========================================================================

/**
 * 打开页面时的默认起局时刻。
 *
 * 本地 0 点这一小时要**归到前一日**：00:00~00:59 在干支上属「晚子时」，
 * 是前一日子时的后半段。若直接把它当今天 23 时，得到的是**今晚**的盘，
 * 与用户此刻想看的那一局不是同一个时刻。
 */
function defaultMoment(): { date: string; shichen: number } {
  const now = new Date();
  const hour = now.getHours();
  if (hour === 0) {
    return { date: shiftDays(todayISODate(), -1), shichen: 0 };
  }
  return { date: todayISODate(), shichen: shichenOfHour(hour) };
}

// ==========================================================================
// 样式
// ==========================================================================

/**
 * 九宫格内间距与格子最小高度。
 *
 * 间距取 2 而非 8pt 栅格值，是**刻意的例外**：3×3 网格里每格宽度只有屏宽
 * 的三分之一，用 8pt 内间距会让可用的字位再少 16pt，而盘面每格的信息量
 * 又很大（神/星/门/两个干）。这里宁可让格子贴紧一点，也要把字保住。
 *
 * 最小高度从 104 收到 92：单屏化后整张盘必须与起局选择器同屏，104 会在
 * 矮屏把盘面顶出可视区（被 FitSlot 裁掉）。92 是"仍能容下五行字 + 不裁"
 * 的折中；内容更高的格子仍会自然撑高（minHeight 只是下限）。
 */
const CELL_GAP = 2;
const CELL_MIN_HEIGHT = 92;

/**
 * 六壬方图外圈格子的最小高度。
 *
 * 比奇门矮一截是**刻意**的：六壬每格只有三行短文本（将名 / 天盘支 / 地盘支），
 * 而外圈有十二格；沿用奇门的高度会让整张盘撑破一屏，反而看不清十二宫的整体结构。
 */
const LR_CELL_MIN_HEIGHT = 58;

const styles = StyleSheet.create({
  col: { gap: space[2] },
  picker: { gap: space[2] },
  hint: { lineHeight: 20 },
  boardHead: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'space-between',
    marginBottom: space[2],
  },
  headline: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: space[2],
    marginTop: space[1],
  },
  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space[2],
  },
  pickerBtn: { minWidth: 76 },
  stepperValue: { alignItems: 'center', flex: 1 },
  quickRow: { flexDirection: 'row', gap: space[2], justifyContent: 'center' },
  divider: { marginVertical: space[3] },
  popupBody: { lineHeight: 20 },

  shichenGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  // 六列：1200 个逻辑像素以下的手机一行放六个「子」这样的单字 chip 是够的
  shichenCell: { width: `${100 / 6}%`, paddingVertical: space[1], alignItems: 'center' },

  grid: { flexDirection: 'row', flexWrap: 'wrap' },
  gridCellWrap: { width: `${100 / 3}%`, padding: CELL_GAP },
  cell: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    backgroundColor: colors.surfaceAlt,
    padding: space[2],
    minHeight: CELL_MIN_HEIGHT,
    gap: CELL_GAP,
  },
  cellZhifu: { borderColor: colors.primary, borderWidth: 1.5, backgroundColor: alpha.primarySoft },
  cellZhishi: { borderColor: colors.gold, borderWidth: 1.5, backgroundColor: alpha.goldSoft },
  cellMissing: { alignItems: 'center', justifyContent: 'center', borderStyle: 'dashed' },
  cellTop: { flexDirection: 'row', justifyContent: 'space-between' },
  cellGodRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cellDoorRow: { flexDirection: 'row', marginTop: CELL_GAP },
  cellGanRow: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' },
  cellFlags: { flexDirection: 'row', gap: space[2] },

  // ---- 六壬方图 ----
  // 四列、十二格外圈 + 中央留白。格子比奇门矮：每格只有三行短文本
  // （将名 / 天盘支 / 地盘支）。
  lrCellWrap: { width: `${100 / LIUREN_GRID_COLUMNS}%`, padding: CELL_GAP },
  lrCell: { minHeight: LR_CELL_MIN_HEIGHT, alignItems: 'center', gap: CELL_GAP },
  lrCenter: { minHeight: LR_CELL_MIN_HEIGHT },
  cellGuiren: { borderColor: colors.gold, borderWidth: 1.5, backgroundColor: alpha.goldSoft },

  // ---- 太乙八宫盘 ----
  // 3×3、中央留白。格子与六壬同高：太乙每格只有门（+吉凶）两行短文本。
  tyCell: { minHeight: LR_CELL_MIN_HEIGHT, alignItems: 'stretch' },
  tyCenter: { minHeight: LR_CELL_MIN_HEIGHT },

  // ---- 四课 / 三传 / 三算行 ----
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: space[2],
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: space[2],
  },
  // 三传所出那一课：加一条左侧强调线，而不是染成"吉/凶"色 ——
  // 它标的是"初传从这里取"，不是好坏。
  itemRowMarked: { borderLeftWidth: 3, borderLeftColor: colors.primary, paddingLeft: space[3] },
  itemMain: { flexDirection: 'row', alignItems: 'center', gap: space[2], flex: 1 },

  retry: { marginTop: space[2], alignSelf: 'flex-start' },
  disclaimer: { marginTop: space[1] },
});
