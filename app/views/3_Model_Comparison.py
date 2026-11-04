"""Model comparison: every algorithm tried for each prediction step, on one screen."""

from __future__ import annotations

import sys
from pathlib import Path

import altair as alt
import joblib
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.config import EVAL_RESULTS, MODELS_DIR, SIM_THRESHOLD  # noqa: E402

user = ui.require_role("analyst")


# ---------------------------------------------------------------- data

ALGO_NAMES = {
    "LogReg (TF-IDF)": ("Logistic Regression", "TF-IDF n-grams"),
    "RandomForest (TF-IDF)": ("Random Forest", "TF-IDF n-grams"),
    "MLP (TF-IDF)": ("Neural net (MLP)", "TF-IDF n-grams"),
    "MiniLM+LogReg": ("MiniLM embeddings + LogReg", "Sentence embeddings (MiniLM)"),
}


@st.cache_data
def load_csv(name: str) -> pd.DataFrame | None:
    path = EVAL_RESULTS / name
    return pd.read_csv(path) if path.exists() else None


@st.cache_data
def deployed_severity_model() -> str | None:
    meta = MODELS_DIR / "severity_meta.joblib"
    try:
        return str(joblib.load(meta).get("model_name"))
    except Exception:
        return None


def algo_label(raw: str) -> str:
    return ALGO_NAMES.get(raw, (raw, ""))[0]


sev = load_csv("severity_comparison.csv")
sev_test = load_csv("severity_test.csv")
intent = load_csv("intent_comparison.csv")
hit = load_csv("retrieval_hit_at_k.csv")
sweep = load_csv("threshold_sweep.csv")
e2e = load_csv("e2e_summary.csv")
conf = load_csv("severity_confusion_test.csv")
faith = load_csv("faithfulness_check.csv")

if sev is not None:
    sev = sev.copy()
    champ_raw = deployed_severity_model()
    if champ_raw not in set(sev["model"]):
        champ_raw = sev.loc[sev["macro_f1"].idxmax(), "model"]
    sev["algorithm"] = sev["model"].map(algo_label)
    sev["features"] = sev["model"].map(lambda m: ALGO_NAMES.get(m, (m, ""))[1])
    sev["chosen"] = sev["model"] == champ_raw
    sev["label"] = sev.apply(lambda r: f"{r['algorithm']} (chosen)" if r["chosen"] else r["algorithm"], axis=1)
    sev = sev.sort_values("macro_f1", ascending=False).reset_index(drop=True)
    champ = sev[sev["chosen"]].iloc[0]

# ---------------------------------------------------------------- header

ui.page_header("Model Benchmarks",
               "Every algorithm tried for each prediction PRAGYAAN makes, scored on held-out data. "
               "The chosen model in each step is the one the app runs.")

# One tile per prediction step: which model is in use and its headline score
tiles = st.columns(4)
with tiles[0]:
    with st.container(key="card-mc-1", height="stretch"):
        if sev is not None:
            st.metric(f"Severity: {champ['algorithm']}", f"{champ['macro_f1']:.3f}")
            test_txt = (
                f" Test set: {sev_test['macro_f1'].iloc[0]:.3f}." if sev_test is not None else ""
            )
            st.caption(f"Macro-F1 on 1,192 validation tickets.{test_txt}")
with tiles[1]:
    with st.container(key="card-mc-2", height="stretch"):
        if intent is not None:
            row = intent.iloc[0]
            st.metric(f"Ticket type: {algo_label(row['model'])}", f"{row['macro_f1']:.3f}")
            st.caption(f"Macro-F1. Accuracy {row['accuracy']:.1%}.")
with tiles[2]:
    with st.container(key="card-mc-3", height="stretch"):
        if hit is not None:
            r5 = hit[hit["k"] == hit["k"].max()].iloc[0]
            st.metric("Retrieval: MiniLM + ChromaDB", f"{r5['hit_queue']:.1%}")
            st.caption(f"Right team in the top {int(r5['k'])} past tickets ({int(r5['n'])} test queries).")
