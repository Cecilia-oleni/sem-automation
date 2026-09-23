# 模块：sem_automation/integrations/yandex/direct/client.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
from __future__ import annotations

import csv

import io

import json

import math

import os

import re

import subprocess

import time

import uuid

from datetime import datetime, timezone

from pathlib import Path

import requests

from dotenv import load_dotenv

API_ROOT = 'https://api.direct.yandex.com/json/v501'

METRICS = ['Impressions', 'Clicks', 'Ctr', 'Cost', 'AvgCpc', 'AvgPageviews',
           'ConversionRate', 'CostPerConversion', 'Conversions']

NUMERIC = set(METRICS)

def parse_tsv(text, expected):
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')), delimiter='\t')
    if reader.fieldnames != expected:
        raise ValueError(f'API 返回列不符：expected={expected}, actual={reader.fieldnames}')
    rows = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('API 返回了不完整 TSV 行')
        typed = {}
        for key, value in row.items():
            base = key.split('_', 1)[0]
            if base in NUMERIC and value not in ('', '--', '-'):
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError(f'无效数字 {key}: {value}')
                if base in ('Impressions', 'Clicks') and not number.is_integer():
                    raise ValueError(f'计数字段非整数 {key}: {value}')
                typed[key] = int(number) if base in ('Impressions', 'Clicks') else number
            else:
                # 缺失数据原样保留；ID、搜索词保持文本。
                typed[key] = value
        rows.append(typed)
    if len(rows) >= 1_000_000:
        raise ValueError('报告达到 API 百万行上限，请缩短日期区间，不能视为完整导出')
    return rows

def expanded_fields(fields, config):
    return [f"{f}_{config['goal_id']}_{config['attribution_model']}"
            if config.get('goal_id') and f in ('Conversions', 'ConversionRate', 'CostPerConversion')
            else f for f in fields]

class DirectClient:
    def __init__(self, token, config, session=None):
        if not token:
            raise ValueError('缺少 YANDEX_OAUTH_TOKEN，请检查项目 .env')
        self.config = config
        self.session = session or requests.Session()
        self.headers = {'Authorization': f'Bearer {token}',
                        'Client-Login': config['client_login'], 'Accept-Language': 'en',
                        'Content-Type': 'application/json; charset=utf-8'}

    def verify_account(self):
        response = self.session.post(f'{API_ROOT}/clients', headers=self.headers,
            json={'method': 'get', 'params': {'FieldNames': ['Login', 'Currency']}}, timeout=60)
        response.raise_for_status()
        data = response.json()
        clients = data.get('result', {}).get('Clients', [])
        matched = [c for c in clients if c['Login'] == self.config['client_login']]
        if len(matched) != 1 or matched[0]['Currency'] != self.config['currency']:
            raise ValueError(f'账户或币种校验失败：{data}')
        return matched[0]

    def report(self, key, report_type, fields, start, end, raw_dir):
        params = {'SelectionCriteria': {'DateFrom': start, 'DateTo': end},
                  'FieldNames': fields, 'ReportName': f'Standard_{key}_{uuid.uuid4().hex[:12]}',
                  'ReportType': report_type, 'DateRangeType': 'CUSTOM_DATE', 'Format': 'TSV',
                  'IncludeVAT': self.config['include_vat'],
                  'IncludeDiscount': self.config['include_discount']}
        if self.config.get('goal_id'):
            params['Goals'] = [str(self.config['goal_id'])]
            params['AttributionModels'] = [self.config['attribution_model']]
        if key == 'search_queries':
            params['SelectionCriteria']['Filter'] = [
                {'Field': 'Clicks', 'Operator': 'GREATER_THAN', 'Values': ['0']}]
        headers = {**self.headers, 'processingMode': 'auto', 'returnMoneyInMicros': 'false',
                   'skipReportHeader': 'true', 'skipColumnHeader': 'false', 'skipReportSummary': 'true'}
        for attempt in range(20):
            response = self.session.post(f'{API_ROOT}/reports', headers=headers,
                                         json={'params': params}, timeout=60)
            response.encoding = 'utf-8'
            if response.status_code == 200:
                rows = parse_tsv(response.text, expanded_fields(fields, self.config))
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / f'{key}.tsv').write_text(response.text, encoding='utf-8')
                audit = {'params': params, 'request_id': response.headers.get('RequestId'),
                         'rows': len(rows), 'warnings': response.headers.get('Warning')}
                (raw_dir / f'{key}.request.json').write_text(
                    json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f'{key}: {len(rows)} 行', flush=True)
                return rows
            if response.status_code in (201, 202, 429, 500, 502, 503, 504):
                try:
                    delay = min(60, max(1, int(response.headers.get('retryIn', '5'))))
                except ValueError:
                    delay = 5
                print(f'{key}: HTTP {response.status_code}, {delay} 秒后重试 ({attempt + 1}/20)', flush=True)
                time.sleep(delay)
                continue
            raise RuntimeError(f'{key}: HTTP {response.status_code}; '
                               f'RequestId={response.headers.get("RequestId")}; {response.text[:1200]}')
        raise TimeoutError(f'{key}: 达到重试上限，未输出成功报告')

