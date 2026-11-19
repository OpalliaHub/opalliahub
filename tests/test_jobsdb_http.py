"""Offline JobsDB V7 transport contracts; no network, cookies or real waits."""
import io
import json
import unittest
from datetime import datetime, timezone
from email.message import Message
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request

from jobcompass.jobsdb_http import JobsDBClient, JobsDBError, JobsDBCancelled


URL = 'https://hk.jobsdb.com/graphql'
PAYLOAD = {'operationName': 'JobSearchV7', 'query': 'fixture query', 'variables': {}}


class ClockEvent:
    def __init__(self):
        self.clock = 100.0
        self.stopped = False
        self.waits = []
        self.cancel_on_wait = False

    def is_set(self):
        return self.stopped

    def wait(self, seconds):
        self.waits.append(seconds)
        self.clock += seconds
        if self.cancel_on_wait:
            self.stopped = True
        return self.stopped


class Response:
    def __init__(self, body=b'{"data":{"ok":true}}', status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = Message()
        for key, value in (headers or {}).items():
            self.headers[key] = value
        self.closed = False
        self.read_sizes = []

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]

    def info(self):
        return self.headers

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


def failure(status, headers=None):
    return HTTPError(URL, status, 'private upstream detail', headers or {}, io.BytesIO(b'secret body'))


def graphql_rate(code=None, message='Too many requests.'):
    error = {'message': message}
    if code:
        error['extensions'] = {'code': code}
    return Response(json.dumps({'errors': [error]}).encode('utf-8'))


