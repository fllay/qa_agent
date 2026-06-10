import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import ChatMessage, ChatThread, LlmSettings, ThreadCreate, Topic, TopicCreate


SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
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
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(topics)").fetchall()}
            if "progress_percent" not in columns:
                conn.execute("ALTER TABLE topics ADD COLUMN progress_percent INTEGER NOT NULL DEFAULT 0")
            if "progress_label" not in columns:
                conn.execute("ALTER TABLE topics ADD COLUMN progress_label TEXT NOT NULL DEFAULT ''")

    def create_topic(self, payload: TopicCreate) -> Topic:
        now = _now()
        topic_id = _slug_id(payload.name)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO topics (id, name, description, status, progress_percent, progress_label, created_at, updated_at)
                VALUES (?, ?, ?, 'new', 0, '', ?, ?)
                """,
                (topic_id, payload.name.strip(), payload.description.strip(), now, now),
            )
            thread_id = _slug_id("Agent Chat")
            conn.execute(
                """
                INSERT INTO chat_threads (id, topic_id, title, created_at, updated_at)
                VALUES (?, ?, 'Agent Chat', ?, ?)
                """,
                (thread_id, topic_id, now, now),
            )
        return self.get_topic(topic_id)

    def list_topics(self) -> list[Topic]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM topics ORDER BY updated_at DESC").fetchall()
        return [_row_to_topic(row) for row in rows]

    def get_topic(self, topic_id: str) -> Topic:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        if row is None:
            raise KeyError(topic_id)
        return _row_to_topic(row)

    def update_topic(
        self,
        topic_id: str,
        *,
        status: str | None = None,
        progress_percent: int | None = None,
        progress_label: str | None = None,
        graph_path: str | None = None,
        last_error: str | None = None,
    ) -> Topic:
        topic = self.get_topic(topic_id)
        values = {
            "status": status if status is not None else topic.status,
            "progress_percent": progress_percent if progress_percent is not None else topic.progress_percent,
            "progress_label": progress_label if progress_label is not None else topic.progress_label,
            "graph_path": graph_path if graph_path is not None else topic.graph_path,
            "last_error": last_error,
            "updated_at": _now(),
            "id": topic_id,
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
                WHERE id = :id
                """,
                values,
            )
        return self.get_topic(topic_id)

    def update_topic_description(self, topic_id: str, description: str) -> Topic:
        self.get_topic(topic_id)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE topics
                SET description = ?, updated_at = ?
                WHERE id = ?
                """,
                (description.strip(), _now(), topic_id),
            )
        return self.get_topic(topic_id)

    def delete_topic(self, topic_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))

    def list_threads(self, topic_id: str | None = None) -> list[ChatThread]:
        with self._connect() as conn:
            if topic_id:
                rows = conn.execute(
                    "SELECT * FROM chat_threads WHERE topic_id = ? ORDER BY updated_at DESC",
                    (topic_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM chat_threads ORDER BY updated_at DESC").fetchall()
        return [_row_to_thread(row) for row in rows]

    def create_thread(self, topic_id: str, payload: ThreadCreate) -> ChatThread:
        self.get_topic(topic_id)
        now = _now()
        thread_id = _slug_id(payload.title)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chat_threads (id, topic_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (thread_id, topic_id, payload.title.strip(), now, now),
            )
            conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, topic_id))
        return self.get_thread(thread_id)

    def get_thread(self, thread_id: str) -> ChatThread:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM chat_threads WHERE id = ?", (thread_id,)).fetchone()
        if row is None:
            raise KeyError(thread_id)
        return _row_to_thread(row)

    def list_messages(self, thread_id: str) -> list[ChatMessage]:
        self.get_thread(thread_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages WHERE thread_id = ? ORDER BY created_at ASC",
                (thread_id,),
            ).fetchall()
        return [_row_to_message(row) for row in rows]

    def append_message(self, thread_id: str, role: str, text: str) -> ChatMessage:
        thread = self.get_thread(thread_id)
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

    def rename_thread(self, thread_id: str, title: str) -> ChatThread:
        thread = self.get_thread(thread_id)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE chat_threads SET title = ?, updated_at = ? WHERE id = ?",
                (title.strip(), now, thread_id),
            )
            conn.execute("UPDATE topics SET updated_at = ? WHERE id = ?", (now, thread.topic_id))
        return self.get_thread(thread_id)

    def get_llm_settings(self, defaults: LlmSettings) -> LlmSettings:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM app_settings WHERE key LIKE 'llm.%'").fetchall()
        values = defaults.model_dump()
        for row in rows:
            field = row["key"].replace("llm.", "", 1)
            if field in values:
                values[field] = row["value"]
        return LlmSettings(**values)

    def update_llm_settings(self, payload: LlmSettings) -> LlmSettings:
        values = payload.model_dump()
        with self._connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (f"llm.{key}", str(value)),
                )
        return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug_id(name: str) -> str:
    clean = "".join(ch.lower() if ch.isalnum() else "-" for ch in name.strip())
    clean = "-".join(part for part in clean.split("-") if part)
    return f"{clean[:48] or 'topic'}-{uuid.uuid4().hex[:8]}"


def _row_to_topic(row: sqlite3.Row) -> Topic:
    return Topic(
        id=row["id"],
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
