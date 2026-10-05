"""Behavior tests; no paid generation or external publication."""
import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.promotion import Promotion, Profile, CHANNELS, KST, router
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.web = Path(self.temp.name) / 'web'
        (self.web / 'admin').mkdir(parents=True)
        (self.web / 'admin/marketing-products.json').write_text(json.dumps({'products':[{'kind':'saju','product_id':'today','name':'오늘 운세','confirmed_results':[]}]}))
        self.s = Promotion(Path(self.temp.name), self.web)
        self.s.identities = lambda: []
        self.env = patch.dict('os.environ', {'PROMO_GEMINI_API_KEY':'test', 'PROMO_IG_ROADLOG_SAJU_TOKEN':'test', 'PROMO_IG_MUMUNG_FACT_TOKEN':'test', 'THREADS_ACCESS_TOKEN':'test'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_idempotent_and_budget(self):
        a = self.s.enqueue('test-once', False)
        self.assertEqual(a, self.s.enqueue('test-once', False))
        with self.assertRaises(ValueError): self.s.enqueue('test-again', False)
        with self.s.db() as c: c.execute("UPDATE jobs SET status='FAILED'")
        p = Profile(monthly_budget=1000, prompt='test').model_dump()
        self.s.save(p)
        with self.assertRaises(ValueError): self.s.enqueue('test-third', False)
        self.assertEqual(self.s.state()['reserved_won'],1000)

    def test_hours_and_schedule(self):
        p = Profile(prompt='test', enabled=True, times=['09:00','12:00']).model_dump()
        self.s.save(p)
        now = datetime(2026,10,5,9,0,tzinfo=KST)
        self.s.tick_schedule(now); self.s.tick_schedule(now)
        self.assertEqual(len(self.s.state()['jobs']),1)
        p['times']=['09:30']
        with self.assertRaises(ValueError): self.s.save(p)
        p['times']=['09:00','09:00']
        with self.assertRaises(ValueError): self.s.save(p)
        p['times']=['09:00']; p['enabled']=False
        self.s.save(p)
        self.assertEqual(self.s.state()['jobs'][0]['status'],'CANCELLED')

    def test_reference_private_and_auth(self):
        buff=io.BytesIO(); Image.new('RGB',(25,25)).save(buff,'PNG')
        ident=self.s.add_reference(base64.b64encode(buff.getvalue()).decode())
        def admin(token):
            if token!='Bearer admin': raise HTTPException(403)
        app=FastAPI();app.include_router(router(self.s,admin))
        client=TestClient(app)
        self.assertEqual(client.get('/api/admin/promotion').status_code,403)
        self.assertEqual(client.get('/api/admin/promotion/reference/'+ident).status_code,403)
        self.assertEqual(client.get('/api/admin/promotion/reference/'+ident,headers={'Authorization':'Bearer admin'}).status_code,200)
        self.assertEqual(client.get('/api/promotion/images/'+ident+'/gemini.key').status_code,404)
        self.assertNotIn('test',json.dumps(self.s.state()['configured']))

    def test_plan_rejects_duplicate_channel(self):
        self.s.gemini=lambda *a:[{'text':json.dumps({'channels':[{'channel':CHANNELS[0]}]*3})}]
        with self.assertRaises(ValueError): self.s.plan(self.s.profile())

    def test_publish_uncertainty_and_no_repetition(self):
        self.s.identities=lambda:[dict(channel=ch,id='123',username=ch.split(':')[1]) for ch in CHANNELS]
        self.s.ready_container=lambda *a:None
        calls=[]
        def graph(ch,method,path,data=None):
            calls.append((ch,path))
            if path.endswith('/media_publish') or path.endswith('/threads_publish'):raise RuntimeError('sensitive key')
            return {'id':'111'}
        self.s.graph=graph
        ident=self.s.enqueue('publish-test')
        result={'channels':[{'channel':ch,'caption':'copy','images':[] if ch.startswith('threads') else ['/a.jpg','/b.jpg']} for ch in CHANNELS]}
        with self.s.db() as c:c.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(result),ident))
        job={'id':ident,'result':json.dumps(result)}
        self.s.publish(job)
        n=len(calls);self.s.publish(job)
        self.assertEqual(len(calls),n)
        s=self.s.state()['jobs'][0]
        self.assertEqual(s['status'],'PARTIAL')
        self.assertEqual([r['status'] for r in s['receipts']],['UNCERTAIN']*3)
        self.assertNotIn('sensitive',json.dumps(s))

    def test_generation_worker_and_single_publish(self):
        ident=self.s.enqueue('preview-test')
        def generate(job):
            with self.s.db() as c:c.execute("UPDATE jobs SET status='READY',result=? WHERE id=?",(json.dumps({'channels':[]}),job['id']))
        self.s.generate=generate
        self.s.step()
        self.assertEqual(self.s.state()['jobs'][0]['status'],'READY')
        self.s.queue_publish(ident)
        with self.assertRaises(ValueError): self.s.queue_publish(ident)

if __name__=='__main__':unittest.main()
