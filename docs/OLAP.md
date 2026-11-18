# Recruitment OLAP and automatic natural-language analysis

The analytics engine groups JobsDB advertisement samples into a small, explicit data cube. Visitors can change dimensions, compare counts and mention rates, inspect a two-dimensional heatmap, and drill into an exact category or period. Natural-language commands are compiled into the same typed query language and executed automatically after validation. The model supplies intent and chart configuration; SQLite supplies the numbers.

This feature is integrated into the public visitor analytics flow. Neither `OLAP` nor the natural-language compiler requires an account. Public deployment, visitor isolation and server-side administration are handled by the application layer; this module does not publish a cloud service or expose source database paths.

## Dimensions, measures and scope

| Dimension | Group label |
| --- | --- |
| `month` | `YYYY-MM` |
| `quarter` | `YYYY-Q1` through `YYYY-Q4` |
| `year` | `YYYY` |
| `sector` | Source category label |
| `location` | Source location label |

Each query accepts one or two different dimensions. Temporal groups use the advertisement's source-marked date, not the date of the browser request. Missing or impossible dates, including invalid calendar days, enter an explicit `Unknown` group. Empty category/location labels also become `Unknown`. An existing literal `Unknown` label shares that bucket.

| Measure | Computation |
| --- | --- |
| `ads` | Number of selected advertisements after the requested deduplication |
| `employers` | Distinct trimmed, lowercased employer display labels, excluding empty, `confidential`, `company confidential`, and `unknown` placeholders |
| `mentions` | Advertisements whose precomputed vocabulary mask contains the selected probe |
| `share_pct` | `100 × mentions / ads`, rounded to four decimal places; `null` when the denominator is zero |

Employer labels are not verified legal entities, and advertisements are not hiring headcounts. Vocabulary matches describe full-text mentions, not required proficiency. Categories and location labels are retained for chart display but are not automatically sent to the model as raw context.

The `research` dataset reads the existing first-observed-version SQLite index in read-only mode. It requires a current analysis index. The `current` dataset uses the existing isolated in-memory snapshot builder, which excludes demonstration records and represents the current mutable job state. Current records normally lack the historical research classification and freshness flags. Applying `common_only` or `fresh_only` to current records can therefore produce an empty cohort; the engine does not silently remove those filters.

## Typed query and execution

```python
from jobcompass.olap import OLAP, validate_query

analytics = OLAP(research)
result = analytics.run({
    "dataset": "research",
    "dimensions": ["month", "sector"],
    "measure": "share_pct",
    "concept": "python",
    "filters": {"common_only": True, "fresh_only": True},
    "exact_filters": {},
    "dedup": "id",
    "limit": 100,
    "sort": "label"
})
```

Only these top-level query fields are allowed:

| Field | Validation/default |
| --- | --- |
| `dataset` | `current` or `research`; default `current` |
| `dimensions` | One or two distinct allowed dimensions; default `["month"]` |
| `measure` | One of the four measures; default `ads` |
| `concept` | A key from the existing probe dictionary; default `python` |
| `filters` | Existing research text/date/boolean filters; default `{}` |
| `exact_filters` | Exact dimension values for drilldown; default `{}` |
| `dedup` | `id` or `family`; default `id` |
| `limit` | Integer 1–100; default 50 |
| `sort` | `label` or `value_desc`; default `label` |

`filters` supports literal substring matching on `title`, `company`, `location`, and `sector`; inclusive `start`/`end` dates; observed-by `cutoff`; and `common_only`/`fresh_only` booleans. The existing `validate_plan` and `_selection` determine their semantics. In particular, family deduplication keeps the first globally observed employer/body family **before** applying later filters. A later repost does not reappear merely because a date filter excludes the first record.

`exact_filters` supports the five cube dimensions, including dimensions not currently displayed. For example, `{"sector":"Engineering","month":"2026-02"}` selects one category and month before grouping. A literal `Unknown` selects the missing bucket. Dimension values are bound SQL parameters, never inserted into SQL text. If you change the displayed dimension from month to quarter while retaining an exact month filter, the query still represents that month; clear the filter when the intended cohort is the entire quarter.

All SQL identifiers and expressions are selected from fixed maps. The model and user cannot supply SQL, executable expressions, arbitrary table names or filesystem paths. Invalid queries raise `ValueError`. `validate_query` returns an independent normalized copy without modifying its input.

