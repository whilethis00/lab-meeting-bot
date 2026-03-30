"""SQLite DB 초기화 및 연결 관리 (aiosqlite + FTS5)"""
import os
import aiosqlite
from bot.config import DATABASE_PATH

_CREATE_MEETINGS = """
CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    title TEXT,
    raw_transcript TEXT NOT NULL,
    parsed_data TEXT,
    summary TEXT,
    decisions TEXT,
    open_issues TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    telegram_chat_id INTEGER
);
"""

_CREATE_MEETINGS_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS meetings_fts USING fts5(
    date, title, summary, decisions, open_issues,
    content='meetings', content_rowid='id'
);
"""

_CREATE_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS meetings_ai AFTER INSERT ON meetings BEGIN
    INSERT INTO meetings_fts(rowid, date, title, summary, decisions, open_issues)
    VALUES (new.id, new.date, new.title, new.summary, new.decisions, new.open_issues);
END;

CREATE TRIGGER IF NOT EXISTS meetings_au AFTER UPDATE ON meetings BEGIN
    INSERT INTO meetings_fts(meetings_fts, rowid, date, title, summary, decisions, open_issues)
    VALUES('delete', old.id, old.date, old.title, old.summary, old.decisions, old.open_issues);
    INSERT INTO meetings_fts(rowid, date, title, summary, decisions, open_issues)
    VALUES (new.id, new.date, new.title, new.summary, new.decisions, new.open_issues);
END;
"""

_CREATE_ACTION_ITEMS = """
CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER REFERENCES meetings(id),
    description TEXT NOT NULL,
    assignee TEXT,
    deadline TEXT,
    priority TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
"""

_CREATE_SPEAKER_NAMES = """
CREATE TABLE IF NOT EXISTS speaker_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    clova_label TEXT NOT NULL,
    real_name TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(chat_id, clova_label)
);
"""

_CREATE_CHAT_CONTEXT = """
CREATE TABLE IF NOT EXISTS chat_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_CHAT_SETTINGS = """
CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    languages TEXT DEFAULT 'ko',
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


async def init_db():
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(_CREATE_MEETINGS)
        await db.execute(_CREATE_ACTION_ITEMS)
        await db.execute(_CREATE_SPEAKER_NAMES)
        await db.execute(_CREATE_CHAT_CONTEXT)
        await db.execute(_CREATE_CHAT_SETTINGS)
        # FTS5 (검색용)
        await db.execute(_CREATE_MEETINGS_FTS)
        for stmt in _CREATE_FTS_TRIGGERS.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await db.execute(stmt)
                except Exception:
                    pass  # 이미 존재하면 무시
        await db.commit()


def get_db_path() -> str:
    return DATABASE_PATH
