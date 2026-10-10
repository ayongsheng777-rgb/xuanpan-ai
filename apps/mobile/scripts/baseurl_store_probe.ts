/**
 * baseUrlStore 探针 —— 把后端地址持久化逻辑的真实行为导出成 JSON，
 * 供 Python 侧做**行为级校验**（见 `tests/mobile/test_api_baseurl_persist.py`）。
 *
 * 为什么需要真跑而不是扫源码：BUG 1（2026-10-08 用户实报）的本质是
 * "改了地址但重启就丢" —— 扫源码只能证明"写了 setItem 这行字"，
 * 证明不了"读回来的确实是写进去的那个"。本探针用内存假存储，
 * 真正走一遍 存 → 读 → 覆盖 → 清除 的完整链路。
 *
 * 运行方式（Node ≥ 22.6，需显式开启类型擦除）：
 *   node --experimental-strip-types apps/mobile/scripts/baseurl_store_probe.ts
 *
 * 注意：本文件**故意**用 `.ts` 后缀导入（Node ESM 要求显式扩展名），
 * 因此已在 `tsconfig.json` 的 `exclude` 里排除，避免 tsc 报
 * "import path can only end with .ts when allowImportingTsExtensions is enabled"。
 */

import {
  API_URL_OVERRIDE_KEY,
  clearApiBaseUrlOverride,
  loadApiBaseUrlOverride,
  saveApiBaseUrlOverride,
  type KeyValueStorage,
} from '../src/api/baseUrlStore.ts';

/** 内存假存储 —— 行为对标 AsyncStorage 的异步键值语义。 */
function memoryStorage(): KeyValueStorage & { dump(): Record<string, string> } {
  const map = new Map<string, string>();
  return {
    async getItem(key: string): Promise<string | null> {
      return map.has(key) ? map.get(key)! : null;
    },
    async setItem(key: string, value: string): Promise<void> {
      map.set(key, value);
    },
    async removeItem(key: string): Promise<void> {
      map.delete(key);
    },
    dump() {
      return Object.fromEntries(map);
    },
  };
}

/** 永远抛错的坏存储 —— 验证"存储坏了也不炸"。 */
const brokenStorage: KeyValueStorage = {
  async getItem(): Promise<string | null> {
    throw new Error('disk gone');
  },
  async setItem(): Promise<void> {
    throw new Error('disk gone');
  },
  async removeItem(): Promise<void> {
    throw new Error('disk gone');
  },
};

async function main(): Promise<void> {
  const out: Record<string, unknown> = { key: API_URL_OVERRIDE_KEY };
  const store = memoryStorage();

  // 1. 空存储读出来是 null（没有覆盖值）
  out['empty_read_is_null'] = (await loadApiBaseUrlOverride(store)) === null;

  // 2. 存一个地址，读回来是同一个（去尾斜杠规范化）
  await saveApiBaseUrlOverride(store, 'http://192.168.1.10:8360///');
  out['roundtrip'] = await loadApiBaseUrlOverride(store);
  out['stored_raw'] = store.dump()[API_URL_OVERRIDE_KEY];

  // 3. 覆盖写入：后写的赢
  await saveApiBaseUrlOverride(store, 'http://10.0.0.5:8360');
  out['overwrite'] = await loadApiBaseUrlOverride(store);

  // 4. 清除后读出来是 null
  await clearApiBaseUrlOverride(store);
  out['after_clear_is_null'] = (await loadApiBaseUrlOverride(store)) === null;

  // 5. 存进去的是空字符串 → 当作没有（不返回空地址）
  await saveApiBaseUrlOverride(store, '   ');
  out['blank_is_null'] = (await loadApiBaseUrlOverride(store)) === null;

  // 6. 存储坏了：读不抛、返回 null；清除不抛
  let readThrew = false;
  try {
    const v = await loadApiBaseUrlOverride(brokenStorage);
    out['broken_read_is_null'] = v === null;
  } catch {
    readThrew = true;
  }
  out['broken_read_threw'] = readThrew;
  let clearThrew = false;
  try {
    await clearApiBaseUrlOverride(brokenStorage);
  } catch {
    clearThrew = true;
  }
  out['broken_clear_threw'] = clearThrew;

  console.log(JSON.stringify(out));
}

await main();
