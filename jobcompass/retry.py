"""Bounded retries for explicit transient DeepSeek HTTP responses only.

The 95-second window bounds retry scheduling, not the lifetime of a socket
operation already in progress. There is no timeout retry or output repair loop.
"""
import time
from urllib.error import HTTPError

MAX_ATTEMPTS = 3
RETRY_DELAYS = (1, 2)
RETRY_WINDOW_SECONDS = 95
TRANSIENT_STATUSES = frozenset({429, 502, 503, 504})


def _http_error(error):
    if isinstance(error, HTTPError):
        return error
    # sources.fetch deliberately exposes a safe ValueError while Python retains
    # the underlying HTTPError. Inspect its type/code, never its text or body.
    if isinstance(error, ValueError):
        cause = error.__cause__
        if cause is None and not error.__suppress_context__:
            cause = error.__context__
        if isinstance(cause, HTTPError):
            return cause
    return None


def request_with_retry(transport, url, data=None, headers=None, timeout=90, trusted_service=True):
    """Call a transport at most three times; parse/validate AI output afterwards."""
    deadline = time.monotonic() + RETRY_WINDOW_SECONDS
    last_error = None
    for attempt in range(MAX_ATTEMPTS):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if last_error is not None:
                raise last_error
            raise TimeoutError('AI request scheduling budget exhausted.')
        try:
            return transport(url, data, headers, timeout=min(timeout, remaining), trusted_service=trusted_service)
        except (ValueError, HTTPError) as error:
            http_error = _http_error(error)
            if http_error is None or http_error.code not in TRANSIENT_STATUSES or attempt == MAX_ATTEMPTS - 1:
                raise
            delay = RETRY_DELAYS[attempt]
            if deadline - time.monotonic() <= delay:
                raise
            last_error = error
            if http_error.fp is not None:
                http_error.close()
            time.sleep(delay)
