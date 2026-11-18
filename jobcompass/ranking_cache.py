"""One-entry, process-local cache for repeated ranking of an unchanged corpus."""
import copy
import hashlib
import json
import threading
from collections import namedtuple

from .matching import rank_jobs


CacheInfo = namedtuple('CacheInfo', 'hits misses maxsize currsize')


def _fingerprint(snapshot):
    """Hash canonical JSON, rejecting ambiguous/non-JSON Python representations."""
    pending, visited = [snapshot], set()
    while pending:
        value = pending.pop()
        if type(value) in (dict, list):
            if id(value) in visited:
                continue  # json.dumps below rejects cycles, but allows shared values.
            visited.add(id(value))
            if isinstance(value, dict):
                if any(not isinstance(key, str) for key in value):
                    raise ValueError('排序数据的对象键必须是字符串。')
                pending.extend(value.values())
            else:
                pending.extend(value)
        elif value is not None and type(value) not in (str, bool, int, float):
            raise ValueError('排序数据必须只包含 JSON 支持的类型。')
    try:
        canonical = json.dumps(snapshot, sort_keys=True, ensure_ascii=False,
                               separators=(',', ':'), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise ValueError('排序数据必须是有效且无循环引用的 JSON，数值必须有限。') from None
    return hashlib.sha256(canonical.encode('utf-8')).digest()


class RankedJobsCache:
    """Cache the last full ranking result, with independent input/output snapshots.

    The key includes the complete resume, profile, job list and preferences.
    Status/note changes deliberately invalidate the entry too: passthrough fields
    must never become stale. A lock serializes cache lookup and computation, so
    concurrent identical requests do not each rebuild TF-IDF. Only one ranking
    result and its digest are retained; memory still scales with corpus size.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._key = None
        self._result = None
        self._hits = 0
        self._misses = 0

    def rank(self, resume, profile, jobs, preferences=None):
        if not isinstance(resume, str) or not isinstance(profile, dict) or not isinstance(jobs, list):
            raise ValueError('排序需要简历文本、画像对象和岗位列表。')
        if preferences is not None and not isinstance(preferences, dict):
            raise ValueError('排序偏好必须是对象。')
        snapshot = copy.deepcopy([resume, profile, jobs, {} if preferences is None else preferences])
        key = _fingerprint(snapshot)
        with self._lock:
            if key == self._key:
                self._hits += 1
                return copy.deepcopy(self._result)
            self._misses += 1
            result = rank_jobs(*snapshot)
            # Publish only after a successful rank and copy. Failed attempts leave
            # the previous good entry intact. The returned miss result is already
            # detached from caller inputs; the retained copy is independent of it.
            retained = copy.deepcopy(result)
            self._key, self._result = key, retained
            return result

    def cache_info(self):
        """Expose counters, never fingerprints or resume content, for diagnostics."""
        with self._lock:
            return CacheInfo(self._hits, self._misses, 1, int(self._key is not None))

    def clear(self):
        """Release the retained ranking and reset diagnostics."""
        with self._lock:
            self._key, self._result = None, None
            self._hits, self._misses = 0, 0
