# 玄盘 AI · 后端服务镜像
#
# 构建上下文必须是**仓库根目录**（不是 services/api/）：运行期需要同时看到
#   services/{api,ai,vision}/   三个 Python 包
#   packages/fortune-core/      确定性计算内核（含 data/ 下的领域数据表）
# 三者通过 PYTHONPATH 组装，未做成可安装包 —— 沿用途项目的源码布局，
# 不为了打包而引入一层 setuptools 配置。见 AGENTS.md §5.1。
#
#   docker build -f services/api/Dockerfile -t xuanpan-api:0.1.0 .

FROM python:3.12-slim

# PYTHONPATH 是本镜像的核心装配点：三个服务 + 内核
ENV PYTHONPATH=/app/services/api:/app/services/ai:/app/services/vision:/app/packages/fortune-core \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# SQLite 需要写权限，故工作目录固定为 /app，data/ 由 compose 挂卷
WORKDIR /app

# ---- 依赖：直接读 pyproject.toml，不在这里重复抄一遍依赖表 ----
# 抄一遍就等于把依赖声明变成两处，迟早漂移（本项目 RULE-005 的同一逻辑）。
#
# ⚠️ 为什么必须显式指定国内 PyPI 镜像（不是"优化"，是不指定就装不上）：
#   实测本机 **宿主自身也解析不了 pypi.org / files.pythonhosted.org**
#   （socket.gethostbyname 报 gaierror）。宿主之所以能装包，是靠 HTTP_PROXY
#   让代理远端解析域名；容器内没有代理环境变量，直连必然
#   `Temporary failure in name resolution` 而失败。
#   容器内实测可用：pypi.tuna.tsinghua.edu.cn、mirrors.aliyun.com。
#   这与生产路线报告 §6「优先国内直连」的策略一致。
#
# 需要换源或走内网源时改这个构建参数即可，不必改本文件：
#   docker compose build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

COPY pyproject.toml ./
# 先把依赖列成 requirements 再装：pip 直接以 `-r` 运行，报错信息是原生可读的，
# 比塞在 python -c 的 subprocess 里只回一句 CalledProcessError 好排查得多。
RUN python -c "\
import tomllib; \
print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" \
        > /tmp/requirements.txt \
    && cat /tmp/requirements.txt \
    && pip install --no-cache-dir --timeout 60 --retries 3 \
        --index-url "$PIP_INDEX_URL" -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

# ---- 源码 ----
# 注意 packages/fortune-core/data/ 是**领域数据**（康熙笔画表、签库），
# 不是运行时产物，必须进镜像；漏掉会退化成"表未提供"而只输出「未定」。
COPY services/ /app/services/
COPY packages/ /app/packages/

# ---- 非 root 运行 ----
# data/ 需要可写：镜像内先建目录并授权，匿名卷/命名卷继承该属主。
RUN useradd --create-home --uid 10001 xuanpan \
    && mkdir -p /app/data \
    && chown -R xuanpan:xuanpan /app
USER xuanpan

# 容器内监听 8352（应用自身默认端口）。
# 宿主映射到 8360 等其它端口 —— 本机 8352 已被 SysCenter 占用，见 AGENTS.md §5.3。
ENV XUANPAN_HOST=0.0.0.0 \
    XUANPAN_PORT=8352 \
    XUANPAN_DB_PATH=/app/data/xuanpan.db
EXPOSE 8352

# 健康检查用 Python 而非 curl：slim 镜像不带 curl，装了只为探活不值得。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8352/healthz',timeout=3).status==200 else 1)"

# 生产用 create_app --factory，便于交给进程管理器；不启 --reload。
CMD ["python", "-m", "uvicorn", "xuanpan_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8352"]
