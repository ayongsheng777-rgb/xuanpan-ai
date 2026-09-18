/**
 * 罗盘盘面仿真 —— 按真实罗盘形制绘制，且**数据驱动**。
 *
 * 与"只画一圈山格的简易选择器"的区别（两者不可互相替代）：
 *   - 简易选择器为「点一下选对宫」而优化：环带刻意做厚、格子刻意做大，
 *     因为它的唯一任务是让手指点得准。
 *   - `CompassDial` 是**盘面本身**：按实物罗盘的层次绘制（二十四山 / 先后天八卦 /
 *     一百二十分金刻度 / 天池磁针），并且可以整体旋转、可以点选取山。
 *     它要解决的不是"点得准"，而是"让用户一眼看出盘面排位与自己手里的罗盘是否一致"——
 *     这一条是识别结果能被信任的前提，也是本组件存在的理由。
 *
 * 四个语义约定（错了就会给出"看起来对"的错误盘面）：
 *   1. **屏幕正上方恒为真北**。磁针永远指向屏幕上方，不随盘面旋转 ——
 *      实物罗盘上转的是盘体，磁针始终指北。反过来画会让人以为罗盘坏了。
 *   2. **rotation 是盘体的旋转量**（顺时针为正）。盘面角 θ 的显示位置 = θ + rotation。
 *   3. **坐山 / 向山 / 实测角都存盘面角**，不存屏幕角。这样旋转盘面不会
 *      悄悄改变"用户选的是哪座山"——旋转是视角，选择是事实。
 *   4. **盘式（`style`）只影响画哪些层、每层多宽**，不影响任何角度换算。
 *      切盘式不该让"用户选的是午"变成别的山。
 *
 * `[待验证]` 红/蓝/墨的盘面角色配色属盘式流派（各版罗盘分色不同），
 * 仅影响视觉识别，不参与任何术数计算（见 `lib/compassDial`）。
 */

import React, { useCallback, useId, useMemo, useRef, useState } from 'react';
import {
  PanResponder,
  StyleSheet,
  View,
  type LayoutChangeEvent,
} from 'react-native';
import Svg, {
  Circle,
  ClipPath,
  Defs,
  G,
  Image as SvgImage,
  Line,
  Path,
  Text as SvgText,
} from 'react-native-svg';

import {
  TRIGRAM_HOUTIAN,
  buildTicks,
  dialDegreeAt,
  dialLayout,
  mountainRole,
  normalizeSigned,
  pointerAngle,
  rotationToAlign,
  TICK_LENGTH_RATIO,
  type TickLevel,
} from '@/lib/compassDial';
import {
  TRIGRAM_XIANTIAN,
  coerceDialStyle,
  layerRadius,
  renderLayers,
  type DialStyleId,
} from '@/lib/dialStyle';
import {
  MOUNTAIN_NAMES,
  degreeToIndex,
  indexToDegree,
  nameOfIndex,
  oppositeIndex,
  pointOnCircle,
  sectorPathOfIndex,
} from '@/lib/ring24';
import { alpha, brand, colors, instrument } from '@/theme/tokens';

/** 拖动与点击的判别阈值（像素）：位移小于它才算"点了一下" */
const TAP_SLOP = 8;
/** 相邻山格之间的视觉缝隙（度） */
const SECTOR_GAP_DEG = 0.6;

/**
 * 盘面调色板 —— 双轨制（《V2 评估与实施路线》冲突 2 裁决）。
 *
 * light：既有暖色浅色盘（确认坐向等浅色页面继续用）；
 * dark ：V2 演示图的深色仪器盘（罗盘域新页面用）。
 * 两轨共用同一套几何（dialLayout / dialStyle），只有配色不同 ——
 * 几何是事实，配色是视角，不能混为一谈。
 */
