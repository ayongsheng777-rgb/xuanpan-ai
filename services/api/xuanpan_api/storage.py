"""SQLite 持久化 —— 零外部依赖（不需要 PostgreSQL / Redis 就能跑通全链路）。

**只存用户输入，不存派生结果**（关键设计）
数据库里保存的是"用户给了什么"（生辰、坐向、摇卦结果…），
而不是"算出了什么"。因为 fortune-core 是确定性的：同样的输入永远得到同样的
输出。这样做有三个好处：

1. **不可能出现"库里结果与内核结果不一致"** —— 只有一份真源
2. 内核升级后，历史记录会自动按新版本重算，而不是留着一批旧口径的僵尸数据
3. 不违反 RULE-008（不篡改用户数据）：录入即原样保存

AI 报告则**必须落库**：它是外部模型的产物，非确定性、不可重算，
丢了就没了。所以 `reports` 表存的是三层全量快照。

隐私默认（见 `config.Settings.keep_photos`）：原图默认**不落盘**，
只在内存里过一遍识别链路；落库的只有结构化识别结果。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id        TEXT PRIMARY KEY,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    title             TEXT NOT NULL DEFAULT '',
    origin            TEXT NOT NULL DEFAULT '',
    question_category TEXT,
    question_text     TEXT,
    compass_input     TEXT,
    bazi_input        TEXT,
    liuyao_input      TEXT,
    qian_input        TEXT,
    naming_input      TEXT,
    recognition       TEXT,
    confirm_state     TEXT
);

CREATE TABLE IF NOT EXISTS reports (
    report_id  TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    question   TEXT,
    payload    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS turns (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    report_id  TEXT,
    created_at TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_reports_session ON reports(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_turns_session   ON turns(session_id, id);
CREATE INDEX IF NOT EXISTS idx_sessions_time   ON sessions(updated_at DESC);
"""

