/**
 * 极简异步状态管理 —— 不引第三方状态库。
 *
 * 为什么不用 TanStack Query / SWR：本 App 的数据形态很简单
 * （读一次元信息、提交一次表单、生成一份报告），引入缓存库会带来
 * "什么时候该 invalidate"的一整套心智负担，收益不足。
 *
 * 但这个 hook 做了一件缓存库常被忽略的事：**把错误分类**。
 * `ApiError.isUserFixable` 为真时说明是"用户输入不成立"（如山名写错），
 * 界面应把 `detail` 原样展示；否则是环境/服务问题，应提示检查网络。
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { ApiError, NetworkError } from '@/api/client';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** 错误是否属于"用户可自行修正"的一类 */
  fixable: boolean;
  /** 是否从未成功过（决定显示骨架还是保留旧数据） */
  stale: boolean;
  reload: () => void;
  setData: (d: T | null) => void;
}

/** 只读加载：组件挂载（或 deps 变化）时自动拉一次 */
export function useAsync<T>(
  loader: () => Promise<T>,
  deps: readonly unknown[] = [],
  options: { auto?: boolean } = {},
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(options.auto !== false);
  const [error, setError] = useState<string | null>(null);
  const [fixable, setFixable] = useState(false);
  const [stale, setStale] = useState(true);

  // 防止"上一次请求回来了、覆盖了后一次的结果"
  const seq = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async () => {
    const my = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      if (!mounted.current || my !== seq.current) return;
      setData(result);
      setStale(false);
    } catch (err) {
      if (!mounted.current || my !== seq.current) return;
      const { message, fix } = describeError(err);
      setError(message);
      setFixable(fix);
    } finally {
      if (mounted.current && my === seq.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (options.auto === false) return;
    void run();
  }, [run, options.auto]);

  return { data, loading, error, fixable, stale, reload: () => void run(), setData };
}

/**
 * 手动提交：不自动执行，返回一个可直接绑到按钮上的函数。
 *
 * **`fn` 若来自某个类实例，必须已绑定 `this`。**
 * 普通类方法依赖调用时的接收者，当值传出去就丢了 `this`，
 * 表现为按下按钮才炸的 `TypeError`（类型检查完全发现不了）。
 * 本项目的 `ApiClient` 公开方法一律写成箭头函数属性，天生绑定，
 * 因此 `useSubmit(getApiClient().scan)` 是安全的；
 * 但换成别的类实例（或后续新增普通方法）时，仍需包一层箭头：
 * `useSubmit((a) => obj.method(a))`。
 */
export function useSubmit<A extends unknown[], R>(
  fn: (...args: A) => Promise<R>,
): {
  run: (...args: A) => Promise<R | null>;
  loading: boolean;
  error: string | null;
  fixable: boolean;
  reset: () => void;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fixable, setFixable] = useState(false);

  const run = useCallback(
    async (...args: A): Promise<R | null> => {
      setLoading(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (err) {
        const d = describeError(err);
        setError(d.message);
        setFixable(d.fix);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [fn],
  );

  const reset = useCallback(() => {
    setError(null);
    setFixable(false);
  }, []);

  return { run, loading, error, fixable, reset };
}

/** 把异常转成"给用户看的一句话 + 是否可自行修正" */
export function describeError(err: unknown): { message: string; fix: boolean } {
  if (err instanceof ApiError) {
    return { message: err.detail, fix: err.isUserFixable };
  }
  if (err instanceof NetworkError) {
    return { message: err.message, fix: false };
  }
  if (err instanceof Error) {
    return { message: err.message, fix: false };
  }
  return { message: '发生未知错误', fix: false };
}
