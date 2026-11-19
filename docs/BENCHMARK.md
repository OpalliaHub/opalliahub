# JobsDB research benchmark

## Provenance and scope

The project maintainer supplied a JobsDB research archive. The integrated version uses **20260928112455_6939.zip**, a snapshot dated **2026-09-28**. It is a frozen historical dataset, not a live JobsDB connection. Other weekly archives and unrelated personal files are not bundled. The original dataset's rights remain with its respective owners; this project does not assign it a new license or claim that research access establishes a general redistribution license.

The normalized snapshot is `data/benchmark/jobsdb_20260928.json.gz`. Its manifest records the input archive checksum, normalized-content checksum, source date, transformations and rejected record count. Paths to personal OneDrive accounts and cloud access links are not included.

## Data preparation

The converter reads JSON records under `original_data` without extracting archive paths. It ignores macOS metadata, validates numeric job IDs and required fields, converts HTML to text, keeps the source job URL without tracking parameters, and deduplicates by JobsDB ID. It excludes raw tracking objects, recruiter contact objects and application questionnaires. Email addresses and Hong Kong phone-like numbers in text are masked heuristically; this can also mask unrelated eight-digit numbers and is not universal anonymization. Descriptions are limited to 30,000 characters by the application's normalizer. Salary retains the original label; no currency or salary-period conversion is inferred.

| Check | Result |
|---|---:|
| Input job records | 6,939 |
| Rejected missing/invalid required data | 29 |
| Accepted unique jobs | 6,910 |
| Unique canonical URLs | 6,910 |
| Missing salary label | 5,465 |
| Missing location label | 0 |
| No skills found by current dictionary | 1,249 |
| Already expired at snapshot time | 2 |

All 6,910 accepted records are used in the historical benchmark. The application imports 6,908 records after excluding the two marked expired at collection time. Other jobs may have expired since then; open the source URL to check before applying. Repeated import updates the same source/URL records and preserves application notes.

## Reproduce locally

No API key, network request or real personal resume is required:

```bash
python scripts/benchmark_jobsdb.py
python main.py --import-benchmark
python main.py
```

A new local application database imports the bundled historical snapshot by default. Starting with `--demo` instead initializes a new database with fictional jobs. Existing databases are not reset. To request another import, use **数据管理 → JobsDB 研究快照 → 导入研究快照**; this explicit action runs as a background task. In public mode, visitors read the shared catalogue, while their own import actions remain in their private workspace.

To convert another compatible ZIP, provide the correct snapshot date and a separate output filename:

```bash
python scripts/prepare_benchmark.py /path/to/snapshot.zip --source "JobsDB research snapshot YYYY-MM-DD" --output data/private/custom.json.gz
python scripts/benchmark_jobsdb.py --snapshot data/private/custom.json.gz --output output/custom_benchmark.json
```

The converter supports the observed JobsDB JSON schema in ZIP files. It does not support 7z archives or infer unknown CSV schemas. Raw archives stay outside the source package. The default publication allowlist includes only the selected normalized snapshot and its manifest.

## Evaluation design and results

The benchmark ranks all 6,910 accepted jobs for the bundled **fictional** resume with an explicit zero-year experience preference. It reports field completeness, deduplication and three complete ranking timings. The recorded Python 3.8.10 macOS run took **4.0517 seconds median** (4.0517, 4.0059 and 4.0634 seconds). The raw report is [benchmark_jobsdb.json](benchmark_jobsdb.json); results depend on hardware and runtime. Import, HTTP transfer and browser rendering time are not included in those timings. These are uncached ranker measurements from the recorded benchmark. The current application uses a per-application [one-entry ranking cache](RANKING_CACHE.md) when a resume is present, so unchanged state requests can reuse the ranked result. Database reads, input hashing and result copying still cost time; the historical benchmark does not measure the current end-to-end UI.

No human resume–job relevance labels were provided. Therefore this dataset does **not** establish Precision@K, Recall@K, NDCG, hiring probability, real-world suitability or fairness. Top-ranked titles are diagnostic examples, not validated recommendations. The separate `scripts/evaluate.py` still uses explicitly synthetic relevance labels and must not be described as evaluation on this real dataset.

For future relevance research, define a rubric, have independent reviewers judge a held-out set of resume–job pairs, measure agreement, separate tuning and evaluation samples, and compare the hybrid ranker against a text-only baseline. No such judgments or outcomes are fabricated here.
