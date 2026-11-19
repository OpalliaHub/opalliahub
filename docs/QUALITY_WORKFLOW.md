# Engineering quality workflow

JobCompass uses deterministic tests, publication checks and explicit evidence to support changes to its research platform. Automated checks and AI-assisted review are distinct from independent human review, live provider availability and production acceptance. Record each outcome only after observing it.

## Run the checks

From the repository root, using the application's interpreter:

```sh
python scripts/quality_gate.py --mutations
python scripts/quality_gate.py --quick
python scripts/mutation_check.py
python -m unittest tests.test_quality_gate -v
python -m doctest -v scripts/quality_gate.py
```

The full gate runs source credential checks, Python syntax validation, executable documentation, discovered unit/integration tests, optional mutation checks, source packaging and validation of the exact archive. It fails on a rejected stage and records `output/quality/report.json` with individual logs. `--quick` reports `quick_checks_passed`; it does not imply a full test run. Checks require no AI key and do not contact recruitment sites. HTTP regression tests use an ephemeral localhost listener.

## Source release boundary

```sh
python scripts/package_project.py
python scripts/quality_gate.py --quick --package dist/jobcompass.zip
```

The archive is `dist/jobcompass.zip`, with one top-level `jobcompass/` directory. Its allowlist includes application code, tests, technical documentation, deployment examples, fictional fixtures and the existing selected benchmark snapshot. The benchmark's original ownership and historical scope remain distinct from the source license; see [open-source scope](OPEN_SOURCE.md).

The builder and independent verifier both exclude private state, database files, symlinks, nested ZIPs, document/presentation binaries and known classroom/report deliverables. Exclusions also apply if an old local copy reappears under a normally allowed folder. Keeping a file untracked is not sufficient to exclude it from a filesystem-based archive. File and directory symlinks are not followed; fixture paths cannot traverse a linked data directory.

The verifier checks the product archive root, traversal and absolute paths, required entry files, duplicate members, CRC, size limits and credential patterns. Tests exercise both archive rejection and the builder's actual file selection. These safeguards must remain in place when release naming or file selection changes.

## Test design

| Requirement or defect risk | Representative validation | Method |
|---|---|---|
| Relevant ranking and honest unknown-condition handling | `tests.test_core.MatchingTests`, recommendation tests | Equivalence classes, boundaries and deterministic scores |
| Invalid imports, unsafe plans and excessive input | Import, research and OLAP tests | Type/range checks, SQL-injection-as-literal fixtures and atomicity |
| AI output must remain typed data and respect privacy | Analytics/research AI and public HTTP tests | Mocked responses, invalid plans and cross-visitor access checks |
| JobsDB retries must respect provider limits | JobsDB transport, V7 and public tests | Bounded mocked transport, cancellation, shared cooldown and partial results |
| Source releases must omit private and excluded deliverables | `tests.test_quality_gate.QualityGateTests` | Real temporary archives, restored excluded files, symlinks and malformed paths |
| Findings must not print credentials | Source and archive scan tests | Generated dummy tokens and redacted result assertions |
| Broken ranking or plan rules should be detected | `scripts/mutation_check.py` | Isolated deliberate faults with a passing baseline |

Fixtures are fictional and temporary. A high passing count does not establish hiring accuracy, complete security or exhaustive coverage. `scripts/static_checks.py` checks mutable defaults, bare exception handlers, direct `eval`/`exec` and wildcard imports; it is focused AST checking, not a complete style or type checker.

## Evidence and test-first changes

For consequential behavior changes, retain the actual initial failure, implementation change and successful rerun. Do not reconstruct an earlier failure from the finished code. Re-running the current code should pass; historical red output describes its recorded earlier state.

Existing unedited publication-check examples are retained in [initial test failure](evidence/tdd_red.txt), [successful rerun](evidence/tdd_green.txt), [path-validation failure](evidence/tdd_doctest_red.txt) and [path-validation rerun](evidence/tdd_doctest_green.txt). Their archive names, commands and counts belong to those past revisions. New release evidence must state the new revision and actual counts separately.

## Mutation checks

The mutation script copies selected modules, tests and fictional fixtures into temporary directories without `.env` or real databases. It runs an unchanged baseline, then gives each deliberate fault a separate copy and the relevant test class. Original source hashes are checked after the experiment.

The current selected faults reverse ranking order, replace skill intersection with union, remove the experience penalty, allow an excessive plan limit, and accept a boolean limit as an integer. Only relevant assertion failures count as detection. Import errors, timeouts, unmatched changes and unrelated failures are inconclusive and fail the check. A result of five detected faults covers that selected set, not every possible mutation or the whole project's correctness.

## CI and delivery

[The workflow](../.github/workflows/tests.yml) runs on pushes, pull requests and manual requests. It tests Python 3.8 on Ubuntu 24.04, Python 3.11/3.12/3.13 on the current Ubuntu runner, and Python 3.11 on the current macOS runner. Each environment runs the same full gate with mutations; counts from different environments must not be added as different tests.

After all test jobs succeed, the delivery job builds `jobcompass.zip`, verifies that exact archive and uploads it with the report as `jobcompass-source-<commit>`. Artifacts have a 14-day retention policy. This distributes reviewed source; it does not automatically deploy or restart the public service. Pipeline configuration alone is not evidence of success: link the actual run for the exact commit.

Actions use read-only repository permissions and disable persisted checkout credentials. The workflow currently uses major tags from the official [checkout](https://github.com/actions/checkout), [setup-python](https://github.com/actions/setup-python) and [artifact upload](https://github.com/actions/upload-artifact) repositories. These are not immutable commit pins; review changes deliberately when updating dependencies and workflows.

## Review and debugging

Use the [pull request template](../.github/pull_request_template.md) to explain the concrete change, its evidence and unresolved limits. Review affected behavior and data assumptions before style. Include file/line references for actionable findings and rerun relevant checks after fixes. Record accepted implementation tradeoffs in [the technical debt register](TECHNICAL_DEBT.md).

To investigate a failing test, reproduce it in an isolated database or temporary mutation copy. Stop at the affected calculation, inspect input types and values, and compare the assertion with the documented requirement. Profiling should record corpus size and environment, and must not modify a production research source. Automated test execution does not establish that an independent reviewer performed a walkthrough.

## Limits

The credential scanner recognizes a bounded set of provider/GitHub token and private-key patterns. It is not a universal secret or personal-data detector. Excluded local files are not inspected. Retained Office-XML inspection helpers support defensive validation of legacy document content, but document binaries are not accepted in current source releases. Embedded images and compressed benchmark contents are not searched for arbitrary personal information.

Offline tests cannot establish external provider availability, browser layout, all natural-language interpretations, future certificate renewal or production load capacity. Keep real network checks, browser observations, deployment evidence and remaining limitations separate from deterministic CI results.
