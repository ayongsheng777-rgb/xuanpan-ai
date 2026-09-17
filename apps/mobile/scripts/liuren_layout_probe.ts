/**
 * 六壬十二宫方图摆位探针 —— 把 `liurenLayout.ts` 的几张表导出成 JSON，
 * 供 Python 侧做**跨来源一致性校验**（见 `tests/mobile/test_liuren_layout.py`）。
 *
 * 为什么需要这道校验：
 * 方图摆位写错**不会报错** —— 十二宫一个不少地渲染出来，只是整体镜像或错位，
 * 用户照着看会得到方向完全错误的判断。而它又只存在于前端，
 * 内核只会按地支给数据、不知道前端把哪一支画在了哪一格，所以只能把表抽出来单独核。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/liuren_layout_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除。
 */

import {
  LIUREN_GRID,
  LIUREN_GRID_COLUMNS,
  LIUREN_RING_CLOCKWISE,
  LIUREN_ZHI,
} from '../src/lib/liurenLayout.ts';

console.log(
  JSON.stringify({
    grid: LIUREN_GRID,
    ring: LIUREN_RING_CLOCKWISE,
    zhi: LIUREN_ZHI,
    columns: LIUREN_GRID_COLUMNS,
  }),
);
