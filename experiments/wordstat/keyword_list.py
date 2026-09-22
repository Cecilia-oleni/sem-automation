# Wordstat 实验模块；从项目根目录运行。
# 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 '.\experiments\wordstat\wordstat.py' --help
# API 请求只由 wordstat.py --execute 显式触发；报告/清单脚本仅操作本地缓存。
"""Read the keyword column from the human-readable tab-separated list."""
from pathlib import Path

def read_keywords():
    lines = Path(__file__).with_name('keywords.txt').read_text(encoding='utf-8-sig').splitlines()
    return list(dict.fromkeys(line.split('\t', 1)[0].strip() for line in lines
                             if line.strip() and not line.startswith('#')))
