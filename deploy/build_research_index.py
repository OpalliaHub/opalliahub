"""Operator-only offline index build; public visitors cannot choose server paths."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobcompass.storage import Store
from jobcompass.research import Research


def main():
    source = os.environ.get('JOBCOMPASS_RESEARCH_DB', '')
    database = os.environ.get('JOBCOMPASS_DB', '')
    if not source or not database:
        raise ValueError('Set JOBCOMPASS_RESEARCH_DB and JOBCOMPASS_DB before building the shared index.')
    store = Store(Path(database))
    research = Research(store)
    research.connect(source)
    result = research.build()
    print(result['message'])


if __name__ == '__main__':
    main()
