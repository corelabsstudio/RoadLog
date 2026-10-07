"""Personal developer journal: verified copy, independent durable scheduler."""
import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from .social_voice import validate as validate_voice, summary as voice_summary

CHANNEL = 'threads:mumung_fact'
KST = ZoneInfo('Asia/Seoul')
DEFAULT = {'enabled': False, 'times': ['09:00', '12:00', '18:00', '21:00']}
BLOCKING = ('QUEUED', 'PREPARING', 'UNCERTAIN', 'PUBLISHED_UNVERIFIED', 'INTERRUPTED')


class DeveloperThreads:
    def __init__(self, promotion):
        self.client = promotion
        self.worker = None
        with self.db() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS developer_settings(key TEXT PRIMARY KEY,value TEXT);
              CREATE TABLE IF NOT EXISTS developer_sources(id TEXT PRIMARY KEY,body TEXT);
              CREATE TABLE IF NOT EXISTS developer_posts(id TEXT PRIMARY KEY, source_id TEXT UNIQUE,
              slot TEXT UNIQUE, created TEXT, format_id TEXT, caption TEXT, status TEXT,
              container TEXT, media TEXT, url TEXT, error TEXT);''')

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.client.path, timeout=20)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def library(self):
        library = json.loads(Path(__file__).with_name('developer_threads.json').read_text(encoding='utf-8'))
        with self.db() as c:
            library['sources'] += [json.loads(r[0]) for r in c.execute('SELECT body FROM developer_sources ORDER BY rowid')]
        return library

    def add_source(self, source):
        source = {k: v.strip() for k, v in source.items()}
        for fmt in self.library()['formats']:
            self.compose(source, fmt['id'])
        if not source['evidence']:
            raise ValueError('실제 작업의 확인 근거를 입력해주세요.')
        source['id'] = uuid.uuid4().hex
        with self.db() as c:
            if any(json.loads(r[0]).get('problem') == source['problem'] and json.loads(r[0]).get('solution') == source['solution']
                   for r in c.execute('SELECT body FROM developer_sources')):
                raise ValueError('같은 문제와 해결 방법이 이미 등록되었습니다.')
            c.execute('INSERT INTO developer_sources VALUES(?,?)', (source['id'], json.dumps(source, ensure_ascii=False)))
        return source['id']

    def profile(self):
        with self.db() as c:
            row = c.execute("SELECT value FROM developer_settings WHERE key='profile'").fetchone()
        return json.loads(row[0]) if row else dict(DEFAULT)

    def identity(self):
        if not self.client.token(CHANNEL):
            raise ValueError('mumung_fact Threads 전용 토큰이 필요합니다.')
        me = self.client.graph(CHANNEL, 'GET', 'me', {'fields': 'id,username'})
        if me.get('username') != 'mumung_fact' or not str(me.get('id', '')).isdigit():
            raise ValueError('개인 개발 기록의 대상은 Threads @mumung_fact여야 합니다.')
        return me

    def has_pending(self, c):
        return c.execute('SELECT 1 FROM developer_posts WHERE status IN (' + ','.join('?' for _ in BLOCKING) + ')', BLOCKING).fetchone()

    def save(self, profile):
        profile = dict(profile)
        reviewed = profile.pop('reviewed_interrupted', False)
        times = profile['times']
        if not times or len(times) > 24 or len(times) != len(set(times)) or any(not re.fullmatch(r'(?:[01]\d|2[0-3]):00', t) for t in times):
            raise ValueError('개인 계정 발행 시간은 중복 없이 1시간 단위로 지정해주세요.')
        if profile['enabled']:
            self.identity()
            with self.db() as c:
                # 🛑 서버 재시작으로 중단된 글만 관리자가 실제 게시 여부를 확인했다고 밝히면 풀 수 있다 (2026-10-07).
                #    소재는 이미 사용 처리돼 있어 다시 쓰이지 않는다. UNCERTAIN 등 다른 불확실 상태는 풀지 않는다.
                if reviewed:
                    c.execute("UPDATE developer_posts SET status='REVIEWED' WHERE status='INTERRUPTED'")
                if c.execute("SELECT 1 FROM developer_posts WHERE status IN ('UNCERTAIN','PUBLISHED_UNVERIFIED','INTERRUPTED')").fetchone():
                    raise ValueError('이전 개인 글의 게시 여부를 먼저 확인해주세요.')
            if not self.remaining():
                raise ValueError('확인된 개발 소재를 추가해야 예약을 켤 수 있습니다.')
        with self.db() as c:
            c.execute("INSERT OR REPLACE INTO developer_settings VALUES('profile',?)", (json.dumps(profile),))
            c.execute("DELETE FROM developer_settings WHERE key='notice'")
            if not profile['enabled']:
                c.execute("UPDATE developer_posts SET status='READY' WHERE status='QUEUED'")

    def remaining(self):
        with self.db() as c:
            used = {r[0] for r in c.execute('SELECT source_id FROM developer_posts')}
        return [s for s in self.library()['sources'] if s['id'] not in used]

    @staticmethod
    def compose(source, format_id):
        if format_id == 'numbered-process':
            paragraphs = [source['hook'], '1. ' + source['problem'], '2. ' + source['solution'], '3. ' + source['result'], source['lesson'], source['question']]
        elif format_id == 'result-then-process':
            paragraphs = [source['result'], source['hook'] + '\n' + source['problem'], source['solution'], source['lesson'], source['question']]
        else:
            paragraphs = [source['hook'], source['problem'], source['solution'], source['result'], source['lesson'], source['question']]
        caption = '\n\n'.join(p for p in paragraphs if p.strip())
        validate_voice(caption)
        if not 1 <= len(caption) <= 500 or re.search(r'https?://|프로필\s*링크|구매|할인|API[_ -]?KEY|access_token|Bearer\s', caption, re.I):
            raise ValueError('개인 개발 기록은 500자 이하이며 홍보 링크·비밀값을 포함할 수 없습니다.')
        return caption

    def enqueue(self, slot, publish=False):
        library = self.library()
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT id FROM developer_posts WHERE slot=?', (slot,)).fetchone()
            if old:
                return old[0]
            if self.has_pending(c):
                raise ValueError('진행 중이거나 게시 확인이 필요한 개인 글이 있습니다.')
            used = {r[0] for r in c.execute('SELECT source_id FROM developer_posts')}
            source = next((s for s in library['sources'] if s['id'] not in used), None)
            if not source:
                raise ValueError('확인된 개발 소재를 모두 사용했습니다. 새 실제 기록이 필요합니다.')
            count = c.execute('SELECT count(*) FROM developer_posts').fetchone()[0]
            fmt = library['formats'][count % len(library['formats'])]
            caption = self.compose(source, fmt['id'])
            ident = uuid.uuid4().hex
            c.execute('INSERT INTO developer_posts VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                      (ident, source['id'], slot, datetime.now(KST).isoformat(), fmt['id'], caption,
                       'QUEUED' if publish else 'READY', None, None, None, None))
        return ident

    def queue_publish(self, ident):
        self.identity()
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            if self.has_pending(c):
                raise ValueError('진행 중이거나 게시 확인이 필요한 개인 글이 있습니다.')
            if c.execute("UPDATE developer_posts SET status='QUEUED' WHERE id=? AND status='READY'", (ident,)).rowcount != 1:
                raise ValueError('아직 게시하지 않은 미리보기만 발행할 수 있습니다.')

    def update(self, ident, **fields):
        with self.db() as c:
            c.execute('UPDATE developer_posts SET ' + ','.join(k + '=?' for k in fields) + ' WHERE id=?', (*fields.values(), ident))

    def state(self):
        library = self.library()
        with self.db() as c:
            posts = [dict(r) for r in c.execute('SELECT * FROM developer_posts ORDER BY created DESC LIMIT 30')]
            notice = c.execute("SELECT value FROM developer_settings WHERE key='notice'").fetchone()
        for post in posts:
            post['format_reference'] = next((f for f in library['formats'] if f['id'] == post['format_id']), {})
            source = next((s for s in library['sources'] if s['id'] == post['source_id']), {})
            post['evidence'] = source.get('evidence', '이전 소재 기록')
        return {'account': 'mumung_fact', 'profile': self.profile(), 'configured': bool(self.client.token(CHANNEL)),
                'remaining_sources': len(self.remaining()), 'posts': posts, 'version': library['version'], 'voice': voice_summary(),
                'notice': notice[0] if notice else '실제 확인된 개발 기록만 게시합니다. 소재 소진·오류 시 예약을 멈춥니다.'}

    def pause(self, notice=None):
        p = self.profile()
        p['enabled'] = False
        with self.db() as c:
            c.execute("INSERT OR REPLACE INTO developer_settings VALUES('profile',?)", (json.dumps(p),))
            if notice:
                c.execute("INSERT OR REPLACE INTO developer_settings VALUES('notice',?)", (notice,))

    def step(self):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute("SELECT * FROM developer_posts WHERE status='QUEUED' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return
            c.execute("UPDATE developer_posts SET status='PREPARING' WHERE id=?", (row['id'],))
        status = 'PREPARING'
        try:
            uid = self.identity()['id']
            container = str(self.client.graph(CHANNEL, 'POST', uid + '/threads', {'media_type': 'TEXT', 'text': row['caption']}).get('id', ''))
            self.client.ready_container(CHANNEL, container)
            status = 'UNCERTAIN'
            self.update(row['id'], status=status, container=container)
            media = str(self.client.graph(CHANNEL, 'POST', uid + '/threads_publish', {'creation_id': container}).get('id', ''))
            if not media.isdigit():
                raise ValueError('개인 글 게시 ID 확인이 필요합니다. 자동 재시도하지 않습니다.')
            status = 'PUBLISHED_UNVERIFIED'
            self.update(row['id'], status=status, media=media)
            detail = self.client.graph(CHANNEL, 'GET', media, {'fields': 'id,username,text,permalink'})
            if detail.get('username') != 'mumung_fact' or detail.get('text') != row['caption'] or not re.fullmatch(r'https://(?:www\.)?threads\.(?:com|net)/@mumung_fact/post/[^/?#]+', detail.get('permalink', '')):
                raise ValueError('개인 글 게시 후 계정·본문·주소 확인이 필요합니다.')
            self.update(row['id'], status='PUBLISHED', url=detail['permalink'])
        except Exception as error:
            self.update(row['id'], status='FAILED' if status == 'PREPARING' else status, error=self.client.safe_error(error))
            self.pause('개인 글 처리에 실패했습니다. 아래 게시 내역을 확인해주세요.')

    def tick(self, now):
        p = self.profile()
        if p['enabled'] and now.strftime('%H:%M') in p['times']:
            try:
                self.enqueue('schedule-' + now.strftime('%Y%m%d-%H%M'), True)
            except ValueError as error:
                self.pause(str(error))

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        with self.db() as c:
            c.execute("UPDATE developer_posts SET status='INTERRUPTED',error='서버 재시작으로 중단되었습니다. 게시 여부를 먼저 확인해주세요.' WHERE status='PREPARING'")
            uncertain = c.execute("SELECT 1 FROM developer_posts WHERE status IN ('INTERRUPTED','UNCERTAIN','PUBLISHED_UNVERIFIED')").fetchone()
        if uncertain:
            self.pause('이전 개인 글의 게시 여부 확인이 필요합니다.')
        self.worker = threading.Thread(target=self.loop, name='personal-threads-worker', daemon=True)
        self.worker.start()

    def loop(self):
        while not self.client.stop.is_set():
            try:
                self.tick(datetime.now(KST))
                self.step()
            except Exception:
                self.pause('개인 글 처리 중 오류가 발생했습니다. 내역을 확인해주세요.')
            self.client.stop.wait(10)
