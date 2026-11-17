"""Sign-in landing: choose the Employee portal or the Senior Analyst portal."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import auth_ui  # noqa: E402
import ui  # noqa: E402
from copilot.auth import needs_setup  # noqa: E402

P = st.session_state["_pages"]
auth_ui.theme()
auth_ui.brand_bar("Back to home", "welcome", key="brand-home")

CARDS = [
    ("employee", "Employee", "Employee portal",
     "Raise tickets, try recommended fixes, follow every step and ask the assistant.",
     [("confirmation_number", "Tickets"), ("lightbulb", "Recommended fixes"), ("forum", "Assistant"),
      ("library_books", "Knowledge Hub")],
     "Continue as Employee"),
    ("analyst", "Senior Analyst", "Senior Analyst portal",
     "Work escalations by predicted priority, assign the team and watch the numbers.",
     [("assignment_late", "Escalations"), ("assignment_ind", "Assignment"), ("monitoring", "Analytics"),
      ("leaderboard", "Model benchmarks")],
     "Continue as Senior Analyst"),
]
ICONS = {"employee": "work", "analyst": "shield_person"}

left, right = st.columns([1, 1.05], vertical_alignment="center")
with left:
    st.markdown(
        f'<div class="pg-pick"><h1>{ui.words("Who’s signing in?")}</h1>'
        '<p>Employees and Senior Analysts get separate workspaces. Pick yours and sign in with the ID '
        'your organisation gave you.</p>'
        f'<ul><li>{auth_ui.icon("verified_user")}Your role is checked on the server, on every page</li>'
        f'<li>{auth_ui.icon("lock")}Passwords are stored only as salted hashes</li>'
        f'<li>{auth_ui.icon("timer")}Sessions end on their own after 12 hours</li></ul></div>',
        unsafe_allow_html=True,
    )
    flash = st.session_state.pop("_auth_flash", None)
    if flash:
        auth_ui.message(*flash)
    if needs_setup():
        auth_ui.message("info", "No Senior Analyst account exists yet. Create the first one to start using PRAGYAAN.")
        if "setup" in P and st.button("Set up the first Senior Analyst", icon=":material/admin_panel_settings:",
                                      key="go-setup"):
            st.switch_page(P["setup"])

with right:
    for role, title, kicker, desc, feats, cta in CARDS:
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
