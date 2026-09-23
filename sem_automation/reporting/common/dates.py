# 模块：sem_automation/reporting/common/dates.py；内部模块由统一入口调用。
# VS Code PowerShell 先输入：Set-Location -LiteralPath 'D:\sem自动化'
# 终端输入（复制时去掉注释符）：& '.\.venv\Scripts\python.exe' -X utf8 '.\sem.py' --help
"""与具体广告平台无关的报告日期与路径工具。"""
from sem_automation.core.paths import PROJECT_ROOT
import calendar
import re
from datetime import date, timedelta
from pathlib import Path




def date_range(month=None, date_from=None, date_to=None):
    if month:
        if date_from or date_to or not re.fullmatch(r'\d{4}-\d{2}', month):
            raise ValueError('使用 --month YYYY-MM 或 --date-from/--date-to，不可混用')
        year, number = map(int, month.split('-'))
        start = date(year, number, 1)
        end = date(year, number, calendar.monthrange(year, number)[1])
    else:
        if not date_from or not date_to:
            raise ValueError('必须指定月份或完整起止日期')
        for value in (date_from, date_to):
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
                raise ValueError('日期格式必须为 YYYY-MM-DD')
        start, end = date.fromisoformat(date_from), date.fromisoformat(date_to)
    if end < start:
        raise ValueError('结束日期不能早于开始日期')
    if end >= date.today():
        raise ValueError('只导出已结束的日期；请将结束日期设为昨天或更早')
    return start.isoformat(), end.isoformat(), (end - start).days + 1


def comparison_period(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    previous_end = first - timedelta(days=1)
    if first.strftime('%Y-%m') == last.strftime('%Y-%m') and first.day == 1 and (last + timedelta(days=1)).day == 1:
        previous_start = previous_end.replace(day=1)
    else:
        previous_start = first - timedelta(days=(last - first).days + 1)
    return previous_start.isoformat(), previous_end.isoformat()
