#!/usr/bin/env node
/**
 * 批量用 CDP 渲染 expo web 全部页面为 PNG（一次 Chrome 启动，多 target 复用）。
 *
 * 设计要点（都是踩过的坑）：
 *  1. `chrome --headless --screenshot --window-size=390,844` 在本机**不生效** ——
 *     实测页面 innerWidth=500，截出来的"390px 手机图"是把 500px 布局裁掉右边，
 *     看着像横向溢出其实是假象。必须用 Emulation.setDeviceMetricsOverride。
 *  2. **不要每页重启 Chrome**：实例之间存在干扰，实测第二页起会永久挂起且无任何
 *     报错（20 分钟只出一页）。改为启动一次 Chrome，每页用独立 target。
 *  3. 每个 await 都要有超时 —— CDP 的连接/命令在不响应时不会 reject，会静默挂死。
 *
 * 零依赖：Node 22 自带全局 WebSocket / fetch。
 *
 * 用法：node cdp_batch.mjs <chrome-exe> <out-dir> <base-url> [onlyName]
 */

import { spawn, spawnSync } from 'node:child_process';
import { writeFileSync, mkdirSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const [, , CHROME, OUT, BASE = 'http://127.0.0.1:8903', ONLY = ''] = process.argv;

if (!CHROME || !OUT) {
  console.error('usage: node cdp_batch.mjs <chrome> <out-dir> <base-url> [onlyName]');
  process.exit(2);
}

/** 后台管理台令牌：从环境变量读，避免写进脚本文件 */
const ADMIN_TOKEN = process.env.XP_ADMIN_TOKEN || '';

/**
 * 待渲染页面：name|path|w|h|mode
 *
 * 一律用 `viewport` 而不是 `full`（captureBeyondViewport），两个理由：
 *   1. 实测全部移动页面 `contentH === 844`（恰等于视口高）—— 本来就是单屏设计；
 *      超长内容放在页面内部的 ScrollView 里，全页截图也照样截不到那部分。
 *   2. `captureBeyondViewport` 在本机出现过 `TIMEOUT Page.captureScreenshot`
 *      （20 秒不返回），稳定性明显更差。
 * 需要判断"内容有没有漏"时看诊断里的 `text` 字段 —— 它取自 innerText，
 * 包含滚动区域内的全部文本，比截图更完整。
 */
const PAGES = [
  ['01-home', '/', 390, 844, 'viewport'],
  ['02-adjust', '/adjust', 390, 844, 'viewport'],
  ['03-sensors', '/sensors', 390, 844, 'viewport'],
  ['04-scan', '/scan', 390, 844, 'viewport'],
  ['05-almanac', '/almanac', 390, 844, 'viewport'],
  ['06-sanshi', '/sanshi', 390, 844, 'viewport'],
  ['07-chart', '/chart', 390, 844, 'viewport'],
  ['08-divine', '/divine', 390, 844, 'viewport'],
  ['09-history', '/history', 390, 844, 'viewport'],
  ['10-mine', '/mine', 390, 844, 'viewport'],
  // 后台管理台：不在 expo web 产物里，由后端服务提供，故用绝对 URL、桌面视口。
  // 带令牌直入，否则只能截到令牌门那一屏（看不到真实面板）。
  [
    '11-admin',
    `http://127.0.0.1:8360/admin${ADMIN_TOKEN ? '?token=' + encodeURIComponent(ADMIN_TOKEN) : ''}`,
    1440,
    900,
    'viewport',
  ],
].filter((p) => !ONLY || ONLY.split(',').map((s) => s.trim()).includes(p[0]));

const PORT = 9300 + Math.floor(Math.random() * 400);
const PROFILE = join(tmpdir(), `xp-ui-render-${process.pid}`);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const withTimeout = (p, ms, label) =>
  Promise.race([
    p,
    new Promise((_, rej) => setTimeout(() => rej(new Error('TIMEOUT ' + label)), ms)),
  ]);

class CDP {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    this.listeners = new Map();
    ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { res, rej } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) rej(new Error(`${msg.error.message} (${msg.error.code})`));
        else res(msg.result);
      } else if (msg.method) {
        for (const fn of this.listeners.get(msg.method) || []) fn(msg.params);
      }
    });
  }
  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await withTimeout(
      new Promise((res, rej) => {
        ws.addEventListener('open', res, { once: true });
        ws.addEventListener('error', () => rej(new Error('ws error')), { once: true });
      }),
      10000,
      'ws-connect'
    );
    return new CDP(ws);
  }
  send(method, params = {}, sessionId) {
    const id = ++this.seq;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    return withTimeout(
      new Promise((res, rej) => {
        this.pending.set(id, { res, rej });
        this.ws.send(JSON.stringify(payload));
      }),
      20000,
      method
    );
  }
}

async function waitForDevtools(port, timeoutMs = 40000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) return await r.json();
    } catch {
      /* 未就绪，继续等 */
    }
    await sleep(300);
  }
  throw new Error('DevTools 未就绪（port ' + port + '）');
}