The application exposes direct queries through `POST /api/analytics/query`, accepting a query object or a `query` wrapper. This endpoint returns the computed result directly. Catalog requests are handled by the application's analytics catalog route.

## Result and mathematical interpretation

Every result has `query`, `rows`, `totals`, `metadata`, and `pivot`:

```json
{
  "query": {"dimensions": ["month"], "measure": "share_pct"},
  "rows": [
    {"month": "2026-01", "ads": 3, "employers": 2, "mentions": 1, "share_pct": 33.3333, "value": 33.3333},
    {"month": "2026-02", "ads": 1, "employers": 1, "mentions": 1, "share_pct": 100.0, "value": 100.0}
  ],
  "totals": {"ads": 4, "employers": 2, "mentions": 2, "share_pct": 50.0},
  "pivot": null
}
```

This illustrative abbreviated response shows why totals are computed from the underlying filtered records. The overall rate is `2/4 = 50%`, not the arithmetic mean of `33.3333%` and `100%`. The employer that appears in both months is counted once in the total, so summing the displayed employer counts would be wrong.

The row limit applies only to displayed groups. Total ads, distinct employers, mentions, rates and `metadata.total_groups` are independent of the limit. A truncated chart never changes its KPI denominator. Sorting by value uses the selected measure and breaks ties deterministically by group labels. Empty cohorts have zero counts, no rows and a `null` rate. Missing months are not manufactured as zero-demand records.

Two-dimensional results include:

```json
{
  "row_dimension": "month",
  "column_dimension": "sector",
  "row_labels": ["2026-01", "2026-02"],
  "column_labels": ["Education & Training", "Engineering"],
  "values": [[0, 1], [null, 1]]
}
```

The pivot contains the selected measure and only the displayed groups. An actual observed group with zero mentions has value `0`; an absent intersection has `null`. When the query is truncated, an absent intersection may also be a group outside the displayed limit. The metadata marks this as `pivot_scope: "displayed_groups_only"`; the matrix is not a complete materialized cube.

Metadata includes `fingerprint`, `total_groups`, `returned_groups`, `truncated`, `warnings`, `date_meaning`, `employer_definition`, `updated_at`, `elapsed_seconds`, `label_source`, and the missing-bucket/pivot interpretation. The current-data fingerprint hashes the **same in-memory snapshot** used by the queries, avoiding a second possibly newer database read. For research data, the existing index/source fingerprint is reused. `updated_at` means the research index build timestamp or the latest current-data observation date; it is not a promise that all advertisements remain open.

## Catalog and bounded facets

`analytics.catalog(dataset=None)` returns:

- `dataset` and `default_dataset`; the default is research when its index is ready, otherwise current.
- `datasets`: IDs, labels, availability, and a reason when unavailable. The selected available dataset also has unfiltered ad/employer counts, a `[first_date,last_date]` date range and update information. Research includes its index fingerprint; the metadata-only current catalog omits a fingerprint because it deliberately skips vocabulary extraction. Unselected datasets may omit detailed statistics; research can expose a cheap stored index count/build timestamp. Unavailable datasets omit counts rather than pretending they contain zero advertisements.
- `dimensions`, `measures`, and `concepts`: labeled options for controls; measures include display units.
- `facets`: at most 50 `{value,ads}` groups per dimension for the selected dataset, plus `facet_limit: 50`.

Catalog counts/facets describe the selected full dataset under the ID-based input representation. They are not dynamically filtered counts for a query, and they do not inherit a user's family-deduplication choice. Changing datasets requests its catalog; the initial catalog does not construct or scan unselected datasets. UI controls must allow absent optional statistics on unselected entries. A stale research index is not silently substituted with current data when an explicit research query is executed.

`Research._current(include_mask=False)` is used only for current-dataset catalog metadata, which never needs probe counts. Its normal default remains `include_mask=True`, so every analytical query still computes correct vocabulary masks and a full snapshot fingerprint. This removes the unnecessary 36-probe scan from catalog startup without caching an old dataset.

A local measurement on 251,042 research advertisements and 7,277 current records reduced the research-selected catalog from **10.6712 seconds to 1.0379 seconds**, with identical research totals and facet sizes. The selected-current catalog then took **0.5087 seconds**. Measurements used fresh OLAP instances without an application result cache; operating-system file caches were not flushed, and these are single-machine observations rather than deployment guarantees. The aggregate timing records are retained in `output/course-audit/catalog-before.json` and `output/course-audit/catalog-after.json`.

## Natural command to executed charts

