"""PRAGYAAN sign-in experience: dark enterprise theme, animated network backdrop, the shared
login form for both portals, and the browser-cookie half of session handling.

Only the look lives here; every credential and role check happens in copilot.auth on the server.
"""

from __future__ import annotations

import html
import json
import math
import random
from pathlib import Path

import streamlit as st

APP = Path(__file__).resolve().parent
COOKIE = "pragyaan_session"
esc = html.escape

VIOLET, CYAN, TEAL = "#8B5CF6", "#22D3EE", "#2DD4BF"
PORTALS = {
    "employee": {
        "label": "Employee", "id_label": "Employee ID", "id_hint": "e.g. EMP-1042", "icon": "work",
        "eyebrow": "Employee portal", "title": "Welcome Back, Employee",
        "subtitle": "Sign in to access your enterprise workspace.",
        "accent": CYAN, "accent2": TEAL,
        "pitch": "Your enterprise workspace",
        "pitch_text": "Raise a ticket and PRAGYAAN predicts its priority, checks thousands of resolved tickets for a "
                      "matching solution and routes it to the right people.",
        "points": [("confirmation_number", "Submit tickets and track every step to resolution"),
                   ("auto_awesome", "Ask the AI assistant, answered from company knowledge"),
                   ("library_books", "Search policies, guides and past solutions")],
    },
    "analyst": {
        "label": "Senior Analyst", "id_label": "Senior Analyst ID", "id_hint": "e.g. SA-007", "icon": "shield_person",
        "eyebrow": "Senior Analyst portal", "title": "Welcome Back, Senior Analyst",
        "subtitle": "Access your intelligence and operations command center.",
        "accent": VIOLET, "accent2": "#6366F1",
        "pitch": "Operations command center",
        "pitch_text": "Review machine-suggested solutions, work the escalation queue, assign tickets to your team "
                      "and watch priority and model performance in one place.",
        "points": [("fact_check", "Approve or reject similarity-matched solutions"),
                   ("assignment_ind", "Assign escalated tickets and balance team workload"),
                   ("monitoring", "Analytics, model benchmarks and team management")],
    },
}


# ---------------------------------------------------------------- backdrop

def _network_svg(seed: int = 11) -> str:
    """Abstract data-network backdrop: nodes, links and a few travelling pulses (pure SVG/CSS)."""
    rng = random.Random(seed)
    w, h = 1600, 1000
    nodes = [(rng.uniform(0, w), rng.uniform(0, h)) for _ in range(46)]
    links = []
    for i, (x1, y1) in enumerate(nodes):
        near = sorted(((math.dist((x1, y1), (x2, y2)), j) for j, (x2, y2) in enumerate(nodes) if j != i))[:2]
        for d, j in near:
            if d < 330 and (j, i) not in links:
                links.append((i, j))
    parts = []
    for k, (i, j) in enumerate(links):
        (x1, y1), (x2, y2) = nodes[i], nodes[j]
        parts.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="l"/>')
        if k % 4 == 0:  # travelling pulse along some links
            length = math.dist((x1, y1), (x2, y2))
            col = "url(#pc)" if k % 8 == 0 else "url(#pv)"
            parts.append(
                f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" class="p" stroke="{col}" '
                f'style="stroke-dasharray:26 {length + 60:.0f};stroke-dashoffset:{length + 86:.0f};'
                f'animation-duration:{rng.uniform(5, 9):.1f}s;animation-delay:-{rng.uniform(0, 8):.1f}s"/>')
    for k, (x, y) in enumerate(nodes):
        r = rng.choice((1.6, 2, 2.4, 3.2))
        cls = "n t" if k % 3 == 0 else "n"
        parts.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" class="{cls}" '
                     f'style="animation-delay:-{rng.uniform(0, 6):.1f}s"/>')
    return (
        f'<svg class="net" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" aria-hidden="true">'
        f'<defs><linearGradient id="pv" x1="0" x2="1"><stop offset="0" stop-color="{VIOLET}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{VIOLET}"/></linearGradient>'
        f'<linearGradient id="pc" x1="0" x2="1"><stop offset="0" stop-color="{CYAN}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>{"".join(parts)}</svg>'
    )


