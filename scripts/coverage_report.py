"""Measure executed Python lines with stdlib trace (offline, optional slow check)."""
import argparse
import contextlib
import sys
import trace
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='output/coverage')
    args = parser.parse_args()
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT))
    tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.base_prefix, sys.prefix])

    def run():
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))
        return unittest.TextTestRunner(verbosity=1).run(suite)

    with (destination / 'tests.txt').open('w', encoding='utf-8') as stream:
        with contextlib.redirect_stderr(stream):
            result = tracer.runfunc(run)
    # Restrict reporting to product modules; output/ is excluded from source ZIPs.
    results = tracer.results()
    results.counts = {key:value for key,value in results.counts.items()
                      if Path(key[0]).resolve().is_relative_to(ROOT / 'jobcompass')} if sys.version_info >= (3, 9) else {
                          key:value for key,value in results.counts.items()
                          if str(Path(key[0]).resolve()).startswith(str(ROOT / 'jobcompass') + '/')}
    with (destination / 'summary.txt').open('w', encoding='utf-8') as stream:
        with contextlib.redirect_stdout(stream):
            results.write_results(show_missing=True, summary=True, coverdir=str(destination))
    print((destination / 'summary.txt').resolve())
    print('Line execution only; this is not branch coverage or proof of correctness. '
          'Worker-thread execution is not counted by stdlib trace.runfunc.')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
