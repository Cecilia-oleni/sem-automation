# 模块：sem_automation/reporting/standard/direct.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""通用客户报告 MVP 1：Direct 只读抓取，原始 TSV/JSON + 白底 XLSX。

不调用 AI，不处理否词，不写入客户月报。按完整月份或任意闭区间运行。
"""
from __future__ import annotations

from sem_automation.integrations.yandex.direct.client import API_ROOT, DirectClient, METRICS, NUMERIC, expanded_fields, parse_tsv

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

from sem_automation.reporting.common.dates import PROJECT_ROOT, date_range
DEFAULT_CONFIG = PROJECT_ROOT / 'config' / 'lingyu_direct_monthly.json'
QUERY_FIELDS = ['Query', 'CampaignName', 'CampaignId', 'AdGroupName', 'AdGroupId',
                'CriterionType', 'MatchType', 'Criterion', 'TargetingCategory',
                'Impressions', 'Clicks', 'Ctr', 'Cost', 'AvgCpc',
                'Conversions', 'ConversionRate', 'CostPerConversion']
DEFAULT_TOLERANCE = {'count_absolute': 2, 'cost_absolute': 1.0, 'relative': 0.005}


def load_config(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    for field in ('client_name', 'client_login', 'client_slug', 'currency'):
        if not isinstance(config.get(field), str) or not config[field].strip():
            raise ValueError(f'配置缺少 {field}')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', config['client_slug']):
        raise ValueError('client_slug 只能包含字母、数字、下划线、连字符')
    for field in ('include_vat', 'include_discount'):
        if config.get(field) not in ('YES', 'NO'):
            raise ValueError(f'{field} 必须为 YES 或 NO')
    if config.get('goal_id') and config.get('attribution_model') not in ('AUTO', 'LC', 'LSCCD', 'FCCD'):
        raise ValueError('attribution_model 必须为 AUTO/LC/LSCCD/FCCD')
    # MVP 保留一个明确的转化口径，避免把多个目标简单求和当作去重转化。
    goal = config.get('goal_id')
    if goal is not None and not re.fullmatch(r'\d+', str(goal)):
        raise ValueError('goal_id 必须为目标 ID 或 null（API 默认汇总）')
    for key, value in config.get('tolerance', {}).items():
        if key not in DEFAULT_TOLERANCE or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f'无效容差配置 {key}: {value}')
    return config


def report_specs():
    return {
        'account': ('ACCOUNT_PERFORMANCE_REPORT', METRICS),
        'campaign': ('CAMPAIGN_PERFORMANCE_REPORT', ['CampaignName', 'CampaignId'] + METRICS),
        'search_queries': ('SEARCH_QUERY_PERFORMANCE_REPORT', QUERY_FIELDS),
    }








def difference_status(expected, actual, field, tolerance=None):
    """绝对量与相对量必须同时满足；零基线只允许零差异。"""
    difference = abs(actual - expected)
    if difference < 1e-6:
        return 'PASS'
    limits = {**DEFAULT_TOLERANCE, **(tolerance or {})}
    absolute = limits['cost_absolute'] if field == 'Cost' else limits['count_absolute']
    if expected != 0 and difference <= absolute + 1e-6 and difference / abs(expected) <= limits['relative'] + 1e-12:
        return 'WARN: within small tolerance'
    return 'MISMATCH'


def reconcile(raw, tolerance=None):
    if len(raw['account']) > 1:
        raise ValueError('账户报告意外返回多个汇总行')
    checks = []
    account = raw['account'][0] if raw['account'] else {}
    for key in ('campaign', 'search_queries'):
        for field in ('Impressions', 'Clicks', 'Cost'):
            total = sum(r[field] for r in raw[key])
            expected = account.get(field, 0)
            difference = total - expected
            # 搜索词不是全部展示；只记录差异，不把它误判为下载失败。
            checks.append({'report': key, 'metric': field, 'account': expected,
                           'detail': round(total, 6), 'difference': round(difference, 6),
                           'status': ('INFO: different scope' if key == 'search_queries' and abs(difference) > 1e-6
                                      else difference_status(expected, total, field, tolerance))})
    return checks


def fetch_dataset(config, start, end, days, output_dir):
    load_dotenv(PROJECT_ROOT / '.env')
    client = DirectClient(os.getenv('YANDEX_OAUTH_TOKEN'), config)
    identity = client.verify_account()
    raw = {key: client.report(key, typ, fields, start, end, output_dir / '_internal')
           for key, (typ, fields) in report_specs().items()}
    notes = [
        'Brand mentions in queries: 当前公开 Reports API 无对应字段，按用户要求省略此列。',
        'TargetingCategory 是旧版分类，仅输出 API 原值；不保证等同新版 Report wizard 的 Request category。',
        '搜索词展示量可能低于账户展示量；搜索词明细合计不可替代账户汇总。',
        '搜索词筛选：Clicks > 0，与用户提供的 Report wizard 搜索词模板一致。',
        '百分比使用 API 的百分数数值（例如 3.36 表示 3.36%），与 Report wizard 一致。',
        '日均花费按含首尾日期的自然日计算；AvgPageviews 直接取 API，不对系列均值再平均。',
        '转化是 API 所选口径，未核准为实际询盘；不使用附件转化数覆盖 API。',
    ]
    dataset = {'schema_version': 1, 'meta': {**config, 'date_from': start, 'date_to': end,
        'days': days, 'verified_account': identity,
        'attribution_model': config.get('attribution_model') if config.get('goal_id') else 'API default (Goals omitted)',
        'fetched_at': datetime.now(timezone.utc).isoformat(),
        'conversion_scope': str(config.get('goal_id') or 'Direct All goals'),
        'tolerance': {**DEFAULT_TOLERANCE, **config.get('tolerance', {})},
        'notes': notes}, 'raw': raw, 'checks': reconcile(raw, config.get('tolerance'))}
    path = output_dir / '_internal' / 'direct_monthly_data.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def export_xlsx(dataset_path, output_dir, node_executable):
    if not node_executable or not Path(node_executable).is_file():
        raise ValueError('请配置 --node 或 CODEX_NODE_EXE 为可用 Node.js 的完整路径（需 @oai/artifact-tool）')
    subprocess.run([str(node_executable), str(PROJECT_ROOT / 'sem_automation/reporting/renderers/standard/direct_monthly_workbook.mjs'),
                    '--input', str(dataset_path), '--out-dir', str(output_dir)],
                   cwd=PROJECT_ROOT, check=True)
    output = output_dir / 'direct_api_review.xlsx'
    if not output.is_file():
        raise RuntimeError('XLSX 未生成，不能视为成功')
    return output
