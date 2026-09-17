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

    /**
     * 后端候选地址表，逗号分隔，**顺序即优先级**。构建期注入。
     *
     * 为什么需要多个：构建机常有多块网卡分属不同网段，而 APK 只能内联一个地址 ——
     * 手机不在那个网段就连不上，现象只是"一直转圈"。APP 启动时并发探活这张表，
     * 切到第一个真正可达的（见 client.ts 的 autoSelectBaseUrl）。
     *
     * 与上面同一条铁律：必须是静态成员访问形式，否则 babel 替换不掉，
     * 运行期静默得到 undefined。
     */
    readonly EXPO_PUBLIC_API_BASE_URLS?: string;
  };
};
