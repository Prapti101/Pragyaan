"""PRAGYAAN design system: tokens, global CSS, reusable components, chart styling.

Every page renders through these helpers so typography, spacing, colour and
states stay consistent. All dynamic text is HTML-escaped before it is placed
in custom markup.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

import altair as alt
import streamlit as st

# ---------------------------------------------------------------- tokens

INK = "#151A31"          # primary text
INK_2 = "#545B78"        # secondary text
MUTED = "#8A90A8"        # captions, axis labels
LINE = "#E2E5EF"         # hairlines
GRID = "#E9EBF2"
AXIS = "#C9CEDB"
SURFACE = "#FFFFFF"
NAVY = "#121A3A"         # sidebar / hero
PRIMARY = "#4257E0"
SAFFRON = "#F0A23B"      # brand accent, used sparingly
NEUTRAL_BAR = "#C9CEDB"

# Categorical chart series, fixed order (validated palette)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

# Status colours: meaning only, always shown with a text label
GOOD = "#0ca30c"
WARNING = "#fab219"
SERIOUS = "#ec835a"
CRITICAL = "#d03b3b"

PRIORITY_COLORS = {"high": "#D03B3B", "medium": "#E39A12", "low": "#2E8C7A"}
PRIORITY_ORDER = ["high", "medium", "low"]
STATUS_LABELS = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved", "closed": "Closed",
                 "todo": "To do", "done": "Done"}

# Severity routing bucket -> Streamlit badge colour + icon (Senior Queue)
BUCKET_BADGE = {
    "Urgent": ("red", ":material/priority_high:"),
    "Normal": ("orange", ":material/schedule:"),
    "Backlog": ("gray", ":material/inbox:"),
}

esc = html.escape

# ---------------------------------------------------------------- CSS

_CSS = f"""
<style>
:root {{
  --pg-ink: {INK}; --pg-ink-2: {INK_2}; --pg-muted: {MUTED}; --pg-line: {LINE};
  --pg-primary: {PRIMARY}; --pg-saffron: {SAFFRON}; --pg-navy: {NAVY};
  --pg-shadow: 0 1px 2px rgba(18,26,58,.05), 0 10px 28px -16px rgba(18,26,58,.22);
}}
.stApp {{
  background:
    radial-gradient(900px 420px at 92% -8%, rgba(66,87,224,.08), transparent 62%),
    radial-gradient(700px 360px at -10% 105%, rgba(240,162,59,.06), transparent 60%),
    #F5F6FA;
}}
[data-testid="stMainBlockContainer"] {{ padding-top: 1.4rem; padding-bottom: 4rem; max-width: 1320px; }}
h1, h2, h3, h4 {{ letter-spacing: -0.015em; }}
[data-testid="stMarkdownContainer"] p {{ max-width: 82ch; }}
[data-testid="stCaptionContainer"] p {{ color: var(--pg-ink-2); }}
[data-testid="stMetricValue"], .pg-num {{ font-variant-numeric: tabular-nums; }}

