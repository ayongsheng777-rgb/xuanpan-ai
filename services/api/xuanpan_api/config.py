"""后端配置 —— 全部可由环境变量覆盖，不写死在代码里。

红线：`.env` 与 `data/` 属重建禁区（AGENTS.md §6），本模块**只读**环境，
不生成、不覆盖任何凭据文件。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    """运行时配置。"""

    #：SQLite 库位置。默认放在项目 data/ 下（该目录已 gitignore 运行时数据）
    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("XUANPAN_DB_PATH") or Path.cwd() / "data" / "xuanpan.db"
        )
    )

    #：上传图片的字节上限（默认 12MB）。超大图对识别没有帮助，只会拖慢链路。
    max_upload_bytes: int = field(default_factory=lambda: _env_int("XUANPAN_MAX_UPLOAD_MB", 12) * 1024 * 1024)

    #：**隐私默认**：识别完成后是否长期保留原图。
    #：默认 False —— 原图只在内存中过一遍，落库的只有结构化识别结果。
    #：用户若需要"原件留档"可显式打开，隐私说明会随之改变措辞。
    keep_photos: bool = field(default_factory=lambda: _env_bool("XUANPAN_KEEP_PHOTOS", False))

    #：图片落盘目录（仅当 keep_photos 为真时使用）
    photo_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("XUANPAN_PHOTO_DIR") or Path.cwd() / "data" / "uploads"
        )
    )

    #：AI 路由模式与任务参数
    ai_mode: str = field(default_factory=lambda: os.environ.get("XUANPAN_AI_MODE", "auto").strip() or "auto")

    #：CORS 允许来源（移动端调试期用；生产应由网关收敛）
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            x.strip() for x in os.environ.get("XUANPAN_CORS_ORIGINS", "*").split(",") if x.strip()
        )
    )

    @property
    def max_upload_mb(self) -> int:
        return max(1, self.max_upload_bytes // (1024 * 1024))


DEFAULT_SETTINGS = Settings()


__all__ = ["Settings", "DEFAULT_SETTINGS"]
