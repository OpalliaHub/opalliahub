"""Anonymous visitor isolation and bounded shared resources for public mode."""
import hashlib
import ipaddress
import math
import os
import re
import secrets
import json
import ssl
import shutil
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .storage import Store
from .sources import AGENT, parse_jsonld, validate_url

SHARED_SETTINGS = frozenset({'research_source', 'research_index', 'jobsdb_last_attempt'})
JOB_COLUMNS = ('id','source','title','company','location','salary','url','description','skills',
               'published_at','collected_at','is_demo','remote','expires_at','availability','last_live_checked')
COOKIE_NAME = 'jobcompass_session'


class SessionStore:
    """Read shared jobs/configuration; keep every visitor mutation in a private DB."""
    def __init__(self, base_store, private_store):
        self.base = base_store
        self.private = private_store
        self.path = private_store.path

    def connection(self):
        return self.private.connection()

    def get(self, key, default=None):
        if key in SHARED_SETTINGS:
            return self.base.get(key, default)
        if key == 'initialized':
            return True
        return self.private.get(key, default)

    def set(self, key, value):
        if key in SHARED_SETTINGS:
            raise ValueError('共享数据配置由服务器维护，访客不能修改。')
        self.private.set(key, value)

    def jobs(self):
        jobs = {job['id']: dict(job, status=None, note=None) for job in self.base.jobs()}
        jobs.update({job['id']: job for job in self.private.jobs()})
        return sorted(jobs.values(), key=lambda job: (job['collected_at'], job['id']), reverse=True)

    def _copy_shared_job(self, jid):
        with self.private.connection() as con:
            if con.execute('SELECT 1 FROM jobs WHERE id=?', (jid,)).fetchone():
                return True
        with self.base.connection() as con:
            row = con.execute('SELECT ' + ','.join(JOB_COLUMNS) + ' FROM jobs WHERE id=?', (jid,)).fetchone()
        if row is None:
            return False
        # Copy exactly the historical identifier, not Store.upsert_jobs' generated
        # identifier; application foreign keys and existing bookmarks depend on it.
        with self.private.connection() as con:
            con.execute('INSERT OR IGNORE INTO jobs (' + ','.join(JOB_COLUMNS) + ') VALUES (' +
                        ','.join('?' for _ in JOB_COLUMNS) + ')', tuple(row))
        return True

    def upsert_jobs(self, jobs):
        jobs = list(jobs)
        wanted = {job.get('url') for job in jobs if job.get('source', '').startswith('JobsDB') and job.get('url')}
        if wanted:
            with self.base.connection() as con:
                shared = [(row['id'], row['url']) for row in con.execute("SELECT id,url FROM jobs WHERE source LIKE 'JobsDB%'")]
            for jid, url in shared:
                if url in wanted:
                    self._copy_shared_job(jid)
        return self.private.upsert_jobs(jobs)

    def application(self, jid, status, note):
        if status not in ('收藏', '已投递', '面试中', '已录用', '已结束', '未收藏'):
            raise ValueError('未知的投递状态。')
        if not isinstance(jid, str) or not isinstance(note, str):
            raise ValueError('岗位编号和备注必须是文本。')
        if not self._copy_shared_job(jid):
            with self.private.connection() as con:
                if not con.execute('SELECT 1 FROM jobs WHERE id=?', (jid,)).fetchone():
                    raise ValueError('岗位不存在。')
        return self.private.application(jid, status, note)

    def reserve_jobsdb_attempt(self, stamp):
        return self.base.reserve_jobsdb_attempt(stamp)

    def application_history(self, action):
        return self.private.application_history(action)

    def history_status(self):
        return self.private.history_status()

    def log(self, source, status, count, message):
        return self.private.log(source, status, count, message)

    def logs(self):
        return self.private.logs()

    def clear_resume(self):
        return self.private.clear_resume()


@dataclass
class SessionContext:
    app: object
    store: SessionStore
    directory: Path
    last_seen: float
    active_requests: int = 0


@dataclass
class ResolvedSession:
    app: object
    store: SessionStore
    directory: Path
    set_cookie: object


class SessionCapacityError(ValueError):
    status_code = 503


