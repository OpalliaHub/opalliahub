"""Local JobsDB research snapshot conversion; never fetches restricted APIs."""
import gzip
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from .config import ROOT
from .sources import normalize, plain

SOURCE = 'JobsDB research snapshot 2026-09-28'
SNAPSHOT = ROOT / 'data' / 'benchmark' / 'jobsdb_20260928.json.gz'
MAX_BYTES = 128 * 1024 * 1024


def clean_text(value):
    text = plain(value)
    text = re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', '[email removed]', text)
    text = re.sub(r'(?<!\d)(?:\+?852[ -]?)?[2-9]\d{3}[ -]?\d{4}(?!\d)', '[phone-like number removed]', text)
    return text


def convert_record(payload, source=SOURCE):
    raw = payload['data']['jobDetails']['job']
    if not isinstance(raw, dict) or not re.fullmatch(r'\d+', str(raw.get('id', ''))):
        raise ValueError('Missing numeric JobsDB ID')
    job = normalize({
        'title': clean_text(raw.get('title')),
        'company': clean_text((raw.get('advertiser') or {}).get('name')),
        'description': clean_text(raw.get('content')),
        'location': clean_text((raw.get('location') or {}).get('label')),
        'salary': plain((raw.get('salary') or {}).get('label')) if isinstance(raw.get('salary'), dict) else plain(raw.get('salary')),
        'published_at': (raw.get('listedAt') or {}).get('dateTimeUtc', ''),
        'url': 'https://hk.jobsdb.com/job/' + str(raw['id']),
    }, source)
    job['id'] = 'jobsdb-' + str(raw['id'])
    job['expired_at_snapshot'] = raw.get('isExpired') is True
    return job


def convert_archive(path, source=SOURCE):
    """Read JSON members without extracting paths or following archive links."""
    jobs = {}
    counts = Counter()
    reasons = Counter()
    with zipfile.ZipFile(path) as archive:
        entries = [i for i in archive.infolist() if '/original_data/' in i.filename
                   and i.filename.endswith('.json') and not i.filename.startswith('__MACOSX/')
                   and not Path(i.filename).name.startswith('.')]
        if not entries or len(entries) > 100000:
            raise ValueError('Expected 1–100000 JobsDB original_data JSON records')
        if sum(i.file_size for i in entries) > 512 * 1024 * 1024:
            raise ValueError('Uncompressed JSON data exceeds 512 MiB')
        for info in sorted(entries, key=lambda i: i.filename):
            counts['input_records'] += 1
            if info.file_size > 1024 * 1024:
                counts['rejected_records'] += 1
                reasons['record_over_1_mib'] += 1
                continue
            try:
                job = convert_record(json.loads(archive.read(info)), source)
                if job['id'] in jobs:
                    counts['duplicate_ids'] += 1
                jobs[job['id']] = job
            except (ValueError, KeyError, TypeError, AttributeError):
                counts['rejected_records'] += 1
                reasons['invalid_schema_or_required_fields'] += 1
    result = sorted(jobs.values(), key=lambda j: j['id'])
    counts['accepted_unique_records'] = len(result)
    return result, dict(counts), dict(reasons)


def write_snapshot(jobs, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(jobs, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    with path.open('wb') as stream:
        with gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as compressed:
            compressed.write(body)
    return hashlib.sha256(body).hexdigest()


def load_snapshot(path=SNAPSHOT):
    try:
        with gzip.open(path, 'rb') as stream:
            body = stream.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('Snapshot exceeds 128 MiB')
        jobs = json.loads(body)
        if not isinstance(jobs, list) or not jobs or len(jobs) > 100000:
            raise ValueError('Snapshot must contain 1–100000 jobs')
        validated = []
        seen = set()
        for job in jobs:
            jid = job.get('id', '')
            if not isinstance(jid, str) or not jid or jid in seen:
                raise ValueError('Missing or duplicate snapshot ID')
            seen.add(jid)
            clean = normalize(job, job.get('source', SOURCE))
            clean['id'] = jid
            clean['expired_at_snapshot'] = job.get('expired_at_snapshot') is True
            validated.append(clean)
        return validated
    except (OSError, EOFError, TypeError, AttributeError) as exc:
        raise ValueError('无法读取本地 benchmark 数据：' + str(exc))


def import_snapshot(store, path=SNAPSHOT):
    jobs = load_snapshot(path)
    # Historical/expired jobs remain in the benchmark, but are not offered in the app.
    active = [job for job in jobs if not job['expired_at_snapshot']]
    count = store.upsert_jobs(active)
    message = '已导入 {} 条研究快照岗位；快照时间不代表当前仍在招聘。'.format(count)
    store.log(SOURCE, 'success', count, message)
    return {'count': count, 'message': message}
