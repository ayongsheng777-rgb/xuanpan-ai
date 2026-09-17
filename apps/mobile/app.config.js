/**
 * Expo 动态配置 —— 只承担两件事：让「后端地址」与「新架构开关」在构建期可参数化。
 * 其余配置一律留在 app.json（静态、可 diff、进版本库）。
 *
 * 一、后端地址
 *   为什么不把局域网 IP 直接写进 app.json：
 *     后端地址是「环境」而非「代码」。真机测试必须用运行后端那台机器的局域网 IP，
 *     而每台机器、每次 DHCP 租约都可能不同。写进 app.json 就会被提交进版本库，
 *     下一个人拉到代码后得到一个指向不存在主机的默认地址，且看不出它是本机专属值。
 *
 *   用法（构建真机包时）：
 *     XUANPAN_API_BASE_URL=http://192.168.57.10:8360 npx expo prebuild --platform android --clean
 *   不设该变量时，回落到 app.json 的 extra.apiBaseUrl（127.0.0.1:8360，模拟器/Web 用）。
 *
 *   一之二、多个候选地址（XUANPAN_API_BASE_URLS，逗号分隔）
 *     为什么还需要"一串"地址：构建机常有多块网卡、分属不同网段，每一块都能访问后端，
 *     而 APK 只能内联**一个** —— 手机不在那个网段就连不上，且现象只是"转圈"。
 *     实测本机同时存在 192.168.57.10 / 192.168.59.56 / 192.168.68.80 三个可用网段。
 *
 *     约定：**第一个是首选，顺序即优先级**；APP 启动时会并发探活并切到第一个真正可达的。
 *     单值变量仍兼容：只给 XUANPAN_API_BASE_URL 时，候选表就是它自己一项。
 *
 * 二、新架构开关（XUANPAN_NEW_ARCH=1 开启）
 *   app.json 当前是 false，原因是**构建环境**而非产品选择：
 *   RN 0.76 的新架构强制要求 NDK 26.1.10909125，本机只装了 27.x（RN 0.76 与
 *   NDK 27 不保证兼容），而补装需下载约 1GB 并解压数万个文件 —— 在本机安全软件
 *   实时扫描下实测约 10 文件/秒，单是复制 6千余个文件的平台包就耗了 10 分钟。
 *
 *   等环境补齐 NDK 26.1（或升级到官方支持 NDK 27 的 RN 版本）后，
 *   用 XUANPAN_NEW_ARCH=1 重新 prebuild 即可切回，不必改代码：
 *     XUANPAN_NEW_ARCH=1 npx expo prebuild --platform android --clean
 *
 * 注意：这里的 process.env 是**构建期**的 Node 环境，不是运行期。
 * 地址被写进 extra 后由 expo-constants 在 App 内读取（见 src/api/client.ts 的 resolveBaseUrl）。
 */
module.exports = ({ config }) => {
  const fallback = config.extra?.apiBaseUrl || 'http://127.0.0.1:8360';
  const injected = process.env.XUANPAN_API_BASE_URL || fallback;

  // 去掉尾部斜杠：ApiClient 自己也会做一次，但提前规范化能让
  // 「构建期注入的值」与「运行期用户输入的值」走完全相同的形态。
  const apiBaseUrl = injected.replace(/\/+$/, '');

  // 多候选地址表。去重、保序、丢弃非法项 —— 与 src/api/client.ts 的
  // normalizeCandidateUrls 是同一套规则，两边各写一份是因为一个跑在构建期
  // 的 Node、一个跑在运行期的 RN 里，无法共享模块；一致性由
  // tests/mobile/test_api_candidates.py 真跑两边代码后逐项比对来保证。
  const rawList = process.env.XUANPAN_API_BASE_URLS || apiBaseUrl;
  const seen = new Set();
  const apiBaseUrls = [];
  for (const part of String(rawList).split(',')) {
    const url = part.trim().replace(/\/+$/, '');
    if (!url || !/^https?:\/\//.test(url) || seen.has(url)) continue;
    seen.add(url);
    apiBaseUrls.push(url);
  }
  // 首选地址必须在表内（哪怕是非法输入被丢掉的那个）：否则「首选」与
  // 「候选表」会指向两个不同的后端，而 API 客户端用的是首选那个。
  if (apiBaseUrls.length === 0) apiBaseUrls.push(apiBaseUrl);

  const newArchEnabled = process.env.XUANPAN_NEW_ARCH === '1'
    ? true
    : Boolean(config.newArchEnabled);

  return {
    ...config,
    newArchEnabled,
    extra: {
      ...config.extra,
      apiBaseUrl,
      apiBaseUrls,
    },
  };
};
