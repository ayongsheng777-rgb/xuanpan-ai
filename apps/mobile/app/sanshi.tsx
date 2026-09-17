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
import type { QimenChart, QimenMetaResponse, QimenPalace } from '@/api/types';
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
import { useAsync } from '@/lib/useAsync';
import { alpha, colors, radius, space } from '@/theme/tokens';

type SanshiKind = 'qimen';

/**
 * 已上线的术式。
 *
 * 六壬与太乙的内核尚未落地，所以这里**不放占位标签** ——
 * 一个点进去只写着"建设中"的标签，比没有这个标签更让人困惑。
 * 内核上线时在此追加一项即可。
 */
const KINDS: readonly { key: SanshiKind; label: string }[] = [
  { key: 'qimen', label: '奇门遁甲' },
];

// ==========================================================================
// 页面
// ==========================================================================

export default function SanshiScreen(): React.JSX.Element {
  const [kind, setKind] = useState<SanshiKind>('qimen');

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
        {kind === 'qimen' ? <QimenPane /> : null}
      </View>

      <AppText size="xs" color="muted" center style={styles.disclaimer}>
        三式盘面由确定性内核算出，各流派取法存在差异；此处仅供参考
      </AppText>
    </Screen>
  );
}

// ==========================================================================
// 一、奇门遁甲
// ==========================================================================

function QimenPane(): React.JSX.Element {
  const initial = useMemo(defaultMoment, []);
  const [date, setDate] = useState(initial.date);
  const [shichen, setShichen] = useState(initial.shichen);

  const metaLoader = useCallback((): Promise<QimenMetaResponse> => getApiClient().qimenMeta(), []);
  const meta = useAsync(metaLoader, []);

  // 时刻变则重排。之所以**不用按钮触发**：盘面是纯函数式的结果，
  // 用户改完时刻却看到旧盘，会以为是缓存或算错了。
  const moment = momentOf(date, shichen);
  const panLoader = useCallback((): Promise<QimenChart> => {
    return getApiClient().qimenPan({ dt: moment, school: 'chaibu' });
  }, [moment]);
  const pan = useAsync(panLoader, [moment]);

  return (
    <>
      <Card title="起局时刻">
        <AppText size="xs" color="muted" style={styles.hint}>
          奇门以**时辰**起局，同一日的不同时辰可能落在不同局，所以要选到时辰而不只是日期。
        </AppText>

        <View style={styles.stepper}>
          <View style={styles.stepperButton}>
            <Button label="−1 天" variant="ghost" onPress={() => setDate((d) => shiftDays(d, -1))} />
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
            <Button label="+1 天" variant="ghost" onPress={() => setDate((d) => shiftDays(d, 1))} />
          </View>
        </View>

        <View style={styles.quickRow}>
          <Chip label="今天" onPress={() => setDate(todayISODate())} active={isToday(date)} />
          <Chip label="明天" onPress={() => setDate(shiftDays(todayISODate(), 1))} />
        </View>

        <Divider style={styles.divider} />

        {/* 十二时辰：两行六列。子时排在最前（而非 23 时排到末尾）——
            时辰是循环的，按钟点排反而会让「子」跑到最后一格。 */}
        <View style={styles.shichenGrid}>
          {SHICHEN.map((name, i) => (
            <View key={name} style={styles.shichenCell}>
              <Chip label={name} onPress={() => setShichen(i)} active={i === shichen} />
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

  retry: { marginTop: space[2], alignSelf: 'flex-start' },
  disclaimer: { marginTop: space[6] },
});