with tiles[3]:
    with st.container(key="card-mc-4", height="stretch"):
        if sweep is not None:
            cur = sweep.iloc[(sweep["threshold"] - SIM_THRESHOLD).abs().argsort()[:1]].iloc[0]
            st.metric(f"Answer-or-escalate cutoff: {SIM_THRESHOLD:.2f}", f"{cur['accuracy']:.1f}%")
            n_q = int(e2e["n"].iloc[0]) if e2e is not None else 40
            st.caption(f"{n_q} test questions sent the right way.")

# ---------------------------------------------------------------- severity

st.divider()
st.subheader("Severity: which algorithm predicts priority best?")

if sev is None:
    st.info("Run scripts/train_severity.py to produce eval/results/severity_comparison.csv.")
else:
    others = sev[~sev["chosen"]]
    runner = others.iloc[0]
    lowest = sev.iloc[-1]
    slowest = sev.loc[sev["train_s"].idxmax()]
    parts = [
        f"All {len(sev)} were trained on the same 9,535 tickets and scored on the same validation split.",
        f"**{champ['algorithm']}** is in use with macro-F1 {champ['macro_f1']:.3f} and accuracy "
        f"{champ['accuracy']:.1%}; the next best is {runner['algorithm']} ({runner['macro_f1']:.3f}).",
    ]
    if champ["train_s"] < runner["train_s"]:
        parts.append(f"It also trains faster: {champ['train_s']:.1f} s against {runner['train_s']:.1f} s.")
    if lowest["model"] == slowest["model"]:
        parts.append(
            f"{lowest['algorithm']} scored lowest and was the slowest to train "
            f"({slowest['train_s'] / 60:.0f} minutes), a sign that keywords predict priority better "
            "than overall sentence meaning."
        )
    st.markdown(" ".join(parts))

    long = sev.melt(
        id_vars=["label", "algorithm", "features", "chosen"],
        value_vars=["macro_f1", "accuracy"],
        var_name="metric",
        value_name="value",
    )
    long["metric"] = long["metric"].map({"macro_f1": "Macro-F1", "accuracy": "Accuracy"})
    order = sev["label"].tolist()
    metric_order = ["Macro-F1", "Accuracy"]

    bars = alt.Chart(long).mark_bar(cornerRadiusEnd=4, height={"band": 0.8}).encode(
        y=alt.Y("label:N", sort=order, title=None, scale=alt.Scale(paddingInner=0.35),
                axis=alt.Axis(labelLimit=260, labelFontSize=13)),
        yOffset=alt.YOffset("metric:N", sort=metric_order, scale=alt.Scale(paddingInner=0.15)),
        x=alt.X("value:Q", title="Score (higher is better)", scale=alt.Scale(domain=[0, 0.6]),
                axis=alt.Axis(format=".1f", tickCount=6)),
        color=alt.Color("metric:N", sort=metric_order,
                        scale=alt.Scale(domain=metric_order, range=ui.SERIES[:2])),
        tooltip=[
            alt.Tooltip("value:Q", title="Score", format=".3f"),
            alt.Tooltip("metric:N", title="Metric"),
            alt.Tooltip("algorithm:N", title="Algorithm"),
            alt.Tooltip("features:N", title="Features"),
        ],
    )
    labels = alt.Chart(long[long["metric"] == "Macro-F1"]).mark_text(
        align="left", dx=6, fontSize=12, color=ui.INK
    ).encode(
        y=alt.Y("label:N", sort=order),
        yOffset=alt.YOffset("metric:N", sort=metric_order, scale=alt.Scale(domain=metric_order, paddingInner=0.15)),
        x="value:Q",
        text=alt.Text("value:Q", format=".3f"),
    )
    left, right = st.columns([3, 2], gap="large")
    with left:
        ui.show_chart(
            (bars + labels).properties(height=250, title="Prediction quality (validation set)")
        )
    with right:
        cost = sev[["label", "algorithm", "train_s", "infer_ms"]]

        def cost_chart(field: str, title: str, fmt: str, unit: str):
            base = alt.Chart(cost).encode(
                y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=200)),
                x=alt.X(f"{field}:Q", title=unit, axis=alt.Axis(tickCount=3, labelFlush=True)),
            )
            b = base.mark_bar(cornerRadiusEnd=4, height=14, color=ui.SERIES[0]).encode(
                tooltip=[alt.Tooltip(f"{field}:Q", title=unit, format=fmt),
                         alt.Tooltip("algorithm:N", title="Algorithm")]
            )
            t = base.mark_text(align="left", dx=5, fontSize=12, color=ui.INK).encode(
                text=alt.Text(f"{field}:Q", format=fmt)
            )
            return (b + t).properties(height=140, title=title)

        ui.show_chart(cost_chart("train_s", "Training time", ",.1f", "Seconds"))
        ui.show_chart(cost_chart("infer_ms", "Time to score one question", ".3f", "Milliseconds"))

    table = sev[["algorithm", "features", "accuracy", "macro_f1", "train_s", "infer_ms", "chosen"]]
    st.dataframe(
        table,
        hide_index=True,
        width="stretch",
        column_config={
            "algorithm": st.column_config.TextColumn("Algorithm"),
            "features": st.column_config.TextColumn("Features"),
            "accuracy": st.column_config.NumberColumn("Accuracy", format="%.3f"),
            "macro_f1": st.column_config.NumberColumn("Macro-F1", format="%.3f"),
            "train_s": st.column_config.NumberColumn("Train time (s)", format="%.2f"),
            "infer_ms": st.column_config.NumberColumn("Inference (ms)", format="%.3f"),
            "chosen": st.column_config.CheckboxColumn("In use"),
        },
    )

    if conf is not None:
        st.markdown(f"##### How {champ['algorithm']} does on unseen test tickets")
        classes = ["low", "medium", "high"]
        cm = conf.copy()
        cm["row_total"] = cm.groupby("true_label")["count"].transform("sum")
        cm["share"] = cm["count"] / cm["row_total"]
        recall = cm[cm["true_label"] == cm["predicted_label"]].set_index("true_label")["share"]
        n_test = int(cm["count"].sum())
        acc = cm.loc[cm["true_label"] == cm["predicted_label"], "count"].sum() / n_test

        c1, c2 = st.columns([2, 3], gap="large")
        with c1:
            heat = alt.Chart(cm).encode(
                x=alt.X("predicted_label:N", sort=classes, title="Predicted priority",
                        axis=alt.Axis(labelAngle=0, orient="top")),
                y=alt.Y("true_label:N", sort=classes, title="Actual priority"),
            )
            cells = heat.mark_rect(cornerRadius=3, stroke="white", strokeWidth=2).encode(
                color=alt.Color(
                    "share:Q",
                    scale=alt.Scale(range=["#EEF4FC", "#2a78d6", "#0d366b"], domain=[0, 0.4, 0.8]),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip("count:Q", title="Tickets"),
                    alt.Tooltip("share:Q", title="Share of actual class", format=".0%"),
                    alt.Tooltip("true_label:N", title="Actual"),
                    alt.Tooltip("predicted_label:N", title="Predicted"),
                ],
            )
            txt = heat.mark_text(fontSize=13).encode(
                text=alt.Text("count:Q"),
                color=alt.condition("datum.share > 0.35", alt.value("white"), alt.value(ui.INK)),
            )
            ui.show_chart((cells + txt).properties(height=230))
        with c2:
            st.markdown(
                f"On {n_test:,} test tickets it gets **{acc:.1%}** right. "
                f"It finds {recall.get('medium', 0):.0%} of medium, {recall.get('high', 0):.0%} of high "
                f"and {recall.get('low', 0):.0%} of low tickets. Most mistakes are between neighbouring "
                "levels, mainly high and medium, which human agents also label inconsistently."
            )
            st.caption("Rows are the true priority; darker cells hold a larger share of that row.")