```python
from jobcompass.analytics_ai import compile_and_run

result = compile_and_run(
    "按月份和职业类别展示 Python 全文提及率，用热力图",
    "research",
    analytics,
    context=None,
)
```

The corresponding application endpoint is `POST /api/analytics/command`. It accepts `command`, `dataset`, and optional `context`, then returns a background task ID. The task result is the ordinary OLAP result plus:

- `chart`: a validated `type` and title.
- `instruction`: the normalized query, model-produced explanation, model name, bounded token usage and `label_source: "model_prediction"`.
- `message`: a short completion message.

Commands accept 1–1,500 characters. One model compilation produces exactly `query`, `chart`, and `explanation`. The compiler validates the whole response, enforces the selected dataset, validates the typed query and chart, then executes once. There is no manual-plan approval screen between a successful command and its query. Unknown response/query/chart fields fail before execution. The shared model transport can retry transient HTTP failures; the compiler does not repair invalid instructions, repeat a failed local query or make a second model call to summarize the result.

Supported chart types are `bar`, `line`, `heatmap`, and `table`. A line chart supports one temporal dimension alone, or one temporal dimension plus `sector`/`location` for multiple category trends. The compiler normalizes the temporal dimension first, so `["sector","quarter"]` becomes `["quarter","sector"]`, while preserving filters, concept and measure. For example, “比较不同职业类别的季度 Python 提及率，画多条折线” can produce a quarter-by-sector line chart. Each category becomes a separate series; absent intersections remain `null` gaps rather than invented zero values. Two temporal dimensions or a line chart without a temporal dimension are rejected. A heatmap needs exactly two dimensions. Titles accept 1–160 characters and explanations 1–1,500. These texts and source group labels are untrusted display content; the UI must escape HTML where its renderer supports HTML tooltips or tables.

For a task outside the query language, the model can return the same three keys with `query: null`, `chart: null`, and an explanation. This is a refusal that raises a validation error and executes nothing. Salary standardization, causal modeling, hiring prediction and raw-data modifications are not silently replaced with unrelated counts. Model intent translation can still be mistaken; the visible normalized instruction lets the visitor verify what was actually computed.

## Follow-up context and data minimization

Follow-up context can be a previous typed query or `{"query": previous_query, "totals": previous_totals}`. Raw result rows are rejected. The compiler sends only allowed query structure, approved date/boolean filters, temporal exact filters, common-sector labels and bounded numeric totals. Title, company, location and other free-text values are withheld. Source paths, raw job text and resumes are not automatically attached. The user's new command itself is sent as entered after trimming.

To preserve a previous private cohort without transmitting its text filters, the server retains the normalized previous query locally. If the model omits `filters` or `exact_filters`, the corresponding complete previous field is inherited. If it explicitly supplies that field, the supplied object replaces the old one; `{}` clears it. The result contains the actual merged query used for execution. Context from a different selected dataset is rejected instead of silently crossing datasets.

The prompt explicitly treats user/context content as untrusted task data and cannot expand the schema or tool authority. The resulting statistics remain sample descriptions. They do not establish representative market demand, causality, statistical significance, verified employer identity, required skills or human-reviewed ground truth.

## Verification and course evidence

Run:

```sh
.venv/bin/python -m unittest tests.test_olap tests.test_analytics_ai -v
```

The 37 focused tests comprise 22 real SQLite OLAP tests and 15 compiler tests with a mocked model. They cover weighted rates, distinct employer totals, missing/impossible dates, quarter/year boundaries, independent group limits, measure sorting, exact drilldown, pivot gaps versus observed zero, empty results, existing deduplication semantics, literal injection-like filter values, read-only source preservation, current-data demo exclusion, snapshot fingerprints, bounded catalog facets, skipping unselected datasets/probe scans during catalog construction, strict schemas, automatic execution, multi-series line normalization with preserved scope, chart constraints, private follow-up inheritance/clearing and unsupported-intent refusal. No live model response quality is claimed by these deterministic tests.

Actual test-first failures are retained in `output/course-audit/olap-red.txt` and `output/course-audit/analytics-ai-red.txt`; the passing run is in `output/course-audit/olap-ai-green.txt`. The evidence includes a real invalid-calendar-date grouping failure before the date expression was corrected, not just missing-module failures. This work demonstrates relational aggregation, non-additive measures, a typed query language, read-only database boundaries, controlled model integration, automatic tool execution and reproducible regression testing.
