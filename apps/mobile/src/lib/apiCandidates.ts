/**
 * 后端候选地址的选择逻辑。
 *
 * 为什么单列成一个**不含 React Native 依赖**的文件：
 * 这段逻辑决定「APP 能不能连上后端」，是整条链路的第一道门，必须能被单元测试
 * 真跑（RULE-007）。而它天然要读 expo-constants 与构建期内联常量 —— 一旦写在
 * `client.ts` 里，就再也没法在裸 node 下加载，"测过了"只能靠人工点页面。
 * 纯逻辑抽到这里后，由 `tests/mobile/test_api_candidates.py` 真跑，
 * 「连不上」这件事终于有了会红的地方。
 *
 * 三件事分得很清，读环境变量 / expo-constants 的动作留在 client.ts：
 *
 * | 函数 | 职责 |
 * |---|---|
 * | `normalizeCandidateUrls` | 一串文本 → 规范地址表（去重保序） |
 * | `mergeCandidateSources` | 多个来源按优先级合并成一张表 |
 * | `pickFirstReachable`   | 并发探活，取第一个回应的 |
 */

/** 规范化单个地址：去空白、去尾部斜杠。非法项返回 null（**丢弃而非报错**）。 */
function normalizeOne(part: string): string | null {
  const url = part.trim().replace(/\/+$/, '');
  if (!url) return null;
  if (!/^https?:\/\//.test(url)) return null;
  return url;
}

/**
 * 把「逗号分隔的候选地址串」规范化成有序、去重的地址表。
 *
 * 丢弃而非报错是刻意的：这张表来自构建期注入，一个手滑写错的地址若让整个 APP
 * 起不来，比"少一个候选"糟糕得多 —— 而且真机上连日志都看不到。
 *
 * ⚠️ `app.config.js` 里有一份同规则实现（那边跑在构建期 Node，无法共享模块）。
 * 两者一致性由 `tests/mobile/test_api_candidates.py` 真跑两边后逐项比对保证，
 * 改了一边忘了另一边会直接测试失败。
 */
export function normalizeCandidateUrls(raw: string | undefined | null): string[] {
  if (!raw) return [];
  const out: string[] = [];
  for (const part of raw.split(',')) {
    const url = normalizeOne(part);
    if (url && !out.includes(url)) out.push(url);
  }
  return out;
}

/**
 * 按**优先级顺序**合并多个来源，得到最终候选表（去重、保序）。
 *
 * 每个来源可以是「逗号分隔的串」或「已经是数组」（extra 里传过来的是数组）。
 * 靠前的来源先入表，因此表内顺序即优先级 —— 首项是 APP 的首选地址。
 */
export function mergeCandidateSources(
  sources: ReadonlyArray<string | readonly string[] | undefined | null>,
): string[] {
  const out: string[] = [];
  const push = (url: string | null): void => {
    if (url && !out.includes(url)) out.push(url);
  };

  for (const src of sources) {
    if (!src) continue;
    if (typeof src === 'string') {
      for (const url of normalizeCandidateUrls(src)) push(url);
    } else {
      for (const item of src) push(normalizeOne(String(item)));
    }
  }
  return out;
}

/**
 * 并发探活，返回**第一个回应**的地址；全部失败返回 null。**从不抛异常。**
 *
 * 并发而非串行：串行的最坏耗时是「候选数 × 单次超时」（3 个候选约 7.5 秒），
 * 并发则恒为一个超时。代价是可能同时发出几个请求 —— 都指向自己的后端，无副作用。
 *
 * 取「第一个成功」而不是「表里最靠前的成功」：两者在意愿上等价（候选都只指向
 * 本机后端，选哪个都能用），但前者不必等靠前的候选把超时耗完。前提是探活本身
 * 会校验后端身份（见 client.ts 的 probeOne）—— 否则同一网段上别的服务
 * 只要在该端口应答就会被误选。
 *
 * 不抛异常很重要：调用点位于 App 启动路径上，启动期连不上是常态
 * （后端没起、手机不在同一网段），抛出去就是一次红屏 —— 用户连
 * 「我的 → 网络线路」这个手改入口都进不去。
 */
export async function pickFirstReachable(
  candidates: readonly string[],
  probe: (url: string) => Promise<unknown>,
): Promise<string | null> {
  if (candidates.length === 0) return null;

  return new Promise<string | null>((resolve) => {
    let done = false;
    let failed = 0;

    for (const url of candidates) {
      probe(url).then(
        () => {
          if (!done) {
            done = true;
            resolve(url);
          }
        },
        () => {
          failed += 1;
          // 只在"全都失败"时收口。任何一个成功都会先 resolve，
          // 之后这里即便计数到达也不会再改结果（done 已为 true）。
          if (!done && failed === candidates.length) {
            done = true;
            resolve(null);
          }
        },
      );
    }
  });
}
