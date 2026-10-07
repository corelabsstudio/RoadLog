"""Three-part Threads publication with a durable receipt before every final call."""
import re

def initialize(client):
    with client.db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS thread_parts(job TEXT,position INTEGER,status TEXT,
          container TEXT,media TEXT,url TEXT,error TEXT,PRIMARY KEY(job,position))''')

def update(client, job, position, status, **fields):
    with client.db() as c:
        c.execute('INSERT OR IGNORE INTO thread_parts(job,position,status) VALUES(?,?,?)',(job,position,status))
        values = dict(status=status,**fields)
        c.execute('UPDATE thread_parts SET '+','.join(k+'=?' for k in values)+' WHERE job=? AND position=?',
                  (*values.values(),job,position))

def publish(client, job, item, uid):
    parts = item['thread_parts']
    if len(parts) != 3 or item['caption'] != parts[0] or any(not isinstance(p,str) or not 1 <= len(p) <= 500 for p in parts):
        raise ValueError('연속 글은 각각 500자 이하인 세 편이어야 합니다.')
    ch = item['channel']
    previous = None
    root = None
    for position, text in enumerate(parts,1):
        update(client,job,position,'PREPARING')
        state = 'PREPARING'
        try:
            data = {'media_type':'TEXT','text':text}
            if previous: data['reply_to_id'] = previous
            container = str(client.graph(ch,'POST',uid+'/threads',data).get('id',''))
            client.ready_container(ch,container)
            state = 'UNCERTAIN'
            update(client,job,position,state,container=container)
            client.receipt(job,ch,'UNCERTAIN',container=container)
            media = str(client.graph(ch,'POST',uid+'/threads_publish',{'creation_id':container}).get('id',''))
            if not media.isdigit(): raise ValueError('연속 글 게시 ID 확인이 필요합니다. 재발행하지 않습니다.')
            state = 'PUBLISHED_UNVERIFIED'
            update(client,job,position,state,media=media)
            detail = client.graph(ch,'GET',media,{'fields':'id,username,text,permalink,replied_to'})
            if (detail.get('username') != 'roadlog_saju' or detail.get('text') != text
                or not re.fullmatch(r'https://(?:www\.)?threads\.(?:net|com)/@roadlog_saju/post/[^/?#]+',detail.get('permalink',''))
                or (previous and str((detail.get('replied_to') or {}).get('id')) != previous)):
                raise ValueError('연속 글의 계정·본문·주소·답글 연결 확인이 필요합니다.')
            update(client,job,position,'PUBLISHED',url=detail['permalink'])
            root = root or (media,detail['permalink'])
            client.receipt(job,ch,'PUBLISHED_UNVERIFIED',media=root[0],url=root[1])
            previous = media
        except Exception as error:
            update(client,job,position,'FAILED' if state == 'PREPARING' else state,error=client.safe_error(error))
            raise
    client.receipt(job,ch,'PUBLISHED',media=root[0],url=root[1])
