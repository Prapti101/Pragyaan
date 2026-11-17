"""Role-based authentication for PRAGYAAN: Employee and Senior Analyst accounts.

Security model
- Passwords: salted PBKDF2-HMAC-SHA256 (200k iterations), never stored in plain text.
- Sign-in: checked against the account's role, so an Employee ID cannot open the Senior
  Analyst portal (and vice versa). Unknown IDs get the same message and the same hashing
  cost as wrong passwords, so the form does not reveal which IDs exist.
- Lockout: 5 failed attempts lock the account for 5 minutes.
- Sessions: random 256-bit tokens; only their SHA-256 hash is stored. Sessions expire
  (12 hours, or 30 days with "Remember me") and are revoked on sign-out, password change,
  password reset and deactivation.
- No default or hard-coded accounts: the first Senior Analyst is created in the first-run
  setup screen or with scripts/create_account.py; everyone else is created by an analyst.

Every function re-reads the account from the database, so role and active status are
always enforced server-side.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import string

from .db import execute, fetchall, fetchone

ROLES = ("employee", "analyst")
ROLE_LABELS = {"employee": "Employee", "analyst": "Senior Analyst"}
ID_LABELS = {"employee": "Employee ID", "analyst": "Senior Analyst ID"}

_ITERATIONS = 200_000
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 5
SESSION_HOURS = 12
REMEMBER_DAYS = 30
# New IDs: letters, digits and . _ - ; 3-64 characters (e.g. EMP-1042, SA-007). IDs are not
# e-mail addresses; accounts migrated from the old e-mail sign-in keep their address until a
# Senior Analyst gives them a new ID.
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
_DUMMY_HASH = None  # computed lazily, used to equalise timing for unknown IDs

_PUBLIC = "id, login_id, name, role, department, title, must_change_password, is_active, created_at, last_login_at"


class AuthError(ValueError):
    """Message is safe to show to the user."""


class PermissionDenied(PermissionError):
    """The signed-in account's role does not allow this action."""


# ---------------------------------------------------------------- passwords

def _hash(password: str, salt: bytes, iterations: int = _ITERATIONS) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"


def hash_password(password: str) -> str:
    return _hash(password, secrets.token_bytes(16))


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, _ = stored.split("$")
        candidate = _hash(password, bytes.fromhex(salt_hex), int(iters))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, stored)


def password_problem(password: str) -> str | None:
    """Why a new password is not acceptable, or None."""
    pw = password or ""
    if len(pw) < 8:
        return "Use at least 8 characters."
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        return "Use both letters and numbers."
    return None


def generate_temporary_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if password_problem(pw) is None:
            return pw


# ---------------------------------------------------------------- accounts

def normalize_id(login_id: str) -> str:
    return (login_id or "").strip()


def _public(row: dict | None) -> dict | None:
    if not row:
        return None
    keys = ("id", "login_id", "name", "role", "department", "title", "must_change_password", "is_active",
            "created_at", "last_login_at")
    out = {k: row.get(k) for k in keys}
    out["must_change_password"] = bool(out["must_change_password"])
    out["is_active"] = bool(out["is_active"])
    out["role_label"] = ROLE_LABELS.get(out["role"], out["role"])
    out["email"] = out["login_id"]  # actor key used across the app (activity, chat, notifications)
    return out


def get_account(account_id: int) -> dict | None:
    return _public(fetchone(f"SELECT {_PUBLIC} FROM accounts WHERE id = ?", (account_id,)))


def get_account_by_login(login_id: str) -> dict | None:
    return _public(fetchone(f"SELECT {_PUBLIC} FROM accounts WHERE login_id = ?", (normalize_id(login_id),)))


def list_accounts(role: str | None = None, active_only: bool = False) -> list[dict]:
    where, params = [], []
    if role:
        where.append("role = ?")
        params.append(role)
    if active_only:
        where.append("is_active = 1")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    rows = fetchall(f"SELECT {_PUBLIC} FROM accounts {clause} ORDER BY role DESC, name COLLATE NOCASE", tuple(params))
    return [_public(r) for r in rows]


def analyst_count(active_only: bool = True) -> int:
    row = fetchone("SELECT COUNT(*) AS n FROM accounts WHERE role = 'analyst'" + (" AND is_active = 1" if active_only else ""))
    return int(row["n"]) if row else 0


def needs_setup() -> bool:
    """True until the first Senior Analyst account exists."""
    return analyst_count(active_only=True) == 0


