/**
 * 构建期环境变量的类型声明。
 *
 * 只声明本工程真正读取的键，**刻意不引入 @types/node** —— 那会把 Buffer、
 * __dirname、require 等 Node 专属全局一并放进来，而它们在 React Native
 * 运行时并不存在。摆在那里等于给出"可用"的错觉，等到运行期才炸。
 */
declare var process: {
  env: {
    /**
     * 后端服务地址，构建期注入。
     *
     * babel-preset-expo 在打包时会把 `process.env.EXPO_PUBLIC_*` 这整个表达式
     * 替换成字面量字符串，所以**必须**写成这种静态成员访问形式。
     * 写成 `globalThis.process?.env?.['EXPO_PUBLIC_API_BASE_URL']` 之类
     * 就替换不掉了，运行期会得到 undefined —— 而且不报任何错。
     */
    readonly EXPO_PUBLIC_API_BASE_URL?: string;
  };
};
