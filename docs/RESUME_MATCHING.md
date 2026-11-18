# Evidence-backed resume recommendations

The resume workspace extracts inspectable strengths from the visitor's saved resume and ranks the current job snapshot. This extension uses deterministic Python rules and the existing matcher. It does not train a model, call DeepSeek, send the resume to a provider, or claim to predict hiring outcomes. The research conversation and the older general job search remain separate features.

## Visitor flow and API

Save a resume and optional location/work-experience preferences, then request personalized recommendations. The server runs one background task against captured inputs. It rejects a completed result if the resume or preferences changed while the task was running; public tasks and results belong to the requesting visitor's workspace. These request/session safeguards are implemented by the server, not by this pure calculation module.

`jobcompass.recommendations` exports:

```python
analyze_strengths(text) -> profile
validate_options(options=None) -> normalized_options
build_recommendations(resume, jobs, preferences=None, options=None) -> result
```

The module accepts a resume of 30–40,000 characters, a list of job dictionaries and preferences containing only `location` and `experience_years`. Experience is a finite value from 0 to 80 or `None`. It does not accept demographic scoring preferences.

| Option | Default | Validation |
| --- | --- | --- |
| `limit` | `10` | Integer from 1 to 30; booleans rejected |
| `target_role` | `""` | Text, at most 100 characters |
| `min_score` | `0` | Finite number from 0 to 100; booleans rejected |
| `strict_location` | `false` | Boolean; requires a nonempty stored location |
| `include_demo` | `false` | Boolean |

Unknown option names and invalid field types raise `ValueError`. The server calls `validate_options` before queueing work. The module does not mutate the resume, preferences, options or job inputs.

The result contains `profile`, `jobs`, `summary`, `method` and a SHA-256 `fingerprint` of the version and complete inputs. The fingerprint identifies the calculation snapshot; it is not anonymization or an authentication token. A change to an application note can change the fingerprint even though notes do not enter scoring.

## Evidence and strengths

The parser reuses the project's canonical skill aliases, splits the resume into local clauses, and records exact excerpts of at most 240 characters. A strength card has `id`, `title`, `skills`, `evidence` and `kind` (`skill`, `experience` or `project`). At most 12 cards are displayed, with at most three excerpts each. Matching evidence may still refer to later resume clauses; its `strength_ids` only references displayed cards.

Negated skills and plans to learn are not treated as present skills. For example, “No experience with Python, but used SQL to build reports” supports SQL and excludes Python. A skill with both a positive assertion and an explicit denial is conservatively excluded as `conflicting`. Excluded items are returned in `profile.excluded_skills` with `denied`, `aspirational` or `conflicting` status and original excerpts.

The heading “技能：Python、SQL、数据分析、项目管理” produces a declaration, not project evidence. Explicit actions such as “项目中使用 SQL 完成报表” can produce practical evidence. A compact authored occupational vocabulary also covers recruitment, payroll, customer service, sales, administration and other business work so that a nontechnical resume need not contain programming skills to obtain a relevant ranking.

Identity/contact lines with recognized labels are removed before analysis. The text similarity calculation receives only accepted canonical skills and allowlisted professional concepts, rather than the original resume, name, age, gender, nationality or contact text. Explicit education and work-experience statements remain available as professional attributes. Age and birth dates are never converted into years of experience.

This is a limited rule system. An excerpt is evidence that the resume says something, not verification of the applicant's proficiency or outcome. Complicated negation, uncommon wording, skills outside the dictionary and long mixed clauses can be misclassified. The UI exposes excerpts and questions so the visitor can inspect and clarify them. Missing evidence does not establish missing ability.

## Ranking method

Version `resume-evidence-1.0` uses fixed, authored component weights:

| Component | Base weight | Calculation |
| --- | ---: | --- |
| Baseline | 75% | Existing skill/text/experience/location/education matcher, applied once to a controlled professional projection |
| Action and project evidence | 20% | Weighted share of the job's extracted skill and occupational concepts supported by an action statement in the resume |
| Optional target title | 5% | Token F1 overlap between the entered target role and job title |

The controlled baseline retains the existing algorithm but does not pass raw personal text through TF-IDF. Its `baseline_score` therefore need not equal the score shown by the older raw-text general search. Text similarity also depends on the selected corpus. Scores from different snapshots are not a calibrated time series.

