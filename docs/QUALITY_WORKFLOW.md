# Engineering quality workflow — Group 11

This document connects the implementation to Lecture 06–10 and Tutorial 5. Automated checks were implemented and executed by the coding assistant. Student walkthroughs, debugger practice, peer review and a GitHub Actions run must be recorded when they actually happen; this document does not invent those activities.

## Run the checks

From the project root, using the same interpreter as the application:

```sh
python scripts/quality_gate.py --mutations
python scripts/quality_gate.py --quick
python scripts/mutation_check.py
python -m unittest tests.test_quality_gate -v
python -m doctest -v scripts/quality_gate.py
```

On the supplied Mac checkout, `python` can be replaced with `.venv/bin/python`. The full gate runs the source scan, AST syntax validation, executable docstrings, all discovered unit/integration tests, optional mutation experiment, ZIP creation, and verification of the exact ZIP. It fails closed and writes `output/quality/report.json` plus per-stage logs. `--quick` explicitly reports `quick_checks_passed`; it does not imply that the whole test suite ran. The checks require no AI key or live JobsDB requests. HTTP regression tests bind an ephemeral localhost port.

## Test design and traceability

| Requirement / defect risk | Representative validation | Technique |
|---|---|---|
| Job ranking must favor relevant skills and respect experience | `tests.test_core.MatchingTests` | Equivalence classes, boundary values, deterministic assertions |
| Imports and research plans must reject malformed or excessive inputs | `tests.test_core.ImportTests`, `tests.test_research.ResearchTests` | Negative cases, type and range boundaries, SQL-injection-as-literal fixtures |
| AI must not execute arbitrary model-provided code or leak a key | Mocked AI responses in core/research tests | Dependency isolation, mocks and malformed output tests |
| Local state must not appear in submission ZIPs | `tests.test_quality_gate.QualityGateTests` | Temporary fixtures, forbidden paths, duplicates, traversal, symlinks, CRC and archive bounds |
| Scanning must not read a local `.env` through a symlink | `test_scan_never_opens_private_env_or_symlink` | Mocked file access that raises if a forbidden read occurs |
| Packaging findings must not echo a credential | `test_scan_reports_location_but_never_secret_value`, archive counterpart | Generated dummy token and redacted result assertions |
| A broken ranking/plan rule must be detected by tests | Five isolated mutation cases | Test effectiveness, beyond a green test count |

Test fixtures are synthetic and temporary. A high passing count alone does not establish real hiring accuracy, comprehensive security or complete coverage. The gate also invokes `scripts/static_checks.py` when available: it checks mutable defaults, bare exception handlers, direct eval/exec and wildcard imports. This is focused AST linting, not PEP 8 style checking or a type checker. Benchmark labels remain explicitly synthetic or rule-derived.

## Actual test-first records

Two small changes were developed with recorded failures before implementation. This is evidence for those changes only; it does not claim that the earlier application was entirely developed with TDD.

1. **Unittest-first publication gate.** Thirteen acceptance tests were written against four minimal interface stubs. Running `python -m unittest tests.test_quality_gate -v` failed with `Ran 13 tests` / `FAILED (failures=21, errors=2)`. Multiple failures were subtests, so 21 is not a count of test methods. After implementation, the same thirteen tests returned `OK`. Three additional archive regression tests were then added; all sixteen passed. The initial uppercase prototype function was subsequently renamed to `private_reason` during implementation.
2. **Doctest-first path validation (Tutorial 5).** Four examples were written in `archive_relative` while its implementation was `return None`. `python -m doctest -v scripts/quality_gate.py` reported `4 passed and 4 failed` (the four older `private_reason` examples already passed). After implementing root/path validation and calling it from the ZIP verifier, the same command reported `8 passed and 0 failed`.

The unedited command outputs are local files:

- `output/course_engineering/tdd_red.txt`
- `output/course_engineering/tdd_green.txt`
- `output/course_engineering/tdd_doctest_red.txt`
- `output/course_engineering/tdd_doctest_green.txt`

These records demonstrate the test-first pattern taught by Tutorial 5. The VeriVibe VS Code extension was not installed or exercised, and no sidebar status or student participation is claimed. Re-running the final code should produce green; the historical red output is evidence of the earlier stub state, not a currently failing program.

## Mutation experiment

