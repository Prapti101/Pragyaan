"""Activity feed and in-app notifications (SQLite).

Notifications have an audience: 'all' (everyone), 'analyst' / 'employee' (everyone with
that role) or 'user' (one person, by login ID in target_login). Each person only sees the
notifications addressed to them.
"""

from __future__ import annotations

from .db import execute, fetchall, fetchone


def log_activity(kind: str, message: str, *, ref_type: str | None = None,
                 ref_id: int | None = None, actor: str | None = None) -> int:
    return execute(
        "INSERT INTO activity (kind, message, ref_type, ref_id, actor) VALUES (?, ?, ?, ?, ?)",
        (kind, message, ref_type, ref_id, actor),
    )


def recent_activity(limit: int = 15, actor: str | None = None) -> list[dict]:
    if actor:
        return fetchall("SELECT * FROM activity WHERE actor = ? ORDER BY id DESC LIMIT ?", (actor, limit))
    return fetchall("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,))


def notify(message: str, *, level: str = "info", page: str | None = None, ref_id: int | None = None,
           audience: str = "analyst", target_login: str | None = None) -> int:
    """Create a notification. Operational alerts go to Senior Analysts by default;
    pass audience='user' with target_login to notify one person."""
    if target_login:
        audience = "user"
    return execute(
        "INSERT INTO notifications (message, level, page, ref_id, audience, target_login) VALUES (?, ?, ?, ?, ?, ?)",
        (message, level, page, ref_id, audience, target_login),
    )


def _visible(alias: str = "n") -> str:
    return (f"({alias}.audience = 'all' OR {alias}.audience = ? OR "
            f"({alias}.audience = 'user' AND {alias}.target_login = ? COLLATE NOCASE))")


def _role_of(user_login: str, role: str | None) -> str:
    if role:
        return role
    row = fetchone("SELECT role FROM accounts WHERE login_id = ?", (user_login,))
    return row["role"] if row else "analyst"


def list_notifications(user_login: str, limit: int = 20, role: str | None = None) -> list[dict]:
    role = _role_of(user_login, role)
    return fetchall(
        f"""
        SELECT n.*, CASE WHEN r.notification_id IS NULL THEN 0 ELSE 1 END AS is_read
        FROM notifications n
        LEFT JOIN notification_reads r
               ON r.notification_id = n.id AND r.user_email = ?
        WHERE {_visible()}
        ORDER BY n.id DESC LIMIT ?
        """,
        (user_login, role, user_login, limit),
    )


def unread_count(user_login: str, role: str | None = None) -> int:
    role = _role_of(user_login, role)
    row = fetchone(
        f"""
        SELECT COUNT(*) AS n FROM notifications n
        WHERE {_visible()} AND NOT EXISTS (SELECT 1 FROM notification_reads r
                          WHERE r.notification_id = n.id AND r.user_email = ?)
        """,
        (role, user_login, user_login),
    )
    return int(row["n"]) if row else 0


def mark_all_read(user_login: str, role: str | None = None) -> None:
    role = _role_of(user_login, role)
    execute(
        f"""
        INSERT OR IGNORE INTO notification_reads (notification_id, user_email)
        SELECT n.id, ? FROM notifications n WHERE {_visible()}
        """,
        (user_login, role, user_login),
    )
