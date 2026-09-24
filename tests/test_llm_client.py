"""Regression checks for bounded reasoning in the shared production client."""
import os
import unittest
from unittest.mock import patch, Mock
from sem_automation.ai.llm_client import call_openrouter


class ReasoningBudgetTests(unittest.TestCase):
    def test_budget_is_sent_without_changing_output_allowance(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'result'}, 'finish_reason': 'stop'}]}
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test', 'OPENROUTER_REASONING_MAX_TOKENS': '2048'}):
            with patch('sem_automation.ai.llm_client.requests.post', return_value=response) as post:
                call_openrouter('prompt', model='test-model', max_tokens=6500)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['reasoning'], {'max_tokens': 2048})
        self.assertEqual(payload['max_tokens'], 6500)

    def test_invalid_budget_fails_before_network(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test', 'OPENROUTER_REASONING_MAX_TOKENS': '6500'}):
            with patch('sem_automation.ai.llm_client.requests.post') as post:
                with self.assertRaises(ValueError):
                    call_openrouter('prompt', model='test-model', max_tokens=6500)
                post.assert_not_called()

    def test_unset_budget_preserves_existing_behavior(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': 'result'}, 'finish_reason': 'stop'}]}
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test', 'OPENROUTER_REASONING_MAX_TOKENS': ''}):
            with patch('sem_automation.ai.llm_client.requests.post', return_value=response) as post:
                call_openrouter('prompt', model='test-model', max_tokens=6500)
        self.assertNotIn('reasoning', post.call_args.kwargs['json'])