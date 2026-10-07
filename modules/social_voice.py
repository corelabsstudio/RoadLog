"""Public-writing-derived voice rules, without transmitting the source corpus."""
import json
import re
from pathlib import Path

def profile():
    return json.loads(Path(__file__).with_name('social_voice.json').read_text(encoding='utf-8'))

def prompt():
    data = profile()
    return ('\n온해님 실제 공개 글에서 정리한 말투 규칙(' + data['version'] + '):\n' + '\n'.join(data['rules']) +
            '\n문장 리듬 예시(직접 만든 문장이며 주제나 사연은 재사용하지 않음):\n'
            '딱딱한 글: 자동화를 구현했지만 중복 처리 문제가 발생했다.\n'
            '원하는 글: 자동으로 올리게 만들어놨거든?\\n근데 비슷한 글이라고 멈춰버리는거야ㅋㅋ\\n\\n그래서 막힌 다음에 뭘 할지도 넣었어.\n'
            '딱딱한 홍보: 관계의 결을 확인하면 답이 선명해질 거야.\n'
            '원하는 홍보: 답장 쓰고 지우고 또 쓰고..\\n보내지도 않았는데 벌써 지치지 않아?\\n\\n근데 지금 궁금한 게 답장이야?\\n아니면 그 사람이 아직 내 생각을 하는지야?\n'
            '예시처럼 문장 사이에서 실제 줄을 바꾸세요. caption과 thread_parts는 한 덩어리 설명문 금지. '
            '한 문단은 1~2문장, 한 문장은 가급적 40자 안팎. ~선명해질 거야, 관계의 결, 본연의 힘, '
            '내 뿌리에 흐르는 성질, 실마리 같은 광고 상투어 금지. 반말 어미만 바꾸는 것으로 끝내지 마세요.')

def validate(text):
    # Catch the original failure without blind suffix replacement or emoji injection.
    formal = re.findall(r'(?:했습니다|합니다|하세요|인가요|무엇인가요|확인했다|필요했다|중요하다|작성했다|반영했다)[.!?]?', text)
    if len(formal) >= 2:
        raise ValueError('온해님 말투로 다시 작성해주세요. 보고서·안내문 어미가 반복됩니다.')
    if re.search(r'선명해질|관계의 결|본연의 힘|실마리|마음의 자리|뿌리에 흐르는', text):
        raise ValueError('온해님 말투로 다시 작성해주세요. 추상적인 광고 문구가 남았습니다.')

def summary():
    data = profile()
    return {'version': data['version'], 'account': data['account'], 'rules': data['rules'], 'review': data['review']}
