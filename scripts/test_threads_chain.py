"""Verify parent links and interruption receipts without publishing externally."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.promotion import Promotion
from modules import social_voice

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Promotion(Path(self.tmp.name), Path(self.tmp.name))
        self.s.configured = lambda: {'gemini':True}
        self.s.identities = lambda: [{'channel':'threads:roadlog_saju','id':'123'}]
        self.s.ready_container = lambda *a: None
        self.parts = ['읽음 표시만 보고 기다려본 적 있어?', '근데 읽었다고 마음까지 알 수는 없잖아.', '어떤 풀이가 있는지 봐봐~ https://roadlog.co.kr/#p/match']
        self.item = {'channel':'threads:roadlog_saju','caption':self.parts[0],'thread_parts':self.parts}
        self.id = self.s.enqueue('chain-test')
        self.job = {'id':self.id,'result':json.dumps({'channels':[self.item]})}
        self.creates = []
        self.finals = 0
        self.fail = False
        self.bad_parent = False
        def graph(ch, method, path, data=None):
            if path.endswith('/threads'):
                self.creates.append(data)
                return {'id':str(100+len(self.creates))}
            if path.endswith('/threads_publish'):
                self.finals += 1
                if self.fail and self.finals == 2: raise TimeoutError('secret')
                return {'id':str(200+self.finals)}
            n = int(path)-201
            detail = {'username':'roadlog_saju','text':self.parts[n], 'permalink':'https://www.threads.com/@roadlog_saju/post/test'+str(n)}
            if n: detail['replied_to'] = {'id':'999' if self.bad_parent else str(200+n)}
            return detail
        self.s.graph = graph

    def tearDown(self): self.tmp.cleanup()

    def test_connected_parts_are_verified_individually(self):
        self.s.publish(self.job)
        self.assertNotIn('reply_to_id',self.creates[0])
        self.assertEqual([x['reply_to_id'] for x in self.creates[1:]],['201','202'])
        self.assertEqual([p['status'] for p in self.s.state()['jobs'][0]['thread_receipts']],['PUBLISHED']*3)
        with self.s.db() as c:
            self.assertEqual(c.execute('SELECT status FROM receipts').fetchone()[0],'PUBLISHED')

    def test_second_final_timeout_never_reposts_root_or_reply(self):
        self.fail = True
        self.s.publish(self.job)
        self.s.publish(self.job)
        self.assertEqual(self.finals,2)
        state = self.s.state()['jobs'][0]
        self.assertEqual([p['status'] for p in state['thread_receipts']],['PUBLISHED','UNCERTAIN'])
        self.assertEqual(state['receipts'][0]['status'],'UNCERTAIN')
        self.assertNotIn('secret',json.dumps(state))

    def test_wrong_parent_stops_before_third_part(self):
        self.bad_parent = True
        self.s.publish(self.job)
        self.assertEqual(self.finals,2)
        self.assertEqual(self.s.state()['jobs'][0]['thread_receipts'][1]['status'],'PUBLISHED_UNVERIFIED')

    def test_report_voice_rejected_without_changing_text(self):
        with self.assertRaises(ValueError): social_voice.validate('자동화를 반영했다. 테스트로 확인했다.')
        social_voice.validate('자동화 넣었어~! 근데 여기서 또 막히는거야ㅋㅋ')

if __name__ == '__main__': unittest.main()