`scripts/mutation_check.py` copies application modules, two test modules and demo fixtures into a `TemporaryDirectory`; `.env` and real databases are not copied. The unchanged copy first runs 32 baseline tests. Each mutation receives a separate copy, one exact code change, and the corresponding test class. Original source SHA-256 values are checked again afterwards.

| Deliberate fault | Expected detector | Observed result, 18 November 2026 |
|---|---|---|
| Sort ranking score ascending | Relevance / generic-skill cases | Killed; 2 assertion failures |
| Replace skill intersection with union | Relevance / generic-skill cases | Killed; 2 assertion failures |
| Remove experience penalty | Experience requirement case | Killed; 1 assertion failure |
| Permit limit 201 instead of maximum 200 | Invalid model plan cases | Killed; 1 assertion failure |
| Accept boolean as integer limit | Invalid model plan cases | Killed; 1 assertion failure |

The observed targeted result was **5/5 killed**, with a passing baseline and unchanged original source. Only assertion failures count as kills. Import errors, timeouts, invalid anchors and unrelated execution errors are inconclusive and fail the experiment. This denominator is five hand-selected faults, not all possible mutations or a whole-project coverage percentage. Machine-readable evidence is in `output/quality/mutations/report.json` and the sibling logs.

## CI and delivery

`.github/workflows/tests.yml` defines push, pull-request and manual triggers; there is no scheduled collection or live API call. Its matrix covers Ubuntu with Python 3.8, 3.11 and 3.13, plus macOS with Python 3.11. Each job installs declared runtime dependencies and runs the same gate with mutations. Failure logs are uploaded with distinct matrix names. Only after all matrix jobs succeed does the delivery job build and verify `group11_project.zip`, then publish it as an Actions artifact. This is continuous delivery of a local-app submission, not automatic deployment of a public web server.

The official Actions repositories were checked for the `checkout`, `setup-python` and `upload-artifact` usage used here. See [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python), and [artifact upload](https://github.com/actions/upload-artifact). The workflow uses their documented v7 action tags, read-only repository permissions and no persisted checkout credentials. Tags should be periodically reviewed; they are not immutable commit pins.

The workflow file must exist under `.github/workflows/` **at the GitHub repository root**, alongside the unpacked source tree. A workflow merely stored inside a downloadable ZIP does not run. A real successful Actions URL is the evidence for cloud CI; the local report deliberately has `cloud_ci_verified: false`. No cloud execution is claimed by this document.

## Review and debugging practice

The pull request template is `.github/pull_request_template.md`; reproducible defect reports use `.github/ISSUE_TEMPLATE/bug_report.md`. Review a focused diff, not the full project at every iteration. Verify the behavior, tests and data assumptions before discussing style. Record any accepted shortcut in `TECHNICAL_DEBT.md`.

For the five-person inspection exercise in Lecture 10, assign actual participants to author, moderator, syntax/maintainability reviewer, logic reviewer, and input/output reviewer. Before the meeting, each reviewer reads the relevant code and writes concrete findings. During the meeting, agree on defects and decisions. After fixes, the moderator repeats the checks. For modern asynchronous review, put findings on the PR, reply with evidence and request a second review. The following is intentionally unfilled:

| Record | Actual value after the activity |
|---|---|
| Commit / PR and relevant requirements | Pending |
| Author, moderator and three reviewers | Pending |
| Findings with file and line references | Pending |
| Fix commits and rerun results | Pending |
| Moderator decision and date | Pending |

For a reproducible debugging exercise, run one named failing mutation test in a temporary copy, stop at the affected calculation, inspect types and values, step into the function, and compare the assertion with the expected requirement. The parent project's debugging lab supplies `pdb`/profiling instructions. A successful automated mutation run does not mean a student has personally performed that debugger walkthrough.

## Limits of the gate

The credential scanner matches a small explicit set of provider/GitHub token and private-key patterns; it is a regression safeguard, not a universal secret/PII detector. It scans allowlisted UTF-8 source and Office XML and reports only locations/rule names. It does not read local `.env`, raw/private data, databases or symlinks. Non-text embedded media and compressed benchmark contents are not searched for arbitrary personal information. The ZIP check additionally verifies names, required files, CRC, size bounds, duplicate members and symlinks without extracting its files.

Portable unit tests and mocked HTTP behavior cannot prove that an external website is available, that a browser rendering is correct, or that a model output is factually accurate. Keep the manual acceptance record separate from deterministic test evidence.