/** 渲染单页，返回诊断对象 */
async function renderOne(cdp, name, path, w, h, mode) {
  const sessionId = `s-${name}`;
  // 用扁平会话：attach 时指定 sessionId，省掉一层消息包装
  const { targetId } = await cdp.send('Target.createTarget', { url: 'about:blank' });
  try {
    const { sessionId: sid } = await cdp.send('Target.attachToTarget', {
      targetId,
      flatten: true,
    });
    await cdp.send('Page.enable', {}, sid);
    await cdp.send('Runtime.enable', {}, sid);
    await cdp.send(
      'Emulation.setDeviceMetricsOverride',
      { width: w, height: h, deviceScaleFactor: 2, mobile: w < 600 },
      sid
    );
    await cdp.send(
      'Page.navigate',
      { url: path.startsWith('http') ? path : BASE + path },
      sid
    );

    // 等渲染稳定：先静置，再等 innerText 长度连续两次一致
    await sleep(4000);
    let last = -1;
    for (let i = 0; i < 8; i++) {
      const r = await cdp.send(
        'Runtime.evaluate',
        { expression: 'document.body?document.body.innerText.length:-1', returnByValue: true },
        sid
      );
      const len = r.result.value ?? -1;
      if (len > 0 && len === last) break;
      last = len;
      await sleep(900);
    }

    const diagExpr = `(()=>{const d=document.documentElement,b=document.body;return JSON.stringify({
      innerW:window.innerWidth,innerH:window.innerHeight,
      scrollW:Math.max(d.scrollWidth,b?b.scrollWidth:0),
      scrollH:Math.max(d.scrollHeight,b?b.scrollHeight:0),
      textLen:b?b.innerText.length:-1,
      errors:(window.__xpErrors||[]).slice(0,4),
      text:(b?b.innerText:'').replace(/\\s+/g,' ').slice(0,700)});})()`;
    const dr = await cdp.send(
      'Runtime.evaluate',
      { expression: diagExpr, returnByValue: true },
      sid
    );
    const diag = JSON.parse(dr.result.value);

    const shot = await cdp.send(
      'Page.captureScreenshot',
      { format: 'png', captureBeyondViewport: mode === 'full' },
      sid
    );
    mkdirSync(OUT, { recursive: true });
    writeFileSync(`${OUT}/${name}.png`, Buffer.from(shot.data, 'base64'));

    return {
      name,
      ok: true,
      viewport: `${w}x${h}`,
      mode,
      overflowX: diag.scrollW - diag.innerW,
      contentH: diag.scrollH,
      textLen: diag.textLen,
      errors: diag.errors,
      text: diag.text,
    };
  } finally {
    try {
      await withTimeout(cdp.send('Target.closeTarget', { targetId }), 5000, 'closeTarget');
    } catch {
      /* 关不掉不影响其他页 */
    }
  }
}

let chrome;
let hardTimer;
try {
  // 清掉上一次产物，避免失败页残留旧图看起来"有更新"
  mkdirSync(OUT, { recursive: true });
  // 只在全量模式清理产物；单页模式（ONLY）下清理会把已渲染好的其他页一起删掉
  if (!ONLY)
    for (const f of readdirSync(OUT)) if (f.endsWith('.png')) rmSync(`${OUT}/${f}`);

  chrome = spawn(
    CHROME,
    [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu',
      '--hide-scrollbars',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-extensions',
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${PROFILE}`,
      'about:blank',
    ],
    { stdio: 'ignore' }
  );

  const version = await waitForDevtools(PORT);
  const cdp = await CDP.connect(version.webSocketDebuggerUrl);
  console.log(`connected: ${version.Browser}`);

  for (const [name, path, w, h, mode] of PAGES) {
    try {
      const r = await withTimeout(renderOne(cdp, name, path, w, h, mode), 70000, name);
      console.log('OK   ' + JSON.stringify(r));
    } catch (e) {
      console.log('FAIL ' + name + ' :: ' + (e && e.message ? e.message : String(e)));
    }
  }

  console.log('DONE');
} catch (err) {
  console.error('FATAL: ' + (err && err.message ? err.message : String(err)));
  process.exitCode = 1;
} finally {
  clearTimeout(hardTimer);
  // 必须杀**进程树**：Windows 上 child.kill() 只结束主进程，
  // 遗留的 renderer 会一直占着 profile 与端口。
  if (chrome && chrome.pid) {
    try {
      // 用 spawnSync 而非 spawn：异步派发后若 Chrome 未及时退出，仍开着的 CDP
      // WebSocket 会让 Node 事件循环一直存活 → 进程永不退出，调用方
      //（pytest / shell）就跟着永久挂起。实测卡死过一次 14 分钟。
      spawnSync('taskkill', ['/F', '/T', '/PID', String(chrome.pid)], { stdio: 'ignore' });
    } catch {
      /* 忽略 */
    }
  }
  // 硬性退出：不依赖事件循环自然排空，避免被残留句柄吊住
  process.exit(process.exitCode || 0);
}
