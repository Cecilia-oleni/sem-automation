# 模块：sem_automation/reporting/standard/pipeline.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports standard --client '.\config\clients\lingyu.json' --month 2026-07 --source existing --data-dir '.\outputs\_archive\lingyu\2026-07'
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""可从 CLI 或未来 GUI 调用的报告服务；客户、模板、数据与渲染独立。"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sem_automation.reporting.common.dates import PROJECT_ROOT, comparison_period, date_range
from sem_automation.reporting.standard import direct as direct_api
from sem_automation.reporting.standard import metrika as metrika_api


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def resolve_node(explicit=None):
    local = PROJECT_ROOT / 'config/runtime.local.json'
    value = explicit or os.getenv('CODEX_NODE_EXE') or (read_json(local).get('node') if local.exists() else None) or shutil.which('node')
    if not value or not Path(value).is_file():
        raise ValueError('未找到 Node.js，请配置 --node、CODEX_NODE_EXE 或 config/runtime.local.json')
    return str(Path(value).resolve())


def load_client(path):
    path = Path(path).resolve()
    client = read_json(path)
    if client.get('version') != 1 or not client.get('name'):
        raise ValueError('无效客户配置版本或名称')
    for key in ('direct_config', 'metrika_config', 'layout', 'template'):
        client[key] = str((path.parent / client[key]).resolve())
        if not Path(client[key]).is_file():
            raise ValueError(f'找不到 {key}: {client[key]}')
    dc = direct_api.load_config(client['direct_config'])
    mc = metrika_api.load_config(client['metrika_config'])
    if client['slug'] != dc['client_slug'] or client['slug'] != mc['client_slug']:
        raise ValueError('客户标识与 Direct/Metrika 配置不一致')
    if client.get('negative_words') not in ('preserve', 'blank'):
        raise ValueError('negative_words 必须为 preserve 或 blank')
    if client['negative_words'] == 'preserve' and client.get('template_client_login') != dc['client_login']:
        raise ValueError('保留否词时必须使用该客户自己的模板，不能携带其他客户的否词')
    layout = read_json(client['layout'])
    validate_layout(layout)
    return client, dc, mc, layout


def validate_layout(layout):
    if layout.get('version') != 1:
        raise ValueError('不支持的模板布局版本')
    if layout.get('presentation', 'dashboard') not in ('classic', 'dashboard'):
        raise ValueError('presentation 必须为 classic 或 dashboard')
    if layout.get('presentation') == 'classic':
        classic = layout.get('classic', {})
        for key in ('summary_order', 'metrika_cards'):
            fields = classic.get(key)
            if not isinstance(fields, list) or len(fields) != len(set(fields)):
                raise ValueError(f'classic.{key} 必须为无重复的字段列表')
    allowed_direct = set(direct_api.METRICS) | {'AvgDailyCost'}
    allowed_metrika = set(metrika_api.SUMMARY_METRICS) | {'ym:pv:pageviews'}
    for name, allowed in [('direct_metrics', allowed_direct), ('metrika_metrics', allowed_metrika)]:
        entries = layout.get(name, [])
        fields = [e['field'] for e in entries]
        if not fields or len(fields) != len(set(fields)) or not set(fields) <= allowed:
            raise ValueError(f'{name} 存在空列表、重复或未支持字段')
    charts = layout.get('charts', {})
    if set(charts) != {'direct_daily','traffic','devices','ages','sources','new_returning','goals'}:
        raise ValueError('布局必须声明全部标准图表区块；不支持未知区块')
    for key, spec in charts.items():
        allowed = {'line', 'bar'} if key in {'direct_daily', 'traffic', 'new_returning', 'goals'} else {'line', 'bar', 'pie', 'doughnut'}
        if spec['type'] not in allowed:
            raise ValueError(f'{key} 图表类型不适合该数据: {spec["type"]}')
        if key == 'direct_daily' and not set(spec['fields']) <= {'Clicks', 'Cost', 'Conversions', 'Impressions'}:
            raise ValueError('direct_daily 含未知指标')
        if key == 'traffic' and not set(spec['fields']) <= {'ym:s:visits', 'ym:s:users', 'ym:s:pageviews'}:
            raise ValueError('traffic 含未知指标')
        if key in {'direct_daily','traffic'} and (not spec['fields'] or len(set(spec['fields'])) != len(spec['fields'])):
            raise ValueError(f'{key} 图表字段不能为空或重复')


