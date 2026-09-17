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

  const newArchEnabled = process.env.XUANPAN_NEW_ARCH === '1'
    ? true
    : Boolean(config.newArchEnabled);

  return {
    ...config,
    newArchEnabled,
    extra: {
      ...config.extra,
      apiBaseUrl,
    },
  };
};
