"""Forgot password: sends a reset request to the Senior Analysts (no e-mail server needed).

A Senior Analyst issues a one-time temporary password from Team management; the person must
choose a new password the first time they sign in with it. The response is identical whether
or not the ID exists, so this form can't be used to discover IDs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import auth_ui  # noqa: E402
from copilot.auth import ID_LABELS, request_password_reset  # noqa: E402

P = st.session_state["_pages"]
role = st.session_state.get("forgot_role", "employee")
portal = auth_ui.PORTALS[role]
back = f"{role}_login"

auth_ui.theme(ambient=True, role=role)
auth_ui.brand_bar(f"Back to {portal['label']} sign-in", back, key="fp-top-back")

_, mid, _ = st.columns([1, 1.5, 1])
with mid:
    with st.container(key="auth-card"):
        st.markdown(f'<div class="pg-form-head" style="--card-accent:{portal["accent"]}">'
                    f'<div class="ic">{auth_ui.icon("key")}</div><h1>Reset your password</h1>'
                    f'<p>Enter your {ID_LABELS[role]}. A Senior Analyst will verify the request and give you a '
                    f'temporary password.</p></div>', unsafe_allow_html=True)
        if st.session_state.get("_fp_done"):
            auth_ui.message("success", st.session_state["_fp_done"])
        with st.form("forgot", border=False):
            login_id = st.text_input(ID_LABELS[role], placeholder=portal["id_hint"], icon=":material/badge:",
                                     autocomplete="username", max_chars=64)
            sent = st.form_submit_button("Request a reset", type="primary", width="stretch",
                                         icon=":material/send:")
        if sent:
            if not login_id.strip():
                auth_ui.message("error", f"Enter your {ID_LABELS[role]}.")
            else:
                with st.spinner("Sending your request…"):
                    request_password_reset(login_id, role)
                st.session_state["_fp_done"] = (
                    f"If {login_id.strip()} is an active {portal['label']} account, the Senior Analyst team has been "
                    "notified. They'll give you a temporary password, and you'll choose a new one when you sign in.")
                st.rerun()
        if role == "analyst":
            auth_ui.message("info", "Locked out and no other Senior Analyst can help? On the server, run "
                            "<code>python scripts/create_account.py reset --id YOUR-ID</code>.", raw_html=True)
        if st.button(f"Back to {portal['label']} sign-in", type="tertiary", icon=":material/arrow_back:", key="fp-back"):
            st.session_state.pop("_fp_done", None)
            st.switch_page(P[back])
auth_ui.footer()
