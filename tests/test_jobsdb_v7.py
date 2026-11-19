"""V7 search contracts with fictional responses; never contact JobsDB."""
import copy
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from jobcompass.jobsdb import collect
from jobcompass.benchmark import convert_record
from jobcompass.jobsdb_http import JobsDBError
from jobcompass.storage import Store
from tests.test_benchmark import fixture
from tests.jobsdb_fixtures import search, ImmediateEvent


class JobsDBV7Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'jobs.db')

    def tearDown(self):
        self.tmp.cleanup()

    def run_collect(self, responses, **kwargs):
        with patch('jobcompass.jobsdb.read_json', side_effect=responses) as request:
            result = collect(self.store, cancel=kwargs.pop('cancel', ImmediateEvent()), **kwargs)
        return result, request

    def test_search_uses_v7_fixed_categories_and_same_session_as_details(self):
        result, request = self.run_collect([search(['12345678']), fixture()], limit=1)
        url, body = request.call_args_list[0].args[:2]
        self.assertEqual(url, 'https://hk.jobsdb.com/graphql')
        self.assertEqual(body['operationName'], 'JobSearchV7')
        params = body['variables']['params']
        self.assertEqual(params['searchIntent']['filter']['categoryId'], ['6281', '1209', '6123'])
        self.assertEqual(params['searchIntent']['sort'], 'listedAt')
        self.assertEqual(params['sessionId'], request.call_args_list[1].args[1]['variables']['sessionId'])
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['search_api'], 'JobSearchV7')

    def test_server_page_size_and_context_drive_more_than_two_pages(self):
        ids = [str(12345670 + i) for i in range(7)]
        responses = [search(ids[i:i+2], page=i//2+1, size=2, count=7,
                            token='token-' + str(i//2+1)) for i in range(0, 7, 2)]
        result, request = self.run_collect(responses + [fixture(jid) for jid in ids], limit=7)
        self.assertEqual(result['count'], 7)
        self.assertEqual(result['pages'], 4)
        self.assertEqual(request.call_count, 11)
        second = request.call_args_list[1].args[1]['variables']['params']
        self.assertEqual(second['responseConfig']['pageSize'], 2)
        self.assertEqual(second['searchToken'], 'token-1')
        self.assertEqual(second['searchIntent']['filter']['newSince'], 1234)

    def test_zero_results_preserve_existing_jobs(self):
        self.store.upsert_jobs([convert_record(fixture())])
        result, request = self.run_collect([search()])
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['status'], 'success')
        self.assertEqual(request.call_count, 1)
        self.assertEqual(len(self.store.jobs()), 1)

    def test_bad_pagination_or_ids_stop_without_detail_calls(self):
        valid = search(['12345678'], count=5)
        variants = []
        for field, value in [('page', True), ('page', 2), ('pageSize', False),
                             ('pageSize', 0), ('pageSize', 101), ('resultCount', -1),
                             ('resultCount', True)]:
            data = copy.deepcopy(valid)
            data['data']['jobSearchV7']['results']['pagination'][field] = value
            variants.append(data)
        for jobs in [None, {}, [{'id': True}], [{'id': '12/34'}], [{}], []]:
            data = copy.deepcopy(valid)
            data['data']['jobSearchV7']['results']['jobs'] = jobs
            variants.append(data)
        for i, response in enumerate(variants):
            with self.subTest(i=i):
                store = Store(Path(self.tmp.name) / ('invalid-%s.db' % i))
                with patch('jobcompass.jobsdb.read_json', return_value=response) as request:
                    with self.assertRaises(ValueError): collect(store, cancel=ImmediateEvent())
                self.assertEqual(request.call_count, 1)
                self.assertEqual(store.jobs(), [])
                self.assertEqual(store.get('jobsdb_last_run')['status'], 'error')

    def test_changed_page_size_or_repeated_page_does_not_silently_succeed(self):
        for i, second in enumerate([search(['87654321'], page=2, size=1, count=4),
                                    search(['12345678'], page=2, size=2, count=4)]):
            store = Store(Path(self.tmp.name) / ('changed-%s.db' % i))
            with patch('jobcompass.jobsdb.read_json', side_effect=[search(['12345678'], size=2, count=4), second]) as request:
                with self.assertRaises(ValueError): collect(store, limit=4, cancel=ImmediateEvent())
            self.assertEqual(request.call_count, 2)

    def test_missing_or_unsafe_context_stops_before_next_page(self):
        for i, (token, since) in enumerate([(True, 1234), ('x'*8193, 1234), ('x', True), ('x', 'wrong')]):
            store = Store(Path(self.tmp.name) / ('context-%s.db' % i))
            with patch('jobcompass.jobsdb.read_json', return_value=search(['12345678'], size=1, count=5, token=token, since=since)) as request:
                with self.assertRaises(ValueError): collect(store, limit=5, cancel=ImmediateEvent())
            self.assertEqual(request.call_count, 1)

    def test_nullable_search_context_is_allowed(self):
        result, request = self.run_collect([search(['12345678'], size=1, count=2, token=None, since=None),
                                           search(['87654321'], page=2, size=1, count=2),
                                           fixture(), fixture('87654321')], limit=2)
        second = request.call_args_list[1].args[1]['variables']['params']
        self.assertNotIn('searchToken', second)
        self.assertIsNone(second['searchIntent']['filter']['newSince'])
        self.assertEqual(result['count'], 2)

    def test_explicit_missing_detail_is_unavailable_but_broken_schema_stops(self):
        result, _ = self.run_collect([search(['12345678']), {'data': {'jobDetails': None}}], limit=1)
        self.assertEqual(result['unavailable'], 1)
        for i, bad in enumerate([{}, {'data': {}}, {'data': {'jobDetails': {}}}]):
            store = Store(Path(self.tmp.name) / ('detail-%s.db' % i))
            with patch('jobcompass.jobsdb.read_json', side_effect=[search(['12345678']), bad]):
                with self.assertRaises(ValueError): collect(store, limit=1, cancel=ImmediateEvent())

    def test_in_process_collection_lock_releases_after_error(self):
        other = Store(Path(self.tmp.name) / 'other.db')
        def during(*args, **kwargs):
            with self.assertRaisesRegex(ValueError, '正在.*更新|更新.*进行'):
                collect(other, limit=1, cancel=ImmediateEvent())
            return search()
        with patch('jobcompass.jobsdb.read_json', side_effect=during):
            collect(self.store, limit=1, cancel=ImmediateEvent())
        with patch('jobcompass.jobsdb.read_json', return_value=search()):
            self.assertEqual(collect(other, limit=1, cancel=ImmediateEvent())['status'], 'success')

    def test_keyword_filters_only_bounded_batch_and_reports_exclusions(self):
        result, request = self.run_collect([search(['12345678', '87654321']),
                                           fixture(), fixture('87654321')], limit=2, keyword='unmatched fictional phrase')
        self.assertEqual(result['checked'], 2)
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['filtered_out'], 2)
        self.assertEqual(result['keyword_scope'], 'batch_text')
        self.assertIn('不是全站搜索', result['message'])
        self.assertNotIn('unmatched fictional phrase', str(request.call_args_list))

    def test_provider_retry_after_persists_between_connections(self):
        with patch('jobcompass.jobsdb.read_json', side_effect=JobsDBError('rate_limited', retry_after=600)):
            with self.assertRaises(ValueError): collect(self.store, cancel=ImmediateEvent())
        other = Store(self.store.path)
        later = (datetime.now(timezone.utc) + timedelta(seconds=65)).isoformat()
        with self.assertRaisesRegex(ValueError, '冷却'):
            other.reserve_jobsdb_attempt(later)
        later = (datetime.now(timezone.utc) + timedelta(seconds=610)).isoformat()
        other.reserve_jobsdb_attempt(later)


if __name__ == '__main__':
    unittest.main()
