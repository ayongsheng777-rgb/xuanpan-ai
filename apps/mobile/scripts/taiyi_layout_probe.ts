/**
 * 太乙八宫盘摆位探针 —— 把 `taiyiLayout.ts` 的几张表导出成 JSON，
 * 供 Python 侧做**跨来源一致性校验**（见 `tests/mobile/test_taiyi_layout.py`）。
 *
 * 为什么需要这道校验：
 * 太乙宫号与洛书**逐宫错位**，摆位表写错（尤其复用奇门的洛书表）**不会报错** ——
 * 八宫一个不少地渲染出来，只是每宫的卦/方位/门整体错位，用户照着看会得到
 * 方向完全错误的判断。而它又只存在于前端，内核只按宫号给数据、
 * 不知道前端把哪一宫画在了哪一格，所以只能把表抽出来单独核。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/taiyi_layout_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除。
 */

import {
  TAIYI_GRID,
  TAIYI_GRID_COLUMNS,
  TAIYI_GRID_DIRECTION,
  TAIYI_PALACES,
} from '../src/lib/taiyiLayout.ts';

console.log(
  JSON.stringify({
    grid: TAIYI_GRID,
    direction: TAIYI_GRID_DIRECTION,
    palaces: TAIYI_PALACES,
    columns: TAIYI_GRID_COLUMNS,
  }),
);
