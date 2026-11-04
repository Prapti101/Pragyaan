"""Workflow automation: priority-based rules that create or suggest tasks.

A rule says "when a ticket's priority is X, create a task <action> due in N hours".
mode='auto'    -> the task is created as soon as the ticket is triaged.
mode='suggest' -> the action is offered on the triage screen; one click creates it.
"""

from __future__ import annotations

from .activity import log_activity
from .db import execute, fetchall, fetchone

PRIORITIES = ("low", "medium", "high")
TASK_STATUSES = ("todo", "in_progress", "done")

DEFAULT_RULES = [
    ("High priority first response", "high", "Send first response and start investigation", 4, "On-call engineer", "auto"),
    ("High priority lead review", "high", "Team lead reviews impact and decides on escalation", 8, "Team lead", "suggest"),
    ("Medium priority response", "medium", "Respond within one business day", 24, "Support queue", "auto"),
    ("Low priority backlog", "low", "Review in the weekly backlog session", 72, "Backlog", "suggest"),
]


def seed_default_rules() -> None:
    row = fetchone("SELECT COUNT(*) AS n FROM automation_rules")
    if row and int(row["n"]) > 0:
        return
    for name, prio, action, sla, assignee, mode in DEFAULT_RULES:
        execute(
            "INSERT INTO automation_rules (name, priority, action, sla_hours, assignee, mode) VALUES (?, ?, ?, ?, ?, ?)",
            (name, prio, action, sla, assignee, mode),
        )


def list_rules() -> list[dict]:
    seed_default_rules()
    return fetchall("SELECT * FROM automation_rules ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, id")


def create_rule(name: str, priority: str, action: str, sla_hours: int, assignee: str | None,
                mode: str = "auto", actor: str | None = None) -> int:
    if priority not in PRIORITIES:
        raise ValueError(f"priority must be one of {PRIORITIES}")
    if mode not in ("auto", "suggest"):
        raise ValueError("mode must be 'auto' or 'suggest'")
    if not name.strip() or not action.strip():
        raise ValueError("Rule name and action are required.")
    rid = execute(
        "INSERT INTO automation_rules (name, priority, action, sla_hours, assignee, mode) VALUES (?, ?, ?, ?, ?, ?)",
        (name.strip(), priority, action.strip(), int(sla_hours), (assignee or "").strip() or None, mode),
    )
    log_activity("rule", f"Created automation rule “{name.strip()}”", ref_type="rule", ref_id=rid, actor=actor)
    return rid


def update_rule(rule_id: int, **fields) -> None:
    allowed = {"name", "priority", "action", "sla_hours", "assignee", "mode", "enabled"}
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    cols = ", ".join(f"{k} = ?" for k in sets)
    execute(f"UPDATE automation_rules SET {cols} WHERE id = ?", (*sets.values(), rule_id))


def delete_rule(rule_id: int) -> None:
    execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))


def matching_rules(priority: str) -> list[dict]:
    seed_default_rules()
    return fetchall(
        "SELECT * FROM automation_rules WHERE enabled = 1 AND priority = ? ORDER BY id", (priority,)
    )


def create_task(title: str, *, description: str | None = None, ticket_id: int | None = None,
                rule_id: int | None = None, priority: str = "medium", assignee: str | None = None,
                due_in_hours: float | None = None, due_at: str | None = None,
                source: str = "manual", created_by: str | None = None) -> int:
    if not title.strip():
        raise ValueError("Task title is required.")
    if priority not in PRIORITIES:
        priority = "medium"
    if due_at is None and due_in_hours is not None:
        due_row = fetchone("SELECT datetime('now', ?) AS d", (f"+{float(due_in_hours)} hours",))
        due_at = due_row["d"] if due_row else None
    tid = execute(
        """
        INSERT INTO tasks (title, description, ticket_id, rule_id, priority, assignee, due_at, source, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (title.strip(), description, ticket_id, rule_id, priority, assignee, due_at, source, created_by),
    )
    where = f" for ticket #{ticket_id}" if ticket_id else ""
    log_activity("task", f"Task created{where}: {title.strip()}", ref_type="task", ref_id=tid, actor=created_by)
    return tid


def task_from_rule(rule: dict, ticket_id: int, subject: str, actor: str | None, source: str) -> int:
    return create_task(
        rule["action"],
        description=f"Ticket #{ticket_id}: {subject}",
        ticket_id=ticket_id,
        rule_id=rule["id"],
        priority=rule["priority"],
        assignee=rule.get("assignee"),
        due_in_hours=rule["sla_hours"],
        source=source,
        created_by=actor,
    )


def apply_rules(ticket_id: int, priority: str, subject: str, actor: str | None = None) -> dict:
    """Run automation for a newly triaged ticket. Returns created task ids and suggestions."""
    created, suggestions = [], []
    for rule in matching_rules(priority):
        if rule["mode"] == "auto":
            created.append(task_from_rule(rule, ticket_id, subject, actor, source="rule"))
        else:
            suggestions.append(rule)
    return {"created": created, "suggestions": suggestions}


def list_tasks(status: str | None = None, ticket_id: int | None = None, limit: int = 500) -> list[dict]:
    where, params = [], []
    if status:
        where.append("status = ?")
        params.append(status)
    if ticket_id:
        where.append("ticket_id = ?")
        params.append(ticket_id)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    return fetchall(
        f"""
        SELECT *, CASE WHEN status != 'done' AND due_at IS NOT NULL AND due_at < datetime('now')
                       THEN 1 ELSE 0 END AS overdue
        FROM tasks {clause}
        ORDER BY CASE status WHEN 'done' THEN 1 ELSE 0 END,
                 CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 COALESCE(due_at, '9999') ASC, id DESC
        LIMIT ?
        """,
        (*params, limit),
    )


def set_task_status(task_id: int, status: str, actor: str | None = None) -> None:
    if status not in TASK_STATUSES:
        raise ValueError(f"status must be one of {TASK_STATUSES}")
    completed = "datetime('now')" if status == "done" else "NULL"
    execute(f"UPDATE tasks SET status = ?, completed_at = {completed} WHERE id = ?", (status, task_id))
    task = fetchone("SELECT title FROM tasks WHERE id = ?", (task_id,))
    label = {"todo": "To do", "in_progress": "In progress", "done": "Done"}[status]
    log_activity("task", f"Task #{task_id} moved to {label}: {task['title'] if task else ''}",
                 ref_type="task", ref_id=task_id, actor=actor)


def delete_task(task_id: int) -> None:
    execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def task_stats() -> dict:
    rows = fetchall("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
    by_status = {r["status"]: int(r["n"]) for r in rows}
    overdue = fetchone(
        "SELECT COUNT(*) AS n FROM tasks WHERE status != 'done' AND due_at IS NOT NULL AND due_at < datetime('now')"
    )
    done_with_due = fetchone(
        "SELECT COUNT(*) AS n, SUM(CASE WHEN completed_at <= due_at THEN 1 ELSE 0 END) AS on_time "
        "FROM tasks WHERE status = 'done' AND due_at IS NOT NULL"
    )
    n_done = int(done_with_due["n"] or 0) if done_with_due else 0
    on_time = int(done_with_due["on_time"] or 0) if done_with_due else 0
    return {
        "todo": by_status.get("todo", 0),
        "in_progress": by_status.get("in_progress", 0),
        "done": by_status.get("done", 0),
        "open": by_status.get("todo", 0) + by_status.get("in_progress", 0),
        "overdue": int(overdue["n"]) if overdue else 0,
        "sla_met_pct": round(100.0 * on_time / n_done, 1) if n_done else None,
        "sla_measured": n_done,
    }