The practical component uses job-feature coverage; general skills such as English and Communication receive weight 0.2, other features weight 1. It is unknown when the resume has no affirmative action evidence or the job has no extractable features. When practical evidence exists but does not intersect a job's features, this component is zero. An omitted target title contributes no component. Available components are renormalized to sum to 100%; without a target and with practical evidence, the effective shares are approximately 78.95% and 21.05%.

Each returned job includes `score`, `baseline_score`, `breakdown`, `baseline_breakdown`, `reasons`, `evidence_matches`, `matched_skills`, `missing_skills`, `warnings`, `effective_coverage`, `unknown_fields` and `weak_signal`, in addition to the original job fields. Component contributions reconcile to the displayed score within rounding. Coverage reports available calculation inputs, not confidence or statistical accuracy. A job can have high coverage and a low match.

Job skill extraction records textual mentions, which may be optional, contextual or negated in the advertisement. The UI accordingly says “岗位提及” and “简历尚未体现”; it does not reinterpret every mention as a mandatory hiring requirement. A soft location mismatch remains in the candidates and gets an explicit warning. Application notes and workflow statuses are preserved as original data but do not influence scores, strengths or matching evidence.

There is no hidden suitability cutoff. `min_score=0` can return weak candidates. `weak_signal=true` means there is no shared substantive skill/occupational concept beyond general English/Communication. Raising `min_score` filters explicitly and can return no candidates with an explanation. Neither score 100 nor a top rank is a hiring probability or an assertion that the person meets every requirement.

## Eligibility, duplicates and freshness

Known expired, closed, inactive, unavailable and removed records are excluded. Timestamp-aware expiry uses the existing expiry helper. For otherwise ambiguous ISO values, a past timestamp without a timezone is interpreted as UTC; a date-only value expires at the end of its UTC day. A future value without a timezone, or an invalid expiry value, becomes `unknown` with a warning rather than confirming that a job is active. Unknown status remains inspectable. Recommendation generation does not contact the original website to verify every listing.

Canonical URL identity normalizes HTTP/HTTPS, hostname case, default ports, fragments, trailing slashes and known tracking parameters; other query parameters remain part of identity. Equal canonical URLs are deduplicated across sources. Without a URL, an explicit job ID identifies the record; only records also lacking an ID use source/title/company/location fallback identity. Duplicate explicit IDs are also suppressed. The first record wins, matching the store's newest-first snapshot. Deduplication precedes expiry filtering so a newer expired copy cannot resurrect through an older active duplicate.

Synthetic jobs are excluded when the input includes observed jobs, unless `include_demo=true`. An all-demo input automatically falls back to clearly labeled demo results. `summary.data_mode` is `empty`, `observed`, `demo` or `mixed`, and `demo_fallback` separately signals that fallback. There is no demo fallback merely because all observed jobs were excluded. No synthetic listing is presented as an application opportunity.

`summary` reports input total, eligible and returned counts, each exclusion-stage count (`excluded_demo`, `excluded_duplicates`, `excluded_expired`, `excluded_location`, `excluded_min_score`), the count remaining before the display limit, weak matches and an empty-result explanation. A duplicate excluded earlier is counted at that stage, not again as expired.

## Verification evidence

The feature tests use fictional resumes and jobs and run without network or paid model calls:

```sh
.venv/bin/python -m unittest tests.test_recommendations -v
```

The targeted run currently passes **26 tests**. They exercise negation/aspiration and conflicts, original local evidence, nominal skill lists, nontechnical profiles, invariance to labeled identity fields and application notes, real project preference, multiple skills, bounded deterministic scores, expiry and URL deduplication, demo labeling, location policy, weak-signal/minimum behavior, strict validation, nonmutation and a single baseline call per batch.

Actual TDD evidence is retained under `output/resume-upgrade/`: `recommendations-red.txt` (initial missing implementation), `recommendations-edge-red.txt` (deduplication boundary failures), `recommendations-boundaries-red.txt` (subsequent review cases), and `recommendations-final-green.txt` (26 passing tests), with `target-intent-red.txt` covering objective/target-role statements that must not become existing skills. These are targeted algorithm checks. HTTP isolation/capacity checks, browser verification, full-suite totals and performance measurements are recorded separately by the integrating release; this document does not claim human relevance labels, measured recommendation accuracy, a new GitHub publication or cloud deployment.

Full integration, browser and measured performance records are in [RESUME_VERIFICATION.md](RESUME_VERIFICATION.md). The UI says “行动与相关经历” for an action excerpt; this label does not assert paid employment.