def validate_datasets(direct, metrika, dc, mc, start, end):
    if direct.get('schema_version') != 1 or metrika.get('schema') != 'metrika_monthly_v1':
        raise ValueError('不是受支持的标准报告数据（不能混用安琪专用格式）')
    for label, data in [('Direct', direct), ('Metrika', metrika)]:
        meta = data['meta']
        if (meta.get('date_from'), meta.get('date_to')) != (start, end):
            raise ValueError(f'{label} 数据日期与要求区间不一致')
    dm, mm = direct['meta'], metrika['meta']
    for field in ('client_login', 'currency', 'goal_id', 'include_vat', 'include_discount'):
        if dm.get(field) != dc.get(field):
            raise ValueError(f'Direct {field} 与客户配置不一致，必须重新拉取')
    if dc.get('goal_id') and dm.get('attribution_model') != dc.get('attribution_model'):
        raise ValueError('Direct attribution_model 与客户配置不一致，必须重新拉取')
    if str(mm.get('counter_id')) != str(mc['counter_id']) or metrika_api.hostname(mm['counter']['site']) != metrika_api.hostname(mc['expected_site']):
        raise ValueError('Metrika 计数器或网站与客户配置不一致')
    for field in ('filters', 'attribution'):
        if mm.get(field, '') != mc.get(field, ''):
            raise ValueError(f'Metrika {field} 已改变，必须重新拉取')
    if mc.get('goal_ids') and set(map(str, mc['goal_ids'])) != {g['id'] for g in metrika['goals']}:
        raise ValueError('Metrika 目标列表与客户配置不一致')
    if any(c['status'] == 'MISMATCH' for c in direct_api.reconcile(direct['raw'], dc.get('tolerance'))):
        raise ValueError('Direct 对账超出容差，不能作为正式报告')
    for key, report in metrika['reports'].items():
        if any(page.get('sample_share', 1) not in (None, 1) for page in report.get('pages', [])):
            raise ValueError(f'Metrika {key} 存在采样数据')


