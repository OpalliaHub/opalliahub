"""Build a reproducible course submission with a strict allowlist."""
import argparse
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ALLOWED_FILES=['main.py','README.md','requirements.txt','.env.example','.gitignore','启动JobCompass.command']
ALLOWED_DIRS=['jobcompass','tests','scripts','docs','.github']
DEMO_FILES=['demo_jobs.json','demo_resume.txt','import_template.csv']

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--group',default='11');args=parser.parse_args()
    if not args.group.isalnum():parser.error('组号只接受字母或数字')
    files=[ROOT/name for name in ALLOWED_FILES]+[ROOT/'data'/name for name in DEMO_FILES]
    for folder in ALLOWED_DIRS:
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.zip') and not p.name.startswith('.'))
    output=ROOT/'dist';output.mkdir(exist_ok=True)
    destination=output/('group'+args.group+'_project.zip')
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(files)):
            if path.is_symlink():continue
            archive.write(path,str(Path('group'+args.group+'_project')/path.relative_to(ROOT)))
    print(destination)

if __name__=='__main__':main()
