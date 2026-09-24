# 终端输入：python -m unittest discover -s tests -p test_wordstat.py -v
import csv
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests

from sem_automation.integrations.yandex.wordstat.client import Quota, WordstatClient, file_lock, save_json
from sem_automation.materials.keywords.tables import seeds_from_table, choose_file, REVIEW_NAMES, load_final, parse_draft
from sem_automation.materials.keywords.wordstat_flow import query, organize, build_candidates, fair_select, validate_enrichment, settings


class WordstatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root/'outputs/materials/test'
        self.out.mkdir(parents=True)

    def review(self, n=3):
        path = self.out/'keywords_v1_reviewed.csv'
        with path.open('w',encoding='utf-8-sig',newline='') as h:
            w=csv.writer(h); w.writerow(['keywords','keywords_CN'])
            w.writerows((f'насос {i:03}', f'水泵{i}') for i in range(n))
        return path

    def client(self):
        return Mock(top_requests=Mock(side_effect=lambda phrase, regions:{'totalCount':'100','results':[
            {'phrase':f'{phrase} тип {j:02}', 'count':str(50-j)} for j in range(50)]}))

    def test_all_100_seeds_queried_despite_early_abundance_and_cached(self):
        self.review(100); client=self.client()
        run=query('test',root=self.root,client=client,report=lambda _:None)
        self.assertEqual(client.top_requests.call_count,100)
        self.assertEqual(json.loads((run/'status.json').read_text())['completed'],100)
        query('test',root=self.root,client=client,report=lambda _:None)
        self.assertEqual(client.top_requests.call_count,100)

    def test_resume_after_failure_and_changed_regions(self):
        self.review()
        client=Mock(top_requests=Mock(side_effect=[{},RuntimeError('offline')]))
        with self.assertRaises(RuntimeError): query('test',root=self.root,client=client,report=lambda _:None)
        client=self.client()
        query('test',root=self.root,client=client,report=lambda _:None)
        self.assertEqual(client.top_requests.call_count,2)
        query('test',root=self.root,regions=['225'],client=client,report=lambda _:None)
        self.assertEqual(client.top_requests.call_count,5)

    def test_quota_survives_restart_and_waits_rolling_hour(self):
        now=[10000.]
        def sleep(n):now[0]+=n
        path=self.root/'quota.json'
        q=Quota(path,clock=lambda:now[0],sleep=sleep,report=lambda _:None)
        for _ in range(100):q.reserve()
        self.assertLess(now[0],10101)
        q=Quota(path,clock=lambda:now[0],sleep=sleep,report=lambda _:None)
        q.reserve()
        self.assertGreaterEqual(now[0],13600)
        q.defer(80); before=now[0];q.reserve()
        self.assertGreaterEqual(now[0]-before,80)

    def test_lock_prevents_concurrent_same_job(self):
        with file_lock(self.root/'job.lock'):
            with self.assertRaises(RuntimeError):
                with file_lock(self.root/'job.lock'):pass
        with file_lock(self.root/'job.lock'):pass

    def test_transport_429_retry_and_auth_failure(self):
        (self.root/'.env').write_text('YANDEX_CLOUD_AI_STUDIO_API_KEY=test\nYANDEX_CLOUD_FOLDER_ID=test',encoding='utf-8')
        q=Mock();session=Mock()
        limited=Mock(status_code=429,headers={'Retry-After':'11'})
        ok=Mock(status_code=200);ok.json.return_value={}
        session.post.side_effect=[limited,ok]
        c=WordstatClient(self.root,session=session,quota=q)
        self.assertEqual(c.top_requests('насос',[]),{})
        q.defer.assert_called_once_with(11)
        self.assertEqual(session.post.call_args.kwargs['json']['numPhrases'],'30')
        session.post.side_effect=[Mock(status_code=403)]
        with self.assertRaisesRegex(RuntimeError,'403'):c.top_requests('насос',[])
        session.post.side_effect=requests.Timeout()
        with self.assertRaisesRegex(RuntimeError,'连续失败'):c.top_requests('насос',[])

    def test_fairness_cap_and_permutation_invariance(self):
        self.review(100); seeds=seeds_from_table(self.review(100))
        records=[{'phrase':s['keywords'],'time':1,'response':self.client().top_requests(s['keywords'],[])} for s in seeds]
        candidates=build_candidates(records,seeds)
        for row in candidates.values():row.update(relevance='high',score=80)
        selected, queues=fair_select(candidates)
        self.assertEqual(len(selected),600)
        self.assertTrue(all(len(q)==30 for q in queues.values()))
        self.assertTrue(all(s['keywords'] in selected for s in seeds))
        for seed in seeds:
            self.assertEqual(sum(k.startswith(seed['keywords']+' тип') for k in selected),5)
        random.Random(42).shuffle(records); seeds.reverse()
        other=build_candidates(records,seeds)
        for row in other.values():row.update(relevance='high',score=80)
        self.assertEqual(selected,fair_select(other)[0])

    def test_no_padding_low_relevance_and_duplicate_volume(self):
        seeds=[{'keywords':'насос','keywords_CN':'水泵'},{'keywords':'товар','keywords_CN':'产品'}]
        records=[{'phrase':'насос','time':1,'response':{'totalCount':'0','results':[{'phrase':'общий','count':'8'}]}},
                 {'phrase':'товар','time':2,'response':{'results':[{'phrase':'общий','count':'9'},{'phrase':'насос','count':'999'}]}}]
        rows=build_candidates(records,seeds)
        self.assertEqual(rows['насос']['volume'],0)
        self.assertIsNone(rows['товар']['volume'])
        self.assertEqual(rows['общий']['volume'],9)
        self.assertEqual(len(rows['общий']['sources']),2)
        for row in rows.values():row.update(relevance='low',score=0)
        self.assertEqual(len(fair_select(rows)[0]),2)

    def test_csv_bilingual_dedup_and_limit_before_network(self):
        path=self.review(601)
        with self.assertRaisesRegex(ValueError,'1–600'):query('test',root=self.root,client=Mock())
        path.write_text('keywords,keywords_CN\nнасос,水泵\nНАСОС,水泵\n',encoding='utf-8-sig')
        self.assertEqual(len(seeds_from_table(path)),1)
        path.write_text('keywords,keywords_CN\nнасос 水泵,水泵\n',encoding='utf-8-sig')
        with self.assertRaisesRegex(ValueError,'含中文'):seeds_from_table(path)

    def test_ambiguous_files_and_final_csv_aliases(self):
        self.review();(self.out/'keywords_v1_reviewed.xlsx').write_bytes(b'x')
        with self.assertRaisesRegex(ValueError,'多个'):choose_file(self.out,REVIEW_NAMES)
        final=self.out/'keywords_v2.csv'
        final.write_text('campaign,adgroup,keywords,volume,keywords_CN\n工业,水泵,насос,0,水泵\n',encoding='utf-8-sig')
        frame=load_final(self.out)
        self.assertEqual(frame.iloc[0].to_dict(),dict(Campaign='工业',AdGroup='水泵',Keyword='насос'))
        from sem_automation.materials.ads.generator import load_keyword_v2
        from sem_automation.materials.negatives.generator import load_keyword_reference
        self.assertEqual(len(load_keyword_v2('test',self.root)),1)
        text,_=load_keyword_reference('test',self.out,str(final),self.root)
        self.assertIn('насос',text)

    def test_json_contract_rejects_hallucination_and_volume(self):
        row=dict(id='a',campaign='系列',adgroup='组',keywords_CN='词',relevance='high',score=80,reason='相关')
        validate_enrichment([row],['a'],{('系列','组')})
        for bad in ([row,row],[dict(row,id='b')],[dict(row,volume=123)],[]):
            with self.assertRaises(ValueError):validate_enrichment(bad,['a'],{('系列','组')})

    def test_dry_run_and_region_defaults(self):
        self.review()
        query('test',root=self.root,dry_run=True,report=lambda _:None)
        self.assertFalse((self.out/'_internal').exists())
        self.assertEqual(settings('test',self.root)['regions'],[])
        save_json(self.root/'uploads/materials/test/wordstat.json',{'regions':['225']})
        self.assertEqual(settings('test',self.root)['regions'],['225'])
        self.assertEqual(settings('test',self.root,['all'])['regions'],[])

    def test_draft_parser_reads_only_bilingual_table(self):
        self.assertEqual(parse_draft('说明\n| keywords | keywords_CN |\n|---|---|\n| насос | 水泵 |')[0]['keywords'],'насос')
        with self.assertRaises(ValueError):parse_draft('насос 水泵')

    def test_ai_retry_does_not_repeat_queries_and_caches_batches(self):
        self.review(1); client=self.client()
        query('test',root=self.root,client=client,report=lambda _:None)
        (self.out/'project_brief.md').write_text('工业水泵',encoding='utf-8')
        calls=[]
        def ai(prompt):
            calls.append(prompt)
            if '只返回 JSON 数组，每项只有' in prompt:return [dict(campaign='工业',adgroup='水泵')]
            batch=json.loads(prompt.split('候选：\n')[1])
            if len(calls)==3:raise RuntimeError('model outage')
            return [dict(id=r['id'],campaign='工业',adgroup='水泵',keywords_CN='水泵',relevance='high',score=80,reason='相关') for r in batch]
        writer=Mock()
        with self.assertRaisesRegex(RuntimeError,'model outage'):
            organize('test',root=self.root,ai=ai,writer=writer)
        writer.assert_not_called()
        organize('test',root=self.root,ai=ai,writer=writer)
        self.assertEqual(client.top_requests.call_count,1)
        self.assertEqual(len(calls),5) # taxonomy, batch0, failed20, retry20, batch40
        self.assertEqual(len(writer.call_args.args[2]),31)

    def test_reviewed_translation_and_excluded_opaque_name(self):
        self.review(1)
        client = Mock()
        client.top_requests.return_value = {'totalCount': '1', 'associations': [{'phrase': 'opaque123', 'count': '2'}]}
        query('test', root=self.root, client=client, report=lambda _: None)
        (self.out/'project_brief.md').write_text('工业水泵', encoding='utf-8')
        def ai(prompt):
            if '只返回 JSON 数组，每项只有' in prompt:
                return [dict(campaign='工业', adgroup='水泵')]
            batch = json.loads(prompt.split('候选：\n')[1])
            return [dict(id=r['id'], campaign='工业', adgroup='水泵', keywords_CN=r['keywords'], relevance='high' if r['seed'] else 'low', score=80 if r['seed'] else 0, reason='业务相关' if r['seed'] else '无关用户名') for r in batch]
        writer = Mock()
        organize('test', root=self.root, ai=ai, writer=writer)
        delivered = writer.call_args.args[2]
        self.assertEqual(len(delivered), 1)
        self.assertRegex(delivered[0]['keywords_CN'], r'[\u3400-\u9fff]')
        audit_path = next((self.out/'_internal').rglob('audit.json'))
        audit = json.loads(audit_path.read_text('utf-8'))
        self.assertEqual(audit['candidates']['opaque123']['selection'], 'low_relevance')
        self.assertEqual(audit['candidates']['opaque123']['keywords_CN'], '已排除词：opaque123')

    def initial_pipeline_files(self):
        (self.root/'uploads/materials/test').mkdir(parents=True,exist_ok=True)
        for name in ('raw_text_local.txt','file_report.csv','project_brief.md','keyword_v1.md'):
            (self.out/name).write_text('原有结果',encoding='utf-8')

    def test_api_pipeline_handoffs_and_downstream_explicit_final(self):
        from sem_automation.materials.pipeline import PipelineRunner
        self.initial_pipeline_files();review=self.review(1)
        final=self.out/'keywords_v2.csv'
        final.write_text('campaign,adgroup,keywords\n工业,水泵,насос\n',encoding='utf-8-sig')
        def organized(*args,**kwargs):
            for ext in ('xlsx','csv'):(self.out/f'wordstat_results.{ext}').write_text('机器输出',encoding='utf-8')
            save_json(self.out/'_internal/wordstat/delivery.json',{'revision':'r1','generated_at':0})
        def negative(*args,**kwargs):
            self.assertEqual(Path(kwargs['keyword_version']),final)
            (self.out/'negative_keywords.md').write_text('否词',encoding='utf-8')
        def ads(*args,**kwargs):
            self.assertEqual(kwargs['keyword_file'],final)
            for name in ('ad_copy_results.xlsx','ad_copy_results.tsv','ad_copy_raw.md'):(self.out/name).write_text('广告',encoding='utf-8')
        with patch('sem_automation.materials.pipeline.query_wordstat') as q, patch('sem_automation.materials.pipeline.organize_wordstat',side_effect=organized), patch('sem_automation.materials.pipeline.generate_negative_keywords',side_effect=negative), patch('sem_automation.materials.pipeline.generate_ad_copy',side_effect=ads), patch.object(PipelineRunner,'_run_website_branch',return_value=True):
            result=PipelineRunner('test',project_root=self.root,input_func=lambda _:'1',output_func=lambda _:None).run()
        self.assertFalse(result['failed']);self.assertFalse(result['waiting'])
        q.assert_called_once()
        self.assertEqual(result['statuses']['ad_copy'],'completed')

    def test_updated_delivery_requires_new_human_review(self):
        from sem_automation.materials.keywords.tables import verify_final_review
        final=self.out/'keywords_v2.csv';final.write_text('reviewed')
        delivery=self.out/'_internal/wordstat/delivery.json'
        save_json(delivery,{'revision':'first','generated_at':0})
        verify_final_review(self.out,final)
        save_json(delivery,{'revision':'second','generated_at':0})
        with self.assertRaisesRegex(ValueError,'重新审核'):verify_final_review(self.out,final)
        final.write_text('new reviewed')
        verify_final_review(self.out,final)

    def test_manual_pipeline_still_waits_for_manual_search(self):
        from sem_automation.materials.pipeline import PipelineRunner
        self.initial_pipeline_files()
        (self.out/'keyword_v1_reviewed.md').write_text('насос',encoding='utf-8')
        (self.out/'wordstat_query_list.txt').write_text('насос',encoding='utf-8')
        with patch('sem_automation.materials.pipeline.query_wordstat') as q, patch.object(PipelineRunner,'_offer_independent_branch'):
            result=PipelineRunner('test',project_root=self.root,wordstat_mode='manual',input_func=lambda _:'1',output_func=lambda _:None).run()
        self.assertIn('wordstat_manual',result['waiting'])
        q.assert_not_called()


if __name__ == '__main__':unittest.main()
