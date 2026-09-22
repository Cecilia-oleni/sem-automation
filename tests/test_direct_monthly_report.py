import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from sem_automation.reporting.standard.direct import (
    DirectClient, date_range, load_config, parse_tsv, reconcile, report_specs, difference_status,
)


class StandardDirectTests(unittest.TestCase):
    def test_periods(self):
        self.assertEqual(date_range('2024-02'), ('2024-02-01', '2024-02-29', 29))
        self.assertEqual(date_range(None, '2026-07-29', '2026-08-04'),
                         ('2026-07-29', '2026-08-04', 7))
        for args in [('2026-07', '2026-07-01', None),
                     (None, '2026-08-02', '2026-08-01'), ('2026-13', None, None)]:
            with self.assertRaises(ValueError):
                date_range(*args)

    def test_numeric_missing_and_identifiers(self):
        fields = ['Query', 'CampaignId', 'Clicks', 'Cost', 'AvgPageviews']
        result = parse_tsv('\ufeff' + '\t'.join(fields) + '\n=1+1\t00123\t2\t1.23\t--\n', fields)
        self.assertEqual(result[0], {'Query': '=1+1', 'CampaignId': '00123', 'Clicks': 2,
                                     'Cost': 1.23, 'AvgPageviews': '--'})
        for text in ['Clicks\n1.5\n', 'Clicks\nnan\n', 'Other\n2\n', 'Clicks\n2\textra\n']:
            with self.assertRaises(ValueError):
                parse_tsv(text, ['Clicks'])

    def test_all_goals_filter_offline_retry(self):
        session = Mock()
        session.post.side_effect = [
            Mock(status_code=201, headers={'retryIn': '1'}),
            Mock(status_code=200, headers={'RequestId': 'test'}, text='Clicks\tConversions\n1\t2.00\n'),
        ]
        client = DirectClient('test-token', load_config(), session)
        with tempfile.TemporaryDirectory() as tmp, patch('sem_automation.reporting.standard.direct.time.sleep'):
            rows = client.report('search_queries', 'SEARCH_QUERY_PERFORMANCE_REPORT',
                                 ['Clicks', 'Conversions'], '2026-07-01', '2026-07-31', Path(tmp))
            audit = (Path(tmp) / 'search_queries.request.json').read_text()
            self.assertNotIn('test-token', audit)
            self.assertTrue((Path(tmp) / 'search_queries.tsv').exists())
        self.assertEqual(rows[0]['Conversions'], 2)
        calls = session.post.call_args_list
        params = calls[0].kwargs['json']['params']
        self.assertNotIn('Goals', params)
        self.assertNotIn('AttributionModels', params)
        self.assertEqual(params['SelectionCriteria']['Filter'],
                         [{'Field': 'Clicks', 'Operator': 'GREATER_THAN', 'Values': ['0']}])
        self.assertEqual(params['ReportName'], calls[1].kwargs['json']['params']['ReportName'])

    def test_search_is_not_account_and_campaign_must_reconcile(self):
        raw = {'account': [{'Impressions': 100, 'Clicks': 10, 'Cost': 5}],
               'campaign': [{'Impressions': 100, 'Clicks': 10, 'Cost': 5}],
               'search_queries': [{'Impressions': 20, 'Clicks': 8, 'Cost': 4}]}
        self.assertTrue(any(c['status'].startswith('INFO') for c in reconcile(raw)))
        raw['campaign'][0]['Clicks'] = 9
        self.assertTrue(any(c['status'] == 'MISMATCH' for c in reconcile(raw)))
        self.assertTrue(all(c['status'] == 'PASS' for c in reconcile({k: [] for k in report_specs()})))

    def test_tolerance_requires_absolute_and_relative_limits(self):
        self.assertEqual(difference_status(1000, 1002, 'Clicks'), 'WARN: within small tolerance')
        self.assertEqual(difference_status(10, 12, 'Clicks'), 'MISMATCH')
        self.assertEqual(difference_status(100000, 100003, 'Clicks'), 'MISMATCH')
        self.assertEqual(difference_status(571.23, 571.93, 'Cost'), 'WARN: within small tolerance')
        self.assertEqual(difference_status(10, 10.7, 'Cost'), 'MISMATCH')
        self.assertEqual(difference_status(0, 1, 'Clicks'), 'MISMATCH')


if __name__ == '__main__':
    unittest.main()
