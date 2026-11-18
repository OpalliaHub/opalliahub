"""Behavior tests for corpus-based, prerequisite-aware learning plans."""
import copy
import json
import unittest

from jobcompass.learning import LearningPlanner, PrerequisiteGraph, build_learning_plan


def job(jid, skills, title='Data Analyst', **overrides):
    result = {'id': jid, 'title': title, 'company': 'Example Ltd',
              'source': 'JobsDB', 'description': '', 'skills': skills, 'is_demo': False}
    result.update(overrides)
    return result


class LearningPlanTests(unittest.TestCase):
    def test_frequency_counts_distinct_jobs_and_normalizes_resume_aliases(self):
        jobs = [job('1', ['Python', 'python', 'SQL', 'mysql']),
                job('1', ['Java']), job('2', ['Python']), job('3', [])]
        result = build_learning_plan(jobs, {'skills': ['postgresql']})
        rows = {row['skill']: row for row in result['skills']}
        self.assertEqual(rows['Python']['count'], 2)
        self.assertEqual(rows['Python']['share_pct'], 66.67)
        self.assertEqual(rows['SQL']['count'], 1)
        self.assertTrue(rows['SQL']['already_known'])
        self.assertNotIn('Java', rows)
        self.assertEqual(result['metrics']['duplicate_jobs'], 1)
        self.assertEqual(result['metrics']['analyzed_jobs'], 3)
        self.assertEqual(result['metrics']['jobs_with_skills'], 2)

    def test_mixed_corpus_excludes_demo_even_when_only_demo_matches_target(self):
        jobs = [job('live', ['SQL'], title='Accountant'),
                job('demo', ['Python'], title='Developer', is_demo=True)]
        result = build_learning_plan(jobs, {}, target='developer')
        self.assertEqual(result['skills'], [])
        self.assertEqual(result['metrics']['excluded_demo_jobs'], 1)
        self.assertEqual(result['metrics']['analyzed_jobs'], 0)
        self.assertFalse(result['metrics']['demo_fallback'])

    def test_all_demo_corpus_is_explicitly_labeled(self):
        result = build_learning_plan([job('demo', ['Python'], is_demo=1)], {})
        self.assertTrue(result['metrics']['demo_fallback'])
        self.assertEqual(result['metrics']['data_mode'], 'demo')
        self.assertIn('演示', result['summary'])
        self.assertEqual(result['metrics']['excluded_demo_jobs'], 0)

    def test_expired_records_are_excluded_without_resurrecting_stale_duplicates(self):
        jobs = [job('1', ['Python'], availability='expired'),
                job('1', ['Python'], availability='active'), job('2', ['SQL'])]
        result = build_learning_plan(jobs, {})
        self.assertEqual(result['metrics']['excluded_expired_jobs'], 1)
        self.assertEqual(result['metrics']['duplicate_jobs'], 1)
        self.assertEqual(result['metrics']['analyzed_jobs'], 1)
        self.assertEqual([row['skill'] for row in result['skills']], ['SQL'])

    def test_expired_real_jobs_do_not_trigger_a_demo_fallback(self):
        result = build_learning_plan([job('1', ['SQL'], availability='expired'),
                                      job('2', ['Python'], is_demo=True)], {})
        self.assertFalse(result['metrics']['demo_fallback'])
        self.assertEqual(result['skills'], [])

    def test_title_filter_is_case_insensitive_literal_substring(self):
        jobs = [job('1', ['Python'], title='Senior DATA Analyst'),
                job('2', ['SQL'], title='Developer', description='data analyst'),
                job('3', ['Java'], title='[Data] Engineer')]
        result = build_learning_plan(jobs, {}, target=' data analyst ')
        self.assertEqual(result['metrics']['analyzed_jobs'], 1)
        self.assertEqual(result['skills'][0]['example_jobs'][0]['id'], '1')
        self.assertEqual(build_learning_plan(jobs, {}, target='[Data]')['skills'][0]['skill'], 'Java')

    def test_missing_skills_are_extracted_from_job_text(self):
        result = build_learning_plan([job('1', [], description='Use pandas and Python.')], {})
        self.assertEqual({s['skill'] for s in result['skills']}, {'Python', 'Pandas'})

    def test_prerequisite_order_is_recursive_and_known_skills_are_skipped(self):
        result = build_learning_plan([job('1', ['PyTorch'])], {'skills': ['python', 'SQL']})
        order = result['learning_order']
        self.assertNotIn('Python', order)
        self.assertEqual(order[-1], 'PyTorch')
        self.assertLess(order.index('Statistics'), order.index('Machine Learning'))
        self.assertLess(order.index('NumPy'), order.index('Machine Learning'))
        self.assertLess(order.index('Machine Learning'), order.index('PyTorch'))
        self.assertIn('Python', result['skills'][0]['prerequisites'])
        self.assertEqual(result['skills'][0]['learning_order'], order)

    def test_known_target_requires_no_learning_steps(self):
        result = build_learning_plan([job('1', ['PyTorch'])], {'skills': ['pytorch']})
        self.assertTrue(result['skills'][0]['already_known'])
        self.assertEqual(result['skills'][0]['learning_order'], [])
        self.assertEqual(result['learning_order'], [])

    def test_top_skill_limit_and_ties_are_deterministic(self):
        jobs = [job('1', ['SQL', 'Python', 'Git']), job('2', ['Python'])]
        result = build_learning_plan(jobs, {}, limit=2)
        self.assertEqual([s['skill'] for s in result['skills']], ['Python', 'Git'])
        self.assertEqual(result['metrics']['distinct_skills'], 3)
        self.assertEqual(result['metrics']['returned_skills'], 2)
        self.assertNotIn('SQL', result['learning_order'])

    def test_examples_are_bounded_and_learning_steps_are_unique(self):
        jobs = [job(str(i), ['Pandas', 'NumPy']) for i in range(6)]
        result = build_learning_plan(jobs, {})
        self.assertEqual(len(result['skills'][0]['example_jobs']), 3)
        self.assertEqual(result['learning_order'].count('Python'), 1)
        for skill in ('Pandas', 'NumPy'):
            self.assertLess(result['learning_order'].index('Python'), result['learning_order'].index(skill))

    def test_unknown_skills_remain_visible_without_invented_prerequisites(self):
        result = build_learning_plan([job('1', ['Rust', 'rust'])], {'skills': ['RUST']})
        self.assertEqual(len(result['skills']), 1)
        self.assertEqual(result['skills'][0]['count'], 1)
        self.assertTrue(result['skills'][0]['already_known'])
        self.assertEqual(result['skills'][0]['prerequisites'], [])

    def test_empty_corpus_is_json_serializable(self):
        result = build_learning_plan([], {})
        self.assertEqual(result['skills'], [])
        self.assertEqual(result['learning_order'], [])
        self.assertEqual(result['metrics']['data_mode'], 'empty')
        self.assertEqual(result['metrics']['analyzed_jobs'], 0)
        json.dumps(result, ensure_ascii=False, allow_nan=False)

    def test_inputs_are_not_mutated_and_missing_ids_have_stable_identity(self):
        jobs = [job('', ['Python']), job('', ['Python'])]
        profile = {'skills': ['SQL']}
        before = copy.deepcopy((jobs, profile))
        result = LearningPlanner().build(jobs, profile)
        self.assertEqual((jobs, profile), before)
        self.assertEqual(result['metrics']['analyzed_jobs'], 1)
        self.assertTrue(result['skills'][0]['example_jobs'][0]['id'])

    def test_invalid_input_is_rejected_instead_of_silently_miscounted(self):
        bad_calls = [({'oops': 1}, {}), ([None], {}), ([], []),
                     ([job('1', 'Python')], {}), ([], {'skills': 'Python'}),
                     ([job('1', ['Python', 12])], {}), ([job('1', [], title=None)], {}),
                     ([job('1', [], is_demo='false')], {})]
        for jobs, profile in bad_calls:
            with self.subTest(jobs=jobs, profile=profile):
                with self.assertRaises(ValueError):
                    build_learning_plan(jobs, profile)
        for limit in (True, 0, -1, 21, 1.5, '3'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                build_learning_plan([], {}, limit=limit)
        for target in (None, 42, 'x' * 101):
            with self.subTest(target=target), self.assertRaises(ValueError):
                build_learning_plan([], {}, target=target)

    def test_scope_is_explained_without_recasting_frequency_as_employer_requirements(self):
        result = build_learning_plan([job('1', ['Pandas'])], {})
        self.assertEqual(result['metrics']['prerequisite_source'], 'authored_learning_suggestions')
        self.assertIn('样本', result['summary'])
        self.assertIn('市场', result['metrics']['limitations'])
        self.assertIn('雇主', result['metrics']['limitations'])


class PrerequisiteGraphTests(unittest.TestCase):
    def test_recursive_diamond_graph_and_cache_return_immutable_results(self):
        graph = PrerequisiteGraph({'D': ('B', 'C'), 'B': ('A',), 'C': ('A',)})
        before = graph.prerequisites.cache_info().hits
        result = graph.prerequisites('D')
        self.assertEqual(result, ('A', 'B', 'C'))
        self.assertIsInstance(result, tuple)
        self.assertIs(graph.prerequisites('D'), result)
        self.assertGreater(graph.prerequisites.cache_info().hits, before)

    def test_cycle_and_self_cycle_are_rejected_with_a_useful_error(self):
        for edges in ({'A': ['B'], 'B': ['A']}, {'A': ['A']}):
            with self.subTest(edges=edges), self.assertRaisesRegex(ValueError, 'cycle|循环'):
                PrerequisiteGraph(edges)

    def test_graph_copies_caller_data_and_unknown_nodes_are_terminal(self):
        edges = {'C': ['B'], 'B': ['A']}
        graph = PrerequisiteGraph(edges)
        edges['B'].append('C')
        self.assertEqual(graph.prerequisites('C'), ('A', 'B'))
        self.assertEqual(graph.prerequisites('Unlisted skill'), ())

    def test_custom_graph_is_used_by_planner(self):
        graph = PrerequisiteGraph({'Rust': ('Programming fundamentals',)})
        result = LearningPlanner(graph).build([job('1', ['Rust'])], {})
        self.assertEqual(result['learning_order'], ['Programming fundamentals', 'Rust'])


if __name__ == '__main__':
    unittest.main()
