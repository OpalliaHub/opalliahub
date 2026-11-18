# JobCompass Project Proposal

INT6181 Applied Programming with Python

Group 11

Members: OU JUNHANG, ZHANG XIQIAN, JIANG YIFAN, CAI SHANGHENG, GUO ZHENGKUN

Revised scope dated 30 September 2026

## Background and objectives

Job seekers compare inconsistent descriptions across recruitment websites and often keep application records separately. JobCompass addresses this problem with a local Python application that connects resume analysis, job discovery and application tracking. The project aims to make recommendations inspectable by showing the evidence and missing requirements behind a ranking score. It supports individual job seekers and provides a substantial course project combining file processing, information retrieval, database operations and network integration.

## Functional scope

Users can paste a resume or import TXT, DOCX and text-based PDF files. The application extracts dictionary skills, education and explicitly stated experience, then keeps supporting resume text for inspection. Users can search and filter jobs, inspect score components, save positions and track application progress. An optional DeepSeek integration explains strengths and suggests resume revisions after the user authorizes transmission. The revised text remains separate from the original resume.

The application collects public jobs from Remotive and Arbeitnow and supports authorized CSV, JSON and structured webpage imports. The revised scope also includes a frozen JobsDB research snapshot supplied through the group's OneDrive collection. This integration reads existing files locally. It does not claim a live JobsDB crawler or access to restricted recruitment APIs. Original source links and snapshot dates remain visible.

## Matching and research data

The ranker combines weighted skill F1 at 45%, TF-IDF text similarity at 25%, experience at 15%, location at 10% and education at 5%. Missing conditions leave the active denominator, and the interface shows condition coverage. Generic English and communication skills receive lower weights within the skill calculation. The result supports comparison and does not estimate an employer's hiring probability. DeepSeek provides assistance but does not determine the numeric score.

The selected JobsDB archive is dated 28 September 2026. Of 6,939 input records, 6,910 pass required-field validation. The application imports 6,908 after excluding two records already marked expired in the snapshot. Research evaluation retains all accepted records. Cleaning removes raw tracking and contact objects, strips HTML and masks common email and Hong Kong phone-like text. Historical job availability still requires verification at the original source.

## Python implementation and usability

Separate Python modules handle resumes, data sources, benchmark conversion, matching, SQLite persistence, HTTP requests and AI calls. The design uses functions, classes, regular expressions, JSON, CSV, ZIP, gzip, parameterized SQL and a bounded thread pool. A browser GUI runs through main.py at http://127.0.0.1:8765/. Users start the Python service first rather than opening the HTML file directly. API keys and personal databases remain outside the submission package.

## Evaluation and deliverables

Verification combines offline tests, synthetic ranking examples, real service connectivity records and reproducible research-data measurements. The current implementation passes 71 local tests. Its recorded full ranking of 6,910 research jobs takes 4.0517 seconds median across three runs on macOS with Python 3.8.10. No human relevance labels were supplied for this snapshot, so the project does not report real-data precision, recall or NDCG. Human annotation and broader evaluation remain future work.

Deliverables include main.py, README.md, source code and tests in group11_project.zip, a five-slide group11_presentation.pptx, a timed demonstration guide and technical documentation. Each member must submit an individual PDF of at least 600 words describing actual contributions. The group must record its own 15-minute video and complete a five-minute classroom presentation. AI assistance is disclosed. Student IDs and personal contribution evidence remain to be supplied by the members.
