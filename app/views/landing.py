"""Public landing page: an editorial poster for PRAGYAAN. Every number comes from the installed archive,
the configuration or the evaluation files; nothing is invented."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import auth_ui  # noqa: E402
import ui  # noqa: E402
from copilot.config import EVAL_RESULTS, SIM_THRESHOLD  # noqa: E402
from copilot.triage import archive_available, model_name  # noqa: E402

P = st.session_state.get("_pages", {})


@st.cache_data(ttl=300, show_spinner=False)
def facts() -> dict:
    """Every number on this page comes from the installed archive or the evaluation files."""
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


def go(name: str) -> None:
    if name in P:
        st.switch_page(P[name])


F = facts()
THR = round(SIM_THRESHOLD * 100)
auth_ui.theme()
st.markdown(
    """
<style>
[data-testid="stMainBlockContainer"] { max-width: 1320px; padding-top: 1.2rem !important; padding-bottom: 0 !important; }
section[data-testid="stMain"], main[data-testid="stMain"], [data-testid="stAppScrollToBottomContainer"] { overflow-x: hidden; }
/* navigation */
.lp-links { display: flex; justify-content: center; gap: .3rem; flex-wrap: wrap; }
.lp-links a { color: var(--ink) !important; text-decoration: none; font-weight: 650; font-size: .95rem; padding: .35rem .8rem; border-radius: 8px;
  border: 2px solid transparent; transition: border-color .2s ease, background .2s ease; }
.lp-links a:hover { border-color: var(--ink); background: var(--lime); }
@media (max-width: 900px) { .lp-links { display: none; } }
.st-key-lnav { flex-wrap: nowrap !important; }
/* hero */
.lp-hero { padding: 4.5rem 0 0; position: relative; }
.lp-hero h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 84%; font-size: clamp(3.4rem, 8.8vw, 8.6rem) !important;
  line-height: .9 !important; letter-spacing: -0.02em; margin: 0 !important; padding: 0 !important; max-width: 9.5ch; color: var(--ink); }
.lp-hero h1 .pg-w > span { animation-duration: .9s; animation-delay: calc(var(--i) * 90ms + 120ms); }
.lp-hero .lede { font-size: 1.22rem; line-height: 1.5; color: var(--ink-2); max-width: 46ch; margin: 1.8rem 0 1.6rem; animation: pg-fade-up .8s .7s var(--ease) both; }
.lp-hero .lede b { color: var(--ink); }
.st-key-lp-ctas { animation: pg-fade-up .8s .85s var(--ease) both; }
.st-key-lp-ctas button { min-height: 3.2rem !important; padding: 0 1.4rem !important; }
.st-key-lp-ctas button p { font-size: 1.02rem !important; }
.st-key-hero-emp [data-testid="stBaseButton-secondary"] { background: var(--lime) !important; }
/* the specimen: the similarity threshold as an object, with stickers dropped on it */
.lp-spec { position: relative; margin-top: 4.8rem; padding: 0 .6rem 2.4rem 1.2rem; }
.lp-slab { position: relative; background: var(--cobalt); color: var(--ivory); border: 2px solid var(--ink); border-radius: 22px; box-shadow: 10px 10px 0 var(--ink);
  padding: 2.4rem 1.8rem 1.8rem; transform: rotate(2deg); animation: pg-drop .9s .35s var(--ease) both; --rot: 2deg; }
.lp-slab .big { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: clamp(6rem, 11vw, 10rem); line-height: .8; letter-spacing: -0.03em; }
.lp-slab .cap { font-weight: 650; font-size: 1.05rem; margin: .6rem 0 1.6rem; max-width: 22ch; line-height: 1.3; }
.lp-ruler { position: relative; height: 30px; border: 2px solid var(--ink); border-radius: 6px; background:
  repeating-linear-gradient(90deg, transparent 0 calc(10% - 2px), var(--ink) calc(10% - 2px) 10%), var(--ivory); }
