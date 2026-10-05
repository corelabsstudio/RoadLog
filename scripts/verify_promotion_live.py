"""Verify deployed administrator endpoints; optionally make one paid preview, no post."""
import base64
import hashlib
import json
from pathlib import Path
import runpy
import sys
import urllib.request
import urllib.error
ROOT=Path(__file__).resolve().parents[1]
config=runpy.run_path(str(ROOT/'scripts/configure_promotion.py'))
v=config['v']
OUT=ROOT/'docs/marketing/admin-promotion-2026-10-05'
OUT.mkdir(parents=True,exist_ok=True)
def request(path,method='GET',body=None,token=None):
    headers={'Content-Type':'application/json','Cache-Control':'no-cache','Cookie':'rl_nocount=1'}
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('https://roadlog.co.kr'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read();return r.status,raw
    except urllib.error.HTTPError as e:return e.code,e.read()
tokenfile=ROOT/'.launch/promotion-admin-session.env'
if tokenfile.exists():token=tokenfile.read_text().strip()
else:
    code,data=request('/api/auth/login','POST',{'email':v.get('ADMIN_USERNAME') or v['ADMIN_EMAIL'],'password':v['ADMIN_PASSWORD']})
    if code!=200:raise SystemExit('Admin login not available; '+str(code))
    token=json.loads(data)['token'];tokenfile.write_text(token)
code,data=request('/api/admin/promotion',token=token)
if code!=200:raise SystemExit('Promotion API not available; '+str(code))
state=json.loads(data)
print(json.dumps({'endpoint_ready':True,'configured':state['configured'],'scheduled':state['profile']['enabled']},ensure_ascii=True))
for path in ['/admin/promotion.html','/admin/']:
    code,raw=request(path)
    name='promotion.html' if 'promotion' in path else 'index.html'
    print(json.dumps({'path':path,'http':code,'matches_local':raw==(ROOT/'web/admin'/name).read_bytes()}))
code,_=request('/api/admin/promotion');print('anonymous_admin_denied',code in (401,403))
if '--start-preview' in sys.argv:
    p=state['profile'];p['enabled']=False
    if not p['references']:
        raw=(ROOT/'web/assets/social/instagram-2026-10-04/01-hook.jpg').read_bytes()
        code,data=request('/api/admin/promotion/reference','POST',{'data':base64.b64encode(raw).decode()},token)
        if code!=200:raise SystemExit('Reference upload failed')
        p['references']=[json.loads(data)['id']]
        p['prompt']='이 예시처럼 보랏빛 밤과 따뜻한 조명, 귀여운 실사 무냥이. 강한 짧은 질문으로 시작하고 둘째 장은 공감 체크리스트. 상품마다 다른 상황과 새로운 문구를 사용해주세요.'
        code,data=request('/api/admin/promotion/profile','PUT',p,token)
        if code!=200:raise SystemExit('Profile save failed')
    code,data=request('/api/admin/promotion/jobs','POST',{'key':'verification-preview-20261005','publish':False},token)
    print('preview_accepted',code==200)
    if code!=200:print('preview_error',json.loads(data).get('detail'))
code,data=request('/api/admin/promotion',token=token);state=json.loads(data)
(OUT/'live-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'jobs':[{'id':j['id'],'status':j['status'],'error':j['error']} for j in state['jobs']]},ensure_ascii=True))
if '--download-preview' in sys.argv:
    for job in state['jobs']:
        if job['status']!='READY':continue
        for channel in job['result']['channels']:
            for url in channel['images']:
                code,raw=request(url)
                if code!=200:raise SystemExit('Generated JPEG not reachable')
                (OUT/url.split('/')[-1]).write_bytes(raw)
        print('preview_jpegs_saved')
