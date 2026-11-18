"""Mocked transport retry contracts; no API key, credits, network or real sleep."""
import json
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from jobcompass.retry import request_with_retry
from jobcompass.ai import call_ai
from jobcompass.research_ai import _call


def http_error(code):
    return HTTPError('https://api.deepseek.com/chat/completions', code, 'fixture', {}, None)


def wrapped_error(code):
    try:
        raise http_error(code)
    except HTTPError:
        try:
            raise ValueError('safe transport error')
        except ValueError as error:
            return error


class RetryTests(unittest.TestCase):
    def request(self, transport, **kwargs):
        return request_with_retry(transport, 'https://api.deepseek.com/chat/completions',
                                  b'{}', {'Authorization': 'Bearer fixture'}, **kwargs)

    def test_first_success_has_no_sleep(self):
        transport = Mock(return_value='ok')
        with patch('jobcompass.retry.time.sleep') as sleep:
            self.assertEqual(self.request(transport), 'ok')
        transport.assert_called_once()
        sleep.assert_not_called()

    def test_transient_statuses_retry_with_same_payload(self):
        for code in (429, 502, 503, 504):
            with self.subTest(code=code), patch('jobcompass.retry.time.sleep') as sleep:
                transport = Mock(side_effect=[wrapped_error(code), 'ok'])
                self.assertEqual(self.request(transport), 'ok')
                self.assertEqual(transport.call_count, 2)
                self.assertEqual(transport.call_args_list[0].args, transport.call_args_list[1].args)
                sleep.assert_called_once_with(1)

    def test_attempt_cap_and_fixed_exponential_wait(self):
        last = wrapped_error(503)
        transport = Mock(side_effect=[wrapped_error(429), wrapped_error(502), last])
        with patch('jobcompass.retry.time.sleep') as sleep, self.assertRaises(ValueError) as raised:
            self.request(transport)
        self.assertIs(raised.exception, last)
        self.assertEqual(transport.call_count, 3)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [1, 2])

    def test_direct_http_error_also_supported(self):
        with patch('jobcompass.retry.time.sleep'):
            self.assertEqual(self.request(Mock(side_effect=[http_error(503), 'ok'])), 'ok')

    def test_auth_balance_permission_and_bad_requests_never_retry(self):
        for code in (400, 401, 402, 403, 404, 409, 422, 500):
            with self.subTest(code=code), patch('jobcompass.retry.time.sleep') as sleep:
                transport = Mock(side_effect=wrapped_error(code))
                with self.assertRaises(ValueError):
                    self.request(transport)
                transport.assert_called_once()
                sleep.assert_not_called()

    def test_ambiguous_timeout_connection_or_message_never_retry(self):
        for error in (TimeoutError(), URLError('timeout'), OSError('connection reset'), ValueError('HTTP 503')):
            with self.subTest(error=type(error).__name__), patch('jobcompass.retry.time.sleep') as sleep:
                transport = Mock(side_effect=error)
                with self.assertRaises(type(error)):
                    self.request(transport)
                transport.assert_called_once()
                sleep.assert_not_called()

    def test_budget_exhaustion_does_not_schedule_retry(self):
        transport = Mock(side_effect=wrapped_error(503))
        with patch('jobcompass.retry.time.monotonic', side_effect=[0, 0, 95]), patch('jobcompass.retry.time.sleep') as sleep:
            with self.assertRaises(ValueError):
                self.request(transport)
        transport.assert_called_once()
        sleep.assert_not_called()

    def test_next_attempt_timeout_uses_remaining_budget(self):
        transport = Mock(side_effect=[wrapped_error(503), 'ok'])
        with patch('jobcompass.retry.time.monotonic', side_effect=[0, 0, 80, 81]), patch('jobcompass.retry.time.sleep'):
            self.assertEqual(self.request(transport), 'ok')
        self.assertEqual(transport.call_args_list[0].kwargs['timeout'], 90)
        self.assertEqual(transport.call_args_list[1].kwargs['timeout'], 14)

    def test_scheduler_delay_does_not_start_late_retry(self):
        first = wrapped_error(503)
        transport = Mock(side_effect=[first, 'unexpected'])
        with patch('jobcompass.retry.time.monotonic', side_effect=[0, 0, 93, 96]), patch('jobcompass.retry.time.sleep'):
            with self.assertRaises(ValueError):
                self.request(transport)
        transport.assert_called_once()


class AdapterRetryTests(unittest.TestCase):
    def test_resume_adapter_recovers_transient_response(self):
        payload = {'choices': [{'message': {'content': json.dumps({'summary':'ok','strengths':[], 'suggestions':[], 'questions':[]})}}]}
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY':'test'}), patch('jobcompass.ai.fetch', side_effect=[wrapped_error(503), json.dumps(payload)]) as fetch, patch('jobcompass.retry.time.sleep'):
            self.assertEqual(call_ai('analyze', 'Python SQL resume')['summary'], 'ok')
        self.assertEqual(fetch.call_count, 2)

    def test_research_adapter_recovers_transient_response(self):
        payload = {'choices': [{'message': {'content': '{"plan":{"action":"skills"}}'}}]}
        with patch.dict('os.environ', {'DEEPSEEK_API_KEY':'test'}), patch('jobcompass.research_ai.fetch', side_effect=[wrapped_error(429), json.dumps(payload)]) as fetch, patch('jobcompass.retry.time.sleep'):
            self.assertEqual(_call('system', {})[0]['plan']['action'], 'skills')
        self.assertEqual(fetch.call_count, 2)

    def test_malformed_model_output_is_not_retried(self):
        for module, invoke in (('ai', lambda: call_ai('analyze', 'Python SQL resume')), ('research_ai', lambda: _call('system', {}))):
            with self.subTest(module=module), patch.dict('os.environ', {'DEEPSEEK_API_KEY':'test'}), patch('jobcompass.' + module + '.fetch', return_value='{}') as fetch, patch('jobcompass.retry.time.sleep') as sleep:
                with self.assertRaises(ValueError):
                    invoke()
                fetch.assert_called_once()
                sleep.assert_not_called()


if __name__ == '__main__':
    unittest.main()
