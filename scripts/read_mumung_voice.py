"""Read the authorized account's public writing; never print credentials."""
import json
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/marketing/mumung-voice-2026-10-07'

def main():
    token = dotenv_values(ROOT / '.launch/threads-mumung_fact.env')['THREADS_ACCESS_TOKEN']
    def get(url):
        if not url.startswith('https://graph.threads.net/'):
            raise ValueError('Unexpected pagination host')
        with urllib.request.urlopen(urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token}), timeout=40) as response:
            return json.load(response)
    me = get('https://graph.threads.net/v1.0/me?fields=id,username')
    assert me['username'] == 'mumung_fact'
    url = 'https://graph.threads.net/v1.0/me/threads?' + urllib.parse.urlencode({'fields':'id,text,timestamp,permalink,media_type,is_quote_post','limit':100})
    posts, pages, seen = [], 0, set()
    while url:
        if url in seen: raise ValueError('Pagination loop')
        seen.add(url)
        data = get(url)
        posts.extend(data['data']); pages += 1
        url = data.get('paging', {}).get('next')
    OUT.mkdir(parents=True, exist_ok=True)
    replies, reply_pages, reply_error = [], 0, None
    url = 'https://graph.threads.net/v1.0/me/replies?' + urllib.parse.urlencode({'fields':'id,text,timestamp,permalink,username','limit':100})
    while url:
        try:
            data = get(url)
        except urllib.error.HTTPError as error:
            reply_error = 'HTTP ' + str(error.code)
            break
        replies.extend(p for p in data['data'] if p.get('username') == 'mumung_fact')
        reply_pages += 1
        url = data.get('paging', {}).get('next')
    report = {'account':me['username'], 'pages':pages, 'exhausted':True, 'posts':posts,
              'replies':replies, 'reply_pages':reply_pages, 'reply_error':reply_error}
    (OUT/'public-posts.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/'public-posts.md').write_text('\n\n'.join('## '+p.get('timestamp','')+' '+p['id']+'\n'+p.get('permalink','')+'\n'+p.get('text','') for p in posts),encoding='utf-8')
    (OUT/'public-replies.md').write_text('\n\n'.join('## '+p.get('timestamp','')+' '+p['id']+'\n'+p.get('text','') for p in replies),encoding='utf-8')
    print(json.dumps({'account':me['username'],'pages':pages,'count':len(posts),'exhausted':True,
                      'replies':len(replies),'reply_pages':reply_pages,'reply_error':reply_error}))

if __name__ == '__main__': main()
