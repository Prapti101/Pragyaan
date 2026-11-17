"""PRAGYAAN design system: tokens, global CSS, reusable components, chart styling.

"Ink & Signal": experimental editorial meets neo-brutalism. Warm ivory paper, deep ink, electric
cobalt, acid lime and vivid coral; oversized Bricolage Grotesque headlines over Instrument Sans text;
thick ink edges with hard offset shadows that press in when clicked. Tickets are drawn as physical
ticket stubs, similarity as a ruler with the threshold notched in, priority as colour blocks.

Every page renders through these helpers so typography, spacing, colour and states stay consistent.
All dynamic text is HTML-escaped before it is placed in custom markup.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import altair as alt
import streamlit as st

# ---------------------------------------------------------------- tokens

INK_BLACK = "#0A0C1B"     # deep ink
IVORY = "#F4EEE1"         # warm ivory paper
IVORY_2 = "#EBE3D1"       # deeper paper (wells, inputs, table headers)
PAPER = "#FFFDF6"         # panel surface
COBALT = "#2340FF"        # electric cobalt
LIME = "#D4FF3A"          # acid lime
CORAL = "#FF5C47"         # vivid coral

INK = INK_BLACK           # primary text
INK_2 = "#4A4D5E"         # secondary text (7:1 on ivory)
MUTED = "#686B7A"         # captions, axis labels (4.6:1 on ivory)
LINE = "rgba(10,12,27,0.14)"
GRID = "rgba(10,12,27,0.09)"
AXIS = INK_BLACK
SURFACE = INK_BLACK       # bar outlines in charts: every mark gets an ink edge
NAVY = INK_BLACK
PRIMARY = COBALT
ICE = COBALT
VIOLET = COBALT
CYAN = COBALT
SAFFRON = "#F2A100"
NEUTRAL_BAR = "#CFC5AE"

# Categorical chart series on ivory, fixed order (cobalt, coral, ink, olive, periwinkle, rust, slate, lime)
SERIES = ["#2340FF", "#FF5C47", "#0A0C1B", "#8FA60F", "#7C8BFF", "#C2410C", "#5B5E70", "#B8E62E"]

# Status colours: meaning only, always shown with a text label
GOOD = "#4D7A00"
WARNING = "#F2A100"
SERIOUS = "#FF8A3D"
CRITICAL = "#E8432E"

# Priority = colour blocks (every mark carries an ink edge and a text label, so colour never works alone)
PRIORITY_COLORS = {"high": CORAL, "medium": LIME, "low": COBALT}
PRIORITY_TEXT = {"high": INK_BLACK, "medium": INK_BLACK, "low": IVORY}
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


def on_color(hex_color: str) -> str:
    """Ink or ivory text, whichever reads better on `hex_color` (WCAG relative luminance)."""
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return INK_BLACK
    def ch(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    lum = 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    return INK_BLACK if (lum + 0.05) / 0.0537 >= 0.90 / (lum + 0.05) else IVORY

# ---------------------------------------------------------------- CSS

_CSS = """
<style>
@font-face { font-family: "Bricolage Grotesque"; src: url("app/static/fonts/bricolage-grotesque-latin-var.woff2") format("woff2");
  font-weight: 200 800; font-stretch: 75% 100%; font-display: swap; }
@font-face { font-family: "Instrument Sans"; src: url("app/static/fonts/instrument-sans-latin-var.woff2") format("woff2");
  font-weight: 400 700; font-stretch: 75% 100%; font-display: swap; }
:root {
  --ink: #0A0C1B; --ink-2: #4A4D5E; --muted: #686B7A; --line: rgba(10,12,27,.14);
  --ivory: #F4EEE1; --ivory-2: #EBE3D1; --paper: #FFFDF6;
  --cobalt: #2340FF; --cobalt-2: #E1E6FF; --lime: #D4FF3A; --coral: #FF5C47; --coral-2: #FFE1DC;
  --display: "Bricolage Grotesque", "Instrument Sans", system-ui, sans-serif;
  --text: "Instrument Sans", system-ui, sans-serif;
  --edge: 2px solid var(--ink); --r: 14px; --r-sm: 10px;
  --hard: 5px 5px 0 var(--ink); --hard-sm: 3px 3px 0 var(--ink);
  --gap: 1.4rem; --pad: 1.35rem;
  --ease: cubic-bezier(.2,.8,.2,1);
  /* old names, kept for page-level inline styles */
  --pg-ink: var(--ink); --pg-ink-2: var(--ink-2); --pg-muted: var(--muted); --pg-line: var(--line); --pg-primary: var(--cobalt);
}
html, body, .stApp { font-family: var(--text); }
.stApp { color: var(--ink); background-color: var(--ivory) !important;
  /* paper: a very faint dot grid, like engineering notebook stock */
  background-image: radial-gradient(rgba(10,12,27,.075) 1px, transparent 1.2px) !important; background-size: 22px 22px !important; }
header[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stMainBlockContainer"] { padding-top: 1rem; padding-bottom: 7.5rem; max-width: 1380px; position: relative; z-index: 1; }

/* ---- layout system: one gap for every row and column, cards in a row share one height */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] { gap: var(--gap); }
[data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) { column-gap: var(--gap); row-gap: var(--gap); }
@media (min-width: 641px) { [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) { flex-wrap: nowrap; } }
[data-testid="stMarkdownContainer"]:has(> :is(div:not([data-testid]), ul[class], ol[class], img, svg):last-child) { margin-bottom: 0; }
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > style:only-child),
[data-testid="stElementContainer"]:has(.pg-js), [data-testid="stElementContainer"]:has(.pg-auth-bg) { position: absolute !important; }
[data-testid="stColumn"] { display: flex; flex-direction: column; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] { flex: 1 1 auto; }
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(> :is([class*="st-key-card"], [class*="st-key-art-"],
  [class*="st-key-portal-"], .st-key-auth-card, .st-key-auth-panel):not([class*="st-key-card-fit"])) { flex: 1 1 auto; }
[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(.pg-fill),
[data-testid="stElementContainer"]:has(.pg-fill) div:has(.pg-fill) { display: flex; flex-direction: column; flex: 1 1 auto; }
.pg-fill { flex: 1 1 auto; box-sizing: border-box; }
[data-testid="stMarkdownContainer"] :is(ul, ol)[class] > li, [data-testid="stMarkdownContainer"] div[class] :is(ul, ol) > li { margin-left: 0 !important; margin-right: 0 !important; }
:is([class*="st-key-card"], [class*="st-key-art-"], [class*="st-key-portal-"]) > [data-testid="stElementContainer"]:last-child:has(:is([data-testid="stButton"], [data-testid="stDownloadButton"])),
:is([class*="st-key-card"], [class*="st-key-art-"]) > [data-testid="stLayoutWrapper"]:last-child:has(> [class*="st-key-actions"]) { margin-top: auto; }
[class*="st-key-actions"] { gap: .7rem !important; }
[data-testid="stColumn"]:last-child:not(:first-child) > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:only-child:has([data-testid="stBaseButton-tertiary"]) { align-self: flex-end; }

/* ---- type */
h1, h2, h3, h4, h5, h6 { font-family: var(--display) !important; color: var(--ink); letter-spacing: -0.025em; }
h1 { font-stretch: 85%; line-height: .95 !important; }
h4, h5, h6 { font-weight: 700 !important; }
[data-testid="stMarkdownContainer"] p { max-width: 78ch; }
[data-testid="stMarkdownContainer"] { color: var(--ink); }
[data-testid="stCaptionContainer"] p, [data-testid="stCaptionContainer"] { color: var(--ink-2) !important; }
[data-testid="stMetricValue"], .pg-num { font-variant-numeric: tabular-nums; }
[data-testid="stMetricValue"] { font-family: var(--display); font-weight: 800; font-stretch: 75%; letter-spacing: -0.02em; color: var(--ink); }
[data-testid="stMetricLabel"] p { color: var(--ink-2) !important; font-weight: 600; }
a { color: var(--cobalt); text-decoration-thickness: 2px; text-underline-offset: 3px; }
::selection { background: var(--lime); color: var(--ink); }
:focus-visible { outline: 3px solid var(--cobalt) !important; outline-offset: 2px !important; }

/* ---- motion: one orchestrated entrance per page (headline words rise out of a mask), plus reveals */
@keyframes pg-rise-mask { from { transform: translateY(105%); } to { transform: none; } }
@keyframes pg-drop { 0% { opacity: 0; transform: translateY(-26px) rotate(var(--rot, -4deg)) scale(1.06); } 70% { opacity: 1; transform: translateY(3px) rotate(var(--rot, -4deg)); }
  100% { opacity: 1; transform: rotate(var(--rot, -4deg)); } }
@keyframes pg-fade-up { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: none; } }
@keyframes pg-grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes pg-pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(212,255,58,.0), var(--hard-sm); } 50% { box-shadow: 0 0 0 6px rgba(212,255,58,.55), var(--hard-sm); } }
@keyframes pg-march { to { background-position: 28px 0; } }
.pg-w { display: inline-block; overflow: hidden; vertical-align: bottom; padding-bottom: .06em; margin-bottom: -.06em; }
.pg-w > span { display: inline-block; animation: pg-rise-mask .7s var(--ease) both; animation-delay: calc(var(--i, 0) * 55ms + 80ms); }
/* scroll reveal: a colour curtain retracts sideways when the block scrolls into view (only once the script is running) */
.pg-reveal { position: relative; }
.pg-fx .pg-reveal::after { content: ""; position: absolute; inset: -2px 0; z-index: 5; pointer-events: none; background: var(--curtain, var(--lime));
  transform-origin: right center; transition: transform 1s cubic-bezier(.77, 0, .18, 1); }
.pg-fx .pg-reveal.in::after { transform: scaleX(0); }

/* ---- panels: any container keyed card-* is a paper slab with an ink edge and a hard shadow.
   Variants by key: card-ink-*, card-cobalt-*, card-lime-*, card-coral-*, card-well-* (and the same after card-fit-) */
[class*="st-key-card"], [class*="st-key-art-"] {
  background: var(--paper); border: var(--edge) !important; border-radius: var(--r) !important; box-shadow: var(--hard);
  padding: var(--pad) !important; position: relative; animation: pg-fade-up .55s var(--ease) both; }
:is([class*="st-key-card"], [class*="st-key-art-"]) h5 { font-weight: 750 !important; font-size: 1.12rem; padding-top: 0 !important; line-height: 1.2; }
:is([class*="st-key-card"], [class*="st-key-art-"]) h4 { padding-top: 0 !important; line-height: 1.15; }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"]) { background: var(--ink); color: var(--ivory); box-shadow: 5px 5px 0 var(--cobalt); }
:is([class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"]) { background: var(--cobalt); color: var(--ivory); }
:is([class*="st-key-card-lime-"], [class*="st-key-card-fit-lime-"]) { background: var(--lime); }
:is([class*="st-key-card-coral-"], [class*="st-key-card-fit-coral-"]) { background: var(--coral); }
:is([class*="st-key-card-well-"], [class*="st-key-card-fit-well-"]) { background: var(--ivory-2); box-shadow: none; }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"])
  :is(h1, h2, h3, h4, h5, h6, p, li, span, label, [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] p) { color: var(--ivory); }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"]) .pg-muted { color: rgba(244,238,225,.72) !important; }
/* inside dark slabs the primary button flips to lime */
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"])
  :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) { background: var(--lime) !important; color: var(--ink) !important; box-shadow: 3px 3px 0 var(--ivory) !important; border-color: var(--ink) !important; }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"])
  :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) p { color: var(--ink) !important; }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"])
  [data-testid="stBaseButton-tertiary"] p { color: var(--lime) !important; }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"])
  [data-testid="stBaseButton-secondary"] { box-shadow: 3px 3px 0 var(--ivory) !important; }

/* ---- buttons: ink edges and hard shadows; they lean toward the pointer (magnetic) and press flat when clicked */
[data-testid^="stBaseButton-"]:not([data-testid*="tertiary"]):not([data-testid*="segmented"]):not([data-testid*="pills"]):not([data-testid="stBaseButton-headerNoPadding"]):not([data-testid="stBaseButton-header"]):not([data-testid="stBaseButton-minimal"]):not([data-testid="stBaseButton-borderlessIcon"]),
[data-testid="stPopoverButton"] {
  border: var(--edge) !important; border-radius: var(--r-sm) !important; font-weight: 600 !important; min-height: 2.65rem;
  box-shadow: var(--hard-sm) !important; transform: translate(var(--mx, 0px), var(--my, 0px));
  transition: transform .18s var(--ease), box-shadow .18s var(--ease), background-color .18s ease !important; }
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) { background: var(--ink) !important; color: var(--lime) !important; box-shadow: 3px 3px 0 var(--cobalt) !important; }
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) p { color: var(--lime) !important; font-weight: 650 !important; }
:is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stPopoverButton"]) { background: var(--paper) !important; color: var(--ink) !important; }
:is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stPopoverButton"]) p { color: var(--ink) !important; }
[data-testid^="stBaseButton-"]:not([data-testid*="tertiary"]):not([data-testid*="segmented"]):not([data-testid*="pills"]):hover,
[data-testid="stPopoverButton"]:hover { transform: translate(calc(var(--mx, 0px) - 1px), calc(var(--my, 0px) - 1px)); }
:is([data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stPopoverButton"]):hover { background: var(--lime) !important; box-shadow: 4px 4px 0 var(--ink) !important; }
:is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]):hover { box-shadow: 5px 5px 0 var(--cobalt) !important; }
[data-testid^="stBaseButton-"]:not([data-testid*="tertiary"]):not([data-testid*="segmented"]):not([data-testid*="pills"]):active,
[data-testid="stPopoverButton"]:active { transform: translate(3px, 3px) !important; box-shadow: 0 0 0 var(--ink) !important; }
[data-testid="stBaseButton-tertiary"] { color: var(--ink) !important; font-weight: 600 !important; border-radius: 6px !important;
  background: linear-gradient(var(--lime), var(--lime)) no-repeat 0 100% / 0 38% !important; transition: background-size .25s var(--ease) !important; }
