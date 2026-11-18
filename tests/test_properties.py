"""Seeded randomized invariants, reproducible without external fuzz services."""
import copy
import json
import random
import unittest

from jobcompass.matching import rank_jobs
from jobcompass.research import validate_plan


class PropertyTests(unittest.TestCase):
    def test_random_ranking_bounds_order_and_no_mutation(self):
        rng = random.Random(6181)
        vocabulary = ['Python', 'SQL', 'Git', 'Excel', 'English', 'Communication']
        for scenario in range(80):
            jobs = [dict(id=str(i), title='Data Analyst', company='Synthetic',
                         description=' '.join(rng.sample(vocabulary, rng.randint(0, 6))),
                         skills=rng.sample(vocabulary, rng.randint(0, 6)), location='', remote=False)
                    for i in range(rng.randint(0, 12))]
            profile = {'skills': rng.sample(vocabulary, rng.randint(0, 6)), 'education':'未知', 'experience_years':None}
            before = copy.deepcopy((jobs, profile))
            result = rank_jobs('Python SQL analytical course project', profile, jobs)
            with self.subTest(scenario=scenario):
                self.assertEqual((jobs, profile), before)
                self.assertEqual(len(result), len(jobs))
                self.assertTrue(all(0 <= row['score'] <= 100 for row in result))
                self.assertEqual([row['score'] for row in result], sorted((row['score'] for row in result), reverse=True))
                self.assertEqual(result, rank_jobs('Python SQL analytical course project', profile, jobs))

    def test_generated_unknown_plan_fields_are_rejected(self):
        rng = random.Random(11)
        for i in range(60):
            key = 'unknown_' + ''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(12))
            plan = {'dataset':'platform', 'analysis':'overview', key:json.dumps({'nested':i})}
            with self.subTest(field=key), self.assertRaises(ValueError):
                validate_plan(plan)
