"""Behavior tests; no paid generation or external publication."""
import base64
import copy
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
    def campaign(self, suffix='original'):
        return {'channels': [dict(channel=ch, topic=f'{i}-{suffix}', product_id='today',
                    caption=f'{i} {suffix} 마음을 살펴보세요. https://roadlog.co.kr/#p/today',
                    cards=[] if ch.startswith('threads:') else [dict(title=f'{suffix} 질문 {i}-{n}',
                        body=f'{suffix} 표현 방식을 살펴보세요.', scene=f'{suffix} scene {i}-{n}') for n in range(2)])
                    for i, ch in enumerate(CHANNELS)]}

    def history(self, plan):
        ident=self.s.enqueue('previous-campaign')
        with self.s.db() as c:c.execute("UPDATE jobs SET result=?,status='PUBLISHED' WHERE id=?",(json.dumps(plan),ident))

    def test_duplicate_replans_before_images_without_disabling_schedule(self):
        old=self.campaign();self.history(old)
        p=Profile(enabled=True).model_dump();self.s.save(p)
        replies=[old,self.campaign('fresh')];calls=[]
        def gemini(model,parts,config):
            calls.append(parts[0]['text']);return [{'text':json.dumps(replies.pop(0))}]
        self.s.gemini=gemini
        plan=self.s.plan(p)
        self.assertEqual(plan['channels'][0]['topic'],'0-fresh')
        self.assertEqual(len(calls),2)
        self.assertIn('중복',calls[1])
        self.assertTrue(self.s.profile()['enabled'])

    def test_repeated_duplicates_switch_to_original_catalog_plan(self):
        old=self.campaign();self.history(old);calls=[]
        def gemini(*args):calls.append(args);return [{'text':json.dumps(old)}]
        self.s.gemini=gemini
        result=self.s.plan(self.s.profile())
        self.assertEqual(len(calls),3)
        self.assertEqual(len({x['topic'] for x in result['channels']}),3)
        for item in result['channels']:
            before=next(x for x in old['channels'] if x['channel']==item['channel'])
            self.assertNotEqual(item['caption'],before['caption'])
            self.assertEqual(item['product_id'],'today')
            if item['channel'].startswith('threads:'):
                self.assertEqual(item['content_type'], 'conversation')
                self.assertNotIn('https://', item['caption'])
                self.assertNotIn('로드로그', item['caption'])
            else:
                self.assertIn('https://roadlog.co.kr/#p/today',item['caption'])
            self.assertLessEqual(len(item['caption']),500)
            for card in item['cards']:
                self.assertLessEqual(len(card['title']),28);self.assertLessEqual(len(card['body']),75)
                self.assertNotIn(card['scene'],[x['scene'] for x in before['cards']])

    def test_new_caption_with_reused_scene_also_replans(self):
        old=self.campaign();self.history(old)
        reused=copy.deepcopy(old)
        for x in reused['channels']:x['caption']='새로운 문장 '+x['caption']
        replies=[reused,self.campaign('changed')]
        self.s.gemini=lambda *args:[{'text':json.dumps(replies.pop(0))}]
        self.assertEqual(self.s.plan(self.s.profile())['channels'][0]['topic'],'0-changed')

    def test_network_failure_is_not_retried_as_content_duplication(self):
        calls=[]
        def fail(*args):calls.append(args);raise RuntimeError('timeout')
        self.s.gemini=fail
        with self.assertRaises(RuntimeError):self.s.plan(self.s.profile())
        self.assertEqual(len(calls),1)

    def test_duplicate_fallback_worker_stays_enabled_and_generates_four_new_images(self):
        old=self.campaign();self.history(old)
        p=Profile(enabled=True).model_dump();self.s.save(p)
        image_calls=[]
        raw=io.BytesIO();Image.new('RGB',(25,25)).save(raw,'PNG')
        def gemini(model,parts,config):
            if model.endswith('image'):
                image_calls.append(parts[0]['text']);return [{'inlineData':{'data':base64.b64encode(raw.getvalue()).decode()}}]
            return [{'text':json.dumps(old)}]
        self.s.gemini=gemini;self.s.render=lambda raw,card:raw
        ident=self.s.enqueue('schedule-recovery',True);self.s.step()
        job=next(j for j in self.s.state()['jobs'] if j['id']==ident)
        self.assertEqual(job['status'],'PUBLISH_QUEUED')
        self.assertEqual(len(image_calls),4);self.assertEqual(len(set(image_calls)),4)
        self.assertTrue(self.s.profile()['enabled'])
        self.assertEqual(job['receipts'],[])

    def test_historical_duplicate_recovery_is_idempotent_and_never_retries_a_post(self):
        ident=self.s.enqueue('schedule-old-failed',True)
        with self.s.db() as c:c.execute("UPDATE jobs SET status='FAILED',error=? WHERE id=?",('이전에 제작한 본문과 중복되어 발행하지 않았습니다.',ident))
        replacement=self.s.regenerate_duplicate(ident)
        self.assertEqual(replacement,self.s.regenerate_duplicate(ident))
        old=next(j for j in self.s.state()['jobs'] if j['id']==ident)
        self.assertEqual(old['status'],'REPLACED')
        with self.s.db() as c:
            c.execute("UPDATE jobs SET status='FAILED',error=? WHERE id=?",('이전에 제작한 본문과 중복되어 발행하지 않았습니다.',replacement))
        self.s.receipt(replacement,CHANNELS[0],'UNCERTAIN')
        with self.assertRaisesRegex(ValueError,'게시 시도 없는'):self.s.regenerate_duplicate(replacement)

    def test_catalog_rotation_continues_after_many_rounds(self):
        previous=[]
        for _ in range(20):
            result=self.s.fresh_catalog_plan(previous[-8:])
            self.assertEqual(self.s.duplicate_channels(result,previous[-8:]),[])
            previous.append(result)

    def test_thread_types_rotate_and_only_product_posts_link(self):
        previous = []
        for expected in ('conversation', 'checklist', 'product', 'conversation'):
            plan = self.s.fresh_catalog_plan(previous)
            thread = plan['channels'][2]
            self.assertEqual(thread['content_type'], expected)
            self.assertEqual('https://roadlog.co.kr/#p/today' in thread['caption'], expected == 'product')
            self.assertLessEqual(len(thread['caption']), 500)
            self.assertIn('오늘 해야 할 일', thread['caption'])
            for instagram in plan['channels'][:2]:
                self.assertIn('https://roadlog.co.kr/#p/today', instagram['caption'])
                self.assertEqual(len(instagram['cards']), 2)
            previous.insert(0, plan)

    def test_planner_conversation_drops_legacy_link_but_rejects_ad_copy(self):
        plan = self.campaign()
        self.s.gemini = lambda *args: [{'text': json.dumps(plan)}]
        result = self.s.plan_once(self.s.profile(), [], '')
        self.assertEqual(result['channels'][2]['content_type'], 'conversation')
        self.assertNotIn('https://', result['channels'][2]['caption'])
        plan['channels'][2]['caption'] = '로드로그에서 오늘 운세를 확인하세요. https://roadlog.co.kr/#p/today'
        with self.assertRaisesRegex(ValueError, '독립적인 내용'):
            self.s.plan_once(self.s.profile(), [], '')

    def test_planner_product_requires_exact_single_product_link(self):
        previous = self.campaign('previous')
        previous['channels'][2]['content_type'] = 'checklist'
        plan = self.campaign('new')
        self.s.gemini = lambda *args: [{'text': json.dumps(plan)}]
        result = self.s.plan_once(self.s.profile(), [json.dumps(previous)], '')
        self.assertEqual(result['channels'][2]['content_type'], 'product')
        plan['channels'][2]['caption'] += ' https://example.com/'
        with self.assertRaisesRegex(ValueError, '주소 하나'):
            self.s.plan_once(self.s.profile(), [json.dumps(previous)], '')

    def test_verified_format_reaches_prompt_and_result_and_rotates(self):
        captured = []
        def model(model, parts, config):
            captured.append(parts[0]['text'])
            return [{'text': json.dumps(self.campaign())}]
        self.s.gemini = model
        result = self.s.plan_once(self.s.profile(), [], '')
        source = result['channels'][2]['format_reference']
        self.assertEqual(source['id'], 'question-options')
        self.assertEqual(source['observed_reactions']['replies'], '314')
        self.assertIn(source['structure'], captured[0])
        self.assertIn('사연·표현·사진·개인 경험은 복제하지', captured[0])
        self.assertEqual(self.s.select_thread_format('conversation', [result])['id'], 'two-values')
        self.assertEqual(self.s.select_thread_format('product', [result])['id'], 'criteria-list')
        self.assertTrue(all('format_reference' not in c for c in result['channels'][:2]))
        self.assertEqual(self.s.state()['threads_writing']['format_count'], 3)

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

    def test_schedule_without_prompt_uses_roadlog_defaults(self):
        p = Profile(enabled=True, times=['12:00']).model_dump()
        self.s.save(p)
        self.s.tick_schedule(datetime(2026,10,5,12,0,tzinfo=KST))
        self.assertEqual(self.s.state()['jobs'][0]['status'], 'QUEUED')
        captured = []
        def gemini(model, parts, config):
            captured.append(parts[0]['text'])
            raise RuntimeError('stop before paid generation')
        self.s.gemini = gemini
        with self.assertRaises(RuntimeError): self.s.plan(self.s.profile())
        self.assertIn('무냥이', captured[0])
        self.assertIn('오늘 운세', captured[0])
        self.assertIn('최근 홍보와 다른 내용', captured[0])

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

    def test_bipedal_mascot_reaches_planner_and_every_image_with_custom_style(self):
        p = Profile(prompt='Photorealistic cat sitting beside a mirror.').model_dump()
        captured = []
        def stop_planner(model, parts, config):
            captured.append(parts[0]['text'])
            raise RuntimeError('captured')
        self.s.gemini = stop_planner
        with self.assertRaises(RuntimeError): self.s.plan(p)
        self.assertIn('stands and walks upright on TWO hind feet', captured[0])
        self.assertIn('NOT to ordinary four-legged cat anatomy', captured[0])
        self.assertIn('WARDROBE IS MANDATORY', captured[0])
        self.assertIn('SIGNATURE MOON (required in EVERY card)', captured[0])
        self.assertIn('pastel rainbow saekdong patchwork', captured[0])
        channels = [dict(channel=ch, cards=[] if ch.startswith('threads:') else
                        [dict(title='title', body='body', scene='A cat crouching on the floor.') for _ in range(2)])
                    for ch in CHANNELS]
        self.s.plan = lambda profile: {'channels': channels}
        raw = io.BytesIO(); Image.new('RGB', (25, 25)).save(raw, 'PNG')
        def image_model(model, parts, config):
            captured.append(parts[0]['text'])
            return [{'inlineData': {'data': base64.b64encode(raw.getvalue()).decode()}}]
        self.s.gemini = image_model
        self.s.render = lambda image, card: image
        ident = self.s.enqueue('mascot-test')
        self.s.generate(dict(id=ident, profile=json.dumps(p), auto=False))
        self.assertEqual(len(captured), 5)
        for prompt in captured[1:]:
            self.assertIn('stands and walks upright on TWO hind feet', prompt)
            self.assertIn('front paws are arms and hands', prompt)
            self.assertIn('full mint hanbok', prompt)
            self.assertIn('both arms inside their sleeves', prompt)
            self.assertIn('both legs inside their trousers', prompt)
            self.assertIn('no exposed torso or slipping clothes', prompt)
            self.assertIn('golden crescent floating just above the head', prompt)
            self.assertIn('A background moon does not satisfy', prompt)
            self.assertIn('lower 65 percent', prompt)
            self.assertIn('pastel rainbow saekdong hood', prompt)
            self.assertIn('brown eyes and pink nose', prompt)
            self.assertIn('adapt all poses to the mandatory bipedal mascot', prompt)
            self.assertNotIn('retain natural proportions', prompt)
        self.assertEqual(self.s.state()['jobs'][0]['status'], 'READY')

    def test_plan_rejects_duplicate_channel(self):
        self.s.gemini=lambda *a:[{'text':json.dumps({'channels':[{'channel':CHANNELS[0]}]*3})}]
        with self.assertRaises(ValueError): self.s.plan(self.s.profile())

    def test_plan_accepts_common_questions_but_rejects_fictional_anecdotes(self):
        channels = [dict(channel=ch, topic=str(i), product_id='today',
                         caption='대화가 자꾸 엇갈리나요? https://roadlog.co.kr/#p/today',
                         cards=[] if ch.startswith('threads:') else [dict(title='마음이 궁금한가요?', body='표현 방식이 다른지 살펴보세요.', scene='A cat under warm lantern light.') for _ in range(2)])
                    for i, ch in enumerate(CHANNELS)]
        self.s.gemini = lambda *a: [{'text': json.dumps({'channels': channels})}]
        self.assertEqual(len(self.s.plan(self.s.profile())['channels']), 3)
        for text in ['(가상 상황: 3년 차 커플 B님)', 'A님은 상대의 침묵이 답답하다고 합니다.', '가상의 인물 이야기']:
            with self.subTest(text=text):
                channels[2]['caption'] = text + ' https://roadlog.co.kr/#p/today'
                with self.assertRaisesRegex(ValueError, '공감 질문'): self.s.plan(self.s.profile())
        channels[2]['caption'] = '연락할 타이밍이 고민인가요? https://roadlog.co.kr/#p/today'
        channels[0]['cards'][0]['body'] = '(가상 사례)'
        with self.assertRaisesRegex(ValueError, '공감 질문'): self.s.plan(self.s.profile())

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

    def test_publication_requires_matching_copy_and_two_children(self):
        self.s.identities=lambda:[dict(channel=ch,id='123',username=ch.split(':')[1]) for ch in CHANNELS]
        self.s.ready_container=lambda *a:None
        def graph(ch,method,path,data=None):
            if method=='POST':return {'id':'111'}
            return {'id':'111','username':'roadlog_saju','text':'copy','caption':'copy','permalink':'https://www.instagram.com/p/test/','media_type':'CAROUSEL_ALBUM','children':{'data':[{'id':'1'},{'id':'2'}]}}
        self.s.graph=graph
        ident=self.s.enqueue('success-test')
        result={'channels':[{'channel':ch,'caption':'copy','images':[] if ch.startswith('threads') else ['/a.jpg','/b.jpg']} for ch in CHANNELS]}
        with self.s.db() as c:c.execute('UPDATE jobs SET result=? WHERE id=?',(json.dumps(result),ident))
        self.s.publish({'id':ident,'result':json.dumps(result)})
        self.assertEqual(self.s.state()['jobs'][0]['status'],'PUBLISHED')
        self.assertEqual(len(self.s.state()['jobs'][0]['receipts']),3)

if __name__=='__main__':unittest.main()
