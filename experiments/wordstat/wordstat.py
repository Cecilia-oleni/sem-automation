# Wordstat 实验模块；从项目根目录运行。
# 终端输入：& '.\.venv\Scripts\python.exe' -X utf8 '.\experiments\wordstat\wordstat.py' --help
# API 请求只由 wordstat.py --execute 显式触发；报告/清单脚本仅操作本地缓存。
"""Isolated stdlib-only Wordstat experiment. Dry run unless --execute."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
ENV = ROOT.parent.parent / '.env'
BASE = 'https://searchapi.api.cloud.yandex.net/v2/wordstat/'
MAX_PAID_ATTEMPTS = 14

def settings():
    values = {}
    for line in ENV.read_text(encoding='utf-8-sig').splitlines():
        name, sep, value = line.strip().partition('=')
        if sep and name.strip() in ('YANDEX_CLOUD_AI_STUDIO_API_KEY', 'YANDEX_CLOUD_FOLDER_ID'):
            value = value.strip()
            if value[:1] in ('"', "'") and value[-1:] == value[:1]:
                value = value[1:-1]
            else:
                value = value.split(' #', 1)[0].strip()
            values[name.strip()] = value
    return values

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--regions-tree', action='store_true')
    p.add_argument('--phrase', default='gobroad глубокая стимуляция мозга')
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    cfg = settings()
    body = {} if a.regions_tree else {'phrase': a.phrase, 'numPhrases': '50', 'devices': ['DEVICE_ALL']}
    if not a.regions_tree and not 1 <= len(a.phrase) <= 400:
        p.error('phrase length must be 1..400')
    if cfg.get('YANDEX_CLOUD_FOLDER_ID'):
        body['folderId'] = cfg['YANDEX_CLOUD_FOLDER_ID']
    method = 'getRegionsTree' if a.regions_tree else 'topRequests'
    fingerprint = hashlib.sha256(json.dumps([method, body], sort_keys=True).encode()).hexdigest()[:20]
    output = ROOT / 'results' / (fingerprint + '.json')
    if output.exists():
        print('CACHE ' + output.read_text(encoding='utf-8'))
        return 0
    print(json.dumps({'method': method, 'request': body, 'execute': a.execute,
                      'estimated_RUB': 0 if a.regions_tree else 0.02}, ensure_ascii=False))
    if not a.execute:
        return 0
    key = cfg.get('YANDEX_CLOUD_AI_STUDIO_API_KEY')
    if not key:
        print('Missing API key; no request sent.')
        return 2
    output.parent.mkdir(exist_ok=True)
    ledger = ROOT / 'results' / 'attempts.jsonl'
    # Exclusive lock also prevents simultaneous processes exceeding the budget.
    lock = ROOT / 'results' / 'request.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print('Another call is running or a stale lock needs review.')
        return 2
    os.close(fd)
    try:
        attempts = [json.loads(x) for x in ledger.read_text().splitlines()] if ledger.exists() else []
        if sum(x['method'] == 'topRequests' for x in attempts) >= MAX_PAID_ATTEMPTS and not a.regions_tree:
            print('Experiment cap reached: 14 paid attempts (RUB 0.28 estimated).')
            return 2
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        with ledger.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'time': stamp, 'method': method, 'fingerprint': fingerprint}) + '\n')
        req = urllib.request.Request(BASE + method, data=json.dumps(body).encode(),
              headers={'Authorization': 'Api-Key ' + key, 'Content-Type': 'application/json'}, method='POST')
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=40) as response:
                data = json.loads(response.read().decode())
            record = {'time': stamp, 'request': body, 'method': method, 'response': data}
            safe = json.dumps(record, ensure_ascii=False, indent=2).replace(key, '[REDACTED]')
            output.write_text(safe, encoding='utf-8')
            print(safe)
            return 0
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors='replace').replace(key, '[REDACTED]')
            safe = json.dumps({'time': stamp, 'http_status': e.code, 'detail': detail}, ensure_ascii=False)
            (ROOT / 'results' / 'last-error.json').write_text(safe, encoding='utf-8')
            print(safe)
            return 1
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            print('Network failure; no automatic retry: ' + str(e).replace(key, '[REDACTED]'))
            return 1
    finally:
        lock.unlink()

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
