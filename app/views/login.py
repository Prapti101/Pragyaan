"""Sign-in landing: choose the Employee portal or the Senior Analyst portal."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import auth_ui  # noqa: E402
from copilot.auth import needs_setup  # noqa: E402

P = st.session_state["_pages"]
auth_ui.theme()
auth_ui.brand_bar("Back to home", "welcome", key="brand-home")

st.markdown(
    '<div style="text-align:center;margin:2.6rem auto 2.4rem;max-width:780px">'
    '<span class="pg-eyebrow"><i></i>Secure sign-in</span>'
    '<div class="pg-hero-t">Choose your <span class="pg-grad">portal</span></div>'
    '<p class="pg-hero-s">PRAGYAAN gives employees and Senior Analysts separate, role-verified workspaces. '
    'Sign in with the ID issued by your organisation.</p></div>',
    unsafe_allow_html=True,
)

flash = st.session_state.pop("_auth_flash", None)
if flash:
    _, mid, _ = st.columns([1, 2.2, 1])
    with mid:
        auth_ui.message(*flash)

if needs_setup():
    _, mid, _ = st.columns([1, 2.2, 1])
    with mid:
        auth_ui.message("info", "No Senior Analyst account exists yet. Create the first one to start using PRAGYAAN.")
        if "setup" in P and st.button("Set up the first Senior Analyst", icon=":material/admin_panel_settings:",
                                      key="go-setup", width="stretch"):
            st.switch_page(P["setup"])
    st.write("")

CARDS = [
    ("employee", "Employee", "Employee portal",
     "Access enterprise knowledge, submit support tickets, find solutions and interact with the AI assistant.",
     [("confirmation_number", "Submit and track support tickets"), ("lightbulb", "Existing solution recommendations"),
      ("auto_awesome", "AI assistant and Knowledge Hub")],
     "Continue as Employee"),
    ("analyst", "Senior Analyst", "Senior Analyst portal",
     "Manage support operations, review escalations, monitor ticket priorities, analyze performance and oversee "
     "the support team.",
     [("fact_check", "Review and approve suggested solutions"), ("assignment_ind", "Escalations and ticket assignment"),
      ("monitoring", "Analytics, reports and team management")],
     "Continue as Senior Analyst"),
]
ICONS = {"employee": "work", "analyst": "shield_person"}

_, a, b, _ = st.columns([0.15, 1, 1, 0.15], gap="large")
for col, (role, title, kicker, desc, feats, cta) in zip((a, b), CARDS):
    with col:
        with st.container(key=f"portal-{role}"):
            items = "".join(f"<li>{auth_ui.icon(i)}{auth_ui.esc(t)}</li>" for i, t in feats)
            st.markdown(
                f'<div class="pc-top"><div class="pc-icon">{auth_ui.icon(ICONS[role])}</div>'
                f'<span class="pc-kicker">{auth_ui.esc(kicker)}</span></div>'
                f'<div class="pc-title">{auth_ui.esc(title)}</div><p class="pc-desc">{auth_ui.esc(desc)}</p>'
                f'<ul class="pc-feats">{items}</ul>',
                unsafe_allow_html=True,
            )
            if st.button(cta, type="primary", width="stretch", key=f"choose-{role}",
                         icon=":material/arrow_forward:", icon_position="right"):
                st.switch_page(P[f"{role}_login"])

auth_ui.footer()
