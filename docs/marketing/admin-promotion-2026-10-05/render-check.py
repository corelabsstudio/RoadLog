"""Check Korean typography and mobile-scale readability using an unbilled scene."""
import io
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from modules.promotion import Promotion
from PIL import Image
root=Path(__file__).resolve().parent
service=Promotion(root/'test-data',root)
raw=io.BytesIO();Image.new('RGB',(1080,1350),'#8565ad').save(raw,'PNG')
card={'title':'마음 스캔 체크리스트','body':'□ 이달 내 글자가 켜져 있는가 □ 떠오를 때의 진심 □ 나를 움직이는 숨은 이유 □ 지금 가장 필요한 한 가지'}
im=Image.open(io.BytesIO(service.render(raw.getvalue(),card)))
assert im.size==(1080,1350)
im.resize((390,488)).save(root/'typography-390.jpg')
print('Korean card render verified 1080x1350 and 390px')