.lp-ruler span { position: absolute; inset: 0 auto 0 0; background: var(--lime); border-right: 2px solid var(--ink); transform-origin: left; animation: pg-grow 1.4s 1s var(--ease) both; }
.lp-ruler i { position: absolute; top: -10px; bottom: -10px; width: 5px; margin-left: -2.5px; background: var(--coral); border: 2px solid var(--ink); border-radius: 3px; }
.lp-ruler-l { display: flex; justify-content: space-between; font-size: .75rem; font-weight: 700; margin-top: .45rem; opacity: .85; }
.lp-spec .pg-sticker { position: absolute; z-index: 2; }
.lp-spec .s1 { top: -2.4rem; left: -.8rem; } .lp-spec .s2 { top: -1.6rem; right: -.6rem; } .lp-spec .s3 { bottom: .2rem; left: 1.6rem; }
/* full-bleed colour bands */
.lp-band { width: 100vw; margin-left: calc(50% - 50vw); padding: 5.5rem max(1.25rem, calc(50vw - 585px)); border-top: 2px solid var(--ink); border-bottom: 2px solid var(--ink); }
.lp-band.cobalt { background: var(--cobalt); color: var(--ivory); margin-top: 6rem; }
.lp-band.ink { background: var(--ink); color: var(--ivory); --curtain: var(--cobalt); }
.lp-band h2 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 84%; font-size: clamp(2.8rem, 6vw, 5.6rem) !important; line-height: .92 !important;
  letter-spacing: -0.02em; margin: 0 0 1rem !important; padding: 0 !important; color: inherit !important; max-width: 14ch; }
.lp-band > p { font-size: 1.1rem; line-height: 1.55; max-width: 52ch; margin: 0 0 3rem; opacity: .9; color: inherit; }
/* how a ticket moves: stations on a track; the ticket travels when the band scrolls into view */
.lp-track { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.2rem; position: relative; }
.lp-track::before { content: ""; position: absolute; left: 1.3rem; right: calc(25% - 1.3rem); top: 1.3rem; height: 4px; background: var(--ivory); border-radius: 2px; }
.lp-track .tk { position: absolute; top: .45rem; left: 0; width: 46px; height: 30px; border-radius: 6px; background: var(--lime); border: 2px solid var(--ink);
  box-shadow: 3px 3px 0 var(--ink); z-index: 2; display: grid; place-items: center; font-family: var(--display); font-weight: 800; color: var(--ink); font-size: .9rem; }
.pg-fx .lp-band:not(.in) .lp-track .tk { left: 2.9rem; }
.lp-band.in .lp-track .tk { animation: lp-travel 3.2s .3s var(--ease) both; }
@keyframes lp-travel { 0% { left: 2.9rem; } 26%, 36% { left: calc(25% + .3rem - 54px); } 62%, 72% { left: calc(50% + .6rem - 54px); } 100% { left: calc(75% + .9rem - 54px); } }
.lp-track .tk { left: calc(75% + .9rem - 54px); }
.lp-track li { position: relative; padding-top: 3.4rem; margin: 0 !important; color: var(--ivory); }
.lp-track li .n { position: absolute; top: 0; left: 0; width: 2.6rem; height: 2.6rem; border-radius: 50%; background: var(--ivory); color: var(--ink); border: 2px solid var(--ink);
  display: grid; place-items: center; font-family: var(--display); font-weight: 800; font-size: 1.15rem; }
.lp-track li h4 { font-family: var(--display) !important; font-weight: 750 !important; font-size: 1.45rem !important; line-height: 1.1; margin: 0 0 .45rem !important;
  padding: 0 !important; color: var(--ivory) !important; letter-spacing: -0.015em; }
.lp-track li p { font-size: .96rem; line-height: 1.5; margin: 0; opacity: .88; color: var(--ivory); }
.lp-track .fork { display: grid; gap: .7rem; }
.lp-track .fork div { border: 2px solid var(--ink); border-radius: 12px; padding: .75rem .9rem; box-shadow: 4px 4px 0 var(--ink); color: var(--ink); }
.lp-track .fork div b { display: block; font-family: var(--display); font-weight: 800; font-size: 1.15rem; margin-bottom: .2rem; }
.lp-track .fork div span { font-size: .88rem; line-height: 1.45; }
.lp-track .fork .yes { background: var(--lime); } .lp-track .fork .no { background: var(--coral); }
@media (max-width: 900px) { .lp-track { grid-template-columns: 1fr; } .lp-track::before, .lp-track .tk { display: none; } }
/* the two workspaces: slabs of different sizes that overlap */
.lp-sec-h { font-family: var(--display); font-weight: 800; font-stretch: 84%; font-size: clamp(2.8rem, 6vw, 5.6rem); line-height: .92; letter-spacing: -0.02em; margin: 6rem 0 2.2rem;
  max-width: 13ch; }
.st-key-card-lime-ws-emp, .st-key-card-ink-ws-ana { padding: 2.2rem 2.2rem 2rem !important; border-radius: 22px !important; box-shadow: 10px 10px 0 var(--ink); }
.st-key-card-ink-ws-ana { margin-top: 4.5rem; margin-left: -3.2rem; box-shadow: 10px 10px 0 var(--cobalt); z-index: 2; }
.lp-ws h3 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 80%; font-size: clamp(2.4rem, 4.4vw, 3.8rem) !important; line-height: .9 !important;
  letter-spacing: -0.03em; margin: 0 0 .8rem !important; padding: 0 !important; color: inherit !important; }