/* Cards: any container keyed card-* */
[class*="st-key-card"] {{
  background: {SURFACE}; border: 1px solid var(--pg-line) !important; border-radius: 14px !important;
  box-shadow: var(--pg-shadow); padding: 1.1rem 1.2rem 1.15rem !important;
}}
[class*="st-key-action"] button {{ transition: transform .14s ease, box-shadow .14s ease, border-color .14s ease; }}
[class*="st-key-action"] button:hover {{ transform: translateY(-2px); box-shadow: var(--pg-shadow); border-color: #C3CAE6; }}

/* Buttons */
[data-testid="stBaseButton-primary"] {{
  background: linear-gradient(135deg, #5468F0 0%, #3A4BD0 100%); border: 0;
  box-shadow: 0 6px 16px -8px rgba(58,75,208,.65); transition: filter .14s ease, transform .1s ease;
}}
[data-testid="stBaseButton-primary"]:hover {{ filter: brightness(1.08); }}
[data-testid="stBaseButton-primary"]:active {{ transform: scale(.98); }}
[data-testid="stBaseButton-secondary"] {{ background: #fff; }}

/* Sidebar */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #121A3A 0%, #0F1633 100%);
  border-right: 1px solid #1E2852;
}}
[data-testid="stSidebarNav"] a {{ border-radius: 8px; margin: 1px 0; }}
[data-testid="stSidebarNav"] a span {{ font-weight: 500; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  background: rgba(255,255,255,.07); box-shadow: inset 3px 0 0 var(--pg-saffron);
}}
[data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: #FFFFFF; }}
[data-testid="stNavSectionHeader"] {{ color: #7F88B3 !important; font-size: .75rem; letter-spacing: .02em; }}

/* Top bar */
.st-key-topbar {{ border-bottom: 1px solid var(--pg-line); padding-bottom: .55rem; margin-bottom: .4rem; }}

/* Page header */
.pg-head {{ margin: .25rem 0 1.1rem; }}
.pg-head h1 {{ font-family: Sora, 'IBM Plex Sans', sans-serif; font-size: 1.9rem; font-weight: 700; margin: 0; color: var(--pg-ink); padding: 0; }}
.pg-head p {{ margin: .3rem 0 0; color: var(--pg-ink-2); font-size: .98rem; max-width: 74ch; }}

/* KPI */
.pg-kpi {{ background: #fff; border: 1px solid var(--pg-line); border-radius: 14px; padding: 1rem 1.1rem;
           box-shadow: var(--pg-shadow); height: 100%; position: relative; overflow: hidden; }}
.pg-kpi .l {{ color: var(--pg-ink-2); font-size: .85rem; font-weight: 500; display: flex; gap: .4rem; align-items: center; }}
.pg-kpi .v {{ font-family: Sora, 'IBM Plex Sans', sans-serif; font-size: 1.9rem; font-weight: 600; color: var(--pg-ink);
              margin-top: .35rem; line-height: 1.1; font-variant-numeric: tabular-nums; }}
.pg-kpi .n {{ color: var(--pg-muted); font-size: .8rem; margin-top: .35rem; }}
.pg-kpi.accent::before {{ content: ""; position: absolute; inset: 0 auto 0 0; width: 3px; background: var(--pg-tone, var(--pg-primary)); }}
.pg-kpi .material-symbols-rounded {{ font-size: 18px; }}

/* Badges */
.pg-badge {{ display: inline-flex; align-items: center; gap: .35rem; padding: .12rem .55rem .14rem; border-radius: 999px;
             font-size: .78rem; font-weight: 600; line-height: 1.4; white-space: nowrap; border: 1px solid transparent; }}
.pg-badge i {{ width: .5rem; height: .5rem; border-radius: 50%; display: inline-block; }}
.pg-prio-high {{ background: #FCEBEB; color: #A82B2B; border-color: #F5CFCF; }} .pg-prio-high i {{ background: {PRIORITY_COLORS['high']}; }}
.pg-prio-medium {{ background: #FDF3E1; color: #8A5A05; border-color: #F6DFB3; }} .pg-prio-medium i {{ background: {PRIORITY_COLORS['medium']}; }}
.pg-prio-low {{ background: #E6F4F1; color: #1F6658; border-color: #C5E5DE; }} .pg-prio-low i {{ background: {PRIORITY_COLORS['low']}; }}
.pg-soft {{ background: #EEF0F7; color: var(--pg-ink-2); border-color: #E2E5EF; }}

/* Empty / error states */
.pg-empty {{ border: 1.5px dashed #D5DAEA; border-radius: 14px; padding: 1.6rem 1.4rem; text-align: center; background: rgba(255,255,255,.6); }}
.pg-empty .ico {{ width: 46px; height: 46px; border-radius: 12px; margin: 0 auto .7rem; display: grid; place-items: center;
                  background: linear-gradient(135deg, rgba(66,87,224,.12), rgba(240,162,59,.14)); color: var(--pg-primary); }}
.pg-empty h4 {{ margin: 0; font-size: 1rem; color: var(--pg-ink); }}
.pg-empty p {{ margin: .3rem auto 0; color: var(--pg-ink-2); font-size: .9rem; max-width: 52ch; }}

/* Activity feed */
.pg-feed {{ list-style: none; margin: 0; padding: 0; }}
.pg-feed li {{ display: grid; grid-template-columns: 30px 1fr auto; gap: .65rem; align-items: start; padding: .55rem 0; border-bottom: 1px solid #EEF0F6; }}
.pg-feed li:last-child {{ border-bottom: 0; }}
.pg-feed .dot {{ width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center; background: #EEF0FA; color: var(--pg-primary); }}
.pg-feed .dot .material-symbols-rounded {{ font-size: 17px; }}
.pg-feed .m {{ font-size: .9rem; color: var(--pg-ink); line-height: 1.4; }}
.pg-feed .t {{ font-size: .78rem; color: var(--pg-muted); white-space: nowrap; }}

/* Probability meter (triage signature) */
.pg-meter {{ display: flex; height: 12px; border-radius: 999px; overflow: hidden; background: #EEF0F6; gap: 2px; }}
.pg-meter span {{ display: block; height: 100%; transition: width .6s cubic-bezier(.2,.8,.2,1); }}
.pg-meter-legend {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .5rem; font-size: .82rem; color: var(--pg-ink-2); }}
.pg-meter-legend b {{ color: var(--pg-ink); font-weight: 600; }}
.pg-meter-legend i {{ display: inline-block; width: .55rem; height: .55rem; border-radius: 2px; margin-right: .3rem; }}

.material-symbols-rounded {{
  font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; font-size: 20px; line-height: 1;
  letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; direction: ltr;
  font-feature-settings: 'liga'; -webkit-font-smoothing: antialiased; vertical-align: middle;
}}
.pg-muted {{ color: var(--pg-ink-2); font-size: .88rem; }}
.pg-kbd {{ font-size: .75rem; padding: .05rem .35rem; border: 1px solid var(--pg-line); border-radius: 5px; background: #fff; }}

/* Ticket progress stepper */
.pg-steps {{ display: flex; gap: 0; margin: .4rem 0 .2rem; flex-wrap: wrap; }}
.pg-step {{ flex: 1 1 0; min-width: 92px; position: relative; padding-top: 22px; font-size: .78rem; color: var(--pg-muted); text-align: center; }}
.pg-step::before {{ content: ""; position: absolute; top: 7px; left: 0; right: 0; height: 2px; background: #E2E5EF; }}
.pg-step:first-child::before {{ left: 50%; }} .pg-step:last-child::before {{ right: 50%; }}
.pg-step i {{ position: absolute; top: 0; left: 50%; transform: translateX(-50%); width: 16px; height: 16px; border-radius: 50%;
             background: #fff; border: 2px solid #CDD2E3; box-sizing: border-box; }}
.pg-step.done {{ color: var(--pg-ink-2); }} .pg-step.done::before {{ background: #8FA0F0; }}
.pg-step.done i {{ background: var(--pg-primary); border-color: var(--pg-primary); }}
.pg-step.now {{ color: var(--pg-ink); font-weight: 600; }}
.pg-step.now i {{ background: #fff; border: 4px solid var(--pg-primary); box-shadow: 0 0 0 4px rgba(66,87,224,.15); }}
.pg-stage {{ display: inline-flex; align-items: center; gap: .35rem; padding: .12rem .55rem .14rem; border-radius: 999px; font-size: .78rem;
            font-weight: 600; line-height: 1.4; white-space: nowrap; background: color-mix(in srgb, var(--st) 12%, #fff);
            color: color-mix(in srgb, var(--st) 80%, #151A31); border: 1px solid color-mix(in srgb, var(--st) 28%, #fff); }}
.pg-stage i {{ width: .5rem; height: .5rem; border-radius: 50%; background: var(--st); display: inline-block; }}
.pg-solution {{ background: linear-gradient(180deg, #F7F8FF, #FFFFFF); border: 1px solid #DDE2FA; border-left: 3px solid var(--pg-primary);
               border-radius: 10px; padding: .75rem .9rem; font-size: .92rem; color: var(--pg-ink); white-space: pre-wrap; }}
.pg-role {{ display: inline-flex; align-items: center; gap: .3rem; padding: .1rem .5rem; border-radius: 999px; font-size: .74rem; font-weight: 600;
           background: #EEF0FF; color: #3446C8; border: 1px solid #D9DEFB; }}
.pg-role.analyst {{ background: #F3EEFF; color: #6D28D9; border-color: #E4D8FE; }}

@keyframes pg-rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
@keyframes pg-orbit {{ to {{ transform: rotate(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation: none !important; transition: none !important; }} }}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def setup_page(title: str, icon: str) -> None:
    """Kept for compatibility: pages run inside the router, which sets config and CSS."""
    return None


# ---------------------------------------------------------------- components

def clip(text: str | None, n: int) -> str:
    """Shorten at a word boundary with an ellipsis."""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(",.;:")
    return cut + "\u2026"


def md_lines(text: str | None) -> str:
    """Keep single line breaks when rendering plain text as Markdown."""
    return (text or "").replace("\r", "").replace("\n", "  \n")


def icon(name: str) -> str:
    return f'<span class="material-symbols-rounded" aria-hidden="true">{esc(name)}</span>'


def page_header(title: str, subtitle: str | None = None) -> None:
    sub = f"<p>{esc(subtitle)}</p>" if subtitle else ""
    st.markdown(f'<div class="pg-head"><h1>{esc(title)}</h1>{sub}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, note: str | None = None, *, icon_name: str | None = None,
        tone: str | None = None) -> None:
    ic = icon(icon_name) if icon_name else ""
    nt = f'<div class="n">{esc(note)}</div>' if note else ""
    style = f' style="--pg-tone:{tone}"' if tone else ""
    cls = "pg-kpi accent" if tone else "pg-kpi"
    st.markdown(f'<div class="{cls}"{style}><div class="l">{ic}{esc(label)}</div>'
                f'<div class="v">{esc(value)}</div>{nt}</div>', unsafe_allow_html=True)


def priority_badge(p: str | None, prefix: str = "") -> str:
    p = (p or "").lower()
    if p not in PRIORITY_COLORS:
        return '<span class="pg-badge pg-soft">Unscored</span>'
    return f'<span class="pg-badge pg-prio-{p}"><i></i>{esc(prefix)}{p.capitalize()}</span>'


def soft_badge(text: str) -> str:
    return f'<span class="pg-badge pg-soft">{esc(text)}</span>'


def empty_state(icon_name: str, title: str, text: str) -> None:
    st.markdown(f'<div class="pg-empty"><div class="ico">{icon(icon_name)}</div><h4>{esc(title)}</h4>'
                f'<p>{esc(text)}</p></div>', unsafe_allow_html=True)


def prob_meter(probs: dict[str, float], predicted: str) -> str:
    segs = "".join(
        f'<span title="{p}: {probs.get(p, 0):.0%}" style="width:{max(probs.get(p, 0) * 100, 0.5):.1f}%;'
        f'background:{PRIORITY_COLORS[p]};opacity:{1 if p == predicted else .35}"></span>'
        for p in ("low", "medium", "high")
    )
    legend = "".join(
        f'<span><i style="background:{PRIORITY_COLORS[p]};opacity:{1 if p == predicted else .45}"></i>'
        f'{p.capitalize()} {"<b>" if p == predicted else ""}{probs.get(p, 0):.0%}{"</b>" if p == predicted else ""}</span>'
        for p in ("low", "medium", "high")
    )
    return f'<div class="pg-meter" role="img" aria-label="Priority probabilities">{segs}</div><div class="pg-meter-legend">{legend}</div>'


_FEED_ICONS = {"ticket": "confirmation_number", "correction": "edit", "task": "task_alt", "document": "description",
               "escalation": "support_agent", "rule": "bolt", "import": "download", "login": "login",
               "account": "manage_accounts"}


def activity_feed(items: list[dict]) -> None:
    lis = "".join(
        f'<li><span class="dot">{icon(_FEED_ICONS.get(a["kind"], "circle"))}</span>'
        f'<span class="m">{esc(a["message"])}</span><span class="t">{esc(ago(a["created_at"]))}</span></li>'
        for a in items
    )
    st.markdown(f'<ul class="pg-feed">{lis}</ul>', unsafe_allow_html=True)


# ---------------------------------------------------------------- time

def _parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "")).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def local_time(s: str | None, fmt: str = "%d %b, %H:%M") -> str:
    d = _parse_utc(s)
    return d.astimezone().strftime(fmt) if d else ""


def ago(s: str | None) -> str:
    d = _parse_utc(s)
    if not d:
        return ""
    secs = (datetime.now(timezone.utc) - d).total_seconds()
    if secs < 0:
        mins = int(-secs // 60)
        return f"in {mins} min" if mins < 60 else (f"in {mins // 60} h" if mins < 2880 else f"in {mins // 1440} d")
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return local_time(s, "%d %b")


# ---------------------------------------------------------------- charts

def style_chart(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """Recessive axes and hairline grid, theme font."""
    return (
        chart.configure(font="IBM Plex Sans", background="transparent")
        .configure_view(stroke=None)
        .configure_axis(labelColor=INK_2, titleColor=INK_2, labelFontSize=12, titleFontSize=12,
                        titleFontWeight=500, gridColor=GRID, domainColor=AXIS, tickColor=AXIS)
        .configure_legend(orient="top", title=None, labelColor=INK, labelFontSize=12, labelLimit=320, symbolSize=120)
        .configure_title(color=INK, fontSize=13, fontWeight=600, anchor="start", font="IBM Plex Sans")
    )


def show_chart(chart: alt.TopLevelMixin) -> None:
    st.altair_chart(style_chart(chart), width="stretch", theme=None)


def current_user() -> dict:
    return st.session_state.get("user") or {}


def require_role(*roles: str) -> dict:
    """Server-side page guard. Re-reads the signed-in account from the database and stops the
    page unless it is active and has one of `roles`, so typing an analyst URL as an employee
    (or using a stale session after a role change) shows an access-denied screen instead."""
    from copilot.auth import ROLE_LABELS, get_account

    u = st.session_state.get("user") or {}
    acct = get_account(int(u["id"])) if u.get("id") else None
    if not acct or not acct["is_active"] or acct["role"] not in roles:
        page_header("Access restricted")
        need = " or ".join(ROLE_LABELS.get(r, r) for r in roles)
        empty_state("lock", "You don't have access to this page",
                    f"This area is available to {need} accounts. Use the navigation to go back to your workspace.")
        st.stop()
    return acct


def has_page(name: str) -> bool:
    return name in (st.session_state.get("_pages") or {})


def go(name: str) -> None:
    """Switch to a page if the signed-in role has it."""
    pages = st.session_state.get("_pages") or {}
    if name in pages:
        st.switch_page(pages[name])


STAGE_COLORS = {"suggested": "#7C3AED", "escalated": "#D03B3B", "assigned": "#2a78d6", "in_progress": "#E39A12",
                "resolved": "#0ca30c", "closed": "#8A90A8"}
STAGE_LABELS = {"suggested": "Solution suggested", "escalated": "Escalated", "assigned": "Assigned",
                "in_progress": "In progress", "resolved": "Resolved", "closed": "Closed"}


def stage_badge(stage: str) -> str:
    return (f'<span class="pg-stage" style="--st:{STAGE_COLORS.get(stage, MUTED)}"><i></i>'
            f'{esc(STAGE_LABELS.get(stage, stage))}</span>')


def role_badge(role: str) -> str:
    label = "Senior Analyst" if role == "analyst" else "Employee"
    return f'<span class="pg-role {esc(role)}">{esc(label)}</span>'


def progress_steps(t: dict) -> str:
    """Where a ticket is. Self-service path: Submitted -> Solution suggested -> Closed.
    Escalated path: Submitted -> Escalated -> Being handled -> Resolved -> Closed."""
    stage, rs = t.get("stage"), t.get("review_status")
    if rs in ("suggested", "pending", "self_resolved"):
        steps = [("Submitted", True), ("Solution suggested", True),
                 ("Solved by you" if rs == "self_resolved" else "Closed", stage == "closed")]
    else:
        steps = [("Submitted", True), ("Solution found" if rs == "approved" else "Escalated", True),
                 ("Assigned" if t.get("assignee_account_id") else "Being handled",
                  stage in ("assigned", "in_progress", "resolved", "closed")),
                 ("Resolved", stage in ("resolved", "closed")), ("Closed", stage == "closed")]
    now = max(i for i, (_, done) in enumerate(steps) if done)
    out = []
    for i, (label, done) in enumerate(steps):
        cls = "now" if i == now else ("done" if done else "")
        out.append(f'<div class="pg-step {cls}"><i></i>{esc(label)}</div>')
    return f'<div class="pg-steps" role="list" aria-label="Ticket progress">{"".join(out)}</div>'


def solution_cards(res: dict, key: str, pick_label: str | None = None) -> tuple[int, dict | None]:
    """Render existing solution recommendations from triage.find_solutions.

    With `pick_label`, each recommendation gets a button (e.g. "This solved my problem"); the
    clicked recommendation is returned so the page can close the issue as self-resolved.
    Returns (number shown, picked recommendation or None)."""
    for err in res.get("errors") or []:
        st.caption(err)
    n, picked = 0, None
    for h in res.get("tickets") or []:
        n += 1
        tag = "Strong match" if h["strong"] else "Possible match"
        st.markdown(
            f"{soft_badge(tag)} &nbsp;<span class='pg-muted'>Resolved ticket #{h['ticket_id']} · "
            f"similarity {h['similarity']:.0%}</span>", unsafe_allow_html=True)
        st.caption(clip(h["snippet"], 160))
        st.markdown(f'<div class="pg-solution">{esc(clip(h["answer"], 700))}</div>', unsafe_allow_html=True)
        if pick_label and st.button(pick_label, key=f"{key}-pick-t-{h['ticket_id']}", icon=":material/check_circle:",
                                    type="secondary"):
            picked = h
        st.write("")
    for i, d in enumerate(res.get("documents") or []):
        n += 1
        a, b = st.columns([5, 1.2], vertical_alignment="center")
        a.markdown(f"{soft_badge('Knowledge Hub')} &nbsp;**{esc(d['title'])}** "
                   f"<span class='pg-muted'>· similarity {d['similarity']:.0%}</span>", unsafe_allow_html=True)
        a.caption(clip(d["text"], 260))
        if has_page("knowledge") and b.button("Open", key=f"{key}-doc-{i}-{d['doc_id']}", type="tertiary"):
            st.session_state["kh_open"] = d["doc_id"]
            go("knowledge")
        if pick_label and st.button(pick_label, key=f"{key}-pick-d-{i}-{d['doc_id']}", icon=":material/check_circle:"):
            picked = d
    return n, picked
