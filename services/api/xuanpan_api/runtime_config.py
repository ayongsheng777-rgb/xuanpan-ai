"""运行时可调配置 —— 环境变量给默认值，管理台覆盖，改完即时生效。

## 为什么需要这一层

`config.Settings` 是**启动时**读环境变量构造的不可变对象。改一个模型名要重启
服务（容器里还得 recreate），而「换个模型试试」恰恰是运维最频繁的动作。
只给一个能写配置的接口是不够的 —— 写了不生效，等于没有。

## 优先级

    管理台覆盖  >  环境变量  >  代码默认值

界面上**必须显示每一项的来源**。否则会遇到最难查的一类问题：运维改了 `.env`
却没有任何变化 —— 因为库里的覆盖把它压住了，而界面上看不出这件事，于是人会去
怀疑"是不是没重启"、"是不是镜像没更新"，排查方向从一开始就是错的。

## 为什么落库而不是写回 .env

`.env` 属重建禁区（AGENTS.md §6）；写回文件在多副本部署下还会互相覆盖。
落 SQLite 与被改的数据同库，备份单元仍是那一个文件。

## 密钥的处理（本模块最需要守住的一条）

`llm.api_key` 与 `admin_token` 是密钥。规矩是：

- 它们的明文**只出现在 `llm()` 一个方法的返回值里**，而那唯一一个调用点是
  构造 AI provider。其它任何地方（`effective()` / `effective_settings()` /
  展示层）都拿不到明文。
- 读接口只返回「是否已配置 + 掩码 + 长度」。
- 日志与错误消息一律不带出密钥（provider 内部另有一道 `_redact`）。

为什么不用一个 `values()` 把什么都装进去、由展示层自己记得脱敏：脱敏一旦依赖
"调用方记得做"，迟早有一处忘记，而且是静默的。把明文限制在单个出口，
忘不掉。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .config import Settings

# ---------------------------------------------------------------- 常量

KIND_BOOL = "bool"
KIND_INT = "int"
KIND_STR = "str"
KIND_ENUM = "enum"
KIND_LIST = "list"
KIND_SECRET = "secret"

#: 生效时机。被 middleware 在启动时读取的配置改不动 —— 与其假装能改，
#: 不如显式告诉运维"这项要重启"，否则他会以为是程序坏了。
APPLIES_NOW = "立即生效"
APPLIES_RESTART = "需重启服务"

SOURCE_OVERRIDE = "override"
SOURCE_ENV = "env"
SOURCE_DEFAULT = "default"

_SOURCE_LABEL = {
    SOURCE_OVERRIDE: "管理台覆盖",
    SOURCE_ENV: "环境变量",
    SOURCE_DEFAULT: "代码默认值",
}

#: 永不回显的键。**新增密钥类配置时必须加进来**，否则会明文泄露。
SECRET_KEYS = frozenset({"llm.api_key", "admin_token"})

#: 云端模型相关的键。四者齐备（除 capability 有默认值外）才启用云端解释。
LLM_KEYS = ("llm.base_url", "llm.api_key", "llm.model", "llm.capability")

_MASK_HEAD = 3
_MASK_TAIL = 4


@dataclass(frozen=True, slots=True)
class SettingSpec:
    """一项可调配置的元数据。

    `read` / `write` 把「该键如何落在 Settings 上」表达成一对函数，
    而不是在别处再写一遍解析逻辑：

    - `read` 为 None 表示该键**不在 `Settings` 上**（如 llm.*，由 AI 路由消费），
      基线值改从环境变量直接读；
    - 有 `read` 时值一律取自 `Settings`，避免出现「config.py 解析一遍、
      这里又解析一遍」的双真源 —— `max_upload_mb` 就是例子，`Settings`
      存的是字节、界面要的是 MB，两处换算必然漂移。
    """

    key: str
    env_var: str
    kind: str
    default: Any
    description: str
    choices: tuple[str, ...] = ()
    minimum: int | None = None
    maximum: int | None = None
    editable: bool = True
    applies: str = APPLIES_NOW
    read: Callable[[Settings], Any] | None = None
    write: Callable[[Any], dict[str, Any]] | None = None

    @property
    def secret(self) -> bool:
        return self.key in SECRET_KEYS


def _cors(s: Settings) -> list[str]:
    return list(s.cors_origins)


SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="ai_mode",
        env_var="XUANPAN_AI_MODE",
        kind=KIND_ENUM,
        default="auto",
        choices=("auto", "cost", "quality"),
        description="AI 选路模式：auto 按任务自动选、cost 省钱优先、quality 能力优先",
        read=lambda s: s.ai_mode,
        write=lambda v: {"ai_mode": v},
    ),
    SettingSpec(
        key="keep_photos",
        env_var="XUANPAN_KEEP_PHOTOS",
        kind=KIND_BOOL,
        default=False,
        description=(
            "识别后是否把原图长期落盘。默认不落盘 —— 只保留结构化识别结果。"
            "打开后隐私说明的措辞也会随之改变"
        ),
        read=lambda s: s.keep_photos,
        write=lambda v: {"keep_photos": bool(v)},
    ),
    SettingSpec(
        key="max_upload_mb",
        env_var="XUANPAN_MAX_UPLOAD_MB",
        kind=KIND_INT,
        default=12,
        minimum=1,
        maximum=64,
        description="上传图片大小上限（MB）。超大图对识别没有帮助，只会拖慢链路",
        read=lambda s: s.max_upload_mb,
        write=lambda v: {"max_upload_bytes": int(v) * 1024 * 1024},
    ),
    SettingSpec(
        key="llm.base_url",
        env_var="XUANPAN_LLM_BASE_URL",
        kind=KIND_STR,
        default="",
        description=(
            "云端模型接入地址（OpenAI 兼容 /chat/completions）。"
            "OpenAI、DeepSeek、通义、智谱、自建 vLLM/Ollama 都可用。留空则只用本地模板"
        ),
    ),
    SettingSpec(
        key="llm.api_key",
        env_var="XUANPAN_LLM_API_KEY",
        kind=KIND_SECRET,
        default="",
        description="云端模型密钥。只在写入时接受，读取时永不回显（仅显示是否已配置）",
    ),
    SettingSpec(
        key="llm.model",
        env_var="XUANPAN_LLM_MODEL",
        kind=KIND_STR,
        default="",
        description="模型名。base_url + api_key + model 三者齐备才会启用云端解释",
    ),
    SettingSpec(
        key="llm.capability",
        env_var="XUANPAN_LLM_CAPABILITY",
        kind=KIND_ENUM,
        default="reasoning",
        choices=("reasoning", "fast", "local"),
        description="该模型在选路时的能力档位，决定它与其它候选的先后次序",
    ),
    SettingSpec(
        key="cors_origins",
        env_var="XUANPAN_CORS_ORIGINS",
        kind=KIND_LIST,
        default=["*"],
        description="允许的跨域来源（逗号分隔）。生产环境应由网关收敛",
        read=_cors,
        write=lambda v: {"cors_origins": tuple(v)},
        applies=APPLIES_RESTART,
    ),
    SettingSpec(
        key="admin_token",
        env_var="XUANPAN_ADMIN_TOKEN",
        kind=KIND_SECRET,
        default="",
        editable=False,
        description=(
            "管理台令牌。刻意「不允许从界面修改」：它一旦被改错，"
            "改它的那个界面立刻就用不了了。启用/更换请改 .env 后重启"
        ),
        read=lambda s: s.admin_token,
        applies=APPLIES_RESTART,
    ),
)

SPEC_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in SPECS}


class ConfigError(ValueError):
    """配置项不合法（键名错、类型错、取值越界）。

    继承 `ValueError`：路由层把它翻译成 400（"你传的东西不成立"），
    而不是 500 —— 后者会把使用者引向"服务坏了"这个完全错误的方向。
    """


# ---------------------------------------------------------------- 取值

def _mask(value: str) -> str:
    """密钥掩码。短到无法安全掩码时只给长度，不给任何字符片段。"""
    if not value:
        return ""
    if len(value) <= _MASK_HEAD + _MASK_TAIL:
        return "*" * len(value)
    return f"{value[:_MASK_HEAD]}…{value[-_MASK_TAIL:]}"


def _coerce(spec: SettingSpec, raw: Any) -> Any:
    """把外部输入（JSON）转成该键该有的类型。不合法即抛 `ConfigError`。"""
    if spec.kind == KIND_BOOL:
        if isinstance(raw, bool):
            return raw
        # 字符串形式也接受 —— curl 手测时 `"true"` 是很自然的写法
        if isinstance(raw, str) and raw.strip().lower() in ("1", "true", "yes", "on", "0", "false", "no", "off"):
            return raw.strip().lower() in ("1", "true", "yes", "on")
        raise ConfigError(f"{spec.key} 需要布尔值 true/false，收到 {raw!r}")

    if spec.kind == KIND_INT:
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            raise ConfigError(f"{spec.key} 需要整数，收到 {raw!r}")
        try:
            val = int(str(raw).strip())
        except (TypeError, ValueError):
            raise ConfigError(f"{spec.key} 需要整数，收到 {raw!r}") from None
        if spec.minimum is not None and val < spec.minimum:
            raise ConfigError(f"{spec.key} 不能小于 {spec.minimum}（收到 {val}）")
        if spec.maximum is not None and val > spec.maximum:
            raise ConfigError(f"{spec.key} 不能大于 {spec.maximum}（收到 {val}）")
        return val

    if spec.kind == KIND_ENUM:
        if not isinstance(raw, str) or raw.strip() not in spec.choices:
            raise ConfigError(
                f"{spec.key} 取值必须是 {'/'.join(spec.choices)} 之一，收到 {raw!r}"
            )
        return raw.strip()

    if spec.kind == KIND_LIST:
        if isinstance(raw, str):
            return [x.strip() for x in raw.split(",") if x.strip()]
        if isinstance(raw, (list, tuple)):
            if not all(isinstance(x, str) for x in raw):
                raise ConfigError(f"{spec.key} 只接受字符串列表，收到 {raw!r}")
            return [x.strip() for x in raw if x.strip()]
        raise ConfigError(f"{spec.key} 需要字符串列表或逗号分隔的字符串，收到 {raw!r}")

    # KIND_STR / KIND_SECRET
    if isinstance(raw, str):
        return raw.strip() if spec.kind == KIND_STR else raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return str(raw)
    raise ConfigError(f"{spec.key} 需要字符串，收到 {raw!r}")


def _baseline(spec: SettingSpec, settings: Settings, env: Mapping[str, str]) -> tuple[Any, str]:
    """该项在没有覆盖时的值与来源。

    有 `read` 的键：值取自 `Settings`（解析只一处），来源靠环境变量是否设置来判。
    两者分开看是有意的 —— `Settings` 把"未设置"变成了默认值，从它身上已经
    分不出「环境变量配的」与「代码默认的」，但界面需要这个区分。
    """
    if spec.read is not None:
        value = spec.read(settings)
    else:
        raw = (env.get(spec.env_var) or "").strip()
        value = _coerce(spec, raw) if raw else spec.default
    source = SOURCE_ENV if (env.get(spec.env_var) or "").strip() else SOURCE_DEFAULT
    return value, source


def _override_value(spec: SettingSpec, raw: str) -> Any:
    """把库里存的字符串还原成该键该有的类型。"""
    if spec.kind == KIND_BOOL:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if spec.kind == KIND_INT:
        try:
            return int(raw.strip())
        except ValueError:
            return spec.default
    if spec.kind == KIND_LIST:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return raw


def _dump_override(spec: SettingSpec, value: Any) -> str:
    """把类型化值压成库里要存的一列文本。"""
    if spec.kind == KIND_BOOL:
        return "true" if value else "false"
    if spec.kind == KIND_LIST:
        return ",".join(str(x) for x in value)
    return str(value)


# ---------------------------------------------------------------- 服务


class RuntimeConfig:
    """生效配置的服务。挂在 `app.state` 上，按需解析。

    设计上**每次调用都从 store 现取覆盖**，不做进程内缓存：
    覆盖的读取量极小（一张几行的表），而缓存会引入"改了之后要看运气才生效"
    这类无法自证的行为。真正需要缓存的是 AI 路由器（构造要读 provider 注册表），
    这一项单独按指纹缓存，见 `ai_router()`。
    """

    def __init__(self, settings: Settings, env: Mapping[str, str] | None = None) -> None:
        self._settings = settings
        #: 环境变量来源。测试可注入，避免"把整个进程环境当输入"。
        self._env: Mapping[str, str] = env if env is not None else _os_env()

    @property
    def settings(self) -> Settings:
        """构造时用的环境基线。`deps` 靠它判断缓存是否还有效。"""
        return self._settings

    # ---------------- 解析 ----------------

    def _resolved(self, store: Any) -> dict[str, tuple[Any, str]]:
        """每个键 → (生效值, 来源)。密钥也会出现在这里（内部用），
        但只经 `llm()` 出口流出，展示层一律另走 `entries()`。"""
        overrides = store.list_setting_overrides() if store is not None else {}
        out: dict[str, tuple[Any, str]] = {}
        for spec in SPECS:
            baseline, source = _baseline(spec, self._settings, self._env)
            if spec.key in overrides:
                out[spec.key] = (_override_value(spec, overrides[spec.key]), SOURCE_OVERRIDE)
            else:
                out[spec.key] = (baseline, source)
        return out

    def effective(self, store: Any) -> dict[str, Any]:
        """非密钥的生效值。给「拿去做判断」用的，不含任何密钥明文。"""
        return {
            k: v for k, (v, _src) in self._resolved(store).items()
            if not SPEC_BY_KEY[k].secret
        }

    def effective_settings(self, store: Any) -> Settings:
        """叠加覆盖后的 `Settings`。

        请求期的读取方（上传大小上限、是否留原件）改用它，"立即生效"才成立。
        """
        values = self.effective(store)
        kwargs: dict[str, Any] = {}
        for spec in SPECS:
            if spec.write is not None and spec.key in values:
                kwargs.update(spec.write(values[spec.key]))
        if not kwargs:
            return self._settings
        try:
            return dataclasses.replace(self._settings, **kwargs)
        except (TypeError, ValueError):
            # 兜底：覆盖值把 Settings 弄成非法状态时，退回环境基线。
            # 宁可这项不生效，也不能让每次请求都炸。
            return self._settings

    def llm(self, store: Any) -> dict[str, str]:
        """云端模型的四项配置，**含密钥明文**。

        ⚠️ 全项目唯一一个会返回密钥明文的地方。唯一的合法调用点是构造
        AI provider 链。不要把它塞进任何 HTTP 响应、日志或错误消息。
        """
        resolved = self._resolved(store)
        return {
            "XUANPAN_LLM_BASE_URL": str(resolved["llm.base_url"][0] or ""),
            "XUANPAN_LLM_API_KEY": str(resolved["llm.api_key"][0] or ""),
            "XUANPAN_LLM_MODEL": str(resolved["llm.model"][0] or ""),
            "XUANPAN_LLM_CAPABILITY": str(resolved["llm.capability"][0] or "reasoning"),
        }

    def cloud_ready(self, store: Any) -> bool:
        """云端解释是否齐备。三件套缺一即 false —— 与 provider 的判据一致。"""
        llm = self.llm(store)
        return bool(
            llm["XUANPAN_LLM_BASE_URL"]
            and llm["XUANPAN_LLM_API_KEY"]
            and llm["XUANPAN_LLM_MODEL"]
        )

    # ---------------- 展示 ----------------

    def entries(self, store: Any) -> list[dict[str, Any]]:
        """给接口的展示版：脱敏 + 来源 + 元数据。

        密钥项**不带 `value` 字段**（不是把它设成 null，而是压根没有）——
        前端少一个可能被误用的字段，好过多一个永远为空的字段。
        """
        resolved = self._resolved(store)
        stamps = store.setting_overrides_meta() if store is not None else {}
        out: list[dict[str, Any]] = []
        for spec in SPECS:
            value, source = resolved[spec.key]
            item: dict[str, Any] = {
                "key": spec.key,
                "env_var": spec.env_var,
                "kind": spec.kind,
                "description": spec.description,
                "editable": spec.editable,
                "applies": spec.applies,
                "secret": spec.secret,
                "source": source,
                "source_label": _SOURCE_LABEL[source],
                "overridden": source == SOURCE_OVERRIDE,
                "override_updated_at": stamps.get(spec.key),
            }
            if spec.choices:
                item["choices"] = list(spec.choices)
            if spec.minimum is not None:
                item["minimum"] = spec.minimum
            if spec.maximum is not None:
                item["maximum"] = spec.maximum
            if spec.secret:
                text = str(value or "")
                item["configured"] = bool(text)
                item["masked"] = _mask(text)
                item["length"] = len(text)
            else:
                item["value"] = value
            out.append(item)
        return out

    # ---------------- 写入 ----------------

    def update(self, store: Any, changes: Mapping[str, Any]) -> dict[str, Any]:
        """写入覆盖。`null` 表示**清除该键的覆盖**（回落环境变量/默认值）。

        为什么统一用 null 表达"清除"，而不是"空字符串也算清除"：
        `llm.api_key` 置空是一个有意义的取值（"我不想用云端了"），
        与"我没动过这一项"是两回事。把两者混起来，用户就失去了
        显式关掉云端的能力。
        """
        if not isinstance(changes, Mapping):
            raise ConfigError("changes 需要是 {键: 值} 的对象")

        unknown = sorted(k for k in changes if k not in SPEC_BY_KEY)
        if unknown:
            raise ConfigError(
                f"未知配置项：{'、'.join(unknown)}。"
                f"可用项：{'、'.join(sorted(SPEC_BY_KEY))}"
            )

        locked = sorted(k for k in changes if not SPEC_BY_KEY[k].editable)
        if locked:
            spec = SPEC_BY_KEY[locked[0]]
            raise ConfigError(f"{locked[0]} 不可从界面修改：{spec.description}")

        to_write: dict[str, str] = {}
        to_clear: list[str] = []
        for key, raw in changes.items():
            spec = SPEC_BY_KEY[key]
            if raw is None:
                to_clear.append(key)
                continue
            to_write[key] = _dump_override(spec, _coerce(spec, raw))

        if to_write:
            store.set_setting_overrides(to_write)
        cleared = store.delete_setting_overrides(to_clear) if to_clear else 0

        # 哪些改动要重启才生效 —— 必须回报，否则用户会以为改动失败了
        touched = list(changes)
        restart = sorted(k for k in touched if SPEC_BY_KEY[k].applies == APPLIES_RESTART)
        return {
            "updated": sorted(k for k in touched if changes[k] is not None),
            "cleared": sorted(to_clear),
            "cleared_existing": cleared,
            "restart_required": restart,
        }

    def reset(self, store: Any, keys: Iterable[str] | None = None) -> dict[str, Any]:
        """清除覆盖。不给 keys 就清全部。

        「全清」**只针对可编辑项**：不可编辑的键（如 `admin_token`）本来就不会有
        覆盖，把它算进来会让"清掉所有覆盖"这个正当操作直接失败 —— 用户说要清，
        却被告知"有一项无需清除"，这是在为难人，不是在保护人。

        显式点名某个不可编辑的键时才报错：那是调用方真的弄错了。
        """
        if keys is None:
            target = [s.key for s in SPECS if s.editable]
        else:
            target = list(keys)
            unknown = sorted(k for k in target if k not in SPEC_BY_KEY)
            if unknown:
                raise ConfigError(f"未知配置项：{'、'.join(unknown)}")
            locked = sorted(k for k in target if not SPEC_BY_KEY[k].editable)
            if locked:
                raise ConfigError(f"{locked[0]} 不可从界面修改，也就不存在覆盖需要清除")
        removed = store.delete_setting_overrides(target)
        return {
            "cleared": target,
            "cleared_existing": removed,
            "restart_required": sorted(
                k for k in target if SPEC_BY_KEY[k].applies == APPLIES_RESTART
            ),
        }

    # ---------------- AI 路由器 ----------------

    def ai_router(self, store: Any) -> Any:
        """AI 路由器，按生效配置构造；配置一变就自动重建。

        这是"改完即时生效"的落点。缓存按**配置指纹**而不是"是否构造过"：
        否则改了模型名仍是旧路由器，接口返回成功、行为毫无变化 ——
        比报错更难发现。

        保留缓存本身是有原因的：路由器承载降级轨迹等运行态，
        每个请求重建会让这些信息在响应之间丢失（见 deps.get_ai_router 注释）。
        """
        values = self.effective(store)
        mode = str(values.get("ai_mode") or "auto")
        llm = self.llm(store)
        fingerprint = (
            mode,
            llm["XUANPAN_LLM_BASE_URL"],
            llm["XUANPAN_LLM_API_KEY"],
            llm["XUANPAN_LLM_MODEL"],
            llm["XUANPAN_LLM_CAPABILITY"],
        )
        cached = getattr(self, "_router_cache", None)
        if cached is not None and cached[0] == fingerprint:
            return cached[1]
        router = build_ai_router(mode=mode, llm=llm)
        self._router_cache: tuple[Any, Any] = (fingerprint, router)
        return router


def _os_env() -> Mapping[str, str]:
    import os

    return os.environ


def build_ai_router(*, mode: str, llm: Mapping[str, str] | None = None) -> Any:
    """按配置构造 AI 路由器。导入失败返回 None，让纯计算功能仍可用。"""
    import logging

    logger = logging.getLogger("xuanpan.api")
    try:
        from xuanpan_ai import AIRouter, RouterConfig
    except ImportError:  # pragma: no cover
        logger.warning("xuanpan_ai 不可用：报告功能将不可用，计算功能不受影响")
        return None
    try:
        return AIRouter(config=RouterConfig(mode=mode), llm=llm)  # type: ignore[arg-type]
    except ValueError:
        logger.warning("ai_mode=%r 非法，回退 auto", mode)
        return AIRouter(config=RouterConfig(mode="auto"), llm=llm)  # type: ignore[arg-type]


__all__ = [
    "APPLIES_NOW",
    "APPLIES_RESTART",
    "ConfigError",
    "LLM_KEYS",
    "RuntimeConfig",
    "SECRET_KEYS",
    "SPECS",
    "SPEC_BY_KEY",
    "SOURCE_DEFAULT",
    "SOURCE_ENV",
    "SOURCE_OVERRIDE",
    "SettingSpec",
    "build_ai_router",
]