export interface DialPalette {
  /** 盘体底色 */
  body: string;
  /** 金环/外框 */
  rim: string;
  /** 细分隔线 */
  hairline: string;
  /** 山格描边 */
  sectorStroke: string;
  /** 天池底 */
  pool: string;
  /** 坐山格填充 */
  sittingFill: string;
  /** 向山格填充 */
  facingFill: string;
  /** 四正淡底 */
  cardinalSoft: string;
  /** 四维淡底 */
  cornerSoft: string;
  /** 普通山格底 */
  plainFill: string;
  /** 坐山字色 */
  sittingText: string;
  /** 向山字色 */
  facingText: string;
  /** 四正字色（朱） */
  cardinalText: string;
  /** 四维字色 */
  cornerText: string;
  /** 普通山名字色 */
  plainText: string;
  /** 卦符色 */
  trigram: string;
  /** 先天八卦卦符色（与后天分开：两者是两套方位，同色会让人以为是一层） */
  trigramXiantian: string;
  /** 磁针北（红） */
  needleNorth: string;
  /** 磁针南 */
  needleSouth: string;
  /** 天池中心点 */
  poolDot: string;
  /** 实测针 */
  measured: string;
  /** 刻度三色：主 / 中 / 细 */
  tick0: string;
  tick1: string;
  tick2: string;
}

export const DIAL_LIGHT: DialPalette = {
  body: colors.sand,
  rim: brand.gold,
  hairline: alpha.primaryBorder,
  sectorStroke: alpha.goldSoft,
  pool: colors.surface,
  sittingFill: colors.primary,
  facingFill: brand.gold,
  cardinalSoft: alpha.cinnabarSoft,
  cornerSoft: alpha.primarySoft,
  plainFill: colors.sand,
  sittingText: colors.onPrimary,
  facingText: colors.primary,
  cardinalText: colors.cinnabar,
  cornerText: colors.primary,
  plainText: colors.text,
  trigram: colors.jade,
  trigramXiantian: colors.cinnabar,
  needleNorth: colors.cinnabar,
  needleSouth: colors.primary,
  poolDot: brand.gold,
  measured: colors.cinnabar,
  tick0: colors.cinnabar,
  tick1: colors.primary,
  tick2: colors.muted,
};

export const DIAL_DARK: DialPalette = {
  body: instrument.dialBody,
  rim: instrument.dialGold,
  hairline: instrument.border,
  sectorStroke: instrument.border,
  pool: instrument.surface,
  sittingFill: instrument.accent,
  facingFill: instrument.surfaceAlt,
  cardinalSoft: 'rgba(224, 85, 72, 0.16)',
  cornerSoft: 'rgba(218, 179, 125, 0.14)',
  plainFill: instrument.dialBody,
  sittingText: instrument.bg,
  facingText: instrument.accent,
  cardinalText: instrument.needle,
  cornerText: instrument.accent,
  plainText: instrument.textSecondary,
  trigram: instrument.accent,
  // 先天八卦用暗金 —— 与后天的亮金分色，避免两层混成一层
  trigramXiantian: 'rgba(218, 179, 125, 0.62)',
  needleNorth: instrument.needle,
  needleSouth: instrument.textSecondary,
  poolDot: instrument.dialGold,
  measured: instrument.needle,
  tick0: instrument.needle,
  tick1: instrument.accent,
  tick2: instrument.muted,
};

/**
 * 照片打底 —— 把用户实拍的罗盘照片作为盘底，矢量层叠在上面。
 *
 * 用途是**校准与还原**：让用户能看到"照片里的盘面"与"算法认出来的盘面"
 * 差多少，并手动把两者对齐（见校准页）。所以变换参数（旋转/缩放/平移）
 * 是**用户的调整量**，不是自动识别结果 —— 自动识别只给初始值。
 *
 * `opacity` 默认 0.5：不透明就看不见下面的矢量层，全透明则等于没打底。
 */
export interface CompassPhoto {
  uri: string;
  /** 照片相对盘面的旋转（度，顺时针） */
  rotation?: number;
  /** 相对盘面直径的缩放；1 = 铺满 */
  scale?: number;
  /** 平移（相对盘面半径的比例） */
  offsetX?: number;
  offsetY?: number;
  /** 照片不透明度 */
  opacity?: number;
}

