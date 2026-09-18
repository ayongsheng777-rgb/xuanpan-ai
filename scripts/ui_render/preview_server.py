"""SPA 静态服务器 + 渲染探针（供 expo web 产物预览与 UI 核对）。

两个职责：

1. **SPA 回落**：expo-router 在 web 上走 history 路由，`/sensors`、`/adjust`
   在产物里没有对应文件，`python -m http.server` 会直接 404。
   这里把所有未命中路径回落到 index.html，由前端路由接管
   （正是 app.json 里 `web.output: "single"` 的语义）。

2. **渲染探针**：给 index.html 注入一段脚本，等页面静置后把**实测结果**回传
   到本服务器的标准输出。这一步的意义在于 —— 一张截图只能看出"长得像不像"，
   看不出"是不是横向溢出""有没有 JS 异常""文字有没有渲染成空"。
   探针让这些变成可读的数字与字符串，而不是靠看图猜。

注意：探针只存在于这个**本地预览服务器**里，不进入仓库、不影响 APP 构建产物。

用法：python spa_server.py <root> <port>
"""

import http.server
import os
import sys
import urllib.parse

PROBE_SNIPPET = r"""
<script>
(function () {
  window.__xpErrors = [];
  window.addEventListener('error', function (e) {
    window.__xpErrors.push('ERROR: ' + (e.message || e.type) +
      ' @ ' + (e.filename || '?') + ':' + (e.lineno || 0));
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason;
    window.__xpErrors.push('REJECTION: ' + ((r && (r.message || r.toString())) || r));
  });
  function probe(tag) {
    try {
      var d = document.documentElement, b = document.body;
      var body = {
        tag: tag,
        path: location.pathname,
        innerW: window.innerWidth,
        innerH: window.innerHeight,
        scrollW: Math.max(d.scrollWidth, b ? b.scrollWidth : 0),
        scrollH: Math.max(d.scrollHeight, b ? b.scrollHeight : 0),
        errors: window.__xpErrors.slice(0, 8),
        textLen: b ? b.innerText.length : -1,
        text: (b ? b.innerText : '').replace(/\s+/g, ' ').slice(0, 1200)
      };
      var x = new XMLHttpRequest();
      x.open('POST', '/__probe', false);
      x.send(JSON.stringify(body));
    } catch (e) {}
  }
  window.addEventListener('load', function () {
    setTimeout(function () { probe('settled'); }, 6000);
  });
})();
</script>
"""


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: spa_server.py <root> <port>", file=sys.stderr)
        return 2
    root = os.path.abspath(sys.argv[1])
    port = int(sys.argv[2])
    if not os.path.isdir(root):
        print(f"root not found: {root}", file=sys.stderr)
        return 2

    index_path = os.path.join(root, "index.html")
    if not os.path.isfile(index_path):
        print(f"index.html not found in {root}", file=sys.stderr)
        return 2

    def build_index() -> bytes:
        """每次请求重读 index.html —— 重新 export 后无需重启本服务器。

        （bundle 文件名每次导出都带新 hash，缓存住旧 index.html 会指向已删除的 bundle。）
        """
        with open(index_path, encoding="utf-8") as fh:
            raw = fh.read()
        if "</head>" in raw:
            raw = raw.replace("</head>", PROBE_SNIPPET + "</head>", 1)
        return raw.encode("utf-8")

    inject_ok = "</head>" in open(index_path, encoding="utf-8").read()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=root, **kwargs)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            rel = parsed.path.lstrip("/")
            target = os.path.join(root, rel)
            # 未命中任何静态文件（含 SPA 深层路由）→ 回注入过探针的 index.html
            if not rel or not os.path.isfile(target):
                patched = build_index()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(patched)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(patched)
                return
            return super().do_GET()

        def do_POST(self):
            if urllib.parse.urlparse(self.path).path != "/__probe":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length") or 0)
            payload = self.rfile.read(length).decode("utf-8", "replace")
            print("PROBE " + payload, flush=True)
            self.send_response(204)
            self.end_headers()

        def log_message(self, fmt, *args):
            # 静音：截图流程里逐条请求日志只会淹没有用的探针输出
            pass

    with http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        print(
            f"SPA server on http://127.0.0.1:{port} root={root} "
            f"probe_injected={inject_ok}",
            flush=True,
        )
        httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
