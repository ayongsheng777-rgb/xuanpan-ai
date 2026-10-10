/**
 * 自定义 expo config plugin —— 把字体复制到 `assets/fonts/<自定义文件名>`。
 *
 * ## 为什么需要这个
 *
 * `@expo/vector-icons` 把字体 family 名注册为小写（如 `ionicons`），
 * RN 在 Android 上用 `Typeface.createFromAsset(assets, "fonts/<family>.ttf")`
 * 拼路径找字体，**文件名必须匹配 family 名（区分大小写）**。
 *
 * 但 `@expo/vector-icons/build/vendor/.../Fonts/Ionicons.ttf` 的文件名是
 * `Ionicons.ttf`（首字母大写），直接交给 `expo-font` plugin 会复制成
 * `assets/fonts/Ionicons.ttf`，运行时 RN 找的是 `assets/fonts/ionicons.ttf` →
 * 找不到 → 字体不加载 → 图标渲染为空白方块。
 *
 * `expo-font` 自带的 plugin 只接受源路径，不能指定目标文件名。
 * 本 plugin 接受 `{ src, family }` 数组，把 src 复制为 `assets/fonts/<family>.ttf`。
 *
 * 只在 Android 上有效 —— iOS 的字体 family 注册走 Info.plist 大小写不敏感。
 *
 * ## 为什么不用 createRunOncePlugin 包装
 *
 * `withStaticPlugin` 加载 plugin 模块时会先 `assertInternalProjectRoot`。
 * `createRunOncePlugin` 内部做的事与它无关，但挂在它的顶部会改变 module
 * 的 export 形状，导致 expo-cli 解析时拿到错误的 plugin 结构触发断言。
 * 所以这里直接 export 一个 `config => config` 函数式 plugin。
 */
const path = require('path');
const fs = require('fs/promises');

module.exports = function withAndroidFonts(config, props = {}) {
  const items = props.fonts ?? [];
  if (items.length === 0) return config;
  const expo = require('expo/config-plugins');
  return expo.withDangerousMod(config, [
    'android',
    async (mod) => {
      const projectRoot = mod.modRequest.projectRoot;
      const fontsDir = path.join(
        mod.modRequest.platformProjectRoot,
        'app/src/main/assets/fonts'
      );
      await fs.mkdir(fontsDir, { recursive: true });
      await Promise.all(
        items.map(async ({ src, family }) => {
          if (!src || !family) {
            throw new Error(
              `[withAndroidFonts] 每项必须有 src 与 family：${JSON.stringify({ src, family })}`
            );
          }
          const from = path.resolve(projectRoot, src);
          const to = path.join(fontsDir, `${family}.ttf`);
          await fs.copyFile(from, to);
        })
      );
      return mod;
    },
  ]);
};
