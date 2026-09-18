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
import { Screen } from '@/components/Screen';
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
import { TAIYI_GRID, TAIYI_GRID_COLUMNS, TAIYI_GRID_DIRECTION } from '@/lib/taiyiLayout';
import { useAsync } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type SanshiKind = 'qimen' | 'liuren' | 'taiyi';

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

  return (
    <Screen scroll>
      {KINDS.length > 1 ? (
        <SegmentedTabs<SanshiKind>
          items={KINDS.map((k) => ({ key: k.key, label: k.label }))}
          value={kind}
          onChange={setKind}
          variant="underline"
        />
      ) : null}

      <View style={styles.body}>
        {kind === 'taiyi' ? (
          <YearPicker year={year} onChange={setYear} hint={KINDS.find((k) => k.key === kind)?.hint ?? ''} />
        ) : (
          <MomentPicker
            date={date}
            shichen={shichen}
            moment={moment}
            onDate={setDate}
            onShichen={setShichen}
            hint={KINDS.find((k) => k.key === kind)?.hint ?? ''}
          />
        )}

        {kind === 'qimen' ? <QimenPane moment={moment} /> : null}
        {kind === 'liuren' ? <LiurenPane moment={moment} /> : null}
        {kind === 'taiyi' ? <TaiyiPane year={year} /> : null}
      </View>

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
 * `hint` 由当前术式给 —— 同样是"要选到时辰"，奇门与六壬的原因并不相同
 * （一个是定局，一个是月将加时），写一句泛泛的"请选择时刻"等于没说。
 */
function MomentPicker({
  date,
  shichen,
  moment,
  onDate,
  onShichen,
  hint,
}: {
  date: string;
  shichen: number;
  moment: string;
  onDate: (next: string) => void;
  onShichen: (next: number) => void;
  hint: string;
}): React.JSX.Element {
  return (
    <Card title="起局时刻">
      <AppText size="xs" color="muted" style={styles.hint}>
        {hint}
      </AppText>

      <View style={styles.stepper}>
        <View style={styles.stepperButton}>
          <Button label="−1 天" variant="ghost" onPress={() => onDate(shiftDays(date, -1))} />
        </View>
        <View style={styles.stepperValue}>
          <AppText size="lg" weight="semibold" color="primary">
            {date}
          </AppText>
          <AppText size="xs" color="muted">
            {SHICHEN[shichen]}时 {shichenRangeLabel(shichen)}
          </AppText>
        </View>
        <View style={styles.stepperButton}>
          <Button label="+1 天" variant="ghost" onPress={() => onDate(shiftDays(date, 1))} />
        </View>
      </View>

      <View style={styles.quickRow}>
        <Chip label="今天" onPress={() => onDate(todayISODate())} active={isToday(date)} />
        <Chip label="明天" onPress={() => onDate(shiftDays(todayISODate(), 1))} />
      </View>

      <Divider style={styles.divider} />

      {/* 十二时辰：两行六列。子时排在最前（而非 23 时排到末尾）——
          时辰是循环的，按钟点排反而会让「子」跑到最后一格。 */}
      <View style={styles.shichenGrid}>
        {SHICHEN.map((name, i) => (
          <View key={name} style={styles.shichenCell}>
            <Chip label={name} onPress={() => onShichen(i)} active={i === shichen} />
          </View>
        ))}
      </View>

      <View style={styles.momentRow}>
        <AppText size="xs" color="muted">
          将以此时刻起局：
        </AppText>
        <AppText size="xs" weight="semibold" color="primary">
          {moment}
        </AppText>
      </View>
    </Card>
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
  hint,
}: {
  year: number;
  onChange: (next: number) => void;
  hint: string;
}): React.JSX.Element {
  const thisYear = new Date().getFullYear();
  return (
    <Card title="起局年份">
      <AppText size="xs" color="muted" style={styles.hint}>
        {hint}
      </AppText>

      <View style={styles.stepper}>
        <View style={styles.stepperButton}>
          <Button label="−1 年" variant="ghost" onPress={() => onChange(year - 1)} />
        </View>
        <View style={styles.stepperValue}>
          <AppText size="xxl" weight="semibold" color="primary">
            {year}
          </AppText>
          <AppText size="xs" color="muted">
            公元年份
          </AppText>
        </View>
        <View style={styles.stepperButton}>
          <Button label="+1 年" variant="ghost" onPress={() => onChange(year + 1)} />
        </View>
      </View>

      <View style={styles.quickRow}>
        <Chip label="今年" onPress={() => onChange(thisYear)} active={year === thisYear} />
        <Chip label="明年" onPress={() => onChange(thisYear + 1)} />
      </View>
    </Card>
  );
}

// ==========================================================================
// 一、奇门遁甲
// ==========================================================================

function QimenPane({ moment }: { moment: string }): React.JSX.Element {
  const metaLoader = useCallback((): Promise<QimenMetaResponse> => getApiClient().qimenMeta(), []);
  const meta = useAsync(metaLoader, []);

  // 时刻变则重排。之所以**不用按钮触发**：盘面是纯函数式的结果，
  // 用户改完时刻却看到旧盘，会以为是缓存或算错了。
  const panLoader = useCallback((): Promise<QimenChart> => {
    return getApiClient().qimenPan({ dt: moment, school: 'chaibu' });
  }, [moment]);
  const pan = useAsync(panLoader, [moment]);

  return (
    <>
      {pan.error ? (
        <Banner tone="error" title="排盘失败">
          <AppText size="sm">{pan.error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={pan.reload} />
        </Banner>
      ) : null}

      {pan.loading && !pan.data ? (
        <Card>
          <AppText size="sm" color="muted">
            排盘中…
          </AppText>
        </Card>
      ) : null}

      {pan.data ? <QimenChartView chart={pan.data} /> : null}

      {meta.data ? (
        <Card title="局数表（节气 → 上/中/下元局数）">
          <AppText size="xs" color="muted" style={styles.hint}>
            由服务端返回，界面不自己维护一份 —— 局数表属领域数据，
            前端存副本必然与内核漂移，而漂移的表现是「显示的局数与实排不符」，不报错。
          </AppText>
          {Object.entries(meta.data.jushu_table).map(([jieqi, triple]) => (
            <KeyValueRow
              key={jieqi}
              label={jieqi}
              value={triple.join(' / ')}
            />
          ))}
        </Card>
      ) : null}

      <UncertaintyList items={pan.data?.uncertainties ?? meta.data?.uncertainties ?? []} />
    </>
  );
}

function QimenChartView({ chart }: { chart: QimenChart }): React.JSX.Element {
  const { dingju, pillars } = chart;
  const byGong = useMemo(() => {
    const m = new Map<number, QimenPalace>();
    chart.palaces.forEach((p) => m.set(p.gong, p));
    return m;
  }, [chart.palaces]);

  return (
    <>
      <Card title="定局">
        <View style={styles.headline}>
          <AppText size="xxl" weight="bold" color="primary">
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
        />
      </Card>

      <Card title="值符值使">
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
        <KeyValueRow label="驿马" value={chart.yima} />
      </Card>

      <Card title="九宫盘（南上北下）">
        <AppText size="xs" color="muted" style={styles.hint}>
          每格自上而下：八神 · 九星 · 八门 · 天盘干 / 地盘干。
          空亡与驿马以角标标注。传统排法为南上北下，与地图方向相反。
        </AppText>
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
    <>
      {cast.error ? (
        <Banner tone="error" title="起课失败">
          <AppText size="sm">{cast.error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={cast.reload} />
        </Banner>
      ) : null}

      {cast.loading && !cast.data ? (
        <Card>
          <AppText size="sm" color="muted">
            起课中…
          </AppText>
        </Card>
      ) : null}

      {cast.data ? <LiurenChartView chart={cast.data} /> : null}

      {meta.data ? (
        <Card title="月将表（中气 → 月将）">
          <AppText size="xs" color="muted" style={styles.hint}>
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
        </Card>
      ) : null}

      <UncertaintyList items={cast.data?.uncertainties ?? meta.data?.uncertainties ?? []} />
    </>
  );
}

function LiurenChartView({ chart }: { chart: LiurenChart }): React.JSX.Element {
  const byGround = useMemo(() => {
    const m = new Map<string, LiurenPalace>();
    chart.palaces.forEach((p) => m.set(p.ground, p));
    return m;
  }, [chart.palaces]);

  const { guiren } = chart;

  return (
    <>
      <Card title="课体">
        <View style={styles.headline}>
          <AppText size="xxl" weight="bold" color="primary">
            {chart.chuanke}
          </AppText>
          <Tag label={`${chart.day_ganzhi}日 · ${chart.hour_zhi}时`} tone="neutral" />
        </View>
        <KeyValueRow label="月将" value={chart.month_general_label} />
        <KeyValueRow label="换将所依" value={`${chart.zhongqi}（${chart.zhongqi_time}）`} />
        <KeyValueRow
          label="贵人"
          value={`${guiren.kind}${guiren.zhi} · 临地盘${guiren.ground} · ${guiren.direction}`}
        />
        <KeyValueRow label="旬空" value={chart.xun_kong.join('、')} />
        <KeyValueRow label="驿马" value={chart.yima} />
        <AppText size="xs" color="muted" style={styles.keNote}>
          {chart.chuanke_note}
        </AppText>
      </Card>

      <Card title="十二宫方图">
        <AppText size="xs" color="muted" style={styles.hint}>
          外圈十二宫沿顺时针排列，每格自上而下为 天将 · 天盘支 / 地盘支；
          贵人所在之宫以金色边框标出。中央留白，起课要点见下方「三传」。
        </AppText>
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

      <Card title="四课">
        <AppText size="xs" color="muted" style={styles.hint}>
          每课「上神 / 下神」——上神取自天盘。第一课的下神位取日干寄宫，
          所以显示的是「日干本身」而非某个地支。标出记号的那一课是三传所出之处。
        </AppText>
        {chart.lessons.map((lesson) => (
          <View
            key={lesson.index}
            style={[styles.itemRow, lesson.is_ke && styles.itemRowMarked]}
          >
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
      </Card>

      <Card title="三传">
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
      </Card>
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
    <>
      {cast.error ? (
        <Banner tone="error" title="起局失败">
          <AppText size="sm">{cast.error}</AppText>
          <Button label="重试" variant="ghost" style={styles.retry} onPress={cast.reload} />
        </Banner>
      ) : null}

      {cast.loading && !cast.data ? (
        <Card>
          <AppText size="sm" color="muted">
            起局中…
          </AppText>
        </Card>
      ) : null}

      {cast.data ? <TaiyiChartView chart={cast.data} /> : null}

      {meta.data ? (
        <Card title="宫号表（🔴与洛书逐宫错位）">
          <AppText size="xs" color="muted" style={styles.hint}>
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
        </Card>
      ) : null}

      <UncertaintyList items={cast.data?.uncertainties ?? meta.data?.uncertainties ?? []} />
    </>
  );
}

function TaiyiChartView({ chart }: { chart: TaiyiChart }): React.JSX.Element {
  const byPalace = useMemo(() => {
    const m = new Map<number, TaiyiBamenLayout>();
    chart.bamen.layout.forEach((l) => m.set(l.palace, l));
    return m;
  }, [chart.bamen.layout]);

  const { taiyi, wenchang, shiji, dingmu, jishen, sansuan, bamen, epoch } = chart;

  return (
    <>
      <Card title="局元">
        <View style={styles.headline}>
          <AppText size="xxl" weight="bold" color="primary">
            {epoch.ju_label}
          </AppText>
          <Tag label={`${chart.year_ganzhi}年`} tone="neutral" />
        </View>
        <KeyValueRow label="太乙积年" value={chart.jiyan} />
        <KeyValueRow label="积年基数（流派）" value={`${chart.school_name} · ${chart.jiyan_base}`} />
        <KeyValueRow label="纪元" value={`第 ${epoch.ji_number} 纪 · 纪内第 ${epoch.ji_year} 年`} />
        <KeyValueRow label="太岁 / 合神" value={`${chart.tai_sui} / ${chart.he_shen}`} />
      </Card>

      <Card title="太乙落宫">
        <View style={styles.headline}>
          <AppText size="xl" weight="bold" color="primary">
            {taiyi.gua} · {taiyi.palace} 宫
          </AppText>
          <Tag label={`${taiyi.direction} · ${taiyi.li}`} tone="good" />
        </View>
        <KeyValueRow label="入宫第几年" value={`第 ${taiyi.ru_gong_year} 年（${taiyi.li}）`} />
      </Card>

      <Card title="三目">
        <AppText size="xs" color="muted" style={styles.hint}>
          文昌 / 始击 / 定目都在十六神上走（含四维乾坤巽艮），计神只在十二支上走。
        </AppText>
        <KeyValueRow label="文昌天目" value={`${wenchang.pos}（${wenchang.name}）· ${wenchang.gua}${wenchang.palace}宫`} />
        <KeyValueRow label="计神" value={jishen.zhi} />
        <KeyValueRow label="始击客目" value={`${shiji.pos}（${shiji.name}）· ${shiji.gua}${shiji.palace}宫`} />
        <KeyValueRow label="定目" value={`${dingmu.pos}（${dingmu.name}）· ${dingmu.gua}${dingmu.palace}宫`} />
      </Card>

      <Card title="三算（主 / 客 / 定）">
        <AppText size="xs" color="muted" style={styles.hint}>
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
      </Card>

      <Card title="值事八门盘（南上北下，中央留白）">
        <AppText size="xs" color="muted" style={styles.hint}>
          太乙八宫盘跳过中五宫，中央留白。每格为 门（+自身吉凶）。值事门以金色边框标出。
          门的吉凶是门自身的固有属性，不是对所问之事的结论。
        </AppText>
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
        <KeyValueRow label="值事门" value={`${bamen.zhishi}（${bamen.zhishi_jixiong}）`} />
      </Card>

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
 */
const CELL_GAP = 2;
const CELL_MIN_HEIGHT = 104;

/**
 * 六壬方图外圈格子的最小高度。
 *
 * 比奇门矮一截是**刻意**的：六壬每格只有三行短文本（将名 / 天盘支 / 地盘支），
 * 而外圈有十二格、还要再排四课与三传两张卡；沿用奇门的 104pt 会让整页
 * 拉到三四屏，反而看不清十二宫的整体结构。
 */
const LR_CELL_MIN_HEIGHT = 62;

const styles = StyleSheet.create({
  body: { gap: space[4], marginTop: space[4] },
  hint: { marginBottom: space[3] },
  headline: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: space[3],
  },
  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space[2],
  },
  stepperButton: { minWidth: 76 },
  stepperValue: { alignItems: 'center', flex: 1 },
  quickRow: { flexDirection: 'row', gap: space[2], marginTop: space[3] },
  divider: { marginVertical: space[4] },

  shichenGrid: { flexDirection: 'row', flexWrap: 'wrap' },
  // 六列：1200 个逻辑像素以下的手机一行放六个「子」这样的单字 chip 是够的
  shichenCell: { width: `${100 / 6}%`, paddingVertical: space[1], alignItems: 'center' },

  momentRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: space[3],
    paddingTop: space[3],
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },

  grid: { flexDirection: 'row', flexWrap: 'wrap', marginTop: space[2] },
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
  // （将名 / 天盘支 / 地盘支），按奇门的 104pt 会把页面拉得很长。
  lrCellWrap: { width: `${100 / LIUREN_GRID_COLUMNS}%`, padding: CELL_GAP },
  lrCell: { minHeight: LR_CELL_MIN_HEIGHT, alignItems: 'center', gap: CELL_GAP },
  lrCenter: { minHeight: LR_CELL_MIN_HEIGHT },
  cellGuiren: { borderColor: colors.gold, borderWidth: 1.5, backgroundColor: alpha.goldSoft },

  // ---- 太乙八宫盘 ----
  // 3×3、中央留白。格子与六壬同高：太乙每格只有门（+吉凶）两行短文本。
  tyCell: { minHeight: LR_CELL_MIN_HEIGHT, alignItems: 'stretch' },
  tyCenter: { minHeight: LR_CELL_MIN_HEIGHT },

  // ---- 四课 / 三传行 ----
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
  keNote: { marginTop: space[3], lineHeight: 18 },

  retry: { marginTop: space[2], alignSelf: 'flex-start' },
  disclaimer: { marginTop: space[6] },
});
