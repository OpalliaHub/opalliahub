# JobCompass — Group 11

INT6181 Applied Programming with Python course project.

**Team:** OU JUNHANG, ZHANG XIQIAN, JIANG YIFAN, CAI SHANGHENG, GUO ZHENGKUN.

## Download and run

[Download the complete project ZIP](group11_project.zip?raw=true) and extract it. All source code, tests, documentation and the normalized research dataset are inside `group11_project/`. This repository currently distributes a complete source archive; the Python modules are inside the ZIP.

```bash
cd group11_project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

Open http://127.0.0.1:8765. On Windows use `.venv\Scripts\python` instead of activating with the Unix command. The offline core works without a DeepSeek key. To enable AI assistance, put your own key in the local `.env` file. No API key or personal resume database is distributed.

## Features

- Resume text, DOCX and optional text-PDF extraction.
- Explainable skill, text, experience, education and location ranking.
- Public Remotive/Arbeitnow collection and local file imports.
- Optional DeepSeek resume polishing and evidence-based strengths analysis.
- Local SQLite storage and application tracking; no automatic job applications.
- Chinese browser interface and Python command-line tools.

## JobsDB research benchmark

The included frozen snapshot is dated **2026-09-28**. It contains **6,910 normalized job records** from **6,939 input records**, with **29 rejected** for invalid/missing required data. The GUI's data workspace can import **6,908** jobs after excluding two already marked expired at snapshot time. These are historical research records; current availability must be checked at the original job links.

```bash
python main.py --import-benchmark
python scripts/benchmark_jobsdb.py
python -m unittest discover -v
```

All **71 local tests passed**. Full ranking of 6,910 jobs for the fictional demo resume took **4.0517 seconds median** over three runs on the author's local macOS/Python 3.8.10 setup. This measures runtime, not accuracy. There are no human relevance labels, so precision, recall, NDCG and hiring probability are not reported. See [benchmark results](benchmark_jobsdb.json) and `docs/BENCHMARK.md` inside the archive for provenance, cleaning, reproducibility and limitations.

Only the selected normalized snapshot is bundled. Raw OneDrive archives, other weekly snapshots, unrelated teaching materials, credentials and personal databases are excluded. Job content retains its original ownership; no new dataset license is asserted.

## Course materials

- [English Project Proposal](Group11_Project_Proposal.docx)
- [Five-slide presentation](group11_presentation.pptx)
- Source archive: specifications, code review, references, demo guide, individual-report draft and tests.

The implementation was generated and tested with AI assistance. Members must verify the work, record their own actual contributions and complete their own presentation/individual-report requirements. The package includes a GitHub Actions workflow for a source-tree checkout; it does not run while stored only inside the ZIP. No cloud CI pass is claimed.
