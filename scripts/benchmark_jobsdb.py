"""Measure snapshot data quality and ranking runtime; not relevance accuracy."""
import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobcompass.benchmark import load_snapshot, SNAPSHOT
from jobcompass.config import ROOT
from jobcompass.matching import rank_jobs
from jobcompass.resume import parse_resume


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--snapshot', type=Path, default=SNAPSHOT)
    p.add_argument('--output', type=Path, default=ROOT/'docs/benchmark_jobsdb.json')
    p.add_argument('--repeats', type=int, default=3)
    args = p.parse_args()
    if not 1 <= args.repeats <= 10:
        p.error('--repeats must be between 1 and 10')
    jobs = load_snapshot(args.snapshot)
    resume = (ROOT/'data/demo_resume.txt').read_text(encoding='utf-8')
    profile = parse_resume(resume)
    timings = []
    for _ in range(args.repeats):
        start = time.perf_counter()
        ranked = rank_jobs(resume, profile, jobs, {'experience_years': 0})
        timings.append(round(time.perf_counter()-start, 4))
    report = {'python': platform.python_version(), 'platform': platform.system(),
        'snapshot_sha256': hashlib.sha256(args.snapshot.read_bytes()).hexdigest(),
        'resume': 'Bundled fictional demo_resume.txt', 'jobs': len(jobs),
        'unique_urls': len({j['url'] for j in jobs}),
        'missing_salary': sum(not j['salary'] for j in jobs),
        'missing_location': sum(not j['location'] for j in jobs),
        'no_dictionary_skills': sum(not j['skills'] for j in jobs),
        'expired_at_snapshot': sum(j['expired_at_snapshot'] for j in jobs),
        'top_locations': Counter(j['location'] for j in jobs).most_common(10),
        'runtime_seconds': timings, 'median_runtime_seconds': statistics.median(timings),
        'top_10': [{'id': j['id'], 'title': j['title'], 'score': j['score']} for j in ranked[:10]],
        'relevance_metrics': None,
        'limitations': 'No human resume-job relevance labels; precision, recall, NDCG and hiring probability are not measured. One snapshot, one fictional resume, no fairness or geographic representativeness claim. Timing depends on hardware; historical jobs may be closed.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
