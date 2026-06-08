import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import LlmSettings, Topic, TopicCreate


SCHEMA = """
CREATE TABLE IF NOT EXISTS topics (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'new',
    graph_path TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
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
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def create_topic(self, payload: TopicCreate) -> Topic:
        now = _now()
        topic_id = _slug_id(payload.name)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO topics (id, name, description, status, created_at, updated_at)
                VALUES (?, ?, ?, 'new', ?, ?)
                """,
                (topic_id, payload.name.strip(), payload.description.strip(), now, now),
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
        graph_path: str | None = None,
        last_error: str | None = None,
    ) -> Topic:
        topic = self.get_topic(topic_id)
        values = {
            "status": status if status is not None else topic.status,
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
                    graph_path = :graph_path,
                    last_error = :last_error,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                values,
            )
        return self.get_topic(topic_id)

    def delete_topic(self, topic_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))

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
        graph_path=row["graph_path"],
        last_error=row["last_error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
