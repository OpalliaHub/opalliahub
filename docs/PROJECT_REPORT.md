# JobCompass Project Report

INT6181 Applied Programming with Python

Group 11

Members: OU JUNHANG, ZHANG XIQIAN, JIANG YIFAN, CAI SHANGHENG, GUO ZHENGKUN

Revision dated 30 September 2026

## Project outcome and scope

JobCompass is a working local application for comparing a resume with jobs from multiple sources and tracking applications. It integrates deterministic Python ranking with optional DeepSeek assistance. The latest version includes a cleaned JobsDB research snapshot, a reproducible benchmark and a browser interface that explains how to start the local service. It runs as a single-user program rather than a hosted public recruitment platform.

The project addresses a practical workflow: import a resume, find relevant vacancies, inspect requirements, improve wording where appropriate and record the next action. It does not submit applications, verify candidates' qualifications or make employers' hiring decisions. Core ranking and stored application records remain usable without the model service.

## User workflow and launch procedure

After installing the requirements, a user starts main.py or double-clicks the supplied macOS launcher. The complete interface opens at http://127.0.0.1:8765/. Opening static/index.html directly does not start Python. Relative asset paths now preserve the visual page in file mode, where a launch guide explains how to reach the service. Safari verification confirmed that the served interface loads its styles, scripts and job data.

The resume screen accepts pasted text, TXT, DOCX and text-based PDF. It shows skills with supporting text and allows the user to set location and experience preferences. The data workspace supports public collection, manual imports and explicit import of the bundled research snapshot. Job cards show source information and score components. Saved records move through an application board and retain notes after a job is imported again.

## Python architecture and engineering techniques

main.py provides the CLI and GUI entry point. resume.py handles extraction, regular expressions and evidence. sources.py normalizes external records and handles public integrations. benchmark.py reads JobsDB archives and validates a reproducible compressed snapshot. matching.py implements weighted F1 and TF-IDF with Python counters and mathematical functions. storage.py uses SQLite transactions, foreign keys and parameterized queries. server.py supplies HTTP routes and a bounded background task pool. ai.py validates structured model responses.

This separation supports testing each component independently. Network collection and AI operations run in background tasks with visible status. Invalid resume or import data produces a controlled error. A complete import batch is validated before database writes, and repeated source URLs update existing jobs while preserving application records. Secrets remain in local environment configuration and are not returned to the browser or included in source archives.

## Matching method and AI assistance

The base weights are skills 45%, text 25%, experience 15%, location 10% and education 5%. Skill matching uses weighted precision and recall and combines them through F1. English and communication each receive weight 0.2 within the skill sets, while other recognized skills receive weight 1. This reduces the influence of generic abilities on unrelated jobs. TF-IDF cosine similarity measures lexical overlap between resume and job text.

The total score is 100 times the weighted sum of available components divided by the sum of their active weights. Unknown requirements are not automatically satisfied. A coverage indicator explains missing conditions. Because IDF depends on the current corpus, adding jobs can change scores. Keyword recognition does not prove proficiency or handle every negation or language variation. The score is an ordering aid, not a calibrated hiring probability.

DeepSeek supports strength analysis, resume polishing and selected-job explanations. Users explicitly authorize sending the saved resume. Common identifiers receive limited masking, but this is not complete anonymization. The original resume stays intact. Generated claims still require human review. AI does not replace the deterministic score, and core functions do not require an API key.

## Research data and provenance

The integrated archive is 20260928112455_6939.zip, dated 28 September 2026 and supplied from the group's OneDrive research collection. The converter reads original_data JSON members without extracting archive paths. It rejects invalid required fields, ignores macOS metadata and deduplicates numeric JobsDB IDs. It retains source URLs without tracking parameters and produces a deterministic gzip file with an accompanying checksum manifest.

The archive contains 6,939 job records. Validation accepts 6,910 unique jobs and rejects 29. All accepted records form the historical benchmark. The application excludes two jobs marked expired at snapshot time and imports 6,908. There are 5,465 missing salary labels and 1,249 jobs with no recognized dictionary skills. No accepted job lacks a location label. Missing salary and skill coverage illustrate the limits of both the source and the parser.

Only this selected normalized snapshot accompanies the project. Other weekly archives and unrelated course materials are excluded. Raw tracking, contact and questionnaire objects are dropped. Text masking can overmatch phone-like numbers and is not universal anonymization. Job content retains its original ownership. The dataset is historical, so the user must check current availability at the source. The integration makes no live request to a restricted JobsDB API.

## Validation and measured results

The current offline suite contains 71 passing tests. Coverage includes resume parsing, unknown values, ranking behavior, invalid imports, persistence, HTTP request boundaries and AI response validation. Benchmark tests add archive filtering, checksum reproducibility, duplicate-ID rejection, contact masking, expired-record exclusion and preservation of application notes on repeat import. The recorded test output is in docs/test_results.txt.

The research benchmark ranks 6,910 jobs for the bundled fictional resume with an explicit zero-year experience preference. Three recorded runs take 4.0517, 4.0059 and 4.0634 seconds, with a median of 4.0517 seconds on macOS and Python 3.8.10. These figures measure ranking only. They exclude import, network transfer and browser rendering, and vary with hardware. The present server reranks on state refresh, so large datasets can slow interactions.

No human resume-job relevance labels were supplied. The project therefore leaves real-data relevance metrics unset. A separate twelve-job synthetic fixture reports Precision at 4 of 1.0, but this narrow result cannot establish recruitment accuracy. Earlier connectivity checks retrieved 16 Remotive and 325 Arbeitnow jobs and completed a DeepSeek request using fictional content. Those are historical service checks, not current vacancy guarantees or evidence of recommendation quality.

## Demonstration and delivery

The classroom deck contains exactly five slides for a five-minute explanation. A separate guide allocates fifteen minutes to the video, including launch, resume evidence, research import, score interpretation, AI assistance, application tracking and evaluation. The demonstrator should use a separate database and the fictional resume. The guide also provides a network-failure fallback and invalid-input examples.

The public GitHub repository currently distributes the complete project as a ZIP with supporting documents. It is a download location, not a hosted running application. The archive contains a GitHub Actions configuration, but storing a workflow inside a ZIP does not execute it. No successful cloud CI run is claimed. The local package excludes .env, personal databases, virtual environments and raw OneDrive archives.

## AI disclosure and remaining student work

Codex assisted specification, implementation, testing, review and documentation. The review record is an AI-assisted self-review rather than an independent audit. Group members must understand the code, verify their own demonstrations and document actual contributions. Student IDs, individual learning evidence, the recorded video and peer assessment remain student responsibilities. The individual-report draft is a starting point and cannot truthfully establish personal work without those additions.

References and reproducibility records are included in docs/REFERENCES.md, docs/BENCHMARK.md, docs/benchmark_jobsdb.json and the source tests. The course requirements come from the supplied INT6181 assignment document. Future improvements include independent relevance annotation, broader language coverage and caching or indexing for larger job collections.