def enrich_datasets(direct, metrika, dc, mc, out, start, end):
    """仅补缺少的图表/前期数据；既有已核对明细不会被替换。"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
    prev_start, prev_end = comparison_period(start, end)
    dclient = direct_api.DirectClient(os.getenv('YANDEX_OAUTH_TOKEN'), dc)
    if 'daily' not in direct['raw']:
        direct['raw']['daily'] = dclient.report('daily', 'ACCOUNT_PERFORMANCE_REPORT',
            ['Date'] + direct_api.METRICS, start, end, out / '_internal')
    if 'previous_account' not in direct['raw']:
        direct['raw']['previous_account'] = dclient.report('previous_account', 'ACCOUNT_PERFORMANCE_REPORT',
            direct_api.METRICS, prev_start, prev_end, out / '_internal')
    direct['meta']['comparison_period'] = {'date_from': prev_start, 'date_to': prev_end}
    mclient = metrika_api.MetrikaClient(os.getenv('YANDEX_OAUTH_TOKEN'))
    if 'previous_pageviews_hits' not in metrika['reports']:
        metrika['reports']['previous_pageviews_hits'] = mclient.report('previous_pageviews_hits', mc,
            prev_start, prev_end, [], ['ym:pv:pageviews'], out / '_internal/metrika')


def validate_enrichment(direct, metrika, start, end, dc):
    previous = comparison_period(start, end)
    if 'daily' not in direct['raw'] or 'previous_account' not in direct['raw'] or 'previous_pageviews_hits' not in metrika['reports']:
        raise ValueError('现有数据缺少每日投放或前期汇总；请加 --enrich 补拉一次，之后可完全离线重建')
    period = direct['meta'].get('comparison_period', {})
    if (period.get('date_from'), period.get('date_to')) != previous:
        raise ValueError('Direct 对比周期不一致')
    for key in ('previous_summary', 'previous_pageviews_hits'):
        r = metrika['reports'][key]
        if (r['date_from'], r['date_to']) != previous:
            raise ValueError(f'Metrika {key} 对比周期不一致')
    seen_dates = set()
    for row in direct['raw']['daily']:
        if not start <= row['Date'] <= end:
            raise ValueError('Direct 每日数据含区间外日期')
        if row['Date'] in seen_dates:
            raise ValueError('Direct 每日数据含重复日期')
        seen_dates.add(row['Date'])
    account = direct['raw']['account'][0] if direct['raw']['account'] else {}
    for field in ('Impressions', 'Clicks', 'Cost'):
        total = sum(row[field] for row in direct['raw']['daily'])
        if direct_api.difference_status(account.get(field, 0), total, field, dc.get('tolerance')) == 'MISMATCH':
            raise ValueError(f'Direct 每日 {field} 与总计差异超限')


def run_report(*, client_path, start, end, source='existing', enrich=False, node=None, data_dir=None, output_dir=None, customer_copy=True, run_dir=None):
    """独立服务入口：返回实际文件路径；没有 input() 或 UI 依赖。"""
    start, end, days = date_range(date_from=start, date_to=end)
    client, dc, mc, layout = load_client(client_path)
    if customer_copy and layout.get('presentation') != 'classic':
        raise ValueError('客户版请使用 classic 版式；dashboard 完整版请加 --internal-only')
    node = resolve_node(node)
    period = start[:7] if start[:7] == end[:7] and start.endswith('-01') and (date.fromisoformat(end) + timedelta(days=1)).day == 1 else f'{start}_{end}'
    if source == 'existing' and not data_dir:
        raise ValueError('离线报告必须显式指定 data_dir')
    if not data_dir and not run_dir:
        raise ValueError('请显式提供本次运行目录 run_dir')
    data_dir = Path(data_dir or run_dir).resolve()
    if run_dir:
        run_dir = Path(run_dir)
        if source == 'existing':
            for relative in ('_internal/direct_monthly_data.json', '_internal/metrika/metrika_monthly_data.json'):
                destination = run_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(data_dir / relative, destination)
        data_dir = run_dir
    output_dir = Path(output_dir or data_dir / 'report').resolve()
    dpath = data_dir / '_internal/direct_monthly_data.json'
    mpath = data_dir / '_internal/metrika/metrika_monthly_data.json'
    if source == 'api':
        dpath = direct_api.fetch_dataset(dc, start, end, days, data_dir)
        mpath = metrika_api.fetch_dataset(mc, start, end, data_dir)
    elif source != 'existing':
        raise ValueError('source 必须为 existing 或 api')
    if not dpath.exists() or not mpath.exists():
        raise ValueError('缺少该客户/区间的数据，请先用 --source api 拉取，或指定 --data-dir')
    direct, metrika = read_json(dpath), read_json(mpath)
    validate_datasets(direct, metrika, dc, mc, start, end)
    if enrich or source == 'api':
        enrich_datasets(direct, metrika, dc, mc, data_dir, start, end)
        validate_enrichment(direct, metrika, start, end, dc)
        write_json(dpath, direct)
        write_json(mpath, metrika)
        # 本次补拉的数据也必须出现在可核对 XLSX 中。
        direct_api.export_xlsx(dpath, data_dir, node)
        metrika_api.export_xlsx(mpath, data_dir, node)
    validate_enrichment(direct, metrika, start, end, dc)
    bundle = {'schema': 'yandex_report_v1', 'client': client, 'layout': layout,
              'direct': direct, 'metrika': metrika,
              'period': {'start': start, 'end': end, 'days': days}}
    bundle_path = (run_dir or output_dir) / '_internal/report_bundle.json'
    write_json(bundle_path, bundle)
    filename = f"{client['slug']}_{start}_{end}_Yandex报告.xlsx"
    result = output_dir / filename
    customer_result = result.with_name(result.stem + '_客户版.xlsx')
    command = [node, str(PROJECT_ROOT / 'sem_automation/reporting/renderers/standard/yandex_report_workbook.mjs'),
               '--input', str(bundle_path), '--output', str(result)]
    if customer_copy:
        command += ['--customer-output', str(customer_result)]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    if not result.is_file():
        raise RuntimeError('最终报告未生成')
    if customer_copy and not customer_result.is_file():
        raise RuntimeError('客户交付版未生成')
    manifest = {'schema': 'report_run_v1', 'client': client['slug'], 'date_from': start, 'date_to': end,
                'source': source, 'completed_at': datetime.now(timezone.utc).isoformat(),
                'inputs': {str(p): hashlib.sha256(Path(p).read_bytes()).hexdigest()
                           for p in (dpath, mpath, Path(client['template']), Path(client['layout']))},
                'report': str(result), 'customer_report': str(customer_result) if customer_copy else None}
    write_json((run_dir or output_dir) / '_internal/run_manifest.json', manifest)
    return customer_result if customer_copy else result
