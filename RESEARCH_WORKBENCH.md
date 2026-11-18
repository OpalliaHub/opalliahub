# Career research workbench v1.2

Updated 8 October 2026. This release adds a local research workspace alongside resume matching, applications and direct JobsDB updates. It follows the user-supplied recruitment requirement-change report's emphasis on measurement validity: a dictionary mention is not a verified requirement or evidence of an emerging skill.

## Use in the browser

Start `python main.py`, open http://127.0.0.1:8765/ and choose **职业研究室**. On this computer the existing longitudinal JobsDB audit database is connected and its compact index has been built. On another computer, expand **研究数据库连接**, enter the audit SQLite path, connect, then build the index. The alternative **当前平台岗位** works with the local job library and does not require the full research database. Synthetic classroom jobs are excluded.

Use the right-hand controls for deterministic local calculations. Or type an instruction, select **生成分析计划**, review the generated JSON plan and select **运行此计划**. Example commands:

- 比较 2025 年 3–4 月与 2026 年 3–4 月，共同三类近期所见广告中 Python 的全文提及率，按唯一广告 ID 去重。
- 分析 Education & Training 类别的近期所见广告，列出 36 类能力的全文提及率。
- 查看共同三类中生成式 AI 词语在同一广告首末观察版本中的新增与删除，给出 20 个原文样例。
- 筛选标题包含 Data Analyst 的广告，按唯一 ID 去重，预览并导出前 100 行。

CSV exports contain the displayed result rows. JSON exports include the plan, sample denominator, source fingerprint, timing and limitations. Record previews and evidence examples have a 200-row ceiling; exports are not unrestricted full-database dumps. **保存当前筛选队列** stores a reusable selection definition without modifying source records. Prior results remain available after restarting the service.

## Implemented analysis

| Operation | Computation and interpretation |
| --- | --- |
| overview | Platform category counts, named advertiser display-name counts, location/title distributions and salary missingness. Category is not an O*NET occupation code. |
| dataset | Filtered, deduplicated metadata preview and CSV export, ordered by observation date and ID. |
| skills | Each of 36 frozen regex probes counted at most once per advertisement; denominator and percent disclosed. |
| trend | Monthly shares from first-observed text and its listed date; absent months are not filled with zero or joined by a continuous trend line. |
| compare | Two non-overlapping inclusive date windows; local numerator, denominator and percentage-point difference. Empty denominators return null. |
| sample | Deterministic probe evidence examples, first record hash, character offsets in source content_text, rule provenance and empty human-gold field. Contact masking can change displayed excerpt offsets. |
| pairs | First/last observed versions with a probe added or removed, source hashes and excerpts. An edit is not automatically a stronger requirement. Cutoff mode includes only ads whose final observation also precedes cutoff; it does not reconstruct the last intermediate version. |
| forecast | One-probe retrospective diagnostics for last mature month and recent three-month mean; no emergence or causal forecast. |

The controls support title, category, date range, observation cutoff, common-sector restriction, fresh-observation restriction and ID/family deduplication. JSON plans also accept company and location substrings. Current-platform jobs have no longitudinal classification/freshness metadata: those two restrictions are off by default when selecting that dataset.

## Data and measurement

The source adapter reads the existing `jobs`, `records`, `record_quality`, `observations` and `snapshots` audit tables with SQLite `mode=ro` and `query_only=ON`. It selects the first observed version of each dated, valid advertisement with at least 100 content characters. It does not substitute later text for a missing first version. The local index contains **251,042 advertisements**, matching the supplied report's first-text population; the source contains **896,503 valid dated observations across 67 snapshots**. These are different units.

The 36 probe expressions are copied with their original exploratory status from the report's research analysis. They were selected on 6 October 2026; this is not open-vocabulary discovery or a historically frozen 2025 system. All outcomes are `rule_derived`; DeepSeek explanations are `model_prediction`; `human_gold` stays null. The current release does not implement an independent human-label collection or adjudication study.

