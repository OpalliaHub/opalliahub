"""Fixed-destination JobsDB transport with one session per bounded collection.

This is ordinary HTTPS, not a browser-verification bypass. Access refusals and
verification pages stop immediately. Explicit rate limits and transient 502/503/
504 responses, connection failures and timeouts share at most three attempts,
respecting Retry-After. TLS verification errors are never retried. Retry waiting
is capped at 60 seconds each and 90 seconds over the entire client batch.
"""
import errno
import http.cookiejar
import json
import math
import socket
import ssl
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .sources import AGENT


ENDPOINT = 'https://hk.jobsdb.com/graphql'
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
REQUEST_INTERVAL = 1.5
REQUEST_TIMEOUT = 20
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT = 60.0
RETRY_WAIT_BUDGET = 90.0
TRANSIENT_STATUSES = frozenset({429, 502, 503, 504})
RATE_CODES = frozenset({'TOO_MANY_REQUESTS', 'RATE_LIMITED', 'THROTTLED'})
RATE_MESSAGES = frozenset({'too many requests', 'rate limit exceeded'})
ERROR_MESSAGES = {
    'invalid_request': 'JobsDB 请求参数或接口地址无效。',
    'closed': '本次 JobsDB 请求会话已结束。',
    'redirect_blocked': 'JobsDB 接口发生重定向，已停止本次更新。',
    'response_too_large': 'JobsDB 返回内容过大，已停止本次更新。',
    'challenge': 'JobsDB 返回浏览器验证页面，已停止；请到原站检查访问状态。',
    'access_denied': 'JobsDB 拒绝当前连接访问，已停止；请到原站检查访问状态。',
    'rate_limited': 'JobsDB 暂时限制请求频率，本次等待或重试额度已用尽，请稍后更新。',
    'transient': 'JobsDB 服务暂时不可用，本次重试已停止，请稍后更新。',
    'http_error': 'JobsDB 接口返回异常状态，已停止本次更新。',
    'invalid_json': 'JobsDB 未返回有效 JSON，已停止本次更新。',
    'invalid_response': 'JobsDB 接口响应结构已变化，已停止本次更新。',
    'graphql_error': 'JobsDB 查询接口返回错误，已停止本次更新。',
    'network': '连接 JobsDB 失败，请稍后检查网络或原站访问状态。',
    'timeout': '连接 JobsDB 超时，已停止本次更新。',
    'tls_error': 'JobsDB 安全连接或证书检查失败，已停止本次更新；请检查网络与证书配置。',
}


class JobsDBError(ValueError):
    """A bounded diagnostic: no upstream body, URL, cookie or error text."""

    def __init__(self, code, retry_after=None):
        self.code = code if code in ERROR_MESSAGES else 'http_error'
        self.retry_after = (float(retry_after) if isinstance(retry_after, (int, float))
                            and not isinstance(retry_after, bool)
                            and math.isfinite(retry_after) and retry_after >= 0 else None)
        super().__init__(ERROR_MESSAGES[self.code])


class JobsDBCancelled(ValueError):
    def __init__(self):
        super().__init__('已取消 JobsDB 更新，停止后续请求。')


class _RetryableNetwork(JobsDBError):
    """Internal marker; retry scheduling still belongs to the one request loop."""

    def __init__(self, code, headers=None):
        super().__init__(code)
        self.retry_headers = {'retry-after': headers['retry-after']} if headers and 'retry-after' in headers else {}


def _network_failure(error, headers=None):
    wrapped = isinstance(error, urllib.error.URLError)
    reason = error
    for _ in range(8):
        if not isinstance(reason, urllib.error.URLError):
            break
        reason = reason.reason
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return JobsDBError('tls_error')
    if isinstance(reason, (TimeoutError, socket.timeout)) or getattr(reason, 'errno', None) == errno.ETIMEDOUT:
        return _RetryableNetwork('timeout', headers)
    if isinstance(reason, urllib.error.URLError):
        # Malformed recursive wrappers are not ordinary urllib network failures.
        return JobsDBError('network')
    if (wrapped or isinstance(reason, ConnectionError)
            or getattr(reason, 'errno', None) in (errno.ECONNRESET, errno.ECONNREFUSED,
                                                 errno.EHOSTUNREACH, errno.ENETUNREACH, errno.EPIPE)):
        return _RetryableNetwork('network', headers)
    return JobsDBError('network')


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise JobsDBError('redirect_blocked')


def _retry_after(value):
    if not isinstance(value, str) or len(value) > 128:
        return None
    try:
        seconds = float(value)
        return max(0.0, seconds) if math.isfinite(seconds) else None
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


def _rate_errors(errors):
    """Retry only when every supplied GraphQL error is a recognized rate limit."""
    if not isinstance(errors, list) or not errors:
        return False
    for error in errors:
        if not isinstance(error, dict):
            return False
        extension = error.get('extensions')
        code = extension.get('code') if isinstance(extension, dict) else None
        message = error.get('message')
        message = message.strip().lower().rstrip('.') if isinstance(message, str) else ''
        if not isinstance(code, str) or code not in RATE_CODES:
            if message not in RATE_MESSAGES:
                return False
    return True


