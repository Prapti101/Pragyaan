"""Senior Analyst: employee and support team management (accounts, roles, resets, workload)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

import ui  # noqa: E402
from copilot.auth import (ROLE_LABELS, AuthError, PermissionDenied, create_account,  # noqa: E402
                          dismiss_reset_request, generate_temporary_password, list_accounts, list_reset_requests,
                          reset_password, update_account)
from copilot.triage import queue_counts, workload  # noqa: E402

user = ui.require_role("analyst")
ui.page_header("Team management", "Create Employee and Senior Analyst accounts, manage roles and access, handle "
               "password resets and balance the support workload.")

accounts = list_accounts()
resets = list_reset_requests(user)
load = {w["id"]: w for w in workload()}
qc = queue_counts()

k1, k2, k3, k4 = st.columns(4)
with k1:
    ui.kpi("Employees", f"{sum(a['role'] == 'employee' and a['is_active'] for a in accounts)}",
           "Active accounts", icon_name="badge")
with k2:
    ui.kpi("Senior Analysts", f"{sum(a['role'] == 'analyst' and a['is_active'] for a in accounts)}",
           "Active accounts", icon_name="shield_person")
with k3:
    ui.kpi("Password resets", f"{len(resets)}", "Requests waiting", icon_name="key",
           tone=ui.WARNING if resets else None)
with k4:
    ui.kpi("Unassigned escalations", f"{qc['escalated']}", "Ready to assign", icon_name="assignment_ind",
           tone=ui.STAGE_COLORS["escalated"] if qc["escalated"] else None)

# One-time display of a temporary password just issued
issued = st.session_state.get("_team_issued")
if issued:
    with st.container(key="card-issued"):
        st.success(f"{issued['what']} for **{issued['name']}** ({issued['login_id']}). Share these details privately; "
                   "the password is shown only once and must be changed at first sign-in.", icon=":material/key:")
        a, b = st.columns(2)
        a.markdown(f"**{ROLE_LABELS[issued['role']]} ID**")
        a.code(issued["login_id"], language=None)
        b.markdown("**Temporary password**")
        b.code(issued["password"], language=None)
        if st.button("Done, I've shared it", key="issued-done", icon=":material/check:"):
            st.session_state.pop("_team_issued", None)
            st.rerun()

views = {"people": f"People ({len(accounts)})", "add": "Add account", "resets": f"Password resets ({len(resets)})"}
st.session_state.setdefault("team_tab", "resets" if resets else "people")
tab = st.segmented_control("Section", list(views), format_func=views.get, key="team_tab", required=True,
                           label_visibility="collapsed") or "people"

if tab == "people":
    with st.container(key="card-people"):
        df = pd.DataFrame([{
            "ID": a["login_id"], "Name": a["name"], "Role": a["role_label"], "Department": a.get("department") or "",
            "Title": a.get("title") or "", "Status": "Active" if a["is_active"] else "Deactivated",
            "Active tickets": int((load.get(a["id"]) or {}).get("active") or 0),
            "High priority": int((load.get(a["id"]) or {}).get("active_high") or 0),
            "Resolved": int((load.get(a["id"]) or {}).get("resolved") or 0),
            "Last sign-in": ui.local_time(a.get("last_login_at")) or "Never",
        } for a in accounts])
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"Active tickets": st.column_config.NumberColumn(format="%d"),
                                    "Resolved": st.column_config.NumberColumn(format="%d")})
        if any("@" in a["login_id"] for a in accounts):
            st.caption("Accounts carried over from the old e-mail sign-in still use their e-mail as ID. Give them an "
                       "Employee / Senior Analyst ID below.")

    with st.container(key="card-edit"):
        st.markdown("##### Edit an account")
        by_id = {a["id"]: a for a in accounts}
        pick = st.selectbox("Account", list(by_id), key="team_pick",
                            format_func=lambda i: f"{by_id[i]['name']} ({by_id[i]['login_id']}) · {by_id[i]['role_label']}"
                            + ("" if by_id[i]["is_active"] else " · deactivated"))
        a = by_id[pick]
        is_me = a["id"] == user["id"]
        with st.form(f"edit-{a['id']}", border=False):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name", value=a["name"])
            login_id = c2.text_input(f"{ROLE_LABELS[a['role']]} ID", value=a["login_id"],
                                     help="Changing the ID signs the person out; tell them their new ID.")
            c3, c4, c5 = st.columns(3)
            role = c3.selectbox("Role", ["employee", "analyst"], index=0 if a["role"] == "employee" else 1,
                                format_func=ROLE_LABELS.get, disabled=is_me)
            dept = c4.text_input("Department", value=a.get("department") or "")
            title = c5.text_input("Job title", value=a.get("title") or "")
            active = st.toggle("Account active", value=a["is_active"], disabled=is_me,
                               help="Deactivated accounts can't sign in; their tickets stay.")
            save = st.form_submit_button("Save changes", type="primary", icon=":material/save:")
        if save:
            try:
                update_account(a["id"], user, name=name, login_id=login_id, role=None if is_me else role,
                               department=dept, title=title, is_active=None if is_me else active)
            except (AuthError, PermissionDenied) as e:
                st.error(str(e), icon=":material/error:")
            else:
                st.session_state["_toast"] = f"Saved {name}."
                st.rerun()
        st.divider()
        if not is_me:
            p1, p2 = st.columns([3, 1.25], vertical_alignment="center")
            p1.markdown(ui.label("Password") + "<div class='pg-muted'>Locked out or forgot it? Issue a one-time "
                        f"temporary password; {ui.esc(a['name'].split(' ')[0])} chooses a new one at the next sign-in."
                        "</div>", unsafe_allow_html=True)
            if p2.button("Issue a temporary password", icon=":material/key:", key=f"reset-{a['id']}", width="stretch"):
                temp = reset_password(a["id"], user)
                st.session_state["_team_issued"] = {"what": "Temporary password issued", "name": a["name"],
                                                    "login_id": a["login_id"], "role": a["role"], "password": temp}
                st.rerun()
        else:
            st.caption("This is your account. Change your own password in My account; another Senior Analyst can "
                       "change your role or status.")

elif tab == "add":
    with st.container(key="card-add"):
        st.markdown("##### Add an account")
        st.caption("Accounts get a one-time temporary password by default; the person chooses their own at first "
                   "sign-in. No default or shared passwords are used.")
        with st.form("add-account", border=True):
            c1, c2 = st.columns(2)
            role = c1.selectbox("Role", ["employee", "analyst"], format_func=ROLE_LABELS.get)
            login_id = c2.text_input("ID", placeholder="e.g. EMP-1042 or SA-007",
                                     help="Used to sign in. 3-64 letters, numbers, dots, dashes or underscores.")
            name = st.text_input("Full name")
            c3, c4 = st.columns(2)
            dept = c3.text_input("Department", placeholder="e.g. Finance")
            title = c4.text_input("Job title", placeholder="e.g. Accounts Executive")
            mode = st.radio("Initial password", ["Generate a temporary password", "Set a password now"],
                            horizontal=True)
            pw = st.text_input("Password (only if you set one now)", type="password", autocomplete="new-password")
            must = st.checkbox("Require a new password at first sign-in", value=True)
            ok = st.form_submit_button("Create account", type="primary", icon=":material/person_add:")
        if ok:
            generated = mode.startswith("Generate")
            password = generate_temporary_password() if generated else pw
            try:
                acct = create_account(login_id, name, role, password, department=dept, title=title,
                                      must_change_password=must or generated, created_by=user)
            except (AuthError, PermissionDenied) as e:
                st.error(str(e), icon=":material/error:")
            else:
                if generated:
                    st.session_state["_team_issued"] = {"what": "Account created", "name": acct["name"],
                                                        "login_id": acct["login_id"], "role": acct["role"],
                                                        "password": password}
                else:
                    st.session_state["_toast"] = f"{acct['role_label']} account {acct['login_id']} created."
                st.rerun()

else:
    with st.container(key="card-resets"):
        st.markdown("##### Password reset requests")
        if not resets:
            ui.empty_state("key", "No open requests", "When someone uses “Forgot password?” on a sign-in page, the "
                           "request appears here.")
        for r in resets:
            a, b, c = st.columns([3.2, 1.3, 1], vertical_alignment="center")
            a.markdown(f"**{ui.esc(r['name'])}** ({ui.esc(r['login_id'])}) {ui.role_badge(r['role'])}<br>"
                       f"<span class='pg-muted'>Requested {ui.ago(r['requested_at'])}. Confirm it's really them "
                       "before sharing a password.</span>", unsafe_allow_html=True)
            if b.button("Issue password", key=f"rr-issue-{r['id']}", type="primary", icon=":material/key:",
                        width="stretch"):
                temp = reset_password(r["account_id"], user)
                st.session_state["_team_issued"] = {"what": "Temporary password issued", "name": r["name"],
                                                    "login_id": r["login_id"], "role": r["role"], "password": temp}
                st.rerun()
            if c.button("Dismiss", key=f"rr-dismiss-{r['id']}", width="stretch"):
                dismiss_reset_request(r["id"], user)
                st.rerun()
