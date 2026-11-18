# JobCompass Demonstration Guide

Group 11. OU JUNHANG, ZHANG XIQIAN, JIANG YIFAN, CAI SHANGHENG, GUO ZHENGKUN.

Revised 30 September 2026. The classroom presentation uses exactly five slides and five minutes. The separate video lasts fifteen minutes. Presenter assignments are suggestions for rehearsal, not evidence of completed contributions. Use the fictional resume and a separate demo database when recording.

## Preparation and launch

Start from the extracted project directory. Install requirements using the README. Start the Python service before opening http://127.0.0.1:8765/. On macOS the launcher is 启动JobCompass.command. Keep the terminal open. GitHub stores the downloadable package and is not the running application. Opening static/index.html directly only displays launch guidance.

For a separate demonstration database and port, run these commands in order. The import command exits before the server starts:

```bash
python main.py --db data/class_demo.db --import-benchmark
python main.py --db data/class_demo.db --port 8766
```

Open http://127.0.0.1:8766/. Click 体验示例匹配 to load the fictional resume. This demo database contains 12 fictional jobs plus 6,908 imported historical JobsDB jobs, for a total of 6,920. A previously used database can have other sources, so its total may differ. The benchmark itself uses 6,910 accepted research records, including two already expired records that the app excludes.

Prepare the data workspace, matching view and application board before recording. Use the source filter to separate historical JobsDB records from classroom samples. Set an explicit zero-year experience preference when comparing against the research benchmark. Its script does not set a location preference. GUI totals and ranking scores can differ when additional sources or preferences change the corpus.

## Five minute classroom script

### Slide 1 from 00 to 01 minute

Good afternoon. We are Group 11, and our project is JobCompass, a local Python application for resume-based job discovery. Job seekers often switch between several websites, compare inconsistent descriptions and maintain separate application notes. Our application brings those activities into one workflow. A user imports a resume, checks recognized skills and compares jobs with visible reasons for each score. The application also records saved jobs and application progress. Optional DeepSeek assistance can suggest clearer resume wording. The interface runs in the browser, while Python and SQLite run on the same computer. We start main.py and open the local address rather than opening the HTML file directly. The demonstration uses a fictional resume.

### Slide 2 from 01 to 02 minutes

The implementation separates responsibilities into Python modules. Resume processing uses regular expressions and file readers. Data-source modules normalize public API records and local imports. A separate benchmark module processes the research archive and produces a reproducible compressed dataset. The matching module uses weighted F1 and TF-IDF similarity. SQLite stores jobs and application records with parameterized SQL and transactions. The HTTP layer exposes the interface and starts bounded background tasks for collection and AI calls. This design makes behavior easier to test without contacting an external service. It demonstrates functions, classes, modules, file input, data structures, networking, persistence, specification and testing. Secrets stay in local configuration and do not enter the submitted package.

### Slide 3 from 02 to 03 minutes

The project supports two live public integrations, Remotive and Arbeitnow. It also integrates an existing JobsDB research archive from the group's collection, dated 28 September 2026. We read that archive locally rather than claim a new live JobsDB scraper. It contains 6,939 input records. Validation accepts 6,910 and rejects 29 with invalid or missing required data. The app imports 6,908 because two records were already marked expired. Cleaning removes HTML and tracking objects, retains canonical job links and masks common contact text. The manifest records checksums so the input and output can be identified. These are historical vacancies. Their presence in the research dataset does not guarantee that an employer is still recruiting.

### Slide 4 from 03 to 04 minutes

The matching score has five components. Skills contribute a base weight of 45 percent, text 25 percent, experience 15 percent, location 10 percent and education 5 percent. Skill matching uses weighted precision and recall, so a generic skill alone has limited influence. Unknown requirements leave the active denominator, and the interface displays coverage. TF-IDF depends on the current job corpus, so scores can change when more jobs enter the database. Each job detail shows matched skills and gaps for human inspection. DeepSeek supplies explanations and a separate resume draft after user authorization. It does not set the numeric ranking score. The score helps prioritize investigation and cannot represent a hiring probability.

### Slide 5 from 04 to 05 minutes