class JobsDBHTTPTests(unittest.TestCase):
    def setUp(self):
        self.event = ClockEvent()
        self.opener = Mock()
        self.factory = patch('jobcompass.jobsdb_http.urllib.request.build_opener', return_value=self.opener).start()
        self.clock = patch('jobcompass.jobsdb_http.time.monotonic', side_effect=lambda: self.event.clock).start()
        self.addCleanup(patch.stopall)
        self.client = JobsDBClient(cancel=self.event)
        self.addCleanup(self.client.close)
        self.opener.open.return_value = Response()

    def read(self):
        return self.client.read_json(URL, PAYLOAD)

    def test_fixed_origin_headers_and_same_identity_for_entire_batch(self):
        self.read()
        self.read()
        self.factory.assert_called_once()
        calls = self.opener.open.call_args_list
        for call in calls:
            request = call.args[0]
            headers = {key.lower(): value for key, value in request.header_items()}
            self.assertEqual(request.full_url, URL)
            self.assertEqual(request.get_method(), 'POST')
            self.assertEqual(json.loads(request.data), PAYLOAD)
            self.assertEqual(call.kwargs['timeout'], 20)
            self.assertEqual(headers['origin'], 'https://hk.jobsdb.com')
            self.assertEqual(headers['referer'], 'https://hk.jobsdb.com/jobs')
            self.assertEqual(headers['x-seek-ec-sessionid'], self.client.session_id)
            self.assertEqual(headers['x-seek-ec-visitorid'], self.client.session_id)
            self.assertTrue(headers['user-agent'].startswith('JobCompass-'))
            self.assertNotIn('authorization', headers)
        self.assertEqual(self.event.waits, [1.5])

    def test_cookie_processor_is_reused_and_cookie_cleared_on_close(self):
        processors = [h for h in self.factory.call_args.args if isinstance(h, HTTPCookieProcessor)]
        self.assertEqual(len(processors), 1)
        processor = processors[0]
        processor.http_response(Request(URL), Response(headers={'Set-Cookie': 'session=fictional; Path=/; Secure'}))
        request = processor.https_request(Request(URL))
        self.assertEqual(request.get_header('Cookie'), 'session=fictional')
        self.read()
        self.read()
        self.assertEqual(len(processor.cookiejar), 1)
        self.client.close()
        self.assertEqual(len(processor.cookiejar), 0)

    def test_exact_destination_rejects_other_hosts_paths_queries_and_credentials(self):
        for url in ('http://hk.jobsdb.com/graphql', URL + '?x=1', URL + '#x',
                    'https://hk.jobsdb.com/jobs', 'https://hk.jobsdb.com.evil.test/graphql',
                    'https://name:secret@hk.jobsdb.com/graphql', 'https://127.0.0.1/graphql'):
            with self.subTest(url=url), self.assertRaises(JobsDBError) as raised:
                self.client.read_json(url, PAYLOAD)
            self.assertEqual(raised.exception.code, 'invalid_request')
        self.opener.open.assert_not_called()

    def test_redirect_handler_rejects_even_same_origin_redirect(self):
        handlers = [h for h in self.factory.call_args.args if hasattr(h, 'redirect_request')]
        self.assertEqual(len(handlers), 1)
        with self.assertRaises(JobsDBError) as raised:
            handlers[0].redirect_request(Request(URL), None, 302, 'private', {}, URL)
        self.assertEqual(raised.exception.code, 'redirect_blocked')

    def test_response_read_is_bounded_and_closed(self):
        response = Response(b'x' * (8 * 1024 * 1024 + 1))
        self.opener.open.return_value = response
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'response_too_large')
        self.assertEqual(response.read_sizes, [8 * 1024 * 1024 + 1])
        self.assertTrue(response.closed)
        self.opener.open.assert_called_once()

    def test_html_challenge_and_content_header_stop_without_retry(self):
        for response in (Response(b'<html>private challenge</html>'),
                         Response(b'not html', headers={'Content-Type': 'text/html; charset=UTF-8'}),
                         Response(headers={'CF-Mitigated': 'challenge'})):
            with self.subTest(headers=dict(response.headers)), self.assertRaises(JobsDBError) as raised:
                self.opener.open.reset_mock()
                self.opener.open.return_value = response
                self.read()
            self.assertEqual(raised.exception.code, 'challenge')
            self.assertNotIn('private', str(raised.exception))
            self.opener.open.assert_called_once()

    def test_access_refusal_and_cloudflare_503_never_retry(self):
        for status, headers, code in ((401, {}, 'access_denied'), (403, {}, 'access_denied'),
                                      (503, {'CF-Mitigated': 'challenge'}, 'challenge'),
                                      (503, {'Content-Type': 'text/html'}, 'challenge')):
            self.opener.open.reset_mock()
            error = failure(status, headers)
            self.opener.open.side_effect = error
            with self.subTest(status=status), self.assertRaises(JobsDBError) as raised:
                self.read()
            self.assertEqual(raised.exception.code, code)
            self.assertNotIn('private', str(raised.exception))
            self.assertTrue(error.fp.closed)
            self.opener.open.assert_called_once()

    def test_only_explicit_transient_http_statuses_retry(self):
        for status in (429, 502, 503, 504):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = [failure(status, {'Retry-After': '2'}), Response()]
            with self.subTest(status=status):
                self.assertEqual(self.read(), {'data': {'ok': True}})
            self.assertEqual(self.opener.open.call_count, 2)
        for status in (400, 404, 500):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = failure(status)
            with self.subTest(status=status), self.assertRaises(JobsDBError):
                self.read()
            self.opener.open.assert_called_once()

    def test_transient_error_with_unlabelled_html_body_stops(self):
        error = HTTPError(URL, 503, 'fixture', {}, io.BytesIO(b' <html>private verification</html>'))
        self.opener.open.side_effect = error
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'challenge')
        self.assertNotIn('private', str(raised.exception))
        self.opener.open.assert_called_once()

    def test_retry_attempts_capped_and_default_rate_wait_respected(self):
        self.opener.open.side_effect = [failure(429), failure(429), failure(429)]
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'rate_limited')
        self.assertEqual(self.opener.open.call_count, 3)
        self.assertEqual(self.event.waits, [30.0, 60.0])

    def test_retry_after_seconds_and_http_date(self):
        self.opener.open.side_effect = [failure(429, {'Retry-After': '7'}), Response()]
        self.read()
        self.assertIn(7.0, self.event.waits)
        with patch('jobcompass.jobsdb_http.datetime') as date:
            date.now.return_value = datetime(2026, 11, 19, tzinfo=timezone.utc)
            self.opener.open.side_effect = [failure(503, {'Retry-After': 'Thu, 19 Nov 2026 00:00:08 GMT'}), Response()]
            self.read()
        self.assertIn(8.0, self.event.waits)

    def test_long_retry_after_stops_without_retrying_early(self):
        self.opener.open.side_effect = failure(429, {'Retry-After': '61'})
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.retry_after, 61.0)
        self.assertEqual(self.event.waits, [])
        self.opener.open.assert_called_once()

    def test_retry_wait_budget_is_shared_across_batch(self):
        self.opener.open.side_effect = [failure(429, {'Retry-After': '60'}), Response(),
                                        failure(429, {'Retry-After': '31'})]
        self.read()
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'rate_limited')
        self.assertEqual(self.opener.open.call_count, 3)
        self.assertNotIn(31.0, self.event.waits)

    def test_graphql_known_rate_errors_retry_but_other_errors_do_not(self):
        for code in ('TOO_MANY_REQUESTS', 'RATE_LIMITED', 'THROTTLED'):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = [graphql_rate(code, 'private diagnostic'), Response()]
            with self.subTest(code=code):
                self.read()
            self.assertEqual(self.opener.open.call_count, 2)
        self.opener.open.reset_mock()
        self.opener.open.side_effect = None
        self.opener.open.return_value = Response(b'{"errors":[{"message":"private schema error"}]}')
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'graphql_error')
        self.assertNotIn('private', str(raised.exception))
        self.opener.open.assert_called_once()

    def test_graphql_rate_message_and_mixed_errors(self):
        self.opener.open.side_effect = [graphql_rate(), Response()]
        self.read()
        self.assertEqual(self.opener.open.call_count, 2)
        self.opener.open.reset_mock()
        self.opener.open.side_effect = None
        self.opener.open.return_value = Response(b'{"errors":[{"message":"Too many requests."},{"message":"Forbidden"}]}')
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'graphql_error')
        self.opener.open.assert_called_once()

    def test_invalid_json_utf8_and_top_level_do_not_retry(self):
        for body in (b'broken', b'[]', b'null', b'\xff'):
            self.opener.open.reset_mock()
            self.opener.open.return_value = Response(body)
            with self.subTest(body=body), self.assertRaises(JobsDBError):
                self.read()
            self.opener.open.assert_called_once()

    def test_network_failures_and_timeouts_have_safe_messages_and_no_retry(self):
        for error in (TimeoutError('private hostname'), URLError('private network route'), OSError('private path')):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = error
            with self.subTest(error=type(error).__name__), self.assertRaises(JobsDBError) as raised:
                self.read()
            self.assertNotIn('private', str(raised.exception))
            self.opener.open.assert_called_once()

    def test_cancel_before_request_and_during_rate_wait(self):
        self.event.stopped = True
        with self.assertRaises(JobsDBCancelled):
            self.read()
        self.opener.open.assert_not_called()
        self.event.stopped = False
        self.event.cancel_on_wait = True
        self.opener.open.side_effect = failure(429)
        with self.assertRaises(JobsDBCancelled):
            self.read()
        self.opener.open.assert_called_once()

    def test_cancel_during_interval_prevents_next_request(self):
        self.read()
        self.event.cancel_on_wait = True
        with self.assertRaises(JobsDBCancelled):
            self.read()
        self.opener.open.assert_called_once()

    def test_slow_request_is_not_followed_by_an_unnecessary_interval(self):
        def slow(*args, **kwargs):
            self.event.clock += 2
            return Response()
        self.opener.open.side_effect = slow
        self.read()
        self.read()
        self.assertEqual(self.event.waits, [])

    def test_progress_reports_safe_wait(self):
        messages = []
        self.client.progress = lambda **data: messages.append(data)
        self.opener.open.side_effect = [failure(429, {'Retry-After': '3'}), Response()]
        self.read()
        self.assertTrue(messages)
        self.assertNotIn('private', str(messages))
        self.assertIn('3', str(messages))

    def test_progress_cancellation_stops_before_retry_wait(self):
        def cancel(**data):
            self.event.stopped = True
        self.client.progress = cancel
        self.opener.open.side_effect = failure(429)
        with self.assertRaises(JobsDBCancelled):
            self.read()
        self.assertEqual(self.event.waits, [])
        self.opener.open.assert_called_once()

    def test_closed_client_cannot_be_reused(self):
        self.client.close()
        self.client.close()
        with self.assertRaises(JobsDBError) as raised:
            self.read()
        self.assertEqual(raised.exception.code, 'closed')
        self.opener.open.assert_not_called()


if __name__ == '__main__':
    unittest.main()