export interface CompassDialProps {
  /** 外径 */
  size?: number;
  /** 盘体旋转量（度，顺时针为正）。0 = 盘面 0°（子）正对屏幕上方 */
  rotation?: number;
  /** 坐山索引（盘面角）；null = 未选 */
  sitting?: number | null;
  /** 实测角度（**盘面角**）。会在盘面上打一根朱红指针 */
  measuredDegree?: number | null;
  /** 是否可拖动旋转 / 点击选山 */
  interactive?: boolean;
  /** 拖动旋转时回调（自由跟手，不吸附；精确对齐交给外部微调按钮） */
  onRotate?: (rotation: number) => void;
  /** 点选山格时回调（传**盘面角**索引） */
  onSelectMountain?: (index: number) => void;
  /** 配色轨：light=暖色浅色盘（默认，既有页面）/ dark=深色仪器盘（罗盘域） */
  palette?: DialPalette;
  /**
   * 盘式：决定画哪些层、每层多宽。
   *
   * 默认 `'simple'` —— 即既有盘面的几何。**不要为了"更好看"改默认值**：
   * 既有调用方（确认坐向页）依赖这个默认，改了会静默改变它的盘面。
   * 新页面要更密的盘，显式传 `'zonghe'`。
   */
  style?: DialStyleId;
  /** 照片打底（校准与还原用）；null = 纯矢量盘 */
  photo?: CompassPhoto | null;
  /** 矢量层整体不透明度（照片打底时可调低，便于比对） */
  vectorOpacity?: number;
}