class SessionManager:
    """One in-memory registry; opaque cookies are bearer capabilities, not accounts.

    The application factory must reuse the server's bounded executor. The manager
    never creates an executor and never shuts down a shared executor on expiry.
    """
    def __init__(self, base_store, root, factory, ttl_seconds=3600, max_sessions=32,
                 secure=True, clock=time.monotonic, creation_limiter=None):
        if ttl_seconds <= 0 or max_sessions < 1:
            raise ValueError('Invalid anonymous session limits')
        self.base, self.root, self.factory = base_store, Path(root), factory
        self.ttl, self.max_sessions, self.secure, self.clock = ttl_seconds, max_sessions, secure, clock
        self.creation_limiter = creation_limiter
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        self._lock = threading.RLock()
        self._items = {}
        self._closed = False
        try:
            import fcntl
        except ImportError:
            raise ValueError('公开会话服务需要 Linux/macOS 文件锁；Windows 可继续使用本地模式。')
        self._registry_lock = (self.root / 'registry.lock').open('a+b')
        try:
            fcntl.flock(self._registry_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._registry_lock.close()
            raise ValueError('访客目录已被另一个进程使用；公开服务必须只运行一个 worker。')
        # Registry tokens intentionally do not survive a restart. Remove only
        # our strictly named old directories, never unrelated files or symlinks.
        for child in self.root.iterdir():
            if re.fullmatch(r'[a-f0-9]{64}', child.name) and child.is_dir() and not child.is_symlink():
                shutil.rmtree(str(child))

    def _token(self, header):
        if not isinstance(header, str) or len(header) > 8192:
            return None
        try:
            cookie = SimpleCookie()
            cookie.load(header)
            value = cookie[COOKIE_NAME].value if COOKIE_NAME in cookie else ''
            return value if re.fullmatch(r'[A-Za-z0-9_-]{43}', value) else None
        except CookieError:
            return None

    def _cookie(self, token):
        cookie = SimpleCookie()
        cookie[COOKIE_NAME] = token
        item = cookie[COOKIE_NAME]
        item['path'], item['httponly'], item['samesite'] = '/', True, 'Strict'
        item['max-age'] = str(int(self.ttl))
        if self.secure:
            item['secure'] = True
        return item.OutputString()

    @staticmethod
    def _busy(context):
        tasks = getattr(context.app, 'tasks', None)
        return context.active_requests > 0 or bool(tasks and tasks.active())

    def cleanup(self):
        with self._lock:
            moment = self.clock()
            expired = [token for token, context in self._items.items()
                       if moment - context.last_seen >= self.ttl and not self._busy(context)]
            for token in expired:
                context = self._items.pop(token)
                shutil.rmtree(str(context.directory))
            return len(expired)

    @contextmanager
    def session(self, cookie_header, peer=None):
        with self._lock:
            if self._closed:
                raise SessionCapacityError('服务正在停止，请稍后再试。')
            self.cleanup()
            token = self._token(cookie_header)
            context = self._items.get(token)
            if context is None:
                if len(self._items) >= self.max_sessions:
                    raise SessionCapacityError('当前访客数量已达到服务器容量，请稍后再试。')
                permit = self.creation_limiter.reserve(peer) if self.creation_limiter else None
                try:
                    token = secrets.token_urlsafe(32)
                    directory = self.root / hashlib.sha256(token.encode('ascii')).hexdigest()
                    directory.mkdir(mode=0o700)
                    try:
                        private = Store(directory / 'visitor.sqlite')
                        Path(private.path).chmod(0o600)
                        store = SessionStore(self.base, private)
                        app = self.factory(store, directory)
                    except Exception:
                        shutil.rmtree(str(directory))
                        raise
                finally:
                    if permit:
                        permit.release()
                context = SessionContext(app, store, directory, self.clock())
                self._items[token] = context
            context.last_seen = self.clock()
            context.active_requests += 1
            resolved = ResolvedSession(context.app, context.store, context.directory, self._cookie(token))
        try:
            yield resolved
        finally:
            with self._lock:
                context.active_requests -= 1
                context.last_seen = self.clock()

    def close(self):
        """Close the registry; caller stops shared background tasks before cleanup."""
        with self._lock:
            self._closed = True
            for token, context in list(self._items.items()):
                if not self._busy(context):
                    shutil.rmtree(str(context.directory))
                    del self._items[token]
            if not self._items and not self._registry_lock.closed:
                self._registry_lock.close()


class RateLimitError(ValueError):
    status_code = 429

    def __init__(self, message, retry_after):
        super().__init__(message)
        self.retry_after = max(1, int(math.ceil(retry_after)))


class _Permit:
    def __init__(self, limiter):
        self.limiter, self.released = limiter, False

    def release(self):
        with self.limiter._lock:
            if not self.released:
                self.limiter._active -= 1
                self.released = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.release()


class RateLimiter:
    """Bound per-IP/global admissions and active work independently of cookies."""
    def __init__(self, per_ip=10, global_limit=100, max_active=3, window_seconds=3600,
                 max_identities=4096, clock=time.monotonic, label='AI'):
        if min(per_ip, global_limit, max_active, window_seconds, max_identities) <= 0:
            raise ValueError('Rate limits must be positive')
        self.per_ip, self.global_limit, self.max_active = per_ip, global_limit, max_active
        self.window_seconds, self.max_identities, self.clock = window_seconds, max_identities, clock
        self.label = label
        self._lock = threading.Lock()
        self._window = None
        self._counts, self._total, self._active = {}, 0, 0

    def reserve(self, ip):
        identity = hashlib.sha256(str(ip).encode('utf-8')).hexdigest()
        with self._lock:
            moment = self.clock()
            window = int(moment // self.window_seconds)
            if window != self._window:
                self._window, self._counts, self._total = window, {}, 0
            retry_after = (window + 1) * self.window_seconds - moment
            if self._active >= self.max_active:
                raise RateLimitError('当前 {} 任务已满，请稍后重试。'.format(self.label), 5)
            if self._total >= self.global_limit or self._counts.get(identity, 0) >= self.per_ip:
                raise RateLimitError('本时段 {} 使用额度已用完，请稍后重试。'.format(self.label), retry_after)
            if identity not in self._counts and len(self._counts) >= self.max_identities:
                raise RateLimitError('当前访问容量已满，请稍后重试。', retry_after)
            self._counts[identity] = self._counts.get(identity, 0) + 1
            self._total += 1
            self._active += 1
            return _Permit(self)


@dataclass(frozen=True)
class PublicConfig:
    origin: str
    allowed_hosts: frozenset
    trusted_proxies: frozenset
    secure: bool = True
    page_hosts: frozenset = frozenset()

    @classmethod
    def from_env(cls, environ=None):
        values = os.environ if environ is None else environ
        origin = values.get('JOBCOMPASS_PUBLIC_ORIGIN', '').strip().rstrip('/')
        hosts = values.get('JOBCOMPASS_ALLOWED_HOSTS', '')
        parsed = urlsplit(origin)
        try:
            parsed.port
        except ValueError:
            raise ValueError('公开 origin 的端口无效。')
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('公开模式必须配置完整的 HTTPS JOBCOMPASS_PUBLIC_ORIGIN。')
        allowed = frozenset(host.strip().lower() for host in hosts.split(',') if host.strip())
        if not allowed or parsed.netloc.lower() not in allowed or any('*' in host or '/' in host or '@' in host or any(ch.isspace() for ch in host) for host in allowed):
            raise ValueError('JOBCOMPASS_ALLOWED_HOSTS 必须明确列出域名，并包含公开 origin 的主机。')
        proxies = frozenset(str(ipaddress.ip_address(value.strip())) for value in values.get('JOBCOMPASS_TRUSTED_PROXIES', '').split(',') if value.strip())
        page_hosts = frozenset(value.strip().lower() for value in values.get('JOBCOMPASS_PAGE_HOSTS', '').split(',') if value.strip())
        if any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '.' not in host or '..' in host for host in page_hosts):
            raise ValueError('JOBCOMPASS_PAGE_HOSTS 只接受精确域名，不接受 URL、路径或通配符。')
        return cls(origin, allowed, proxies, page_hosts=page_hosts)

    def valid_request(self, host, origin=None, write=False):
        return isinstance(host, str) and host.lower() in self.allowed_hosts and (not write or origin == self.origin)

    def client_ip(self, peer, real_ip=None):
        try:
            peer = str(ipaddress.ip_address(peer))
            if peer in self.trusted_proxies and real_ip:
                return str(ipaddress.ip_address(real_ip.strip()))
        except ValueError:
            pass
        return peer


class PublicCollectionError(ValueError):
    status_code = 403


def validate_page_url(url, allowed_hosts, resolve=False):
    """Only operator-approved exact HTTPS hosts; never trust visitor subdomains."""
    try:
        parsed = urlsplit(url)
        allowed = (parsed.scheme == 'https' and parsed.hostname in allowed_hosts and
                   not parsed.username and not parsed.password and parsed.port in (None, 443))
    except (ValueError, TypeError):
        allowed = False
    if not allowed:
        raise PublicCollectionError('此网页域名未获服务器允许采集；可使用 JobsDB 更新或导入 CSV、JSON、HTML 文件。')
    if resolve:
        validate_url(url)
    return url


class PublicRedirect(HTTPRedirectHandler):
    def __init__(self, allowed_hosts):
        self.allowed_hosts = frozenset(allowed_hosts)

    def redirect_request(self, request, fp, code, message, headers, newurl):
        validate_page_url(newurl, self.allowed_hosts, resolve=True)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch_public_page(url, allowed_hosts):
    """No credentials/proxy environment; every redirect retains the same allowlist."""
    validate_page_url(url, allowed_hosts, resolve=True)
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    opener = build_opener(ProxyHandler({}), PublicRedirect(allowed_hosts), HTTPSHandler(context=context))
    request = Request(url, headers={'User-Agent':AGENT, 'Accept':'text/html,application/json'})
    try:
        with opener.open(request, timeout=25) as response:
            body = response.read(8 * 1024 * 1024 + 1)
            if len(body) > 8 * 1024 * 1024:
                raise ValueError('网站返回内容过大。')
            return body.decode('utf-8-sig')
    except HTTPError as error:
        raise ValueError('允许采集的网站返回 HTTP {}。'.format(error.code)) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError('网站连接失败或超时，可改用本地文件导入。') from None


def collect_public_page(url, store, allowed_hosts):
    validate_page_url(url, allowed_hosts)
    parsed = urlsplit(url)
    shared = getattr(store, 'base', store)
    stamp = datetime.now(timezone.utc).isoformat()
    key = 'public_page_attempt_' + parsed.hostname
    with shared.connection() as connection:
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        if row and (datetime.fromisoformat(stamp) - datetime.fromisoformat(json.loads(row[0]))).total_seconds() < 15:
            raise ValueError('所有访客对同一网站的采集至少间隔 15 秒，请稍后重试。')
        connection.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, json.dumps(stamp)))
    robots = RobotFileParser()
    robots.parse(fetch_public_page('https://' + parsed.netloc + '/robots.txt', allowed_hosts).splitlines())
    if not robots.can_fetch(AGENT, url):
        raise ValueError('网站 robots.txt 不允许此采集，可使用授权导出文件。')
    count = store.upsert_jobs(parse_jsonld(fetch_public_page(url, allowed_hosts), url))
    store.log(parsed.hostname, 'success', count, '允许域名的公开网页结构化采集')
    return {'count':count, 'message':'已导入 {} 条网页岗位。'.format(count)}


def sanitize_public(value):
    """Remove infrastructure paths from metadata/errors without changing URLs."""
    hidden = {'path','source_path','database_path','db_path','index_root','result_root','root','directory','traceback'}
    if isinstance(value, dict):
        return {key: sanitize_public(item) for key, item in value.items() if str(key).lower() not in hidden}
    if isinstance(value, list):
        return [sanitize_public(item) for item in value]
    if isinstance(value, str):
        if value.startswith('/'):
            return '[server path]'
        value = re.sub(r'(?<![:/\w])/(?:[^/\s<>"\']+/)+[^\s<>"\']*', '[server path]', value)
        return re.sub(r'\b[A-Za-z]:[\\/][^\s<>"\']+', '[server path]', value)
    return value
