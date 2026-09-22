# 模块：sem_automation/reporting/standard/metrika.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""通用月报第二阶段：只读 Metrika API，独立 JSON 与 XLSX。"""
from __future__ import annotations

from sem_automation.integrations.yandex.metrika.client import API_ROOT, MetrikaClient, flatten_report, hostname

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
from sem_automation.reporting.common.dates import PROJECT_ROOT, date_range, comparison_period

DEFAULT_CONFIG = PROJECT_ROOT / 'config' / 'lingyu_metrika_monthly.json'
SUMMARY_METRICS = ['ym:s:visits', 'ym:s:users', 'ym:s:pageviews', 'ym:s:bounceRate',
                   'ym:s:pageDepth', 'ym:s:avgVisitDurationSeconds', 'ym:s:newUsers']
ATTRIBUTIONS = {'first', 'last', 'lastsign', 'last_yandex_direct_click',
                'cross_device_first', 'cross_device_last', 'cross_device_last_significant',
                'cross_device_last_yandex_direct_click', 'automatic'}


def load_config(path=DEFAULT_CONFIG):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not str(config.get('counter_id') or '').isdigit():
        raise ValueError('请先在 Metrika 客户配置中填写已确认的 counter_id；不自动猜选同域名计数器')
    if not config.get('client_name') or not re.fullmatch(r'[A-Za-z0-9_-]+', config.get('client_slug', '')):
        raise ValueError('需要 client_name 和合法的 client_slug')
    if not config.get('expected_site'):
        raise ValueError('需要 expected_site，用于校验 Counter ID 对应网站')
    if config.get('attribution') not in ATTRIBUTIONS:
        raise ValueError('不支持的归因模型')
    if config.get('accuracy') != 'full':
        raise ValueError('核对阶段必须使用 accuracy=full')
    if not isinstance(config.get('filters', ''), str):
        raise ValueError('filters 必须是字符串；空字符串代表不增加流量筛选')
    goals = config.get('goal_ids', [])
    if not isinstance(goals, list) or any(not str(g).isdigit() for g in goals):
        raise ValueError('goal_ids 必须是数字 ID 列表；空列表表示读取全部当前目标')
    if len(set(map(str, goals))) != len(goals):
        raise ValueError('goal_ids 不能重复')
    return config








def fetch_dataset(config, start, end, output_dir):
    load_dotenv(PROJECT_ROOT / '.env')
    client = MetrikaClient(os.getenv('YANDEX_OAUTH_TOKEN'))
    counter = client.verify_counter(config)
    goals = client.get(f'/management/v1/counter/{config["counter_id"]}/goals')['goals']
    goals_by_id = {str(g['id']): g for g in goals}
    selected = list(map(str, config.get('goal_ids') or goals_by_id.keys()))
    missing = set(selected) - goals_by_id.keys()
    if missing:
        raise ValueError(f'当前计数器缺少配置中的目标 {sorted(missing)}，请核对计数器或目标配置')
    raw_dir = output_dir / '_internal' / 'metrika'
    specs = {
        'summary': ([], SUMMARY_METRICS, ''),
        'pageviews_hits': ([], ['ym:pv:pageviews'], ''),
        'daily': (['ym:s:date'], SUMMARY_METRICS, ''),
        'devices': (['ym:s:deviceCategory'], ['ym:s:visits'], ''),
        'ages': (['ym:s:ageInterval'], ['ym:s:visits'], ''),
        'sources': ([f'ym:s:{config["attribution"]}TrafficSource'], ['ym:s:visits'], ''),
        'new_returning': (['ym:s:isNewUser'], ['ym:s:users'], ''),
        'new_returning_daily': (['ym:s:date', 'ym:s:isNewUser'], ['ym:s:users'], ''),
    }
    reports = {}
    for key, (dimensions, metrics, extra_filter) in specs.items():
        reports[key] = client.report(key, config, start, end, dimensions, metrics, raw_dir, extra_filter)
    prev_start, prev_end = comparison_period(start, end)
    reports['previous_summary'] = client.report('previous_summary', config, prev_start, prev_end,
                                               [], SUMMARY_METRICS, raw_dir)
    for gid in selected:
        metrics = [f'ym:s:goal{gid}{suffix}' for suffix in ('conversionRate', 'visits', 'reaches')]
        # 只请求目标指标会省略无转化日期，导致返回总转化率的分母缩小。
        # 加入总会话数，让全部有访问日期都参与 API 汇总与每日分母。
        metrics.append('ym:s:visits')
        reports[f'goal_{gid}'] = client.report(f'goal_{gid}', config, start, end, ['ym:s:date'], metrics, raw_dir)
    notes = list(config.get('notes', [])) + [
        'Users 按整个区间去重；不能把每日 Users 相加当作月 Users。',
        '新老访客在不同访问中可能跨组，同一人可同时出现在两组；两组之和不一定等于去重 Users。',
        '年龄报告含未识别数据，分母按具体图表口径确定；不把缺失年龄自动算作 Other。',
        'Conversions(reaches) 是目标达成次数；Converted sessions(visits) 是达成目标的会话数，不混用。',
        'Metrika 全站目标统计与 Direct All goals 广告归因口径不同，不能强制相等。',
        'Pageviews 卡片对应 ym:pv:pageviews（页面事件口径）；流量图与浏览深度对应 ym:s:pageviews（会话口径），分别保留。',
        '完整月份的环比默认比较前一自然月；截图的自动上一周期可能是等天数区间，百分比不一定相同。',
        'API 使用 accuracy=full，若仍发生采样则中止；敏感数据限制在导出口径页提示。',
    ]
    data = {'schema': 'metrika_monthly_v1', 'meta': {**config, 'counter': counter,
            'date_from': start, 'date_to': end, 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'notes': notes}, 'goals': [{'id': gid, 'name': goals_by_id[gid]['name']} for gid in selected],
            'reports': reports}
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / 'metrika_monthly_data.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


def export_xlsx(dataset, output_dir, node):
    if not node or not Path(node).is_file():
        raise ValueError('需要 --node 或 CODEX_NODE_EXE 指定 Node.js 完整路径')
    subprocess.run([node, str(PROJECT_ROOT / 'sem_automation/reporting/renderers/standard/metrika_monthly_workbook.mjs'),
                    '--input', str(dataset), '--out-dir', str(output_dir)], cwd=PROJECT_ROOT, check=True)
    return output_dir / 'metrika_api_review.xlsx'
