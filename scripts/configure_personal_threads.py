"""Provision/verify the existing personal account without printing secrets."""
import argparse
import json
from pathlib import Path
import runpy
import sys
import urllib.request
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
shared = runpy.run_path(str(ROOT / 'scripts/verify_threads_writing.py'))
OUT = ROOT / 'docs/marketing/personal-threads-2026-10-07'


def api(path='', method='GET', body=None):
    token = (ROOT / '.launch/promotion-admin-session.env').read_text().strip()
    headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Cookie': 'rl_nocount=1'}
    req = urllib.request.Request('https://roadlog.co.kr/api/admin/promotion' + path, method=method,
                                 headers=headers, data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provision', action='store_true')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--publish-first', action='store_true')
    parser.add_argument('--enable', action='store_true')
    args = parser.parse_args()
    if args.provision:
        values = dotenv_values(ROOT / '.launch/threads-mumung_fact.env')
        token = values['THREADS_ACCESS_TOKEN']
        me = shared['request']('https://graph.threads.net/v1.0/me?fields=id,username', token=token)
        if me.get('username') != 'mumung_fact' or str(me.get('id')) != str(values['THREADS_USER_ID']):
            raise SystemExit('Personal account identity mismatch')
        shared['railway']('mutation($input:VariableUpsertInput!){variableUpsert(input:$input)}',
                          {'input': {'projectId': '9d3da15b-b2e6-4790-af3c-b0229e2d1965',
                                     'environmentId': '367f2cc2-ac64-4daf-b04d-0d28f4ac97c7',
                                     'serviceId': 'ebf3faf1-2f14-425a-acad-9cc2c67fa633',
                                     'name': 'PROMO_THREADS_MUMUNG_FACT_TOKEN', 'value': token, 'skipDeploys': True}})
        print(json.dumps({'verified_account': me['username'], 'dedicated_token_saved': True}))
        return
    if args.preview:
        api('/personal/jobs', 'POST', {'key': 'personal-first-preview-20261007', 'publish': False})
    state = api()
    personal = state.get('personal_threads')
    if not personal:
        raise SystemExit('Personal journal is not deployed yet')
    if args.publish_first:
        first = next((p for p in personal['posts'] if p['slot'] == 'personal-first-preview-20261007'), None)
        if not first:
            raise SystemExit('Create and inspect the preview first')
        if first['status'] == 'READY':
            api('/personal/jobs/' + first['id'] + '/publish', 'POST', {})
        elif first['status'] not in ('QUEUED', 'PREPARING', 'PUBLISHED'):
            raise SystemExit('Do not repeat an uncertain or failed publication')
    if args.enable:
        if not any(p['status'] == 'PUBLISHED' for p in personal['posts']):
            raise SystemExit('Verify one successful personal publication before enabling')
        api('/personal/profile', 'PUT', {'enabled': True, 'times': ['09:00', '12:00', '18:00', '21:00']})
    personal = api()['personal_threads']
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'live-state.json').write_text(json.dumps(personal, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(personal, ensure_ascii=True))


if __name__ == '__main__': main()
