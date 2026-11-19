# Bounded multi-step career research agent

The career research workbench can now plan an aggregate analysis, execute it locally, inspect a restricted observation, and decide whether another analysis would help. The agent loop uses explicit tools, observation history and stopping rules. It extends the existing one-shot plan compiler; it does not grant the model access to Python, SQL, the filesystem or arbitrary network tools.

## Using it in the platform

Open “深度研究”, select the current job dataset or the connected research dataset, and enter a command of 1–1,000 characters. The research dataset needs its existing analysis index. Enable the checkbox consenting to send this command and restricted aggregate statistics to DeepSeek, then start the multi-step research action. The browser requests three logical model turns. The backend independently requires `consent: true`.

The interface displays each validated plan and its aggregate observation. “查看统计结果” opens the result saved by the existing research runner, including its denominators, cohort definition and warnings. Use the stop button to request cancellation. Cancellation is cooperative: an in-flight network call, its bounded transport retries, or a running local query must return before the agent stops. Already completed analyses remain saved.

A suitable command is “分析共同三类近期所见广告中 Python 和 SQL 的全文提及情况，说明样本边界。” The model may choose an overview followed by skill frequencies and then a summary; this sequence is not guaranteed. A model can also finish immediately if it considers the question unsupported. The result explicitly states when no local analysis was executed.

The command itself is transmitted as entered after trimming. The application does not automatically attach a resume, source database path or raw advertisement text. Do not put private material into the command unless sending that text is intended.

## Execution and API contract

The Python entry point is:

```python
from jobcompass.research_agent import run_agent

trace = run_agent(
    command="分析 Python 全文提及率及样本局限",
    dataset="current",
    run_plan=research.run,
    max_steps=3,
    progress=progress_callback,  # optional callback accepting keyword arguments
    cancel=cancel_event,        # optional object providing is_set()
)
```

The HTTP entry point is `POST /api/research/agent`:

```json
{"command":"分析 Python 全文提及率及样本局限","dataset":"current","max_steps":3,"consent":true}
```

The HTTP call returns a background task ID. Task polling returns the completed trace. The dataset is fixed to `current` or `research` for the entire run. `max_steps` must be an integer from 1 to 4; booleans, malformed input and missing consent are rejected before scheduling a model call.

Each model turn must return exactly one of:

```json
{"action":"run","plan":{"dataset":"current","action":"skills","concept":"python"}}
```

```json
{"action":"finish","summary":"A bounded explanation of the observed results."}
```

Unknown response fields are rejected. A run plan must explicitly identify its dataset and action, pass the existing `validate_plan`, and belong to the four permitted aggregate operations:

| Operation | Local computation |
| --- | --- |
| `overview` | Cohort size, category distribution and limited data-quality counts |
| `skills` | Counts and sample shares for the predefined vocabulary probes |
| `trend` | Monthly counts and shares for one probe |
| `compare` | Two non-overlapping date windows and a sample percentage-point difference |

`sample`, `pairs`, `dataset`, `forecast`, executable code and arbitrary operations are unavailable to this agent even though some are available through separate manual research controls. Filters are data values interpreted by existing parameterized queries. The model cannot change the chosen dataset, modify source records, execute generated SQL, choose a local path or request an extra tool.

Validated plans are canonicalized before execution; a duplicate plan stops the loop before running the tool again. Each successful callback result must have the expected plan and a valid saved-result ID. The existing `Research.run` persists individual analysis results. The task trace itself is held by the background-task system, so a server restart can remove that task trace while the saved analysis records remain available.

## Turn budget and HTTP retry budget

`model_calls` and `max_steps` count **logical model turns**, not HTTP requests. A `finish` decision consumes a turn. A failed model call also consumes its attempted turn. There is no additional model call to summarize after reaching the budget: budget exhaustion returns a deterministic stop message and the completed analysis trace.

The shared transport helper can make up to three HTTP attempts for one logical model call, retrying only explicit transient HTTP 429, 502, 503 or 504 responses. Therefore:

| Logical turn limit | Maximum transport attempts |
| ---: | ---: |
| 1 | 3 |
| 3, the browser default | 9 |
| 4, the API maximum | 12 |

These are upper bounds, not a promise that all attempts occur. The retry helper has a 95-second retry-scheduling window and bounded backoff; that scheduling window is not a hard wall-clock deadline for a socket operation already in progress. Timeouts, arbitrary network failures, invalid model JSON and invalid plans do not trigger a model-output repair loop. See `jobcompass/retry.py` for the shared retry policy.

