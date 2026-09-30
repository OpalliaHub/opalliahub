"""Convert a user-provided JobsDB ZIP to a normalized, reproducible snapshot."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobcompass.benchmark import convert_archive, write_snapshot, SNAPSHOT, SOURCE
from jobcompass.config import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=SNAPSHOT)
    parser.add_argument('--source', default=SOURCE, help='Include the actual snapshot date')
    args = parser.parse_args()
    jobs, counts, reasons = convert_archive(args.archive, args.source)
    digest = write_snapshot(jobs, args.output)
    manifest = {'source_archive': args.archive.name,
                'archive_sha256': hashlib.sha256(args.archive.read_bytes()).hexdigest(),
                'normalized_sha256': digest, 'source': args.source,
                'counts': counts, 'rejection_reasons': reasons,
                'labels_available': False,
                'transformations': ['HTML converted to plain text', 'tracking URL parameters removed',
                    'only job fields retained; no phoneNumber/contactMatches/tracking/questionnaire objects',
                    'email addresses and Hong Kong phone-like numbers masked (heuristic, can overmask)',
                    'deduplicated by numeric JobsDB ID', 'no inferred relevance labels'],
                'scope': 'One user-provided research snapshot. No live JobsDB API request.'}
    args.output.with_suffix('').with_suffix('.manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
