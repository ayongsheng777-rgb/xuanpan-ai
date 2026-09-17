/**
 * 罗盘盘面仿真 —— 按真实罗盘形制绘制，且**数据驱动**。
 *
 * 与"只画一圈山格的简易选择器"的区别（两者不可互相替代）：
 *   - 简易选择器为「点一下选对宫」而优化：环带刻意做厚、格子刻意做大，
 *     因为它的唯一任务是让手指点得准。
 *   - `CompassDial` 是**盘面本身**：按实物罗盘的层次绘制（二十四山 / 后天八卦 /
 *     一百二十分金刻度 / 天池磁针），并且可以整体旋转、可以点选取山。
 *     它要解决的不是"点得准"，而是"让用户一眼看出盘面排位与自己手里的罗盘是否一致"——
 *     这一条是识别结果能被信任的前提，也是本组件存在的理由。
 *
 * 三个语义约定（错了就会给出"看起来对"的错误盘面）：
 *   1. **屏幕正上方恒为真北**。磁针永远指向屏幕上方，不随盘面旋转 ——
 *      实物罗盘上转的是盘体，磁针始终指北。反过来画会让人以为罗盘坏了。
 *   2. **rotation 是盘体的旋转量**（顺时针为正）。盘面角 θ 的显示位置 = θ + rotation。
 *   3. **坐山 / 向山 / 实测角都存盘面角**，不存屏幕角。这样旋转盘面不会
 *      悄悄改变"用户选的是哪座山"——旋转是视角，选择是事实。
 *
 * `[待验证]` 红/蓝/墨的盘面角色配色属盘式流派（各版罗盘分色不同），
 * 仅影响视觉识别，不参与任何术数计算（见 `lib/compassDial`）。
 */

import React, { useCallback, useMemo, useRef, useState } from 'react';
import {
  PanResponder,
  StyleSheet,
  View,
  type LayoutChangeEvent,
} from 'react-native';
import Svg, { Circle, G, Line, Path, Text as SvgText } from 'react-native-svg';

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
  MOUNTAIN_NAMES,
  degreeToIndex,
  indexToDegree,
  nameOfIndex,
  oppositeIndex,
  pointOnCircle,
  sectorPathOfIndex,
} from '@/lib/ring24';
import { alpha, brand, colors } from '@/theme/tokens';

/** 拖动与点击的判别阈值（像素）：位移小于它才算"点了一下" */
const TAP_SLOP = 8;
/** 相邻山格之间的视觉缝隙（度） */
const SECTOR_GAP_DEG = 0.6;

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
}

