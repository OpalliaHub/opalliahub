"""Behavioral regression tests for the bounded ranking result cache."""
import copy
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from jobcompass.matching import rank_jobs
from jobcompass.ranking_cache import RankedJobsCache


RESUME = 'Python SQL data analysis developer with two years of experience.'
PROFILE = {'skills': ['Python', 'SQL'], 'experience_years': 2, 'education': '本科'}
JOBS = [
    {'id': '1', 'title': 'Python developer', 'description': 'Python SQL. Bachelor degree. 2 years experience.',
     'skills': ['Python', 'SQL'], 'company': 'Example', 'location': 'Hong Kong',
     'status': 'saved', 'note': '', 'metadata': {'tags': ['example']}},
    {'id': '2', 'title': 'Data analyst', 'description': 'Python Pandas data analysis.',
     'skills': ['Python', 'Pandas'], 'company': 'Sample', 'location': 'Singapore'},
]
PREFERENCES = {'location': 'Hong Kong', 'experience_years': 2}


class RankedJobsCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = RankedJobsCache()
        self.args = copy.deepcopy([RESUME, PROFILE, JOBS, PREFERENCES])

    def test_hit_matches_actual_ranker_without_recomputing(self):
        expected = rank_jobs(*self.args)
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.assertEqual(self.cache.rank(*self.args), expected)
            self.assertEqual(self.cache.rank(*self.args), expected)
        self.assertEqual(rank.call_count, 1)
        info = self.cache.cache_info()
        self.assertEqual((info.hits, info.misses, info.maxsize, info.currsize), (1, 1, 1, 1))

    def test_dictionary_insertion_order_does_not_invalidate(self):
        reordered = json.loads(json.dumps(self.args, sort_keys=True))
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.assertEqual(self.cache.rank(*self.args), self.cache.rank(*reordered))
        self.assertEqual(rank.call_count, 1)

    def test_none_and_empty_preferences_are_equivalent(self):
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.assertEqual(self.cache.rank(*self.args[:3]), self.cache.rank(*self.args[:3], {}))
        self.assertEqual(rank.call_count, 1)

    def test_every_ranking_input_change_invalidates(self):
        changes = {
            'resume': lambda a: a.__setitem__(0, a[0] + ' Pandas'),
            'profile skills': lambda a: a[1]['skills'].append('Pandas'),
            'profile experience': lambda a: a[1].__setitem__('experience_years', 4),
            'profile education': lambda a: a[1].__setitem__('education', '硕士'),
            'location preference': lambda a: a[3].__setitem__('location', 'Singapore'),
            'experience preference': lambda a: a[3].__setitem__('experience_years', 0),
            'description': lambda a: a[2][0].__setitem__('description', 'Unrelated design Figma'),
            'title': lambda a: a[2][0].__setitem__('title', 'Designer'),
            'job skills': lambda a: a[2][0]['skills'].append('Java'),
            'job location': lambda a: a[2][0].__setitem__('location', 'Singapore'),
            'job experience': lambda a: a[2][0].__setitem__('experience_years', 10),
            'job removal': lambda a: a[2].pop(),
            'job insertion': lambda a: a[2].append(dict(a[2][0], id='3')),
            'job id': lambda a: a[2][0].__setitem__('id', 'updated'),
            'availability': lambda a: a[2][0].__setitem__('availability', 'expired'),
            'application status': lambda a: a[2][0].__setitem__('status', 'applied'),
            'application note': lambda a: a[2][0].__setitem__('note', 'Interview tomorrow'),
            'nested metadata': lambda a: a[2][0]['metadata']['tags'].append('updated'),
        }
        for name, change in changes.items():
            with self.subTest(change=name):
                cache = RankedJobsCache()
                changed = copy.deepcopy(self.args)
                change(changed)
                with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
                    cache.rank(*self.args)
                    result = cache.rank(*changed)
                self.assertEqual(result, rank_jobs(*changed))
                self.assertEqual(rank.call_count, 2)

    def test_only_last_result_is_retained(self):
        changed = copy.deepcopy(self.args)
        changed[0] += ' Pandas'
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.cache.rank(*self.args)
            self.cache.rank(*changed)
            self.cache.rank(*self.args)
        self.assertEqual(rank.call_count, 3)
        self.assertEqual(self.cache.cache_info().currsize, 1)

    def test_both_hit_and_miss_results_are_independent_deep_copies(self):
        expected = rank_jobs(*self.args)
        first = self.cache.rank(*self.args)
        first[0]['skills'].append('tampered')
        first[0]['breakdown'][0]['value'] = -1
        first[0]['metadata']['tags'].append('tampered')
        second = self.cache.rank(*self.args)
        self.assertEqual(second, expected)
        second[0]['warnings'].append('tampered')
        self.assertEqual(self.cache.rank(*self.args), expected)
        self.assertEqual(self.args[2], JOBS)

    def test_caller_input_mutation_cannot_mutate_already_returned_results(self):
        result = self.cache.rank(*self.args)
        expected = copy.deepcopy(result)
        self.args[2][0]['skills'].append('Java')
        self.args[2][0]['metadata']['tags'].append('changed')
        self.assertEqual(result, expected)
        self.assertEqual(self.cache.rank(*self.args), rank_jobs(*self.args))

    def test_failed_recomputation_keeps_previous_good_result(self):
        expected = self.cache.rank(*self.args)
        broken = copy.deepcopy(self.args)
        del broken[2][0]['description']
        with self.assertRaises(KeyError):
            self.cache.rank(*broken)
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.assertEqual(self.cache.rank(*self.args), expected)
        self.assertEqual(rank.call_count, 0)

    def test_empty_result_is_a_cacheable_result(self):
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.assertEqual(self.cache.rank(RESUME, PROFILE, []), [])
            self.assertEqual(self.cache.rank(RESUME, PROFILE, []), [])
        self.assertEqual(rank.call_count, 1)

    def test_clear_discards_result_and_resets_statistics(self):
        self.cache.rank(*self.args)
        self.cache.clear()
        info = self.cache.cache_info()
        self.assertEqual((info.hits, info.misses, info.currsize), (0, 0, 0))
        with patch('jobcompass.ranking_cache.rank_jobs', wraps=rank_jobs) as rank:
            self.cache.rank(*self.args)
        self.assertEqual(rank.call_count, 1)

    def test_parallel_identical_requests_compute_once_and_return_independent_results(self):
        workers = 6
        start = threading.Barrier(workers + 1)
        entered, release = threading.Event(), threading.Event()

        def delayed_rank(*args):
            entered.set()
            if not release.wait(3):
                raise AssertionError('Test did not release the ranking worker')
            return rank_jobs(*args)

        def request():
            start.wait(timeout=3)
            return self.cache.rank(*self.args)

        with patch('jobcompass.ranking_cache.rank_jobs', side_effect=delayed_rank) as rank:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(request) for _ in range(workers)]
                start.wait(timeout=3)
                self.assertTrue(entered.wait(3))
                release.set()
                results = [future.result(timeout=3) for future in futures]
        self.assertEqual(rank.call_count, 1)
        self.assertEqual(self.cache.cache_info().hits, workers - 1)
        results[0][0]['skills'].append('modified')
        for result in results[1:]:
            self.assertEqual(result, rank_jobs(*self.args))

    def test_non_json_input_fails_with_value_error(self):
        for args in ([None, PROFILE, JOBS], [RESUME, [], JOBS], [RESUME, PROFILE, {}],
                     [RESUME, PROFILE, JOBS, []], [RESUME, PROFILE, [object()]],
                     [RESUME, {'experience_years': float('nan')}, JOBS]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.cache.rank(*args)

    def test_ambiguous_keys_and_python_containers_are_rejected(self):
        for metadata in ({1: 'number key'}, ('tuple',), {'value': float('inf')}):
            changed = copy.deepcopy(self.args)
            changed[2][0]['metadata'] = metadata
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                self.cache.rank(*changed)

    def test_circular_data_fails_without_replacing_a_good_cache_entry(self):
        expected = self.cache.rank(*self.args)
        circular = copy.deepcopy(self.args)
        circular[1]['circular'] = circular[1]
        with self.assertRaises(ValueError):
            self.cache.rank(*circular)
        self.assertEqual(self.cache.rank(*self.args), expected)


if __name__ == '__main__':
    unittest.main()