def require_role(actor: dict | None, *roles: str) -> dict:
    """Server-side permission check: re-reads the account so stale sessions can't keep a role."""
    acct = get_account(int(actor["id"])) if actor and actor.get("id") else None
    if not acct or not acct["is_active"] or acct["role"] not in roles:
        raise PermissionDenied("You don't have permission to do this.")
    return acct


def bootstrap_accounts_from_env() -> list[str]:
    """Create the accounts named in the hosting secrets, for deployments without a shell (e.g. Streamlit Community
    Cloud, whose file system starts empty after every restart).

    Reads PRAGYAAN_ANALYST_ID / PRAGYAAN_ANALYST_PASSWORD / PRAGYAAN_ANALYST_NAME and the same three for
    PRAGYAAN_EMPLOYEE_*. An ID that already exists is left untouched. As everywhere else, only the salted hash of the
    password is stored in the database."""
    created = []
    for role, prefix in (("analyst", "PRAGYAAN_ANALYST"), ("employee", "PRAGYAAN_EMPLOYEE")):
        login_id = os.getenv(f"{prefix}_ID", "").strip()
        password = os.getenv(f"{prefix}_PASSWORD", "")
        if not login_id or not password:
            continue
        if fetchone("SELECT id FROM accounts WHERE login_id = ?", (normalize_id(login_id),)):
            continue
        name = os.getenv(f"{prefix}_NAME", "").strip() or ROLE_LABELS[role]
        try:
            create_account(login_id, name, role, password)
            created.append(normalize_id(login_id))
        except AuthError:
            pass  # an invalid ID or weak password in the secrets: leave it to first-run setup
    return created


def create_account(login_id: str, name: str, role: str, password: str, *, department: str | None = None,
                   title: str | None = None, must_change_password: bool = False,
                   created_by: dict | None = None) -> dict:
    """Create an account. Only Senior Analysts may create accounts, except the first-run setup
    (created_by=None while no Senior Analyst exists) and the command-line script."""
    if created_by is not None:
        require_role(created_by, "analyst")
    login_id = normalize_id(login_id)
    if role not in ROLES:
        raise AuthError("Choose Employee or Senior Analyst.")
    if not _ID_RE.match(login_id):
        raise AuthError("IDs use 3-64 letters, numbers, dots, dashes or underscores (e.g. EMP-1042).")
    if not (name or "").strip():
        raise AuthError("Enter the person's full name.")
    problem = password_problem(password)
    if problem:
        raise AuthError(problem)
    if fetchone("SELECT id FROM accounts WHERE login_id = ?", (login_id,)):
        raise AuthError(f"The ID {login_id} is already in use.")
    aid = execute(
        "INSERT INTO accounts (login_id, name, role, department, title, password_hash, must_change_password, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (login_id, name.strip(), role, (department or "").strip() or None, (title or "").strip() or None,
         hash_password(password), int(must_change_password), (created_by or {}).get("login_id") or "setup"),
    )
    from .activity import log_activity

    log_activity("account", f"{ROLE_LABELS[role]} account {login_id} created for {name.strip()}",
                 ref_type="account", ref_id=aid, actor=(created_by or {}).get("login_id"))
    return get_account(aid)


def authenticate(login_id: str, password: str, portal_role: str) -> dict:
    """Verify credentials for one portal. Raises AuthError with a user-safe message."""
    global _DUMMY_HASH
    login_id = normalize_id(login_id)
    if not login_id or not password:
        raise AuthError(f"Enter your {ID_LABELS.get(portal_role, 'ID')} and password.")
    row = fetchone("SELECT * FROM accounts WHERE login_id = ?", (login_id,))
    generic = f"{ID_LABELS.get(portal_role, 'ID')} or password is incorrect."
    if not row:
        _DUMMY_HASH = _DUMMY_HASH or hash_password("timing-equaliser-0")
        verify_password(password, _DUMMY_HASH)
        raise AuthError(generic)
    locked = fetchone("SELECT CAST((julianday(?) - julianday('now')) * 1440 AS INTEGER) + 1 AS mins "
                      "WHERE ? IS NOT NULL AND ? > datetime('now')",
                      (row["locked_until"], row["locked_until"], row["locked_until"]))
    if locked:
        raise AuthError(f"Too many failed attempts. Try again in {max(1, int(locked['mins']))} minute(s).")
    if not verify_password(password, row["password_hash"]):
        attempts = int(row["failed_attempts"] or 0) + 1
        if attempts >= MAX_FAILED_ATTEMPTS:
            execute("UPDATE accounts SET failed_attempts = 0, locked_until = datetime('now', ?) WHERE id = ?",
                    (f"+{LOCK_MINUTES} minutes", row["id"]))
            raise AuthError(f"Too many failed attempts. Try again in {LOCK_MINUTES} minutes.")
        execute("UPDATE accounts SET failed_attempts = ? WHERE id = ?", (attempts, row["id"]))
        raise AuthError(generic)
    # Correct password: the role and status checks come after, with the same generic message
    # for the wrong portal, so a valid Employee ID gives nothing away on the analyst portal.
    if row["role"] != portal_role:
        raise AuthError(generic)
    if not row["is_active"]:
        raise AuthError("This account is deactivated. Contact a Senior Analyst.")
    execute("UPDATE accounts SET failed_attempts = 0, locked_until = NULL, last_login_at = datetime('now') "
            "WHERE id = ?", (row["id"],))
    return get_account(row["id"])


