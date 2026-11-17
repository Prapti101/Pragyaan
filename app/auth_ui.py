"""PRAGYAAN sign-in experience: the ivory-and-ink signed-out pages, the shared login form for both
portals, and the browser-cookie half of session handling.

Only the look lives here; every credential and role check happens in copilot.auth on the server.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
COOKIE = "pragyaan_session"
esc = html.escape

# Each portal owns one colour: acid lime for Employees, electric cobalt for Senior Analysts.
LIME, COBALT, INK, IVORY = "#D4FF3A", "#2340FF", "#0A0C1B", "#F4EEE1"
PORTALS = {
    "employee": {
        "label": "Employee", "id_label": "Employee ID", "id_hint": "e.g. EMP-1042", "icon": "work",
        "eyebrow": "Employee portal", "title": "Sign in",
        "subtitle": "Use the Employee ID your organisation gave you.",
        "accent": LIME, "on": INK, "word": "Employee",
        "pitch": "Raise a ticket and get a fix in seconds",
        "pitch_text": "PRAGYAAN predicts how urgent each ticket is, checks thousands of solved tickets for a "
                      "matching fix and sends the rest to the right people.",
        "points": [("confirmation_number", "Submit tickets and follow every step"),
                   ("lightbulb", "Recommended fixes from solved tickets"),
                   ("forum", "An assistant that answers from company knowledge")],
    },
    "analyst": {
        "label": "Senior Analyst", "id_label": "Senior Analyst ID", "id_hint": "e.g. SA-007", "icon": "shield_person",
        "eyebrow": "Senior Analyst portal", "title": "Sign in",
        "subtitle": "Use the Senior Analyst ID your organisation gave you.",
        "accent": COBALT, "on": IVORY, "word": "Senior Analyst",
        "pitch": "Run support operations from one desk",
        "pitch_text": "Work the tickets the similarity engine couldn't solve, assign them to your team and watch "
                      "priorities, self-service and model quality in one place.",
        "points": [("assignment_late", "Escalations ordered by predicted priority"),
                   ("assignment_ind", "Assignment and team workload"),
                   ("monitoring", "Analytics, model benchmarks and access")],
    },
}


_CSS = """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1280px; padding-top: 1.6rem !important; padding-bottom: 3rem; }
/* brand bar */
.st-key-brandbar { margin-bottom: .2rem; }
.pg-brandbar { display: flex; align-items: center; gap: .9rem; }
.pg-brandbar img { display: block; height: 122px; }
.pg-brandbar .tag { font-size: .95rem; font-weight: 600; color: var(--ink-2); padding-left: .9rem; border-left: 2px solid var(--ink); }
/* messages */
.pg-msg { display: flex; gap: .6rem; align-items: flex-start; padding: .7rem .85rem; border-radius: 10px; border: 2px solid var(--ink);
  box-shadow: 3px 3px 0 var(--ink); font-size: .92rem; line-height: 1.45; background: var(--paper); color: var(--ink); margin: .2rem 0; }
.pg-msg .material-symbols-rounded { font-size: 20px; flex: none; margin-top: .05rem; }
.pg-msg.error { background: #FFE1DC; } .pg-msg.success { background: var(--lime); } .pg-msg.info { background: var(--paper); }
.pg-msg code { background: var(--ivory-2); padding: .05rem .3rem; border-radius: 4px; }
/* the sign-in card */
.st-key-auth-card { background: var(--paper); border: 2px solid var(--ink) !important; border-radius: 20px !important; box-shadow: 9px 9px 0 var(--ink);
  padding: 2.3rem 2.3rem 1.8rem !important; justify-content: center; animation: pg-fade-up .6s var(--ease) both; }
.pg-form-head { margin-bottom: .4rem; }
.pg-form-head .ic { width: 54px; height: 54px; border-radius: 13px; display: grid; place-items: center; background: var(--ac, var(--lime)); color: var(--ac-on, var(--ink));
  border: 2px solid var(--ink); box-shadow: 3px 3px 0 var(--ink); margin-bottom: 1.1rem; }
.pg-form-head .ic .material-symbols-rounded { font-size: 28px; }
.pg-form-head h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 85%; font-size: clamp(2.4rem, 4vw, 3.4rem) !important;
  line-height: .92 !important; letter-spacing: -0.025em; margin: 0 0 .5rem !important; padding: 0 !important; }