#：会话里所有 input 列（用于统一读写）
INPUT_COLUMNS = (
    "compass_input", "bazi_input", "liuyao_input", "qian_input", "naming_input",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Store:
    """SQLite 存储。无状态（每次调用开独立连接），因此可安全用于多线程。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        """建表（幂等）。"""
        with self.connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES('version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(SCHEMA_VERSION),),
            )

    def schema_version(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM schema_meta WHERE key='version'").fetchone()
        return int(row["value"]) if row else 0

    # ---------------- 会话 ----------------

    def create_session(
        self,
        *,
        origin: str = "",
        title: str = "",
        question_category: str | None = None,
        question_text: str | None = None,
    ) -> str:
        session_id = new_id("sess")
        stamp = _now()
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(session_id, created_at, updated_at, title, origin,"
                " question_category, question_text) VALUES(?,?,?,?,?,?,?)",
                (session_id, stamp, stamp, title, origin, question_category, question_text),
            )
        return session_id

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        return _decode_session(row) if row else None

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """列表页只要摘要，不回传全量输入（列表会变重）。"""
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT session_id, created_at, updated_at, title, origin,"
                " question_category, question_text,"
                " (compass_input IS NOT NULL) AS has_compass,"
                " (bazi_input    IS NOT NULL) AS has_bazi,"
                " (liuyao_input  IS NOT NULL) AS has_liuyao,"
                " (qian_input    IS NOT NULL) AS has_qian,"
                " (naming_input  IS NOT NULL) AS has_naming,"
                " (recognition   IS NOT NULL) AS has_recognition,"
                " (SELECT COUNT(*) FROM reports r WHERE r.session_id = s.session_id) AS report_count"
                " FROM sessions s ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (max(1, limit), max(0, offset)),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_sessions(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        return int(row["n"]) if row else 0

    def stats(self) -> dict[str, int]:
        """各表行数概览。

        供管理界面显示体量。**刻意不做任何业务判断**（如"报告率是否健康"）——
        那属于上层的事，存储层只回答"有几行"。
        """
        with self.connect() as conn:
            return {
                name: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                # 表名是**本模块的常量**，不含用户输入，故 f-string 拼入安全。
                for name, table in (
                    ("sessions", "sessions"),
                    ("reports", "reports"),
                    ("turns", "turns"),
                )
            }

    def update_session(
        self,
        session_id: str,
        *,
        inputs: dict[str, Any] | None = None,
        recognition: dict[str, Any] | None = None,
        confirm_state: dict[str, Any] | None = None,
        question_category: str | None = None,
        question_text: str | None = None,
        title: str | None = None,
        origin: str | None = None,
    ) -> bool:
        """按列更新。未传的列保持原值（**不做整行覆盖**，避免竞态下丢数据）。"""
        sets: list[str] = ["updated_at = ?"]
        values: list[Any] = [_now()]

        for column, value in (inputs or {}).items():
            if column not in INPUT_COLUMNS:
                raise ValueError(f"未知的输入列：{column}")
            sets.append(f"{column} = ?")
            values.append(json.dumps(value, ensure_ascii=False) if value is not None else None)

        if recognition is not None:
            sets.append("recognition = ?")
            values.append(json.dumps(recognition, ensure_ascii=False))
        if confirm_state is not None:
            sets.append("confirm_state = ?")
            values.append(json.dumps(confirm_state, ensure_ascii=False))
        if question_category is not None:
            sets.append("question_category = ?")
            values.append(question_category)
        if question_text is not None:
            sets.append("question_text = ?")
            values.append(question_text)
        if title is not None:
            sets.append("title = ?")
            values.append(title)
        if origin is not None:
            sets.append("origin = ?")
            values.append(origin)

        values.append(session_id)
        with self.connect() as conn:
            cur = conn.execute(
                f"UPDATE sessions SET {', '.join(sets)} WHERE session_id = ?", values
            )
        return cur.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """删除会话及其报告、对话轮次（外键级联）。

        这是**用户主动要求**的删除（RULE-008 的删除权），不是系统清理。
        """
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        return cur.rowcount > 0

    # ---------------- 报告 ----------------

    def save_report(
        self,
        session_id: str,
        payload: dict[str, Any],
        *,
        question: str | None = None,
    ) -> str:
        report_id = new_id("rep")
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO reports(report_id, session_id, created_at, question, payload)"
                " VALUES(?,?,?,?,?)",
                (report_id, session_id, _now(), question, json.dumps(payload, ensure_ascii=False)),
            )
        self.update_session(session_id, origin="report")
        return report_id

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM reports WHERE report_id = ?", (report_id,)
            ).fetchone()
        if not row:
            return None
        return {
            "report_id": row["report_id"],
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "question": row["question"],
            "payload": json.loads(row["payload"]),
        }

    def list_reports(self, session_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT report_id, session_id, created_at, question FROM reports"
                " WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------------- 多轮对话 ----------------

    def add_turn(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
        report_id: str | None = None,
    ) -> int:
        if role not in ("user", "assistant"):
            raise ValueError(f"role 须为 user/assistant，收到 {role!r}")
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO turns(session_id, report_id, created_at, role, content)"
                " VALUES(?,?,?,?,?)",
                (session_id, report_id, _now(), role, content),
            )
        return int(cur.lastrowid or 0)

    def list_turns(self, session_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, report_id, created_at, role, content FROM turns"
                " WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, max(1, limit)),
            ).fetchall()
        return [dict(r) for r in rows]


def _decode_session(row: sqlite3.Row) -> dict[str, Any]:
    out = dict(row)
    for key in (*INPUT_COLUMNS, "recognition", "confirm_state"):
        raw = out.get(key)
        if isinstance(raw, str) and raw:
            try:
                out[key] = json.loads(raw)
            except ValueError:
                out[key] = None
    return out


__all__ = ["Store", "SCHEMA_VERSION", "INPUT_COLUMNS", "new_id"]