The logical turn limit is not a billing cap. The trace's token `usage` sums the valid usage fields returned by successful logical responses; it cannot account for every failed request or any provider-side billing behavior. Cancellation likewise does not retract an already submitted request.

## What crosses the model boundary

The first request contains the user command, selected dataset, restricted schema and remaining turn budget. Later requests add a projected history with at most 40 aggregate rows per completed step. The projector uses a whitelist rather than removing a few known sensitive fields:

- Numeric counts, denominators and shares are retained. Shares and two-period differences are derived from the local counts.
- Skill labels must be members of the project's fixed probe dictionary; period labels must be `A` or `B`; month/date labels must validate as dates.
- Overview labels are restricted to the three common research sectors and `Unknown`. Other labels are merged into `Other sectors`. Distinct advertiser counts are not summed across that bucket, because one firm can occur in multiple groups.
- Only selected numeric quality counts and valid first/last dates can pass from overview details. Truncation and filtered-row counts are visible.
- Raw advertisement rows, descriptions, titles, company names, location names, sample evidence, resume text, filesystem paths, snapshot identifiers, arbitrary warnings and result IDs are excluded from model history.
- History retains approved date/boolean filters and the names of free-text filter fields, but does not echo their text values. The complete validated plan remains in the local trace for inspection.

The system instruction explicitly treats observations as untrusted data. Injection-like text in a raw record cannot become an executable tool instruction; arbitrary labels are also withheld by the projector. This boundary reduces data exposure and tool authority. It does not prove that every model interpretation is correct.

## Trace fields and stopping states

The result contains `status`, `summary`, `message`, `steps`, `model_calls`, `executed_steps`, `max_steps`, `dataset`, `model`, `label_source`, `usage`, and `limitations`. Each step contains `step`, `action`, `status`, `plan`, `result_id`, and `observation`; unavailable fields are `null`. A finish step additionally contains its model-generated `summary`.

| Final status | Meaning |
| --- | --- |
| `completed` | The model returned a valid finish response |
| `budget_exhausted` | All permitted logical turns were consumed |
| `cancelled` | The cancellation flag was observed between operations |
| `duplicate_plan` | The model proposed an already executed normalized plan |
| `invalid_response` | The decision, schema, dataset or action violated the allowed protocol |
| `model_error` | The model call failed |
| `tool_error` | Local execution or aggregate-result validation failed |

Executed analysis steps use `status: "executed"`. Model and tool exception messages are not echoed into the trace, avoiding accidental disclosure of keys, paths or raw response text. The user-facing error is a fixed explanation. Optional progress-observer errors do not undo or abort completed analyses.

`label_source: "model_prediction"` identifies the agent output as model-assisted interpretation. Local counts are computed by the existing research engine, but a completed model summary can still invent an interpretation, miss a limitation, or incorrectly describe a cohort. Check it against the saved results. Full-text mentions are not proof of requirements; advertising samples do not represent the whole labor market; these tools do not establish causality, hiring probability or statistical significance. No human gold labels or manual verification are claimed.

## Tests and retained evidence

The original 19 dedicated offline tests cover validated execution, observation feedback, early finish, turn limits, duplicate detection, dataset locking, the four-operation allowlist, strict model responses, cancellation before and during calls, saved-result retention, safe error handling, aggregate data minimization, bounded rows, overview category folding, percentage-point calculation and input validation. One test runs the real `Research.run` against temporary SQLite data and verifies that the resulting analysis can be reopened. All model calls are mocked; this suite does not contact DeepSeek or certify the quality of a live response.

Run the focused suite with:

```sh
.venv/bin/python -m unittest tests.test_research_agent -v
```

The tests were written and executed before implementation. The actual initial failure is retained in [agent-red.txt](evidence/agent-red.txt). The original combined agent, HTTP integration and retry run passed **53 tests**; the verified output is in [agent-http-green.txt](evidence/agent-http-green.txt). These logs record the automated development process; they are not an independent human review or a current whole-project test count.

This feature demonstrates a bounded planning/execution/observation loop, narrow tool interfaces, explicit state, defensive validation, cooperative cancellation, reproducible local computations, network-retry boundaries and mock-based regression testing. It complements the project's single-plan compiler and learning planner without replacing the manual evidence-review workflow.