.pg-form-head p { color: var(--ink-2); margin: 0 !important; font-size: 1rem; }
.st-key-auth-card [data-testid="stForm"] { border: 0; padding: 0; }
/* the portal slab beside it: one colour per portal, the role set huge */
.st-key-auth-panel { background: var(--ac, var(--lime)); border: 2px solid var(--ink) !important; border-radius: 20px !important; box-shadow: 9px 9px 0 var(--ink);
  padding: 2rem 2.1rem !important; overflow: hidden; position: relative; animation: pg-fade-up .6s .1s var(--ease) both; }
.pg-panel { display: flex; flex-direction: column; min-height: 540px; color: var(--ac-on, var(--ink)); position: relative; }
.pg-panel .top { display: flex; align-items: center; gap: .7rem; }
.pg-panel .top .chip { width: 46px; height: 46px; border-radius: 12px; display: grid; place-items: center; background: var(--ink); color: var(--ac, var(--lime)); }
.pg-panel .top b { font-weight: 700; font-size: .95rem; }
.pg-panel .word { font-family: var(--display); font-weight: 800; font-stretch: 78%; font-size: clamp(3.6rem, 7.4vw, 6.6rem); line-height: .84;
  letter-spacing: -0.03em; margin: 1.6rem 0 1.2rem; }
.pg-panel h2 { font-family: var(--display) !important; font-weight: 750 !important; font-size: 1.45rem !important; line-height: 1.15; margin: 0 0 .5rem !important; padding: 0 !important;
  color: inherit !important; letter-spacing: -0.015em; }
.pg-panel p { margin: 0 0 1.1rem; line-height: 1.55; opacity: .88; max-width: 46ch; color: inherit; }
.pg-panel ul { list-style: none; margin: 0 0 1.4rem; padding: 0; display: grid; gap: .55rem; }
.pg-panel li { display: flex; align-items: center; gap: .7rem; font-weight: 600; font-size: .95rem; margin: 0 !important; color: inherit; }
.pg-panel li .material-symbols-rounded { width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center; font-size: 18px; flex: none;
  background: var(--paper); color: var(--ink); border: 2px solid var(--ink); }
.pg-panel .sec { margin-top: auto; display: flex; flex-wrap: wrap; gap: .4rem; }
.pg-panel .sec span { display: inline-flex; align-items: center; gap: .3rem; font-size: .78rem; font-weight: 700; padding: .25rem .55rem; border-radius: 7px;
  background: var(--ink); color: var(--ivory); }
.pg-panel .sec .material-symbols-rounded { font-size: 15px; color: var(--ac, var(--lime)); }
.pg-panel .pg-sticker { position: absolute; top: .2rem; right: 0; }
/* role selection: two doors that overlap like cards dropped on a desk */
.pg-pick h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 80%; font-size: clamp(3.4rem, 7.8vw, 7.4rem) !important;
  line-height: .86 !important; letter-spacing: -0.032em; margin: .4rem 0 1.2rem !important; padding: 0 !important; max-width: 8ch; }
