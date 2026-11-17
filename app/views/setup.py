"""First-run setup: create the first Senior Analyst account.

Available only while no active Senior Analyst exists, and only from the computer running
PRAGYAAN (or use scripts/create_account.py on the server). After that, accounts are created
by Senior Analysts in Team management.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import auth_ui  # noqa: E402
from copilot.auth import AuthError, create_account, needs_setup  # noqa: E402

P = st.session_state["_pages"]
auth_ui.theme(ambient=True, role="analyst")
auth_ui.brand_bar("Back to role selection", "login", key="setup-back")

_, mid, _ = st.columns([1, 1.7, 1])
with mid:
    with st.container(key="auth-card"):
        st.markdown('<div class="pg-form-head" style="--card-accent:#8B5CF6"><div class="ic">'
                    f'{auth_ui.icon("admin_panel_settings")}</div><h1>Set up PRAGYAAN</h1>'
                    '<p>Create the first Senior Analyst account. You will then add employees and other analysts '
                    'from Team management.</p></div>', unsafe_allow_html=True)
        if not needs_setup():
            auth_ui.message("info", "Setup is complete: a Senior Analyst account already exists. Sign in from the "
                            "Senior Analyst portal.")
            if st.button("Go to Senior Analyst sign-in", type="primary", width="stretch", key="setup-done"):
                st.switch_page(P["analyst_login"])
            st.stop()
        if st.context.ip_address is not None:
            auth_ui.message("error", "For security, first-run setup only works on the computer running PRAGYAAN. "
                            "Open it there, or run <code>python scripts/create_account.py create --role analyst "
                            "--id SA-001 --name \"Your Name\"</code> on the server.", raw_html=True)
            st.stop()
        with st.form("setup", border=False):
            name = st.text_input("Full name", icon=":material/person:", autocomplete="name")
            c1, c2 = st.columns(2)
            login_id = c1.text_input("Senior Analyst ID", placeholder="e.g. SA-001", icon=":material/badge:",
                                     help="3-64 letters, numbers, dots, dashes or underscores. Not an e-mail address.")
            dept = c2.text_input("Department (optional)", placeholder="e.g. IT Support")
            c3, c4 = st.columns(2)
            pw = c3.text_input("Password", type="password", autocomplete="new-password",
                               help="At least 8 characters with letters and numbers.")
            pw2 = c4.text_input("Confirm password", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Create Senior Analyst account", type="primary", width="stretch",
                                       icon=":material/check:")
        if ok:
            if pw != pw2:
                auth_ui.message("error", "The two passwords don't match.")
            else:
                try:
                    with st.spinner("Creating your account…"):
                        acct = create_account(login_id, name, "analyst", pw, department=dept, title="Senior Analyst")
                except AuthError as e:
                    auth_ui.message("error", str(e))
                else:
                    st.session_state["_auth_flash"] = ("success", f"Account {acct['login_id']} created. Sign in to "
                                                                  "open the operations command center.")
                    st.switch_page(P["analyst_login"])
auth_ui.footer()
