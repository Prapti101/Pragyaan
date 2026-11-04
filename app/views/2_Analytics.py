"""Analytics: ticket trends, model statistics, assistant and workflow metrics, report export."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.automation import task_stats  # noqa: E402
from copilot.config import EVAL_RESULTS  # noqa: E402
from copilot.db import fetchall  # noqa: E402
from copilot.feedback import analytics_summary  # noqa: E402
from copilot.reports import corrections_csv, html_report, tasks_csv, tickets_csv  # noqa: E402
from copilot.triage import correction_pairs, ticket_stats  # noqa: E402

P = st.session_state["_pages"]
user = ui.require_role("analyst")

ui.page_header("Analytics & reports", "Ticket trends, how the priority model performs in daily use, assistant and workflow "
               "results. Everything here is computed from this installation's data.")

c1, c2, _ = st.columns([1.6, 1.2, 2.5], vertical_alignment="center")
period = c1.segmented_control("Period", ["7 days", "30 days", "90 days"], default="30 days", key="an_period",
                              label_visibility="collapsed") or "30 days"
days = int(period.split()[0])
include_archive = c2.toggle("Include archive tickets", value=False, key="an_arch",
                            help="Historical tickets imported from the knowledge base. They were part of the "
                                 "model's training data, so they are left out of model statistics.")
src = "" if include_archive else "AND source != 'archive'"

rows = fetchall(
    f"SELECT date(created_at, 'localtime') AS day, COALESCE(final_priority, predicted_priority) AS priority, "
    f"status, confidence, source, predicted_priority, final_priority FROM tickets "
    f"WHERE created_at >= datetime('now', ?) {src}",
    (f"-{days} days",),
)
df = pd.DataFrame(rows, columns=["day", "priority", "status", "confidence", "source", "predicted_priority",
                                 "final_priority"])
ts = ticket_stats(include_archive=include_archive)
a = analytics_summary()
ks = task_stats()

k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi(f"Tickets, last {days} days", f"{len(df):,}", f"{ts['total']:,} all time", icon_name="confirmation_number")
with k2:
    share = (df["priority"] == "high").mean() if len(df) else None
    ui.kpi("High priority share", f"{share:.0%}" if share is not None else "n/a",
           f"{int((df['priority'] == 'high').sum())} high-priority tickets" if len(df) else "No tickets in period",
           icon_name="priority_high")
with k3:
    manual = df[df["source"] == "manual"]
    agree = (manual["final_priority"].isna() | (manual["final_priority"] == manual["predicted_priority"])).mean() \
        if len(manual) else None
    ui.kpi("Model priority kept", f"{agree:.0%}" if agree is not None else "n/a",
           f"on {len(manual)} tickets triaged here" if len(manual) else "No tickets triaged here yet",
           icon_name="verified")
with k4:
    ui.kpi("Assistant answered", f"{a['auto_resolve_pct']}%", f"of {a['total']} questions, avg {a['avg_latency_ms']:.0f} ms",
           icon_name="forum")
st.write("")

tab_t, tab_m, tab_a, tab_x = st.tabs(["Tickets", "Model in use", "Assistant and workflow", "Export"], key="an_tabs")

ORDER = [p.capitalize() for p in ui.PRIORITY_ORDER]
COLOR = alt.Scale(domain=ORDER, range=[ui.PRIORITY_COLORS[p] for p in ui.PRIORITY_ORDER])

with tab_t:
    if df.empty:
        ui.empty_state("monitoring", f"No tickets in the last {days} days",
                       "Triage tickets on the Smart Triage page and their trends appear here.")
    else:
        left, right = st.columns([2.2, 1], gap="large")
        with left:
            with st.container(key="card-trend"):
                st.markdown("##### Tickets per day by priority")
                all_days = [(date.today() - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
                g = df.groupby(["day", "priority"]).size().rename("n").reset_index()
                full = pd.MultiIndex.from_product([all_days, ui.PRIORITY_ORDER], names=["day", "priority"])
                g = g.set_index(["day", "priority"]).reindex(full, fill_value=0).reset_index()
                g["Priority"] = g["priority"].str.capitalize()
                chart = alt.Chart(g).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2, width={"band": 0.65}).encode(
                    x=alt.X("day:O", title=None, axis=alt.Axis(labelAngle=0, labelExpr="slice(datum.value, 5)",
                                                              labelOverlap=True)),
                    y=alt.Y("sum(n):Q", title="Tickets", axis=alt.Axis(tickMinStep=1, format="d")),
                    color=alt.Color("Priority:N", sort=ORDER, scale=COLOR),
                    order=alt.Order("priority:N", sort="descending"),
                    tooltip=["day:O", "Priority:N", alt.Tooltip("n:Q", title="Tickets")],
                )
                ui.show_chart(chart.properties(height=260))
        with right:
            with st.container(key="card-mix"):
                st.markdown("##### Priority mix")
                mix = df["priority"].value_counts().reindex(ui.PRIORITY_ORDER, fill_value=0).rename("n").reset_index()
                mix["Priority"] = mix["priority"].str.capitalize()
                mix["share"] = mix["n"] / max(1, mix["n"].sum())
                base = alt.Chart(mix).encode(y=alt.Y("Priority:N", sort=ORDER, title=None),
                                             x=alt.X("n:Q", title="Tickets", axis=alt.Axis(tickMinStep=1, format="d")))
                b = base.mark_bar(cornerRadiusEnd=4, height=16).encode(
                    color=alt.Color("Priority:N", scale=COLOR, legend=None),
                    tooltip=["Priority:N", alt.Tooltip("n:Q", title="Tickets"), alt.Tooltip("share:Q", format=".0%", title="Share")])
                t = base.mark_text(align="left", dx=5, fontSize=12, color=ui.INK).encode(text=alt.Text("share:Q", format=".0%"))
                ui.show_chart((b + t).properties(height=120))
                st.markdown("##### Status")
                stc = df["status"].value_counts()
                for s in ["open", "in_progress", "resolved", "closed"]:
                    st.markdown(f"{ui.STATUS_LABELS[s]}: **{int(stc.get(s, 0))}**")

with tab_m:
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(key="card-conf"):
            st.markdown("##### Confidence of predictions")
            if manual.empty:
                st.caption("No tickets triaged here in this period.")
            else:
                cd = manual.copy()
                cd["Kept"] = cd["final_priority"].isna().map({True: "Kept by agent", False: "Corrected"})
                hist = alt.Chart(cd).mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2).encode(
                    x=alt.X("confidence:Q", bin=alt.Bin(step=0.1, extent=[0.3, 1.0]), title="Model confidence",
                            axis=alt.Axis(format=".0%")),
                    y=alt.Y("count():Q", title="Tickets", axis=alt.Axis(tickMinStep=1, format="d")),
                    color=alt.Color("Kept:N", scale=alt.Scale(domain=["Kept by agent", "Corrected"],
                                                              range=[ui.SERIES[0], ui.SERIES[1]])),
                    tooltip=[alt.Tooltip("count():Q", title="Tickets"), "Kept:N"],
                )
                ui.show_chart(hist.properties(height=220))
                st.caption(f"Average confidence {manual['confidence'].mean():.0%}. Corrections concentrated at low "
                           "confidence suggest a review threshold.")
    with right:
        with st.container(key="card-corr"):
            st.markdown("##### Manual corrections")
            pairs = correction_pairs()
            if not pairs:
                st.caption("No corrections yet. When agents change a predicted priority, the pattern shows here "
                           "and can be exported for retraining.")
            else:
                cp = pd.DataFrame(pairs)
                heat = alt.Chart(cp).encode(
                    x=alt.X("corrected:N", sort=["low", "medium", "high"], title="Corrected to", axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("predicted:N", sort=["low", "medium", "high"], title="Model predicted"),
                )
                cells = heat.mark_rect(cornerRadius=3, stroke="white", strokeWidth=2).encode(
                    color=alt.Color("n:Q", scale=alt.Scale(range=["#EEF4FC", "#2a78d6"]), legend=None),
                    tooltip=["predicted:N", "corrected:N", alt.Tooltip("n:Q", title="Tickets")])
                txt = heat.mark_text(fontSize=13, color=ui.INK).encode(text="n:Q")
                ui.show_chart((cells + txt).properties(height=200))
    with st.container(key="card-bench"):
        st.markdown("##### Offline benchmarks")
        try:
            sev = pd.read_csv(EVAL_RESULTS / "severity_comparison.csv")
            test = pd.read_csv(EVAL_RESULTS / "severity_test.csv")
            best = sev.loc[sev["macro_f1"].idxmax()]
            st.markdown(f"Priority model: **{best['model']}**, macro-F1 {best['macro_f1']:.3f} on validation and "
                        f"{test['macro_f1'].iloc[0]:.3f} on the held-out test set ({test['accuracy'].iloc[0]:.1%} accuracy), "
                        f"best of {len(sev)} algorithms compared.")
        except Exception:
            st.caption("Benchmark files not found in eval/results.")
        if st.button("Open model benchmarks", icon=":material/leaderboard:", key="an-open-bench"):
            st.switch_page(P["benchmarks"])

with tab_a:
    left, right = st.columns(2, gap="large")
    with left:
        with st.container(key="card-asst"):
            st.markdown("##### AI Assistant")
            st.markdown(f"Questions asked: **{a['total']}**  \nAnswered automatically: **{a['auto_resolve_pct']}%**  \n"
                        f"Average response: **{a['avg_latency_ms']:.0f} ms**  \n"
                        f"Feedback: **{a['thumbs_up']}** helpful, **{a['thumbs_down']}** not helpful")
            sev_e = a.get("escalations_by_severity") or {}
            if sev_e:
                order = ["low", "medium", "high"]
                d = pd.DataFrame({"severity": order, "count": [int(sev_e.get(k, 0)) for k in order]})
                base = alt.Chart(d).encode(y=alt.Y("severity:N", sort=order[::-1], title=None),
                                           x=alt.X("count:Q", title="Escalations", axis=alt.Axis(tickMinStep=1, format="d")))
                b = base.mark_bar(cornerRadiusEnd=4, height=16, color=ui.SERIES[0]).encode(
                    tooltip=[alt.Tooltip("count:Q", title="Escalations"), "severity:N"])
                t = base.mark_text(align="left", dx=5, fontSize=12, color=ui.INK).encode(text="count:Q")
                ui.show_chart((b + t).properties(height=120, title="Escalations by severity"))
    with right:
        with st.container(key="card-flow"):
            st.markdown("##### Workflow")
            sla = f"{ks['sla_met_pct']:.0f}% of {ks['sla_measured']}" if ks["sla_met_pct"] is not None else "n/a"
            st.markdown(f"Open tasks: **{ks['open']}**  \nOverdue: **{ks['overdue']}**  \n"
                        f"Completed: **{ks['done']}**  \nCompleted within deadline: **{sla}**")
    recent = a.get("recent") or []
    st.markdown("##### Latest assistant questions")
    if recent:
        rd = pd.DataFrame(recent)
        for col in ("severity_label", "thumbs", "intent"):
            if col in rd:
                rd[col] = rd[col].fillna("")
        st.dataframe(rd, hide_index=True, width="stretch", column_config={
            "id": st.column_config.NumberColumn("#", format="%d", width="small"),
            "question": st.column_config.TextColumn("Question", width="large"),
            "route": "Outcome", "intent": "Type",
            "confidence": st.column_config.ProgressColumn("Match", min_value=0.0, max_value=1.0, format="%.2f"),
            "severity_label": "Severity", "latency_ms": st.column_config.NumberColumn("ms", format="%d"),
            "thumbs": "Vote", "created_at": "Asked at (UTC)"})
    else:
        st.caption("No questions yet.")

with tab_x:
    st.markdown("Download the data behind these views. Files are generated from the database at the moment you "
                "click.")
    e1, e2 = st.columns(2, gap="large")
    with e1:
        with st.container(key="card-exp-1"):
            st.markdown("##### Operations report")
            st.caption("A self-contained HTML page with ticket, workflow and assistant figures and the latest tickets. "
                       "Open it in a browser or print it to PDF.")
            st.download_button("Download report (HTML)", html_report(include_archive), file_name="pragyaan-report.html",
                               mime="text/html", icon=":material/description:", type="primary")
    with e2:
        with st.container(key="card-exp-2"):
            st.markdown("##### Raw data (CSV)")
            st.download_button("Tickets", tickets_csv(), file_name="pragyaan-tickets.csv", mime="text/csv",
                               icon=":material/table:")
            st.download_button("Priority corrections (for retraining)", corrections_csv(),
                               file_name="pragyaan-corrections.csv", mime="text/csv", icon=":material/edit:")
            st.download_button("Tasks", tasks_csv(), file_name="pragyaan-tasks.csv", mime="text/csv",
                               icon=":material/task_alt:")
