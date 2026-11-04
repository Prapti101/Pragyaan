# PRAGYAAN – Enterprise Intelligence & Knowledge Automation

Organisations lose time searching scattered tickets, documents and policies, and on repetitive triage. PRAGYAAN brings that knowledge together: it predicts the priority of incoming support tickets with a trained model, answers questions from documents and 9.5k resolved tickets with citations, turns priorities into tracked tasks, and measures it all.

> **Dataset:** Multilingual Customer Support Tickets (English subset, 11,919 tickets), framed as internal knowledge-transfer history for coursework.

## Modules

| Module | What it does | Backed by |
|---|---|---|
| Landing + sign-in | Public landing page and two role-based portals (Employee, Senior Analyst) with ID + password sign-in, remember me, forgot password, lockout | `accounts`, `sessions`, `password_reset_requests` tables (`src/copilot/auth.py`, `app/auth_ui.py`) |
| Employee workspace | Home (ticket tracking, solution recommendations), Submit a ticket, My tickets (raised by me / assigned to me), AI Assistant, Knowledge Hub (read-only) | `src/copilot/triage.py` workflow functions |
| Escalations | Senior Analysts assign or resolve tickets with no close match (or whose recommended solution didn't help), and see what employees solved themselves | `tickets.review_status`, `suggested_solution`, `assignee_account_id` |
| Team management | Create Employee / Senior Analyst accounts, edit IDs and roles, deactivate, issue temporary passwords, handle reset requests, workload | `accounts` table |
| Operations overview | Review / escalation queues, open tickets, priority mix, 14-day trend, open/overdue tasks, model agreement, needs-attention list, activity feed, quick actions | Live SQLite queries |
| Smart Triage | Subject + body → LOW / MEDIUM / HIGH from the trained Random Forest, class probabilities, confidence, driving words, ticket type, similar past tickets. Save, override, change status, correct priority later | `models/severity.joblib`, `models/intent.joblib`, ChromaDB, `tickets` table |
| AI Assistant | Chat over uploaded documents and the ticket archive with sources; unanswered questions go to the Senior Queue; summaries of documents and recent tickets | `src/copilot/assistant.py`, existing RAG pipeline, `chat_messages` |
| Knowledge Hub | Upload PDF, DOCX, TXT, MD, CSV, JSON, HTML; collections and tags; semantic search; preview, summary, download, edit, delete | `data/documents/`, ChromaDB collection `documents_kb` |
| Workflow Automation | Priority rules that create or suggest tasks with an owner and deadline; task board (to do, in progress, done), overdue tracking | `automation_rules`, `tasks` |
| Senior Queue | Seniors answer escalations; the answer is added to the knowledge base (closed loop) | Existing escalation flow |
| Analytics | Ticket trends, priority mix, model confidence and corrections, assistant and SLA metrics, HTML report and CSV exports (including corrections for retraining) | `src/copilot/reports.py` |
| Model Benchmarks | The four severity algorithms, intent model, retrieval Hit@k and threshold sweep, plus a live model probe | `eval/results/*.csv` |

Global search (top bar) covers tickets, tasks, documents and the archive (employees only see their own tickets); notifications are addressed by role or to one person.

## Accounts and roles

| | Employee | Senior Analyst |
|---|---|---|
| Signs in at | Employee portal, with an Employee ID | Senior Analyst portal, with a Senior Analyst ID |
| Tickets | Submits tickets; closes them when a recommended solution or an answer works, or escalates; sees tickets they raised or that are assigned to them; works and resolves assigned tickets | Sees all tickets; works escalations; assigns, resolves, reopens; corrects priorities; sees self-resolved tickets |
| Other pages | AI Assistant, Knowledge Hub (read), Search, My account | Everything, plus Senior Queue, Automation, Team management, Analytics, Model Benchmarks |

**Ticket workflow.** When a ticket is submitted, the Random Forest predicts its priority and the similarity engine searches the resolved-ticket archive. If a resolved ticket is at least `SIM_THRESHOLD` (0.55) similar, its solution is shown to the employee straight away: *This solved my issue* closes the ticket as self-resolved (no analyst action; it shows on the Senior Analyst dashboard as completed), *Not solved, escalate* sends it to the Senior Analysts. Below the threshold, the ticket goes directly to the New / Escalated queue. Employees can also pick a recommendation with *This solved my problem* before submitting (Check existing solutions, or the Home page search); that is recorded as a closed, self-resolved ticket. Solutions written by analysts or assignees are sent to the employee, who confirms or reopens, and are added to the archive so similar tickets match next time. Employees can close their own open ticket at any time once the issue is solved.

**Security.** Passwords are salted PBKDF2-SHA256 hashes (200,000 iterations). The ID is checked against the portal's role on the server, with the same message for unknown IDs and wrong passwords. Five failed attempts lock an account for 5 minutes. Sessions are random tokens stored only as SHA-256 hashes; they expire after 12 hours (30 days with Remember me) and are revoked on sign-out, password change, reset, role change or deactivation. Every run re-validates the session, only the pages for the account's role are registered (typing another role's URL lands on your home page), and each role-specific page re-checks the role. The session cookie is `SameSite=Strict`; Streamlit can't set `HttpOnly` cookies from Python, which is why the server-side revocation matters.

**Creating accounts (no default passwords).** Either open the app on the computer running it while no Senior Analyst exists and use *Set up the first Senior Analyst*, or run on the server:

```powershell
..\.venv\Scripts\python scripts\create_account.py create --role analyst --id SA-001 --name "Your Name"
..\.venv\Scripts\python scripts\create_account.py reset --id SA-001   # recover a locked-out analyst
..\.venv\Scripts\python scripts\create_account.py list
```

The password is typed at a hidden prompt. After that, Senior Analysts add everyone else in **Team management** (a one-time temporary password is generated and must be changed at first sign-in). *Forgot password?* sends a request to the Senior Analysts, who issue a temporary password from Team management. Accounts from the earlier e-mail sign-in were carried over automatically: administrators became Senior Analysts, other users Employees; they sign in with their old e-mail as ID and their old password, and a Senior Analyst can give them a proper ID in Team management.

## Run it (Windows)

Double-click **`run_project.bat`** in this folder. It installs anything missing (a bundled `pypdf` wheel is installed offline), starts the app and opens **http://localhost:8501**. Or by hand from this folder:

```powershell
..\.venv\Scripts\python -m pip install -r requirements.txt --find-links wheels
..\.venv\Scripts\python -m streamlit run app\Home.py
```

Always start from the project root so `.streamlit/config.toml` (theme, bundled fonts in `app/static/fonts`, OFL licence) is picked up. Choose **Sign in**, then the Employee or Senior Analyst portal (see *Accounts and roles* below for creating the first account). A sign-in survives page reloads until you sign out or the session expires.

### What is real, and what needs configuration

- **Real, no setup:** priority prediction (Random Forest), ticket type (Logistic Regression), semantic search (all-MiniLM-L6-v2 + ChromaDB), document text extraction, rules and tasks, analytics and exports. All numbers come from the database or `eval/results`.
- **Without an LLM key (default):** the assistant quotes the most relevant document paragraph or past answer with its source, and summaries are extractive (TF-IDF sentence selection). Nothing is generated. The sidebar shows "Language model: not connected".
- **To enable written answers and summaries:** add `GROQ_API_KEY` (or `GEMINI_API_KEY`, model set by `GEMINI_MODEL`) to a `.env` file. See `.env.example`.
- **Not included:** single sign-on (replace `authenticate()` in `src/copilot/auth.py`, or use Streamlit's `st.login` with an OIDC provider), email/Slack delivery of notifications (in-app only), and OCR for scanned PDFs. Password reset is handled by Senior Analysts (no e-mail server is used).

---

## Architecture

```
[ Joinee Query ]
       │
       ▼
[ Intent Classifier (LogReg) ] ──► Predicts Type: Incident / Request / Problem / Change
       │
       ▼
[ ChromaDB Vector Search ] ──► Top-5 past tickets (all-MiniLM-L6-v2)
       │
  Similarity >= 0.55 ?
    ├── YES ──► [ RAG / Grounded Answer ] ──► RESOLVED (Answer + Ticket citations)
    └── NO  ──► [ Severity Model (RandomForest) ] ──► Score + Reason terms ──► ESCALATED
                      │
                      ▼
            [ Senior Queue in UI ] ──► Senior resolves ticket
                      │
                      ▼
            [ Upsert into ChromaDB ] (Closed Loop — Next query resolves!)
```

---

## Quick Start

### 1. Environment Setup
```powershell
# In PowerShell:
.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "src"

# Optional: set GEMINI_API_KEY in .env for generative answers
# Without an API key, the system uses the local top-ticket fallback.
```

### 2. Run Tests
```powershell
.venv\Scripts\pytest -v
```
13 tests: the 3 pipeline smoke tests (`tests/test_pipeline.py`) plus 10 platform tests (`tests/test_platform.py`: accounts and portals, lockout, sessions and password resets, migration of old accounts, the employee → analyst ticket workflow, triage with corrections and automation, task deadlines, document ingest/search/delete, assistant routing and summaries, reports and search). Platform tests use a temporary database and never touch your data.

### 3. Run the Demo "Money Shot"
```powershell
.venv\Scripts\python scripts\demo_money_shot.py
```
Demonstrates asking a novel urgent question $\rightarrow$ escalated $\rightarrow$ senior resolves $\rightarrow$ asked again $\rightarrow$ resolved from KB.

### 4. Run the Streamlit Application
```powershell
.venv\Scripts\streamlit run app/Home.py
```
`app/Home.py` is the router (sign-in, sidebar navigation, top bar). Pages live in `app/views/` (deliberately not `pages/`, which would switch Streamlit into its legacy multipage mode); shared design components in `app/ui.py`.

---

## Evaluations & Deliverables

- **Final Course Report:** See [`REPORT.md`](file:///c:/5th%20sem/ML_prj/REPORT.md) for full methodology, EDA, benchmark tables, and discussion.
- **Severity Experiments Notebook:** [`notebooks/severity_experiments.ipynb`](file:///c:/5th%20sem/ML_prj/notebooks/severity_experiments.ipynb) (24 cells with EDA, distributions, heatmaps, model comparison bar plots, confusion matrices, and explainability).
- **Threshold Sweep:** Run `python scripts/sweep_threshold.py` (outputs to `eval/results/threshold_sweep.png` and `threshold_sweep.csv`).
- **Answer Faithfulness Audit:** Run `python scripts/eval_faithfulness.py` (20/20 answers 100% grounded in `eval/results/faithfulness_check.csv`).
- **Model Files:** Saved in `models/` (`severity.joblib`, `intent.joblib`, `tfidf.joblib`).
