"""Public landing page."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.config import EVAL_RESULTS, SIM_THRESHOLD  # noqa: E402
from copilot.triage import archive_available, model_name  # noqa: E402

P = st.session_state.get("_pages", {})


@st.cache_data(ttl=300, show_spinner=False)
def facts() -> dict:
    f = {"kb": archive_available(), "model": model_name(), "n_algos": None, "f1": None, "hit5": None, "route": None}
    try:
        sev = pd.read_csv(EVAL_RESULTS / "severity_comparison.csv")
        f["n_algos"] = len(sev)
        f["f1"] = float(sev["macro_f1"].max())
    except Exception:
        pass
    try:
        hit = pd.read_csv(EVAL_RESULTS / "retrieval_hit_at_k.csv")
        f["hit5"] = float(hit.sort_values("k").iloc[-1]["hit_queue"])
    except Exception:
        pass
    try:
        sw = pd.read_csv(EVAL_RESULTS / "threshold_sweep.csv")
        f["route"] = float(sw.iloc[(sw["threshold"] - SIM_THRESHOLD).abs().argsort()[:1]].iloc[0]["accuracy"])
    except Exception:
        pass
    return f


F = facts()

st.markdown(
    """
<style>
[data-testid="stMainBlockContainer"] { padding-top: 1rem; max-width: 1240px; }
.st-key-hero {
  background:
    radial-gradient(600px 340px at 85% 30%, rgba(98,116,255,.35), transparent 65%),
    radial-gradient(420px 260px at 70% 95%, rgba(240,162,59,.18), transparent 70%),
    linear-gradient(160deg, #141D45 0%, #0E1534 100%);
  border-radius: 22px; padding: 1.4rem 2.2rem 2.6rem !important; color: #E8EBF7;
  box-shadow: 0 30px 60px -30px rgba(14,21,52,.6); overflow: hidden;
}
.st-key-hero [data-testid="stBaseButton-secondary"] { background: rgba(255,255,255,.06); color: #fff; border-color: rgba(255,255,255,.22); }
.st-key-hero [data-testid="stBaseButton-secondary"]:hover { background: rgba(255,255,255,.12); border-color: rgba(255,255,255,.4); color: #fff; }
.pg-hero-copy { animation: pg-rise .7s cubic-bezier(.2,.8,.2,1) both; }
.pg-hero-copy h1 { font-family: Sora, sans-serif; font-weight: 700; color: #fff; font-size: clamp(2.1rem, 4.2vw, 3.35rem);
  line-height: 1.08; letter-spacing: -0.03em; margin: 2.2rem 0 1rem; padding: 0; max-width: 15ch; }
.pg-hero-copy p { color: #B9C0E0; font-size: 1.08rem; line-height: 1.6; max-width: 46ch; margin: 0 0 1.4rem; }
.pg-orbit { position: relative; height: 380px; display: grid; place-items: center; }
@media (prefers-reduced-motion: reduce) { .pg-orbit .rv { display: none; } }
.pg-orbit .disc { width: 150px; height: 150px; border-radius: 50%;
  background: radial-gradient(circle at 35% 30%, #A9B4FF 0%, #6576F2 38%, #3343C4 75%, #26339A 100%);
  box-shadow: 0 0 80px rgba(110,128,255,.45), inset -14px -18px 30px rgba(10,16,60,.45); }
.pg-orbit .ring { position: absolute; width: 330px; height: 330px; border-radius: 50%; transform: rotateX(72deg) rotateZ(-20deg); }
.pg-orbit .ring::before { content: ""; position: absolute; inset: 0; border-radius: 50%; border: 2px solid rgba(240,162,59,.85); }
.pg-orbit .spin { position: absolute; inset: 0; animation: pg-orbit 9s linear infinite; }
.pg-orbit .rover { position: absolute; top: -9px; left: calc(50% - 9px); width: 18px; height: 18px; border-radius: 50%;
  background: #F0A23B; box-shadow: 0 0 0 4px rgba(240,162,59,.25), 0 0 18px rgba(240,162,59,.9); }
.pg-chip { position: absolute; background: rgba(18,26,58,.72); border: 1px solid rgba(255,255,255,.14); color: #E8EBF7;
  padding: .5rem .75rem; border-radius: 12px; font-size: .82rem; backdrop-filter: blur(8px); white-space: nowrap;
  animation: pg-rise .8s cubic-bezier(.2,.8,.2,1) both; }
.pg-chip b { color: #fff; font-family: Sora, sans-serif; font-weight: 600; font-size: .95rem; display: block; }
.pg-chip.c1 { top: 22px; right: 4%; animation-delay: .25s; } .pg-chip.c2 { bottom: 42px; left: 2%; animation-delay: .4s; }
.pg-chip.c3 { bottom: 4px; right: 12%; animation-delay: .55s; }
.pg-sec { margin: 2.6rem 0 .9rem; }
.pg-sec h2 { font-family: Sora, sans-serif; font-weight: 600; font-size: 1.45rem; margin: 0; padding: 0; letter-spacing: -0.02em; }
.pg-sec p { color: #545B78; margin: .3rem 0 0; }
.pg-mod { background: #fff; border: 1px solid #E2E5EF; border-radius: 16px; padding: 1.15rem 1.2rem; height: 100%;
  box-shadow: 0 1px 2px rgba(18,26,58,.05); transition: transform .16s ease, box-shadow .16s ease; }
.pg-mod:hover { transform: translateY(-3px); box-shadow: 0 16px 32px -20px rgba(18,26,58,.35); }
.pg-mod .ic { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; color: #4257E0;
  background: linear-gradient(135deg, rgba(66,87,224,.13), rgba(240,162,59,.16)); margin-bottom: .7rem; }
.pg-mod h3 { font-family: Sora, sans-serif; font-size: 1.02rem; font-weight: 600; margin: 0 0 .3rem; padding: 0; }
.pg-mod p { color: #545B78; font-size: .9rem; line-height: 1.5; margin: 0; }
.pg-step { display: grid; grid-template-columns: 36px 1fr; gap: .8rem; }
.pg-step .n { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; font-family: Sora, sans-serif;
  font-weight: 600; color: #121A3A; background: #F7E2C0; }
.pg-step h4 { margin: .1rem 0 .2rem; font-size: .98rem; padding: 0; }
.pg-step p { margin: 0; color: #545B78; font-size: .88rem; line-height: 1.5; }
.pg-stat { border-left: 3px solid #F0A23B; padding: .2rem 0 .2rem 1rem; }
.pg-stat b { font-family: Sora, sans-serif; font-size: 1.9rem; font-weight: 600; color: #151A31; display: block; line-height: 1.15; }
.pg-stat span { color: #545B78; font-size: .88rem; }
.pg-foot { margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid #E2E5EF; color: #8A90A8; font-size: .85rem; }
@media (max-width: 760px) {
  .pg-orbit { height: 300px; } .pg-orbit svg { width: 300px; height: 285px; }
  .pg-chip { font-size: .74rem; padding: .4rem .6rem; } .pg-chip b { font-size: .85rem; }
  .pg-chip.c1 { top: 0; right: 0; } .pg-chip.c2 { bottom: 26px; left: 0; } .pg-chip.c3 { bottom: -6px; right: 0; }
  .st-key-hero { padding: 1rem 1.1rem 1.8rem !important; }
  .st-key-hero-signin { display: none; }
}
</style>
""",
    unsafe_allow_html=True,
)


def go(name: str) -> None:
    if name in P:
        st.switch_page(P[name])


with st.container(key="hero"):
    top_l, top_r = st.columns([4, 1.2], vertical_alignment="center")
    with top_l:
        st.image(str(ROOT / "app" / "static" / "pragyaan-logo.svg"), width=190)
    with top_r:
        if st.button("Sign in", key="hero-signin", width="stretch", icon=":material/login:"):
            go("login")

    left, right = st.columns([1.1, 1], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            """<div class="pg-hero-copy"><h1>Know what's urgent. Find what's already known.</h1>
            <p>PRAGYAAN reads each incoming ticket, predicts its priority with a trained model, answers from past
            tickets and your own documents, and turns urgent work into tracked tasks.</p></div>""",
            unsafe_allow_html=True,
        )
        b1, b2, _ = st.columns([1.15, 1.35, 0.9])
        with b1:
            if st.button("Employee portal", type="primary", width="stretch", key="hero-emp", icon=":material/work:"):
                go("employee_login")
        with b2:
            if st.button("Senior Analyst portal", width="stretch", key="hero-ana", icon=":material/shield_person:"):
                go("analyst_login")
    with right:
        kb = f"{F['kb']:,}" if F["kb"] else "No"
        f1 = f"{F['f1']:.3f} macro-F1" if F["f1"] else "trained classifier"
        algos = f"{F['n_algos']} algorithms compared" if F["n_algos"] else "benchmarked models"
        orbit = "M35 190 A165 50 0 1 1 365 190 A165 50 0 1 1 35 190"
        st.markdown(
            f"""<div class="pg-orbit" aria-hidden="true">
              <svg viewBox="0 0 400 380" width="400" height="380" style="max-width:100%">
                <defs>
                  <radialGradient id="pgd" cx="35%" cy="30%" r="75%">
                    <stop offset="0" stop-color="#B3BCFF"/><stop offset=".4" stop-color="#6576F2"/>
                    <stop offset=".8" stop-color="#3343C4"/><stop offset="1" stop-color="#26339A"/></radialGradient>
                  <filter id="pgglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
                </defs>
                <g transform="rotate(-14 200 190)">
                  <path d="M35 190 A165 50 0 0 1 365 190" fill="none" stroke="#F0A23B" stroke-opacity=".55" stroke-width="2"/>
                  <circle class="rv" r="7" fill="#F0A23B" opacity="1">
                    <animateMotion dur="10s" repeatCount="indefinite" path="{orbit}"/>
                    <animate attributeName="opacity" values="1;0" keyTimes="0;0.5" calcMode="discrete" dur="10s" repeatCount="indefinite"/>
                  </circle>
                </g>
                <circle cx="200" cy="190" r="86" fill="#6E80FF" opacity=".35" filter="url(#pgglow)"/>
                <circle cx="200" cy="190" r="78" fill="url(#pgd)"/>
                <g transform="rotate(-14 200 190)">
                  <path d="M35 190 A165 50 0 0 0 365 190" fill="none" stroke="#F0A23B" stroke-width="2.4"/>
                  <circle class="rv" r="9" fill="#F0A23B" stroke="#FFE2B3" stroke-width="2" opacity="0">
                    <animateMotion dur="10s" repeatCount="indefinite" path="{orbit}"/>
                    <animate attributeName="opacity" values="0;1" keyTimes="0;0.5" calcMode="discrete" dur="10s" repeatCount="indefinite"/>
                  </circle>
                </g>
              </svg>
              <div class="pg-chip c1"><b>{ui.esc(kb)}</b>resolved tickets indexed</div>
              <div class="pg-chip c2"><b>{ui.esc(F['model'])}</b>{ui.esc(f1)}</div>
              <div class="pg-chip c3"><b>{ui.esc(algos)}</b>for priority prediction</div>
            </div>""",
            unsafe_allow_html=True,
        )

st.markdown('<div class="pg-sec"><h2>One workspace for support knowledge</h2>'
            '<p>Six connected modules, all working on the same tickets, documents and tasks.</p></div>',
            unsafe_allow_html=True)
MODULES = [
    ("space_dashboard", "Dashboard", "Open tickets, priority mix, overdue work and the latest activity in one view."),
    ("bolt", "Smart Triage", "Paste a ticket and get its priority from the trained model, with probabilities and the words that drove it."),
    ("forum", "AI Assistant", "Ask in plain language. Answers come from your documents and 9.5k past tickets, with sources."),
    ("library_books", "Knowledge Hub", "Upload PDFs, Word, text and CSV files, organise them into collections and search by meaning."),
    ("account_tree", "Automation", "Priority rules create tasks with deadlines, so high-priority tickets never wait."),
    ("insights", "Analytics", "Ticket trends, model agreement, SLA results and exportable reports."),
]
for row in (MODULES[:3], MODULES[3:]):
    cols = st.columns(3, gap="medium")
    for col, (ic, title, text) in zip(cols, row):
        col.markdown(f'<div class="pg-mod"><div class="ic">{ui.icon(ic)}</div><h3>{ui.esc(title)}</h3>'
                     f'<p>{ui.esc(text)}</p></div>', unsafe_allow_html=True)

st.markdown('<div class="pg-sec"><h2>How a ticket moves through PRAGYAAN</h2></div>', unsafe_allow_html=True)
STEPS = [
    ("Triage", "The Random Forest model scores the ticket low, medium or high and explains which words mattered."),
    ("Act", "Automation rules turn the priority into tasks with a deadline and an owner."),
    ("Answer", "The assistant looks for an answer in your documents and past tickets, and cites them."),
    ("Learn", "If nothing matches, a senior answers once and that answer is reused from then on."),
]
cols = st.columns(4, gap="medium")
for i, (col, (title, text)) in enumerate(zip(cols, STEPS), start=1):
    col.markdown(f'<div class="pg-step"><div class="n">{i}</div><div><h4>{ui.esc(title)}</h4>'
                 f'<p>{ui.esc(text)}</p></div></div>', unsafe_allow_html=True)

stats = []
if F["f1"]:
    stats.append((f"{F['f1']:.3f}", f"macro-F1 of the priority model, best of {F['n_algos']} algorithms tested"))
if F["hit5"]:
    stats.append((f"{F['hit5']:.0%}", "of test questions find a ticket from the right team in the top 5 results"))
if F["route"]:
    stats.append((f"{F['route']:.1f}%", "of test questions correctly answered or escalated"))
if stats:
    st.markdown('<div class="pg-sec"><h2>Measured, not assumed</h2>'
                '<p>Figures come from the evaluation files in eval/results.</p></div>', unsafe_allow_html=True)
    cols = st.columns(len(stats), gap="large")
    for col, (v, t) in zip(cols, stats):
        col.markdown(f'<div class="pg-stat"><b>{ui.esc(v)}</b><span>{ui.esc(t)}</span></div>', unsafe_allow_html=True)

st.markdown('<div class="pg-foot">PRAGYAAN, enterprise intelligence and knowledge automation. '
            'Runs on your own machine; tickets, documents and accounts stay in the project\'s data folder.</div>',
            unsafe_allow_html=True)