[data-testid="stBaseButton-tertiary"] p { color: inherit !important; font-weight: 600 !important; }
[data-testid="stBaseButton-tertiary"]:hover { background-size: 100% 38% !important; color: var(--ink) !important; }
button:disabled { opacity: .45 !important; box-shadow: none !important; transform: none !important; }

/* ---- inputs */
[data-testid="stTextInputRootElement"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-testid="stNumberInputContainer"], [data-testid="stDateInputField"] {
  background: var(--paper) !important; border: var(--edge) !important; border-radius: var(--r-sm) !important; transition: box-shadow .15s ease, border-color .15s ease; }
[data-testid="stTextInputRootElement"] > div, [data-baseweb="base-input"], [data-baseweb="textarea"] textarea, [data-baseweb="input"] { background: transparent !important; }
[data-testid="stTextInputRootElement"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-testid="stNumberInputContainer"]:focus-within {
  border-color: var(--cobalt) !important; box-shadow: 0 0 0 4px var(--lime) !important; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { font-weight: 650 !important; color: var(--ink) !important; font-size: .9rem !important; }
input::placeholder, textarea::placeholder { color: #7D7F8C !important; opacity: 1; }

/* ---- tabs, segmented controls, pills: ink chips */
[data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] { gap: .5rem; border-bottom: 0 !important; flex-wrap: wrap; box-shadow: none !important; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"], [data-testid="stTabs"] .react-aria-SelectionIndicator { display: none !important; }
:is([data-baseweb="tab"], [data-testid="stTab"]) { border: var(--edge) !important; border-radius: 999px !important; padding: .4rem 1rem !important; background: var(--paper) !important;
  height: auto !important; transition: background .18s ease, transform .18s var(--ease); }
:is([data-baseweb="tab"], [data-testid="stTab"]):hover { background: var(--lime) !important; }
:is([data-baseweb="tab"], [data-testid="stTab"]) p { font-weight: 650 !important; color: var(--ink) !important; }
:is([data-baseweb="tab"], [data-testid="stTab"]):is([aria-selected="true"]) { background: var(--ink) !important; box-shadow: 3px 3px 0 var(--cobalt); }
:is([data-baseweb="tab"], [data-testid="stTab"]):is([aria-selected="true"]) p { color: var(--lime) !important; }
:is([data-baseweb="tab-panel"], [data-testid="stTabPanel"]) { padding-top: 1.1rem !important; }
[data-testid="stButtonGroup"] button[data-variant] { border: var(--edge) !important; background: var(--paper) !important; transition: background .18s ease, box-shadow .18s ease; }
[data-testid="stButtonGroup"] button[data-variant] :is(p, span) { font-weight: 650 !important; color: var(--ink) !important; }
[data-testid="stButtonGroup"] button[data-variant]:hover { background: var(--lime) !important; }
[data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]) { background: var(--ink) !important; box-shadow: 2px 2px 0 var(--cobalt); }
[data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]) :is(p, span) { color: var(--lime) !important; }

/* ---- expanders, popovers, alerts, tables, dialogs */
[data-testid="stExpander"] details { background: var(--paper); border: var(--edge) !important; border-radius: var(--r-sm) !important; }
[data-testid="stExpander"] summary p { font-weight: 650 !important; }
[data-testid="stExpander"] summary:hover { background: var(--ivory-2); }
[data-testid="stPopoverBody"] { background: var(--paper) !important; border: var(--edge) !important; border-radius: var(--r) !important; box-shadow: var(--hard) !important; }
[data-testid="stAlertContainer"] { border: var(--edge) !important; border-radius: var(--r-sm) !important; box-shadow: var(--hard-sm); }
[data-testid="stAlertContainer"] p { color: var(--ink) !important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { border: var(--edge); border-radius: var(--r-sm); overflow: hidden; background: var(--paper); }
[data-testid="stToast"] { background: var(--ink) !important; color: var(--ivory) !important; border: 2px solid var(--ink); box-shadow: 4px 4px 0 var(--lime); border-radius: var(--r-sm) !important; }
[data-testid="stToast"] p { color: var(--ivory) !important; }
[data-testid="stDialog"] [role="dialog"] { border: var(--edge); box-shadow: var(--hard); border-radius: var(--r) !important; background: var(--paper); }
hr { border-color: var(--ink) !important; opacity: .18; }

/* ---- AI chat: the person writes on ink, the assistant answers on paper */
[data-testid="stChatMessage"] { background: var(--paper); border: var(--edge); border-radius: var(--r); padding: 1rem 1.15rem; box-shadow: var(--hard-sm);
  animation: pg-fade-up .45s var(--ease) both; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: var(--ink); margin-left: min(14%, 140px); box-shadow: 4px 4px 0 var(--cobalt); }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) :is(p, li, span) { color: var(--ivory) !important; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) { margin-right: min(6%, 60px); }
[data-testid="stChatMessageAvatarAssistant"] { background: var(--lime) !important; color: var(--ink) !important; border: var(--edge); border-radius: 10px !important; }
[data-testid="stChatMessageAvatarUser"] { background: var(--ivory) !important; color: var(--ink) !important; border-radius: 10px !important; }
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: transparent !important; }
[data-testid="stBottomBlockContainer"] { padding-bottom: 5.6rem !important; }
[data-testid="stChatInput"] { border: var(--edge) !important; border-radius: var(--r) !important; background: var(--paper) !important; box-shadow: var(--hard); }
[data-testid="stChatInput"]:focus-within { box-shadow: 0 0 0 4px var(--lime), var(--hard) !important; }
[data-testid="stChatInputSubmitButton"] { background: var(--ink) !important; border-radius: 8px !important; }
[data-testid="stChatInputSubmitButton"] svg { fill: var(--lime) !important; color: var(--lime) !important; }

