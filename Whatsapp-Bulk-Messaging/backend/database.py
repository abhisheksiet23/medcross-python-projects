"""
SQLite schema + connection helpers for the platform.
Kept intentionally simple (no ORM) so it's easy to read and extend.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS groups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,
    phone        TEXT NOT NULL UNIQUE,
    email        TEXT,
    group_id     INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    tags         TEXT,                 -- comma separated
    notes        TEXT,
    opted_in     INTEGER DEFAULT 1,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS templates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,        -- must match Meta-approved template name
    category      TEXT,                 -- MARKETING / UTILITY / AUTHENTICATION
    language_code TEXT DEFAULT 'en_US',
    body_preview  TEXT,                 -- human readable preview w/ {{1}} placeholders
    variable_count INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'approved',  -- approved / pending / rejected (mirrors Meta status)
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaigns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    template_id   INTEGER REFERENCES templates(id),
    group_id      INTEGER REFERENCES groups(id),
    status        TEXT DEFAULT 'draft',   -- draft / scheduled / sending / paused / completed / failed
    scheduled_at  TEXT,
    started_at    TEXT,
    completed_at  TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS campaign_recipients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id   INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id    INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    wa_message_id TEXT,
    status        TEXT DEFAULT 'pending', -- pending/sent/delivered/read/failed/replied
    failed_reason TEXT,
    sent_at       TEXT,
    delivered_at  TEXT,
    read_at       TEXT,
    replied_at    TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id    INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    campaign_id   INTEGER REFERENCES campaigns(id),
    direction     TEXT NOT NULL,      -- 'in' or 'out'
    wa_message_id TEXT,
    body          TEXT,
    message_type  TEXT DEFAULT 'text',
    template_name TEXT,
    status        TEXT DEFAULT 'sent',  -- sent/delivered/read/failed/received
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id);
CREATE INDEX IF NOT EXISTS idx_campaign_recipients_campaign ON campaign_recipients(campaign_id);
"""


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db_cursor():
    """Context manager yielding a cursor, committing on success."""
    conn = get_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def now() -> str:
    return datetime.now().isoformat()


def get_setting(key: str, default: str = "") -> str:
    with db_cursor() as cur:
        row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
