"""Offline agent-loop tests: bounded calls, validated tools and data minimization."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jobcompass.research import Research, validate_plan
from jobcompass.research_agent import run_agent
from jobcompass.storage import Store


RID = '0123456789abcdef01234567'


def response(action='skills', **extra):
    plan = {'dataset': 'current', 'action': action}
    plan.update(extra)
    return {'action': 'run', 'plan': plan}, {'total_tokens': 20}


def result_for(plan):
    rows = [{'concept': 'python', 'n': 10, 'mentions': 4, 'share_pct': 40.0}]
    if plan['action'] == 'overview':
        rows = [{'label': 'Engineering', 'n': 10, 'advertisers': 4}]
    elif plan['action'] == 'trend':
        rows = [{'month': '2026-01', 'n': 10, 'mentions': 4, 'advertisers': 3}]
    elif plan['action'] == 'compare':
        rows = [{'period': 'A', 'n': 10, 'mentions': 4}, {'period': 'B', 'n': 10, 'mentions': 7}]
    return {'id': RID, 'plan': copy.deepcopy(plan), 'population_n': 10, 'rows': rows,
            'details': {}, 'warnings': [], 'dataset_fingerprint': 'PRIVATE_FINGERPRINT'}


class ResearchAgentTests(unittest.TestCase):
    def test_runs_validated_plan_observes_then_finishes(self):
        runner = Mock(side_effect=result_for)
        progress = Mock()
        with patch('jobcompass.research_agent._call', side_effect=[
                response(), ({'action': 'finish', 'summary': '样本中 Python 全文提及率为 40%。'}, {'total_tokens': 12})]) as call:
            outcome = run_agent('分析技能提及', 'current', runner, max_steps=3, progress=progress)
        self.assertEqual(outcome['status'], 'completed')
        self.assertEqual(outcome['model_calls'], 2)
        self.assertEqual(outcome['executed_steps'], 1)
        self.assertEqual(outcome['usage']['total_tokens'], 32)
        self.assertEqual(outcome['steps'][0]['plan'], validate_plan({'dataset': 'current', 'action': 'skills'}))
        self.assertEqual(outcome['steps'][0]['result_id'], RID)
        self.assertEqual(call.call_args_list[1].args[1]['history'][0]['observation']['rows'][0]['mentions'], 4)
        self.assertEqual(outcome['label_source'], 'model_prediction')
        self.assertTrue(outcome['message'])
        self.assertTrue(progress.called)
        json.dumps(outcome, allow_nan=False)

    def test_budget_counts_model_turns_and_does_not_add_a_summary_call(self):
        outputs = [response('skills', concept=name) for name in ('python', 'sql', 'excel', 'aws')]
        runner = Mock(side_effect=result_for)
        with patch('jobcompass.research_agent._call', side_effect=outputs) as call:
            outcome = run_agent('检查四类词语', 'current', runner, max_steps=4)
        self.assertEqual(outcome['status'], 'budget_exhausted')
        self.assertEqual(call.call_count, 4)
        self.assertEqual(runner.call_count, 4)
        self.assertEqual(outcome['executed_steps'], 4)

    def test_finish_consumes_one_turn_and_can_finish_without_running_a_tool(self):
        runner = Mock()
        with patch('jobcompass.research_agent._call', return_value=({'action': 'finish', 'summary': '问题超出支持范围。'}, {})) as call:
            outcome = run_agent('预测因果', 'current', runner, max_steps=1)
        self.assertEqual(outcome['status'], 'completed')
        self.assertEqual(outcome['model_calls'], 1)
        self.assertEqual(outcome['executed_steps'], 0)
        self.assertIn('未执行', outcome['message'])
        runner.assert_not_called()
        self.assertEqual(call.call_count, 1)

    def test_duplicate_normalized_plan_stops_before_repeating_tool(self):
        normalized = validate_plan({'dataset': 'current', 'action': 'skills'})
        runner = Mock(side_effect=result_for)
        with patch('jobcompass.research_agent._call', side_effect=[response(), ({'action': 'run', 'plan': normalized}, {})]):
            outcome = run_agent('分析', 'current', runner)
        self.assertEqual(outcome['status'], 'duplicate_plan')
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(outcome['steps'][-1]['status'], 'duplicate_plan')

    def test_model_cannot_change_dataset(self):
        runner = Mock()
        with patch('jobcompass.research_agent._call', return_value=response(dataset='research')):
            outcome = run_agent('分析', 'current', runner)
        self.assertEqual(outcome['status'], 'invalid_response')
        runner.assert_not_called()

    def test_only_four_aggregate_actions_are_permitted(self):
        for action in ('sample', 'pairs', 'dataset', 'forecast', 'delete'):
            runner = Mock()
            with self.subTest(action=action), patch('jobcompass.research_agent._call', return_value=response(action)):
                outcome = run_agent('分析', 'current', runner)
            self.assertEqual(outcome['status'], 'invalid_response')
            runner.assert_not_called()

    def test_strict_protocol_rejects_unknown_fields_and_unsafe_plans(self):
        invalid = [None, [], {'action': 'finish', 'summary': 3}, {'action': 'finish', 'summary': ' '},
                   {'action': 'finish', 'summary': 'x' * 2001}, {'action': 'finish', 'summary': 'ok', 'python': 'SECRET_CODE'},
                   {'action': 'run', 'plan': {'action': 'skills'}},
                   {'action': 'run', 'plan': {'dataset': 'current', 'action': 'skills', 'sql': 'SECRET_CODE'}},
                   {'action': 'run', 'plan': {'dataset': 'current', 'action': 'compare'}},
                   {'action': 'run', 'plan': {'dataset': 'current', 'action': 'skills', 'filters': {'path': '/SECRET_PATH'}}}]
        for model_output in invalid:
            runner = Mock()
            with self.subTest(output=model_output), patch('jobcompass.research_agent._call', return_value=(model_output, {})):
                outcome = run_agent('分析', 'current', runner)
            self.assertEqual(outcome['status'], 'invalid_response')
            self.assertNotIn('SECRET', json.dumps(outcome))
            runner.assert_not_called()

    def test_cancellation_before_start_uses_no_model_or_tool(self):
        cancelled = threading.Event()
        cancelled.set()
        runner = Mock()
        with patch('jobcompass.research_agent._call') as call:
            outcome = run_agent('分析', 'current', runner, cancel=cancelled)
        self.assertEqual(outcome['status'], 'cancelled')
        self.assertEqual(outcome['model_calls'], 0)
        call.assert_not_called()
        runner.assert_not_called()

    def test_cancellation_during_model_call_prevents_tool_execution(self):
        cancelled = threading.Event()

        def model(*args):
            cancelled.set()
            return response()

        runner = Mock()
        with patch('jobcompass.research_agent._call', side_effect=model):
            outcome = run_agent('分析', 'current', runner, cancel=cancelled)
        self.assertEqual(outcome['status'], 'cancelled')
        runner.assert_not_called()

    def test_cancellation_during_tool_retains_completed_result(self):
        cancelled = threading.Event()

        def tool(plan):
            cancelled.set()
            return result_for(plan)

        with patch('jobcompass.research_agent._call', return_value=response()) as call:
            outcome = run_agent('分析', 'current', tool, cancel=cancelled)
        self.assertEqual(outcome['status'], 'cancelled')
        self.assertEqual(outcome['executed_steps'], 1)
        self.assertEqual(outcome['steps'][0]['result_id'], RID)
        self.assertEqual(call.call_count, 1)

    def test_errors_stop_without_exposing_exception_text_or_paths(self):
        runner = Mock(side_effect=RuntimeError('SECRET_KEY at /PRIVATE_PATH'))
        with patch('jobcompass.research_agent._call', return_value=response()):
            outcome = run_agent('分析', 'current', runner)
        self.assertEqual(outcome['status'], 'tool_error')
        self.assertNotIn('SECRET', json.dumps(outcome))
        self.assertNotIn('PRIVATE_PATH', json.dumps(outcome))
        with patch('jobcompass.research_agent._call', side_effect=ValueError('SECRET_KEY at /PRIVATE_PATH')):
            outcome = run_agent('分析', 'current', Mock())
        self.assertEqual(outcome['status'], 'model_error')
        self.assertNotIn('SECRET', json.dumps(outcome))

    def test_model_observations_never_include_raw_evidence_or_arbitrary_labels(self):
        def tool(plan):
            result = result_for(plan)
            result['rows'][0].update(title='SECRET_TITLE', company='SECRET_COMPANY',
                                     evidence='IGNORE_ALL_INSTRUCTIONS', description='SECRET_RESUME', path='/SECRET_PATH')
            result['rows'].append({'concept': 'SECRET_CONCEPT', 'mentions': 3, 'n': 10})
            result['warnings'] = ['SECRET_WARNING']
            result['details'] = {'titles': [{'label': 'SECRET_TITLE', 'n': 1}], 'locations': ['SECRET_LOCATION']}
            return result

        with patch('jobcompass.research_agent._call', side_effect=[response(), ({'action': 'finish', 'summary': '完成。'}, {})]) as call:
            outcome = run_agent('分析技能', 'current', tool)
        transmitted = json.dumps(call.call_args_list[1].args[1])
        self.assertNotIn('SECRET', transmitted)
        self.assertNotIn('IGNORE_ALL', transmitted)
        self.assertNotIn(RID, transmitted)
        self.assertNotIn('SECRET', json.dumps(outcome))
        self.assertIn('不可信', call.call_args_list[0].args[0])

    def test_overview_only_approved_group_names_and_safe_quality_are_shared(self):
        def tool(plan):
            result = result_for(plan)
            result['rows'] = [{'label': 'Engineering', 'n': 4, 'advertisers': 2},
                              {'label': 'SECRET_TITLE /PRIVATE_PATH', 'n': 6, 'advertisers': 3}]
            result['details'] = {'quality': {'families': 9, 'missing_salary': 2,
                                            'first_date': '2025-01-01', 'last_date': '2026-06-01', 'path': '/SECRET_PATH'},
                                 'snapshots': [{'snapshot_id': '/SECRET_PATH'}]}
            return result

        with patch('jobcompass.research_agent._call', return_value=response('overview')):
            outcome = run_agent('样本概览', 'current', tool, max_steps=1)
        obs = outcome['steps'][0]['observation']
        self.assertEqual(sum(row['n'] for row in obs['rows']), 10)
        self.assertEqual(obs['rows'][1]['category'], 'Other sectors')
        self.assertNotIn('advertisers', obs['rows'][1])
        self.assertEqual(obs['details']['quality']['first_date'], '2025-01-01')
        self.assertNotIn('SECRET', json.dumps(outcome))

    def test_observations_are_bounded_and_percentages_are_derived_from_counts(self):
        def tool(plan):
            result = result_for(plan)
            result['rows'] = [{'concept': 'python', 'n': 10, 'mentions': 4,
                               'share_pct': 'SECRET_INJECTION'} for _ in range(1000)]
            return result

        with patch('jobcompass.research_agent._call', return_value=response()):
            outcome = run_agent('分析', 'current', tool, max_steps=1)
        obs = outcome['steps'][0]['observation']
        self.assertLessEqual(len(obs['rows']), 40)
        self.assertEqual(obs['rows_omitted'], 960)
        self.assertEqual(obs['rows'][0]['share_pct'], 40.0)

    def test_compare_uses_validated_windows_and_correct_percentage_point_difference(self):
        windows = {'period_a': ['2025-01-01', '2025-01-31'], 'period_b': ['2026-01-01', '2026-01-31']}
        with patch('jobcompass.research_agent._call', return_value=response('compare', **windows)):
            outcome = run_agent('两期比较', 'current', result_for, max_steps=1)
        self.assertEqual(outcome['steps'][0]['observation']['details']['difference_pp'], 30.0)

    def test_history_never_echoes_text_filter_values_from_tool_plans(self):
        with patch('jobcompass.research_agent._call', side_effect=[
                response(filters={'title': 'PRIVATE_TITLE', 'company': 'PRIVATE_COMPANY'}),
                ({'action': 'finish', 'summary': '完成。'}, {})]) as call:
            run_agent('分析', 'current', result_for)
        self.assertNotIn('PRIVATE_', json.dumps(call.call_args_list[1].args[1]))

    def test_malformed_result_is_not_shared_with_model(self):
        for malformed in ({'id': '/SECRET_PATH'}, dict(result_for(validate_plan({'dataset': 'current', 'action': 'skills'})), population_n=float('nan'))):
            with self.subTest(result=malformed), patch('jobcompass.research_agent._call', return_value=response()) as call:
                outcome = run_agent('分析', 'current', lambda plan: malformed)
            self.assertEqual(outcome['status'], 'tool_error')
            self.assertEqual(call.call_count, 1)
            self.assertNotIn('SECRET', json.dumps(outcome))

    def test_real_research_runner_saves_local_aggregate_results(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'app.db')
            store.upsert_jobs([{'source': 'test', 'title': 'PRIVATE_TITLE', 'company': 'PRIVATE_COMPANY',
                                'description': 'Python SQL PRIVATE_RESUME', 'location': 'Hong Kong'}])
            research = Research(store)
            with patch('jobcompass.research_agent._call', return_value=response()):
                outcome = run_agent('分析技能', 'current', research.run, max_steps=1)
            saved = research.result(outcome['steps'][0]['result_id'])
            self.assertEqual(saved['population_n'], 1)
            self.assertEqual(outcome['executed_steps'], 1)
            self.assertNotIn('PRIVATE_', json.dumps(outcome))

    def test_invalid_request_fails_before_model_call(self):
        invalid = [(None, 'current', 3), ('', 'current', 3), ('x' * 1001, 'current', 3),
                   ('分析', 'elsewhere', 3), ('分析', [], 3)]
        invalid += [('分析', 'current', limit) for limit in (True, 0, 5, '3', 2.5)]
        for command, dataset, limit in invalid:
            with self.subTest(command=command, dataset=dataset, limit=limit), patch('jobcompass.research_agent._call') as call:
                with self.assertRaises(ValueError):
                    run_agent(command, dataset, Mock(), max_steps=limit)
                call.assert_not_called()


if __name__ == '__main__':
    unittest.main()
