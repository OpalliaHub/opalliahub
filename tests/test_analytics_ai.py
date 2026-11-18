"""Typed AI instructions execute automatically, without code or raw-data prompts."""
import copy
import json
import unittest
from unittest.mock import Mock, patch

from jobcompass.analytics_ai import compile_and_run
from jobcompass.olap import validate_query


def model_response(**changes):
    value = {'query': {'dataset': 'current', 'dimensions': ['month'], 'measure': 'ads'},
             'chart': {'type': 'line', 'title': 'Monthly advertisements'},
             'explanation': '按来源标示月份统计样本广告。'}
    value.update(changes)
    return value, {'total_tokens': 42}


def cube_result(query):
    return {'query': copy.deepcopy(query), 'rows': [{'month': '2026-01', 'ads': 8, 'employers': 3,
            'mentions': 2, 'share_pct': 25.0, 'value': 8}],
            'totals': {'ads': 8, 'employers': 3, 'mentions': 2, 'share_pct': 25.0},
            'metadata': {'fingerprint': 'local-fingerprint', 'warnings': []}, 'pivot': None}


class AnalyticsAITests(unittest.TestCase):
    def test_valid_instruction_is_validated_then_executed_without_confirmation(self):
        olap = Mock()
        olap.run.side_effect = cube_result
        with patch('jobcompass.analytics_ai._call', return_value=model_response()) as call:
            result = compile_and_run('按月统计广告数并画图', 'current', olap)
        olap.run.assert_called_once_with(validate_query(model_response()[0]['query']))
        self.assertEqual(result['chart']['type'], 'line')
        self.assertEqual(result['totals']['ads'], 8)
        self.assertEqual(result['instruction']['label_source'], 'model_prediction')
        self.assertEqual(result['instruction']['query'], result['query'])
        self.assertEqual(call.call_count, 1)
        self.assertTrue(result['message'])

    def test_dataset_is_fixed_and_invalid_instructions_never_execute(self):
        invalid = [
            {'query': {'dataset': 'research', 'dimensions': ['month'], 'measure': 'ads'}},
            {'query': {'dataset': 'current', 'dimensions': ['month'], 'measure': 'ads', 'sql': 'DROP TABLE ads'}},
            {'query': {'dataset': 'current', 'dimensions': ['company'], 'measure': 'ads'}},
            {'query': {'dimensions': ['month'], 'measure': 'ads'}},
            {'chart': {'type': 'line', 'title': 'x', 'javascript': 'SECRET_CODE'}},
            {'chart': {'type': 'pie', 'title': 'x'}},
            {'chart': {'type': 'bar', 'title': ''}},
            {'chart': {'type': 'bar', 'title': 'x' * 161}},
            {'explanation': ['unsafe']},
        ]
        for changes in invalid:
            olap = Mock()
            with self.subTest(changes=changes), patch('jobcompass.analytics_ai._call', return_value=model_response(**changes)):
                with self.assertRaises(ValueError):
                    compile_and_run('分析', 'current', olap)
            olap.run.assert_not_called()

    def test_heatmap_requires_two_dimensions_and_line_requires_exactly_one_temporal_dimension(self):
        for dims, chart_type in [(['month'], 'heatmap'), (['sector'], 'line'), (['month', 'quarter'], 'line'),
                                 (['sector', 'location'], 'line')]:
            with self.subTest(dims=dims, chart=chart_type), patch('jobcompass.analytics_ai._call', return_value=model_response(
                    query={'dataset': 'current', 'dimensions': dims, 'measure': 'ads'}, chart={'type': chart_type, 'title': 'x'})):
                with self.assertRaises(ValueError):
                    compile_and_run('分析', 'current', Mock())

    def test_category_comparison_line_normalizes_time_first_and_preserves_scope(self):
        olap = Mock()
        olap.run.side_effect = cube_result
        query = {'dataset': 'current', 'dimensions': ['sector', 'quarter'], 'measure': 'share_pct',
                 'concept': 'python', 'filters': {'start': '2025-01-01'}, 'exact_filters': {'location': 'Hong Kong'}}
        with patch('jobcompass.analytics_ai._call', return_value=model_response(
                query=query, chart={'type': 'line', 'title': '不同职业类别的季度提及率'})):
            result = compile_and_run('比较不同职业类别的季度 Python 提及率，画多条折线', 'current', olap)
        self.assertEqual(result['query']['dimensions'], ['quarter', 'sector'])
        self.assertEqual(result['query']['filters'], query['filters'])
        self.assertEqual(result['query']['exact_filters'], query['exact_filters'])
        self.assertEqual(result['query']['concept'], 'python')
        self.assertEqual(result['query']['measure'], 'share_pct')
        self.assertEqual(query['dimensions'], ['sector', 'quarter'])
        self.assertEqual(result['chart']['type'], 'line')
        self.assertEqual(olap.run.call_count, 1)

    def test_valid_heatmap_instruction_executes(self):
        olap = Mock()
        olap.run.side_effect = cube_result
        with patch('jobcompass.analytics_ai._call', return_value=model_response(
                query={'dataset': 'current', 'dimensions': ['month', 'sector'], 'measure': 'share_pct'},
                chart={'type': 'heatmap', 'title': '样本提及率'})):
            result = compile_and_run('按月份与类别分析', 'current', olap)
        self.assertEqual(result['query']['dimensions'], ['month', 'sector'])
        self.assertEqual(result['chart']['type'], 'heatmap')

    def test_followup_context_shares_only_safe_query_structure_and_numeric_totals(self):
        previous = {'query': {'dataset': 'current', 'dimensions': ['sector'], 'measure': 'ads',
                    'filters': {'title': 'PRIVATE_TITLE', 'company': 'PRIVATE_COMPANY', 'start': '2026-01-01'},
                    'exact_filters': {'location': 'PRIVATE_LOCATION'}},
                    'totals': {'ads': 8, 'employers': 3, 'mentions': 2, 'share_pct': 25.0,
                               'description': 'PRIVATE_DESCRIPTION', 'path': '/PRIVATE_PATH'}}
        olap = Mock()
        olap.run.side_effect = cube_result
        with patch('jobcompass.analytics_ai._call', return_value=model_response()) as call:
            compile_and_run('改成按月统计', 'current', olap, context=previous)
        payload = call.call_args.args[1]
        self.assertNotIn('PRIVATE_', json.dumps(payload))
        self.assertIn('2026-01-01', json.dumps(payload))
        self.assertIn('不可信', call.call_args.args[0])
        self.assertEqual(payload['context']['totals']['ads'], 8)

    def test_plain_previous_query_is_accepted(self):
        olap = Mock()
        olap.run.side_effect = cube_result
        previous = validate_query({'dataset': 'current', 'dimensions': ['sector']})
        with patch('jobcompass.analytics_ai._call', return_value=model_response()) as call:
            compile_and_run('改成按月', 'current', olap, context=previous)
        self.assertEqual(call.call_args.args[1]['context']['query']['dimensions'], ['sector'])

    def test_omitted_filters_preserve_private_previous_cohort_locally(self):
        previous = {'dataset': 'current', 'filters': {'title': 'PRIVATE_TITLE'},
                    'exact_filters': {'location': 'PRIVATE_LOCATION'}}
        olap = Mock()
        olap.run.side_effect = cube_result
        with patch('jobcompass.analytics_ai._call', return_value=model_response()) as call:
            result = compile_and_run('改为按月', 'current', olap, context=previous)
        self.assertEqual(result['query']['filters'], previous['filters'])
        self.assertEqual(result['query']['exact_filters'], previous['exact_filters'])
        self.assertNotIn('PRIVATE_', json.dumps(call.call_args.args[1]))

    def test_explicit_empty_filters_clear_previous_cohort(self):
        previous = {'dataset': 'current', 'filters': {'title': 'Developer'}, 'exact_filters': {'sector': 'Engineering'}}
        olap = Mock()
        olap.run.side_effect = cube_result
        value, usage = model_response()
        value['query'].update(filters={}, exact_filters={})
        with patch('jobcompass.analytics_ai._call', return_value=(value, usage)):
            result = compile_and_run('取消筛选，查看全部', 'current', olap, context=previous)
        self.assertEqual(result['query']['filters'], {})
        self.assertEqual(result['query']['exact_filters'], {})

    def test_engine_failure_is_not_reexecuted_or_summarized_by_model(self):
        olap = Mock()
        olap.run.side_effect = ValueError('Dataset unavailable')
        with patch('jobcompass.analytics_ai._call', return_value=model_response()) as call:
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                compile_and_run('分析', 'current', olap)
        self.assertEqual(olap.run.call_count, 1)
        self.assertEqual(call.call_count, 1)

    def test_raw_result_rows_are_not_accepted_as_followup_context(self):
        context = {'query': {'dataset': 'current'}, 'rows': [{'title': 'PRIVATE_TITLE'}]}
        with patch('jobcompass.analytics_ai._call') as call, self.assertRaises(ValueError):
            compile_and_run('分析', 'current', Mock(), context=context)
        call.assert_not_called()

    def test_model_response_unknown_fields_are_rejected(self):
        value, usage = model_response()
        value['python'] = 'print(1)'
        olap = Mock()
        with patch('jobcompass.analytics_ai._call', return_value=(value, usage)), self.assertRaises(ValueError):
            compile_and_run('分析', 'current', olap)
        olap.run.assert_not_called()

    def test_unsupported_intent_is_refused_without_substituting_an_analysis(self):
        olap = Mock()
        with patch('jobcompass.analytics_ai._call', return_value=model_response(
                query=None, chart=None, explanation='当前指标不支持工资标准化或因果推断。')):
            with self.assertRaisesRegex(ValueError, '不支持'):
                compile_and_run('分析工资的因果影响', 'current', olap)
        olap.run.assert_not_called()

    def test_invalid_command_or_dataset_fails_before_model_call(self):
        for command, dataset in [('', 'current'), (None, 'current'), ('x' * 1501, 'current'), ('分析', 'other')]:
            with self.subTest(command=command, dataset=dataset), patch('jobcompass.analytics_ai._call') as call:
                with self.assertRaises(ValueError):
                    compile_and_run(command, dataset, Mock())
                call.assert_not_called()

    def test_empty_aggregate_context_retains_null_not_false_zero_rate(self):
        olap = Mock()
        olap.run.side_effect = cube_result
        context = {'query': {'dataset': 'current'}, 'totals': {'ads': 0, 'employers': 0, 'mentions': 0, 'share_pct': None}}
        with patch('jobcompass.analytics_ai._call', return_value=model_response()) as call:
            compile_and_run('分析', 'current', olap, context=context)
        self.assertIsNone(call.call_args.args[1]['context']['totals']['share_pct'])


if __name__ == '__main__':
    unittest.main()
