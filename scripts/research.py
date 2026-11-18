"""Build the local index or replay an exported plan without the browser."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobcompass.config import DB_PATH
from jobcompass.storage import Store
from jobcompass.research import Research

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',help='Existing JobsDB audit SQLite path, opened read-only')
    p.add_argument('--build',action='store_true')
    p.add_argument('--plan',type=Path,help='JSON plan or previously exported result JSON')
    args=p.parse_args();research=Research(Store(DB_PATH))
    if args.source:print(research.connect(args.source)['message'])
    if args.build:print(research.build(lambda **v:print(v['completed'], '/',v['total'],flush=True))['message'])
    if args.plan:
        raw=json.loads(args.plan.read_text(encoding='utf-8'));result=research.run(raw.get('plan',raw));print(json.dumps(result,ensure_ascii=False,indent=2))
    if not args.build and not args.plan:print(json.dumps(research.status(),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