_CSS = """
<style>
:root { --a-ink:#EEF1FF; --a-ink2:#A9B1D6; --a-muted:#7B83AC; --a-line:rgba(148,163,255,.16);
        --a-violet:#8B5CF6; --a-cyan:#22D3EE; --a-teal:#2DD4BF; }
.stApp { background: #060A1C !important; color: var(--a-ink); }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMainBlockContainer"] { max-width: 1160px; padding-top: 1.6rem !important; padding-bottom: 3rem; position: relative; z-index: 2; }
.stApp p, .stApp li, .stApp label { color: var(--a-ink2); }
.stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--a-ink); }

/* backdrop */
.pg-auth-bg { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden;
  background:
    radial-gradient(1100px 640px at 88% -12%, rgba(139,92,246,.26), transparent 62%),
    radial-gradient(900px 560px at -8% 112%, rgba(34,211,238,.16), transparent 60%),
    radial-gradient(600px 400px at 50% 50%, rgba(45,212,191,.05), transparent 70%),
    linear-gradient(180deg, #070B21 0%, #060A1A 100%); }
.pg-auth-bg::before { content: ""; position: absolute; inset: 0;
  background-image: radial-gradient(rgba(169,177,214,.10) 1px, transparent 1.2px); background-size: 28px 28px;
  -webkit-mask-image: radial-gradient(ellipse at 50% 40%, #000 30%, transparent 78%);
          mask-image: radial-gradient(ellipse at 50% 40%, #000 30%, transparent 78%); }
.pg-auth-bg .blob { position: absolute; border-radius: 50%; filter: blur(70px); opacity: .55; }
.pg-auth-bg .b1 { width: 420px; height: 420px; background: rgba(139,92,246,.35); top: 8%; right: 6%; animation: pg-drift 22s ease-in-out infinite; }
.pg-auth-bg .b2 { width: 360px; height: 360px; background: rgba(34,211,238,.22); bottom: 4%; left: 4%; animation: pg-drift 26s ease-in-out infinite reverse; }
.pg-auth-bg .net { position: absolute; inset: 0; width: 100%; height: 100%; opacity: .75; }
.pg-auth-bg .net .l { stroke: rgba(148,163,255,.13); stroke-width: 1; }
.pg-auth-bg .net .p { stroke-width: 1.6; stroke-linecap: round; fill: none; animation-name: pg-pulse; animation-timing-function: linear; animation-iteration-count: infinite; }
.pg-auth-bg .net .n { fill: rgba(190,198,255,.55); }
.pg-auth-bg .net .n.t { fill: #9FE9F7; animation: pg-twinkle 6s ease-in-out infinite; }
@keyframes pg-pulse { to { stroke-dashoffset: 0; } }
@keyframes pg-twinkle { 0%,100% { opacity: .25; } 50% { opacity: 1; } }
@keyframes pg-drift { 0%,100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-40px,30px) scale(1.08); } }
@keyframes pg-in { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes pg-sweep { to { transform: rotate(360deg); } }

/* brand bar */
.pg-brandbar { display: flex; align-items: center; gap: .7rem; }
.pg-brandbar .tag { font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: var(--a-muted);
  border-left: 1px solid var(--a-line); padding-left: .75rem; }

/* typography */
.pg-eyebrow { display: inline-flex; align-items: center; gap: .45rem; font-size: .74rem; font-weight: 600; letter-spacing: .16em;
  text-transform: uppercase; color: #C4B5FD; padding: .32rem .7rem; border-radius: 999px;
  background: rgba(139,92,246,.12); border: 1px solid rgba(139,92,246,.32); }
.pg-eyebrow i { width: 6px; height: 6px; border-radius: 50%; background: var(--a-cyan); box-shadow: 0 0 10px var(--a-cyan); }
.pg-hero-t { font-family: Sora, 'IBM Plex Sans', sans-serif; font-weight: 700; color: var(--a-ink); letter-spacing: -.025em;
  font-size: clamp(2rem, 4.2vw, 3.1rem); line-height: 1.08; margin: 1rem 0 .7rem; }
.pg-grad { background: linear-gradient(92deg, #C4B5FD 0%, #8B5CF6 35%, #22D3EE 75%, #5EEAD4 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent; }
.pg-hero-s { color: var(--a-ink2); font-size: 1.04rem; line-height: 1.6; max-width: 60ch; margin: 0 auto; }

/* glass surfaces */
[class*="st-key-portal-"], .st-key-auth-card, .st-key-auth-panel {
  position: relative; border-radius: 22px !important;
  background: linear-gradient(180deg, rgba(22,28,72,.72) 0%, rgba(11,16,46,.78) 100%);
  border: 1px solid rgba(148,163,255,.14) !important;
  -webkit-backdrop-filter: blur(18px) saturate(140%); backdrop-filter: blur(18px) saturate(140%);
  box-shadow: 0 30px 80px -34px rgba(0,0,0,.85), inset 0 1px 0 rgba(255,255,255,.05);
  animation: pg-in .6s cubic-bezier(.2,.8,.2,1) both; }
[class*="st-key-portal-"]::before, .st-key-auth-card::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1px; pointer-events: none;
  background: linear-gradient(140deg, var(--pc, rgba(139,92,246,.75)), rgba(255,255,255,.04) 45%, transparent 70%);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); -webkit-mask-composite: xor;
          mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0); mask-composite: exclude;
  opacity: .55; transition: opacity .3s ease; }

/* portal cards */
[class*="st-key-portal-"] { padding: 1.9rem 1.9rem 1.7rem !important; transition: transform .35s cubic-bezier(.2,.8,.2,1), box-shadow .35s ease; }
.st-key-portal-employee { --pc: #22D3EE; }
.st-key-portal-analyst { --pc: #8B5CF6; animation-delay: .08s; }
[class*="st-key-portal-"]:hover { transform: translateY(-6px);
  box-shadow: 0 40px 90px -36px rgba(0,0,0,.9), 0 0 0 1px color-mix(in srgb, var(--pc) 45%, transparent),
              0 0 60px -12px color-mix(in srgb, var(--pc) 55%, transparent); }
[class*="st-key-portal-"]:hover::before { opacity: 1; }
.pc-top { display: flex; align-items: center; justify-content: space-between; }
.pc-icon { width: 58px; height: 58px; border-radius: 16px; display: grid; place-items: center; color: #fff;
  background: linear-gradient(135deg, var(--pc), color-mix(in srgb, var(--pc) 35%, #0B1030));
  box-shadow: 0 12px 30px -10px color-mix(in srgb, var(--pc) 70%, transparent), inset 0 1px 0 rgba(255,255,255,.25); }
.pc-icon .material-symbols-rounded { font-size: 30px; }
.pc-kicker { font-size: .7rem; font-weight: 600; letter-spacing: .16em; text-transform: uppercase;
  color: color-mix(in srgb, var(--pc) 70%, #fff); }
.pc-title { font-family: Sora, sans-serif; font-size: 1.55rem; font-weight: 700; color: var(--a-ink); margin: 1.25rem 0 .45rem; letter-spacing: -.02em; }
.pc-desc { color: var(--a-ink2); font-size: .97rem; line-height: 1.6; margin: 0 0 1.1rem; min-height: 4.8em; }
.pc-feats { list-style: none; padding: 0; margin: 0 0 1.4rem; display: grid; gap: .55rem; }
.pc-feats li { display: flex; align-items: center; gap: .6rem; font-size: .9rem; color: #C9CFEE; }
.pc-feats .material-symbols-rounded { font-size: 18px; color: color-mix(in srgb, var(--pc) 80%, #fff); }

/* buttons */
.stApp [data-testid="stBaseButton-primary"], .stApp [data-testid="stBaseButton-primaryFormSubmit"] {
  border: 0 !important; color: #fff !important; font-weight: 600; min-height: 2.95rem; border-radius: 12px !important;
  background: linear-gradient(92deg, var(--b1, #7C3AED) 0%, var(--b2, #4F46E5) 100%) !important;
  box-shadow: 0 14px 30px -14px var(--bglow, rgba(124,58,237,.9)), inset 0 1px 0 rgba(255,255,255,.18);
  transition: filter .2s ease, transform .15s ease, box-shadow .2s ease; }
.stApp [data-testid="stBaseButton-primary"]:hover, .stApp [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  filter: brightness(1.12); transform: translateY(-1px); }
.stApp [data-testid="stBaseButton-primary"] p, .stApp [data-testid="stBaseButton-primaryFormSubmit"] p { color: #fff !important; }
.st-key-portal-employee, .pg-emp { --b1: #0891B2; --b2: #0D9488; --bglow: rgba(34,211,238,.75); }
.st-key-portal-analyst, .pg-ana { --b1: #7C3AED; --b2: #4F46E5; --bglow: rgba(139,92,246,.85); }
.stApp [data-testid="stBaseButton-secondary"] { background: rgba(255,255,255,.04) !important; color: var(--a-ink) !important;
  border: 1px solid var(--a-line) !important; border-radius: 12px !important; }
.stApp [data-testid="stBaseButton-secondary"]:hover { border-color: rgba(139,92,246,.6) !important; background: rgba(139,92,246,.1) !important; }
.stApp [data-testid="stBaseButton-secondary"] p { color: var(--a-ink) !important; }
.stApp [data-testid="stBaseButton-tertiary"] { color: var(--a-ink2) !important; }
.stApp [data-testid="stBaseButton-tertiary"] p { color: inherit !important; }
.stApp [data-testid="stBaseButton-tertiary"]:hover { color: var(--a-cyan) !important; }

/* form fields */
.stApp [data-testid="stWidgetLabel"] p { color: #C3C9EA !important; font-weight: 500; font-size: .86rem; }
.stApp [data-testid="stTextInputRootElement"], .stApp [data-testid="stTextAreaRootElement"],
.stApp [data-baseweb="input"], .stApp [data-baseweb="select"] > div, .stApp [data-baseweb="textarea"] {
  background: rgba(8,12,38,.7) !important; border: 1px solid rgba(148,163,255,.22) !important; border-radius: 12px !important;
  transition: border-color .2s ease, box-shadow .2s ease; }
.stApp [data-testid="stTextInputRootElement"]:hover { border-color: rgba(148,163,255,.4) !important; }
.stApp [data-testid="stTextInputRootElement"]:focus-within, .stApp [data-testid="stTextAreaRootElement"]:focus-within,
.stApp [data-baseweb="input"]:focus-within, .stApp [data-baseweb="textarea"]:focus-within {
  border-color: rgba(139,92,246,.9) !important; box-shadow: 0 0 0 4px rgba(139,92,246,.2) !important; }
.stApp [data-testid="stTextInputRootElement"] > div { background: transparent !important; }
.stApp [data-testid="stTextInputField"], .stApp [data-baseweb="input"] input, .stApp textarea {
  color: var(--a-ink) !important; -webkit-text-fill-color: var(--a-ink); caret-color: var(--a-cyan);
  background: transparent !important; font-size: .98rem; }
.stApp [data-testid="stTextInputField"] { min-height: 2.75rem; }
.stApp [data-testid="stTextInputField"]::placeholder, .stApp textarea::placeholder { color: #5D668F !important; -webkit-text-fill-color: #5D668F; }
.stApp [data-testid="stTextInputRootElement"] button, .stApp [data-testid="stTextInputRootElement"] svg,
.stApp [data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"] { color: #8F98C4 !important; }
.stApp [data-testid="stTextInputRootElement"]:focus-within [data-testid="stIconMaterial"] { color: #C4B5FD !important; }
.stApp input:-webkit-autofill { -webkit-box-shadow: 0 0 0 1000px #0B1033 inset !important; -webkit-text-fill-color: var(--a-ink) !important; }
.stApp [data-testid="stCheckbox"] label p { color: var(--a-ink2) !important; font-size: .9rem; }
.stApp [data-testid="InputInstructions"] { display: none; }
.stApp [data-testid="stForm"] { border: 0; padding: 0; }
.stApp [data-testid="stSpinner"], .stApp [data-testid="stSpinner"] p { color: var(--a-ink2) !important; }
.stApp hr { border-color: var(--a-line); }

/* login card + side panel */
.st-key-auth-card { padding: 2.2rem 2.2rem 1.6rem !important; }
.st-key-auth-card.pg-emp, .st-key-auth-card { --pc: var(--card-accent, #8B5CF6); }
.pg-form-head .ic { width: 48px; height: 48px; border-radius: 14px; display: grid; place-items: center; color: #fff; margin-bottom: 1.1rem;
  background: linear-gradient(135deg, var(--card-accent), color-mix(in srgb, var(--card-accent) 30%, #0B1030));
  box-shadow: 0 12px 28px -10px var(--card-accent); }
.pg-form-head .ic .material-symbols-rounded { font-size: 26px; }
.pg-form-head h1 { font-family: Sora, sans-serif; font-size: 1.75rem; font-weight: 700; color: var(--a-ink); margin: 0; padding: 0; letter-spacing: -.02em; }
.pg-form-head p { color: var(--a-ink2); margin: .35rem 0 1.3rem; font-size: .98rem; }
.st-key-auth-panel { padding: 2.1rem 2rem !important; overflow: hidden; min-height: 100%; }
.pg-panel h2 { font-family: Sora, sans-serif; font-size: 1.6rem; line-height: 1.22; color: var(--a-ink); margin: 1.1rem 0 .7rem; padding: 0; letter-spacing: -.02em; }
.pg-panel p { color: var(--a-ink2); font-size: .97rem; line-height: 1.62; }
.pg-panel ul { list-style: none; padding: 0; margin: 1.3rem 0 0; display: grid; gap: .8rem; }
.pg-panel li { display: grid; grid-template-columns: 36px 1fr; gap: .75rem; align-items: center; color: #CDD2F0; font-size: .93rem; }
.pg-panel li span.ico { width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center;
  background: rgba(255,255,255,.05); border: 1px solid var(--a-line); color: var(--card-accent); }
.pg-panel li .material-symbols-rounded { font-size: 19px; }
.pg-secure { display: flex; flex-wrap: wrap; gap: .5rem 1.1rem; margin-top: 1.5rem; padding-top: 1.1rem; border-top: 1px solid var(--a-line);
  font-size: .8rem; color: var(--a-muted); }
.pg-secure span { display: inline-flex; align-items: center; gap: .35rem; }
.pg-secure .material-symbols-rounded { font-size: 16px; color: var(--a-teal); }
/* analyst "radar" emblem: decorative, no data */
.pg-radar { position: relative; width: 150px; height: 150px; margin: .4rem 0 .2rem; }
.pg-radar::before { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 1px solid rgba(139,92,246,.45);
  background: repeating-radial-gradient(circle, rgba(139,92,246,.32) 0 1px, transparent 1px 25px),
              linear-gradient(90deg, transparent 49.6%, rgba(139,92,246,.25) 50%, transparent 50.4%),
              linear-gradient(0deg, transparent 49.6%, rgba(139,92,246,.25) 50%, transparent 50.4%); }
.pg-radar::after { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, rgba(139,92,246,.42), rgba(34,211,238,.06) 18%, transparent 26%);
  animation: pg-sweep 5s linear infinite; }
.pg-radar i { position: absolute; width: 7px; height: 7px; border-radius: 50%; background: #22D3EE; box-shadow: 0 0 12px #22D3EE;
  animation: pg-twinkle 3s ease-in-out infinite; z-index: 1; }
.pg-orbit { position: relative; width: 150px; height: 150px; margin: .4rem 0 .2rem; }
.pg-orbit span { position: absolute; inset: 0; border-radius: 50%; border: 1px dashed rgba(34,211,238,.35); animation: pg-sweep 24s linear infinite; }
.pg-orbit span:nth-child(2) { inset: 22px; border-color: rgba(45,212,191,.3); animation-duration: 16s; animation-direction: reverse; }
.pg-orbit span:nth-child(3) { inset: 46px; border: 0; background: radial-gradient(circle, rgba(34,211,238,.6), rgba(13,148,136,.15) 60%, transparent 70%); }
.pg-orbit span::after { content: ""; position: absolute; top: -4px; left: 50%; width: 8px; height: 8px; border-radius: 50%; background: #22D3EE; box-shadow: 0 0 12px #22D3EE; }
.pg-orbit span:nth-child(3)::after { display: none; }

/* inline messages */
.pg-msg { display: flex; gap: .65rem; align-items: flex-start; padding: .8rem .95rem; border-radius: 12px; font-size: .9rem; line-height: 1.45;
  margin: .2rem 0 .8rem; animation: pg-in .3s ease both; }
.pg-msg .material-symbols-rounded { font-size: 19px; margin-top: 1px; }
.pg-msg.error { background: rgba(244,63,94,.1); border: 1px solid rgba(244,63,94,.35); color: #FECDD3; }
.pg-msg.error .material-symbols-rounded { color: #FB7185; }
.pg-msg.success { background: rgba(45,212,191,.1); border: 1px solid rgba(45,212,191,.35); color: #CCFBF1; }
.pg-msg.success .material-symbols-rounded { color: #2DD4BF; }
.pg-msg.info { background: rgba(34,211,238,.08); border: 1px solid rgba(34,211,238,.28); color: #CFFAFE; }
.pg-msg.info .material-symbols-rounded { color: #22D3EE; }
.pg-msg code { background: rgba(255,255,255,.08); color: #fff; padding: .05rem .35rem; border-radius: 5px; }

.pg-foot { text-align: center; color: var(--a-muted); font-size: .8rem; margin-top: 2.2rem; }
.pg-foot .material-symbols-rounded { font-size: 15px; color: var(--a-teal); }

@media (max-width: 900px) {
  .pc-desc { min-height: 0; }
  .st-key-auth-card { padding: 1.6rem 1.3rem 1.2rem !important; }
  [class*="st-key-portal-"] { padding: 1.5rem 1.3rem 1.3rem !important; }
  .pg-panel-wrap { display: none; }
}
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
</style>
"""


