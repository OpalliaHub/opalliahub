# JobCompass · Group 11

**v1.2.0 · Career Research Workbench · 8 October 2026**

[Download the complete source project](group11_project.zip?raw=true) · [Research guide](RESEARCH_WORKBENCH.md) · [Actual verification results](research_verification.json)

The platform now combines direct JobsDB updates, resume matching, application tracking and a local career research workspace. DeepSeek can turn Chinese instructions into validated analysis plans, which run locally and produce tables, charts, evidence and exports.

## Start locally

Extract group11_project.zip, then run:

```bash
cd group11_project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

Open http://127.0.0.1:8765/ after starting Python. On Windows use `.venv\Scripts\python` with the commands above. Do not open static/index.html as the running application. GitHub stores the downloadable project; it does not host the application.

DeepSeek is optional; configure your own key in the local .env. Offline analysis and matching still work without it.

## What's new

- JobsDB primary-source updates from inside the platform, with progress, cancellation and preserved application notes.
- **职业研究室**: career/category distributions, 36 probe mention shares, monthly trends, period comparisons, filtered dataset previews, paired advertisement revisions and mature-window retrospective diagnostics.
- Chinese command → DeepSeek JSON plan → local parameterized analysis → optional aggregate interpretation. The model cannot execute arbitrary Python, SQL, shell commands or source-data mutations.
- Reusable cohorts and CSV/JSON export with denominators, data identity, query plans and explicit research limitations.

On the development computer, a read-only connection to the existing longitudinal audit database indexes **251,042 first-version advertisements**, from **896,503 valid observations and 67 snapshots**. The Python reference comparison reproduces **1,423/19,109 (7.4468%)** versus **1,523/15,069 (10.1068%)**. Mention frequency is not verified skill demand, market representativeness or causality.

**120 local tests passed** on Python 3.8.10. A live DeepSeek command, plan execution and CSV download were verified in the browser. These are software/integration checks, not research accuracy scores. Code and the optional source-tree CI workflow are inside the ZIP; no GitHub Actions pass is claimed.

## Data and versions

The full 1.9 GB longitudinal research database and derived local indices remain on the user's computer and are not bundled. On another computer, connect a compatible JobsDB audit SQLite via the research UI, or choose **当前平台岗位** to analyze the bundled 28 September historical snapshot. Raw source text, personal resumes, application notes and credentials are not newly published by this update. The already-published normalized snapshot remains historical and retains its original ownership.

The root Word/PDF/PPT files and group11_course_submission.zip are the **30 September classroom revision**. They have not been rewritten for v1.2. Download group11_project.zip for the latest software and consult the Research guide for its current scope. v1.1 is preserved in commit [58dca2e](https://github.com/OpalliaHub/opalliahub/commit/58dca2e162065716e9af1099678ccad1c23f45ca).

Team: OU JUNHANG, ZHANG XIQIAN, JIANG YIFAN, CAI SHANGHENG, GUO ZHENGKUN.
