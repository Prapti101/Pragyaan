"""Report exports built from stored data (CSV and a self-contained HTML report)."""

from __future__ import annotations

import html
from datetime import datetime

import pandas as pd

from .automation import task_stats
from .db import fetchall
from .feedback import analytics_summary
from .triage import ticket_stats


def tickets_csv() -> bytes:
    rows = fetchall(
        "SELECT id, created_at, subject, body, requester, predicted_priority, final_priority, "
        "COALESCE(final_priority, predicted_priority) AS priority, reference_priority, prob_low, prob_medium, "
        "prob_high, confidence, severity_score, predicted_type, status, source, created_by, corrected_by, "
        "corrected_at, model_name FROM tickets ORDER BY id"
    )
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def corrections_csv() -> bytes:
    """Manually corrected tickets: ready to append to a retraining set."""
    rows = fetchall(
        "SELECT id, subject, body, predicted_priority, final_priority AS corrected_priority, corrected_by, corrected_at "
        "FROM tickets WHERE final_priority IS NOT NULL AND final_priority != predicted_priority ORDER BY id"
    )
    return pd.DataFrame(rows, columns=["id", "subject", "body", "predicted_priority", "corrected_priority",
                                       "corrected_by", "corrected_at"]).to_csv(index=False).encode("utf-8")


def tasks_csv() -> bytes:
    rows = fetchall("SELECT * FROM tasks ORDER BY id")
    return pd.DataFrame(rows).to_csv(index=False).encode("utf-8")


def html_report(include_archive: bool = False) -> bytes:
    t = ticket_stats(include_archive=include_archive)
    k = task_stats()
    a = analytics_summary()
    now = datetime.now().strftime("%d %b %Y, %H:%M")

    def row(label, value):
        return f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>"

    recent = fetchall(
        "SELECT id, created_at, subject, COALESCE(final_priority, predicted_priority) AS priority, status "
        "FROM tickets " + ("" if include_archive else "WHERE source != 'archive' ") + "ORDER BY id DESC LIMIT 25"
    )
    recent_rows = "".join(
        f"<tr><td>#{r['id']}</td><td>{html.escape(r['created_at'])}</td><td>{html.escape(r['subject'])}</td>"
        f"<td>{html.escape(r['priority'] or '')}</td><td>{html.escape(r['status'])}</td></tr>" for r in recent
    ) or "<tr><td colspan=5>No tickets yet.</td></tr>"
    agreement = f"{t['agreement_pct']}%" if t["agreement_pct"] is not None else "n/a"
    conf = f"{t['avg_confidence']:.2f}" if t["avg_confidence"] is not None else "n/a"
    sla = f"{k['sla_met_pct']}% of {k['sla_measured']}" if k["sla_met_pct"] is not None else "n/a"
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>PRAGYAAN report {now}</title>
<style>body{{font-family:system-ui,sans-serif;color:#151A31;max-width:900px;margin:40px auto;padding:0 16px}}
h1{{font-size:24px}}h2{{font-size:17px;margin-top:28px}}table{{border-collapse:collapse;width:100%}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #E2E5EF;font-size:14px}}th{{color:#545B78;font-weight:600}}
.muted{{color:#545B78;font-size:13px}}</style></head><body>
<h1>PRAGYAAN operations report</h1><p class="muted">Generated {now}. Source: this installation's database.
{'Includes' if include_archive else 'Excludes'} tickets imported from the historical archive.</p>
<h2>Tickets</h2><table>{row('Total tickets', t['total'])}{row('Open', t['open'])}
{row('Open high priority', t['open_high'])}{row('High / medium / low', f"{t['by_priority']['high']} / {t['by_priority']['medium']} / {t['by_priority']['low']}")}
{row('Average model confidence (triaged here)', conf)}{row('Model priority kept by agents', agreement)}
{row('Manual corrections', t['corrected'])}</table>
<h2>Workflow</h2><table>{row('Open tasks', k['open'])}{row('Overdue tasks', k['overdue'])}
{row('Completed tasks', k['done'])}{row('Completed within SLA', sla)}</table>
<h2>AI Assistant</h2><table>{row('Questions asked', a['total'])}{row('Answered automatically', f"{a['auto_resolve_pct']}%")}
{row('Average response time', f"{a['avg_latency_ms']:.0f} ms")}{row('Helpful votes', f"{a['thumbs_up']} up, {a['thumbs_down']} down")}</table>
<h2>Latest tickets</h2><table><tr><th>#</th><th>Created (UTC)</th><th>Subject</th><th>Priority</th><th>Status</th></tr>{recent_rows}</table>
</body></html>"""
    return doc.encode("utf-8")