export function CompassDial({
  size = 280,
  rotation = 0,
  sitting = null,
  measuredDegree = null,
  interactive = false,
  onRotate,
  onSelectMountain,
  palette = DIAL_LIGHT,
  style = 'simple',
  photo = null,
  vectorOpacity = 1,
}: CompassDialProps): React.JSX.Element {
  // 实测宽高：容器与 SVG 不一致时拖动坐标会整体错位
  const [box, setBox] = useState<number>(size);
  const onLayout = useCallback((e: LayoutChangeEvent) => {
    const w = e.nativeEvent.layout.width;
    if (w > 0) setBox(w);
  }, []);

  // 盘式是脏数据容忍的：存档里可能存着已废弃的盘式名，不能让它把页面搞崩
  const dialStyle = coerceDialStyle(style);

  /**
   * 统一布局：`dialLayout` 给出与旧渲染路径完全一致的几何，
   * `renderLayers` 给出按盘式算出的层半径。两者共用同一个 box，
   * 故不会出现"外层按旧比例、内层按新比例"的错配。
   */
  const L = useMemo(() => dialLayout(box), [box]);
  const layers = useMemo(() => renderLayers(dialStyle, box), [dialStyle, box]);
  const ticks = useMemo(() => buildTicks(), []);
  const facing = sitting === null ? null : oppositeIndex(sitting);

  const radiusOf = useCallback(
    (id: Parameters<typeof layerRadius>[1]) => layerRadius(dialStyle, id, box),
    [dialStyle, box],
  );

  const poolRadius = radiusOf('pool') ?? { outer: L.pool, inner: 0, mid: L.pool / 2 };

  // ClipPath 的 id 必须唯一：同页多盘时若共用 id，后一个盘面的照片会裁进前一个
  const rawId = useId();
  const clipId = `dial-clip-${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;

  // ---- 手势：PanResponder 需要稳定的 handler，故用 ref 透传最新值 ----
  const rotationRef = useRef(rotation);
  rotationRef.current = rotation;
  const onRotateRef = useRef(onRotate);
  onRotateRef.current = onRotate;
  const onSelectRef = useRef(onSelectMountain);
  onSelectRef.current = onSelectMountain;
  const drag = useRef({ pointerDeg: 0, rotation: 0, moved: 0, x: 0, y: 0 });

  const pan = useMemo(
    () =>
      PanResponder.create({
        onStartShouldSetPanResponder: () => interactive,
        onMoveShouldSetPanResponder: () => interactive,
        onPanResponderGrant: (e) => {
          const { locationX, locationY } = e.nativeEvent;
          const deg = pointerAngle(L.center, { x: locationX, y: locationY });
          drag.current = {
            pointerDeg: deg,
            rotation: rotationRef.current,
            moved: 0,
            x: locationX,
            y: locationY,
          };
        },
        onPanResponderMove: (e) => {
          const { locationX, locationY } = e.nativeEvent;
          const s = drag.current;
          s.moved = Math.hypot(locationX - s.x, locationY - s.y);
          if (s.moved < TAP_SLOP) return; // 还在"按"的阶段，先不动盘
          const deg = pointerAngle(L.center, { x: locationX, y: locationY });
          // 用带符号差值跨越 360° 边界，否则过零点会跳一整圈
          onRotateRef.current?.(s.rotation + normalizeSigned(deg - s.pointerDeg));
        },
        onPanResponderRelease: (e) => {
          const s = drag.current;
          if (s.moved >= TAP_SLOP) return; // 是拖动，不是点选
          const { locationX, locationY } = e.nativeEvent;
          const dist = Math.hypot(locationX - L.center.x, locationY - L.center.y);
          // 点在环外空白 = 明确的无操作，不悄悄选中一格
          if (dist < L.mountainInner || dist > L.mountainOuter) return;
          const screenDeg = pointerAngle(L.center, { x: locationX, y: locationY });
          onSelectRef.current?.(degreeToIndex(dialDegreeAt(screenDeg, rotationRef.current)));
        },
        onPanResponderTerminationRequest: () => false,
      }),
    [interactive, L],
  );

  const { center } = L;
  const mountainRadius = radiusOf('mountain24');
  const houtianRadius = radiusOf('houtian');
  const xiantianRadius = radiusOf('xiantian');
  const fenjinRadius = radiusOf('fenjin');
  const dragonRadius = radiusOf('dragon');

  return (
    <View onLayout={onLayout} style={[styles.wrap, { width: size, height: size }]}>
      <Svg width={box} height={box}>
        <Defs>
          <ClipPath id={clipId}>
            <Circle cx={center.x} cy={center.y} r={L.rim - 1} />
          </ClipPath>
        </Defs>

        {/* ---------- 底盘 ---------- */}
        <Circle cx={center.x} cy={center.y} r={L.rim - 1} fill={palette.body} />

        {/* ---------- 照片打底（最底层，被矢量层盖住） ---------- */}
        {photo ? (
          <G clipPath={`url(#${clipId})`}>
            <PhotoLayer L={L} photo={photo} clipId={clipId} />
          </G>
        ) : null}

        <Circle
          cx={center.x}
          cy={center.y}
          r={L.rim - 1}
          stroke={palette.rim}
          strokeWidth={2.5}
          fill="none"
        />
        <Circle
          cx={center.x}
          cy={center.y}
          r={L.rim - 5}
          stroke={palette.hairline}
          strokeWidth={0.8}
          fill="none"
        />

        {/* ---------- 随盘旋转的整体（各层 / 十字线 / 实测针） ---------- */}
        <G transform={`rotate(${rotation} ${center.x} ${center.y})`} opacity={vectorOpacity}>
          {fenjinRadius ? (
            <TickBand center={center} radius={fenjinRadius} ticks={ticks} palette={palette} />
          ) : null}

          {mountainRadius ? (
            <MountainBand
              center={center}
              radius={mountainRadius}
              sitting={sitting}
              facing={facing}
              palette={palette}
            />
          ) : null}

          {houtianRadius ? (
            <TrigramBand
              center={center}
              radius={houtianRadius}
              trigrams={TRIGRAM_HOUTIAN}
              color={palette.trigram}
              palette={palette}
            />
          ) : null}

          {dragonRadius ? (
            <DragonBand center={center} radius={dragonRadius} palette={palette} />
          ) : null}

          {xiantianRadius ? (
            <TrigramBand
              center={center}
              radius={xiantianRadius}
              trigrams={TRIGRAM_XIANTIAN}
              color={palette.trigramXiantian}
              palette={palette}
            />
          ) : null}

          {/* 天池外圈与十字红线（刻在盘体上，随盘转） */}
          <Circle cx={center.x} cy={center.y} r={poolRadius.outer} fill={palette.pool} />
          <G opacity={0.7}>
            <Line
              x1={center.x}
              y1={center.y - poolRadius.outer}
              x2={center.x}
              y2={center.y + poolRadius.outer}
              stroke={palette.measured}
              strokeWidth={0.7}
            />
            <Line
              x1={center.x - poolRadius.outer}
              y1={center.y}
              x2={center.x + poolRadius.outer}
              y2={center.y}
              stroke={palette.measured}
              strokeWidth={0.7}
            />
          </G>
          <Circle
            cx={center.x}
            cy={center.y}
            r={poolRadius.outer}
            stroke={palette.rim}
            strokeWidth={1.2}
            fill="none"
          />

          {/* 实测角指针：只作视觉提示，不改写任何选择 */}
          {measuredDegree !== null && mountainRadius ? (
            <MeasuredNeedle
              center={center}
              degree={measuredDegree}
              fromRadius={mountainRadius.inner}
              poolRadius={poolRadius.outer}
              palette={palette}
            />
          ) : null}
        </G>

        {/* ---------- 磁针（不随盘转：屏幕上方恒为真北） ---------- */}
        <MagnetNeedle center={center} poolRadius={poolRadius.outer} palette={palette} />
      </Svg>

      {/* 手势层放在 SVG 之上、且透明 */}
      {interactive ? (
        <View
          {...pan.panHandlers}
          style={StyleSheet.absoluteFill}
          accessibilityRole="adjustable"
          accessibilityLabel="罗盘盘面，可拖动旋转、点按选择坐山"
        />
      ) : null}
    </View>
  );
}

