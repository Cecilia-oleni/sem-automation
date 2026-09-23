# 终端输入：python sem.py materials wordstat query --help
"""Persistent shared quota, process locks and Wordstat transport; no business rules."""
import contextlib
import hashlib
import json
import os
import time
from pathlib import Path
from email.utils import parsedate_to_datetime

import requests
from dotenv import dotenv_values


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


@contextlib.contextmanager
def file_lock(path):
    """OS-owned lock: released on process death; never delete an active lock file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f'另一个进程正在处理此任务，请稍后重试：{path}') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


class Quota:
    def __init__(self, path, *, clock=time.time, sleep=time.sleep, report=print, hourly=100):
        self.path = Path(path)
        self.clock, self.sleep, self.report = clock, sleep, report
        self.hourly = hourly

    def reserve(self):
        while True:
            with file_lock(self.path.with_suffix('.lock')):
                state = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {}
                now = self.clock()
                attempts = [t for t in state.get('attempts', []) if t > now - 3600]
                wait = max(0, state.get('blocked_until', 0) - now)
                if attempts:
                    wait = max(wait, attempts[-1] + 1 - now)
                if len(attempts) >= self.hourly:
                    wait = max(wait, attempts[-self.hourly] + 3600.1 - now)
                if wait <= 0:
                    state['attempts'] = attempts + [now]
                    save_json(self.path, state)
                    return
            self.report(f'Wordstat 配额等待：约 {int(wait)+1} 秒；可以 Ctrl+C，之后续跑。')
            self.sleep(min(wait, 60))

    def defer(self, seconds):
        with file_lock(self.path.with_suffix('.lock')):
            state = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {}
            state['blocked_until'] = max(state.get('blocked_until', 0), self.clock() + seconds)
            save_json(self.path, state)


class WordstatClient:
    URL = 'https://searchapi.api.cloud.yandex.net/v2/wordstat/topRequests'

    def __init__(self, root, *, session=None, quota=None):
        cfg = {**dotenv_values(Path(root)/'.env'), **os.environ}
        self.key = cfg.get('YANDEX_CLOUD_AI_STUDIO_API_KEY')
        self.folder = cfg.get('YANDEX_CLOUD_FOLDER_ID')
        if not self.key or not self.folder:
            raise ValueError('请在根目录 .env 配置 YANDEX_CLOUD_AI_STUDIO_API_KEY 与 YANDEX_CLOUD_FOLDER_ID')
        scope = hashlib.sha256(self.folder.encode()).hexdigest()[:16]
        self.quota = quota or Quota(Path(root)/'cache/wordstat'/f'{scope}.json')
        self.session = session or requests.Session()

    def top_requests(self, phrase, regions):
        if not 1 <= len(phrase) <= 400:
            raise ValueError('Wordstat 关键词必须为 1–400 字符')
        body = dict(phrase=phrase, numPhrases='30', devices=['DEVICE_ALL'], folderId=self.folder)
        if regions:
            body['regions'] = regions
        failures = 0
        while True:
            self.quota.reserve()
            try:
                response = self.session.post(self.URL, json=body, headers={
                    'Authorization': 'Api-Key ' + self.key}, timeout=40, allow_redirects=False)
            except requests.RequestException:
                failures += 1
                if failures >= 3:
                    raise RuntimeError('Wordstat 网络请求连续失败；已保存进度，请稍后续跑。') from None
                self.quota.defer(2 ** failures)
                continue
            if response.status_code == 429:
                retry = response.headers.get('Retry-After', '60')
                try:
                    seconds = float(retry)
                except ValueError:
                    try:
                        seconds = parsedate_to_datetime(retry).timestamp() - self.quota.clock()
                    except (ValueError, TypeError):
                        seconds = 60
                self.quota.defer(max(1, seconds))
                continue
            if response.status_code >= 500:
                failures += 1
                if failures < 3:
                    self.quota.defer(2 ** failures)
                    continue
            if response.status_code != 200:
                raise RuntimeError(f'Wordstat HTTP {response.status_code}；检查权限、地区参数或稍后续跑。')
            data = response.json()
            if not isinstance(data, dict) or 'error' in data:
                raise ValueError('Wordstat 返回结构异常，未标记完成')
            return data
