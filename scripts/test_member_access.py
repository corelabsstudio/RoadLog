"""Isolated HTTP checks: no production users, database or external calls."""
import ast
import os
from pathlib import Path
import re
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, RedirectResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

app = FastAPI()
def token_user(header):
    if header != 'Bearer valid-test-session':
        raise HTTPException(401, 'invalid session')
    return {'id': 'local-fixture'}

namespace = dict(app=app, BaseModel=BaseModel, Request=Request, Header=Header,
                 Response=Response, RedirectResponse=RedirectResponse,
                 HTTPException=HTTPException, re=re, os=os, _token_user=token_user,
                 is_production=lambda: True)
source = ast.parse((Path(__file__).resolve().parents[1] / 'server.py').read_text(encoding='utf-8-sig'))
names = {'MemberAccessBody', 'member_access', 'member_access_clear', '_member_page', 'member_only_middleware'}
nodes = [n for n in source.body if getattr(n, 'name', None) in names or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'MEMBER_COOKIE', 'MEMBER_ONLY'} for t in n.targets)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'server-member-access', 'exec'), namespace)
# 기본값은 꺼짐(2026-10-07 비회원 둘러보기 복원). 아래 잠금 검사는 스위치를 켠 상태(MEMBER_ONLY=1)를 시험한다.
assert namespace['MEMBER_ONLY'] is False
namespace['MEMBER_ONLY'] = True

@app.api_route('/{path:path}', methods=['GET', 'POST'])
def fixture(path):
    return {'path': path}

client = TestClient(app, base_url='https://testserver', follow_redirects=False)
private = ['/saju/money.html', '/blog/index.html', '/curse.html', '/gwan/index.html',
           '/hall-of-fame', '/card/test.html', '/index.html']
for path in private:
    response = client.get(path)
    assert response.status_code == 303, (path, response.status_code)
    assert response.headers['location'].startswith('/?member_next=')
for path in ['/api/saju/taste', '/api/pets/hall-of-fame', '/api/products/test', '/api/curse/test']:
    assert client.post(path).status_code == 401, path
for path in ['/', '/legal/terms.html', '/legal/privacy.html', '/legal/refund.html', '/reset.html', '/api/auth/login', '/api/auth/google', '/assets/social/test.jpg']:
    assert client.get(path).status_code == 200, path
assert client.post('/api/member/access', json={'keep': True}).status_code == 401
client.cookies.set('roadlog_member', 'forged')
assert client.get('/saju/money.html').status_code == 303
client.cookies.clear()
response = client.post('/api/member/access', json={'keep': True}, headers={'Authorization': 'Bearer valid-test-session'})
assert response.status_code == 200
cookie = response.headers['set-cookie']
for marker in ['HttpOnly', 'Secure', 'SameSite=lax', 'Max-Age=604800']:
    assert marker in cookie, cookie
for path in private:
    assert client.get(path).status_code == 200, path
assert client.post('/api/saju/taste').status_code == 200
assert client.delete('/api/member/access').status_code == 200
assert client.get('/saju/money.html').status_code == 303
assert client.get('/saju/money.html', headers={'Authorization': 'Bearer valid-test-session'}).status_code == 200
response = client.post('/api/member/access', json={'keep': False}, headers={'Authorization': 'Bearer valid-test-session'})
assert 'Max-Age' not in response.headers['set-cookie']
# 스위치가 꺼진 기본 상태: 비회원도 모든 페이지·API 를 쓴다(색인·방문자 복원)
namespace['MEMBER_ONLY'] = False
guest = TestClient(app, base_url='https://testserver', follow_redirects=False)
for path in private + ['/', '/saju/money.html']:
    assert guest.get(path).status_code == 200, ('off', path)
for path in ['/api/saju/taste', '/api/pets/hall-of-fame', '/api/products/test', '/api/curse/test']:
    assert guest.post(path).status_code == 200, ('off', path)
assert 'no-store' not in guest.get('/saju/money.html').headers.get('cache-control', '')
print('PASS: guest pages/APIs, legal/auth exceptions, forged session, authenticated cookie/Bearer, logout, secure session lifetime')
