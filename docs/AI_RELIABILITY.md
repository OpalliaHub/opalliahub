# Bounded AI transport recovery

The resume and research DeepSeek adapters now share `jobcompass/retry.py`. It implements the bounded feedback/retry idea from Lecture 05 for a specific operational failure: an explicit transient HTTP response before a usable model result arrives.

| Condition | Behavior |
|---|---|
| Successful response | Return immediately; do not repeat it |
| HTTP 429, 502, 503 or 504 | At most three total transport calls; wait 1 second before the second and 2 seconds before the third |
| HTTP 400, 401, 402, 403, 404, 409, 422, 500 or another unlisted status | Propagate immediately |
| Connection failure, local timeout or unknown transport error | Propagate immediately; do not guess whether the server processed the request |
| Invalid JSON, missing fields, unsupported research action or invalid analysis plan | Validate after transport recovery and reject; do not automatically ask the model to repair it |

DeepSeek documents authentication, balance, rate-limit and service errors separately in its [official error-code reference](https://api-docs.deepseek.com/quick_start/error_codes/). This project's narrower four-status allowlist and three-call cap are local design choices, not a claim that every provider recommendation is implemented.

## Budget and implementation boundary

The request has a **95-second retry scheduling window**, measured using `time.monotonic()`. Before every attempt, the adapter passes `min(90, remaining_window)` as the transport timeout. It checks the remaining window before sleeping and again after sleep; a delayed scheduler cannot start another attempt outside the window. There are at most two sleeps totaling three seconds and at most three calls. The final original error is preserved when attempts or scheduling time are exhausted.

This window is not a hard wall-clock cancellation mechanism. The existing `urllib` timeout applies to blocking network operations, and an already running call can exceed the scheduling window; the helper does not forcibly cancel sockets or start replacement work in parallel. See the [Python urllib request documentation](https://docs.python.org/3/library/urllib.request.html). No retry is scheduled after an ambiguous timeout. The design does not promise exactly-once billing or processing for HTTP gateway failures.

`sources.fetch` translates `HTTPError` into a safe `ValueError`. Python retains the original exception as context; the retry helper checks that object's type and numeric status. It never parses a human error message, reads an error response body, prints credentials, changes the payload or alters the configured endpoint. Responses with an open error stream are closed before a retry. Existing tests patching `jobcompass.ai.fetch` and `jobcompass.research_ai.fetch` remain compatible.

The helper wraps only network transport. JSON parsing and schema validation remain outside the retry loop. Research plans still pass `validate_plan`, and neither a retry nor a model response can execute Python or SQL or modify the original research database. No live API request or paid model call was made to implement or verify this change.

## Actual test-first evidence

Twelve tests were written before the retry implementation, while the helper made exactly one transport call and the two adapters still called their existing transport directly. The initial run recorded `Ran 12 tests` and `FAILED (failures=1, errors=8)`; after implementation the same test suite passed. One mocked scheduler timestamp was refined from 94 to 93 seconds so the test actually exercises the post-sleep deadline check rather than the earlier budget guard.

- Red output: `output/course_engineering/retry_tdd_red.txt`
- Green output: `output/course_engineering/retry_tdd_green.txt`
- Reproduce final tests: `python -m unittest tests.test_retry -v`

All sleeps and transport calls are mocked. Tests exercise every permitted status, permanent HTTP errors, ambiguous failures, the attempt cap, precise 1/2-second delays, shrinking timeouts, scheduler overruns, unchanged payloads, both adapters, and rejection of malformed model output without a second call. The final local test run passed all 12 methods; this verifies the deterministic policy, not live provider availability.