def theme() -> None:
    """Dark theme + animated backdrop for the signed-out pages."""
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="pg-auth-bg"><div class="blob b1"></div><div class="blob b2"></div>{_network_svg()}</div>',
                unsafe_allow_html=True)


def icon(name: str) -> str:
    return f'<span class="material-symbols-rounded" aria-hidden="true">{esc(name)}</span>'


def message(kind: str, text: str, *, raw_html: bool = False) -> None:
    ico = {"error": "error", "success": "check_circle", "info": "info"}[kind]
    body = text if raw_html else esc(text)
    role = "alert" if kind == "error" else "status"
    st.markdown(f'<div class="pg-msg {kind}" role="{role}">{icon(ico)}<div>{body}</div></div>', unsafe_allow_html=True)


def brand_bar(back_label: str | None = None, back_to: str | None = None, key: str = "brand-back") -> None:
    left, right = st.columns([3, 1], vertical_alignment="center")
    with left:
        st.markdown(
            f'<div class="pg-brandbar"><img src="app/static/pragyaan-logo.svg" alt="PRAGYAAN" height="34">'
            f'<span class="tag">Enterprise knowledge &amp; support intelligence</span></div>',
            unsafe_allow_html=True)
    if back_label and back_to:
        with right:
            _, c = st.columns([0.2, 1])
            if c.button(back_label, icon=":material/arrow_back:", type="tertiary", key=key, width="stretch"):
                st.switch_page(st.session_state["_pages"][back_to])