// ==========================================================================
// 照片打底
// ==========================================================================

/**
 * 照片层。
 *
 * 变换顺序（从左到右作用于坐标系）：先平移回原点 → 旋转 → 缩放 → 移回中心。
 * 顺序写反会出现"缩放把旋转后的偏移也放大了"这类错位 ——
 * 单看照片仍然是一张正常照片，只有与矢量层比对时才发现对不齐。
 */
function PhotoLayer({
  L,
  photo,
}: {
  L: ReturnType<typeof dialLayout>;
  photo: CompassPhoto;
  clipId: string;
}): React.JSX.Element {
  const { center } = L;
  const r = L.rim - 1;
  const scale = photo.scale ?? 1;
  const rot = photo.rotation ?? 0;
  const dx = (photo.offsetX ?? 0) * r;
  const dy = (photo.offsetY ?? 0) * r;
  return (
    <SvgImage
      x={center.x - r}
      y={center.y - r}
      width={r * 2}
      height={r * 2}
      opacity={photo.opacity ?? 0.5}
      preserveAspectRatio="xMidYMid slice"
      href={{ uri: photo.uri }}
      transform={`translate(${center.x + dx} ${center.y + dy}) rotate(${rot}) scale(${scale}) translate(${-center.x} ${-center.y})`}
    />
  );
}

// ==========================================================================
// 二十四山环
// ==========================================================================

function MountainBand({
  center,
  radius,
  sitting,
  facing,
  palette,
}: {
  center: { x: number; y: number };
  radius: { outer: number; inner: number; mid: number };
  sitting: number | null;
  facing: number | null;
  palette: DialPalette;
}): React.JSX.Element {
  const width = radius.outer - radius.inner;
  // 字号随层宽缩放（层数越多层越窄）。下限 6px：再小就是一团墨点，
  // 不如让它略溢出层带 —— 宁可挤，不可糊。
  const fontSize = Math.max(6, width * 0.58);
  return (
    <G>
      {MOUNTAIN_NAMES.map((_, i) => {
        const role = mountainRole(i);
        const isSitting = i === sitting;
        const isFacing = i === facing;
        // 坐山最重、向山次重、四正淡朱、四维淡蓝、其余留白
        const fill = isSitting
          ? palette.sittingFill
          : isFacing
            ? palette.facingFill
            : role === 'cardinal'
              ? palette.cardinalSoft
              : role === 'corner'
                ? palette.cornerSoft
                : palette.plainFill;
        return (
          <Path
            key={`m-${i}`}
            d={sectorPathOfIndex(center, radius.inner, radius.outer, i, SECTOR_GAP_DEG)}
            fill={fill}
            stroke={palette.sectorStroke}
            strokeWidth={0.8}
          />
        );
      })}

      {MOUNTAIN_NAMES.map((name, i) => {
        const deg = indexToDegree(i);
        const p = pointOnCircle(center, radius.mid, deg);
        const role = mountainRole(i);
        const isSitting = i === sitting;
        const isFacing = i === facing;
        const fill = isSitting
          ? palette.sittingText
          : isFacing
            ? palette.facingText
            : role === 'cardinal'
              ? palette.cardinalText
              : role === 'corner'
                ? palette.cornerText
                : palette.plainText;
        return (
          <G key={`mt-${i}`} transform={`rotate(${deg} ${p.x} ${p.y})`}>
            <SvgText
              x={p.x}
              y={p.y}
              fill={fill}
              fontSize={fontSize}
              fontWeight={isSitting || isFacing || role !== 'branch' ? '700' : '500'}
              textAnchor="middle"
              alignmentBaseline="central"
            >
              {name}
            </SvgText>
          </G>
        );
      })}
    </G>
  );
}

