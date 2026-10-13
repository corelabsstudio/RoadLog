"""Free public curses: no billing, isolated ownership, retries, nights and locale."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='roadlog-free-test-')
os.environ['SUPABASE_URL'] = ''
os.environ['SUPABASE_KEY'] = ''
os.environ['APP_ENV'] = 'test'

from fastapi.testclient import TestClient
import server
from modules import jeoju, jeoju_free, saju_writer, site_locale
from test_jeoju_nights import fake_call

ORDER = dict(target='친구', nick='Test Goblin', year='', sin='They never return borrowed things', spot='입')


class FreeCurseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(jeoju, '_FILE', Path(self.tmp.name)/'results.json'),
                        patch.object(jeoju_free, '_USAGE', Path(self.tmp.name)/'usage.json'),
                        patch.object(saju_writer, '_call', side_effect=fake_call)]
        for p in self.patches: p.start()
        self.client = TestClient(server.app)
        server.limiter._hits.clear()

    def tearDown(self):
        self.client.close()
        for p in self.patches: p.stop()
        self.tmp.cleanup()

    def cast(self, lv=1, ritual='a'*24, client=None, **extra):
        return (client or self.client).post('/api/jeoju/free', json={**ORDER, 'level': lv, 'ritual': ritual, **extra})

    def test_all_seven_levels_without_login_or_payment_and_preserved_upgrade(self):
        first = None
        with patch.object(server, '_token_user', side_effect=AssertionError('login used')), \
             patch.object(server.lamps_ops, 'owns', side_effect=AssertionError('billing used')):
            for lv in range(1, 8):
                r = self.cast(lv)
                self.assertEqual(r.status_code, 200, r.text)
                doc = r.json()['doc']
                self.assertEqual(doc['level'], lv)
                first = first or doc['line']
                self.assertEqual(doc['line'], first)
        self.assertEqual(len(doc['nights']), 13)
        self.assertTrue(doc['nights'][0]['open'])
        self.assertEqual(doc['nights'][1]['text'], '')
        self.assertIn('HttpOnly', r.headers['set-cookie'])
        self.assertEqual(len(self.client.get('/api/jeoju/free/mine').json()['items']), 1)

    def test_multiple_people_and_guest_cannot_read_other_guests_or_paid_records(self):
        self.assertEqual(self.cast(1).status_code, 200)
        self.assertEqual(self.cast(4, 'b'*24, nick='Other Goblin').status_code, 200)
        self.assertEqual(len(self.client.get('/api/jeoju/free/mine').json()['items']), 2)
        with TestClient(server.app) as other:
            self.assertEqual(other.get('/api/jeoju/free/'+'a'*24).status_code, 404)
            self.assertEqual(other.get('/api/jeoju/free/mine').json()['items'], [])
        jeoju.save('buyer@example.com', 'c'*24, 'd'*32, ORDER, {'level':7,'title':'paid','line':'paid'})
        self.assertEqual(self.client.get('/api/jeoju/free/'+'c'*24).status_code, 404)
        self.assertEqual(jeoju.get('buyer@example.com','c'*24)['doc']['title'], 'paid')

    def test_retry_is_idempotent_and_tampered_identity_is_rejected(self):
        self.assertEqual(self.cast().status_code, 200)
        with patch.object(jeoju, 'write', side_effect=AssertionError('regenerated')):
            self.assertEqual(self.cast().status_code, 200)
        self.assertEqual(self.cast(nick='Different target').status_code, 400)
        self.assertEqual(self.cast(8).status_code, 400)
        self.assertEqual(self.cast(4, 'b'*24, spot='').status_code, 400)

    def test_failure_refunds_budget_and_daily_cap_persists(self):
        with patch.object(jeoju, 'write', side_effect=RuntimeError('fixture failure')):
            self.assertEqual(self.cast().status_code, 503)
        self.assertIn('"used": 0', jeoju_free._USAGE.read_text())
        with patch.object(jeoju_free, 'DAILY_CAP', 1):
            self.assertEqual(self.cast().status_code, 200)
            self.assertEqual(self.cast(1,'b'*24).status_code, 429)
        self.assertEqual(self.cast().status_code, 200)

    def test_guest_night_access_opens_by_date_without_email(self):
        r = self.cast(7)
        visitor = jeoju_free.owner(server.Request({'type':'http','headers':[(b'cookie', ('rl_jeoju_guest='+self.client.cookies.get('rl_jeoju_guest')).encode())]}))
        doc = jeoju.get(visitor, 'a'*24)['doc']
        with patch.object(jeoju.time, 'time', return_value=(doc['nights'][1]['at']+1)/1000):
            later = self.client.get('/api/jeoju/free/'+'a'*24).json()['doc']
            self.assertTrue(later['nights'][1]['text'])
        self.assertEqual(jeoju.due_notices(doc['nights'][2]['at']+1), [])

    def test_country_default_and_english_country_prompt(self):
        self.assertEqual(site_locale.locate('8.8.8.8','ko')['language'], 'en')
        self.assertEqual(site_locale.locate('168.126.63.1','en-US')['language'], 'ko')
        self.assertEqual(site_locale.locate('127.0.0.1','ko-KR')['language'], 'ko')
        self.assertEqual(site_locale.locate('127.0.0.1','en-US')['language'], 'en')
        with patch.object(site_locale, 'locate', return_value={'language':'en','country':'US','country_name':'United States'}):
            r = self.cast(7, language='en')
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()['doc']['language'], 'en')
            system = saju_writer._call.call_args.args[0]
            self.assertIn('K-Curse', system)
            self.assertIn('United States', system)
            self.assertIn('Every customer-facing value must be natural English', system)
        self.assertIn('no-store', self.client.get('/api/site/locale').headers['cache-control'])

    def test_old_checkout_redirects_to_free_and_ads_uses_real_publisher(self):
        r=self.client.get('/pay.html?premium=jeoju_g', follow_redirects=False)
        self.assertEqual(r.status_code,303)
        self.assertEqual(r.headers['location'],'/?lv=jeoju_g')
        self.assertIn('pub-2523025753289844',self.client.get('/ads.txt').text)
        with patch.dict(os.environ, {'ADSENSE_CLIENT':'xxxx','ADSENSE_SLOT':'xxxx','JEOJU_ADS_ENABLED':'1'}):
            cfg=self.client.get('/api/ads/config').json()
            self.assertTrue(cfg['enabled'])
            self.assertEqual(cfg['slot'],'1812158500')
            self.assertNotIn('xxxx',cfg['client'])
        with patch.object(site_locale,'locate',return_value={'country':'GB','language':'en','country_name':'United Kingdom'}):
            self.assertFalse(self.client.get('/api/ads/config').json()['enabled'])


if __name__ == '__main__': unittest.main()