A fresh observation is between minus one and 35 days after the source-listed timestamp. Source scrape timestamps have an unverified timezone; minus one day is a screening tolerance. The comparison uses IT, Engineering and Education as common categories. Family sensitivity keeps the first observed normalized employer-name plus exact-body-hash group globally before other filters, which can remove genuine repeated hiring. Names are not entity-resolved employers. No currency/period normalization or salary-premium inference is performed.

The default all-date view includes October 2026 observations; its 132,459 common-sector fresh IDs therefore differs from the report's 130,420 total limited to February 2025–September 2026. Match date filters before comparing these totals.

The report's Python comparison was recomputed from the source: March–April 2025 **1,423/19,109 = 7.4468%**, versus March–April 2026 **1,523/15,069 = 10.1068%**, difference **2.66 percentage points**. These are descriptive sample mentions, not market demand or significance estimates. Reported bootstrap intervals, O*NET mapping, open-world discovery and gold-label benchmark scores have not been recreated in this application.

The forecast protocol starts training in September 2025, considers January–August 2026 origins, excludes July's collection gap and requires three mature training months. Each vintage is frozen at next-month start plus 35 days, conservatively cutting at the preceding full date because the compact index stores dates. This excludes immature August and leaves February–June as eligible origins for the full corpus. June follow-up overlaps July's gap and should be examined separately. These are per-probe diagnostics and do not claim to reproduce the report's pooled 36-probe error scores. Modern LLM pretraining and retrospectively selected probes remain sources of future-knowledge contamination even when observation dates are truncated.

## DeepSeek and reproducibility boundaries

DeepSeek receives the user's typed instruction plus allowed plan fields, not the source database. Optional result interpretation receives selected aggregate counts, percentages and cohort settings. Raw evidence, paired excerpts, resume data, local paths and credentials are excluded from that interpretation request. The UI labels model explanations separately; they can still misinterpret a statistic, and the local table is authoritative.

The integration uses [DeepSeek JSON output](https://api-docs.deepseek.com/guides/json_mode/) with non-thinking structured responses. Every returned plan is validated against allowed operations, fields, dates and limits. Unknown keys, arbitrary SQL/Python, external paths and mutation operations are rejected. There is no `eval`, `exec`, generated SQL or subprocess execution. SQL column names originate only from code; values are parameterized.

The data identity is a SHA256 of source path, byte size, modification time and the frozen probe file. It detects routine source changes and is checked before analysis; it is **not a full content checksum** of the 1.9 GB source. The index file can be rebuilt. Original archive checksums remain in the upstream audit project. Old saved results retain their prior data fingerprint and plan. Full raw databases, compact local indices, saved user runs and personal configuration are excluded from GitHub and the source ZIP.

## Command line

```bash
python scripts/research.py --source /path/to/research/data_audit/jobsdb.sqlite --build
python scripts/research.py --plan exported-research-result.json
python -m unittest discover -v
```

The source database path may also be configured with `JOBCOMPASS_RESEARCH_DB` in `.env`. The local connection UI persists a selected path in the application database. On this computer the sibling research workspace is auto-discovered; no user-specific absolute path is committed. The full audit database must be supplied separately for longitudinal research. The bundled historical job snapshot enables current-library analysis on another computer.

## Verification and course artifacts

See `research_verification.json` and `test_results.txt` for actual local checks. Tests cover reference denominators, family sensitivity, future observation exclusion, mature training windows, cancellation preserving the index, SQL/code rejection, CSV formula escaping, schema validation, source immutability and evidence provenance. Browser checks exercise a live Chinese command, plan execution and CSV export. This release does not assert a hosted multi-user big-data service, a scientific novelty result, model accuracy or a completed research benchmark.

The Word, PDF and PowerPoint files under `docs/submission` and the old course bundle remain the 30 September classroom revision. The current v1.2 code and this guide are the new deliverables; those classroom artifacts should not be presented as descriptions of the research module.
