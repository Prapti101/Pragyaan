"""PRAGYAAN entry point: page config, session check, role-based navigation.

Run from the project root:  streamlit run app/Home.py

Access control happens here on the server for every run: the session token is checked
against the database (expiry, revocation, account status and role), and only the pages the
account's role may use are registered with st.navigation. A page that isn't registered
can't be opened by typing its URL; each role-specific page also re-checks the role itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def _refresh_backend_modules() -> None:
    """Load the current code if project files changed while the server was running.

    Streamlit re-runs page scripts on change, but modules they import (the backend in
    src/copilot and the shared app/ui.py, app/auth_ui.py) can stay in memory in their old
    version and mix with new code, e.g. after an update. When any of those files changed since
    the last run, drop the old modules so this run imports the current ones.
    """
    files = sorted((ROOT / "src" / "copilot").glob("*.py")) + [APP / "ui.py", APP / "auth_ui.py"]
    current = {str(p): p.stat().st_mtime for p in files if p.exists()}
    if getattr(sys, "_pragyaan_module_mtimes", None) != current:
        for name in [n for n in sys.modules if n in ("copilot", "ui", "auth_ui") or n.startswith("copilot.")]:
            del sys.modules[name]
        sys._pragyaan_module_mtimes = current


_refresh_backend_modules()

import auth_ui  # noqa: E402
import ui  # noqa: E402
from copilot.activity import list_notifications, log_activity, mark_all_read, unread_count  # noqa: E402
from copilot.auth import needs_setup, revoke_session, session_account  # noqa: E402
from copilot.automation import seed_default_rules  # noqa: E402
from copilot.db import ensure_db  # noqa: E402

st.set_page_config(
    page_title="PRAGYAAN",
    page_icon=str(APP / "static" / "pragyaan-mark.svg"),
    layout="wide",
    initial_sidebar_state="expanded",
)
ensure_db()
seed_default_rules()


# ---------------------------------------------------------------- session

def _signed_in_account() -> dict | None:
    """The account for this browser session, validated against the database on every run."""
    token = st.session_state.get("auth_token")
    if token is None and not st.session_state.get("_cookie_checked"):
        st.session_state["_cookie_checked"] = True  # read the browser cookie once per connection
        token = st.context.cookies.get(auth_ui.COOKIE) or None
    acct = session_account(token) if token else None
    if token and not acct:  # expired, revoked, or the account was deactivated
        st.session_state.pop("auth_token", None)
        st.session_state["_clear_cookie"] = True
        if st.session_state.get("user"):
            st.session_state["_auth_flash"] = ("info", "Your session ended. Please sign in again.")
            st.session_state["_to_portal"] = True
    elif acct:
        st.session_state["auth_token"] = token
    st.session_state["user"] = acct
    return acct


def _sign_out() -> None:
    user = st.session_state.get("user") or {}
    revoke_session(st.session_state.get("auth_token"))
    if user:
        log_activity("login", f"{user.get('name')} signed out", actor=user.get("login_id"))
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state["_cookie_checked"] = True  # don't restore the (now revoked) cookie
    st.session_state["_clear_cookie"] = True
    st.session_state["_auth_flash"] = ("success", "You've been signed out.")
    st.session_state["_to_portal"] = True


user = _signed_in_account()


def page(path: str, title: str, icon: str, url: str, **kw) -> st.Page:
    return st.Page(f"views/{path}", title=title, icon=f":material/{icon}:", url_path=url, **kw)


# ---------------------------------------------------------------- signed out
if not user:
    ui.inject_css()
    # no sidebar while signed out (it can linger after signing out in the same tab)
    st.markdown('<style>section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], '
                '[data-testid="stExpandSidebarButton"] { display: none !important; }</style>', unsafe_allow_html=True)
    P = {
        "welcome": page("landing.py", "PRAGYAAN", "public", "welcome", default=True),
        "login": page("login.py", "Choose your portal", "login", "login"),
        "employee_login": page("login_employee.py", "Employee sign-in", "work", "employee-login"),
        "analyst_login": page("login_analyst.py", "Senior Analyst sign-in", "shield_person", "analyst-login"),
        "forgot": page("forgot_password.py", "Reset password", "key", "forgot-password"),
    }
    if needs_setup():
        P["setup"] = page("setup.py", "Set up PRAGYAAN", "admin_panel_settings", "setup")
    st.session_state["_pages"] = P
    if st.session_state.pop("_clear_cookie", False):
        auth_ui.clear_session_cookie()
    nav = st.navigation(list(P.values()), position="hidden")
    if st.session_state.pop("_to_portal", False):
        st.switch_page(P["login"])
    nav.run()
    st.stop()

# ---------------------------------------------------------------- signed in
ui.inject_css()
if st.session_state.pop("_clear_cookie", False):
    auth_ui.clear_session_cookie()
cookie = st.session_state.pop("_set_cookie", None)
if cookie:
    auth_ui.set_session_cookie(*cookie)
if st.session_state.get("_toast"):
    st.toast(st.session_state.pop("_toast"), icon=":material/check_circle:")

role = user["role"]
account_page = page("account.py", "My account", "manage_accounts", "account",
                    default=user["must_change_password"])

if user["must_change_password"]:
    # A temporary password only opens the change-password screen.
    P = {"account": account_page}
    sections = {"Account": [account_page]}
elif role == "employee":
    P = {
        "home": page("emp_home.py", "Home", "home", "home", default=True),
        "submit": page("emp_submit.py", "Submit a ticket", "add_circle", "submit"),
        "my_tickets": page("emp_tickets.py", "My tickets", "confirmation_number", "my-tickets"),
        "assistant": page("5_AI_Assistant.py", "AI Assistant", "forum", "assistant"),
        "knowledge": page("6_Knowledge_Hub.py", "Knowledge Hub", "library_books", "knowledge"),
        "search": page("8_Search.py", "Search", "search", "search", visibility="hidden"),
        "account": account_page,
    }
    sections = {
        "Workspace": [P["home"], P["submit"], P["my_tickets"]],
        "Knowledge": [P["assistant"], P["knowledge"]],
        "Account": [P["account"], P["search"]],
    }
else:  # analyst
    P = {
        "dashboard": page("0_Dashboard.py", "Operations overview", "space_dashboard", "dashboard", default=True),
        "review": page("review_queue.py", "Escalations", "assignment_late", "review"),
        "triage": page("4_Smart_Triage.py", "All tickets", "confirmation_number", "triage"),
        "queue": page("1_Senior_Queue.py", "Senior Queue", "support_agent", "queue"),
        "assistant": page("5_AI_Assistant.py", "AI Assistant", "forum", "assistant"),
        "knowledge": page("6_Knowledge_Hub.py", "Knowledge Hub", "library_books", "knowledge"),
        "automation": page("7_Automation.py", "Automation", "account_tree", "automation"),
        "team": page("team.py", "Team management", "groups", "team"),
        "analytics": page("2_Analytics.py", "Analytics & reports", "insights", "analytics"),
        "benchmarks": page("3_Model_Comparison.py", "Model Benchmarks", "leaderboard", "benchmarks"),
        "search": page("8_Search.py", "Search", "search", "search", visibility="hidden"),
        "account": account_page,
    }
    sections = {
        "Operations": [P["dashboard"], P["review"], P["triage"], P["queue"]],
        "Knowledge & automation": [P["assistant"], P["knowledge"], P["automation"]],
        "Team & insights": [P["team"], P["analytics"], P["benchmarks"]],
        "Account": [P["account"], P["search"]],
    }
st.session_state["_pages"] = P

st.logo(str(APP / "static" / "pragyaan-logo.svg"), size="large",
        icon_image=str(APP / "static" / "pragyaan-mark.svg"))
nav = st.navigation(sections, position="sidebar")
if st.session_state.pop("_go_home", False) and not user["must_change_password"]:
    st.switch_page(P["home" if role == "employee" else "dashboard"])


def _submit_search() -> None:
    q = (st.session_state.get("global_q") or "").strip()
    if q:
        st.session_state["search_q"] = q
        st.session_state["_go_search"] = True
    st.session_state["global_q"] = ""


# Top bar: global search, notifications, profile
with st.container(key="topbar"):
    c_search, c_space, c_bell, c_me = st.columns([6, 1.6, 1.1, 2], vertical_alignment="center")
    with c_search:
        if "search" in P:
            hint = ("Search your tickets, documents and past solutions…" if role == "employee"
                    else "Search tickets, documents, tasks and the archive…")
            st.text_input("Search", key="global_q", placeholder=hint, label_visibility="collapsed",
                          on_change=_submit_search, icon=":material/search:")
    with c_bell:
        n_unread = unread_count(user["login_id"], role)
        with st.popover(f"{n_unread}" if n_unread else "", icon=":material/notifications:",
                        help="Notifications", width="stretch"):
            notes = list_notifications(user["login_id"], limit=8, role=role)
            if not notes:
                st.caption("No notifications yet. Updates on your tickets show up here." if role == "employee" else
                           "No notifications yet. Suggested solutions, escalations and reset requests show up here.")
            for n in notes:
                dot = "\U0001F534 " if n["level"] == "high" else ""
                weight = "**" if not n["is_read"] else ""
                st.markdown(f"{dot}{weight}{n['message']}{weight}  \n:gray[{ui.ago(n['created_at'])}]")
                target = n.get("page") or ""
                if target in P and st.button("Open", key=f"note-open-{n['id']}", type="tertiary"):
                    mark_all_read(user["login_id"], role)
                    if n.get("ref_id") and target in ("triage", "my_tickets", "review"):
                        st.session_state["focus_ticket"] = n["ref_id"]
                    st.switch_page(P[target])
            if n_unread and st.button("Mark all as read", key="note-read-all", width="stretch"):
                mark_all_read(user["login_id"], role)
                st.rerun()
    with c_me:
        initials = "".join(w[0] for w in user["name"].split()[:2]).upper() or "U"
        with st.popover(f"{initials} · {user['role_label']}", icon=":material/account_circle:", width="stretch"):
            st.markdown(f"**{ui.esc(user['name'])}**  \n{ui.esc(user.get('title') or user['role_label'])}",
                        unsafe_allow_html=True)
            st.markdown(f"{ui.role_badge(role)} &nbsp;<span class='pg-muted'>ID <b>{ui.esc(user['login_id'])}</b>"
                        "</span>", unsafe_allow_html=True)
            if not user["must_change_password"] and st.button("My account", icon=":material/manage_accounts:",
                                                              width="stretch", key="go-account"):
                st.switch_page(P["account"])
            if st.button("Sign out", icon=":material/logout:", width="stretch", key="signout"):
                _sign_out()
                st.rerun()

if st.session_state.pop("_go_search", False) and "search" in P:
    st.switch_page(P["search"])

# Sidebar footer: who is signed in, and which models/integrations are live (real status)
with st.sidebar:
    from copilot.llm import provider_name
    from copilot.triage import archive_available, model_status

    ms = model_status()
    llm = provider_name()
    if "_kb_count" not in st.session_state:
        st.session_state["_kb_count"] = archive_available()
    kb_n = st.session_state["_kb_count"]
    accent = "#A78BFA" if role == "analyst" else "#22D3EE"
    st.markdown(
        f"""<div style="margin-top:1.2rem;padding:.75rem .85rem;border:1px solid #26315C;border-radius:12px;
        background:rgba(255,255,255,.03);font-size:.8rem;line-height:1.5;color:#AEB5D6">
        <div style="color:{accent};font-weight:600;font-size:.7rem;letter-spacing:.12em;text-transform:uppercase">
        {ui.esc(user['role_label'])} workspace</div>
        <div style="color:#fff;font-weight:600;margin-top:.15rem">{ui.esc(user['name'])}</div>
        <div>{ui.esc(user['login_id'])}</div></div>
        <div style="margin-top:.6rem;padding:.8rem .85rem;border:1px solid #26315C;border-radius:12px;
        background:rgba(255,255,255,.03);font-size:.8rem;line-height:1.55;color:#AEB5D6">
        <div style="color:#fff;font-weight:600;margin-bottom:.25rem">System status</div>
        <div>{'&#9679;' if ms['ok'] else '&#9675;'} Priority model: {ui.esc('ready' if ms['ok'] else 'missing')}</div>
        <div>{'&#9679;' if kb_n else '&#9675;'} Solution archive: {f"{kb_n:,} tickets" if kb_n else 'not indexed'}</div>
        <div>{'&#9679;' if llm else '&#9675;'} Language model: {ui.esc(llm or 'not connected')}</div>
        </div>""",
        unsafe_allow_html=True,
    )

nav.run()