.pg-pick p { color: var(--ink-2); font-size: 1.1rem; line-height: 1.55; max-width: 44ch; margin: 0 0 1.4rem !important; }
.pg-pick ul { list-style: none; padding: 0; margin: 0; display: grid; gap: .45rem; }
.pg-pick li { display: flex; gap: .55rem; align-items: center; font-weight: 600; font-size: .92rem; margin: 0 !important; }
.pg-pick li .material-symbols-rounded { font-size: 18px; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; background: var(--ink); color: var(--lime); }
html.pg-dark .pg-pick li .material-symbols-rounded { background: #E62E2A; color: #FFF6EC; }
[class*="st-key-portal-"] { border: 2px solid var(--ink) !important; border-radius: 20px !important; box-shadow: 8px 8px 0 var(--ink); padding: 1.6rem 1.7rem 1.5rem !important;
  gap: .2rem !important; transition: transform .35s var(--ease), box-shadow .35s var(--ease); position: relative; }
.st-key-portal-employee { background: var(--lime); transform: rotate(-1deg); animation: pg-door-a .7s .15s var(--ease) both; z-index: 1; }
.st-key-portal-analyst { background: var(--cobalt); transform: rotate(.9deg); margin: -1.4rem 0 0 2.6rem; animation: pg-door-b .7s .3s var(--ease) both; z-index: 2; }
@keyframes pg-door-a { from { opacity: 0; transform: translateY(-30px) rotate(-6deg); } to { opacity: 1; transform: rotate(-1deg); } }
@keyframes pg-door-b { from { opacity: 0; transform: translateY(-30px) rotate(7deg); } to { opacity: 1; transform: rotate(.9deg); } }
[class*="st-key-portal-"]:hover { transform: rotate(0deg) translate(-3px, -3px); box-shadow: 12px 12px 0 var(--ink); z-index: 3; }
.st-key-portal-analyst :is(p, li, b, .pc-title, .pc-feats span) { color: var(--ivory); }
.st-key-portal-analyst .pc-icon .material-symbols-rounded { color: var(--cobalt) !important; }
.st-key-portal-analyst [data-testid="stBaseButton-primary"] :is(p, span) { color: var(--ink) !important; }
.pc-top { display: flex; align-items: center; justify-content: space-between; gap: .8rem; }
.pc-icon { width: 52px; height: 52px; border-radius: 13px; display: grid; place-items: center; background: var(--ink); color: var(--lime); }
.st-key-portal-analyst .pc-icon { background: var(--ivory); color: var(--cobalt); }
.pc-icon .material-symbols-rounded { font-size: 28px; }
.pc-kicker { font-size: .8rem; font-weight: 700; padding: .2rem .6rem; border-radius: 7px; border: 2px solid var(--ink); background: var(--paper); color: var(--ink) !important; }
.pc-title { font-family: var(--display); font-weight: 800; font-stretch: 80%; font-size: clamp(2.4rem, 3.8vw, 3.3rem); line-height: .9; letter-spacing: -0.025em; margin: 1.1rem 0 .5rem; }
.pc-desc { font-size: .98rem; line-height: 1.5; margin: 0 0 .9rem !important; max-width: 44ch; }
.pc-feats { list-style: none; padding: 0; margin: 0 0 1.2rem; display: flex; flex-wrap: wrap; gap: .4rem; }
.pc-feats li { display: inline-flex; align-items: center; gap: .3rem; font-size: .8rem; font-weight: 650; padding: .22rem .55rem; border-radius: 7px;
  background: rgba(10,12,27,.08); border: 1.5px solid var(--ink); margin: 0 !important; }
.st-key-portal-analyst .pc-feats li { background: rgba(244,238,225,.12); border-color: var(--ivory); }
.pc-feats .material-symbols-rounded { font-size: 15px; }
.st-key-portal-employee [data-testid="stBaseButton-primary"] { background: var(--ink) !important; }
.st-key-portal-analyst [data-testid="stBaseButton-primary"] { background: var(--lime) !important; box-shadow: 3px 3px 0 var(--ink) !important; }
.st-key-portal-analyst [data-testid="stBaseButton-primary"] p { color: var(--ink) !important; }
.pg-foot { text-align: center; color: var(--ink-2); font-size: .84rem; margin-top: 2rem; font-weight: 550; }
.pg-foot .material-symbols-rounded { font-size: 16px; vertical-align: -3px; }
@media (max-width: 900px) {
  .st-key-portal-analyst { margin: .4rem 0 0; transform: none; } .st-key-portal-employee { transform: none; }
  @keyframes pg-door-a { from { opacity: 0; } to { opacity: 1; transform: none; } } @keyframes pg-door-b { from { opacity: 0; } to { opacity: 1; transform: none; } }
  .pg-panel { min-height: 0; } .st-key-auth-card { padding: 1.6rem 1.3rem 1.3rem !important; } .st-key-auth-panel { padding: 1.5rem 1.3rem !important; }
}
@media (max-width: 640px) { .pg-brandbar .tag { display: none; } .pg-brandbar img { height: 76px; } }
</style>
"""


def accent_style(role: str) -> str:
    """Page-wide accent for one portal's screens: lime for Employees, cobalt for Senior Analysts."""
    p = PORTALS[role]
    return f"<style>html body .stApp {{ --ac: {p['accent']}; --ac-on: {p['on']}; }}</style>"


def ui_words(text: str) -> str:
    from ui import words

    return words(text)


def theme(ambient: bool = False, role: str | None = None) -> None:
    """Styles for the signed-out pages; `role` gives the page that portal's colour.
    (`ambient` is accepted for compatibility; every sign-in screen now shares one look.)"""
    st.markdown(_CSS, unsafe_allow_html=True)
    if role in PORTALS:
        st.markdown(accent_style(role), unsafe_allow_html=True)


def icon(name: str) -> str:
    return f'<span class="material-symbols-rounded" aria-hidden="true">{esc(name)}</span>'


def message(kind: str, text: str, *, raw_html: bool = False) -> None:
    ico = {"error": "error", "success": "check_circle", "info": "info"}[kind]
    body = text if raw_html else esc(text)
    role = "alert" if kind == "error" else "status"
    st.markdown(f'<div class="pg-msg {kind}" role="{role}">{icon(ico)}<div>{body}</div></div>', unsafe_allow_html=True)


def brand_bar(back_label: str | None = None, back_to: str | None = None, key: str = "brand-back") -> None:
    """Logo on the left, the way back on the right, both on one line."""
    with st.container(key="brandbar", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
        st.markdown(
            f'<div class="pg-brandbar"><img class="pg-logo" src="app/static/pragyaan-logo-full.png?v=red" alt="PRAGYAAN" height="64">'
            f'<span class="tag">Support intelligence for every ticket</span></div>',
            unsafe_allow_html=True, width="content")
        with st.container(horizontal=True, gap="small", width="content", vertical_alignment="center"):
            from ui import theme_switch
            theme_switch()
            if back_label and back_to:
                if st.button(back_label, icon=":material/arrow_back:", type="tertiary", key=key):
                    st.switch_page(st.session_state["_pages"][back_to])


def footer() -> None:
    st.markdown(
        f'<div class="pg-foot">{icon("lock")} Passwords are stored only as salted hashes, sessions expire on their own, '
        f'and access is checked on the server for every page.</div>',
        unsafe_allow_html=True)


# ---------------------------------------------------------------- browser cookie (session token)

def set_session_cookie(token: str, remember: bool) -> None:
    """Store the session token in the browser so a refresh keeps you signed in. Only a hash of
    the token is kept on the server; "Remember me" makes the cookie last 30 days, otherwise it
    ends with the browser session (the server also expires it after 12 hours)."""
    max_age = "; max-age=2592000" if remember else ""
    st.html(
        "<script>(function(){var s=location.protocol==='https:'?'; Secure':'';"
        f"document.cookie={json.dumps(COOKIE + '=' + token)}+'; path=/; SameSite=Strict{max_age}'+s;}})();</script>",
        unsafe_allow_javascript=True, width=1)


def clear_session_cookie() -> None:
    st.html(f"<script>document.cookie={json.dumps(COOKIE + '=; path=/; max-age=0; SameSite=Strict')};</script>",
            unsafe_allow_javascript=True, width=1)


def start_session(account: dict, remember: bool) -> None:
    """Called after copilot.auth.authenticate succeeded: create the server-side session."""
    from copilot.activity import log_activity
    from copilot.auth import create_session

    token = create_session(account["id"], remember=remember)
    st.session_state["auth_token"] = token
    st.session_state["user"] = account
    st.session_state["_set_cookie"] = (token, remember)
    log_activity("login", f"{account['name']} signed in to the {account['role_label']} portal",
                 actor=account["login_id"])


# ---------------------------------------------------------------- portal login page

def _side_panel(role: str) -> None:
    from ui import sticker

    p = PORTALS[role]
    points = "".join(f'<li>{icon(i)}{esc(t)}</li>' for i, t in p["points"])
    with st.container(key="auth-panel"):
        st.markdown(
            f'<div class="pg-panel"><div class="top"><span class="chip">{icon(p["icon"])}</span><b>{esc(p["eyebrow"])}</b></div>'
            f'{sticker("Role-verified sign-in", "paper", rot=6, delay=.6)}'
            f'<div class="word">{ui_words(p["word"])}</div>'
            f'<h2>{esc(p["pitch"])}</h2><p>{esc(p["pitch_text"])}</p><ul>{points}</ul>'
            f'<div class="sec"><span>{icon("lock")}Salted password hashes</span><span>{icon("timer")}Sessions expire</span>'
            f'<span>{icon("verified_user")}Checked on the server</span></div></div>', unsafe_allow_html=True)


def login_page(role: str) -> None:
    """Shared sign-in screen for one portal. Credentials are checked by copilot.auth.authenticate,
    which also rejects accounts of the other role."""
    from copilot.auth import AuthError, authenticate

    p = PORTALS[role]
    theme(role=role)
    brand_bar("Back to role selection", "login", key=f"top-back-{role}")
    panel, form = st.columns([1.1, 1])
    with panel:
        _side_panel(role)
    with form:
        with st.container(key="auth-card"):
            st.markdown(f'<div class="pg-form-head">'
                        f'<div class="ic">{icon(p["icon"])}</div><h1>{ui_words(p["title"])}</h1>'
                        f'<p>{esc(p["subtitle"])}</p></div>', unsafe_allow_html=True)
            flash = st.session_state.pop("_auth_flash", None)
            if flash:
                message(flash[0], flash[1])
            with st.form(f"signin-{role}", border=False, enter_to_submit=True):
                login_id = st.text_input(p["id_label"], placeholder=p["id_hint"], icon=":material/badge:",
                                         autocomplete="username", max_chars=64, key=f"{role}-id")
                password = st.text_input("Password", type="password", placeholder="Enter your password",
                                         icon=":material/lock:", autocomplete="current-password", key=f"{role}-pw")
                remember = st.checkbox("Remember me for 30 days", key=f"{role}-remember",
                                       help="Keeps you signed in on this browser. Don't use on shared computers.")
                submitted = st.form_submit_button("Sign in", type="primary", width="stretch",
                                                  icon=":material/login:")
            err_slot = st.empty()
            c1, c2 = st.columns(2)
            if c1.button("Forgot password?", type="tertiary", key=f"forgot-{role}", icon=":material/key:"):
                st.session_state["forgot_role"] = role
                st.switch_page(st.session_state["_pages"]["forgot"])
            if c2.button("Back to role selection", type="tertiary", key=f"back-{role}", icon=":material/swap_horiz:"):
                st.switch_page(st.session_state["_pages"]["login"])
            if submitted:
                with err_slot.container():
                    with st.spinner("Verifying your credentials…"):
                        try:
                            account = authenticate(login_id, password, role)
                        except AuthError as e:
                            message("error", str(e))
                            account = None
                if account:
                    start_session(account, remember)
                    st.rerun()
    footer()
