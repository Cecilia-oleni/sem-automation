# 模块：sem_automation/reporting/yutong/history.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化 - 副本'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' reports yutong --config '.\config\reports\yutong\2026-08.json' --month 2026-08
# 该示例复用本地数据；详见 docs/月报操作说明.md。
"""Strict month keys and dynamic history block discovery; no workbook writes."""
from datetime import date, datetime
import math
import re

def month_key(value):
    if isinstance(value, (datetime, date)):
        return value.strftime('%Y-%m')
    if isinstance(value, float) and not math.isfinite(value):
        return None
    # Decimal .1 cannot distinguish January from October; require text/date.
    if isinstance(value, (int, float)) and re.fullmatch(r'\d{4}\.1', str(value)):
        raise ValueError(f'月份 {value} 有歧义，请在源表改为文本 YYYY-MM')
    match = re.fullmatch(r'((?:20)?\d{2})[-.年](\d{1,2})(?:月)?', str(value).strip())
    if not match:
        return None
    y,m=map(int,match.groups())
    if y<100:y+=2000
    if not 1<=m<=12:
        raise ValueError(f'无效月份: {value}')
    return f'{y:04d}-{m:02d}'

def periods(month):
    if not re.fullmatch(r'20\d{2}-\d{2}', month) or month_key(month)!=month:
        raise ValueError('月份格式必须为 YYYY-MM')
    y,m=map(int,month.split('-'))
    return {'current':month, 'previous':f'{y if m>1 else y-1:04d}-{m-1 if m>1 else 12:02d}', 'yearAgo':f'{y-1:04d}-{m:02d}', 'ytd':[f'{y:04d}-{i:02d}' for i in range(1,m+1)]}

def label(value):
    return str(value or '').split('（')[0].strip()

def blocks(rows, required_countries=None, sheet_name='history', raw=False):
    found={}
    for index,row in enumerate(rows):
        key=month_key(row[0] if row else None)
        if key is None:continue
        if key in found:raise ValueError(f'{sheet_name}: 重复月份 {key}，行 {found[key]["start"]} 与 {index+1}')
        if index+1>=len(rows) or label(rows[index+1][0])!='国家':
            raise ValueError(f'{sheet_name}: {key} 后没有国家表头，行 {index+1}')
        headers=rows[index+1]
        if len(headers)<6 or headers[1:3]!=['展示合计','点击合计'] or headers[5]!='线索':
            raise ValueError(f'{sheet_name}: {key} 的历史表头无法识别')
        records={}; row_numbers={}; total=None
        for j in range(index+2,len(rows)):
            current=rows[j]; name=label(current[0])
            if not name:
                if len(records)==len(required_countries or []) and (raw or any(v is not None for v in current[1:6])):
                    total=j+1
                break
            if name=='合计':total=j+1;break
            if month_key(current[0]):break
            if name in records:raise ValueError(f'{sheet_name}: {key} 重复国家 {name}')
            records[name]=current;row_numbers[name]=j+1
        if required_countries and set(records)!=set(required_countries):
            raise ValueError(f'{sheet_name}: {key} 国家不完整或有未知国家: {set(required_countries)^set(records)}')
        if not total:raise ValueError(f'{sheet_name}: {key} 缺少合计行')
        found[key]={'start':index+1,'end':total,'rows':records,'row_numbers':row_numbers,'total':total}
    if not found:raise ValueError(f'{sheet_name}: 未识别出任何月份数据块')
    return found

def require_periods(history, expected, source):
    missing=[key for key in expected if key not in history]
    if missing:raise ValueError(f'{source}: 缺少历史期间 {", ".join(missing)}')

def destination(history, month, last_row):
    return history[month]['start'] if month in history else last_row+4