def change_password(account_id: int, current_password: str | None, new_password: str,
                    keep_token_hash: str | None = None) -> None:
    """Change your own password. `current_password` is skipped only for a forced change right
    after signing in with a temporary password."""
    row = fetchone("SELECT * FROM accounts WHERE id = ?", (account_id,))
    if not row:
        raise AuthError("Account not found.")
    if not row["must_change_password"] and not verify_password(current_password or "", row["password_hash"]):
        raise AuthError("Your current password is incorrect.")
    problem = password_problem(new_password)
    if problem:
        raise AuthError(problem)
    if verify_password(new_password, row["password_hash"]):
        raise AuthError("Choose a password different from the current one.")
    execute("UPDATE accounts SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (hash_password(new_password), account_id))
    # sign out other devices
    execute("UPDATE sessions SET revoked = 1 WHERE account_id = ? AND token_hash != COALESCE(?, '')",
            (account_id, keep_token_hash))


def reset_password(account_id: int, actor: dict) -> str:
    """Senior Analyst sets a temporary password (returned once) that must be changed at next sign-in."""
    require_role(actor, "analyst")
    if not get_account(account_id):
        raise AuthError("Account not found.")
    temp = generate_temporary_password()
    execute("UPDATE accounts SET password_hash = ?, must_change_password = 1, failed_attempts = 0, "
            "locked_until = NULL WHERE id = ?", (hash_password(temp), account_id))
    execute("UPDATE sessions SET revoked = 1 WHERE account_id = ?", (account_id,))
    execute("UPDATE password_reset_requests SET status = 'done', handled_by = ?, handled_at = datetime('now') "
            "WHERE account_id = ? AND status = 'open'", (actor["login_id"], account_id))
    from .activity import log_activity

    log_activity("account", f"Temporary password issued for {get_account(account_id)['login_id']}",
                 ref_type="account", ref_id=account_id, actor=actor["login_id"])
    return temp


def update_account(account_id: int, actor: dict, *, name: str | None = None, login_id: str | None = None,
                   role: str | None = None, department: str | None = None, title: str | None = None,
                   is_active: bool | None = None) -> dict:
    """Edit an account (Senior Analysts only). Keeps at least one active Senior Analyst."""
    me = require_role(actor, "analyst")
    acct = get_account(account_id)
    if not acct:
        raise AuthError("Account not found.")
    sets: dict = {}
    if name is not None:
        if not name.strip():
            raise AuthError("Name can't be empty.")
        sets["name"] = name.strip()
    if login_id is not None and normalize_id(login_id) != acct["login_id"]:
        new_id = normalize_id(login_id)
        if not _ID_RE.match(new_id):
            raise AuthError("IDs use 3-64 letters, numbers, dots, dashes or underscores (e.g. EMP-1042).")
        if fetchone("SELECT id FROM accounts WHERE login_id = ? AND id != ?", (new_id, account_id)):
            raise AuthError(f"The ID {new_id} is already in use.")
        sets["login_id"] = new_id
    if department is not None:
        sets["department"] = department.strip() or None
    if title is not None:
        sets["title"] = title.strip() or None
    losing_analyst = (role is not None and role != acct["role"] and acct["role"] == "analyst") or \
                     (is_active is False and acct["is_active"] and acct["role"] == "analyst")
    if losing_analyst and analyst_count() <= 1:
        raise AuthError("PRAGYAAN needs at least one active Senior Analyst.")
    if account_id == me["id"] and (is_active is False or (role is not None and role != acct["role"])):
        raise AuthError("You can't deactivate your own account or change your own role.")
    if role is not None and role != acct["role"]:
        if role not in ROLES:
            raise AuthError("Unknown role.")
        sets["role"] = role
    if is_active is not None and bool(is_active) != acct["is_active"]:
        sets["is_active"] = int(bool(is_active))
    if sets:
        cols = ", ".join(f"{k} = ?" for k in sets)
        execute(f"UPDATE accounts SET {cols} WHERE id = ?", (*sets.values(), account_id))
        if "role" in sets or sets.get("is_active") == 0 or "login_id" in sets:
            execute("UPDATE sessions SET revoked = 1 WHERE account_id = ?", (account_id,))
        if "login_id" in sets:  # keep this person's tickets, chats and notifications attached
            old, new = acct["login_id"], sets["login_id"]
            for sql in ("UPDATE tickets SET created_by = ? WHERE created_by = ?",
                        "UPDATE chat_messages SET user_email = ? WHERE user_email = ?",
                        "UPDATE notification_reads SET user_email = ? WHERE user_email = ?",
                        "UPDATE notifications SET target_login = ? WHERE target_login = ?"):
                execute(sql, (new, old))
        from .activity import log_activity

        log_activity("account", f"Account {acct['login_id']} updated ({', '.join(sets)})",
                     ref_type="account", ref_id=account_id, actor=me["login_id"])
    return get_account(account_id)


# ---------------------------------------------------------------- sessions

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(account_id: int, remember: bool = False) -> str:
    """Start a server-side session. Returns the raw token (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    span = f"+{REMEMBER_DAYS} days" if remember else f"+{SESSION_HOURS} hours"
    execute("INSERT INTO sessions (token_hash, account_id, remember, expires_at, last_seen_at) "
            "VALUES (?, ?, ?, datetime('now', ?), datetime('now'))",
            (_token_hash(token), account_id, int(remember), span))
    return token


def session_account(token: str | None) -> dict | None:
    """The active account for a session token, or None if missing/expired/revoked/deactivated."""
    if not token:
        return None
    row = fetchone(
        "SELECT a.id FROM sessions s JOIN accounts a ON a.id = s.account_id "
        "WHERE s.token_hash = ? AND s.revoked = 0 AND s.expires_at > datetime('now') AND a.is_active = 1",
        (_token_hash(token),),
    )
    if not row:
        return None
    execute("UPDATE sessions SET last_seen_at = datetime('now') WHERE token_hash = ?", (_token_hash(token),))
    return get_account(row["id"])


def token_hash(token: str | None) -> str | None:
    return _token_hash(token) if token else None


def revoke_session(token: str | None) -> None:
    if token:
        execute("UPDATE sessions SET revoked = 1 WHERE token_hash = ?", (_token_hash(token),))


# ---------------------------------------------------------------- forgot password

def request_password_reset(login_id: str, portal_role: str) -> None:
    """Record a reset request for Senior Analysts to handle. Always behaves the same way,
    whether or not the ID exists, so the form can't be used to discover IDs."""
    row = fetchone("SELECT id, role, is_active FROM accounts WHERE login_id = ?", (normalize_id(login_id),))
    if not row or row["role"] != portal_role or not row["is_active"]:
        return
    if fetchone("SELECT id FROM password_reset_requests WHERE account_id = ? AND status = 'open'", (row["id"],)):
        return
    execute("INSERT INTO password_reset_requests (account_id) VALUES (?)", (row["id"],))
    from .activity import notify

    notify(f"Password reset requested by {normalize_id(login_id)}", level="info", page="team", audience="analyst")


def list_reset_requests(actor: dict, status: str = "open") -> list[dict]:
    require_role(actor, "analyst")
    return fetchall(
        "SELECT r.*, a.login_id, a.name, a.role FROM password_reset_requests r JOIN accounts a ON a.id = r.account_id "
        "WHERE r.status = ? ORDER BY r.id DESC", (status,))


def dismiss_reset_request(request_id: int, actor: dict) -> None:
    require_role(actor, "analyst")
    execute("UPDATE password_reset_requests SET status = 'dismissed', handled_by = ?, handled_at = datetime('now') "
            "WHERE id = ?", (actor["login_id"], request_id))


# ---------------------------------------------------------------- compatibility

def user_count() -> int:
    row = fetchone("SELECT COUNT(*) AS n FROM accounts")
    return int(row["n"]) if row else 0
