"""Isolated HTTP checks: no production users, database or external calls."""
import ast
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
                 HTTPException=HTTPException, re=re, _token_user=token_user,
                 is_production=lambda: True)
source = ast.parse((Path(__file__).resolve().parents[1] / 'server.py').read_text(encoding='utf-8-sig'))
names = {'MemberAccessBody', 'member_access', 'member_access_clear', '_member_page', 'member_only_middleware'}
nodes = [n for n in source.body if getattr(n, 'name', None) in names or
         isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'MEMBER_COOKIE' for t in n.targets)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), 'server-member-access', 'exec'), namespace)

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
print('PASS: guest pages/APIs, legal/auth exceptions, forged session, authenticated cookie/Bearer, logout, secure session lifetime')
