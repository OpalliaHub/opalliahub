# Bounded cache for repeated vacancy ranking

The state endpoint repeatedly reads the same resume and job corpus while the browser refreshes task progress. Previously, every refresh rebuilt the TF-IDF corpus and every job's score. `RankedJobsCache` reuses the last ranking when the complete input has not changed. The scoring formula and returned ranking remain identical to `matching.rank_jobs`.

## Integration

Create one cache per application instance, then replace its repeated rank call:

```python
from jobcompass.ranking_cache import RankedJobsCache

ranking_cache = RankedJobsCache()
jobs = ranking_cache.rank(resume, profile, jobs, preferences)
print(ranking_cache.cache_info())
# CacheInfo(hits=0, misses=1, maxsize=1, currsize=1) after the first successful call
```

`rank(resume, profile, jobs, preferences=None)` returns the usual ranked list. `cache_info()` reports counters without exposing the key or resume content. `clear()` releases the entry and resets counters. The cache is process-local: an application restart starts empty. If ranking rules are changed dynamically in a running process, call `clear()`; deploying new source normally restarts the application.

## Correctness and design

The cache hashes canonical JSON containing the **entire** resume, profile, ordered job list and preferences. It sorts dictionary keys, retains list order, normalizes absent preferences to `{}`, and rejects non-finite numbers or non-JSON data. Dictionary keys must be strings. Restricting values to JSON types avoids collisions between Python representations that JSON would otherwise coerce, such as numeric versus string dictionary keys or tuples versus lists.

A changed job description, skill list, title, location, experience requirement, job ID, inserted/deleted record, resume, or preference invalidates the result. Status, notes and other passthrough fields also invalidate it. This conservative design ensures the returned application information stays current without a separate metadata merge. It can recompute more often than a cache that separates scores from display metadata, but has fewer stale-data paths.

The input is deep-copied before hashing and ranking. The retained result is a separate deep copy. Both cache hits and misses return objects independent of the stored entry and caller inputs, including nested skill lists, score explanations and metadata. Callers must still avoid modifying the input **while** the copy is being made; no cache can make an external mutable collection atomic without the caller's cooperation.

A lock covers lookup, scoring and cache publication. Concurrent identical calls compute once, and all callers receive separate results. Changed requests serialize through the same lock. The old entry is replaced only after ranking and copying succeed; a failed request cannot poison an existing good entry.

Only one digest and one ranked result are retained, never an unbounded history of resumes or corpora. The entry's memory use still scales with the size of the corpus, and requests temporarily allocate input/output copies. Warm calls still serialize, hash and copy the data; this is not constant-time memoization. No fingerprint, input or result is written to disk by the cache.

## Measured local performance

On 18 November 2026, a deterministic synthetic fixture containing 1,200 jobs and 1,998,720 description characters was measured using Python 3.8.10 on an arm64 macOS machine. Five role families share realistic analytical/programming vocabulary; all records are explicitly synthetic. Each result was compared for exact equality with the original ranker.

| Path | Runs | Median | Minimum–maximum |
| --- | ---: | ---: | ---: |
| Original uncached `rank_jobs` | 5 | 201.321 ms | 198.972–205.051 ms |
| Cold cache, cleared before each call | 5 | 255.026 ms | 250.980–257.352 ms |
| Warm cache, same inputs | 10 | 52.661 ms | 52.053–56.277 ms |

The measured warm call was 3.82 times faster than the original ranker and 4.84 times faster than a cold cache call. A cold call was slower than the original ranker because it also copied, serialized and hashed the input. The intended benefit is repeated unchanged state refreshes. These timings exclude HTTP, SQLite reads, rendering and other application work; they describe this fixture and machine, not general performance guarantees. Raw results are retained in [ranking-cache-benchmark.json](evidence/ranking-cache-benchmark.json).

To reproduce the workload from the repository directory, run the following using `.venv/bin/python`:

```python
import statistics
from time import perf_counter
from jobcompass.matching import rank_jobs
from jobcompass.ranking_cache import RankedJobsCache

resume = 'Python SQL Pandas data analysis, ETL dashboards, Git, Docker. Bachelor degree. 2 years experience.'
profile = {'skills': ['Python', 'SQL', 'Pandas', 'Git', 'Docker'],
           'experience_years': 2, 'education': '本科'}
preferences = {'location': 'Hong Kong', 'experience_years': 2}
roles = [('Data Analyst', ['Python', 'SQL', 'Pandas']),
         ('Backend Engineer', ['Python', 'SQL', 'Docker']),
         ('Research Assistant', ['Python', 'Statistics']),
         ('Business Analyst', ['Excel', 'SQL']),
         ('Machine Learning Engineer', ['Python', 'PyTorch', 'Machine Learning'])]
jobs = []
for i in range(1200):
    title, skills = roles[i % len(roles)]
    description = (title + '. ' + ' '.join(skills)
        + '. Bachelor degree. {} years experience. '.format(i % 6)
        + 'Build reliable data products, investigate business questions, maintain pipelines and present findings. '
        + 'Collaborate with engineering and product teams. Document processes and review analytical results. ') * 6
    jobs.append({'id': 'synthetic-{:04d}'.format(i), 'title': title,
                 'company': 'Synthetic Company {}'.format(i % 47),
                 'description': description, 'skills': skills[:],
                 'location': 'Hong Kong' if i % 3 else 'Singapore',
                 'source': 'synthetic benchmark', 'is_demo': True, 'status': '', 'note': ''})
args = resume, profile, jobs, preferences
cache = RankedJobsCache()
expected = rank_jobs(*args)

def measure(function, repeats, reset=None):
    durations = []
    for _ in range(repeats):
        if reset:
            reset()
        start = perf_counter()
        result = function(*args)
        durations.append((perf_counter() - start) * 1000)
        assert result == expected
    return statistics.median(durations), min(durations), max(durations)

print('Uncached median/min/max ms:', measure(rank_jobs, 5))
print('Cold median/min/max ms:', measure(cache.rank, 5, cache.clear))
print('Warm median/min/max ms:', measure(cache.rank, 10))
```

## Tests and retained evidence

Run `.venv/bin/python -m unittest tests.test_ranking_cache -v`. The original fourteen tests cover output equivalence, canonical key ordering, preference normalization, 18 distinct invalidation cases, one-entry eviction, nested mutation isolation, failed recomputation, empty results, clearing, concurrent callers and invalid JSON representations. Tests assert computation counts and output correctness, not brittle wall-clock speed thresholds.

The tests were written and executed before implementation. The actual first failure is preserved in [cache-red.txt](evidence/cache-red.txt). The successful implementation demonstrates encapsulation, a bounded cache, hashing, locks for concurrent requests, independent copies instead of shared aliases, mock-based interaction tests, regression tests and a measured technical-debt improvement. This evidence does not establish an independent human review.