class JobsDBClient:
    """One serial collection session; do not share this client across tasks."""

    def __init__(self, cancel=None, progress=None):
        self.cancel = cancel if cancel is not None else threading.Event()
        self.progress = progress or (lambda **kwargs: None)
        self.session_id = str(uuid.uuid4())
        self._next_start = 0.0
        self._retry_wait_used = 0.0
        self._closed = False
        self._cookies = http.cookiejar.CookieJar()
        context = ssl.create_default_context()
        try:
            import certifi
            context.load_verify_locations(certifi.where())
        except ImportError:
            pass
        # Retain urllib's normal environment proxy behavior. Never export cookies
        # or forward them to another origin; redirects are prohibited altogether.
        self._opener = urllib.request.build_opener(
            _NoRedirect(), urllib.request.HTTPCookieProcessor(self._cookies),
            urllib.request.HTTPSHandler(context=context))

    def _check(self):
        if self._closed:
            raise JobsDBError('closed')
        if self.cancel.is_set():
            raise JobsDBCancelled()

    def _wait(self, delay):
        self._check()
        if delay > 0 and self.cancel.wait(delay):
            raise JobsDBCancelled()
        self._check()

    def _send(self, request):
        self._check()
        self._wait(max(0.0, self._next_start - time.monotonic()))
        self._next_start = time.monotonic() + REQUEST_INTERVAL
        try:
            with self._opener.open(request, timeout=REQUEST_TIMEOUT) as response:
                headers = {key.lower(): value for key, value in response.headers.items()}
                status = response.status
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise JobsDBError('response_too_large')
                return status, headers, body
        except urllib.error.HTTPError as error:
            try:
                headers = {key.lower(): value for key, value in (error.headers or {}).items()}
                body = b''
                # A 503 verification page can lack challenge/HTML headers. Inspect
                # only bounded candidate-retry bodies, never display or log them.
                # Explicit refusals and labeled challenges require no body read.
                if (error.code in TRANSIENT_STATUSES and error.fp is not None
                        and headers.get('cf-mitigated', '').lower() != 'challenge'
                        and 'text/html' not in headers.get('content-type', '').lower()):
                    try:
                        body = error.read(MAX_RESPONSE_BYTES + 1)
                    except (urllib.error.URLError, OSError) as failure:
                        raise _network_failure(failure, headers) from None
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise JobsDBError('response_too_large')
                return error.code, headers, body
            finally:
                error.close()
        except (urllib.error.URLError, OSError) as failure:
            raise _network_failure(failure) from None

    def _retry(self, code, headers, attempt):
        supplied = _retry_after(headers.get('retry-after'))
        delay = supplied if supplied is not None else (30.0 if code == 'rate_limited' else 2.0) * (2 ** attempt)
        if (attempt + 1 >= MAX_ATTEMPTS or delay > MAX_RETRY_WAIT
                or self._retry_wait_used + delay > RETRY_WAIT_BUDGET):
            raise JobsDBError(code, retry_after=supplied)
        self.progress(phase='JobsDB 请求暂缓，等待 {:g} 秒后重试。'.format(delay))
        self._wait(delay)
        self._retry_wait_used += delay

    def read_json(self, url, payload=None):
        self._check()
        if url != ENDPOINT or (payload is not None and not isinstance(payload, dict)):
            raise JobsDBError('invalid_request')
        try:
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8') if payload is not None else None
        except (ValueError, TypeError, UnicodeError):
            raise JobsDBError('invalid_request') from None
        headers = {
            'User-Agent': AGENT, 'Accept': 'application/json',
            'Accept-Language': 'en-HK,en;q=0.9',
            'Origin': 'https://hk.jobsdb.com', 'Referer': 'https://hk.jobsdb.com/jobs',
            'X-Seek-EC-SessionId': self.session_id,
            'X-Seek-EC-VisitorId': self.session_id,
        }
        if data is not None:
            headers['Content-Type'] = 'application/json'
        for attempt in range(MAX_ATTEMPTS):
            # A fresh Request lets the same cookie processor update cookies on
            # retries while retaining the original payload and session identity.
            try:
                status, response_headers, body = self._send(urllib.request.Request(url, data=data, headers=headers))
            except _RetryableNetwork as error:
                self._retry(error.code, error.retry_headers, attempt)
                continue
            self._check()
            if response_headers.get('cf-mitigated', '').lower() == 'challenge':
                raise JobsDBError('challenge')
            if status in (401, 403):
                raise JobsDBError('access_denied')
            if ('text/html' in response_headers.get('content-type', '').lower()
                    or body.lstrip(b'\xef\xbb\xbf \t\r\n').startswith(b'<')):
                raise JobsDBError('challenge')
            if status in TRANSIENT_STATUSES:
                self._retry('rate_limited' if status == 429 else 'transient', response_headers, attempt)
                continue
            if 300 <= status < 400:
                raise JobsDBError('redirect_blocked')
            if status != 200:
                raise JobsDBError('http_error')
            try:
                result = json.loads(body.decode('utf-8-sig'))
            except (ValueError, UnicodeError):
                raise JobsDBError('invalid_json') from None
            if not isinstance(result, dict):
                raise JobsDBError('invalid_response')
            if result.get('errors'):
                if _rate_errors(result['errors']):
                    self._retry('rate_limited', response_headers, attempt)
                    continue
                raise JobsDBError('graphql_error')
            return result
        raise JobsDBError('transient')  # Defensive: _retry raises at the last attempt.

    def close(self):
        if not self._closed:
            self._closed = True
            self._cookies.clear()
            self._opener.close()

    def __enter__(self):
        self._check()
        return self

    def __exit__(self, *args):
        self.close()