// ==========================================================================
// 八卦环（先后天共用）
// ==========================================================================

/**
 * 八卦环。先后天共用本组件，只用 `trigrams` 与 `color` 区分。
 *
 * ⚠️ 先后天是**两套方位**：同一卦在两张表里落点不同（八个卦无一重合）。
 * 共用组件是安全的（几何逻辑确实一样），但**共用数据表是错的** ——
 * 那会让每个卦都错位、而画面仍是一圈标准八卦图。
 * 守卫见 `tests/mobile/test_dial_style.py::test_xiantian_never_shares_a_direction_with_houtian`。
 */
function TrigramBand({
  center,
  radius,
  trigrams,
  color,
  palette,
}: {
  center: { x: number; y: number };
  radius: { outer: number; inner: number; mid: number };
  trigrams: readonly { readonly name: string; readonly centerDegree: number; readonly yao: readonly number[] }[];
  color: string;
  palette: DialPalette;
}): React.JSX.Element {
  const width = radius.outer - radius.inner;
  // 三爻在径向占满层带：3 条线 + 2 个间隔 = 2·gap + 3·stroke
  const gap = Math.max(2, width * 0.37);
  const strokeWidth = Math.max(0.7, width * 0.11);
  const yaoWidth = Math.max(4, width * 0.62);
  return (
    <G>
      <Circle cx={center.x} cy={center.y} r={radius.outer} stroke={palette.hairline} strokeWidth={0.8} fill="none" />
      <Circle cx={center.x} cy={center.y} r={radius.inner} stroke={palette.hairline} strokeWidth={0.8} fill="none" />
      {trigrams.map((t) => {
        const p = pointOnCircle(center, radius.mid, t.centerDegree);
        return (
          <G key={t.name} transform={`rotate(${t.centerDegree} ${p.x} ${p.y})`}>
            <TrigramYao
              x={p.x}
              y={p.y}
              yao={t.yao}
              color={color}
              width={yaoWidth}
              gap={gap}
              strokeWidth={strokeWidth}
            />
          </G>
        );
      })}
    </G>
  );
}

/** 三爻卦符：阳爻一整条、阴爻断成两截。`yao` 自下而上（初爻在前） */
function TrigramYao({
  x,
  y,
  yao,
  color,
  width,
  gap,
  strokeWidth,
}: {
  x: number;
  y: number;
  yao: readonly number[];
  color: string;
  width: number;
  gap: number;
  strokeWidth: number;
}): React.JSX.Element {
  const mid = (yao.length - 1) / 2;
  return (
    <G>
      {yao.map((v, i) => {
        // 初爻在最下：屏幕 y 向下，故需要反向
        const yy = y + (mid - i) * gap;
        if (v === 1) {
          return (
            <Line
              key={i}
              x1={x - width}
              y1={yy}
              x2={x + width}
              y2={yy}
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
            />
          );
        }
        return (
          <G key={i}>
            <Line
              x1={x - width}
              y1={yy}
              x2={x - width * 0.26}
              y2={yy}
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
            />
            <Line
              x1={x + width * 0.26}
              y1={yy}
              x2={x + width}
              y2={yy}
              stroke={color}
              strokeWidth={strokeWidth}
              strokeLinecap="round"
            />
          </G>
        );
      })}
    </G>
  );
}

// ==========================================================================
// 内圈细分刻度环
// ==========================================================================

/**
 * 只画线不写字的细分环。
 *
 * 为什么不着字：实物罗盘在这个位置通常是七十二龙或二十八宿，但仓库里
 * **没有这两张数据表**。画刻度是纯几何（不声称任何术数含义），
 * 写字则是编造内容 —— 前者可做，后者不做（RULE-008）。
 */
