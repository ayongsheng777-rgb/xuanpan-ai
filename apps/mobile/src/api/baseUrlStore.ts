/**
 * 后端地址的人工覆盖值 —— 存手机本地（AsyncStorage），不上服务端。
 *
 * 为什么要单独一个模块：`client.ts` 里 `setApiBaseUrl` 原来只换内存里的
 * 单例，App 重启就丢 —— 用户在「我的 → 网络线路」里改的地址**存不住**
 * （2026-10-08 用户实报 BUG）。持久化逻辑是纯的（读写一个 key），
 * 与 RN 运行时无关，所以抽到这里，用可注入的存储后端，真跑测试
 * （见 `tests/mobile/test_api_baseurl_persist.py`）。
 *
 * 约定：
 * - 有人工覆盖值时，它**永远优先**于启动自动探活 —— 用户亲手设的地址，
 *   不能被一次静默的自动切线覆盖掉，否则就是同一个 BUG 的另一种形态。
 * - 读写失败不抛异常：存盘失败时内存里的地址已经生效，不能因此报错；
 *   读盘失败时当作"没有覆盖值"，走原来的自动探活。
 */

export const API_URL_OVERRIDE_KEY = '@xuanpan:api_base_url';

/** 最小的键值存储面 —— AsyncStorage 天然满足，测试时用内存假实现。 */
export interface KeyValueStorage {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

/** 读出用户手设的后端地址；没有或读失败返回 null。 */
export async function loadApiBaseUrlOverride(
  storage: KeyValueStorage,
): Promise<string | null> {
  try {
    const raw = await storage.getItem(API_URL_OVERRIDE_KEY);
    const url = (raw ?? '').trim().replace(/\/+$/, '');
    return url ? url : null;
  } catch {
    return null;
  }
}

/** 存下用户手设的后端地址。调用方自行决定是否吞掉异常。 */
export async function saveApiBaseUrlOverride(
  storage: KeyValueStorage,
  url: string,
): Promise<void> {
  await storage.setItem(API_URL_OVERRIDE_KEY, url.trim().replace(/\/+$/, ''));
}

/** 清掉人工覆盖值 —— 「恢复默认」按钮用。 */
export async function clearApiBaseUrlOverride(
  storage: KeyValueStorage,
): Promise<void> {
  try {
    await storage.removeItem(API_URL_OVERRIDE_KEY);
  } catch {
    // 删不掉也不报错：下次启动读到的仍是旧值，用户会再看到它，
    // 比"点了恢复默认却静默失败"诚实 —— 界面会显示当前实际生效的地址。
  }
}
