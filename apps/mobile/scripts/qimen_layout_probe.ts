/**
 * 奇门九宫摆位探针 —— 把 `qimenLayout.ts` 的两张表导出成 JSON，
 * 供 Python 侧与内核宫殿的 `direction` 做**跨来源一致性校验**
 * （见 `tests/mobile/test_qimen_layout.py`）。
 *
 * 为什么需要这道校验：
 * 洛书摆位写错**不会报错** —— 九宫一个不少地渲染出来，只是方位整体错位，
 * 用户照着看会得到方向完全错误的结论。而它又只存在于前端，
 * 内核不知道前端把哪个宫摆在了哪里，所以只能把表抽出来单独核。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/qimen_layout_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除。
 */

import { QIMEN_GRID, QIMEN_GRID_DIRECTION } from '../src/lib/qimenLayout.ts';

console.log(
  JSON.stringify({
    grid: QIMEN_GRID,
    direction: QIMEN_GRID_DIRECTION,
  }),
);