/* ---- sidebar: the ink spine */
section[data-testid="stSidebar"] { background: var(--ink) !important; border-right: 0 !important; }
section[data-testid="stSidebar"] > div:first-child { background: var(--ink) !important; }
[data-testid="stSidebarHeader"] { padding-bottom: .4rem; }
[data-testid="stSidebarNav"] a { border-radius: 10px; margin: 3px 0; border: 2px solid transparent; transition: background .2s ease, transform .2s var(--ease); }
[data-testid="stSidebarNav"] a :is(span, p) { font-weight: 550; color: #E9E3D5 !important; }
[data-testid="stSidebarNav"] a:hover { background: rgba(244,238,225,.08); transform: translateX(3px); }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--lime); border-color: var(--ink); box-shadow: 3px 3px 0 var(--cobalt); }
[data-testid="stSidebarNav"] a[aria-current="page"] :is(span, p) { color: var(--ink) !important; font-weight: 700; }
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] span { color: rgba(244,238,225,.55) !important; font-size: .78rem !important; font-weight: 600 !important; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { color: #E9E3D5; }
.pg-side { margin-top: 1.1rem; display: grid; gap: .6rem; font-size: .8rem; line-height: 1.5; color: rgba(244,238,225,.75); }
.pg-side .who { padding: .8rem .9rem; border-radius: 12px; background: var(--cobalt); color: var(--ivory); border: 2px solid var(--ivory); }
.pg-side .who b { display: block; font-family: var(--display); font-size: 1.15rem; font-weight: 750; color: var(--ivory); letter-spacing: -0.01em; }
.pg-side .sys { padding: .8rem .9rem; border-radius: 12px; border: 1.5px dashed rgba(244,238,225,.3); }
.pg-side .sys b { color: var(--ivory); }
.pg-side .sys div { display: flex; gap: .45rem; align-items: center; }
.pg-side .sys i { width: 9px; height: 9px; border-radius: 2px; background: var(--lime); flex: none; }
.pg-side .sys i.off { background: transparent; border: 1.5px solid rgba(244,238,225,.5); }

/* ---- top bar: a paper strip with an ink edge */
.st-key-topbar { position: sticky; top: .6rem; z-index: 60; margin-bottom: .2rem; border-radius: var(--r) !important; background: var(--paper);
  border: var(--edge); box-shadow: var(--hard-sm); padding: .4rem .5rem !important; }
.st-key-topbar [data-testid="stTextInputRootElement"] { border-width: 0 !important; background: var(--ivory-2) !important; }
.st-key-topbar [data-testid="stTextInputRootElement"]:focus-within { box-shadow: 0 0 0 3px var(--lime) !important; }
.st-key-topbar [data-testid="stPopoverButton"] { box-shadow: none !important; min-height: 2.4rem; }
.st-key-topbar [data-testid="stPopoverButton"]:hover { box-shadow: var(--hard-sm) !important; }

/* ---- dock: the ink ticker at the bottom of the content area */
[data-testid="stAppViewContainer"] > div:has(> main) { transform: translateZ(0); }
.st-key-dock { position: fixed; left: 50%; bottom: 16px; translate: -50% 0; z-index: 70; width: auto !important; max-width: calc(100% - 32px);
  gap: .2rem !important; padding: .35rem !important; border-radius: 16px; background: var(--ink); border: 2px solid var(--ink); box-shadow: 5px 5px 0 var(--cobalt);
  animation: pg-fade-up .6s .2s var(--ease) both; }
.st-key-dock button { border: 0 !important; box-shadow: none !important; background: transparent !important; min-height: 2.5rem !important; border-radius: 11px !important; }
.st-key-dock button p, .st-key-dock button span { color: #E9E3D5 !important; }
.st-key-dock button:hover { background: rgba(244,238,225,.1) !important; transform: none !important; }
.st-key-dock button[data-testid="stBaseButton-primary"] { background: var(--lime) !important; }
.st-key-dock button[data-testid="stBaseButton-primary"] :is(p, span) { color: var(--ink) !important; }

/* ---- page masthead: an oversized headline, words rising into place */
.pg-head { margin: .7rem 0 .2rem; display: grid; gap: .7rem; }
.pg-head h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 88%; font-size: clamp(2.5rem, 5.2vw, 4.4rem) !important;
  line-height: .92 !important; letter-spacing: -0.022em !important; margin: 0 !important; padding: 0 !important; color: var(--ink) !important; max-width: 18ch; }
.pg-head p { color: var(--ink-2); font-size: 1.04rem; line-height: 1.5; max-width: 62ch; margin: 0 !important; }
.pg-hero { display: grid; gap: .55rem; margin: .4rem 0 0; }
.pg-hero .hi { font-weight: 650; font-size: .95rem; color: var(--ink); display: inline-flex; align-items: center; gap: .5rem; }
.pg-hero .hi::before { content: ""; width: 26px; height: 10px; border-radius: 3px; background: var(--lime); border: 2px solid var(--ink); }
.pg-hero h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 86%; font-size: clamp(2.8rem, 6.2vw, 5.6rem) !important;
  line-height: .9 !important; letter-spacing: -0.025em !important; margin: 0 !important; padding: 0 !important; color: var(--ink) !important; max-width: 16ch; }
.pg-hero p { color: var(--ink-2); font-size: 1.08rem; line-height: 1.5; max-width: 58ch; margin: .3rem 0 0 !important; }
.pg-hero.center { text-align: center; justify-items: center; }
.pg-hero.center .hi::before { display: none; }
.pg-muted { color: var(--ink-2); }
.pg-label { font-size: .84rem; font-weight: 700; color: var(--ink); margin: 0 0 .4rem; display: flex; align-items: center; gap: .45rem; }
.pg-label::before { content: ""; width: 12px; height: 4px; background: var(--ink); border-radius: 2px; }

/* ---- stat tiles */
.pg-kpi { background: var(--paper); border: var(--edge); border-radius: var(--r); padding: 1rem 1.1rem 1.05rem; box-shadow: var(--hard-sm);
  position: relative; overflow: hidden; animation: pg-fade-up .5s var(--ease) both; }
.pg-kpi .l { display: flex; align-items: center; gap: .45rem; font-size: .86rem; font-weight: 650; color: var(--ink); }
.pg-kpi .l .material-symbols-rounded { font-size: 18px; }
.pg-kpi .v { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 2.9rem; line-height: .95; letter-spacing: -0.02em;
  margin-top: .5rem; color: var(--ink); font-variant-numeric: tabular-nums; }
.pg-kpi .n { color: var(--ink-2); font-size: .82rem; line-height: 1.4; margin-top: .45rem; }
.pg-kpi.accent { background: var(--pg-tone); }
.pg-kpi.accent :is(.l, .v, .n) { color: var(--pg-on, var(--ink)); }

/* ---- badges */
.pg-badge { display: inline-flex; align-items: center; gap: .35rem; padding: .14rem .55rem; border-radius: 6px; font-size: .78rem; font-weight: 700;
  border: 1.5px solid var(--ink); line-height: 1.35; white-space: nowrap; vertical-align: middle; }
.pg-badge i { display: none; }
.pg-prio-high { background: var(--coral); color: var(--ink); }
.pg-prio-medium { background: var(--lime); color: var(--ink); }
.pg-prio-low { background: var(--cobalt); color: var(--ivory); }
.pg-soft { background: var(--ivory-2); color: var(--ink); }
.pg-stage { display: inline-flex; align-items: center; gap: .4rem; font-size: .78rem; font-weight: 650; padding: .12rem .55rem .12rem .4rem;
  border-radius: 999px; border: 1.5px solid var(--ink); background: var(--paper); color: var(--ink); white-space: nowrap; vertical-align: middle; }
.pg-stage i { width: 9px; height: 9px; border-radius: 50%; background: var(--st); border: 1.5px solid var(--ink); }
.pg-role { display: inline-block; font-size: .76rem; font-weight: 700; padding: .12rem .55rem; border-radius: 6px; border: 1.5px solid var(--ink); }
.pg-role.analyst { background: var(--cobalt); color: var(--ivory); } .pg-role.employee { background: var(--lime); color: var(--ink); }
.pg-kbd { font-size: .75rem; padding: .05rem .35rem; border: 1.5px solid var(--ink); border-radius: 5px; background: var(--paper); }

/* ---- empty state */
.pg-empty { text-align: left; padding: 1rem .2rem; display: grid; grid-template-columns: auto 1fr; gap: .2rem 1rem; align-items: start; }
.pg-empty .ico { grid-row: span 2; width: 52px; height: 52px; border-radius: 12px; display: grid; place-items: center; background: var(--lime);
  border: var(--edge); box-shadow: var(--hard-sm); color: var(--ink); }
.pg-empty h4 { margin: .2rem 0 0 !important; padding: 0 !important; font-size: 1.2rem !important; }
.pg-empty p { color: var(--ink-2); margin: 0 !important; max-width: 60ch; }

/* ---- priority probabilities: three blocks sized by probability; the predicted one is solid, the rest hatched */
.pg-meter { display: flex; height: 30px; border: var(--edge); border-radius: 8px; overflow: hidden; background: var(--paper); }
.pg-meter span { height: 100%; border-right: 2px solid var(--ink); transform-origin: left; animation: pg-grow .8s var(--ease) both; }
.pg-meter span:last-child { border-right: 0; }
.pg-meter span.off { background-image: repeating-linear-gradient(135deg, rgba(10,12,27,.0) 0 5px, rgba(10,12,27,.28) 5px 6.5px) !important; opacity: .55; }
.pg-meter-legend { display: flex; flex-wrap: wrap; gap: .3rem 1rem; margin-top: .5rem; font-size: .84rem; color: var(--ink-2); }
.pg-meter-legend span { display: inline-flex; align-items: center; gap: .35rem; }
.pg-meter-legend i { width: 12px; height: 12px; border-radius: 3px; border: 1.5px solid var(--ink); }
.pg-meter-legend b { color: var(--ink); }

/* ---- activity feed: a wire service */
.pg-feed { list-style: none; margin: 0; padding: 0; }
.pg-feed li { display: grid; grid-template-columns: 30px 1fr auto; gap: .7rem; align-items: start; padding: .6rem 0; border-bottom: 1.5px dashed var(--line); }
.pg-feed li:last-child { border-bottom: 0; } .pg-feed li:first-child { padding-top: .1rem; }
.pg-feed .dot { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; background: var(--ivory-2); border: 1.5px solid var(--ink); }
.pg-feed .dot .material-symbols-rounded { font-size: 16px; }
.pg-feed .m { font-size: .9rem; line-height: 1.4; color: var(--ink); }
.pg-feed .t { font-size: .76rem; color: var(--muted); white-space: nowrap; font-weight: 600; }

/* ---- ticket progress: stations on a rail */
.pg-steps { display: flex; align-items: flex-start; margin: .5rem 0 .3rem; position: relative; }
.pg-step { flex: 1; position: relative; font-size: .76rem; font-weight: 600; color: var(--muted); padding-top: 24px; text-align: center; line-height: 1.25; }
.pg-step i { position: absolute; top: 0; left: 50%; width: 18px; height: 18px; margin-left: -9px; border-radius: 50%; background: var(--paper); border: 2px solid var(--ink); z-index: 1; }
.pg-step::before { content: ""; position: absolute; top: 8px; left: -50%; right: 50%; height: 2px; background: var(--ink); opacity: .25; }
.pg-step:first-child::before { display: none; }
.pg-step.done, .pg-step.now { color: var(--ink); }
.pg-step.done i { background: var(--ink); }
.pg-step.done::before, .pg-step.now::before { opacity: 1; height: 3px; top: 7.5px; }
.pg-step.now i { background: var(--lime); width: 22px; height: 22px; margin-left: -11px; top: -2px; animation: pg-pulse 1.6s ease-out 2; }

/* ---- solution text: a quoted answer */
.pg-solution { background: var(--paper); border: var(--edge); border-left-width: 8px; border-left-color: var(--cobalt) !important; border-radius: var(--r-sm);
  padding: .8rem 1rem; color: var(--ink); line-height: 1.55; font-size: .94rem; white-space: pre-wrap; }

/* ---- Find a fix: priority line, compact match line, the problem and the solution in plain steps */
.pg-sev { display: flex; flex-wrap: wrap; align-items: center; gap: .35rem .6rem; padding: .7rem .9rem; margin: 0 0 .9rem;
  border: var(--edge); border-radius: var(--r-sm); background: var(--ivory-2); }
.pg-sev .t { font-weight: 750; font-size: .9rem; color: var(--ink); }
.pg-sev .m { font-size: .9rem; color: var(--ink); }
.pg-sev .w { font-size: .82rem; color: var(--ink-2); display: inline-flex; flex-wrap: wrap; gap: .25rem; align-items: center; }
.pg-sev .w span, .pg-mline .w span { padding: .02rem .45rem; border-radius: 5px; background: var(--paper); border: 1.5px solid var(--ink); color: var(--ink); font-weight: 650; }
.pg-sev small { flex-basis: 100%; font-size: .74rem; color: var(--ink-2); }
.pg-mline { display: flex; flex-wrap: wrap; align-items: center; gap: .3rem .6rem; margin: .55rem 0 .2rem; font-size: .88rem; color: var(--ink-2); }
.pg-mline > b { font-family: var(--display); font-size: 1.35rem; font-weight: 800; color: var(--ink); line-height: 1; }
.pg-mline .bar { position: relative; flex: 0 1 180px; min-width: 110px; height: 10px; border: 1.5px solid var(--ink); border-radius: 4px; background: var(--paper); }
.pg-mline .bar > span { position: absolute; left: 0; top: 0; bottom: 0; background: var(--why, var(--cobalt)); border-radius: 2px 0 0 2px; }
.pg-mline .bar i { position: absolute; top: -4px; bottom: -4px; width: 3px; margin-left: -1.5px; background: var(--ink); border-radius: 2px; }
.pg-mline small { font-size: .76rem; }
.pg-mline .w { font-size: .8rem; display: inline-flex; flex-wrap: wrap; gap: .25rem; align-items: center; }
.pg-past { margin: .45rem 0 0; font-size: .9rem; color: var(--ink-2); line-height: 1.5; }
.pg-past b, .pg-fixsol > b { display: block; font-size: .78rem; font-weight: 750; color: var(--ink); margin-bottom: .1rem; }
.pg-fixsol { margin: .7rem 0 .4rem; padding: .85rem 1rem; background: var(--paper); border: var(--edge); border-left-width: 8px;
  border-left-color: var(--lime) !important; border-radius: var(--r-sm); color: var(--ink); line-height: 1.55; font-size: .95rem; }
.pg-fixsol ol { margin: .2rem 0 .3rem 1.2rem; padding: 0; } .pg-fixsol li { margin: .15rem 0; }
.pg-fixsol p { margin: .2rem 0; } .pg-fixsol small { display: block; margin-top: .35rem; font-size: .74rem; color: var(--ink-2); }

/* ---- similarity ruler: tick marks every 10%, the threshold notched in, the score as a big number */
.pg-why { margin-top: .2rem; padding: .9rem 1rem 1rem; border-radius: var(--r-sm); background: var(--ivory-2); border: var(--edge); }
.pg-why .hd { display: flex; align-items: flex-end; justify-content: space-between; gap: .8rem; }
.pg-why .hd .t { font-size: .86rem; font-weight: 700; color: var(--ink); }
.pg-why .hd .pct { font-family: var(--display); font-size: 2.3rem; font-weight: 800; font-stretch: 75%; color: var(--ink); font-variant-numeric: tabular-nums; line-height: .85; }
.pg-why .hd .pct small { font-family: var(--text); font-size: .8rem; font-weight: 600; color: var(--ink-2); margin-left: .3rem; letter-spacing: 0; }
.pg-why .bar { position: relative; height: 18px; border: var(--edge); border-radius: 5px; background:
  repeating-linear-gradient(90deg, transparent 0 calc(10% - 1.5px), rgba(10,12,27,.35) calc(10% - 1.5px) 10%), var(--paper); margin: .65rem 0 1.25rem; }
.pg-why .bar span { position: absolute; left: 0; top: 0; bottom: 0; background: var(--why, var(--cobalt)); border-right: 2px solid var(--ink); transform-origin: left; animation: pg-grow .9s var(--ease) both; }
.pg-why .bar i { position: absolute; top: -7px; bottom: -7px; width: 4px; margin-left: -2px; background: var(--ink); border-radius: 2px; }
.pg-why .bar i::after { content: attr(data-l); position: absolute; top: calc(100% + 2px); left: 50%; transform: translateX(-50%); white-space: nowrap; font-size: .7rem; font-weight: 700; color: var(--ink); }
.pg-why .lv { font-size: .84rem; color: var(--ink-2); }
.pg-why .lv b { color: var(--ink); font-weight: 750; }
.pg-why .chips { margin-top: .55rem; display: flex; flex-wrap: wrap; gap: .3rem; align-items: center; font-size: .8rem; color: var(--ink-2); font-weight: 600; }
.pg-why .chips span { padding: .06rem .5rem; border-radius: 5px; background: var(--lime); border: 1.5px solid var(--ink); color: var(--ink); font-weight: 650; }
.pg-why .x { margin: .7rem 0 0; font-size: .92rem; line-height: 1.55; color: var(--ink); max-width: none !important; }
.pg-why .x .chk { display: block; margin-top: .5rem; padding: .5rem .65rem; border-radius: 8px; background: var(--paper); border: 1.5px dashed var(--ink); color: var(--ink); font-size: .88rem; }
.pg-why .by { margin-top: .55rem; font-size: .76rem; color: var(--muted); font-weight: 600; }
.pg-why.esc { background: var(--coral-2); }

/* ---- priority donut, gauges, avatars, day columns */
.pg-dial { display: grid; grid-template-columns: auto 1fr; align-items: center; gap: 1.2rem; }
.pg-dial ul { list-style: none; margin: 0; padding: 0; display: grid; gap: .5rem; }
.pg-dial li { display: flex; align-items: center; gap: .5rem; font-size: .9rem; font-weight: 600; color: var(--ink); }
.pg-dial li i { width: 14px; height: 14px; border-radius: 4px; border: 1.5px solid var(--ink); flex: none; }
.pg-dial li b { margin-left: auto; font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 1.25rem; font-variant-numeric: tabular-nums; }
.pg-dial.stack { grid-template-columns: 1fr; justify-items: center; gap: .9rem; }
.pg-dial.stack ul { display: grid; grid-template-columns: repeat(3, 1fr); width: 100%; gap: .4rem; }
.pg-dial.stack li { flex-direction: column; gap: .15rem; font-size: .8rem; }
.pg-dial.stack li b { margin: 0; }
.pg-gauge { display: flex; flex-direction: column; align-items: center; text-align: center; }
.pg-gauge .cap { color: var(--ink-2); font-size: .85rem; line-height: 1.4; margin-top: .1rem; font-weight: 550; }
.pg-tile { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: .2rem; }
.pg-avatars { display: flex; align-items: center; }
.pg-avatars span { width: 34px; height: 34px; border-radius: 9px; display: grid; place-items: center; font-size: .74rem; font-weight: 750;
  border: 2px solid var(--ink); margin-left: -7px; color: var(--ink); }
.pg-avatars span:first-child { margin-left: 0; }
.pg-avatars span.more { background: var(--ink); color: var(--lime); }
.pg-days { display: grid; grid-template-columns: repeat(var(--n), 1fr); gap: .55rem; align-items: end; }
.pg-days > div { display: grid; grid-template-rows: auto 1fr auto auto; justify-items: center; gap: .3rem; text-align: center; }
.pg-days .col { width: 100%; height: 120px; display: flex; flex-direction: column-reverse; border: var(--edge); border-radius: 7px; overflow: hidden; background:
  repeating-linear-gradient(0deg, transparent 0 23px, rgba(10,12,27,.08) 23px 24px), var(--paper); }
.pg-days .col span { display: block; border-top: 2px solid var(--ink); transform-origin: bottom; animation: pg-grow-y .7s var(--ease) both; }
@keyframes pg-grow-y { from { transform: scaleY(0); } to { transform: scaleY(1); } }
.pg-days b { font-size: .78rem; font-weight: 700; } .pg-days em { font-style: normal; font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 1.5rem; line-height: 1; }
.pg-days small { color: var(--muted); font-size: .7rem; font-weight: 600; }
.pg-days .today b { background: var(--lime); border: 1.5px solid var(--ink); border-radius: 4px; padding: 0 .3rem; }

/* ---- number tiles, figure rows, numbered steps, list items */
.pg-big { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 3.4rem; line-height: .9; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
.pg-numcard { display: flex; align-items: center; justify-content: space-between; gap: .8rem; }
.pg-numcard .ico { width: 44px; height: 44px; border-radius: 11px; display: grid; place-items: center; background: var(--lime); border: var(--edge); color: var(--ink); }
.pg-numlbl { color: var(--ink-2); font-size: .88rem; line-height: 1.4; margin-top: .45rem; font-weight: 550; }
.pg-rows { list-style: none; margin: 0; padding: 0; }
.pg-rows li { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; padding: .6rem 0; border-bottom: 1.5px dashed var(--line); font-size: .93rem; color: var(--ink-2); }
.pg-rows li:last-child { border-bottom: 0; } .pg-rows li:first-child { padding-top: .2rem; }
.pg-rows li b { color: var(--ink); font-family: var(--display); font-weight: 800; font-stretch: 80%; font-size: 1.15rem; font-variant-numeric: tabular-nums; }
.pg-howto { list-style: none; margin: 0; padding: 0; display: grid; gap: .75rem; counter-reset: s; }
.pg-howto li { display: grid; grid-template-columns: 30px 1fr; gap: .75rem; align-items: start; color: var(--ink-2); font-size: .93rem; line-height: 1.5; counter-increment: s; }
.pg-howto li::before { content: counter(s); width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center; font-family: var(--display); font-size: .95rem; font-weight: 800;
  color: var(--ink); background: var(--lime); border: var(--edge); }
.pg-howto b { color: var(--ink); font-weight: 700; }
.pg-fix { display: flex; flex-direction: column; gap: .3rem; height: 100%; }
.pg-fix .t { color: var(--ink); font-weight: 700; font-size: .96rem; line-height: 1.35; }
.pg-fix .pg-solution { margin-top: .5rem; flex: 1 1 auto; }
.pg-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: .7rem 0; border-bottom: 1.5px dashed var(--line); }
.pg-item:last-child { border-bottom: 0; } .pg-item:first-child { padding-top: 0; }
.pg-item .t { color: var(--ink); font-size: .94rem; line-height: 1.4; margin-top: .35rem; font-weight: 550; }
.pg-item .s { color: var(--ink-2); font-size: .84rem; line-height: 1.4; margin-top: .2rem; }

/* ---- ticket stubs: the core object, drawn like a real ticket (perforation, notches, a coloured stub) */
.pg-tk { --pc: var(--ivory-2); --pt: var(--ink); position: relative; display: grid; grid-template-columns: 74px 1fr; min-height: 112px;
  background: var(--paper); border: var(--edge); border-radius: 12px; box-shadow: var(--hard-sm);
  -webkit-mask: radial-gradient(circle 9px at 74px 0, #0000 98%, #000) top / 100% 51% no-repeat, radial-gradient(circle 9px at 74px 100%, #0000 98%, #000) bottom / 100% 51% no-repeat;
          mask: radial-gradient(circle 9px at 74px 0, #0000 98%, #000) top / 100% 51% no-repeat, radial-gradient(circle 9px at 74px 100%, #0000 98%, #000) bottom / 100% 51% no-repeat; }
.pg-tk.p-high { --pc: var(--coral); } .pg-tk.p-medium { --pc: var(--lime); } .pg-tk.p-low { --pc: var(--cobalt); --pt: var(--ivory); }
.pg-tk .stub { background: var(--pc); color: var(--pt); border-right: 2px dashed var(--ink); display: flex; flex-direction: column; align-items: center; justify-content: space-between;
  padding: .7rem .2rem; border-radius: 10px 0 0 10px; }
.pg-tk .stub .no { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 1.5rem; line-height: 1; letter-spacing: -0.02em; writing-mode: vertical-rl; transform: rotate(180deg); }
.pg-tk .stub .pr { font-size: .66rem; font-weight: 800; letter-spacing: .02em; }
.pg-tk .body { padding: .75rem .95rem .7rem 1rem; display: flex; flex-direction: column; gap: .35rem; min-width: 0; }
.pg-tk .meta { display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; font-size: .76rem; color: var(--muted); font-weight: 600; }
.pg-tk .sub { font-family: var(--display); font-weight: 750; font-size: 1.08rem; line-height: 1.18; color: var(--ink); letter-spacing: -0.01em;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.pg-tk .foot { margin-top: auto; font-size: .78rem; color: var(--ink-2); display: flex; justify-content: space-between; gap: .5rem; font-weight: 550; }
.pg-tk.compact { min-height: 88px; grid-template-columns: 58px 1fr; -webkit-mask: none; mask: none; }
.pg-tk.compact .stub .no { font-size: 1.2rem; }
.pg-tk.compact .sub { font-size: .98rem; }
/* tap targets: a container whose transparent button covers it, so the whole ticket is clickable */
[class*="st-key-tap-"] { position: relative; gap: 0 !important; transition: transform .2s var(--ease); transform: translate(var(--mx, 0px), var(--my, 0px)); }
[class*="st-key-tap-"]:hover { transform: translate(calc(var(--mx, 0px) - 2px), calc(var(--my, 0px) - 2px)); }
[class*="st-key-tap-"]:hover .pg-tk { box-shadow: 6px 6px 0 var(--ink); }
[class*="st-key-tap-"]:active { transform: translate(2px, 2px); }
[class*="st-key-tap-"] > [data-testid="stElementContainer"]:has([data-testid="stButton"]) { position: absolute !important; inset: 0; margin: 0; z-index: 2; width: auto !important; }
[class*="st-key-tap-"] [data-testid="stButton"], [class*="st-key-tap-"] [data-testid="stButton"] > div, [class*="st-key-tap-"] [data-testid="stButton"] button { width: 100% !important; height: 100% !important; }
[class*="st-key-tap-"] [data-testid="stButton"] button { background: transparent !important; border: 0 !important; box-shadow: none !important; color: transparent !important; border-radius: 12px !important; transform: none !important; }
[class*="st-key-tap-"] [data-testid="stButton"] button p { color: transparent !important; }
[class*="st-key-tap-on-"] .pg-tk { outline: 3px solid var(--cobalt); outline-offset: 3px; }

/* ---- ticket list rows (My tickets) */
[class*="st-key-mtrow-"] { position: relative; gap: .3rem !important; padding: .75rem .85rem !important; border-radius: 12px; border: 2px solid transparent;
  transition: background .2s ease, border-color .2s ease; }
[class*="st-key-mtrow-"]:hover { background: var(--ivory-2); }
[class*="st-key-mtrow-on-"] { background: var(--lime); border-color: var(--ink); box-shadow: var(--hard-sm); }
[class*="st-key-mtrow-"] > [data-testid="stElementContainer"]:has([data-testid="stButton"]) { position: absolute !important; inset: 0; margin: 0; z-index: 2; width: auto !important; }
[class*="st-key-mtrow-"] [data-testid="stButton"], [class*="st-key-mtrow-"] [data-testid="stButton"] > div, [class*="st-key-mtrow-"] [data-testid="stButton"] button { width: 100% !important; height: 100% !important; }
[class*="st-key-mtrow-"] [data-testid="stButton"] button { background: transparent !important; border: 0 !important; box-shadow: none !important; color: transparent !important; border-radius: 12px !important; transform: none !important; }
[class*="st-key-mtrow-"] [data-testid="stButton"] button p { color: transparent !important; }
.pg-mt .t { color: var(--ink); font-weight: 700; font-size: .95rem; line-height: 1.35; margin: .45rem 0 .2rem; }
.pg-mt .s { color: var(--ink-2); font-size: .8rem; font-weight: 550; }

/* ---- card header row, recommendation blocks, example suggestions */
[class*="st-key-head-"] { gap: .75rem !important; min-height: 2.1rem; }
[class*="st-key-head-"] h5 { padding: 0 !important; margin: 0 !important; }
[class*="st-key-head-"] [data-testid="stMarkdownContainer"], [class*="st-key-line-"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
:is([class*="st-key-card"], [class*="st-key-art-"]) [data-testid="stMarkdownContainer"] hr { margin: .3rem 0 !important; }
[class*="st-key-rec-"] { gap: .75rem !important; padding-bottom: 1.15rem; border-bottom: 2px dashed var(--line); }
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-rec-"]):last-child > [class*="st-key-rec-"] { border-bottom: 0; padding-bottom: 0; }
.st-key-card-fit-examples [data-testid="stBaseButton-tertiary"] { justify-content: flex-start !important; text-align: left; padding: .5rem .55rem !important; min-height: 0;
  background-size: 0 100% !important; }
.st-key-card-fit-examples [data-testid="stBaseButton-tertiary"]:hover { background-size: 100% 100% !important; }
.st-key-card-fit-examples [data-testid="stBaseButton-tertiary"] > div { justify-content: flex-start !important; }
.st-key-card-fit-examples [data-testid="stBaseButton-tertiary"] p { text-align: left; }
.st-key-card-fit-examples { gap: .15rem !important; }

/* ---- knowledge documents: index cards with a coloured tab */
.pg-doc .ic { width: 46px; height: 46px; border-radius: 11px; display: grid; place-items: center; margin-bottom: .8rem; background: var(--lime); border: var(--edge); color: var(--ink); }
.pg-doc h4 { font-family: var(--display) !important; font-weight: 750 !important; font-size: 1.15rem !important; margin: 0 0 .35rem !important; padding: 0 !important; line-height: 1.2; }
.pg-doc .meta { color: var(--ink-2); font-size: .8rem; margin-bottom: .35rem; font-weight: 550; }
.pg-doc .tags { margin-bottom: .35rem; min-height: 1.2rem; }
.pg-welcome { padding: .6rem .2rem .2rem; }
.pg-welcome h2 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 80%; font-size: clamp(2rem, 3.4vw, 3rem) !important; letter-spacing: -0.035em;
  margin: .7rem 0 .4rem !important; padding: 0 !important; line-height: .95; }
.pg-welcome p { color: var(--ink-2); max-width: 56ch; margin: 0 0 1rem; line-height: 1.6; }

/* ---- stickers: rotated colour labels that drop onto a composition */
.pg-sticker { display: inline-block; padding: .45rem .8rem; border: var(--edge); border-radius: 10px; box-shadow: var(--hard-sm); font-weight: 750; font-size: .9rem;
  line-height: 1.25; transform: rotate(var(--rot, -4deg)); animation: pg-drop .7s var(--ease) both; animation-delay: var(--d, .5s); }
.pg-sticker.lime { background: var(--lime); color: var(--ink); } .pg-sticker.coral { background: var(--coral); color: var(--ink); }
.pg-sticker.cobalt { background: var(--cobalt); color: var(--ivory); } .pg-sticker.paper { background: var(--paper); color: var(--ink); }
.pg-sticker.ink { background: var(--ink); color: var(--lime); }
.pg-sticker b { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 1.6em; line-height: .9; display: block; letter-spacing: -0.02em; }

.pg-spark { display: inline-grid; } .pg-spark svg { display: block; }
.material-symbols-rounded { font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; font-size: 20px; line-height: 1;
  letter-spacing: normal; text-transform: none; display: inline-block; white-space: nowrap; direction: ltr; -webkit-font-smoothing: antialiased; vertical-align: middle; }

/* ---- compositions shared by the workspace pages */
/* masthead: the headline, and beside it one real number on a tilted colour block */
.pg-mast { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2.2rem; align-items: end; margin: 1rem 0 .4rem; }
.pg-mast .hi { font-weight: 650; font-size: .95rem; color: var(--ink); display: inline-flex; align-items: center; gap: .5rem; margin-bottom: .6rem; }
.pg-mast .hi::before { content: ""; width: 26px; height: 10px; border-radius: 3px; background: var(--lime); border: 2px solid var(--ink); }
.pg-mast h1 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 86%; font-size: clamp(2.7rem, 6vw, 5.4rem) !important;
  line-height: .9 !important; letter-spacing: -0.025em !important; margin: 0 !important; padding: 0 !important; color: var(--ink) !important; max-width: 15ch; }
.pg-mast p { color: var(--ink-2); font-size: 1.06rem; line-height: 1.5; max-width: 60ch; margin: .8rem 0 0 !important; }
.pg-mast .fig { background: var(--tone, var(--lime)); color: var(--on, var(--ink)); border: var(--edge); border-radius: 18px; box-shadow: 8px 8px 0 var(--ink);
  padding: 1.05rem 1.35rem 1.15rem; min-width: 210px; max-width: 290px; --rot: 2.5deg; transform: rotate(var(--rot)); animation: pg-drop .8s .25s var(--ease) both;
  margin: 0 .6rem .4rem 0; }
.pg-mast .fig b { display: block; font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: clamp(4.2rem, 7.5vw, 6.6rem); line-height: .82;
  letter-spacing: -0.03em; font-variant-numeric: tabular-nums; color: inherit; }
.pg-mast .fig span:not(.pg-count) { display: block; margin-top: .55rem; font-weight: 650; font-size: .93rem; line-height: 1.3; color: inherit; }
/* the priority ribbon: one band, each priority's share of it in its own colour */
.pg-ribbon { display: flex; border: var(--edge); border-radius: 14px; overflow: hidden; min-height: 116px; background: var(--paper); box-shadow: var(--hard-sm); }
.pg-ribbon > div { flex: var(--n) 1 0; min-width: 6.8rem; padding: .75rem .95rem .8rem; display: flex; flex-direction: column; justify-content: space-between;
  border-right: 2px solid var(--ink); background: var(--pc); color: var(--pt); transform-origin: left; animation: pg-grow .9s var(--ease) both; }
.pg-ribbon > div:last-child { border-right: 0; }
.pg-ribbon > div.zero { flex: 0 0 auto; min-width: 5.6rem; background: repeating-linear-gradient(135deg, transparent 0 6px, rgba(10,12,27,.13) 6px 7.5px), var(--paper); color: var(--ink-2); }
.pg-ribbon b { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 3.3rem; line-height: .85; color: inherit; font-variant-numeric: tabular-nums; }
.pg-ribbon > div > span { font-weight: 700; font-size: .86rem; color: inherit; display: flex; justify-content: space-between; gap: .5rem; flex-wrap: wrap; }
.pg-ribbon > div > span em { font-style: normal; opacity: .8; font-weight: 650; }
.pg-ribbon.v { flex-direction: column; } .pg-ribbon.v > div { border-right: 0; border-bottom: 2px solid var(--ink); min-height: 64px; flex-direction: row; align-items: center; gap: 1rem; }
.pg-ribbon.v > div:last-child { border-bottom: 0; } .pg-ribbon.v > div > span { flex: 1; }
.pg-ribbon .p-high { --pc: var(--coral); --pt: var(--ink); } .pg-ribbon .p-medium { --pc: var(--lime); --pt: var(--ink); } .pg-ribbon .p-low { --pc: var(--cobalt); --pt: var(--ivory); }
/* typographic figures: big numbers set like a newspaper's numbers column */
.pg-figs { display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); border-top: 2px solid var(--ink); }
.pg-figs > div { padding: 1rem 1.1rem .3rem 0; margin-right: 1.1rem; border-right: 2px solid var(--line); min-width: 0; }
.pg-figs > div:last-child { border-right: 0; margin-right: 0; }
.pg-figs b { display: inline-block; font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: clamp(2.7rem, 4.6vw, 4.3rem); line-height: .86;
  letter-spacing: -0.02em; color: var(--ink); font-variant-numeric: tabular-nums; box-shadow: inset 0 -.2em 0 var(--tone, transparent); }
.pg-figs > div > span { display: block; margin-top: .6rem; font-size: .9rem; line-height: 1.4; color: var(--ink); font-weight: 650; max-width: 28ch; }
.pg-figs > div > small { display: block; margin-top: .2rem; font-size: .8rem; line-height: 1.4; color: var(--ink-2); max-width: 30ch; }
.pg-figs.dark { border-top-color: rgba(244,238,225,.35); } .pg-figs.dark > div { border-right-color: rgba(244,238,225,.2); }
.pg-figs.dark b { color: var(--lime); box-shadow: none; } .pg-figs.dark > div > span { color: var(--ivory); } .pg-figs.dark > div > small { color: rgba(244,238,225,.7); }
@media (max-width: 760px) { .pg-figs { grid-template-columns: 1fr 1fr; } .pg-figs > div:nth-child(2n) { border-right: 0; margin-right: 0; } }
/* similarity ladder: every candidate's score on the same ruler, the reuse threshold drawn through all of them */
.pg-ladder { display: grid; gap: .6rem; }
.pg-ladder .r { display: grid; grid-template-columns: 5.2rem minmax(0, 1fr) 3.4rem; gap: .8rem; align-items: center; }
.pg-ladder .id { font-weight: 750; font-size: .84rem; color: var(--ink); line-height: 1.2; }
.pg-ladder .id small { display: block; font-weight: 600; color: var(--muted); font-size: .7rem; }
.pg-ladder .rail { position: relative; height: 24px; border: var(--edge); border-radius: 6px; background:
  repeating-linear-gradient(90deg, transparent 0 calc(10% - 1.5px), rgba(10,12,27,.2) calc(10% - 1.5px) 10%), var(--paper); }
.pg-ladder .rail span { position: absolute; inset: 0 auto 0 0; border-right: 2px solid var(--ink); transform-origin: left; animation: pg-grow .9s var(--ease) both;
  background: repeating-linear-gradient(135deg, transparent 0 5px, rgba(10,12,27,.22) 5px 6.5px), #D9DEFF; }
.pg-ladder .r.ok .rail span { background: var(--lime); }
.pg-ladder .rail i { position: absolute; top: -6px; bottom: -6px; width: 4px; margin-left: -2px; background: var(--coral); border: 1.5px solid var(--ink); border-radius: 2px; }
.pg-ladder .pct { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 1.5rem; text-align: right; color: var(--ink); font-variant-numeric: tabular-nums; }
.pg-ladder .key { display: flex; flex-wrap: wrap; gap: .3rem 1rem; font-size: .78rem; color: var(--ink-2); font-weight: 600; margin-top: .2rem; }
.pg-ladder .key i { display: inline-block; width: 12px; height: 12px; border: 1.5px solid var(--ink); border-radius: 3px; vertical-align: -2px; margin-right: .3rem; }
/* horizontal bars, one row per person */
.pg-hbars { display: grid; gap: .75rem; }
.pg-hbars .r { display: grid; grid-template-columns: minmax(6rem, 9.5rem) minmax(0, 1fr) auto; gap: .8rem; align-items: center; }
.pg-hbars .n { font-weight: 700; font-size: .9rem; line-height: 1.2; color: var(--ink); min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.pg-hbars .n small { display: block; color: var(--muted); font-weight: 600; font-size: .72rem; }
.pg-hbars .b { display: flex; height: 24px; border: var(--edge); border-radius: 6px; overflow: hidden; background: var(--paper); }
.pg-hbars .b span { height: 100%; border-right: 2px solid var(--ink); transform-origin: left; animation: pg-grow .8s var(--ease) both; }
.pg-hbars .b span:last-child { border-right: 0; }
.pg-hbars .v { font-size: .8rem; color: var(--ink-2); font-weight: 600; white-space: nowrap; }
.pg-hbars .v b { font-family: var(--display); font-weight: 800; font-size: 1.2rem; color: var(--ink); }
/* the triage verdict: the predicted priority as a block of its own colour */
.pg-verdict { position: relative; background: var(--pc, var(--paper)); color: var(--pt, var(--ink)); border: var(--edge); border-radius: 18px; box-shadow: 8px 8px 0 var(--ink);
  padding: 1rem 1.3rem 1.2rem; overflow: hidden; animation: pg-drop .7s var(--ease) both; --rot: -1deg; }
.pg-verdict.p-high { --pc: var(--coral); } .pg-verdict.p-medium { --pc: var(--lime); } .pg-verdict.p-low { --pc: var(--cobalt); --pt: var(--ivory); }
.pg-verdict .k { font-weight: 700; font-size: .88rem; color: inherit; }
.pg-verdict .w { font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: clamp(3.8rem, 7vw, 6rem); line-height: .8; letter-spacing: -0.03em; margin-top: .45rem; color: inherit; }
.pg-verdict .c { position: absolute; right: 1.3rem; top: 1rem; text-align: right; color: inherit; }
.pg-verdict .c b { display: block; font-family: var(--display); font-weight: 800; font-stretch: 75%; font-size: 2.6rem; line-height: .9; color: inherit; }
.pg-verdict .c > span { font-size: .8rem; font-weight: 650; color: inherit; }
.pg-verdict .why { margin-top: .9rem; display: flex; flex-wrap: wrap; gap: .35rem; align-items: center; font-size: .82rem; font-weight: 650; color: inherit; }
.pg-verdict .why span { background: var(--paper); color: var(--ink); border: 1.5px solid var(--ink); border-radius: 6px; padding: .08rem .5rem; font-weight: 700; }
/* a small rotated stamp on a card corner */
.pg-stamp { position: absolute; top: -.7rem; right: .9rem; z-index: 3; transform: rotate(4deg); background: var(--lime); color: var(--ink); border: var(--edge); border-radius: 7px;
  padding: .12rem .55rem; font-size: .76rem; font-weight: 800; box-shadow: 2px 2px 0 var(--ink); }
.pg-fix { position: relative; }
/* feeds and figures on dark slabs */
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"]) .pg-feed li { border-bottom-color: rgba(244,238,225,.18); }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"]) .pg-feed .m { color: var(--ivory); }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"]) .pg-feed .t { color: rgba(244,238,225,.6); }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"]) .pg-feed .dot { background: var(--lime); border-color: var(--lime); }
:is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"]) .pg-feed .dot span { color: var(--ink) !important; }
.pg-tk .body .sub { color: var(--ink) !important; } .pg-tk .stub span { color: var(--pt) !important; }
.pg-tk .pg-stage { color: var(--ink) !important; } .pg-tk .foot span { color: var(--ink-2) !important; }
.pg-ribbon > div :is(span, b, em) { color: inherit !important; } .pg-ribbon > div { color: var(--pt) !important; }
.pg-ribbon > div.zero { color: var(--ink-2) !important; }
/* section title inside the flow of a page: big, with a short ink rule before it */
.pg-sec { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: .8rem 0 -.2rem; }
.pg-sec h3 { font-family: var(--display) !important; font-weight: 800 !important; font-stretch: 86%; font-size: clamp(1.7rem, 3vw, 2.4rem) !important; line-height: 1 !important;
  letter-spacing: -0.02em !important; margin: 0 !important; padding: 0 !important; color: inherit !important; }
.pg-sec > span { color: var(--ink-2); font-size: .9rem; font-weight: 600; }
@media (max-width: 760px) { .pg-mast { grid-template-columns: 1fr; gap: 1.4rem; } .pg-mast .fig { justify-self: start; }
  .pg-ribbon { flex-direction: column; } .pg-ribbon > div { border-right: 0; border-bottom: 2px solid var(--ink); min-height: 70px; flex-direction: row; align-items: center; }
  .pg-ribbon > div:last-child { border-bottom: 0; } .pg-ladder .r { grid-template-columns: 4.2rem minmax(0, 1fr) 3rem; } .pg-verdict .c { position: static; text-align: left; margin-top: .6rem; } }
@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] { padding-top: 3.4rem; padding-left: 1rem; padding-right: 1rem; }
  .st-key-topbar { position: relative; top: 0; }
  .st-key-topbar [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; gap: .5rem !important; }
  .st-key-topbar [data-testid="stColumn"] { min-width: 0 !important; }
  .st-key-topbar [data-testid="stColumn"]:nth-child(1) { flex: 1 1 100% !important; }
  .st-key-topbar [data-testid="stColumn"]:nth-child(2) { display: none !important; }
  .st-key-topbar [data-testid="stColumn"]:nth-child(3) { flex: 0 0 5.5rem !important; }
  .st-key-topbar [data-testid="stColumn"]:nth-child(4) { flex: 1 1 0 !important; }
  .pg-head h1 { font-size: 2.5rem !important; } .pg-hero h1 { font-size: 2.9rem !important; }
  [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { margin-left: 8%; }
  [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) { margin-right: 0; }
}
@media (max-width: 560px) {
  .st-key-dock button p { display: none; }
  .st-key-dock { max-width: calc(100% - 20px); }
  .pg-kpi .v { font-size: 2.3rem; }
}
/* ---- dark mode: the page turns to deep ink; coloured slabs, tickets, badges and charts keep their light-mode inks
   (each is a "light island" that restores the light variables inside it) */
