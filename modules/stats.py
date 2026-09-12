# -*- coding: utf-8 -*-
"""방문자 · 매출 · 가입 집계.

방문자는 서버가 직접 센다. 쿠키를 굽지 않고 애널리틱스도 붙이지 않는다.
「그날 처음 온 브라우저」만 세려고 (IP + 브라우저 + 날짜)를 그날치 소금과 함께
해시로만 남긴다. 원래 값으로 되돌릴 수 없고, 90일 지나면 지운다.

매출과 가입은 이미 쌓이고 있는 것(lamps.json 장부, users.json 가입일)을 훑어서 낸다.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from modules.config import DATA_DIR

VISITS_JSON = Path(DATA_DIR) / "visits.json"
KEEP_DAYS = 90
_LOCK = threading.Lock()
_SALT = (os.environ.get("APP_SECRET") or "roadlog") + "|visit"

# 사주 서비스를 연 날. 이전에 만들어진 계정은 옛 운행일지 계정이다.
SAJU_SINCE = os.environ.get("SAJU_SINCE", "2026-09-04")


KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """서버는 세계표준시로 돈다. 날짜는 한국 시간으로 끊어야 맞다."""
    return datetime.now(KST)


def _today() -> str:
    return now_kst().strftime("%Y-%m-%d")


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(path)


def _fingerprint(ip: str, ua: str, day: str) -> str:
    raw = f"{_SALT}|{day}|{ip}|{ua}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# 어디서 왔는지 — 주소의 호스트를 사람이 읽는 이름으로 묶는다
SOURCES = [
    ("google.", "구글"), ("naver.", "네이버"), ("daum.", "다음"),
    ("kakao", "카카오"), ("instagram.", "인스타그램"), ("threads.", "스레드"),
    ("tistory.", "티스토리"), ("youtube.", "유튜브"), ("youtu.be", "유튜브"),
    ("bing.", "빙"), ("x.com", "X"), ("twitter.", "X"), ("facebook.", "페이스북"),
    ("t.co", "X"), ("chatgpt.com", "챗GPT"), ("perplexity.", "퍼플렉시티"),
    # 🛑 한국 커뮤니티 (2026-09-11 디시 사주팔자 연구 갤러리에 올리면서 넣음).
    #    없으면 `gall.dcinside.com` 처럼 주소가 그대로 찍혀서, 같은 곳에서 온 것인데
    #    갤러리마다 다른 줄로 흩어진다.
    ("dcinside", "디시인사이드"), ("theqoo.", "더쿠"), ("pann.nate", "네이트판"),
    ("fmkorea.", "에펨코리아"), ("ruliweb.", "루리웹"), ("clien.", "클리앙"),
    ("tiktok.", "틱톡"), ("band.us", "밴드"),
]


# 링크에 붙어 오는 `utm_source` 는 영문이 많다. 우리 표 이름으로 맞춰 준다.
# 🛑 **안 맞추면 같은 곳이 두 줄로 갈린다** (2026-09-11 온해님 「한글 스레드랑 영문
#    스레드는 무슨 차이야?」 — 「스레드 9명」과 「threads 1명」이 따로 서 있었다).
UTM_ALIAS = {
    # 옛 기록의 이름을 지금 이름으로 — 읽을 때 합쳐진다
    "사이트 안": "이어서 보기",
    "threads": "스레드", "instagram": "인스타그램", "ig": "인스타그램",
    # 🛑 카드뉴스·공유카드에 박은 QR 로 들어온 사람 (2026-09-13 온해님
    #    「QR 코드 찍고 들어온 사람이 몇 명인지 보이게 해줘」). 스레드와 갈라 둔다
    "threads-qr": "스레드 QR", "qr": "QR",
    "tiktok": "틱톡", "youtube": "유튜브", "yt": "유튜브", "shorts": "유튜브",
    "dcinside": "디시인사이드", "디시": "디시인사이드", "dc": "디시인사이드",
    "naver": "네이버", "kakao": "카카오", "kakaotalk": "카카오",
    "google": "구글", "bing": "빙", "daum": "다음",
    "x": "X", "twitter": "X", "facebook": "페이스북", "fb": "페이스북",
    "band": "밴드", "theqoo": "더쿠", "fmkorea": "에펨코리아",
    "ruliweb": "루리웹", "clien": "클리앙", "tistory": "티스토리",
}


def _tidy_map(d: dict) -> dict:
    """이름을 맞춰 같은 곳끼리 더한다."""
    out: dict[str, int] = {}
    for k, v in (d or {}).items():
        n = tidy_source(k)
        out[n] = int(out.get(n, 0)) + int(v or 0)
    return out


def tidy_source(name: str) -> str:
    """유입경로 이름을 하나로 맞춘다. **읽을 때도 부른다** — 이미 쌓인 기록까지 합쳐진다."""
    s = " ".join(str(name or "").split())
    return UTM_ALIAS.get(s.lower(), s)


def source_of(ref: str, host: str = "") -> str:
    """유입경로 한 줄. 광고 파라미터(utm_source)가 있으면 그것을 우선한다."""
    r = (ref or "").strip().lower()
    if not r:
        return "직접 · 앱"
    try:
        from urllib.parse import urlsplit
        p = urlsplit(r)
        h = p.netloc
    except Exception:
        h = r
    if not h:
        return "직접 · 앱"
    if host and host.lower() in h:
        # 🛑 **밖에서 들어온 게 아니다.** 우리 페이지에서 다른 페이지로 넘어간 것이다
        #    (홈 → 결제 화면, 홈 → 상품 안내 …). 이름이 「사이트 안」이라 유입처럼
        #    읽혀서 2026-09-12 에 온해님이 「정확히 어디서 유입되는 거야」라고 물으셨다.
        return "이어서 보기"
    for key, name in SOURCES:
        if key in h:
            return name
    return h[:40]


# ── 무엇으로 들어왔나 ────────────────────────────────────
# 「직접·앱」이 크면 사람인지 크롤러인지 갈라 봐야 한다. UA 원문은 길고 개인을
# 가리킬 수 있어 저장하지 않고, **계열 이름만** 세어 둔다.
# 🛑 카카오톡·네이버앱 인앱 브라우저는 UA 에 Chrome 도 같이 들어 있다.
#    그래서 **먼저 걸리는 것부터** 본다. 순서를 바꾸면 전부 「크롬」이 된다.
_APPS = [
    ("KAKAOTALK", "카카오톡"),
    ("NAVER(inapp", "네이버앱"), ("NAVER(", "네이버앱"),
    ("Instagram", "인스타그램"),
    ("FBAV", "페이스북"), ("FB_IAB", "페이스북"),
    ("Line/", "라인"),
    ("DaumApps", "다음앱"),
    ("Whale", "웨일"),
    ("SamsungBrowser", "삼성인터넷"),
    ("Edg/", "엣지"),
    ("OPR/", "오페라"),
    ("Firefox", "파이어폭스"),
    ("CriOS", "크롬"), ("Chrome", "크롬"),
    ("Safari", "사파리"),
]
_OS = [
    ("iPhone", "아이폰"), ("iPad", "아이패드"),
    ("Android", "안드로이드"),
    ("Macintosh", "맥"), ("Mac OS X", "맥"),
    ("Windows", "윈도우"),
    ("Linux", "리눅스"),
]


def client_of(ua: str) -> str:
    """UA 를 「크롬 · 안드로이드」 같은 한 줄로 줄인다."""
    ua = ua or ""
    app = next((n for k, n in _APPS if k in ua), "기타")
    osn = next((n for k, n in _OS if k in ua), "기타")
    # 사람 브라우저인 척하는 것들. 헤드리스는 자동화 도구다
    if "HeadlessChrome" in ua or "Headless" in ua:
        app = "헤드리스(자동화)"
    return f"{app} · {osn}"


def hit(ip: str, ua: str, path: str, ref: str = "", host: str = "",
        utm: str = "", campaign: str = "") -> None:
    """페이지 한 번 열림. 화면(HTML)만 세고 자산·API 는 안 센다.

    🛑 **`utm_source` 가 있으면 그게 우선이다** (2026-09-11). 링크에 대놓고 적어
       보낸 것이라 referrer 추측보다 정확하다. 카카오톡·인스타처럼 referrer 를
       안 주거나 뭉개는 데서도 이건 남는다.
    """
    day = _today()
    fp = _fingerprint(ip or "", ua or "", day)
    utm = " ".join(str(utm or "").split())[:24]
    campaign = " ".join(str(campaign or "").split())[:32]
    src = tidy_source(utm) if utm else source_of(ref, host)
    with _LOCK:
        data = _read(VISITS_JSON, {})
        d = data.setdefault(day, {"pv": 0, "uv": [], "src": {}})
        d.setdefault("src", {})
        d.setdefault("ua", {})
        d["pv"] = int(d.get("pv", 0)) + 1
        if fp not in d["uv"]:
            d["uv"].append(fp)
            # 유입경로·기기는 그날 처음 온 사람만 센다 — 안 그러면 새로고침이 다 잡힌다
            d["src"][src] = int(d["src"].get(src, 0)) + 1
            # 🛑 캠페인은 **게시글 하나하나**다. 같은 스레드라도 어느 글이 물어 왔는지
            #    알아야 다음에 무엇을 또 쓸지 정할 수 있다.
            if campaign:
                d.setdefault("camp", {})
                key = ("%s · %s" % (utm, campaign)) if utm else campaign
                d["camp"][key] = int(d["camp"].get(key, 0)) + 1
            cl = client_of(ua or "")
            d["ua"][cl] = int(d["ua"].get(cl, 0)) + 1
        # 오래된 날짜는 버린다
        if len(data) > KEEP_DAYS + 10:
            cut = (now_kst() - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
            for k in [k for k in data if k < cut]:
                data.pop(k, None)
        _write(VISITS_JSON, data)


# ── 지금 사이트에 있는 사람 (2026-09-12 온해님) ──────────────────
#
# 🛑 **파일에 안 쓴다. 메모리에만 둔다.** 「지금」이라 다시 뜨면 비는 게 맞고,
#    요청마다 디스크를 만지면 느려진다.
# 🛑 **`hit()` 으로는 못 센다.** 그건 HTML 이 열릴 때만 도는데, 우리 화면은 SPA 라
#    손님이 사주를 보는 내내 HTML 요청이 한 번도 안 간다. 그래서 **API 요청까지**
#    세는 자리를 따로 뒀다.
# 🛑 회원인지는 **Authorization 헤더가 붙었는지**로만 본다. 토큰을 제대로 맞춰
#    보지 않는다 — 세는 값이라 그 정도면 되고, 요청마다 DB 를 열면 느려진다.
_LIVE: dict[str, tuple[float, bool]] = {}
_LIVE_LOCK = threading.Lock()
# 🛑 **2분**이다 (2026-09-13). 앞단이 45초마다 `/api/ping` 을 보내므로 보고 있는
#    사람은 계속 잡히고, 창을 닫으면 **최대 2분 뒤 사라진다.** 전에는 5분이라
#    나간 사람이 오래 남았고, 반대로 가만히 읽는 사람은 사라졌다.
LIVE_MIN = 2           # 이 시간 안에 움직였으면 「지금 있는 사람」


def live_touch(ip: str, ua: str, member: bool) -> None:
    """요청 하나가 왔다. 지문·시각·기기를 메모리에 남긴다."""
    fp = _fingerprint(ip or "", ua or "", _today())
    now = datetime.now(KST).timestamp()
    # 🛑 **기기를 같이 남긴다** (2026-09-12 온해님 「5명 접속중인데 죄다 비회원이야」).
    #    숫자만으로는 사람인지 크롤러인지 모른다. `client_of` 가 「크롬·안드로이드」
    #    같은 이름을 내는데, 정체를 모르는 것은 「기타」로 떨어진다 — 그게 많으면 봇이다.
    cl = client_of(ua or "")
    with _LIVE_LOCK:
        was = _LIVE.get(fp)
        # 🛑 한 번이라도 회원으로 들어왔으면 회원으로 둔다. 화면 하나를 여는 동안
        #    토큰이 붙는 요청과 안 붙는 요청이 섞여서, 덮어쓰면 숫자가 깜박인다.
        _LIVE[fp] = (now, bool(member) or bool(was and was[1]), cl)
        if len(_LIVE) > 4000:                    # 쌓이면 오래된 것부터 버린다
            cut = now - LIVE_MIN * 60
            for k in [k for k, v in _LIVE.items() if v[0] < cut]:
                _LIVE.pop(k, None)


def live(minutes: int = LIVE_MIN) -> dict[str, Any]:
    """지금 있는 사람 — 전부 · 회원 · 비회원 · 기기별."""
    cut = datetime.now(KST).timestamp() - minutes * 60
    with _LIVE_LOCK:
        rows = [v for v in _LIVE.values() if v[0] >= cut]
    mem = sum(1 for r in rows if r[1])
    # 🛑 기기별 쪼갠 값은 **안 내려보낸다** (2026-09-12 온해님 「없애 그냥」).
    #    화면에서 걷어냈으니 여기서도 셈하지 않는다.
    return {"all": len(rows), "members": mem, "guests": len(rows) - mem,
            "minutes": minutes}


# ── 오늘 들어온 회원 (2026-09-12 온해님) ────────────────────────
#
# > 회원은 안 늘고 있는데 방문자랑 페이지 열림은 어제보다 많아서
# > **기존 회원이 재방문하는건지** 궁금해서 그래
#
# 방문자(uv)는 지문이라 회원인지 모른다. 그래서 **로그인해서 들어온 회원**을 따로 센다.
# 🛑 `users.json` 은 안 건드린다 — Supabase 와 두 갈래라 손대면 어긋난다.
# 🛑 **하루에 한 사람당 한 번만 쓴다.** 요청마다 디스크를 만지면 느려진다.
SEEN_JSON = Path(DATA_DIR) / "seen.json"
_SEEN_TODAY: set[str] = set()
_SEEN_DAY = ""


def seen_member(email: str) -> None:
    """회원이 오늘 움직였다. 이미 적은 사람은 그냥 지나간다."""
    global _SEEN_DAY
    email = (email or "").strip().lower()
    if not email:
        return
    day = _today()
    with _LOCK:
        if _SEEN_DAY != day:
            _SEEN_DAY = day
            _SEEN_TODAY.clear()
        if email in _SEEN_TODAY:
            return
        _SEEN_TODAY.add(email)
        data = _read(SEEN_JSON, {})
        lst = data.setdefault(day, [])
        if email not in lst:
            lst.append(email)
        if len(data) > KEEP_DAYS + 10:
            cut = (now_kst() - timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
            for k in [k for k in data if k < cut]:
                data.pop(k, None)
        _write(SEEN_JSON, data)


# 🛑 **20초만 기억해 둔다** (2026-09-13 온해님 「5초마다 서버를 두드리는 게 문제가 되나?」).
#    화면이 5초마다 묻는데 이 값은 **하루 단위**라 그때마다 디스크를 읽을 이유가 없다.
#    접속 인원은 메모리에서 세므로, 이걸 캐시하면 5초짜리 요청이 파일을 아예 안 만진다.
_SEEN_CACHE: dict[str, Any] = {"at": 0.0, "days": 0, "out": []}
SEEN_CACHE_SEC = 20


def seen_days(days: int = 2) -> list[dict[str, Any]]:
    """최근 며칠, 날짜별로 들어온 회원 수. 오늘이 맨 앞이다."""
    now = datetime.now(KST).timestamp()
    if (_SEEN_CACHE["days"] == days
            and now - float(_SEEN_CACHE["at"]) < SEEN_CACHE_SEC):
        return _SEEN_CACHE["out"]
    data = _read(SEEN_JSON, {})
    out = []
    for i in range(days):
        d = (now_kst() - timedelta(days=i)).strftime("%Y-%m-%d")
        out.append({"day": d, "members": len(data.get(d, []))})
    _SEEN_CACHE.update({"at": now, "days": days, "out": out})
    return out


def tap(what: str, product: str = "") -> None:
    """카드를 저장했거나 공유했다. 날짜별로 세기만 한다 (2026-09-11).

    🛑 **누가 눌렀는지는 안 남긴다.** 몇 번 눌렸는지만 안다.
    """
    # 🛑 **`open` 을 더했다** (2026-09-12 온해님 「사주 열람도 일별로 볼 수 있어야 하는데」).
    #    대시보드의 「열람」은 `acc["owned"]` 를 세는데, 그건 **복채를 낸 것만** 들어간다.
    #    「오늘 운세」처럼 무료로 연 것은 어디에도 안 세어져서, 66명이 와서 사주를
    #    봤는지 아닌지 알 길이 없었다. 앞단이 리포트를 **끝까지 열 때** 이걸 부른다.
    what = " ".join(str(what or "").split())[:24]
    if what not in ("save", "share", "sns", "copy", "open"):
        return
    product = " ".join(str(product or "").split())[:24]
    day = _today()
    with _LOCK:
        data = _read(VISITS_JSON, {})
        d = data.setdefault(day, {"pv": 0, "uv": [], "src": {}})
        t = d.setdefault("tap", {})
        key = ("%s:%s" % (what, product)) if product else what
        t[key] = int(t.get(key, 0)) + 1
        _write(VISITS_JSON, data)


def forget_visits(day: str | None = None) -> int:
    """방문 기록을 지운다. 잘못 센 날을 털어낼 때 쓴다."""
    with _LOCK:
        data = _read(VISITS_JSON, {})
        if day:
            gone = 1 if data.pop(day, None) is not None else 0
        else:
            gone = len(data)
            data = {}
        _write(VISITS_JSON, data)
    return gone


def _visits() -> dict[str, dict[str, Any]]:
    out = {}
    for day, d in _read(VISITS_JSON, {}).items():
        out[day] = {
            "pv": int(d.get("pv", 0)),
            "uv": len(d.get("uv", [])),
            "src": dict(d.get("src", {})),
            "camp": dict(d.get("camp", {})),
            "tap": dict(d.get("tap", {})),
            "ua": dict(d.get("ua", {})),      # 무엇으로 들어왔나 (계열 이름만)
        }
    return out


def _charges() -> list[dict[str, Any]]:
    """돈이 오간 기록 전부. 계정별 장부에 흩어져 있는 것을 모은다.

    🛑 `charge`(등불 판매)만 세면 매출이 영영 0 이다 (2026-09-07 발견).
       등불 판매는 KG이니시스 거절로 접었고, 지금 돈이 들어오는 길은
       `premium`(리포트 건별 결제) 하나뿐이다. 실제로 8,900원 결제 기록이
       장부에 있는데도 운영 화면은 「매출 0원 · 결제 0건」을 보여 주고 있었다.
    """
    from modules import lamps as lamps_ops

    rows = []
    for email, acc in (lamps_ops._read() or {}).items():
        if not isinstance(acc, dict):
            continue
        for e in acc.get("ledger", []):
            # 🛑 환불도 센다 — 금액이 음수라 매출이 저절로 준다 (2026-09-11)
            if e.get("type") not in ("charge", "premium", "refund"):
                continue
            at = str(e.get("at", ""))[:10]
            if not at:
                continue
            # 🛑 테스트 채널 기간 건은 매출이 아니다 (lamps.REAL_PAY_FROM 참고).
            #    원장에는 남아 있고 여기서 세지만 않는다.
            if at < lamps_ops.REAL_PAY_FROM:
                continue
            rows.append({
                "day": at,
                # 🛑 **무엇을 샀는지 담는다** (2026-09-10 온해님 「뭘 결제했는지
                #    알 수가 없네」). 전에는 날짜·이메일·금액만 뽑아서, 운영 화면이
                #    매출 총액은 아는데 **무슨 상품이 팔렸는지는 못 보여 줬다.**
                "at": str(e.get("at", "")),
                "email": email,
                "product": str(e.get("product") or ""),
                "pair": str(e.get("pair") or ""),
                "payment_id": str(e.get("payment_id") or ""),
                "kind": str(e.get("type") or ""),
                "price": int(e.get("price") or 0),
                "lamps": int(e.get("lamps") or 0),
            })
    return rows


def _spends() -> list[dict[str, Any]]:
    """어떤 사주가 몇 번 열렸나."""
    from modules import lamps as lamps_ops

    rows = []
    for email, acc in (lamps_ops._read() or {}).items():
        if not isinstance(acc, dict):
            continue
        for o in acc.get("owned", []):
            at = str(o.get("at", ""))[:10]
            if at:
                rows.append({"day": at, "product": o.get("product", ""), "email": email})
    return rows


def _signups() -> list[str]:
    """사주 손님만. 옛 운행일지 계정은 세지 않는다."""
    return [m["at"] for m in members() if m["at"] and not m["legacy"]]


def members(limit: int = 300) -> list[dict[str, Any]]:
    """가입한 사람들. 관리자만 본다."""
    from modules.config import USERS_JSON
    from modules import lamps as lamps_ops

    lamp = lamps_ops._read() or {}
    # 🛑 **순위표를 한 번만 만든다** (2026-09-11). 회원마다 다시 계산하면 300명이면
    #    장부를 300번 훑는다. 배지는 1·2·3위에만 붙는다.
    _board = lamps_ops.refer_board(3)
    rank_of = {b["email"]: b["rank"] for b in _board}
    rank_name = {b["email"]: b["name"] for b in _board}
    out = []
    for email, u in (_read(Path(USERS_JSON), {}) or {}).items():
        if not isinstance(u, dict):
            continue
        acc = lamp.get(email) or {}
        # 🛑 **`charge` 만 세면 회원별 결제액이 영영 0 이다** (2026-09-10 온해님이 잡으심).
        #    등불 판매는 2026-09-07 에 없앴고, 지금 돈이 들어오는 길은 `premium`
        #    (리포트 건별 결제) 하나뿐이다. 매출 총액에서 이미 같은 사고를 한 번 겪고
        #    `_charges()` 는 고쳤는데, **회원 표만 옛 조건으로 남아 있었다.**
        #    실제로 47,500원을 쓰신 분이 화면에 「0원」으로 보였다.
        # 🛑 매출 총액과 같은 잣대로 센다 — 테스트 채널 기간 건은 뺀다
        #    (`lamps.REAL_PAY_FROM`). 안 그러면 총액과 회원별 합계가 안 맞는다.
        charged = sum(int(e.get("price") or 0)
                      for e in acc.get("ledger", [])
                      if e.get("type") in ("charge", "premium", "refund")
                      and str(e.get("at", ""))[:10] >= lamps_ops.REAL_PAY_FROM)
        bal = sum(int(l.get("remain") or 0) for l in acc.get("lots", []))
        if email.endswith("@kakao.local"):
            how = "카카오"
        elif email.endswith("@roadlog.local"):
            how = "관리자"
        else:
            how = "이메일 · 소셜"
        at = str(u.get("created_at", ""))[:10]
        opens = len(acc.get("owned", []))
        # 사주를 쓴 적이 있거나, 사주 시작일 이후에 가입했으면 사주 손님이다
        used = bool(opens or acc.get("ledger"))
        legacy = (how == "관리자") or not (used or (at and at >= SAJU_SINCE))
        # 🛑 **데려온 사람 수** (2026-09-11 온해님). 원장에 `refer` 항목이 하나씩
        #    쌓이므로 세기만 하면 된다 — 누구를 데려왔는지는 안 남는다(개인정보).
        refer = sum(1 for e in acc.get("ledger", []) if e.get("type") == "refer")
        # 남은 무료 이용권 — 받은 것에서 쓴 것을 뺀다 (장수를 따로 저장하지 않는다)
        ticket_left = max(0, sum(1 for e in acc.get("ledger", []) if e.get("type") == "ticket")
                          - sum(1 for e in acc.get("ledger", []) if e.get("type") == "ticket-use"))
        out.append({
            "via": str(acc.get("via") or ""),
            "email": email,
            "name": u.get("name") or "",
            "at": at,
            "how": how,
            "lamps": bal,
            "spent": charged,
            "opens": opens,
            "refer": refer,
            "rank": rank_of.get(email, 0),
            "badge": rank_name.get(email, ""),
            "ticket": ticket_left,
            "legacy": legacy,
        })
    out.sort(key=lambda m: m["at"], reverse=True)
    return out[:limit]


def overview(days: int = 30) -> dict[str, Any]:
    """오늘·이번 달·최근 N일을 한 번에."""
    now = now_kst()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")

    vis = _visits()
    ch = _charges()
    sp = _spends()
    su = _signups()

    start = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    by_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sales": 0, "charges": 0, "signups": 0, "uv": 0, "pv": 0,
                 "opens": 0, "asks": 0})
    for r in ch:
        by_day[r["day"]]["sales"] += r["price"]
        by_day[r["day"]]["charges"] += 1
    for d in su:
        by_day[d]["signups"] += 1
    # 🛑 **「더 물어보기」를 사주 열람과 갈라 센다** (2026-09-13 온해님
    #    「9/11 복채 내고 봄이 7인데 결제된 건 2,900원이 다야」).
    #    둘 다 `owned` 에 쌓여서 한 칸에 섞여 있었다. 실측으로 90일 34건 중
    #    **24건이 더 물어보기**였다 — 등불 30개짜리라 돈이 안 들어온다.
    for r in sp:
        if str(r.get("product", "")).startswith("ask:"):
            by_day[r["day"]]["asks"] += 1
        else:
            by_day[r["day"]]["opens"] += 1
    for d, v in vis.items():
        by_day[d]["uv"] = v["uv"]
        by_day[d]["pv"] = v["pv"]

    # 🛑 날짜마다 **어디서·무엇으로** 들어왔는지를 같이 보낸다 (2026-09-09 온해님 요청).
    #    자료는 원래 날짜별로 쌓여 있었는데 합계만 보내느라 화면에서 하루를 못 골랐다.
    # 🛑 **무료로 연 것을 같이 내려보낸다** (2026-09-12 온해님 「사주 열람도 일별로」).
    #    `opens` 는 복채를 낸 것(`owned`)만 센다. 무료 열람은 `tap` 의 `open:*` 에 쌓인다.
    def _free_opens(day: str) -> int:
        t = (vis.get(day) or {}).get("tap") or {}
        return sum(int(v or 0) for k, v in t.items()
                   if k == "open" or str(k).startswith("open:"))

    daily = [{"day": d, **by_day[d],
              "free_opens": _free_opens(d),
              # 이미 쌓인 기록도 읽을 때 이름을 맞춘다
              "src": _tidy_map((vis.get(d) or {}).get("src") or {}),
              "ua": dict((vis.get(d) or {}).get("ua") or {})}
             for d in sorted(by_day) if d >= start]
    daily.reverse()

    def _sum(keep) -> dict[str, int]:
        out = {"sales": 0, "charges": 0, "signups": 0, "uv": 0, "pv": 0,
               "opens": 0, "asks": 0}
        for d, v in by_day.items():
            if not keep(d):
                continue
            for k in out:
                out[k] += v[k]
        return out

    by_month: dict[str, int] = defaultdict(int)
    for r in ch:
        by_month[r["day"][:7]] += r["price"]

    prod: dict[str, int] = defaultdict(int)
    for r in sp:
        prod[r["product"]] += 1

    # 유입경로 — 이번 달과 최근 N일
    src_month: dict[str, int] = defaultdict(int)
    src_recent: dict[str, int] = defaultdict(int)
    ua_recent: dict[str, int] = defaultdict(int)
    camp: dict[str, int] = defaultdict(int)
    for d, v in vis.items():
        for name, c in _tidy_map(v.get("src") or {}).items():
            if d.startswith(month):
                src_month[name] += c
            if d >= start:
                src_recent[name] += c
        if d >= start:
            for name, c in (v.get("ua") or {}).items():
                ua_recent[name] += c
            # 캠페인은 최근 N일치만 본다 — 지난 게시글까지 섞이면 지금 뭐가 되는지 흐려진다
            for name, c in (v.get("camp") or {}).items():
                camp[name] += c

    # 🛑 사람 수와 페이지 수가 거의 1:1 이면 사람이 아니다.
    #    사람은 한 명이 여러 페이지를 본다. 1:1 은 서로 다른 IP 에서 한 번씩 찍고 간 것 —
    #    링크 미리보기 크롤러다 (2026-09-05 스레드에서 실제로 겪었다).
    real = [v for d, v in vis.items() if d >= start]
    r_uv = sum(v["uv"] for v in real)
    r_pv = sum(v["pv"] for v in real)
    per = round(r_pv / r_uv, 2) if r_uv else 0.0

    # 🛑 **건별 내역을 함께 준다.** 총액만으로는 무엇이 팔렸는지 알 수 없다
    recent = sorted(ch, key=lambda r: r.get("at") or r["day"], reverse=True)[:50]
    return {
        "recent": recent,
        "today": {"day": today, **_sum(lambda d: d == today)},
        "month": {"month": month, **_sum(lambda d: d.startswith(month))},
        "total": {
            "sales": sum(r["price"] for r in ch),
            "charges": len(ch),
            "signups": len(su),
            # 🛑 사주 열람만. 「더 물어보기」는 `asks` 로 따로 센다 (2026-09-13)
            "opens": len([r for r in sp if not str(r.get("product", "")).startswith("ask:")]),
            "asks": len([r for r in sp if str(r.get("product", "")).startswith("ask:")]),
            "members": len(su),
            "legacy": len([m for m in members() if m["legacy"]]),
            "uv": sum(v["uv"] for v in vis.values()),
            "pv": sum(v["pv"] for v in vis.values()),
        },
        "members": members(),
        "daily": daily,
        "byMonth": [{"month": m, "sales": s} for m, s in sorted(by_month.items(), reverse=True)],
        "bySource": sorted(
            [{"name": n, "uv": c} for n, c in src_recent.items()],
            key=lambda x: x["uv"], reverse=True),
        "byClient": sorted(
            [{"name": n, "uv": c} for n, c in ua_recent.items()],
            key=lambda x: x["uv"], reverse=True),
        "crawlerHint": {
            "uv": r_uv, "pv": r_pv, "perPerson": per,
            # 1.3 미만이면 「한 명이 한 페이지만 보고 갔다」에 가깝다
            "suspicious": bool(r_uv >= 10 and per < 1.3),
            "unknownUa": ua_recent.get("기타 · 기타", 0),
        },
        "bySourceMonth": sorted(
            [{"name": n, "uv": c} for n, c in src_month.items()],
            key=lambda x: x["uv"], reverse=True),
        "byProduct": sorted(
            [{"product": p, "opens": c} for p, c in prod.items()],
            key=lambda x: x["opens"], reverse=True),
        # 캠페인별 유입 — 링크에 붙여 보낸 utm_campaign 으로 센다.
        # 같은 스레드라도 어느 글이 사람을 물어 왔는지 알아야 다음 글을 정한다.
        "byCampaign": sorted(
            [{"name": n, "uv": c} for n, c in camp.items()],
            key=lambda x: x["uv"], reverse=True)[:30],
        # 🛑 **유입 → 가입 → 결제**를 한 줄로 잇는다 (2026-09-11 온해님).
        #    「누가 왔나」까지만 알고 「누가 샀나」를 모르면 어느 글을 또 쓸지 정할 수 없다.
        #    가입할 때 계정에 적어 둔 `via` 로 묶는다.
        "byVia": _via_funnel(),
        # 🛑 **공유 통계** — 카드를 저장했거나 공유 단추를 누른 횟수 (2026-09-11).
        #    카드가 퍼져야 손님이 오는 구조라, 이 숫자가 곧 바이럴의 온도다.
        "byTap": _tap_sum(vis, start),
    }


def _tap_sum(vis: dict[str, Any], start: str) -> list[dict[str, Any]]:
    """최근 N일 공유 눌림. 무엇을 · 어느 상품에서."""
    LABEL = {"save": "이미지로 저장", "share": "공유하기",
             "sns": "SNS 로 바로", "copy": "링크 복사"}
    got: dict[str, int] = {}
    for day, v in vis.items():
        if day < start:
            continue
        for key, c in (v.get("tap") or {}).items():
            what, _, prod = str(key).partition(":")
            name = LABEL.get(what, what) + ((" · " + prod) if prod else "")
            got[name] = got.get(name, 0) + int(c)
    return sorted([{"name": n, "n": c} for n, c in got.items()],
                  key=lambda x: x["n"], reverse=True)[:20]


def _via_funnel() -> list[dict[str, Any]]:
    """어디서 온 사람이 가입하고 얼마를 썼나."""
    from modules import lamps as lamps_ops

    lamp = lamps_ops._read() or {}
    out: dict[str, dict[str, Any]] = {}
    for m in members():
        if m.get("legacy") and m.get("how") == "관리자":
            continue
        name = str(m.get("via") or "").strip() or "바로 들어옴"
        row = out.setdefault(name, {"name": name, "signups": 0, "buyers": 0, "sales": 0})
        row["signups"] += 1
        acc = lamp.get(m["email"]) or {}
        paid = sum(int(e.get("price") or 0) for e in acc.get("ledger", [])
                   if e.get("type") in ("charge", "premium", "refund")
                   and str(e.get("at", ""))[:10] >= lamps_ops.REAL_PAY_FROM)
        if paid:
            row["buyers"] += 1
            row["sales"] += paid
    return sorted(out.values(), key=lambda x: (-x["sales"], -x["signups"]))[:30]