export function CompassDial({
  size = 280,
  rotation = 0,
  sitting = null,
  measuredDegree = null,
  interactive = false,
  onRotate,
  onSelectMountain,
}: CompassDialProps): React.JSX.Element {
  // 实测宽高：容器与 SVG 不一致时拖动坐标会整体错位
  const [box, setBox] = useState<number>(size);
  const onLayout = useCallback((e: LayoutChangeEvent) => {
    const w = e.nativeEvent.layout.width;
    if (w > 0) setBox(w);
  }, []);

  const L = useMemo(() => dialLayout(box), [box]);
  const ticks = useMemo(() => buildTicks(), []);
  const facing = sitting === null ? null : oppositeIndex(sitting);

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

  return (
    <View onLayout={onLayout} style={[styles.wrap, { width: size, height: size }]}>
      <Svg width={box} height={box}>
        {/* ---------- 底盘 ---------- */}
        <Circle cx={center.x} cy={center.y} r={L.rim - 1} fill={colors.sand} />
        <Circle
          cx={center.x}
          cy={center.y}
          r={L.rim - 1}
          stroke={brand.gold}
          strokeWidth={2.5}
          fill="none"
        />
        <Circle
          cx={center.x}
          cy={center.y}
          r={L.rim - 5}
          stroke={alpha.primaryBorder}
          strokeWidth={0.8}
          fill="none"
        />

        {/* ---------- 随盘旋转的整体（山 / 八卦 / 刻度 / 十字线） ---------- */}
        <G transform={`rotate(${rotation} ${center.x} ${center.y})`}>
          <MountainBand L={L} sitting={sitting} facing={facing} />
          <TrigramBand L={L} />
          <TickBand L={L} ticks={ticks} />

          {/* 天池外圈与十字红线（刻在盘体上，随盘转） */}
          <Circle cx={center.x} cy={center.y} r={L.pool} fill={colors.surface} />
          <G opacity={0.7}>
            <Line
              x1={center.x}
              y1={center.y - L.pool}
              x2={center.x}
              y2={center.y + L.pool}
              stroke={colors.cinnabar}
              strokeWidth={0.7}
            />
            <Line
              x1={center.x - L.pool}
              y1={center.y}
              x2={center.x + L.pool}
              y2={center.y}
              stroke={colors.cinnabar}
              strokeWidth={0.7}
            />
          </G>
          <Circle
            cx={center.x}
            cy={center.y}
            r={L.pool}
            stroke={brand.gold}
            strokeWidth={1.2}
            fill="none"
          />

          {/* 实测角指针：只作视觉提示，不改写任何选择 */}
          {measuredDegree !== null ? (
            <MeasuredNeedle L={L} degree={measuredDegree} />
          ) : null}
        </G>

        {/* ---------- 磁针（不随盘转：屏幕上方恒为真北） ---------- */}
        <MagnetNeedle L={L} />
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
// 二十四山环
// ==========================================================================

function MountainBand({
  L,
  sitting,
  facing,
}: {
  L: ReturnType<typeof dialLayout>;
  sitting: number | null;
  facing: number | null;
}): React.JSX.Element {
  return (
    <G>
      {MOUNTAIN_NAMES.map((_, i) => {
        const role = mountainRole(i);
        const isSitting = i === sitting;
        const isFacing = i === facing;
        // 坐山最重、向山次重、四正淡朱、四维淡蓝、其余留白
        const fill = isSitting
          ? colors.primary
          : isFacing
            ? brand.gold
            : role === 'cardinal'
              ? alpha.cinnabarSoft
              : role === 'corner'
                ? alpha.primarySoft
                : colors.sand;
        return (
          <Path
            key={`m-${i}`}
            d={sectorPathOfIndex(L.center, L.mountainInner, L.mountainOuter, i, SECTOR_GAP_DEG)}
            fill={fill}
            stroke={alpha.goldSoft}
            strokeWidth={0.8}
          />
        );
      })}

      {MOUNTAIN_NAMES.map((name, i) => {
        const deg = indexToDegree(i);
        const p = pointOnCircle(L.center, L.labelRadius, deg);
        const role = mountainRole(i);
        const isSitting = i === sitting;
        const isFacing = i === facing;
        const fill = isSitting
          ? colors.onPrimary
          : isFacing
            ? colors.primary
            : role === 'cardinal'
              ? colors.cinnabar
              : role === 'corner'
                ? colors.primary
                : colors.text;
        return (
          <G key={`mt-${i}`} transform={`rotate(${deg} ${p.x} ${p.y})`}>
            <SvgText
              x={p.x}
              y={p.y}
              fill={fill}
              fontSize={L.mountainOuter * 0.115}
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
// 后天八卦环（自绘爻线，不依赖字体里的 ☰☱… ）
// ==========================================================================

function TrigramBand({ L }: { L: ReturnType<typeof dialLayout> }): React.JSX.Element {
  return (
    <G>
      <Circle
        cx={L.center.x}
        cy={L.center.y}
        r={L.trigramOuter}
        stroke={alpha.primaryBorder}
        strokeWidth={0.8}
        fill="none"
      />
      <Circle
        cx={L.center.x}
        cy={L.center.y}
        r={L.trigramInner}
        stroke={alpha.primaryBorder}
        strokeWidth={0.8}
        fill="none"
      />
      {TRIGRAM_HOUTIAN.map((t) => {
        const p = pointOnCircle(L.center, L.trigramRadius, t.centerDegree);
        return (
          <G key={t.name} transform={`rotate(${t.centerDegree} ${p.x} ${p.y})`}>
            <TrigramYao
              x={p.x}
              y={p.y}
              yao={t.yao}
              color={colors.jade}
              width={L.trigramOuter * 0.14}
              gap={L.trigramOuter * 0.075}
              strokeWidth={1.6}
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
// 一百二十分金刻度环
// ==========================================================================

const TICK_STYLE: Record<TickLevel, { color: string; width: number }> = {
  0: { color: colors.cinnabar, width: 1.6 },
  1: { color: colors.primary, width: 1.1 },
  2: { color: colors.muted, width: 0.7 },
};

function TickBand({
  L,
  ticks,
}: {
  L: ReturnType<typeof dialLayout>;
  ticks: ReturnType<typeof buildTicks>;
}): React.JSX.Element {
  const span = L.tickOuter - L.tickInner;
  return (
    <G>
      <Circle
        cx={L.center.x}
        cy={L.center.y}
        r={L.tickOuter}
        stroke={alpha.primaryBorder}
        strokeWidth={0.8}
        fill="none"
      />
      <Circle
        cx={L.center.x}
        cy={L.center.y}
        r={L.tickInner}
        stroke={alpha.primaryBorder}
        strokeWidth={0.8}
        fill="none"
      />
      {ticks.map((t) => {
        const style = TICK_STYLE[t.level];
        const from = pointOnCircle(L.center, L.tickOuter, t.degree);
        const to = pointOnCircle(L.center, L.tickInner + span * (1 - TICK_LENGTH_RATIO[t.level]), t.degree);
        return (
          <Line
            key={t.degree}
            x1={from.x}
            y1={from.y}
            x2={to.x}
            y2={to.y}
            stroke={style.color}
            strokeWidth={style.width}
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

/** 磁针：红头指北（屏幕上方）、深蓝尾指南。**不随盘体旋转** */
function MagnetNeedle({ L }: { L: ReturnType<typeof dialLayout> }): React.JSX.Element {
  const { center } = L;
  const len = L.pool * 0.82;
  const halfW = L.pool * 0.16;
  return (
    <G opacity={0.92}>
      <Path
        d={`M ${center.x} ${center.y - len} L ${center.x + halfW} ${center.y} L ${center.x - halfW} ${center.y} Z`}
        fill={colors.cinnabar}
      />
      <Path
        d={`M ${center.x} ${center.y + len} L ${center.x + halfW} ${center.y} L ${center.x - halfW} ${center.y} Z`}
        fill={colors.primary}
      />
      <Circle cx={center.x} cy={center.y} r={L.pool * 0.1} fill={brand.gold} />
    </G>
  );
}

/** 实测角指针：一根从刻度环伸向天池的朱红细针（位于旋转组内，故用**盘面角**） */
function MeasuredNeedle({
  L,
  degree,
}: {
  L: ReturnType<typeof dialLayout>;
  degree: number;
}): React.JSX.Element {
  const outer = pointOnCircle(L.center, L.mountainInner, degree);
  const inner = pointOnCircle(L.center, L.pool, degree);
  return (
    <G>
      <Line
        x1={outer.x}
        y1={outer.y}
        x2={inner.x}
        y2={inner.y}
        stroke={colors.cinnabar}
        strokeWidth={2}
        strokeLinecap="round"
      />
      <Circle cx={outer.x} cy={outer.y} r={2.6} fill={colors.cinnabar} />
    </G>
  );
}

const styles = StyleSheet.create({
  wrap: { alignSelf: 'center', justifyContent: 'center', alignItems: 'center' },
});

export { rotationToAlign, nameOfIndex, oppositeIndex, degreeToIndex };
