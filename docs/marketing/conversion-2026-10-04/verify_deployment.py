"""Read-only release verification. Prints status and public commit/assets only."""
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[3]
token = (ROOT / '.launch/railway.token').read_text(encoding='utf-8-sig').strip().splitlines()[0].strip().strip('"').strip("'")
query = '''query($s:String!,$e:String!){deployments(first:3,input:{serviceId:$s,environmentId:$e}){edges{node{id status createdAt meta}}}}'''
req = urllib.request.Request('https://backboard.railway.app/graphql/v2',
    data=json.dumps({'query': query, 'variables': {'s': 'ebf3faf1-2f14-425a-acad-9cc2c67fa633', 'e': '367f2cc2-ac64-4daf-b04d-0d28f4ac97c7'}}).encode(),
    headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.load(r)
except urllib.error.HTTPError as error:
    print('railway_status_unavailable', error.code)
    result = {}
if result.get('errors'):
    print('railway_status_unavailable', 'query')
for edge in ((result.get('data') or {}).get('deployments') or {}).get('edges') or []:
    node = edge['node']
    print(json.dumps({'status': node['status'], 'commit': (node.get('meta') or {}).get('commitHash'), 'at': node['createdAt']}, ensure_ascii=False))

def get(path):
    req = urllib.request.Request('https://roadlog.co.kr' + path,
        headers={'Cookie': 'rl_nocount=1', 'User-Agent': 'RoadLog-release-verification', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()

html = get('/?nocount=1')
print('home_has_primary_cta', '오늘 운세 무료로 보기'.encode() in html)
print('home_matches_build', hashlib.sha256(html).digest() == hashlib.sha256((ROOT / 'web/index.html').read_bytes()).digest())
assets = re.findall(rb'(?:src|href)="(/assets/[^"?]+\.(?:js|css))"', html)
for asset in assets:
    path = asset.decode()
    local = ROOT / 'web' / path.lstrip('/')
    print('asset', path, 'matches_build', local.exists() and hashlib.sha256(get(path)).digest() == hashlib.sha256(local.read_bytes()).digest())
health = json.loads(get('/api/health'))
print('health_ok', health.get('ok', health.get('status')))
print('persistent_storage', health.get('storage_persistent'))