.lp-ws p { font-size: 1.04rem; line-height: 1.55; margin: 0 0 1.2rem !important; max-width: 46ch; color: inherit; }
.lp-ws ul { list-style: none; margin: 0 0 1.5rem; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: .55rem .9rem; }
.lp-ws li { display: flex; gap: .55rem; align-items: center; font-weight: 650; font-size: .95rem; margin: 0 !important; color: inherit; }
.lp-ws li .material-symbols-rounded { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; font-size: 17px; flex: none;
  background: var(--ink); color: var(--lime); }
.st-key-card-ink-ws-ana .lp-ws li .material-symbols-rounded { background: var(--lime); color: var(--ink); }
@media (max-width: 900px) { .st-key-card-ink-ws-ana { margin: 0; } .lp-ws ul { grid-template-columns: 1fr; } }
/* measured results: giant numbers that count up */
.lp-stats { display: grid; grid-template-columns: repeat(var(--n), 1fr); gap: 0; border-top: 2px solid rgba(244,238,225,.25); }
.lp-stats > div { padding: 1.8rem 1.6rem 0 0; border-right: 2px solid rgba(244,238,225,.25); margin-right: 1.6rem; }
.lp-stats > div:last-child { border-right: 0; }
.lp-stats b { display: block; font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: clamp(3.6rem, 7vw, 6.6rem); line-height: .85; color: var(--lime);
  letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.lp-stats > div > span { display: block; margin-top: .8rem; font-size: 1rem; line-height: 1.45; max-width: 30ch; opacity: .9; color: var(--ivory); }
@media (max-width: 900px) { .lp-stats { grid-template-columns: 1fr; } .lp-stats > div { border-right: 0; border-bottom: 2px solid rgba(244,238,225,.25); padding-bottom: 1.4rem; } }
.lp-end { display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 2rem 0 2.4rem; font-size: .88rem; color: var(--ink-2); font-weight: 550; }
.lp-end img { height: 56px; display: block; }
@media (max-width: 900px) { .lp-hero { padding-top: 2rem; } .lp-spec { margin-top: 2.6rem; padding-left: .4rem; } }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- navigation
with st.container(key="lnav", horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
    st.markdown('<img class="pg-logo" src="app/static/pragyaan-logo-full.png?v=red" alt="PRAGYAAN" height="84">', unsafe_allow_html=True,
                width="content")
    st.markdown('<div class="lp-links"><a href="#how">How a ticket moves</a><a href="#workspaces">Workspaces</a>'
                '<a href="#results">Results</a></div>', unsafe_allow_html=True, width="content")
    with st.container(horizontal=True, gap="small", width="content", vertical_alignment="center"):
        ui.theme_switch()
        if st.button("Sign in", key="hero-signin", type="primary", icon=":material/login:"):
            go("login")

# ---------------------------------------------------------------- hero: the headline, and the threshold as an object
kb_txt = f"{F['kb']:,}" if F["kb"] else "your"
h_l, h_r = st.columns([1.5, 1])
with h_l:
    st.markdown(
        f'<div class="lp-hero"><h1>{ui.words("Every ticket finds its answer.")}</h1>'
        f'<p class="lede">PRAGYAAN predicts how urgent each support ticket is, finds the fix among <b>{ui.esc(kb_txt)} '
        'solved tickets</b> and sends only what truly needs a person to a Senior Analyst.</p></div>',
        unsafe_allow_html=True,
    )
    with st.container(key="lp-ctas", horizontal=True, gap="small"):
        with st.container(key="hero-emp", width="content"):
            if st.button("Employee portal", key="hero-emp-btn", icon=":material/arrow_outward:", icon_position="right"):
                go("employee_login")
        if st.button("Senior Analyst portal", type="primary", key="hero-ana", icon=":material/arrow_outward:",
                     icon_position="right"):
            go("analyst_login")
with h_r:
    s1 = (ui.sticker(f'<b>{ui.esc(kb_txt)}</b>solved tickets to learn from', "lime", rot=-6, delay=.9).replace(
        'class="pg-sticker', 'class="s1 pg-sticker') if F["kb"] else "")
    s2 = (ui.sticker(f'<b>{F["f1"]:.3f}</b>macro-F1, priority model', "ink", rot=4, delay=1.15).replace(
        'class="pg-sticker', 'class="s2 pg-sticker') if F["f1"] else "")
    s3 = ui.sticker(f"Below {THR}%, a Senior Analyst takes it", "coral", rot=3, delay=1.35).replace(
        'class="pg-sticker', 'class="s3 pg-sticker')
    st.markdown(
        f'<div class="lp-spec">{s1}{s3}<div class="lp-slab"><div class="big">{THR}%</div>'
        f'<div class="cap">similar to a solved ticket, and the fix goes straight to the employee</div>'
        f'<div class="lp-ruler" role="img" aria-label="Similarity scale with the {THR}% threshold marked">'
        f'<span style="width:{THR}%"></span><i style="left:{THR}%"></i></div>'
        f'<div class="lp-ruler-l"><span>0%</span><span>similarity</span><span>100%</span></div></div>{s2}</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- how a ticket moves (a real sequence)
st.markdown(
    f"""<section class="lp-band cobalt pg-reveal" id="how"><h2>How a ticket moves</h2>
<p>The same steps for every ticket, in seconds. Most never need a Senior Analyst.</p>
<ol class="lp-track"><span class="tk" aria-hidden="true">#</span>
<li><span class="n">1</span><h4>Raised</h4><p>An employee describes the problem in their own words.</p></li>
<li><span class="n">2</span><h4>Priority predicted</h4><p>A trained Random Forest rates it low, medium or high, with its confidence and the words behind it.</p></li>
<li><span class="n">3</span><h4>Matched</h4><p>Similarity search compares it with {ui.esc(kb_txt)} solved tickets and the company's documents.</p></li>
<li><span class="n">4</span><div class="fork">
  <div class="yes"><b>{THR}% or more similar</b><span>The fix goes straight to the employee. If it works, they close the ticket.</span></div>
  <div class="no"><b>Below {THR}%, or the fix failed</b><span>Escalated to the Senior Analysts with its priority.</span></div></div></li>
</ol></section>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------- the two workspaces
st.markdown('<div class="lp-sec-h" id="workspaces">Two workspaces. One source of truth.</div>', unsafe_allow_html=True)
w1, w2 = st.columns([1.15, 1])
with w1:
    with st.container(key="card-lime-ws-emp"):
        st.markdown(
            f'<div class="lp-ws"><h3>Employees</h3><p>Raise a ticket, try the recommended fix and follow every step '
            f'until it\'s solved.</p><ul><li>{ui.icon("lightbulb")}Recommended fixes</li><li>{ui.icon("timeline")}Live progress</li>'
            f'<li>{ui.icon("forum")}AI assistant</li><li>{ui.icon("library_books")}Knowledge Hub</li></ul></div>',
            unsafe_allow_html=True)
        if st.button("Sign in as Employee", type="primary", key="ws-emp", icon=":material/arrow_forward:",
                     icon_position="right"):
            go("employee_login")
with w2:
    with st.container(key="card-ink-ws-ana"):
        st.markdown(
            f'<div class="lp-ws"><h3>Senior Analysts</h3><p>Work the escalations, assign the team and watch '
            f'priorities, self-service and model quality.</p><ul><li>{ui.icon("assignment_late")}Escalations</li>'
            f'<li>{ui.icon("groups")}Team and access</li><li>{ui.icon("insights")}Analytics</li>'
            f'<li>{ui.icon("leaderboard")}Benchmarks</li></ul></div>', unsafe_allow_html=True)
        if st.button("Sign in as Senior Analyst", type="primary", key="ws-ana", icon=":material/arrow_forward:",
                     icon_position="right"):
            go("analyst_login")

# ---------------------------------------------------------------- measured results (from eval/results)
stats = []
if F["f1"]:
    stats.append((ui.count(F["f1"], dec=3), f"macro-F1 of the priority model, the best of {F['n_algos']} algorithms tested"))
if F["hit5"]:
    stats.append((ui.count(F["hit5"] * 100, suffix="%"), "of test questions find a ticket from the right team in the top 5"))
if F["route"]:
    stats.append((ui.count(F["route"], dec=1, suffix="%"), "of test questions correctly answered or escalated"))
if stats:
    cells = "".join(f'<div><b>{v}</b><span>{ui.esc(t)}</span></div>' for v, t in stats)
    st.markdown(f'<section class="lp-band ink pg-reveal" id="results" style="margin-top:6rem"><h2>Measured, not assumed</h2>'
                f'<p>From the evaluation files shipped with this installation.</p>'
                f'<div class="lp-stats" style="--n:{len(stats)}">{cells}</div></section>', unsafe_allow_html=True)

st.markdown('<div class="lp-end"><img class="pg-logo" src="app/static/pragyaan-logo-full.png?v=red" alt="PRAGYAAN" height="56">'
            '<span>Runs on your own machine. Tickets, documents and accounts stay in the project\'s data folder.</span></div>',
            unsafe_allow_html=True)