function DragonBand({
  center,
  radius,
  palette,
}: {
  center: { x: number; y: number };
  radius: { outer: number; inner: number; mid: number };
  palette: DialPalette;
}): React.JSX.Element {
  // 每 3° 一格，与分金同制；只画长短两种，避免在窄层里糊成一片
  const span = radius.outer - radius.inner;
  const out: React.JSX.Element[] = [];
  for (let deg = 0; deg < 360; deg += 3) {
    const isMajor = deg % 15 === 0;
    const from = pointOnCircle(center, radius.outer, deg);
    const to = pointOnCircle(center, radius.outer - span * (isMajor ? 1 : 0.55), deg);
    out.push(
      <Line
        key={deg}
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        stroke={isMajor ? palette.tick1 : palette.tick2}
        strokeWidth={isMajor ? 1 : 0.6}
      />,
    );
  }
  return (
    <G>
      <Circle cx={center.x} cy={center.y} r={radius.outer} stroke={palette.hairline} strokeWidth={0.8} fill="none" />
      <Circle cx={center.x} cy={center.y} r={radius.inner} stroke={palette.hairline} strokeWidth={0.8} fill="none" />
      {out}
    </G>
  );
}

// ==========================================================================
// 一百二十分金刻度环
// ==========================================================================

const TICK_STYLE_KEYS: Record<TickLevel, 'tick0' | 'tick1' | 'tick2'> = {
  0: 'tick0',
  1: 'tick1',
  2: 'tick2',
};

const TICK_WIDTH: Record<TickLevel, number> = { 0: 1.6, 1: 1.1, 2: 0.7 };

function TickBand({
  center,
  radius,
  ticks,
  palette,
}: {
  center: { x: number; y: number };
  radius: { outer: number; inner: number; mid: number };
  ticks: ReturnType<typeof buildTicks>;
  palette: DialPalette;
}): React.JSX.Element {
  const span = radius.outer - radius.inner;
  return (
    <G>
      <Circle cx={center.x} cy={center.y} r={radius.outer} stroke={palette.hairline} strokeWidth={0.8} fill="none" />
      <Circle cx={center.x} cy={center.y} r={radius.inner} stroke={palette.hairline} strokeWidth={0.8} fill="none" />
      {ticks.map((t) => {
        const from = pointOnCircle(center, radius.outer, t.degree);
        const to = pointOnCircle(center, radius.outer - span * TICK_LENGTH_RATIO[t.level], t.degree);
        return (
          <Line
            key={t.degree}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            stroke={palette[TICK_STYLE_KEYS[t.level]]}
            strokeWidth={TICK_WIDTH[t.level]}
            strokeLinecap="butt"
          />
        );
      })}
    </G>
  );
}

// ==========================================================================
// 天池磁针 与 实测指针
// ==========================================================================

/** 磁针：红头指北（屏幕上方）、蓝尾指南。**不随盘体旋转** */
function MagnetNeedle({
  center,
  poolRadius,
  palette,
}: {
  center: { x: number; y: number };
  poolRadius: number;
  palette: DialPalette;
}): React.JSX.Element {
  const len = poolRadius * 0.82;
  const halfW = poolRadius * 0.16;
  return (
    <G opacity={0.92}>
      <Path
        d={`M ${center.x} ${center.y - len} L ${center.x + halfW} ${center.y} L ${center.x - halfW} ${center.y} Z`}
        fill={palette.needleNorth}
      />
      <Path
        d={`M ${center.x} ${center.y + len} L ${center.x + halfW} ${center.y} L ${center.x - halfW} ${center.y} Z`}
        fill={palette.needleSouth}
      />
      <Circle cx={center.x} cy={center.y} r={poolRadius * 0.1} fill={palette.poolDot} />
    </G>
  );
}

/** 实测角指针：一根从山环内缘伸向天池的朱红细针（位于旋转组内，故用**盘面角**） */
function MeasuredNeedle({
  center,
  degree,
  fromRadius,
  poolRadius,
  palette,
}: {
  center: { x: number; y: number };
  degree: number;
  fromRadius: number;
  poolRadius: number;
  palette: DialPalette;
}): React.JSX.Element {
  const outer = pointOnCircle(center, fromRadius, degree);
  const inner = pointOnCircle(center, poolRadius, degree);
  return (
    <G>
      <Line
        x1={outer.x}
        y1={outer.y}
        x2={inner.x}
        y2={inner.y}
        stroke={palette.measured}
        strokeWidth={2}
        strokeLinecap="round"
      />
      <Circle cx={outer.x} cy={outer.y} r={2.6} fill={palette.measured} />
    </G>
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: 'center', justifyContent: 'center', alignItems: 'center' },
});

export { rotationToAlign, nameOfIndex, oppositeIndex, degreeToIndex };