html.pg-dark { --ink: #F1ECDF; --ink-2: #C9C5B9; --muted: #9C9DAC; --line: rgba(241,236,223,.17); --ivory: #0B0D1C; --ivory-2: #1D2038;
  --paper: #151830; --coral-2: #3A1F28; --edge: 2px solid #D9D3C4; --hard: 5px 5px 0 #000; --hard-sm: 3px 3px 0 #000; color-scheme: dark; }
html.pg-dark .stApp { background-color: #0B0D1C !important; background-image: radial-gradient(rgba(241,236,223,.07) 1px, transparent 1.2px) !important; }
html.pg-dark :is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-fit-cobalt-"], [class*="st-key-card-lime-"], [class*="st-key-card-fit-lime-"], [class*="st-key-card-coral-"], [class*="st-key-card-fit-coral-"], section[data-testid="stSidebar"], .st-key-dock, .pg-tk, .pg-badge, .pg-prio-high, .pg-prio-medium, .pg-prio-low, .pg-role, .pg-sticker, .pg-stamp, .pg-ribbon > div:not(.zero), .pg-verdict, .pg-why .chips span, .pg-days .today b, .pg-empty .ico, .pg-numcard .ico, .pg-howto li::before, .pg-avatars span, [data-testid="stAlertContainer"], [data-testid="stChatInputSubmitButton"], [data-testid="stChatMessageAvatarAssistant"], [data-testid="stToast"], [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"], :is([data-baseweb="tab"], [data-testid="stTab"])[aria-selected="true"], [data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]), .st-key-auth-panel, [class*="st-key-portal-"], .lp-band, .lp-slab, .lp-links a:hover, .lp-track .fork div, .pg-mast .fig, [data-testid="stVegaLiteChart"], .pg-theme-btn) { --ink: #0A0C1B; --ink-2: #4A4D5E; --muted: #686B7A; --line: rgba(10,12,27,.14); --ivory: #F4EEE1; --ivory-2: #EBE3D1; --paper: #FFFDF6; --coral-2: #FFE1DC; --edge: 2px solid #0A0C1B; --hard: 5px 5px 0 #0A0C1B; --hard-sm: 3px 3px 0 #0A0C1B; }
html.pg-dark :is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], .lp-band.ink) { background: #05060F !important; border-color: #3A3E5C !important; }
html.pg-dark :is([class*="st-key-card-ink-"], [class*="st-key-card-fit-ink-"], [class*="st-key-art-"], [class*="st-key-card-cobalt-"], [class*="st-key-card-lime-"], [class*="st-key-card-coral-"], [class*="st-key-portal-"], .st-key-auth-panel) { border-color: #D9D3C4 !important; }
html.pg-dark section[data-testid="stSidebar"], html.pg-dark section[data-testid="stSidebar"] > div:first-child { background: #05060F !important; border-right: 1.5px solid #23263F !important; }
html.pg-dark .st-key-dock { background: #05060F; border-color: #3A3E5C; }
html.pg-dark :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) { background: var(--lime) !important; border-color: #0A0C1B !important; box-shadow: 3px 3px 0 var(--cobalt) !important; }
html.pg-dark :is([data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"]) :is(p, span) { color: #0A0C1B !important; }
html.pg-dark .st-key-dock button[data-testid="stBaseButton-primary"] { box-shadow: none !important; }
html.pg-dark :is([data-baseweb="tab"], [data-testid="stTab"])[aria-selected="true"] { background: var(--lime) !important; }
html.pg-dark :is([data-baseweb="tab"], [data-testid="stTab"])[aria-selected="true"] p { color: #0A0C1B !important; }
html.pg-dark [data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]) { background: var(--lime) !important; }
html.pg-dark [data-testid="stButtonGroup"] button[data-variant]:is([aria-checked="true"], [data-selected="true"], [aria-pressed="true"]) :is(p, span) { color: #0A0C1B !important; }
html.pg-dark :is(input, textarea) { color: var(--ink) !important; -webkit-text-fill-color: var(--ink); caret-color: var(--lime); }
html.pg-dark [data-baseweb="select"] div { color: var(--ink); }
html.pg-dark [data-baseweb="select"] > div, html.pg-dark [data-baseweb="select"] > div * { background-color: transparent; }
html.pg-dark [data-baseweb="select"] > div { background: var(--paper) !important; }
html.pg-dark [data-baseweb="select"] svg { fill: var(--ink); color: var(--ink); }
html.pg-dark [data-baseweb="popover"] [role="listbox"], html.pg-dark [data-baseweb="menu"] { background: var(--paper) !important; }
html.pg-dark [data-baseweb="popover"] [role="option"] { color: var(--ink) !important; }
html.pg-dark [data-baseweb="popover"] [role="option"]:hover, html.pg-dark [data-baseweb="popover"] [aria-selected="true"][role="option"] { background: var(--ivory-2) !important; }
html.pg-dark [data-testid="stCheckbox"] label > span:first-child, html.pg-dark [data-baseweb="checkbox"] > div:first-child { border-color: var(--ink) !important; }
html.pg-dark .pg-days .today b { color: #0A0C1B; }
:is([data-testid="stSelectbox"], [data-testid="stMultiSelect"]) [role="group"] { background: var(--paper) !important; border: var(--edge) !important; border-radius: var(--r-sm) !important; }
:is([data-testid="stSelectbox"], [data-testid="stMultiSelect"]) [role="group"]:focus-within { box-shadow: 0 0 0 4px var(--lime) !important; }
:is([data-testid="stSelectbox"], [data-testid="stMultiSelect"]) [role="group"] button svg { fill: var(--ink); color: var(--ink); }
html.pg-dark :is(.react-aria-Popover, [role="listbox"]) { background: var(--paper) !important; color: var(--ink) !important; border-color: var(--ink) !important; }
html.pg-dark [role="listbox"] [role="option"] { color: var(--ink) !important; }
html.pg-dark [role="listbox"] [role="option"]:is(:hover, [data-focused], [data-selected="true"], [aria-selected="true"]) { background: var(--ivory-2) !important; }
html.pg-dark .st-key-hero-emp button :is(p, span) { color: #0A0C1B !important; }
html.pg-dark [data-testid="stMain"] label :is(p, span, div) { color: var(--ink); }
html.pg-dark [data-testid="stExpander"] summary :is(p, span) { color: var(--ink); }
html.pg-dark [data-testid="stExpander"] summary:hover { background: var(--ivory-2); }
html.pg-dark :is([data-testid="stVegaLiteChart"], [data-testid="stDataFrame"]) { background: #F4EEE1; border-radius: 10px; padding: 6px; }
html.pg-dark [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: #05060F; border-color: #3A3E5C; }
html.pg-dark [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) :is(p, li, span) { color: #F1ECDF !important; }
html.pg-dark [data-testid="stChatMessageAvatarUser"] { background: var(--lime) !important; color: #0A0C1B !important; }
html.pg-dark .pg-ribbon > div.zero { background: repeating-linear-gradient(135deg, transparent 0 6px, rgba(241,236,223,.12) 6px 7.5px), var(--paper); }
html.pg-dark .pg-ladder .rail span { background: repeating-linear-gradient(135deg, transparent 0 5px, rgba(10,12,27,.3) 5px 6.5px), #8E9BFF; }
html.pg-dark .pg-ladder .r.ok .rail span { background: var(--lime); }
html.pg-dark .pg-figs b { box-shadow: inset 0 -.2em 0 var(--tone, transparent); }
html.pg-dark .pg-figs.dark b { color: var(--lime); }
/* the logo: transparent, the light version on ivory and the dark version on ink */
img.pg-logo { display: block; width: auto; background: none; }
html.pg-dark img.pg-logo { content: url("app/static/pragyaan-logo-full-dark.png?v=red"); }
:is([data-testid="stSidebarLogo"], [data-testid="stHeaderLogo"]) { height: 104px !important; max-height: none !important; width: auto !important; }
[data-testid="stSidebarHeader"] { height: auto !important; min-height: 0 !important; padding-top: 1rem !important; align-items: flex-start !important; }
[data-testid="stSidebarCollapsedControl"] :is(img, [data-testid="stHeaderLogo"]) { height: 44px !important; }
/* the theme switch */
.pg-theme-btn { display: inline-flex; align-items: center; gap: .4rem; height: 2.5rem; padding: 0 .85rem; border-radius: 10px; border: 2px solid #0A0C1B;
  background: #FFFDF6; color: #0A0C1B; font: 650 .88rem var(--text); cursor: pointer; box-shadow: 3px 3px 0 #0A0C1B; transition: transform .18s var(--ease), background .18s ease; }
.pg-theme-btn:hover { background: var(--lime); transform: translate(-1px, -1px); }
.pg-theme-btn:active { transform: translate(2px, 2px); box-shadow: none; }
.pg-theme-btn .material-symbols-rounded { font-size: 19px; }
.pg-theme-btn .l, html.pg-dark .pg-theme-btn .d { display: none; }
html.pg-dark .pg-theme-btn .l { display: inline; }
html.pg-dark .pg-theme-btn { background: #05060F; color: var(--lime); border-color: #D9D3C4; box-shadow: 3px 3px 0 var(--cobalt); }
html.pg-dark .pg-theme-btn:hover { background: #1D2038; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } .pg-reveal::after { display: none !important; } }
</style>
"""

# Pointer magnetism, count-up numbers and scroll reveals. Runs once per browser tab (guarded),
# watches the page for new elements because Streamlit re-renders as people work.
_JS = """
<span class="pg-js"></span>
<script>
(function () {
  if (window.__pragyaan_fx) return; window.__pragyaan_fx = true;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduce && 'IntersectionObserver' in window) document.documentElement.classList.add('pg-fx');
  // light / dark theme: the saved choice, else the system setting; the switch flips it and remembers it
  var root = document.documentElement, saved = null;
  try { saved = localStorage.getItem('pragyaan-theme'); } catch (e) {}
  var sysDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  function setTheme(dark) {
    root.classList.toggle('pg-dark', dark);
    document.querySelectorAll('.pg-theme-btn').forEach(function (b) {
      b.setAttribute('aria-pressed', dark ? 'true' : 'false');
      b.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    });
  }
  setTheme(saved ? saved === 'dark' : !!sysDark);
  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest ? e.target.closest('.pg-theme-btn') : null;
    if (!b) return;
    var dark = !root.classList.contains('pg-dark');
    setTheme(dark);
    try { localStorage.setItem('pragyaan-theme', dark ? 'dark' : 'light'); } catch (err) {}
  });
  var MAG = '[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"], [data-testid="stBaseButton-secondary"], [class*="st-key-tap-"], .pg-magnet';
  var cur = null;
  function clear() { if (cur) { cur.style.removeProperty('--mx'); cur.style.removeProperty('--my'); cur = null; } }
  document.addEventListener('pointermove', function (e) {
    if (reduce || e.pointerType === 'touch') return;
    var el = e.target && e.target.closest ? e.target.closest(MAG) : null;
    if (el && el.closest('.st-key-dock')) el = null;
    if (cur && cur !== el) clear();
    if (!el) return;
    var r = el.getBoundingClientRect();
    var dx = (e.clientX - (r.left + r.width / 2)) / Math.max(r.width, 1);
    var dy = (e.clientY - (r.top + r.height / 2)) / Math.max(r.height, 1);
    var k = el.matches('[class*="st-key-tap-"]') ? 5 : 7;
    el.style.setProperty('--mx', (dx * k).toFixed(1) + 'px'); el.style.setProperty('--my', (dy * k * 0.8).toFixed(1) + 'px'); cur = el;
  }, { passive: true });
  document.addEventListener('pointerleave', clear);
  function fmt(n, d) { return n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function count(el) {
    var to = parseFloat(el.getAttribute('data-to')), d = parseInt(el.getAttribute('data-dec') || '0', 10), suf = el.getAttribute('data-suf') || '';
    if (!isFinite(to)) return;
    if (reduce) { el.textContent = fmt(to, d) + suf; return; }
    var t0 = performance.now(), dur = 1200;
    function step(t) { var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = fmt(to * e, d) + suf; if (k < 1) requestAnimationFrame(step); }
    requestAnimationFrame(step);
  }
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (x) {
      if (!x.isIntersecting) return;
      var el = x.target; io.unobserve(el);
      if (el.classList.contains('pg-count')) count(el); else el.classList.add('in');
    });
  }, { threshold: 0, rootMargin: '0px 0px -22% 0px' });
  function scan() {
    document.querySelectorAll('.pg-theme-btn:not([aria-pressed])').forEach(function (b) {
      var dark = root.classList.contains('pg-dark');
      b.setAttribute('aria-pressed', dark ? 'true' : 'false');
      b.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
    });
    document.querySelectorAll('.pg-count:not([data-pg-seen]), .pg-reveal:not([data-pg-seen])').forEach(function (el) {
      el.setAttribute('data-pg-seen', '1'); io.observe(el);
    });
  }
  new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
  scan();
})();
</script>
"""


def inject_css(calm: bool = True) -> None:
    """Global stylesheet plus the small interaction script (magnetic buttons, count-up numbers, reveals)."""
    st.markdown(_CSS, unsafe_allow_html=True)
    try:
        st.html(_JS, unsafe_allow_javascript=True)
    except TypeError:  # older Streamlit without script support: everything still works, just without the motion
        pass


def words(text: str) -> str:
    """Wrap each word so headlines rise word by word out of a mask on page load."""
    parts = text.split()
    return "".join(f'<span class="pg-w"><span style="--i:{i}">{esc(w)}</span></span>{" " if i < len(parts) - 1 else ""}'
                   for i, w in enumerate(parts))


def count(value: float | int, *, dec: int = 0, suffix: str = "") -> str:
    """A number that counts up from zero when it scrolls into view (the final value is in the markup)."""
    shown = f"{value:,.{dec}f}{suffix}"
    return f'<span class="pg-count" data-to="{value}" data-dec="{dec}" data-suf="{esc(suffix)}">{esc(shown)}</span>'


def sticker(html_inner: str, tone: str = "lime", rot: float = -4, delay: float = .5, style: str = "") -> str:
    """A rotated colour label that drops onto the composition (trusted inner HTML)."""
    return (f'<span class="pg-sticker {tone}" style="--rot:{rot}deg;--d:{delay}s;{style}">{html_inner}</span>')


SPARK_SVG = ('<svg width="34" height="34" viewBox="0 0 24 24" aria-hidden="true">'
             '<path d="M12 1.5l2.2 6.3 6.3-2.2-3.8 5.4 5.8 3.1-6.6.9.9 6.6-4.8-4.6-4.8 4.6.9-6.6-6.6-.9 5.8-3.1-3.8-5.4 6.3 2.2z" '
             'fill="#D4FF3A" stroke="#0A0C1B" stroke-width="1.6" stroke-linejoin="round"/></svg>')


def sparkle() -> str:
    """The lime burst used where the assistant introduces itself."""
    return f'<span class="pg-spark" aria-hidden="true">{SPARK_SVG}</span>'


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
    st.markdown(f'<div class="pg-head"><h1>{words(title)}</h1>{sub}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, note: str | None = None, *, icon_name: str | None = None,
        tone: str | None = None) -> None:
    ic = icon(icon_name) if icon_name else ""
    nt = f'<div class="n">{esc(note)}</div>' if note else ""
    style = f' style="--pg-tone:{tone};--pg-on:{on_color(tone)}"' if tone else ""
    cls = "pg-kpi pg-fill accent" if tone else "pg-kpi pg-fill"
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
    """Three colour blocks sized by the model's probabilities; the predicted class is solid, the others hatched."""
    segs = "".join(
        f'<span class="{"" if p == predicted else "off"}" title="{p}: {probs.get(p, 0):.0%}" '
        f'style="width:{max(probs.get(p, 0) * 100, 0.5):.1f}%;background-color:{PRIORITY_COLORS[p]}"></span>'
        for p in ("low", "medium", "high")
    )
    legend = "".join(
        f'<span><i style="background:{PRIORITY_COLORS[p]}"></i>'
        f'{p.capitalize()} {"<b>" if p == predicted else ""}{probs.get(p, 0):.0%}{"</b>" if p == predicted else ""}</span>'
        for p in ("low", "medium", "high")
    )
    return (f'<div class="pg-meter" role="img" aria-label="Priority probabilities: '
            f'{", ".join(f"{p} {probs.get(p, 0):.0%}" for p in ("low", "medium", "high"))}">{segs}</div>'
            f'<div class="pg-meter-legend">{legend}</div>')


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
    """Ink axes, dashed paper grid, ink-edged marks, theme fonts."""
    return (
        chart.configure(font="Instrument Sans", background="transparent")
        .configure_view(stroke=None)
        .configure_axis(labelColor=INK_2, titleColor=INK, labelFontSize=12, titleFontSize=12, labelFontWeight=500,
                        titleFontWeight=700, gridColor=GRID, gridDash=[3, 3], domainColor=INK, domainWidth=2,
                        tickColor=INK, tickWidth=1.5)
        .configure_legend(orient="top", title=None, labelColor=INK, labelFontSize=12, labelFontWeight=600, labelLimit=320,
                          symbolSize=140, symbolStrokeColor=INK, symbolStrokeWidth=1.5, symbolType="square")
        .configure_title(color=INK, fontSize=14, fontWeight=700, anchor="start", font="Bricolage Grotesque")
        .configure_bar(stroke=INK, strokeWidth=1.5)
        .configure_arc(stroke=INK, strokeWidth=2)
        .configure_line(strokeWidth=3)
        .configure_point(stroke=INK, strokeWidth=1.5, filled=True, size=70)
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


STAGE_COLORS = {"suggested": LIME, "escalated": CORAL, "assigned": COBALT, "in_progress": "#7C8BFF",
                "resolved": "#4D7A00", "closed": "#CFC5AE"}
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


def _explain_in_chat(query: str, source: str, text: str) -> None:
    """Open the AI Assistant with this fix loaded, asking for a step-by-step explanation."""
    st.session_state["pending_q"] = f"Explain this fix step by step for my problem: {clip(query, 200)}"
    st.session_state["pending_ctx"] = {"source": source, "text": text[:2500]}
    go("assistant")


def _steps_html(text: str) -> str:
    """A solution as HTML: numbered lines become a list, everything else a paragraph (all escaped)."""
    items, paras = [], []
    for line in (text or "").replace("**", "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)[.)]\s+(.*)$", line)
        if m:
            items.append(f"<li>{esc(m.group(2))}</li>")
        elif items:
            items[-1] = items[-1][:-5] + f" {esc(line)}</li>"
        else:
            paras.append(f"<p>{esc(line)}</p>")
    return "".join(paras) + (f"<ol>{''.join(items)}</ol>" if items else "")


def _match_line(pct: int, thr: int, shared: list[str], what: str = "similar to your problem") -> str:
    tone = LIME if pct >= thr + 10 else (COBALT if pct >= thr else CORAL)
    words = "".join(f"<span>{esc(w)}</span>" for w in shared[:4])
    return (f'<div class="pg-mline" style="--why:{tone}"><b>{pct}%</b><span class="t">{esc(what)}</span>'
            f'<span class="bar" role="img" aria-label="{pct}% similar; {thr}% needed"><span style="width:{max(2, min(pct, 100))}%"></span>'
            f'<i style="left:{thr}%"></i></span><small>{thr}% needed</small>'
            + (f'<span class="w">Both mention {words}</span>' if words else "") + "</div>")


def priority_strip(sev: dict | None) -> str:
    """The priority model's estimate for the employee's problem, in one plain line."""
    if not sev:
        return ""
    lab = str(sev.get("label") or "medium").lower()
    conf = sev.get("confidence")
    sure = f"{round(conf * 100)}% sure" if conf is not None else ""
    words = "".join(f"<span>{esc(t)}</span>" for t in (sev.get("terms") or [])[:4])
    meaning = {"high": "it would be handled first", "medium": "it would be handled in the normal queue",
               "low": "it can wait in the backlog"}.get(lab, "")
    return (f'<div class="pg-sev"><span class="t">Priority of your problem</span>{priority_badge(lab)}'
            f'<span class="m">{esc(sure)}{", " if sure and meaning else ""}{esc(meaning)}</span>'
            + (f'<span class="w">Because of {words}</span>' if words else "")
            + '<small>Predicted by the priority model from the words you used</small></div>')


def solution_cards(res: dict, key: str, pick_label: str | None = None,
                   explain: bool = False) -> tuple[int, dict | None]:
    """Render existing solution recommendations from triage.find_solutions.

    The priority of the problem comes first, then the best matching solved ticket with its solution in plain steps,
    then other similar tickets and company documents. With `pick_label`, each recommendation gets a button (e.g.
    "This solved my problem"); the clicked recommendation is returned so the page can close the issue as
    self-resolved. With `explain`, each gets "Explain this step by step", which opens the AI Assistant.
    Returns (number shown, picked recommendation or None)."""
    from copilot.config import DOC_SIM_THRESHOLD, SIM_THRESHOLD
    from copilot.explain import shared_terms, solution_steps
    from copilot.retrieval import get_ticket_text

    for err in res.get("errors") or []:
        st.caption(err)
    query = res.get("query") or ""
    if res.get("severity") and query:
        st.markdown(priority_strip(res["severity"]), unsafe_allow_html=True)
    thr = round(SIM_THRESHOLD * 100)
    n, picked = 0, None

    def actions(h: dict, kid: str, source: str, text: str) -> None:
        nonlocal picked
        with st.container(key=f"rec-{key}-{kid}-acts", horizontal=True, gap="small"):
            if pick_label and st.button(pick_label, key=f"{key}-pick-{kid}", icon=":material/check_circle:",
                                        type="primary"):
                picked = h
            if explain and has_page("assistant") and st.button("Explain this step by step", key=f"{key}-explain-{kid}",
                                                               icon=":material/forum:", type="secondary"):
                _explain_in_chat(query, source, text)

    tickets = res.get("tickets") or []
    for i_t, h in enumerate(tickets[:1]):
        n += 1
        past = get_ticket_text(h["ticket_id"]) or h["snippet"]
        sol = solution_steps(query, past, h["answer"])
        pct = round(h["similarity"] * 100)
        with st.container(key=f"rec-{key}-t-{h['ticket_id']}"):
            by = (f"Written by {esc(sol['method'])} from support's reply to that ticket" if sol["method"] else
                  "Support's reply to that ticket" + (f" (language model unavailable right now: {esc(sol['llm_error'])})"
                                                      if sol["llm_error"] else ""))
            st.markdown(
                f"<div>{soft_badge('Best match')} &nbsp;<span class='pg-muted'>Solved ticket #{h['ticket_id']}</span></div>"
                + _match_line(pct, thr, shared_terms(query, f"{past} {h['answer']}"))
                + f"<div class='pg-past'><b>Similar problem</b>{esc(clip(past, 220))}</div>"
                + f"<div class='pg-fixsol'><b>Solution</b>{_steps_html(sol['text'])}<small>{by}</small></div>",
                unsafe_allow_html=True)
            if sol["method"]:
                with st.expander("Support's original reply"):
                    st.markdown(f'<div class="pg-solution">{esc(clip(h["answer"], 900))}</div>', unsafe_allow_html=True)
            actions(h, f"t-{h['ticket_id']}", f"the fix from solved ticket #{h['ticket_id']}", sol["text"])
    if len(tickets) > 1:
        with st.expander(f"Other similar solved tickets ({len(tickets) - 1})", icon=":material/history:"):
            for h in tickets[1:]:
                n += 1
                with st.container(key=f"rec-{key}-t-{h['ticket_id']}"):
                    st.markdown(f"<div><span class='pg-muted'>Solved ticket #{h['ticket_id']}</span></div>"
                                + _match_line(round(h["similarity"] * 100), thr, [])
                                + f"<div class='pg-past'><b>Similar problem</b>{esc(clip(h['snippet'], 180))}</div>"
                                + f'<div class="pg-solution">{esc(clip(h["answer"], 600))}</div>', unsafe_allow_html=True)
                    actions(h, f"t-{h['ticket_id']}", f"the fix from solved ticket #{h['ticket_id']}", h["answer"])
    docs = res.get("documents") or []
    if docs:
        st.markdown("<div class='pg-past' style='margin-top:.6rem'><b>From your company documents</b></div>",
                    unsafe_allow_html=True)
    for i, d in enumerate(docs):
        n += 1
        with st.container(key=f"rec-{key}-d-{i}"):
            a, b = st.columns([5, 1.2], vertical_alignment="center")
            a.markdown(f"<div>{soft_badge('Knowledge Hub')} &nbsp;<b>{esc(d['title'])}</b></div>"
                       + _match_line(round(d["similarity"] * 100), round(DOC_SIM_THRESHOLD * 100), [],
                                     "relevant to your problem")
                       + f"<div class='pg-muted' style='margin-top:.3rem'>{esc(clip(d['text'], 260))}</div>",
                       unsafe_allow_html=True)
            if has_page("knowledge") and b.button("Open", key=f"{key}-doc-{i}-{d['doc_id']}", type="tertiary"):
                st.session_state["kh_open"] = d["doc_id"]
                go("knowledge")
            actions(d, f"d-{i}-{d['doc_id']}", f"the company document “{d['title']}”", d["text"])
    return n, picked


# ---------------------------------------------------------------- glass compositions

def hero(greeting: str, title: str, text: str | None = None, center: bool = False) -> None:
    """Oversized opening statement of a workspace page."""
    p = f"<p>{esc(text)}</p>" if text else ""
    st.markdown(f'<div class="pg-hero{" center" if center else ""}"><div class="hi">{esc(greeting)}</div>'
                f'<h1>{words(title)}</h1>{p}</div>', unsafe_allow_html=True)


def number_card(value: str, label: str, icon_name: str) -> str:
    """Big light numeral with its round icon on the right and the caption underneath (inside a card)."""
    return (f'<div class="pg-numcard"><div class="pg-big">{esc(value)}</div><span class="ico">{icon(icon_name)}</span></div>'
            f'<div class="pg-numlbl">{esc(label)}</div>')


def stat_rows(items: list[tuple[str, object]]) -> str:
    """Label / value rows separated by hairlines (for small figure lists inside a card)."""
    lis = "".join(f"<li><span>{esc(str(k))}</span><b>{esc(str(v))}</b></li>" for k, v in items)
    return f'<ul class="pg-rows">{lis}</ul>'


def howto(steps: list[str]) -> str:
    """Numbered steps. Each step is trusted HTML written in the page (may contain <b>)."""
    return '<ol class="pg-howto">' + "".join(f"<li><div>{s}</div></li>" for s in steps) + "</ol>"


def card_head(title: str, action: str | None = None, *, key: str, icon_name: str | None = None) -> bool:
    """A card's title row with an optional small action on the far right. Returns True when it was clicked."""
    with st.container(key=f"head-{key}", horizontal=True, vertical_alignment="center", wrap=False):
        st.markdown(f"##### {title}", width="stretch")
        if action:
            return st.button(action, key=key, type="tertiary", icon=f":material/{icon_name}:" if icon_name else None,
                             icon_position="right")
    return False


def _why_text(text: str) -> str:
    """LLM explanation as safe HTML; a trailing "Check:" line gets its own highlighted box."""
    body, chk = text.strip(), ""
    m = re.search(r"(?im)^\s*\**check:?\**\s*(.+)$", body)
    if m:
        chk = m.group(1).strip()
        body = (body[:m.start()] + body[m.end():]).strip()
    html_body = esc(body.replace("**", "")).replace("\n", "<br>")
    if chk:
        html_body += f'<span class="chk"><b>Check:</b> {esc(chk.replace("**", ""))}</span>'
    return html_body


def why_panel(ex: dict | None, title: str = "Why this answer") -> str:
    """Explainability panel for a suggested answer or solution (from copilot.explain.explain_match)."""
    if not ex:
        return ""
    pct, thr = int(ex.get("pct") or 0), int(ex.get("threshold_pct") or 0)
    tone = LIME if pct >= thr + 10 else (COBALT if pct >= thr else CORAL)
    chips = "".join(f"<span>{esc(w)}</span>" for w in ex.get("shared") or [])
    chips = f'<div class="chips">Words in common {chips}</div>' if chips else ""
    if ex.get("text"):
        body, by = _why_text(ex["text"]), f"Explained by {esc(ex.get('method') or 'the language model')} from the two texts and the score"
    else:
        body = esc(ex.get("summary") or "")
        by = (f"Language model unavailable right now ({esc(ex['llm_error'])}), so this is explained from the similarity score"
              if ex.get("llm_error") else "Explained from the similarity score (no language model connected)")
    return (f'<div class="pg-why" style="--why:{tone}"><div class="hd"><span class="t">{esc(title)}</span>'
            f'<span class="pct">{pct}%<small>match</small></span></div>'
            f'<div class="bar" role="img" aria-label="{pct}% similar; {thr}% needed"><span style="width:{max(2, min(pct, 100))}%"></span>'
            f'<i style="left:{thr}%" data-l="{thr}% needed"></i></div>'
            f'<div class="lv"><b>{esc(ex.get("level") or "")}</b>, {esc(ex.get("source") or "")}</div>'
            f'{chips}<p class="x">{body}</p><div class="by">{by}</div></div>')


def escalation_panel(ex: dict | None) -> str:
    """Why a question went to a Senior Analyst, and why it got its priority (copilot.explain.explain_escalation)."""
    if not ex:
        return ""
    pct, thr = int(ex.get("pct") or 0), int(ex.get("threshold_pct") or 0)
    lab = str(ex.get("label") or "medium")
    conf = f", {ex['confidence_pct']}% probability" if ex.get("confidence_pct") is not None else ""
    chips = "".join(f"<span>{esc(w)}</span>" for w in ex.get("terms") or [])
    chips = f'<div class="chips">Priority signals {chips}</div>' if chips else ""
    if ex.get("text"):
        body, by = _why_text(ex["text"]), f"Explained by {esc(ex.get('method') or 'the language model')} from the scores"
    else:
        body = esc(ex.get("summary") or "")
        by = "Explained from the similarity score and the priority model" + (
            f" (language model unavailable right now: {esc(ex['llm_error'])})" if ex.get("llm_error") else "")
    return (f'<div class="pg-why esc" style="--why:{CORAL}"><div class="hd"><span class="t">Why it went to a Senior Analyst</span>'
            f'<span class="pct">{pct}%<small>best match</small></span></div>'
            f'<div class="bar" role="img" aria-label="{pct}% similar; {thr}% needed"><span style="width:{max(2, min(pct, 100))}%"></span>'
            f'<i style="left:{thr}%" data-l="{thr}% needed to answer"></i></div>'
            f'<div class="lv">Priority {priority_badge(lab)}{esc(conf)}</div>'
            f'{chips}<p class="x">{body}</p><div class="by">{by}</div></div>')


def ticket_match_explanation(problem: str, match_ticket_id: int | None, solution: str | None,
                             similarity: float | None, *, use_llm: bool = True) -> dict | None:
    """Explanation for a recommended solution taken from a resolved ticket (ticket pages)."""
    if similarity is None or not solution:
        return None
    from copilot.explain import explain_match
    from copilot.retrieval import get_ticket_text

    matched = get_ticket_text(match_ticket_id) if match_ticket_id else None
    src = f"resolved ticket #{match_ticket_id}" if match_ticket_id else "a resolved ticket"
    return explain_match(problem, matched, solution, float(similarity), source=src, use_llm=use_llm)


def label(text: str) -> str:
    return f'<div class="pg-label">{esc(text)}</div>'


def greeting(name: str) -> str:
    h = datetime.now().hour
    part = "Good morning" if h < 12 else ("Good afternoon" if h < 17 else "Good evening")
    return f"{part}, {(name or '').split(' ')[0]}"


def priority_dial(counts: dict[str, int], center_label: str = "open", size: int = 168, stacked: bool = False) -> str:
    """Thick donut of tickets by priority (real counts), ink-edged segments, total in the centre; every segment
    is also listed with its number, so colour never carries meaning alone."""
    import math

    total = sum(int(counts.get(p, 0)) for p in PRIORITY_ORDER)
    cx, sw = size / 2, size * 0.17
    r = size / 2 - sw / 2 - 3
    segs, a0 = [], -90.0
    for p in PRIORITY_ORDER:
        n = int(counts.get(p, 0))
        if not n or not total:
            continue
        sweep = 360 * n / total
        a1 = a0 + sweep
        if sweep >= 359.9:
            segs.append(f'<circle cx="{cx}" cy="{cx}" r="{r:.1f}" fill="none" stroke="{PRIORITY_COLORS[p]}" stroke-width="{sw:.1f}"><title>{p.capitalize()}: {n}</title></circle>')
        else:
            ro, ri = r + sw / 2, r - sw / 2
            def pt(rad: float, ang: float) -> str:
                return f"{cx + rad * math.cos(math.radians(ang)):.2f} {cx + rad * math.sin(math.radians(ang)):.2f}"
            large = 1 if sweep > 180 else 0
            d = (f"M{pt(ro, a0)} A{ro:.2f} {ro:.2f} 0 {large} 1 {pt(ro, a1)} L{pt(ri, a1)} "
                 f"A{ri:.2f} {ri:.2f} 0 {large} 0 {pt(ri, a0)} Z")
            segs.append(f'<path d="{d}" fill="{PRIORITY_COLORS[p]}" style="stroke:var(--ink)" stroke-width="2" stroke-linejoin="round">'
                        f'<title>{p.capitalize()}: {n}</title></path>')
        a0 = a1
    ring = (f'<circle cx="{cx}" cy="{cx}" r="{r + sw / 2:.1f}" fill="none" style="stroke:var(--ink)" stroke-width="2"/>'
            f'<circle cx="{cx}" cy="{cx}" r="{r - sw / 2:.1f}" style="fill:var(--paper);stroke:var(--ink)" stroke-width="2"/>')
    track = f'<circle cx="{cx}" cy="{cx}" r="{r:.1f}" fill="none" style="stroke:var(--ivory-2)" stroke-width="{sw:.1f}"/>'
    centre = (f'<text x="{cx}" y="{cx + size * 0.08:.1f}" text-anchor="middle" style="fill:var(--ink)" font-family="Bricolage Grotesque" '
              f'font-size="{size * 0.27:.0f}" font-weight="800" font-stretch="75%">{total}</text>'
              f'<text x="{cx}" y="{cx + size * 0.2:.1f}" text-anchor="middle" style="fill:var(--ink-2)" font-family="Instrument Sans" '
              f'font-size="12" font-weight="600">{esc(center_label)}</text>')
    svg = (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" '
           f'aria-label="Tickets by priority">{track}{"".join(segs)}{ring}{centre}</svg>')
    items = "".join(f'<li><i style="background:{PRIORITY_COLORS[p]}"></i>{p.capitalize()}<b>{int(counts.get(p, 0))}</b></li>'
                    for p in PRIORITY_ORDER)
    return f'<div class="pg-dial{" stack" if stacked else ""}">{svg}<ul>{items}</ul></div>'


def ring_gauge(pct: float | None, value_text: str, caption: str, *, size: int = 170, tone: str = COBALT) -> str:
    """A 270-degree dial with tick marks, an ink track, a coloured fill and a lime knob, for a 0-100 % measure."""
    import math

    r, c = size / 2 - 18, size / 2
    sweep, start = 270, 135
    frac = max(0.0, min(1.0, (pct or 0) / 100))
    arc_len = 2 * math.pi * r * sweep / 360
    ticks = []
    for k in range(11):
        a = math.radians(start + sweep * k / 10)
        r1, r2 = r + 11, r + (16 if k % 5 == 0 else 14)
        ticks.append(f'<line x1="{c + r1 * math.cos(a):.1f}" y1="{c + r1 * math.sin(a):.1f}" x2="{c + r2 * math.cos(a):.1f}" '
                     f'y2="{c + r2 * math.sin(a):.1f}" style="stroke:var(--ink)" stroke-width="{2 if k % 5 == 0 else 1.3}"/>')
    ang = math.radians(start + sweep * frac)
    kx, ky = c + r * math.cos(ang), c + r * math.sin(ang)
    knob = (f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="9" fill="{LIME}" style="stroke:var(--ink)" stroke-width="2.5"/>'
            if pct is not None else "")
    svg = (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="{esc(caption)}: {esc(value_text)}">'
        f'{"".join(ticks)}'
        f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" style="stroke:var(--ink)" stroke-width="16" stroke-linecap="round" '
        f'stroke-dasharray="{arc_len:.1f} 999" transform="rotate({start} {c} {c})"/>'
        f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" style="stroke:var(--ivory-2)" stroke-width="11" stroke-linecap="round" '
        f'stroke-dasharray="{arc_len:.1f} 999" transform="rotate({start} {c} {c})"/>'
        f'<circle cx="{c}" cy="{c}" r="{r:.1f}" fill="none" stroke="{tone}" stroke-width="11" stroke-linecap="round" '
        f'stroke-dasharray="{max(arc_len * frac, 0.1):.1f} 999" transform="rotate({start} {c} {c})"/>{knob}'
        f'<text x="{c}" y="{c + size * 0.09:.1f}" text-anchor="middle" style="fill:var(--ink)" font-family="Bricolage Grotesque" '
        f'font-size="{size * 0.24:.0f}" font-weight="800" font-stretch="75%">{esc(value_text)}</text></svg>')
    return f'<div class="pg-gauge">{svg}<div class="cap">{esc(caption)}</div></div>'


_AVATAR_TONES = [LIME, CORAL, COBALT, PAPER, "#7C8BFF", "#FFB4A8"]


def avatars(names: list[str], limit: int = 7) -> str:
    """Initials of real team members, overlapping like a member stack."""
    out = []
    for n in names[:limit]:
        ini = "".join(w[0] for w in n.split()[:2]).upper() or "?"
        tone = _AVATAR_TONES[sum(map(ord, n)) % len(_AVATAR_TONES)]
        out.append(f'<span title="{esc(n)}" style="background:{tone};color:{on_color(tone)}">{esc(ini)}</span>')
    if len(names) > limit:
        out.append(f'<span class="more">+{len(names) - limit}</span>')
    return f'<div class="pg-avatars">{"".join(out)}</div>'


def day_strip(rows: list[dict], days: int = 5) -> str:
    """Tickets raised per day for the last few days: one ink-edged column per day, stacked by priority."""
    from datetime import date, timedelta

    by_day: dict[str, dict[str, int]] = {}
    for r in rows:
        by_day.setdefault(r["day"], {})[r["priority"]] = int(r["n"])
    span = [date.today() - timedelta(days=i) for i in range(days - 1, -1, -1)]
    peak = max([sum(by_day.get(d.isoformat(), {}).values()) for d in span] + [1])
    cells = []
    for k, d in enumerate(span):
        c = by_day.get(d.isoformat(), {})
        total = sum(c.values())
        bars = "".join(f'<span style="height:{100 * c.get(p, 0) / peak:.1f}%;background:{PRIORITY_COLORS[p]};'
                       f'animation-delay:{k * 70}ms"></span>' for p in reversed(PRIORITY_ORDER) if c.get(p))
        label = "Today" if k == days - 1 else d.strftime("%a")
        title = ", ".join(f"{p}: {c.get(p, 0)}" for p in PRIORITY_ORDER)
        cells.append(f'<div class="{"today" if k == days - 1 else ""}" title="{esc(title)}"><em>{total}</em>'
                     f'<div class="col">{bars}</div><b>{label}</b><small>{d.strftime("%d %b")}</small></div>')
    return f'<div class="pg-days" style="--n:{days}">{"".join(cells)}</div>'


# ---------------------------------------------------------------- ticket stubs

_PRIO_SHORT = {"high": "High", "medium": "Med", "low": "Low"}


def ticket_stub(t: dict, *, compact: bool = False, show_requester: bool = False) -> str:
    """One ticket drawn as a physical ticket: a stub in its priority colour with the number set vertically,
    a perforated edge, then the stage, subject and when it was raised."""
    p = (t.get("priority") or "").lower()
    pcls = f"p-{p}" if p in PRIORITY_COLORS else ""
    who = (t.get("requester_name") or t.get("requester") or "") if show_requester else ""
    stage = stage_badge(t["stage"]) if t.get("stage") else ""
    foot_l = esc(f"Raised {ago(t.get('created_at'))}" + (f" by {who}" if who else ""))
    foot_r = esc(t.get("assignee_name") or "")
    return (f'<div class="pg-tk {pcls}{" compact" if compact else ""}">'
            f'<div class="stub"><span class="no">#{int(t["id"])}</span><span class="pr">{_PRIO_SHORT.get(p, "")}</span></div>'
            f'<div class="body"><div class="meta">{stage}</div><div class="sub">{esc(t.get("subject") or "")}</div>'
            f'<div class="foot"><span>{foot_l}</span><span>{foot_r}</span></div></div></div>')


def ticket_tap(t: dict, key: str, *, compact: bool = False, show_requester: bool = False, selected: bool = False,
               label: str | None = None) -> bool:
    """A ticket stub you can click anywhere on. Returns True when clicked."""
    with st.container(key=f"tap-{'on-' if selected else ''}{key}"):
        st.markdown(ticket_stub(t, compact=compact, show_requester=show_requester), unsafe_allow_html=True)
        return st.button(label or f"Open ticket #{t['id']}: {clip(t.get('subject'), 60)}", key=f"tapbtn-{key}")


# ---------------------------------------------------------------- page compositions

def masthead(kicker: str | None, title: str, sub: str | None = None, *, fig: float | int | None = None,
             fig_label: str = "", tone: str = LIME, dec: int = 0, suffix: str = "", rot: float = 2.5) -> None:
    """A page's opening: the headline on the left and, when given, one real number on a tilted colour block."""
    hi = f'<div class="hi">{esc(kicker)}</div>' if kicker else ""
    p = f"<p>{esc(sub)}</p>" if sub else ""
    figure = ""
    if fig is not None:
        figure = (f'<div class="fig" style="--tone:{tone};--on:{on_color(tone)};--rot:{rot}deg"><b>{count(fig, dec=dec, suffix=suffix)}</b>'
                  f'<span>{esc(fig_label)}</span></div>')
    st.markdown(f'<div class="pg-mast"><div>{hi}<h1>{words(title)}</h1>{p}</div>{figure}</div>', unsafe_allow_html=True)


def section(title: str, note: str | None = None) -> None:
    """A large in-page section title."""
    n = f"<span>{esc(note)}</span>" if note else ""
    st.markdown(f'<div class="pg-sec"><h3>{esc(title)}</h3>{n}</div>', unsafe_allow_html=True)


def ribbon(counts: dict[str, int], *, of: str = "open", vertical: bool = False) -> str:
    """The priority ribbon: one band split by how many tickets have each priority."""
    total = sum(counts.values())
    cells = []
    for k, p in enumerate(PRIORITY_ORDER):
        n = int(counts.get(p, 0))
        share = f"{n / total:.0%} of {of}" if total else ""
        cls = f"p-{p}" if n else "zero"
        cells.append(f'<div class="{cls}" style="--n:{max(n, 0.0001)};animation-delay:{k * 90}ms"><b>{count(n)}</b>'
                     f'<span>{p.capitalize()}<em>{share}</em></span></div>')
    label = ", ".join(f"{counts.get(p, 0)} {p}" for p in PRIORITY_ORDER)
    return (f'<div class="pg-ribbon{" v" if vertical else ""}" role="img" aria-label="Tickets by priority: {esc(label)}">'
            f'{"".join(cells)}</div>')


def figures(items: list[tuple], *, dark: bool = False) -> str:
    """Big typographic numbers in a row. Each item: (value_html, label[, note[, tone]]); value_html is trusted."""
    cells = []
    for it in items:
        v, lab = it[0], it[1]
        note = f"<small>{esc(it[2])}</small>" if len(it) > 2 and it[2] else ""
        tone = f' style="--tone:{it[3]}"' if len(it) > 3 and it[3] else ""
        cells.append(f"<div{tone}><b>{v}</b><span>{esc(lab)}</span>{note}</div>")
    return f'<div class="pg-figs{" dark" if dark else ""}" style="--n:{len(items)}">{"".join(cells)}</div>'


def ladder(rows: list[dict], threshold: float, *, caption: str = "needed to reuse the solution") -> str:
    """Similarity ladder. rows: {label, sub, sim (0..1)}; the threshold line runs through every rung."""
    thr = round(threshold * 100)
    out = []
    for k, r in enumerate(rows):
        pct = round(100 * float(r.get("sim") or 0))
        ok = pct >= thr
        out.append(f'<div class="r{" ok" if ok else ""}"><span class="id">{esc(r["label"])}<small>{esc(r.get("sub") or "")}</small></span>'
                   f'<div class="rail" role="img" aria-label="{pct}% similar, {thr}% {esc(caption)}">'
                   f'<span style="width:{max(2, min(pct, 100))}%;animation-delay:{k * 80}ms"></span><i style="left:{thr}%"></i></div>'
                   f'<span class="pct">{pct}%</span></div>')
    key = (f'<div class="key"><span><i style="background:{LIME}"></i>Reusable: {thr}% or more</span>'
           f'<span><i style="background:#D9DEFF"></i>Below {thr}%</span>'
           f'<span><i style="background:{CORAL}"></i>The {thr}% line, {esc(caption)}</span></div>')
    return f'<div class="pg-ladder">{"".join(out)}{key}</div>'


def hbars(rows: list[dict]) -> str:
    """Horizontal bars per person. rows: {name, sub, parts: [(value, colour, label)], value_html}."""
    peak = max([sum(v for v, _, _ in r["parts"]) for r in rows] + [1])
    out = []
    for k, r in enumerate(rows):
        segs = "".join(f'<span title="{esc(lab)}: {v}" style="width:{100 * v / peak:.1f}%;background:{c};animation-delay:{k * 70}ms"></span>'
                       for v, c, lab in r["parts"] if v)
        out.append(f'<div class="r"><span class="n">{esc(r["name"])}<small>{esc(r.get("sub") or "")}</small></span>'
                   f'<div class="b">{segs}</div><span class="v">{r.get("value_html", "")}</span></div>')
    return f'<div class="pg-hbars">{"".join(out)}</div>'


def verdict(priority: str, confidence: float, terms: list[str] | None = None, *, kicker: str = "Predicted priority") -> str:
    """The priority model's call as a block in that priority's colour, with its confidence and the words behind it."""
    p = priority if priority in PRIORITY_COLORS else "medium"
    why = ""
    if terms:
        why = '<div class="why">Words behind it ' + "".join(f"<span>{esc(t)}</span>" for t in terms[:6]) + "</div>"
    return (f'<div class="pg-verdict p-{p}"><div class="k">{esc(kicker)}</div><div class="w">{esc(p.capitalize())}</div>'
            f'<div class="c"><b>{count(round(confidence * 100), suffix="%")}</b><span>model confidence</span></div>{why}</div>')


THEME_SWITCH = ('<button type="button" class="pg-theme-btn" aria-label="Switch to dark mode">'
                '<span class="material-symbols-rounded d" aria-hidden="true">dark_mode</span><span class="d">Dark</span>'
                '<span class="material-symbols-rounded l" aria-hidden="true">light_mode</span><span class="l">Light</span></button>')


def theme_switch() -> None:
    """The light/dark switch. It runs in the browser and remembers the choice on this device."""
    st.markdown(THEME_SWITCH, unsafe_allow_html=True, width="content")
