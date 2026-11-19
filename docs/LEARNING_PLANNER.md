# Skill-gap learning planner

The “技能成长” feature turns the current vacancy sample and the saved resume profile into an explainable study plan. It answers two distinct questions: which skills occur frequently in the selected sample, and which study foundations could help a person learn a missing skill. The frequency is computed from jobs; the study dependencies are authored learning suggestions.

## Use and API

The platform exposes `POST /api/learning` with a JSON body such as:

```json
{"target": "data analyst", "limit": 10}
```

The server uses the saved resume profile and stored jobs. An empty target includes all eligible titles. Matching is a case-insensitive literal substring of the title, not a regular expression or a search of descriptions. The target accepts at most 100 characters; `limit` accepts integers from 1 to 20. Invalid input raises `ValueError`, which the server reports as a validation error.

The equivalent Python entry point is:

```python
from jobcompass.learning import build_learning_plan

plan = build_learning_plan(jobs, {"skills": ["Python", "SQL"]},
                           target="data analyst", limit=10)
```

The response is JSON ready and contains:

| Field | Meaning |
| --- | --- |
| `summary` | Chinese explanation of sample size, skill count and gaps |
| `skills` | Top skills, sorted by descending frequency and then name |
| `skills[].skill`, `count`, `share_pct` | Canonical skill label, distinct job count, percentage of analyzed jobs |
| `skills[].already_known` | Whether that skill appears in the resume profile; not a proficiency assessment |
| `skills[].prerequisites` | Transitive authored study suggestions, foundation first |
| `skills[].learning_order` | Suggested foundations plus that skill, excluding skills already listed in the resume; empty for an already-known target |
| `skills[].example_jobs` | At most three `{id, title, company}` evidence records |
| `learning_order` | A deduplicated, prerequisite-first plan for the displayed missing skills |
| `metrics` | Counts, filters, sample type, exclusions and explicit limitations |

The most useful metrics for the UI are `input_jobs`, `analyzed_jobs`, `excluded_demo_jobs`, `excluded_expired_jobs`, `duplicate_jobs`, `jobs_with_skills`, `distinct_skills`, `returned_skills`, `missing_skills`, and `learning_steps`. `missing_skills` is limited to displayed rows; it is not a count of all missing skills in the corpus. `data_mode` is `observed`, `demo`, or `empty`; `demo_fallback` makes demonstration data unmistakable. `target`, `limit`, `prerequisite_source`, and `limitations` retain interpretation context.

## Counting and data boundaries

1. Validate and copy the relevant input into immutable sample records. Inputs are not mutated, no database rows are changed, and no code or network requests are executed.
2. Exclude demonstration jobs whenever any non-demonstration record exists. Use demonstration data only when the entire input is demonstration data, and label the result accordingly. An unmatched title or expired real vacancy never triggers a silent demo fallback.
3. Deduplicate by job ID, keeping the first input record. The repository supplies the most recently collected records first. For data without IDs, derive a stable identity from source and URL, or source/title/company/location. These fallback identities cannot reliably detect reposts or different advertisements with identical metadata.
4. Exclude deduplicated records whose `availability` is `expired`. The server refreshes this flag with the existing `expiry_status` helper, including `expires_at`, before invoking the planner. Direct Python callers must supply the normalized availability themselves. Unknown availability remains in the sample; this is not a live vacancy check.
5. Filter by title, then count each canonical skill once per job. Existing aliases from `resume.SKILLS` are reused. For example, `mysql` and `postgresql` count under `SQL`; this taxonomy deliberately groups related technologies and does not certify interchangeability.
6. Prefer supplied structured skills. Only when the list is empty, extract known keywords from title and description using the existing resume parser. Unknown structured skills are retained without inventing prerequisite relationships.
7. Divide skill counts by **all** analyzed jobs, including those without recognized skills. Different skills can co-occur, so percentages do not sum to 100%. Keep jobs without skills visible through `jobs_with_skills` rather than silently changing the denominator.
8. Select the top `limit` skills, then construct study suggestions for missing displayed skills. A lower-frequency gap beyond the limit will not appear until the limit or title filter changes.

This sample can be biased by source coverage, collection date, search choices, parsing failures and duplicates that have different IDs. It does not estimate overall labor-market demand. Prerequisite edges such as `Python → Pandas` or `Machine Learning → PyTorch` are editable learning suggestions, not employer requirements. A skill absent from a resume may still be known, and a skill present in a resume is not proof of proficiency.

## Implementation design

| Design element | Implementation |
| --- | --- |
| Functions and default arguments | `build_learning_plan(jobs, profile, target='', limit=10)` is the stable public API |
| Classes and encapsulation | `LearningPlanner` separates orchestration from `PrerequisiteGraph`; frozen dataclasses represent evidence and skill rows |
| Nested functions and scope | `visit` closes over traversal state within `_ordered` |
| Recursion | Depth-first traversal visits a skill's prerequisite graph before the skill |
| Base and recursive cases | An unknown/root skill has no outgoing prerequisites; other nodes recursively visit their foundations |
| Decorators and caching | `@lru_cache(maxsize=256)` memoizes prerequisite tuples on the reused planner graph |
| Lists as stacks | `active.append`/`active.pop` track the current recursion path and give a useful cycle error |
| Sets | Active/completed sets detect cycles, avoid revisiting shared foundations and remove repeated study steps |
| Dictionaries, tuples and aliasing | A copied `MappingProxyType` of immutable tuples prevents callers from changing the graph through their original input; cached results are tuples |
| Sorting and counters | `Counter` counts occurrences and explicit tie-breaking makes output deterministic |
| Exceptions and validation | Invalid profiles, jobs, limits, targets, and cyclic graphs fail with a useful `ValueError` |
| Test-first development | Saved red output precedes implementation and the regression suite covers observable behavior |

A dependency walk costs `O(V + E)` for reachable nodes and edges, with `O(V)` traversal storage. A cache hit avoids repeating that walk. Corpus processing additionally reads the supplied job text when skill extraction is necessary; it is linear in that text size plus skill occurrences. Sorting costs `O(S log S)` for `S` distinct skills. This is an in-memory current-corpus feature; the research pipeline remains the appropriate place to preprocess large historical datasets.

## Tests and usage example

Run from the project directory:

```sh
.venv/bin/python -m unittest tests.test_learning -v
```

The original 20-test suite covers alias normalization, distinct-job denominators, sample exclusions, expired-record precedence, demo labeling, literal title filtering, extraction fallback, recursive ordering, known skills, limits and ties, example bounds, unknown skills, JSON serialization, input immutability, validation, immutable cache results, shared prerequisites, custom graphs and cycle detection.

[learning-red.txt](evidence/learning-red.txt) records two actual pre-fix runs: the first run failed because the module had not yet been implemented; the second exposed missing expiry behavior and the stricter input boundaries before those changes were made. These logs demonstrate the automated sequence performed during development. They do not establish an independent human review.

To inspect the feature, save a resume with Python and SQL, select a title present in the current data, inspect one skill's job examples, then compare its authored foundations with the employer evidence. A PyTorch example demonstrates multiple recursive levels; shared Python prerequisites appear only once. A custom `PrerequisiteGraph({'A': ['B'], 'B': ['A']})` raises a cycle error instead of recursing forever. The graph tests demonstrate cache reuse without relying on unreliable wall-clock timing.