The current version passes 71 local automated tests. These cover invalid inputs, persistence, matching, request boundaries and the research import pipeline. The real-data benchmark ranks 6,910 accepted JobsDB records for a fictional resume. Its recorded median is 4.0517 seconds across three local runs. This measures ranking runtime only. There are no human relevance labels, so we do not claim real-data accuracy, recall or NDCG. The separate synthetic fixture has twelve authored jobs and only demonstrates expected sample behavior. Our demonstration shows the resume evidence, a score breakdown and a saved application record. Codex assisted implementation and documentation. Each member must verify the project and report their own actual contributions. Independent relevance annotation is a future improvement.

## Fifteen minute video sequence

### 00:00 to 01:00 Problem and launch

Introduce Group 11 and the job-search problem. Show main.py or the launcher, then the correct localhost address. Explain that GitHub distributes the code. Identify the fictional resume and the separate demonstration database.

### 01:00 to 03:00 Resume evidence

Open 我的简历 and load the fictional example. Inspect recognized skills and their supporting text. Set zero years of experience and explain that a missing value stays unknown. Do not show a real member's private contact information. Save before requesting AI assistance.

### 03:00 to 05:00 Sources and research import

Open 数据工作台. Show Remotive and Arbeitnow, their attribution and the six-hour collection interval. Show JobsDB 研究快照 and run its local import. The task should report 6,908 imported records. Repeat import to demonstrate that source/URL records update rather than multiplying. Explain the distinction between 6,939 input, 6,910 accepted and 6,908 app-imported records. Do not claim the UI's overall total is the benchmark size.

### 05:00 to 07:30 Matching and limitations

Open 岗位发现, select a source and inspect a job. Explain the five weights, coverage, matched skills and missing evidence. Compare an entry-level sample with the senior Python sample, which has experience and geographic requirements. Restore filters if needed. State that a missing skill means the resume did not demonstrate it, not that the person lacks it.

### 07:30 to 09:30 AI assistance

Use the fictional saved resume. Select the consent checkbox and request strengths or polishing. Show task feedback and compare the separate draft with the original. Do not display the API key or balance. If the request fails, show the clear error and continue with the offline workflow. A previously saved result must be identified as a previous result rather than a new successful call.

### 09:30 to 11:00 Application tracking

Save a fictional sample job, set status to 面试中 and add the note 课堂演示. Open 投递看板, refresh and verify persistence. Export the job list if useful. Clarify that changing the status does not send a real application to an employer.

### 11:00 to 13:00 Tests and benchmark

Run python -m unittest discover -v and show the current result. Run python scripts/benchmark_jobsdb.py and explain the record count, field completeness, three timing measurements and empty relevance metrics. New timing results may differ from the recorded 4.0517-second median. Show the source manifest and identify the fictional resume. Do not describe the synthetic Precision at 4 result as measured accuracy on JobsDB.

### 13:00 to 14:00 Error handling

Try saving fewer than 30 characters as a resume. Confirm an error and preservation of the previous record. Try importing an empty JSON array and explain batch validation. Describe the offline fallback for unavailable external APIs. Keep invalid data separate from the real database.

### 14:00 to 15:00 Conclusions and disclosure

Summarize the useful workflow and Python techniques. Explain historical data, dictionary coverage and the lack of independent relevance labels. State that the GitHub archive contains a workflow configuration but has not run cloud CI from inside the ZIP. Disclose AI assistance and close with the group's next evaluation step. Members must record and present themselves.

## Questions and concise answers

Why use deterministic ranking? It provides a reproducible offline baseline and exposes components that a user can inspect. AI requests are reserved for explanations and wording.

Does JobsDB integration collect live data? This version imports a supplied historical archive. It does not use login traffic or restricted JobsDB APIs.

Why are there three dataset counts? There are 6,939 input records, 6,910 accepted historical records and 6,908 app records after removing two already expired jobs.

Does 71 passing tests prove relevance? It verifies specified behavior. Relevance requires independent human judgments of resume-job pairs, which were not provided.

Why can scores change after importing more jobs? TF-IDF recalculates term rarity over the current corpus, and saved preferences can change active components.

Why is the browser page blank when opening a file? The Python service supplies data and HTTP routes. Start the program and open its localhost URL. The revised file preview explains this requirement.

What remains for the members? Supply student IDs, verify understanding, record the video, attend the classroom presentation, complete peer assessment and write truthful individual reports of at least 600 words.
