import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from sem_automation.reporting.standard.metrika import MetrikaClient, comparison_period, flatten_report, hostname


class MetrikaTests(unittest.TestCase):
    def test_comparison_period(self):
        self.assertEqual(comparison_period('2026-07-01', '2026-07-31'), ('2026-06-01', '2026-06-30'))
        self.assertEqual(comparison_period('2026-07-20', '2026-07-26'), ('2026-07-13', '2026-07-19'))
        self.assertEqual(comparison_period('2026-07-01', '2026-08-31'), ('2026-04-30', '2026-06-30'))

    def test_hostname_normalization(self):
        self.assertEqual(hostname('https://RU.LINGYUAIR.COM/path'), 'ru.lingyuair.com')

    def test_missing_dimension_is_preserved_and_shape_checked(self):
        response = {'data': [{'dimensions': [None], 'metrics': [32]}]}
        self.assertEqual(flatten_report(response, ['age'], ['visits']), [{'age': None, 'age:id': None, 'visits': 32}])
        with self.assertRaises(ValueError):
            flatten_report(response, [], ['visits'])

    def client(self, responses):
        session = Mock()
        session.get.side_effect = [Mock(status_code=200, json=Mock(return_value=r)) for r in responses]
        return MetrikaClient('test-token', session)

    def config(self):
        return {'counter_id': 1, 'attribution': 'lastsign', 'filters': ''}

    def test_pagination_and_unique_total_not_sum(self):
        data = [
            {'total_rows': 2, 'totals': [3], 'sampled': False, 'data': [{'dimensions': [{'id':'a','name':'A'}], 'metrics':[2]}]},
            {'total_rows': 2, 'totals': [3], 'sampled': False, 'data': [{'dimensions': [{'id':'b','name':'B'}], 'metrics':[2]}]},
        ]
        client = self.client(data)
        with tempfile.TemporaryDirectory() as tmp:
            report = client.report('users', self.config(), '2026-07-01', '2026-07-31', ['dim'], ['users'], Path(tmp))
            self.assertEqual(report['totals']['users'], 3)
            self.assertEqual(len(report['rows']), 2)
            self.assertEqual(report['pages'][1]['offset'], 2)
            self.assertNotIn('test-token', (Path(tmp)/'users.page1.json').read_text())

    def test_sampling_is_not_silently_accepted(self):
        client = self.client([{'sampled': True, 'data': [], 'totals': [0], 'total_rows':0}])
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            client.report('test', self.config(), '2026-07-01', '2026-07-31', [], ['users'], Path(tmp))

    def test_pagination_change_fails(self):
        client = self.client([
            {'total_rows':2, 'totals':[3], 'data':[{'dimensions':[{'name':'A'}], 'metrics':[1]}]},
            {'total_rows':3, 'totals':[4], 'data':[{'dimensions':[{'name':'B'}], 'metrics':[2]}]},
        ])
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            client.report('test', self.config(), '2026-07-01', '2026-07-31', ['dim'], ['users'], Path(tmp))


if __name__ == '__main__':
    unittest.main()
