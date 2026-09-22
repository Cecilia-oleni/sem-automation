"""Run: python -m unittest discover -s tests -v (offline)."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sem_automation.reporting.yutong.history import periods, month_key, blocks, require_periods, destination
from sem_automation.reporting.yutong.sync import sync
from sem_automation.core.runs import digest, write_json
from sem_automation.cli.main import main

class PeriodTests(unittest.TestCase):
    def test_september_october_january(self):
        for month,previous,year_ago,length in [('2026-09','2026-08','2025-09',9),('2026-10','2026-09','2025-10',10),('2027-01','2026-12','2026-01',1)]:
            p=periods(month)
            self.assertEqual((p['previous'],p['yearAgo'],len(p['ytd'])),(previous,year_ago,length))
        self.assertEqual(month_key('2026.10'),'2026-10')
        with self.assertRaises(ValueError):month_key(2026.1)

    def test_dynamic_rows_duplicates_and_missing(self):
        rows=[[None]*8 for _ in range(1500)]
        rows += [['2026-08'],['国家','展示合计','点击合计','消耗合计','消耗合计人民币','线索'],['俄罗斯',10,2,3,21.9,1],['合计',10,2,3,21.9,1]]
        history=blocks(rows,['俄罗斯'])
        self.assertEqual(history['2026-08']['row_numbers']['俄罗斯'],1503)
        self.assertEqual(destination(history,'2026-08',len(rows)),1501)
        self.assertEqual(destination(history,'2026-09',len(rows)),1508)
        with self.assertRaisesRegex(ValueError,'重复月份'):blocks(rows+rows[-4:],['俄罗斯'])
        with self.assertRaisesRegex(ValueError,'2026-07'):require_periods(history,['2026-07'],'fixture')

    def test_dry_run_never_connects_or_writes(self):
        with patch('socket.socket',side_effect=AssertionError('network forbidden')), patch('pathlib.Path.mkdir',side_effect=AssertionError('writes forbidden')), patch('pathlib.Path.write_text',side_effect=AssertionError('writes forbidden')):
            self.assertEqual(main(['materials','run','--project','dry-run-new-project','--dry-run']),0)

class SyncTests(unittest.TestCase):
    def fixture(self,root):
        run=root/'runs/test';entries=[]
        for i in range(2):
            source=root/f'history{i}.xlsx';source.write_bytes(f'old{i}'.encode())
            candidate=run/'history_candidates'/f'next{i}.xlsx';candidate.parent.mkdir(parents=True,exist_ok=True);candidate.write_bytes(f'new{i}'.encode())
            entries.append({'source':str(source),'source_sha256':digest(source),'candidate':str(candidate),'candidate_sha256':digest(candidate)})
        manifest=run/'_internal/manifest.json'
        write_json(manifest,{'schema':'yutong_sync_v1','status':'completed','client':'yutong','month':'2026-08','run':str(run),'entries':entries})
        write_json(run/'_internal/resolved_config.json',{'client':'yutong','reportMonth':'2026-08','paths':{'countryHistory':entries[0]['source'],'ytdHistory':entries[1]['source']}})
        return manifest,entries

    def test_success_and_source_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,entries=self.fixture(Path(tmp))
            backup=sync(manifest)
            self.assertEqual(Path(entries[0]['source']).read_bytes(),b'new0')
            self.assertEqual(len(list(backup.glob('*.xlsx'))),2)
            with self.assertRaisesRegex(ValueError,'原表已变化'):sync(manifest)

    def test_tampered_candidate_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest,entries=self.fixture(Path(tmp))
            Path(entries[0]['candidate']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'候选文件已变化'):sync(manifest)
            self.assertEqual(Path(entries[0]['source']).read_bytes(),b'old0')

    def test_locked_second_source_rolls_back_first(self):
        import os
        original=os.replace
        with tempfile.TemporaryDirectory() as tmp:
            manifest,entries=self.fixture(Path(tmp))
            def replace(source,target):
                if Path(target)==Path(entries[1]['source']) and str(source).endswith('.pending'):raise PermissionError('file in use')
                return original(source,target)
            with patch('sem_automation.reporting.yutong.sync.os.replace',side_effect=replace):
                with self.assertRaises(PermissionError):sync(manifest)
            for i,e in enumerate(entries):self.assertEqual(Path(e['source']).read_bytes(),f'old{i}'.encode())
            status=json.loads((manifest.parent/'sync_result.json').read_text(encoding='utf-8'))
            self.assertEqual(status['status'],'rolled_back')

    @unittest.skipUnless(__import__('os').name=='nt','Windows file sharing test')
    def test_real_windows_file_lock(self):
        import ctypes
        from ctypes import wintypes
        create=ctypes.windll.kernel32.CreateFileW
        create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        create.restype=wintypes.HANDLE
        close=ctypes.windll.kernel32.CloseHandle;close.argtypes=[wintypes.HANDLE]
        with tempfile.TemporaryDirectory() as tmp:
            manifest,entries=self.fixture(Path(tmp))
            handle=create(entries[1]['source'],0x80000000,1,None,3,0x80,None)
            self.assertNotEqual(handle,ctypes.c_void_p(-1).value)
            try:
                with self.assertRaises(OSError):sync(manifest)
            finally:close(handle)
            for i,e in enumerate(entries):self.assertEqual(Path(e['source']).read_bytes(),f'old{i}'.encode())
