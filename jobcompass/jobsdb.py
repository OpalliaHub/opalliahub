"""Platform-owned JobsDB collection adapted from the user's jobsdb-pipeline.

Uses the supplied V7 search/GraphQL flow, without running the external script.
One batch session, bounded requests, no identity rotation or browser challenge
automation. Only job fields are requested; no resume is sent.
"""
import re
import threading
import uuid
from datetime import datetime, timezone
from .benchmark import convert_record
from .jobsdb_http import JobsDBClient, JobsDBError, JobsDBCancelled, ENDPOINT
from .storage import now

SEARCH_URL = DETAIL_URL = ENDPOINT
CLASSIFICATIONS = '6281,1209,6123'  # Same three categories as the supplied crawler.
MAX_SEARCH_PAGES = 20
_COLLECTION_LOCK = threading.Lock()
SEARCH_QUERY = '''query JobSearchV7($params: JobSearchV7QueryInput!) {
  jobSearchV7(params: $params) {
    results { jobs { id } pagination { page pageSize resultCount } }
    context { searchToken filterNewSince }
  }
}'''
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


def read_json(url, payload=None, client=None):
    if client is not None:
        return client.read_json(url, payload)
    with JobsDBClient() as connection:
        return connection.read_json(url, payload)


def _search_body(session, page, size, token, since):
    params = {
        'sessionId': session,
        'responseConfig': {'results': ['jobs'], 'representations': ['uiV1'],
                           'page': page, 'pageSize': size},
        'searchContext': {'brand': 'jobsdb', 'channel': 'web', 'intent': 'SEARCH',
                          'source': 'FE_SERP', 'solVisitorId': session},
        'searchIntent': {'country': 'HK', 'locale': 'en-HK', 'sort': 'listedAt',
                         'distanceKms': 2,
                         'filter': {'categoryId': CLASSIFICATIONS.split(','), 'newSince': since}},
    }
    if token:
        params['searchToken'] = token
    return {'operationName': 'JobSearchV7', 'query': SEARCH_QUERY, 'variables': {'params': params}}


def _search_page(payload, page, previous_size):
    data = payload.get('data')
    search = data.get('jobSearchV7') if isinstance(data, dict) else None
    result = search.get('results') if isinstance(search, dict) else None
    pagination = result.get('pagination') if isinstance(result, dict) else None
    rows = result.get('jobs') if isinstance(result, dict) else None
    if not isinstance(pagination, dict) or not isinstance(rows, list):
        raise ValueError('JobsDB 搜索结构已变化，未将错误响应作为空列表保存。')
    number, size, total = (pagination.get(key) for key in ('page', 'pageSize', 'resultCount'))
    if (any(isinstance(n, bool) or not isinstance(n, int) for n in (number, size, total))
            or number != page or not 1 <= size <= 100 or total < 0
            or (page > 1 and size != previous_size) or len(rows) > size
            or (not rows and total > (page - 1) * size) or (rows and total == 0)):
        raise ValueError('JobsDB 分页响应无效或发生变化，已停止以免遗漏岗位。')
    ids = []
    for row in rows:
        jid = row.get('id') if isinstance(row, dict) else None
        if (isinstance(jid, bool) or not isinstance(jid, (str, int))
                or not re.fullmatch(r'[0-9]{1,30}', str(jid))):
            raise ValueError('JobsDB 列表缺少有效岗位编号，已停止本次更新。')
        ids.append(str(jid))
    context = search.get('context')
    return ids, size, total, context


def _next_context(context):
    token = context.get('searchToken') if isinstance(context, dict) else None
    since = context.get('filterNewSince') if isinstance(context, dict) else None
    if (context is not None and not isinstance(context, dict)
            or token is not None and (not isinstance(token, str) or len(token) > 8192)
            or since is not None and (isinstance(since, bool) or not isinstance(since, int) or since < 0)):
        raise ValueError('JobsDB 翻页上下文无效，已停止以免重复或遗漏岗位。')
    return token, since


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
    # Public visitors share the provider quota. A single process is also the
    # supported production deployment model; the DB attempt cooldown persists.
    if not _COLLECTION_LOCK.acquire(blocking=False):
        raise ValueError('已有 JobsDB 更新正在进行，请稍后再试。')
    try:
        return _collect(store, settings, progress, cancel)
    finally:
        _COLLECTION_LOCK.release()


