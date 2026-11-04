"""Create or reset PRAGYAAN accounts from the command line (run on the server).

This is the secure way to create the first Senior Analyst without opening the web app,
and to recover access if every Senior Analyst is locked out. The password is typed at a
hidden prompt (never passed on the command line, so it stays out of shell history) and
only its salted PBKDF2 hash is stored.

Examples (from the project folder):
    python scripts/create_account.py create --role analyst --id SA-001 --name "Prapti Priya"
    python scripts/create_account.py create --role employee --id EMP-1042 --name "Ravi Kumar" --department IT
    python scripts/create_account.py reset --id EMP-1042
    python scripts/create_account.py list
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot.auth import (_ID_RE, AuthError, ROLE_LABELS, create_account, get_account_by_login,  # noqa: E402
                          hash_password, list_accounts, normalize_id, password_problem)
from copilot.db import ensure_db, execute  # noqa: E402


def _ask_password() -> str:
    while True:
        pw = getpass.getpass("New password (min 8 characters, letters and numbers): ")
        problem = password_problem(pw)
        if problem:
            print(f"  {problem}")
            continue
        if getpass.getpass("Repeat the password: ") != pw:
            print("  The two passwords don't match.")
            continue
        return pw


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="create an Employee or Senior Analyst account")
    c.add_argument("--role", choices=["employee", "analyst"], required=True)
    c.add_argument("--id", required=True, help="Employee ID / Senior Analyst ID used to sign in")
    c.add_argument("--name", required=True)
    c.add_argument("--department")
    c.add_argument("--title")
    r = sub.add_parser("reset", help="set a new password for an existing account")
    r.add_argument("--id", required=True)
    sub.add_parser("list", help="list accounts (no passwords)")
    args = ap.parse_args()

    ensure_db()
    if args.cmd == "list":
        for a in list_accounts():
            state = "active" if a["is_active"] else "deactivated"
            print(f"{a['login_id']:<24} {ROLE_LABELS[a['role']]:<15} {a['name']:<28} {state}")
        return 0
    if args.cmd == "create":
        if not _ID_RE.match(normalize_id(args.id)):
            print("Error: IDs use 3-64 letters, numbers, dots, dashes or underscores (e.g. EMP-1042).")
            return 1
        if get_account_by_login(args.id):
            print(f"Error: the ID {args.id} is already in use.")
            return 1
        pw = _ask_password()
        try:
            acct = create_account(args.id, args.name, args.role, pw, department=args.department, title=args.title)
        except AuthError as e:
            print(f"Error: {e}")
            return 1
        print(f"Created {ROLE_LABELS[acct['role']]} account {acct['login_id']} for {acct['name']}.")
        return 0
    acct = get_account_by_login(args.id)
    if not acct:
        print(f"Error: no account with ID {args.id}.")
        return 1
    pw = _ask_password()
    execute("UPDATE accounts SET password_hash = ?, must_change_password = 0, failed_attempts = 0, "
            "locked_until = NULL, is_active = 1 WHERE id = ?", (hash_password(pw), acct["id"]))
    execute("UPDATE sessions SET revoked = 1 WHERE account_id = ?", (acct["id"],))
    print(f"Password updated for {acct['login_id']}; existing sessions were signed out.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled; nothing was changed.")
        raise SystemExit(1)
