import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import ChatMessage, ChatThread, LlmSettings, ThreadCreate, Topic, TopicCreate

DEFAULT_USER_ID = "legacy-default"


SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'legacy-default',
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    progress_percent INTEGER NOT NULL DEFAULT 0,
    progress_label TEXT NOT NULL DEFAULT '',
    graph_path TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_threads (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'legacy-default',
    topic_id TEXT NOT NULL,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES topics(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(thread_id) REFERENCES chat_threads(id) ON DELETE CASCADE
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_topics_user_updated_at ON topics(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_threads_user_topic_updated_at ON chat_threads(user_id, topic_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created_at ON chat_messages(thread_id, created_at ASC);
"""


class TopicStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            topic_columns = {row["name"] for row in conn.execute("PRAGMA table_info(topics)").fetchall()}
            if "user_id" not in topic_columns:
                _safe_add_column(conn, f"ALTER TABLE topics ADD COLUMN user_id TEXT NOT NULL DEFAULT '{DEFAULT_USER_ID}'")
            if "graph_path" not in topic_columns:
                _safe_add_column(conn, "ALTER TABLE topics ADD COLUMN graph_path TEXT")
            if "last_error" not in topic_columns:
                _safe_add_column(conn, "ALTER TABLE topics ADD COLUMN last_error TEXT")
            if "progress_percent" not in topic_columns:
                _safe_add_column(conn, "ALTER TABLE topics ADD COLUMN progress_percent INTEGER NOT NULL DEFAULT 0")
            if "progress_label" not in topic_columns:
                _safe_add_column(conn, "ALTER TABLE topics ADD COLUMN progress_label TEXT NOT NULL DEFAULT ''")
            thread_columns = {row["name"] for row in conn.execute("PRAGMA table_info(chat_threads)").fetchall()}
            if "user_id" not in thread_columns:
                _safe_add_column(conn, f"ALTER TABLE chat_threads ADD COLUMN user_id TEXT NOT NULL DEFAULT '{DEFAULT_USER_ID}'")
                conn.execute(
                    """
                    UPDATE chat_threads
                    SET user_id = COALESCE(
                        (SELECT topics.user_id FROM topics WHERE topics.id = chat_threads.topic_id),
                        ?
                    )
                    """,
                    (DEFAULT_USER_ID,),
                )
            conn.executescript(INDEXES)

    def create_topic(self, payload: TopicCreate, user_id: str = DEFAULT_USER_ID) -> Topic:
        now = _now()
        topic_id = _slug_id(payload.name)
        initial_thread_title = payload.initial_thread_title.strip() or "New chat"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO topics (id, user_id, name, description, status, progress_percent, progress_label, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'new', 0, '', ?, ?)
                """,
                (topic_id, user_id, payload.name.strip(), payload.description.strip(), now, now),
            )
            thread_id = _slug_id("New chat")
            conn.execute(
                """
                INSERT INTO chat_threads (id, user_id, topic_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_id, user_id, topic_id, initial_thread_title, now, now),
            )
        return self.get_topic(topic_id, user_id=user_id)

    def list_topics(self, user_id: str = DEFAULT_USER_ID) -> list[Topic]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM topics WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [_row_to_topic(row) for row in rows]

    def get_topic(self, topic_id: str, user_id: str = DEFAULT_USER_ID) -> Topic:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM topics WHERE id = ? AND user_id = ?",
                (topic_id, user_id),
            ).fetchone()
        if row is None:
            raise KeyError(topic_id)
        return _row_to_topic(row)

    def update_topic(
        self,
        topic_id: str,
        user_id: str = DEFAULT_USER_ID,
        *,
        status: str | None = None,
        progress_percent: int | None = None,
        progress_label: str | None = None,
        graph_path: str | None = None,
        last_error: str | None = None,
    ) -> Topic:
        topic = self.get_topic(topic_id, user_id=user_id)
        values = {
            "status": status if status is not None else topic.status,
            "progress_percent": progress_percent if progress_percent is not None else topic.progress_percent,
            "progress_label": progress_label if progress_label is not None else topic.progress_label,
            "graph_path": graph_path if graph_path is not None else topic.graph_path,
            "last_error": last_error,
            "updated_at": _now(),
            "id": topic_id,
            "user_id": user_id,
        }
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE topics
                SET status = :status,
                    progress_percent = :progress_percent,
                    progress_label = :progress_label,
                    graph_path = :graph_path,
                    last_error = :last_error,
                    updated_at = :updated_at
                WHERE id = :id AND user_id = :user_id
                """,
                values,
            )
        return self.get_topic(topic_id, user_id=user_id)

    def update_topic_description(self, topic_id: str, description: str, user_id: str = DEFAULT_USER_ID) -> Topic:
        self.get_topic(topic_id, user_id=user_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE topics
                SET description = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (description.strip(), _now(), topic_id, user_id),
            )
        return self.get_topic(topic_id, user_id=user_id)

    def delete_topic(self, topic_id: str, user_id: str = DEFAULT_USER_ID) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM topics WHERE id = ? AND user_id = ?", (topic_id, user_id))

    def list_threads(self, topic_id: str | None = None, user_id: str = DEFAULT_USER_ID) -> list[ChatThread]:
        with self._connect() as conn:
            if topic_id:
                rows = conn.execute(
                    "SELECT * FROM chat_threads WHERE topic_id = ? AND user_id = ? ORDER BY updated_at DESC",
                    (topic_id, user_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM chat_threads WHERE user_id = ? ORDER BY updated_at DESC",
                    (user_id,),
                ).fetchall()
        return [_row_to_thread(row) for row in rows]

    def delete_thread(self, thread_id: str, user_id: str = DEFAULT_USER_ID) -> None:
        thread = self.get_thread(thread_id, user_id=user_id)
        with self._connect() as conn:
            conn.execute("DELETE FROM chat_threads WHERE id = ? AND user_id = ?", (thread_id, user_id))
            conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (_now(), thread.topic_id))

    def delete_threads_by_title(self, topic_id: str, title: str, user_id: str = DEFAULT_USER_ID) -> int:
        self.get_topic(topic_id, user_id=user_id)
        normalized = title.strip()
        if not normalized:
            return 0
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM chat_threads WHERE topic_id = ? AND user_id = ? AND title = ?",
                (topic_id, user_id, normalized),
            )
            deleted = int(cursor.rowcount or 0)
            if deleted:
                conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (_now(), topic_id))
        return deleted

    def create_thread(self, topic_id: str, payload: ThreadCreate, user_id: str = DEFAULT_USER_ID) -> ChatThread:
        self.get_topic(topic_id, user_id=user_id)
        now = _now()
        thread_id = _slug_id(payload.title)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_threads (id, user_id, topic_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_id, user_id, topic_id, payload.title.strip(), now, now),
            )
            conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, topic_id))
        return self.get_thread(thread_id, user_id=user_id)

    def get_thread(self, thread_id: str, user_id: str = DEFAULT_USER_ID) -> ChatThread:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM chat_threads WHERE id = ? AND user_id = ?",
                (thread_id, user_id),
            ).fetchone()
        if row is None:
            raise KeyError(thread_id)
        return _row_to_thread(row)

    def list_messages(self, thread_id: str, user_id: str = DEFAULT_USER_ID) -> list[ChatMessage]:
        self.get_thread(thread_id, user_id=user_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE thread_id = ? ORDER BY created_at ASC",
                (thread_id,),
            ).fetchall()
        return [_row_to_message(row) for row in rows]

    def append_message(self, thread_id: str, role: str, text: str, user_id: str = DEFAULT_USER_ID) -> ChatMessage:
        thread = self.get_thread(thread_id, user_id=user_id)
        now = _now()
        message_id = _slug_id(role)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_messages (id, thread_id, role, text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message_id, thread_id, role, text.strip(), now),
            )
            conn.execute("UPDATE chat_threads SET updated_at = ? WHERE id = ?", (now, thread_id))
            conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, thread.topic_id))
        return self.get_message(message_id)

    def get_message(self, message_id: str) -> ChatMessage:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM chat_messages WHERE id = ?", (message_id,)).fetchone()
        if row is None:
            raise KeyError(message_id)
        return _row_to_message(row)

    def update_message_text(self, message_id: str, text: str, user_id: str = DEFAULT_USER_ID) -> ChatMessage:
        message = self.get_message(message_id)
        self.get_thread(message.thread_id, user_id=user_id)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE chat_messages SET text = ? WHERE id = ?",
                (text.strip(), message_id),
            )
            conn.execute(
                "UPDATE chat_threads SET updated_at = ? WHERE id = ?",
                (now, message.thread_id),
            )
        return self.get_message(message_id)

    def rename_thread(self, thread_id: str, title: str, user_id: str = DEFAULT_USER_ID) -> ChatThread:
        thread = self.get_thread(thread_id, user_id=user_id)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE chat_threads SET title = ?, updated_at = ? WHERE id = ?",
                (title.strip(), now, thread_id),
            )
            conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, thread.topic_id))
        return self.get_thread(thread_id, user_id=user_id)

    def get_llm_settings(self, defaults: LlmSettings, user_id: str = DEFAULT_USER_ID) -> LlmSettings:
        with self._connect() as conn:
            prefix = f"llm.{user_id}."
            rows = conn.execute(
                "SELECT key, value FROM app_settings WHERE key LIKE ?",
                (f"{prefix}%",),
            ).fetchall()
            if not rows and user_id == DEFAULT_USER_ID:
                rows = conn.execute("SELECT key, value FROM app_settings WHERE key LIKE 'llm.%'").fetchall()
        values = defaults.model_dump()
        for row in rows:
            key = row["key"]
            if key.startswith(prefix):
                field = key.replace(prefix, "", 1)
            else:
                field = key.replace("llm.", "", 1)
            if field in values:
                values[field] = row["value"]
        return LlmSettings(**values)

    def update_llm_settings(self, payload: LlmSettings, user_id: str = DEFAULT_USER_ID) -> LlmSettings:
        values = payload.model_dump()
        with self._connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (f"llm.{user_id}.{key}", str(value)),
                )
        return payload

    def clear_llm_settings(self, user_id: str = DEFAULT_USER_ID) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM app_settings WHERE key LIKE ?", (f"llm.{user_id}.%",))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_id(name: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    clean = "-".join(part for part in clean.split("-") if part)
    return f"{clean[:48] or 'topic'}-{uuid.uuid4().hex[:8]}"


def _safe_add_column(conn: sqlite3.Connection, sql: str) -> None:
    try:
        conn.execute(sql)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def _row_to_topic(row: sqlite3.Row) -> Topic:
    return Topic(
        id=row["id"],
        user_id=row["user_id"] or DEFAULT_USER_ID,
        name=row["name"],
        description=row["description"],
        status=row["status"],
        progress_percent=int(row["progress_percent"] or 0),
        progress_label=row["progress_label"] or "",
        graph_path=row["graph_path"],
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_thread(row: sqlite3.Row) -> ChatThread:
    return ChatThread(
        id=row["id"],
        user_id=row["user_id"] or DEFAULT_USER_ID,
        topic_id=row["topic_id"],
        title=row["title"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_message(row: sqlite3.Row) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        thread_id=row["thread_id"],
        role=row["role"],
        text=row["text"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
