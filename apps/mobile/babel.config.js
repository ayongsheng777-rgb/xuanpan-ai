/**
 * Babel 配置。
 *
 * 只需要 `babel-preset-expo`：expo-router 的路由解析、TypeScript、
 * React Native 的 JSX 转换都已包含在该 preset 内。
 *
 * ⚠️ **不要加 `expo-router/babel`**：它在 SDK 50 起已是空操作，
 * 唯一作用是每次打包都打印一条废弃警告（见 `node_modules/expo-router/babel.js`）。
 * 这条警告很容易被误读成"打包配置有问题"，从而浪费排查时间。
 */
module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
  };
};
