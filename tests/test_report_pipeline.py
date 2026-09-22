import copy
import unittest
from sem_automation.reporting.common.dates import PROJECT_ROOT
from sem_automation.reporting.standard.pipeline import load_client, validate_datasets, validate_layout, validate_enrichment


class ReportPipelineTests(unittest.TestCase):
    def setUp(self):
        self.client,self.dc,self.mc,self.layout=load_client(PROJECT_ROOT/'config/clients/lingyu.json')
        self.d={'schema_version':1,'meta':{**self.dc,'date_from':'2026-07-01','date_to':'2026-07-31'},
                'raw':{'account':[{'Impressions':1000,'Clicks':100,'Cost':500}],
                       'campaign':[{'Impressions':1000,'Clicks':100,'Cost':500}], 'search_queries':[]}}
        self.m={'schema':'metrika_monthly_v1','meta':{**self.mc,'date_from':'2026-07-01','date_to':'2026-07-31',
                'counter':{'site':self.mc['expected_site']}},'goals':[{'id':x} for x in self.mc['goal_ids']], 'reports':{}}

    def validate(self):
        validate_datasets(self.d,self.m,self.dc,self.mc,'2026-07-01','2026-07-31')

    def test_same_client_same_period(self):
        self.validate()

    def test_no_mixing_monthly_data_into_week(self):
        with self.assertRaisesRegex(ValueError,'日期'):
            validate_datasets(self.d,self.m,self.dc,self.mc,'2026-07-01','2026-07-07')

    def test_no_cross_client_data(self):
        self.d['meta']['client_login']='different-client'
        with self.assertRaisesRegex(ValueError,'client_login'):self.validate()
        self.d['meta']['client_login']=self.dc['client_login']
        self.m['meta']['counter_id']=105091790
        with self.assertRaisesRegex(ValueError,'计数器'):self.validate()

    def test_changed_scope_requires_refetch(self):
        self.m['meta']['filters']="ym:s:trafficSource=='ad'"
        with self.assertRaisesRegex(ValueError,'filters'):self.validate()

    def test_selected_goal_attribution_must_match(self):
        self.dc.update(goal_id='123',attribution_model='LC')
        self.d['meta'].update(goal_id='123',attribution_model='AUTO')
        with self.assertRaisesRegex(ValueError,'attribution_model'):self.validate()

    def test_large_discrepancy_blocks_formal_report(self):
        self.d['raw']['campaign'][0]['Cost']=510
        with self.assertRaisesRegex(ValueError,'容差'):self.validate()

    def test_small_discrepancy_permitted(self):
        self.d['raw']['campaign'][0]['Cost']=500.5
        self.validate()

    def test_no_automatic_reuse_of_foreign_goals(self):
        self.m['goals'][0]['id']='999'
        with self.assertRaisesRegex(ValueError,'目标列表'):self.validate()

    def test_chart_and_field_configuration(self):
        self.layout['charts']['devices']['type']='pie'
        self.layout['charts']['traffic']['type']='line'
        self.layout['direct_metrics']=self.layout['direct_metrics'][:4]
        validate_layout(self.layout)
        self.layout['charts']['traffic']['type']='pie'
        with self.assertRaisesRegex(ValueError,'类型'):validate_layout(self.layout)

    def test_another_client_needs_no_code_branch(self):
        dc,mc=copy.deepcopy(self.dc),copy.deepcopy(self.mc)
        dc['client_login']='second-test-client';dc['client_slug']='second'
        mc['counter_id']=123456;mc['expected_site']='second.example';mc['client_slug']='second'
        self.d['meta'].update(dc);self.m['meta'].update(mc);self.m['meta']['counter']['site']='second.example'
        validate_datasets(self.d,self.m,dc,mc,'2026-07-01','2026-07-31')

    def test_requires_correct_previous_period(self):
        self.d['raw']['daily']=[{'Date':'2026-07-01','Impressions':1000,'Clicks':100,'Cost':500}]
        self.d['raw']['previous_account']=[]
        self.d['meta']['comparison_period']={'date_from':'2026-06-01','date_to':'2026-06-30'}
        self.m['reports']={key:{'date_from':'2026-06-01','date_to':'2026-06-30'} for key in ('previous_summary','previous_pageviews_hits')}
        validate_enrichment(self.d,self.m,'2026-07-01','2026-07-31',self.dc)
        self.m['reports']['previous_summary']['date_from']='2026-05-31'
        with self.assertRaisesRegex(ValueError,'对比周期'):validate_enrichment(self.d,self.m,'2026-07-01','2026-07-31',self.dc)


if __name__=='__main__':unittest.main()
