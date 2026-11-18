"""Platform-owned JobsDB collection adapted from the user's jobsdb-pipeline.

Uses the supplied search/GraphQL flow, without importing or running that script.
One fixed user agent, bounded requests, no cookie/identity rotation or automatic
retry after access refusal. Only job fields are requested; no resume is sent.
"""
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode
from .benchmark import convert_record
from .sources import fetch
from .storage import now

SEARCH_URL = 'https://hk.jobsdb.com/api/jobsearch/v5/search'
DETAIL_URL = 'https://hk.jobsdb.com/graphql'
CLASSIFICATIONS = '6281,1209,6123'  # Same three categories as the supplied crawler.
QUERY = '''query jobDetails($jobId: ID!, $sessionId: String!, $correlationId: String!, $locale: Locale!) {
  jobDetails(id: $jobId, tracking: {channel: "WEB", jobDetailsViewedCorrelationId: $correlationId, sessionId: $sessionId}) {
    job { id title content(platform: WEB) isExpired
      expiresAt { dateTimeUtc } listedAt { dateTimeUtc }
      salary { label } advertiser { name(locale: $locale) }
      location { label(locale: $locale, type: LONG) }
    }
  }
}'''


def options(body):
    limit = body.get('limit', 50)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError('每次更新数量须为 1 至 200 的整数。')
    keyword = body.get('keyword', '')
    if not isinstance(keyword, str) or len(keyword.strip()) > 100:
        raise ValueError('搜索关键词最多 100 个字符。')
    return {'limit': limit, 'keyword': keyword.strip()}


def read_json(url, payload=None):
    try:
        value = json.loads(fetch(url,
            data=json.dumps(payload).encode('utf-8') if payload else None,
            headers={'Content-Type': 'application/json'} if payload else None,
            trusted_service=True, timeout=20))
    except (json.JSONDecodeError, UnicodeError):
        raise ValueError('JobsDB 返回的内容不是有效 JSON，可能需要人工访问网站。')
    if not isinstance(value, dict):
        raise ValueError('JobsDB 接口格式已变化。')
    if value.get('errors'):
        raise ValueError('JobsDB 详情接口返回错误；更新已停止，请稍后或到原站核实。')
    return value


def expiry_status(job, at=None):
    if job.get('availability') == 'expired':
        return 'expired'
    expires = job.get('expires_at')
    if expires:
        try:
            date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            if date.tzinfo and date <= (at or datetime.now(timezone.utc)):
                return 'expired'
        except (ValueError, TypeError, AttributeError):
            pass
    return job.get('availability') or 'unknown'


def collect(store, limit=50, keyword='', progress=None, cancel=None):
    settings = options({'limit': limit, 'keyword': keyword})
    cancel = cancel or threading.Event()
    progress = progress or (lambda **kwargs: None)
    stamp = now()
    store.reserve_jobsdb_attempt(stamp)
    session = str(uuid.uuid4())
    ids, seen = [], set()
    jobs, rejected, unavailable = [], 0, 0
    stopped_error = None
    progress(phase='正在读取 JobsDB 岗位列表', completed=0, total=limit, saved=0)
    try:
        # At most two list pages, followed by at most 200 detail requests.
        for page in range(1, 3):
            if cancel.is_set():
                break
            params = {'siteKey': 'HK-Main', 'sourcesystem': 'houston',
                      'classification': CLASSIFICATIONS, 'sortmode': 'ListedDate',
                      'pageSize': min(100, limit), 'page': page, 'locale': 'en-HK'}
            if settings['keyword']:
                params['keywords'] = settings['keyword']
            payload = read_json(SEARCH_URL + '?' + urlencode(params))
            rows = payload.get('data')
            if not isinstance(rows, list):
                raise ValueError('JobsDB 列表格式已变化，未写入无效数据。')
            before = len(ids)
            for row in rows:
                if not isinstance(row, dict):
                    continue
                metadata = row.get('solMetadata') or {}
                jid = str(row.get('id') or (metadata.get('jobId') if isinstance(metadata, dict) else '') or '')
                if re.fullmatch(r'\d+', jid) and jid not in seen:
                    seen.add(jid)
                    ids.append(jid)
                    if len(ids) == limit:
                        break
            if len(ids) >= limit or not rows or len(ids) == before:
                break
            if cancel.wait(1.5):
                break
        for index, jid in enumerate(ids):
            if cancel.wait(1.5):
                break
            progress(phase='正在读取岗位详情', completed=index, total=len(ids), saved=len(jobs))
            payload = read_json(DETAIL_URL, {'operationName': 'jobDetails', 'query': QUERY,
                'variables': {'jobId': jid, 'sessionId': session,
                              'correlationId': str(uuid.uuid4()), 'locale': 'en-HK'}})
            detail = payload.get('data')
            detail = detail.get('jobDetails') if isinstance(detail, dict) else None
            raw = detail.get('job') if isinstance(detail, dict) else None
            if raw is None:
                unavailable += 1
                continue
            try:
                job = convert_record(payload, 'JobsDB')
                if job['id'] != 'jobsdb-' + jid:
                    raise ValueError('JobsDB detail ID mismatch')
                expires = raw.get('expiresAt') or {}
                job['expires_at'] = str(expires.get('dateTimeUtc') or '')[:50] if isinstance(expires, dict) else ''
                job['availability'] = 'expired' if job['expired_at_snapshot'] else 'current'
                job['last_live_checked'] = stamp
                jobs.append(job)
            except (ValueError, KeyError, TypeError, AttributeError):
                rejected += 1
            progress(phase='正在读取岗位详情', completed=index + 1, total=len(ids), saved=len(jobs))
    except (ValueError, OSError) as exc:
        stopped_error = str(exc)
    # A partial update only changes fetched IDs; absence from a keyword/limited
    # search is never interpreted as a closed vacancy. Existing notes survive.
    count = store.upsert_jobs(jobs) if jobs else 0
    expired = sum(expiry_status(j) == 'expired' for j in jobs)
    status = 'cancelled' if cancel.is_set() else ('partial' if stopped_error and count else 'error' if stopped_error else 'success')
    result = {'source': 'JobsDB', 'count': count, 'expired': expired,
              'rejected': rejected, 'unavailable': unavailable,
              'requested': limit, 'found': len(ids), 'keyword': settings['keyword'],
              'status': status, 'checked_at': stamp}
    message = '已更新 {} 条 JobsDB 岗位（其中 {} 条已过期），跳过 {} 条无效及 {} 条不可用详情。'.format(count, expired, rejected, unavailable)
    if stopped_error:
        message += ' 本次已停止：' + stopped_error
    elif cancel.is_set():
        message += ' 已停止后续请求，保留已获取的有效结果。'
    elif not ids:
        message = '本次搜索未返回岗位，可更换关键词重试；原岗位库保持不变。'
    result['message'] = message
    store.set('jobsdb_last_run', result)
    store.log('JobsDB', status, count, message)
    progress(phase=message, completed=len(jobs) + rejected + unavailable, total=len(ids), saved=count)
    if stopped_error and not count:
        raise ValueError(message)
    return result
