"""My account: profile and password change (forced after a temporary password)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.auth import AuthError, change_password, token_hash  # noqa: E402

user = ui.require_role("employee", "analyst")
forced = user["must_change_password"]

ui.page_header("Choose a new password" if forced else "My account",
               "You signed in with a temporary password. Choose your own password to continue." if forced
               else "Your profile and sign-in settings.")

left, right = st.columns([1.15, 1])
with left:
    with st.container(key="card-password"):
        st.markdown("##### Change password")
        with st.form("chpw", border=False):
            current = None if forced else st.text_input("Current password", type="password",
                                                        autocomplete="current-password")
            new = st.text_input("New password", type="password", autocomplete="new-password",
                                help="At least 8 characters, with letters and numbers.")
            new2 = st.text_input("Confirm new password", type="password", autocomplete="new-password")
            ok = st.form_submit_button("Update password", type="primary", icon=":material/lock_reset:")
        if ok:
            if new != new2:
                st.error("The two new passwords don't match.", icon=":material/error:")
            else:
                try:
                    with st.spinner("Updating…"):
                        change_password(user["id"], current, new,
                                        keep_token_hash=token_hash(st.session_state.get("auth_token")))
                except AuthError as e:
                    st.error(str(e), icon=":material/error:")
                else:
                    st.session_state["_toast"] = "Password updated. Other devices were signed out."
                    if forced:  # continue to the workspace now that the account is fully set up
                        st.session_state["_go_home"] = True
                    st.rerun()
with right:
    with st.container(key="card-profile"):
        st.markdown("##### Profile")
        st.markdown(
            f"**{ui.esc(user['name'])}**  \n{ui.esc(user.get('title') or user['role_label'])}"
            f"{' · ' + ui.esc(user['department']) if user.get('department') else ''}", unsafe_allow_html=True)
        st.markdown(f"{ui.soft_badge(user['role_label'])} &nbsp;<span class='pg-muted'>ID "
                    f"<b>{ui.esc(user['login_id'])}</b></span>", unsafe_allow_html=True)
        st.caption(f"Last sign-in: {ui.local_time(user.get('last_login_at')) or 'now'}. "
                   "Your name, ID and role are managed by a Senior Analyst.")