def footer() -> None:
    st.markdown(
        f'<div class="pg-foot">{icon("lock")} Passwords are stored only as salted hashes · '
        f'sessions expire automatically · access is checked on the server for every page</div>',
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
    p = PORTALS[role]
    emblem = ('<div class="pg-radar"><i style="top:32%;left:64%"></i><i style="top:62%;left:30%;animation-delay:1.2s"></i>'
              '<i style="top:24%;left:38%;animation-delay:2.1s"></i></div>') if role == "analyst" else \
             '<div class="pg-orbit"><span></span><span></span><span></span></div>'
    points = "".join(f'<li><span class="ico">{icon(i)}</span>{esc(t)}</li>' for i, t in p["points"])
    with st.container(key="auth-panel"):
        st.markdown(
            f'<div class="pg-panel" style="--card-accent:{p["accent"]}">{emblem}'
            f'<span class="pg-eyebrow"><i></i>{esc(p["eyebrow"])}</span>'
            f'<h2>{esc(p["pitch"])}</h2><p>{esc(p["pitch_text"])}</p><ul>{points}</ul>'
            f'<div class="pg-secure"><span>{icon("verified_user")}Role-verified sign-in</span>'
            f'<span>{icon("lock")}PBKDF2 password hashing</span><span>{icon("timer")}Auto-expiring sessions</span></div>'
            '</div>', unsafe_allow_html=True)


def login_page(role: str) -> None:
    """Shared sign-in screen for one portal. Credentials are checked by copilot.auth.authenticate,
    which also rejects accounts of the other role."""
    from copilot.auth import AuthError, authenticate

    p = PORTALS[role]
    theme()
    st.markdown(f"<style>.st-key-auth-card {{ --card-accent: {p['accent']}; --pc: {p['accent']}; }}"
                f".st-key-auth-card {{ {'--b1:#0891B2;--b2:#0D9488;--bglow:rgba(34,211,238,.75);' if role == 'employee' else '--b1:#7C3AED;--b2:#4F46E5;--bglow:rgba(139,92,246,.85);'} }}"
                "</style>", unsafe_allow_html=True)
    brand_bar("Back to role selection", "login", key=f"top-back-{role}")
    st.write("")
    panel, form = st.columns([1, 1.05], gap="large")
    with panel:
        st.markdown('<div class="pg-panel-wrap"></div>', unsafe_allow_html=True)
        _side_panel(role)
    with form:
        with st.container(key="auth-card"):
            st.markdown(f'<div class="pg-form-head" style="--card-accent:{p["accent"]}">'
                        f'<div class="ic">{icon(p["icon"])}</div><h1>{esc(p["title"])}</h1>'
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
