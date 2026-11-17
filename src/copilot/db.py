"""SQLite init + helpers for escalations, interactions, feedback."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import SQLITE_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    intent TEXT,
    severity_label TEXT,
    severity_score REAL,
    reason_terms TEXT,
    neighbors_json TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    resolution TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolved_by TEXT
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    route TEXT NOT NULL,
    intent TEXT,
    confidence REAL,
    severity_label TEXT,
    severity_score REAL,
    answer TEXT,
    escalation_id INTEGER,
    latency_ms INTEGER,
    thumbs TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interaction_id INTEGER NOT NULL,
    thumbs TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (interaction_id) REFERENCES interactions(id)
);
"""

# PRAGYAAN platform tables (users, tickets, workflow, knowledge hub, activity).
# All CREATE ... IF NOT EXISTS, so existing databases are upgraded in place.
PLATFORM_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'agent',
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    requester TEXT,
    predicted_priority TEXT,
    prob_low REAL,
    prob_medium REAL,
    prob_high REAL,
    confidence REAL,
    severity_score REAL,
    reason_terms TEXT,
    predicted_type TEXT,
    model_name TEXT,
    final_priority TEXT,
    reference_priority TEXT,
    corrected_by TEXT,
    corrected_at TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    source TEXT NOT NULL DEFAULT 'manual',
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS automation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    priority TEXT NOT NULL,
    action TEXT NOT NULL,
    sla_hours INTEGER NOT NULL DEFAULT 24,
    assignee TEXT,
    mode TEXT NOT NULL DEFAULT 'auto',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    ticket_id INTEGER,
    rule_id INTEGER,
    priority TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'todo',
    assignee TEXT,
    due_at TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    collection TEXT NOT NULL DEFAULT 'General',
    tags TEXT,
    file_type TEXT,
    size_bytes INTEGER,
    char_count INTEGER,
    chunk_count INTEGER,
    uploaded_by TEXT,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    ref_type TEXT,
    ref_id INTEGER,
    actor TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    page TEXT,
    ref_id INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notification_reads (
    notification_id INTEGER NOT NULL,
    user_email TEXT NOT NULL,
    PRIMARY KEY (notification_id, user_email)
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    meta_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tickets_created ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_activity_created ON activity(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_email, id);
"""

# Role-based authentication: Employee and Senior Analyst accounts, server-side sessions
# and password-reset requests. Passwords are only ever stored as salted PBKDF2 hashes;
# session tokens only as SHA-256 hashes.
AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login_id TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('employee', 'analyst')),
    department TEXT,
    title TEXT,
    password_hash TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    account_id INTEGER NOT NULL,
    remember INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    last_seen_at TEXT,
    revoked INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS password_reset_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    handled_by TEXT,
    handled_at TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_account ON sessions(account_id);
"""

# Columns added to tables that already exist in older databases.
_ADDED_COLUMNS = {
    "tickets": [
        ("requester_account_id", "INTEGER"),
        ("assignee_account_id", "INTEGER"),
        ("match_ticket_id", "INTEGER"),
        ("match_similarity", "REAL"),
        ("suggested_solution", "TEXT"),
        ("review_status", "TEXT NOT NULL DEFAULT 'none'"),
        ("resolution", "TEXT"),
        ("resolved_by", "TEXT"),
        ("resolved_at", "TEXT"),
    ],
    "notifications": [
        ("audience", "TEXT NOT NULL DEFAULT 'all'"),
        ("target_login", "TEXT"),
    ],
    # who asked (so the senior's answer goes back to them), and, when an employee escalates an answer
    # that didn't help, what the assistant answered and what they said was still wrong
    "escalations": [
        ("requester", "TEXT"),
        ("source", "TEXT NOT NULL DEFAULT 'unanswered'"),
        ("attempted_answer", "TEXT"),
        ("employee_note", "TEXT"),
    ],
}

_initialized: set[str] = set()


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in _ADDED_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in cols:
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_requester ON tickets(requester_account_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_assignee ON tickets(assignee_account_id)")
    # Recommended solutions now go to the employee instead of waiting for Senior Analyst approval.
    conn.execute("UPDATE tickets SET review_status = 'suggested' WHERE review_status = 'pending' AND status = 'open'")
    # Accounts created before role-based login (email + password, role admin/agent) keep working:
    # administrators become Senior Analysts, others Employees; the ID is their old email until
    # a Senior Analyst changes it in Team management. Password hashes are copied as-is.
    if conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
        legacy = conn.execute("SELECT email, name, role, password_hash, created_at FROM users").fetchall()
        for email, name, role, pw_hash, created in legacy:
            conn.execute(
                "INSERT OR IGNORE INTO accounts (login_id, name, role, password_hash, created_by, created_at) "
                "VALUES (?, ?, ?, ?, 'migration', ?)",
                (email.lower(), name, "analyst" if role == "admin" else "employee", pw_hash, created),
            )


def ensure_db(path: Path | None = None) -> Path:
    db_path = path or SQLITE_PATH
    key = str(db_path)
    if key in _initialized and db_path.exists():
        return db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(PLATFORM_SCHEMA_SQL)
        conn.executescript(AUTH_SCHEMA_SQL)
        _migrate(conn)
        conn.commit()
    _initialized.add(key)
    return db_path


@contextmanager
def get_conn(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    db_path = ensure_db(path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def execute(sql: str, params: tuple[Any, ...] = (), path: Path | None = None) -> int:
    with get_conn(path) as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)


def fetchall(sql: str, params: tuple[Any, ...] = (), path: Path | None = None) -> list[dict]:
    with get_conn(path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def fetchone(sql: str, params: tuple[Any, ...] = (), path: Path | None = None) -> dict | None:
    with get_conn(path) as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None
