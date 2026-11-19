"""Build an allowlisted JobCompass source release without private/local artifacts."""
import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ''):
    sys.path.insert(0, str(ROOT))
from scripts.quality_gate import source_files

DEMO_FILES = ('demo_jobs.json', 'demo_resume.txt', 'import_template.csv')
BENCHMARK_FILES = ('jobsdb_20260928.json.gz', 'jobsdb_20260928.manifest.json')


def _fixture(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        return None
    if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
        return None
    return path


def build_package(root=ROOT):
    """Return the archive path; local excluded files are neither read nor copied."""
    root = Path(root)
    files = set(source_files(root))
    names = ['data/' + name for name in DEMO_FILES]
    names.extend('data/benchmark/' + name for name in BENCHMARK_FILES)
    for name in names:
        path = _fixture(root, name)
        if path is not None:
            files.add(path)
    output = root / 'dist'
    if output.is_symlink():
        raise ValueError('Release output directory must not be a symbolic link.')
    output.mkdir(exist_ok=True)
    destination = output / 'jobcompass.zip'
    if destination.is_symlink():
        raise ValueError('Release archive must not be a symbolic link.')
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, str(Path('jobcompass') / path.relative_to(root)))
    return destination


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(build_package())


if __name__ == '__main__':
    main()
