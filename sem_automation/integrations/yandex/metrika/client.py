# 模块：sem_automation/integrations/yandex/metrika/client.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
from __future__ import annotations

import json

import math

import os

import re

import subprocess

import time

from datetime import datetime, timezone

from pathlib import Path

from urllib.parse import urlparse

import requests

from dotenv import load_dotenv

API_ROOT = 'https://api-metrika.yandex.net'

def hostname(site):
    return (urlparse(site if '://' in site else 'https://' + site).hostname or '').lower().rstrip('.')

def flatten_report(response, dimensions, metrics):
    rows = []
    for item in response.get('data', []):
        dims, values = item.get('dimensions', []), item.get('metrics', [])
        if len(dims) != len(dimensions) or len(values) != len(metrics):
            raise ValueError('Metrika 响应列数与请求不符')
        row = {}
        for name, value in zip(dimensions, dims):
            row[name] = value.get('name') if value else None
            row[name + ':id'] = str(value['id']) if value and value.get('id') is not None else None
        for name, value in zip(metrics, values):
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f'Metrika 返回无效指标：{name}')
            row[name] = value
        rows.append(row)
    return rows

class MetrikaClient:
    def __init__(self, token, session=None):
        if not token:
            raise ValueError('缺少 YANDEX_OAUTH_TOKEN')
        self.session = session or requests.Session()
        self.headers = {'Authorization': f'OAuth {token}'}

    def get(self, endpoint, params=None):
        for attempt in range(5):
            response = self.session.get(API_ROOT + endpoint, params=params,
                                        headers=self.headers, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(min(30, 2 ** (attempt + 1)))
                continue
            if response.status_code != 200:
                raise RuntimeError(f'Metrika HTTP {response.status_code}: {response.text[:1000]}')
            result = response.json()
            if result.get('errors'):
                raise RuntimeError(f'Metrika API 返回错误：{result["errors"]}')
            return result
        raise TimeoutError('Metrika API 超过重试次数')

    def verify_counter(self, config):
        cid = config['counter_id']
        counter = self.get(f'/management/v1/counter/{cid}')['counter']
        if str(counter['id']) != str(cid) or hostname(counter['site']) != hostname(config['expected_site']):
            raise ValueError('Counter ID 或站点不匹配，停止拉取')
        # 只保存所需元数据，不存计数器管理设置中的其他信息。
        return {k: counter.get(k) for k in ('id', 'name', 'site', 'time_zone_name', 'status')}

    def report(self, key, config, start, end, dimensions, metrics, raw_dir, extra_filters=''):
        params = {'ids': config['counter_id'], 'date1': start, 'date2': end,
                  'metrics': ','.join(metrics), 'accuracy': 'full', 'lang': 'en',
                  'include_undefined': 'true', 'limit': 10000, 'offset': 1,
                  'attribution': config['attribution']}
        if dimensions:
            params['dimensions'] = ','.join(dimensions)
            params['sort'] = ','.join(dimensions)
        filters = [f for f in (config.get('filters', ''), extra_filters) if f]
        if filters:
            params['filters'] = ' AND '.join(f'({f})' for f in filters)
        rows, pages, totals = [], [], None
        expected_rows = None
        for page in range(100):
            response = self.get('/stat/v1/data', params)
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f'{key}.page{page + 1}.json').write_text(
                json.dumps({'request': params.copy(), 'response': response}, ensure_ascii=False, indent=2), encoding='utf-8')
            if response.get('sampled'):
                raise ValueError(f'{key} 发生采样；保留响应供检查，不将其作为完整核对数据')
            chunk = flatten_report(response, dimensions, metrics)
            if expected_rows is None:
                expected_rows = response.get('total_rows', len(chunk))
                totals = response.get('totals', [])
            elif response.get('total_rows') != expected_rows or response.get('totals') != totals:
                raise ValueError(f'{key} 分页期间数据变化，请重新运行')
            pages.append({'offset': params['offset'], 'rows': len(chunk),
                          'sample_share': response.get('sample_share'),
                          'contains_sensitive_data': response.get('contains_sensitive_data', False)})
            rows.extend(chunk)
            if len(rows) >= expected_rows:
                break
            if not chunk:
                raise ValueError(f'{key} 分页提前结束，数据不完整')
            params['offset'] += len(chunk)
        else:
            raise ValueError(f'{key} 超过分页上限，请缩短日期区间')
        if dimensions and len(rows) != expected_rows:
            raise ValueError(f'{key} 明细行数不符')
        if len(totals) != len(metrics):
            raise ValueError(f'{key} 总计列数不符')
        print(f'{key}: {len(rows)} 行', flush=True)
        return {'dimensions': dimensions, 'metrics': metrics, 'rows': rows,
                'totals': dict(zip(metrics, totals)), 'pages': pages,
                'date_from': start, 'date_to': end}

