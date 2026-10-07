"""Read-only live policy check; --plan makes one text-only preview, never posts."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.promotion import Promotion, Profile, THREADS_WRITING_VERSION

OUT = ROOT / 'docs/marketing/threads-writing-2026-10-07'


def request(url, body=None, token=None):
    headers = {'Content-Type': 'application/json', 'User-Agent': 'RoadLog-policy-check',
               'Cookie': 'rl_nocount=1', 'Cache-Control': 'no-cache'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)


def railway(query, variables):
    token = (ROOT / '.launch/railway.token').read_text(encoding='utf-8-sig').strip().splitlines()[0].strip().strip('"').strip("'")
    data = request('https://backboard.railway.app/graphql/v2', {'query': query, 'variables': variables}, token)
    if data.get('errors'):
        raise RuntimeError('Railway query failed; no credentials printed')
    return data['data']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--product', action='store_true')
    parser.add_argument('--deployments', action='store_true')
    args = parser.parse_args()
    if args.deployments:
        result = railway('query($s:String!,$e:String!){deployments(input:{serviceId:$s,environmentId:$e},first:3){edges{node{id status createdAt meta}}}}',
                         {'s': 'ebf3faf1-2f14-425a-acad-9cc2c67fa633', 'e': '367f2cc2-ac64-4daf-b04d-0d28f4ac97c7'})
        print(json.dumps(result, ensure_ascii=True))
        return
    report = {'expected': THREADS_WRITING_VERSION}
    if args.plan:
        values = railway('query($p:String!,$e:String!,$s:String!){variables(projectId:$p,environmentId:$e,serviceId:$s)}',
                         {'p': '9d3da15b-b2e6-4790-af3c-b0229e2d1965', 'e': '367f2cc2-ac64-4daf-b04d-0d28f4ac97c7', 's': 'ebf3faf1-2f14-425a-acad-9cc2c67fa633'})['variables']
        # Only the text model key is needed, never account/publishing credentials.
        for key in ('PROMO_GEMINI_API_KEY', 'GEMINI_API_KEY'):
            if values.get(key):
                os.environ[key] = str(values[key])
        with tempfile.TemporaryDirectory() as directory:
            service = Promotion(Path(directory), ROOT / 'web')
            OUT.mkdir(parents=True, exist_ok=True)
            generate = service.gemini
            def capture(model, parts, config):
                result = generate(model, parts, config)
                (OUT / 'model-response.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                return result
            service.gemini = capture
            # Public product catalog + public format summaries + source-code defaults only.
            # Do not read or transmit administrator settings, private references or job history.
            previous = [json.dumps({'channels':[{'channel':'threads:roadlog_saju','content_type':'checklist'}]})] if args.product else []
            if previous:
                ident = service.enqueue('public-format-preview')
                with service.db() as c:
                    c.execute("UPDATE jobs SET result=?,status='PUBLISHED' WHERE id=?",(previous[0],ident))
            plan = service.plan(Profile().model_dump())
            report['planning'] = plan.get('planning')
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / 'text-preview.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
            thread = next(c for c in plan['channels'] if c['channel'].startswith('threads:'))
            report['text_preview'] = thread
            report['external_posts_created'] = 0
    else:
        token = (ROOT / '.launch/promotion-admin-session.env').read_text().strip()
        state = request('https://roadlog.co.kr/api/admin/promotion', token=token)
        report.update(live=state.get('threads_writing'), voice_version=state.get('social_voice',{}).get('version'), schedule_enabled=state['profile']['enabled'],
                      personal={'profile':state['personal_threads']['profile'],'version':state['personal_threads']['version'],'remaining_sources':state['personal_threads']['remaining_sources']})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
    if not args.plan and state.get('threads_writing', {}).get('version') != THREADS_WRITING_VERSION:
        raise SystemExit('Live policy is not updated yet')


if __name__ == '__main__':
    main()
