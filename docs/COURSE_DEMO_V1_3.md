# Group 11 — v1.3 course demonstration supplement

Members: OU JUNHANG, ZHANG XIQIAN, JIANG YIFAN, CAI SHANGHENG, GUO ZHENGKUN.
Prepared 18 November 2026. This supplement updates the software demonstration; the September Word/PowerPoint files remain historical artifacts. Recheck the original assignment before final submission.

## Suggested five-minute presentation

**0:00–0:40 — Problem and scope.** “JobCompass helps a job seeker inspect JobsDB vacancies, understand resume matches and investigate changes in advertised skills. It runs locally and keeps decisions with the user.” Explain historical versus online data and that scores are not hiring probabilities.

**0:40–1:30 — Python pipeline.** Open a fictional resume, show extracted skills and a ranking breakdown. Point to functions, dictionaries, sets, classes, file handling, parameterized SQLite and the transparent weighted algorithm. Show one source evidence excerpt rather than reading code line by line.

**1:30–2:30 — Research and generative AI.** Show an already-built research result with its plan, sample denominator and time windows. Explain DeepSeek command → validated JSON → local predefined operation → optional aggregate explanation. Use saved local results if the API is unavailable; do not imply the AI executed arbitrary code.

**2:30–3:25 — Learning and safe editing.** Open 技能成长 and generate a target-title plan. Explain frequency counting and recursive prerequisite traversal with cycle detection and immutable caching. In 投递看板 undo and redo one fictional note, showing persistent LIFO history.

**3:25–4:30 — Quality evidence.** Show an actual failing test log and the matching passing run, one isolated mutation caught by tests, the quality gate and the PR checklist. Distinguish local checks from an actually completed GitHub Actions run.

**4:30–5:00 — Limits and contribution.** Explain no labeled real-world ranking ground truth, authored learning prerequisites, read-only research data and remaining manual review. Each member describes only work they personally performed. The implementation and drafting were AI-assisted.

## Extended demonstration checkpoints

Use `python main.py --demo --db /tmp/group11-class-demo.db --port 8766 --no-browser` and fictional data. Include valid/invalid resume input, source labels, parameter bounds, unknown AI plan rejection, zero-sample learning, undo/redo after restarting, isolated tests and source-package exclusions. Show reproducible commands and actual outputs. Record the video and conduct classroom discussion yourselves; scripts are preparation, not evidence these events occurred.

## Answers the team should be ready to explain

1. Why are missing conditions excluded from the score denominator?
2. Why does a skill appear once per vacancy rather than once per word occurrence?
3. What is the recursive base case, and how is a dependency cycle detected?
4. Why must undo history and an application change share a transaction?
5. Why must cached results be copied before returning mutable dictionaries?
6. What can a killed mutation establish, and what can it not establish?
7. Why is line coverage different from branch coverage and correctness?
8. Which artifacts prove a CI run, code review or individual contribution actually occurred?