def _collect(store, settings, progress, cancel):
    limit, keyword = settings['limit'], settings['keyword']
    stamp = now()
    store.reserve_jobsdb_attempt(stamp)
    ids, seen = [], set()
    jobs, rejected, unavailable = [], 0, 0
    filtered_out, checked, pages, search_total = 0, 0, 0, None
    stopped_error = None
    stop_code = None
    progress_state = {'completed': 0, 'total': limit, 'saved': 0}

    def report(**changes):
        progress_state.update(changes)
        progress(**progress_state)

    report(phase='正在读取 JobsDB 最新岗位列表')
    client = JobsDBClient(cancel=cancel, progress=report)
    session = client.session_id
    try:
        size, token, since = min(100, limit), None, None
        for page in range(1, MAX_SEARCH_PAGES + 1):
            if cancel.is_set():
                break
            report(phase='正在读取 JobsDB 搜索第 {} 页'.format(page))
            payload = read_json(SEARCH_URL, _search_body(session, page, size, token, since), client=client)
            rows, size, search_total, context = _search_page(payload, page, size)
            pages += 1
            before = len(ids)
            for jid in rows:
                if jid not in seen:
                    seen.add(jid)
                    ids.append(jid)
                    if len(ids) == limit:
                        break
            if rows and len(ids) == before:
                raise ValueError('JobsDB 搜索重复返回相同岗位，已停止翻页。')
            if len(ids) >= limit or page * size >= search_total:
                break
            if page == MAX_SEARCH_PAGES:
                stopped_error = '已达到本次 20 页读取上限，仅保留已取得的岗位。'
                stop_code = 'page_limit'
            else:
                token, since = _next_context(context)
        for index, jid in enumerate(ids):
            if cancel.is_set():
                break
            report(phase='正在读取岗位详情', completed=index, total=len(ids), saved=len(jobs))
            payload = read_json(DETAIL_URL, {'operationName': 'jobDetails', 'query': QUERY,
                'variables': {'jobId': jid, 'sessionId': session,
                              'correlationId': str(uuid.uuid4()), 'locale': 'en-HK'}}, client=client)
            detail = payload.get('data')
            if not isinstance(detail, dict) or 'jobDetails' not in detail:
                raise ValueError('JobsDB 详情响应结构已变化，已停止本次更新。')
            detail = detail['jobDetails']
            if detail is not None and (not isinstance(detail, dict) or 'job' not in detail):
                raise ValueError('JobsDB 详情响应结构已变化，已停止本次更新。')
            raw = detail.get('job') if detail is not None else None
            checked += 1
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
                # V7 keyword input is not documented by the supplied crawler.
                # Apply an explicit, bounded local substring filter, not an
                # invented server parameter or silently ignored user preference.
                text = ' '.join(job.get(k, '') for k in ('title', 'company', 'description'))
                if keyword and keyword.casefold() not in text.casefold():
                    filtered_out += 1
                else:
                    jobs.append(job)
            except (ValueError, KeyError, TypeError, AttributeError):
                rejected += 1
            report(phase='正在读取岗位详情', completed=index + 1, total=len(ids), saved=len(jobs))
    except JobsDBCancelled:
        cancel.set()
    except (ValueError, OSError) as exc:
        stopped_error = str(exc)
        stop_code = exc.code if isinstance(exc, JobsDBError) else 'invalid_response'
        if isinstance(exc, JobsDBError) and exc.retry_after is not None:
            store.defer_jobsdb_attempt(exc.retry_after)
    finally:
        client.close()
    # A partial update only changes fetched IDs; absence from a keyword/limited
    # search is never interpreted as a closed vacancy. Existing notes survive.
    count = store.upsert_jobs(jobs) if jobs else 0
    expired = sum(expiry_status(j) == 'expired' for j in jobs)
    status = 'cancelled' if cancel.is_set() else ('partial' if stopped_error and count else 'error' if stopped_error else 'success')
    result = {'source': 'JobsDB', 'count': count, 'expired': expired,
              'rejected': rejected, 'unavailable': unavailable,
              'requested': limit, 'found': len(ids), 'keyword': settings['keyword'],
              'status': status, 'checked_at': stamp, 'search_api': 'JobSearchV7',
              'pages': pages, 'search_total': search_total, 'checked': checked,
              'filtered_out': filtered_out, 'keyword_scope': 'batch_text',
              'stop_code': stop_code}
    message = '已更新 {} 条 JobsDB 岗位（其中 {} 条已过期），跳过 {} 条无效及 {} 条不可用详情。'.format(count, expired, rejected, unavailable)
    if stopped_error:
        message += ' 本次已停止：' + stopped_error
    elif cancel.is_set():
        message += ' 已停止后续请求，保留已获取的有效结果。'
    elif not ids:
        message = '本次搜索未返回岗位，原岗位库保持不变。'
    if keyword:
        message += ' 关键词仅筛选本批最新岗位的标题、公司及正文，{} 条未命中；不是全站搜索。'.format(filtered_out)
    result['message'] = message
    store.set('jobsdb_last_run', result)
    store.log('JobsDB', status, count, message)
    report(phase=message, completed=checked, total=len(ids), saved=count)
    if stopped_error and not count:
        raise ValueError(message)
    return result
