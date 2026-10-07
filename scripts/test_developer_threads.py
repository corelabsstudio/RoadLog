"""Personal Threads behavior tests; external APIs are mocked."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.promotion import Promotion, KST, router
from modules.developer_threads import CHANNEL
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'PROMO_THREADS_MUMUNG_FACT_TOKEN': 'personal', 'THREADS_ACCESS_TOKEN': 'brand'})
        self.env.start()
        self.parent = Promotion(Path(self.temp.name), Path(self.temp.name))
        self.s = self.parent.developer
        self.calls = []
        self.parent.ready_container = lambda *args: None
        def graph(channel, method, path, data=None):
            self.calls.append((channel, method, path, data))
            if path == 'me': return {'id': '123', 'username': 'mumung_fact'}
            if path.endswith('/threads'): return {'id': '456'}
            if path.endswith('/threads_publish'): return {'id': '789'}
            return {'id': '789', 'username': 'mumung_fact', 'text': self.s.state()['posts'][0]['caption'],
                    'permalink': 'https://www.threads.com/@mumung_fact/post/test'}
        self.parent.graph = graph

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_all_verified_sources_fit_every_format_without_ad_or_links(self):
        for source in self.s.library()['sources']:
            self.assertTrue(source['evidence'])
            for fmt in self.s.library()['formats']:
                text = self.s.compose(source, fmt['id'])
                self.assertLessEqual(len(text), 500)
                self.assertNotIn('https://', text)
                self.assertNotIn('로드로그', text)
                self.assertIn(source['solution'], text)

    def test_token_routing_and_account_mismatch(self):
        self.assertEqual(self.parent.token(CHANNEL), 'personal')
        self.assertEqual(self.parent.token('threads:roadlog_saju'), 'brand')
        self.parent.graph = lambda *args: {'id': '123', 'username': 'roadlog_saju'}
        with self.assertRaisesRegex(ValueError, 'mumung_fact'): self.s.identity()

    def test_schedule_is_independent_and_same_slot_is_idempotent(self):
        self.s.save({'enabled': True, 'times': ['09:00','12:00','18:00','21:00']})
        now = datetime(2026, 10, 7, 18, 0, tzinfo=KST)
        self.s.tick(now); self.s.tick(now)
        self.assertEqual(len(self.s.state()['posts']), 1)
        self.assertFalse(self.parent.profile()['enabled'])
        self.assertTrue(self.s.profile()['enabled'])
        self.s.step(); self.s.step()
        self.assertEqual(self.s.state()['posts'][0]['status'], 'PUBLISHED')
        self.assertEqual(sum(c[2].endswith('/threads_publish') for c in self.calls), 1)
        self.assertTrue(all(c[0] == CHANNEL for c in self.calls))

    def test_timeout_after_final_call_never_republishes(self):
        self.s.save({'enabled': True, 'times': ['21:00']})
        original = self.parent.graph
        def timeout(channel, method, path, data=None):
            if path.endswith('/threads_publish'): raise RuntimeError('secret token must not leak')
            return original(channel, method, path, data)
        self.parent.graph = timeout
        self.s.enqueue('timeout-test', True); self.s.step(); self.s.step()
        state = self.s.state()
        self.assertEqual(state['posts'][0]['status'], 'UNCERTAIN')
        self.assertFalse(state['profile']['enabled'])
        self.assertNotIn('secret', json.dumps(state))
        with self.assertRaises(ValueError): self.s.enqueue('next-test', True)

    def test_exhaustion_does_not_invent_or_recycle_sources(self):
        count = len(self.s.library()['sources'])
        for i in range(count): self.s.enqueue('preview-' + str(i))
        self.assertEqual(len({p['source_id'] for p in self.s.state()['posts']}), count)
        self.assertEqual(self.s.state()['remaining_sources'], 0)
        with self.assertRaisesRegex(ValueError, '모두 사용'): self.s.enqueue('extra-preview')

    def test_preview_not_published_until_requested(self):
        ident = self.s.enqueue('preview-test')
        self.s.step()
        self.assertEqual(self.calls, [])
        self.s.queue_publish(ident); self.s.step()
        self.assertEqual(self.s.state()['posts'][0]['status'], 'PUBLISHED')
        with self.assertRaises(ValueError): self.s.queue_publish(ident)

    def test_new_actual_source_is_persistent_and_duplicate_or_ad_rejected(self):
        source = dict(self.s.library()['sources'][0])
        source.pop('id')
        source['problem'] = '실제 작업 기록으로 확인한 별도 문제.'
        source['solution'] = '실제로 수행한 해결 방법.'
        ident = self.s.add_source(source)
        self.assertIn(ident, [s['id'] for s in self.s.library()['sources']])
        with self.assertRaisesRegex(ValueError, '이미 등록'): self.s.add_source(source)
        source['solution'] = 'https://example.com 구매하세요'
        with self.assertRaises(ValueError): self.s.add_source(source)

    def test_admin_required_and_bad_time_rejected(self):
        app = FastAPI()
        def admin(token):
            if token != 'Bearer admin': raise HTTPException(403)
        app.include_router(router(self.parent, admin))
        client = TestClient(app)
        self.assertEqual(client.post('/api/admin/promotion/personal/jobs', json={'key':'private-test'}).status_code, 403)
        self.assertEqual(client.put('/api/admin/promotion/personal/profile', headers={'Authorization':'Bearer admin'}, json={'enabled':False,'times':['25:00']}).status_code, 400)
        self.assertEqual(client.post('/api/admin/promotion/personal/jobs', headers={'Authorization':'Bearer admin'}, json={'key':'preview-auth-test'}).status_code, 200)


if __name__ == '__main__': unittest.main()