# ---------------------------------------------------------------- retrieval

st.divider()
st.subheader("Retrieval: does the right past ticket come back?")
if hit is None:
    st.info("Run scripts/evaluate.py to produce eval/results/retrieval_hit_at_k.csv.")
else:
    h = hit.melt(id_vars=["k", "n"], value_vars=["hit_queue", "hit_type"], var_name="match", value_name="rate")
    match_names = {"hit_queue": "Same team (queue)", "hit_type": "Same ticket type"}
    h["match"] = h["match"].map(match_names)
    h["top"] = h["k"].map(lambda k: f"Top {k}")
    m_order = list(match_names.values())
    k_order = [f"Top {k}" for k in sorted(hit["k"])]
    r1 = hit.sort_values("k").iloc[0]
    rk = hit.sort_values("k").iloc[-1]
    left, right = st.columns([3, 2], gap="large")
    with left:
        base = alt.Chart(h).encode(
            x=alt.X("top:N", sort=k_order, title="Past tickets shown", scale=alt.Scale(paddingInner=0.45),
                    axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("match:N", sort=m_order, scale=alt.Scale(paddingInner=0.1)),
            y=alt.Y("rate:Q", title="Queries with a match", scale=alt.Scale(domain=[0, 1]),
                    axis=alt.Axis(format="%", tickCount=5)),
        )
        b = base.mark_bar(cornerRadiusEnd=4, width={"band": 0.9}).encode(
            color=alt.Color("match:N", sort=m_order, scale=alt.Scale(domain=m_order, range=ui.SERIES[:2])),
            tooltip=[alt.Tooltip("rate:Q", title="Hit rate", format=".1%"),
                     alt.Tooltip("match:N", title="Match"), alt.Tooltip("top:N", title="Shown")],
        )
        t = base.mark_text(dy=-8, fontSize=12, color=ui.INK).encode(text=alt.Text("rate:Q", format=".0%"))
        ui.show_chart((b + t).properties(height=240))
    with right:
        st.markdown(
            f"{int(rk['n'])} unseen test tickets were used as questions against the knowledge base, "
            "embedded with all-MiniLM-L6-v2 and searched in ChromaDB by cosine similarity."
        )
        st.markdown(
            f"The single closest ticket is from the right team {r1['hit_queue']:.0%} of the time. "
            f"Within the top {int(rk['k'])} that rises to {rk['hit_queue']:.0%}, "
            f"and {rk['hit_type']:.0%} share the ticket type, so the answer is drawn from relevant history."
        )
        if faith is not None:
            ok = int(faith["is_faithful"].astype(str).str.lower().eq("true").sum())
            st.markdown(f"In a manual check, {ok} of {len(faith)} answers were fully supported by the tickets they cite.")

# ---------------------------------------------------------------- threshold

st.divider()
st.subheader("Routing: when to answer and when to escalate")
if sweep is None:
    st.info("Run scripts/sweep_threshold.py to produce eval/results/threshold_sweep.csv.")
else:
    series = {
        "auto_resolve_pct": "Known answered",
        "false_resolve_pct": "New answered wrongly",
        "accuracy": "Routed correctly",
    }
    s_order = list(series.values())
    sw = sweep.melt(id_vars=["threshold"], value_vars=list(series), var_name="series", value_name="pct")
    sw["series"] = sw["series"].map(series)
    wide = sweep.rename(columns=series)

    left, right = st.columns([3, 2], gap="large")
    with left:
        hover = alt.selection_point(fields=["threshold"], nearest=True, on="pointerover", empty=False)
        x = alt.X("threshold:Q", title="Similarity cutoff", scale=alt.Scale(domain=[0.3, 0.85], nice=False),
                  axis=alt.Axis(format=".2f", values=[0.3, 0.4, 0.5, 0.55, 0.6, 0.7, 0.8]))
        lines = alt.Chart(sw).mark_line(strokeWidth=2).encode(
            x=x,
            y=alt.Y("pct:Q", title="Percent of test questions", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("series:N", sort=s_order, scale=alt.Scale(domain=s_order, range=ui.SERIES[:3])),
        )
        points = lines.mark_point(filled=True, size=50, stroke="white", strokeWidth=1.5)
        rule_in_use = alt.Chart(pd.DataFrame({"threshold": [SIM_THRESHOLD]})).mark_rule(
            color=ui.INK_2, strokeWidth=1
        ).encode(x=x)
        rule_label = alt.Chart(pd.DataFrame({"threshold": [SIM_THRESHOLD], "y": [75]})).mark_text(
            align="left", dx=6, fontSize=12, color=ui.INK
        ).encode(x=x, y="y:Q", text=alt.value(f"In use: {SIM_THRESHOLD:.2f}"))
        crosshair = alt.Chart(wide).mark_rule(color=ui.AXIS, strokeWidth=12, opacity=0.001).encode(
            x=x,
            tooltip=[alt.Tooltip("threshold:Q", title="Cutoff", format=".2f")]
            + [alt.Tooltip(f"{name}:Q", title=name, format=".1f") for name in s_order],
        ).add_params(hover)
        hover_line = alt.Chart(wide).mark_rule(color=ui.AXIS, strokeWidth=1).encode(
            x=x
        ).transform_filter(hover)
        ui.show_chart(
            alt.layer(rule_in_use, rule_label, hover_line, lines, points, crosshair).properties(height=300)
        )
    with right:
        cur = sweep.iloc[(sweep["threshold"] - SIM_THRESHOLD).abs().argsort()[:1]].iloc[0]
        best = sweep[sweep["accuracy"] == sweep["accuracy"].max()]["threshold"]
        n_q = int(e2e["n"].iloc[0]) if e2e is not None else 40
        st.markdown(
            f"If the closest past ticket is at least this similar, the copilot answers; otherwise it escalates. "
            f"{n_q} test questions were used: half already covered by the knowledge base (known), half new."
        )
        st.markdown(
            f"At the cutoff in use ({SIM_THRESHOLD:.2f}), {cur['auto_resolve_pct']:.0f}% of known questions are "
            f"answered and {cur['false_resolve_pct']:.0f}% of new ones are answered when they should have been "
            f"escalated, for {cur['accuracy']:.1f}% correct overall."
        )
        if len(best):
            lo, hi = best.min(), best.max()
            span = f"{lo:.2f}" if lo == hi else f"{lo:.2f} to {hi:.2f}"
            st.markdown(
                f"The highest score on this set ({sweep['accuracy'].max():.1f}%) is at {span}. "
                "Lower cutoffs answer new questions with unrelated tickets; higher ones start "
                "escalating questions the knowledge base already covers."
            )

# ---------------------------------------------------------------- live

st.divider()
st.subheader("Try the models on a question")
st.caption("Runs the three models in use on your text. Nothing is saved or escalated from here.")

with st.form("probe", border=False):
    q = st.text_input(
        "Question",
        value=st.session_state.get("probe_q", "Production database is down and customers cannot check out"),
        label_visibility="collapsed",
    )
    run = st.form_submit_button("Run models", type="primary")

if run and q.strip():
    st.session_state["probe_q"] = q.strip()

probe_q = st.session_state.get("probe_q")
if probe_q:
    from copilot.intent import intent_probabilities
    from copilot.retrieval import search
    from copilot.severity import predict_severity, routing_bucket, severity_probabilities

    with st.spinner("Scoring…"):
        ip = intent_probabilities(probe_q)
        sp = severity_probabilities(probe_q)
        sev_info = predict_severity(probe_q)
        hits = search(probe_q, k=5)

    def prob_chart(probs: dict[str, float], order: list[str], title: str):
        top = max(probs, key=probs.get)
        df = pd.DataFrame({"cls": list(probs), "p": list(probs.values())})
        df["is_top"] = df["cls"] == top
        base = alt.Chart(df).encode(
            y=alt.Y("cls:N", sort=order, title=None),
            x=alt.X("p:Q", title="Probability", scale=alt.Scale(domain=[0, 1]), axis=alt.Axis(format="%", tickCount=5)),
        )
        b = base.mark_bar(cornerRadiusEnd=4, height=16).encode(
            color=alt.condition("datum.is_top", alt.value(ui.SERIES[0]), alt.value(ui.NEUTRAL_BAR)),
            tooltip=[alt.Tooltip("p:Q", title="Probability", format=".1%"), alt.Tooltip("cls:N", title="Class")],
        )
        t = base.mark_text(align="left", dx=5, fontSize=12, color=ui.INK).encode(text=alt.Text("p:Q", format=".0%"))
        return (b + t).properties(height=34 * len(order) + 30, title=title)

    c1, c2, c3 = st.columns(3, gap="large")
    with c1:
        with st.container(key="card-mc-probe-1"):
            top_i = max(ip, key=ip.get)
            st.markdown(f"**Ticket type:** {top_i}")
            ui.show_chart(prob_chart(ip, ["Incident", "Problem", "Request", "Change"], "Logistic Regression"))
    with c2:
        with st.container(key="card-mc-probe-2"):
            bucket = routing_bucket(sev_info.score)
            color, icon = ui.BUCKET_BADGE.get(bucket, ("gray", ""))
            st.markdown(
                f"**Severity:** {sev_info.label} :{color}-badge[{icon} {bucket}]  \n"
                f":gray[Score {sev_info.score:.2f} = P(medium) × 0.5 + P(high)]"
            )
            ui.show_chart(prob_chart(sp, ["low", "medium", "high"], "Random Forest"))
            if sev_info.top_terms:
                st.markdown("Words that pushed the score: " + " ".join(f":gray-badge[{t}]" for t in sev_info.top_terms))
    with c3:
        with st.container(key="card-mc-probe-3"):
            top_sim = hits[0].similarity if hits else 0.0
            if top_sim >= SIM_THRESHOLD:
                st.markdown(f"**Route:** :green-badge[:material/check: Answer from ticket {hits[0].ticket_id}]")
            else:
                st.markdown("**Route:** :orange-badge[:material/forward: Escalate to a senior]")
            if hits:
                hd = pd.DataFrame(
                    {"ticket": [f"#{h.ticket_id}" for h in hits], "sim": [h.similarity for h in hits],
                     "snippet": [h.snippet[:90] for h in hits]}
                )
                tk_order = hd["ticket"].tolist()
                base = alt.Chart(hd).encode(
                    y=alt.Y("ticket:N", sort=tk_order, title=None),
                    x=alt.X("sim:Q", title="Cosine similarity", scale=alt.Scale(domain=[0, 1]),
                            axis=alt.Axis(format=".1f", tickCount=5)),
                )
                b = base.mark_bar(cornerRadiusEnd=4, height=14, color=ui.SERIES[0]).encode(
                    tooltip=[alt.Tooltip("sim:Q", title="Similarity", format=".3f"),
                             alt.Tooltip("snippet:N", title="Ticket")]
                )
                t = base.mark_text(align="left", dx=5, fontSize=12, color=ui.INK).encode(
                    text=alt.Text("sim:Q", format=".2f")
                )
                rule = alt.Chart(pd.DataFrame({"x": [SIM_THRESHOLD]})).mark_rule(
                    color=ui.INK_2, strokeWidth=1
                ).encode(x="x:Q")
                ui.show_chart((b + t + rule).properties(height=200, title="Closest past tickets (line = cutoff)"))
