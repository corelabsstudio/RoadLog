# -*- coding: utf-8 -*-
"""반려동물 관상 **명예의 전당** — 등록 · 좋아요 · 이달의 관상왕 (2026-09-14 온해님 기획).

표 `pet_physiognomy_ranks` 를 **DATA_DIR 의 JSON 한 벌**로 둔다 (사이트의 다른 기록과 같은 방식 ·
Railway 볼륨). 칸은 기획서 그대로다:

| 칸 | 뜻 |
|---|---|
| id | UUID |
| pet_name | 손님이 적은 이름 |
| image_url | `/api/pets/<id>/image` — 사진은 `DATA_DIR/pet_hall/<id>.jpg` |
| card_title | 관상 타이틀 (share_card_data.card_title) |
| like_count | 좋아요 수 (기본 0) |
| character_design | 제미나이가 쓴 2D 캐릭터화 칸 |
| is_monthly_winner | 이달의 관상왕 (그달이 끝나면 굳힌다 · 진행 중인 달은 1위에게 붙여 보여 준다) |

🛑 **사진은 손님이 「명예의 전당에 올리기」에 동의했을 때만 남긴다.** 관상 결과만 볼 때는 여전히 안 남긴다.
🛑 **관상 결과가 서버에 있는 사진만 올릴 수 있다.** 사진 해시로 저장본(`pet_read`)을 찾아 맞춰 본다 —
   동물이 아니라고 걸러진 사진, 결과 없이 아무 사진이나 올리는 것을 막는다.
🛑 **좋아요 중복 막기** — 브라우저 쿠키로 한 번. IP 는 **같은 IP 에서 한 아이에게 5번까지만** 둔다.
   IP 하나로만 막으면 휴대폰 통신사가 여러 사람을 한 IP 로 묶는 경우 다른 사람 표까지 막힌다.
🛑 IP 는 **해시로만** 남긴다. 원래 주소는 저장하지 않는다.

**갤러리 · 댓글 (2026-09-14 온해님 「인스타그램 감성 명예의 전당 페이지」)**
기획서의 표 두 개를 이 사이트 방식(JSON 한 벌씩)으로 둔다.

| 기획서 표 | 여기 |
|---|---|
| `pet_gallery_posts` | 위 `pet_physiognomy_ranks.json` 의 줄 — `summary` · `comment_count` 칸을 더했다 |
| `pet_gallery_comments` | `DATA_DIR/pet_gallery_comments.json` (id · post_id · nickname · content · created_at) |

🛑 **댓글은 로그인 없이 쓴다**(기획서). 대신 막는 것: 주소(링크) 금지 · 같은 IP 하루 30개 ·
   같은 브라우저 10초에 1개 · 닉네임 12자 · 내용 200자.
🛑 **지우기** — 쓴 브라우저(쿠키) · 같은 계정 · 비밀번호(적었을 때) · 관리자. 비밀번호는 PBKDF2 해시만 남긴다.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json
import re
import os
import threading
import uuid
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_KST = _dt.timezone(_dt.timedelta(hours=9))
IP_LIKE_CAP = 5            # 같은 IP 에서 한 아이에게 줄 수 있는 좋아요 수
SHARE_DAILY_CAP = 5        # 한 계정이 하루에 올릴 수 있는 수
NAME_MAX = 12


def _dir() -> Path:
    return Path(os.getenv("DATA_DIR") or ".")


def _file() -> Path:
    return _dir() / "pet_physiognomy_ranks.json"


def image_path(pid: str) -> Path:
    return _dir() / "pet_hall" / ("%s.jpg" % pid)


def _read() -> dict[str, Any]:
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        return {"rows": [], "winners": {}}


def _write(d: dict[str, Any]) -> None:
    f = _file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)                                       # 반쯤 쓴 파일이 남지 않게


def month_of(ts: str | None = None) -> str:
    """한국 날짜 기준 달 (YYYY-MM). 🛑 서버는 UTC 다 — 9월 1일 새벽이 8월로 잡히지 않게."""
    if ts:
        return ts[:7]
    return _dt.datetime.now(_KST).strftime("%Y-%m")


def _now() -> str:
    return _dt.datetime.now(_KST).strftime("%Y-%m-%dT%H:%M:%S")


def _h(s: str) -> str:
    return hashlib.sha256(("roadlog-pet|" + (s or "")).encode("utf-8")).hexdigest()[:24]


def snapshot(result: dict[str, Any]) -> dict[str, Any]:
    """갤러리 상세 창에 쓸 관상 결과 조각. 올릴 때 한 번 떠 둔다 — 저장본이 나중에 바뀌어도 올린 모습 그대로."""
    sc = result.get("share_card_data") or {}
    stats = {}
    for k, v in (result.get("stats") or {}).items():
        try:
            stats[str(k)] = max(0, min(100, int(v)))
        except (TypeError, ValueError):
            continue
    return {
        "summary": str(result.get("summary") or "")[:80],
        "factcheck_short": str(sc.get("main_factcheck_short") or "")[:120],
        "advice": str(result.get("one_line_advice") or "")[:120],
        "keywords": [str(x)[:12] for x in (sc.get("pet_keywords") or [])][:3],
        "stats": stats,
        "stat_names": {str(k): str(v)[:16] for k, v in (result.get("stat_names") or {}).items()},
    }


def public(row: dict[str, Any], *, winner: bool = False) -> dict[str, Any]:
    """밖으로 내보내는 칸만. 🛑 등록한 사람 이메일·투표 기록은 내보내지 않는다."""
    snap = row.get("snap") or {}
    return {
        "summary": snap.get("summary", ""),
        "factcheck_short": snap.get("factcheck_short", ""),
        "advice": snap.get("advice", ""),
        "keywords": snap.get("keywords", []),
        "stats": snap.get("stats", {}),
        "stat_names": snap.get("stat_names", {}),
        "owner_label": row.get("owner_label", ""),
        "comment_count": int(row.get("comment_count", 0)),
        "id": row["id"],
        "pet_name": row.get("pet_name", ""),
        "image_url": "/api/pets/%s/image" % row["id"],
        "card_title": row.get("card_title", ""),
        "title": row.get("title", ""),
        "grade_badge": row.get("grade_badge", ""),
        "like_count": int(row.get("like_count", 0)),
        "character_design": row.get("character_design") or {},
        "is_monthly_winner": bool(row.get("is_monthly_winner") or winner),
        "month": row.get("month", ""),
        "created_at": row.get("created_at", ""),
    }


def _settle(d: dict[str, Any]) -> bool:
    """끝난 달의 1위를 굳힌다. 바뀐 게 있으면 True."""
    now = month_of()
    changed = False
    months = {r.get("month") for r in d["rows"] if not r.get("hidden")}
    for m in sorted(x for x in months if x and x < now):
        if m in d["winners"]:
            continue
        top = _ranked([r for r in d["rows"] if r.get("month") == m and not r.get("hidden")])
        if top and int(top[0].get("like_count", 0)) > 0:
            d["winners"][m] = top[0]["id"]
            top[0]["is_monthly_winner"] = True
        else:
            d["winners"][m] = ""
        changed = True
    return changed


def _ranked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # 좋아요 많은 순 · 같으면 먼저 올린 아이가 위
    return sorted(rows, key=lambda r: (-int(r.get("like_count", 0)), r.get("created_at", "")))


def add(*, owner: str, shot: str, pet_name: str, jpeg: bytes, result: dict[str, Any], owner_label: str = "") -> dict[str, Any]:
    """명예의 전당에 올린다. 같은 사진은 한 번만."""
    name = " ".join(str(pet_name or "").split())[:NAME_MAX]
    if not name:
        raise ValueError("아이 이름을 적어 주세요.")
    sc = result.get("share_card_data") or {}
    with _LOCK:
        d = _read()
        for r in d["rows"]:
            if r.get("shot") == shot and not r.get("hidden"):
                return public(r)                          # 이미 올린 사진 — 그 칸을 그대로 준다
        today = _now()[:10]
        mine_today = sum(1 for r in d["rows"] if r.get("owner") == _h(owner) and r.get("created_at", "")[:10] == today)
        if mine_today >= SHARE_DAILY_CAP:
            raise PermissionError("오늘은 명예의 전당에 여기까지 올릴 수 있어요. 내일 다시 올려 주세요.")
        pid = str(uuid.uuid4())
        ip = image_path(pid)
        ip.parent.mkdir(parents=True, exist_ok=True)
        ip.write_bytes(jpeg)
        row = {
            "id": pid, "pet_name": name, "card_title": sc.get("card_title", ""),
            "title": result.get("title", ""), "grade_badge": sc.get("grade_badge", ""),
            "like_count": 0, "character_design": result.get("character_design") or {},
            "is_monthly_winner": False, "month": month_of(), "created_at": _now(),
            "shot": shot, "owner": _h(owner), "voters": [], "ips": {}, "hidden": False,
            "snap": snapshot(result), "owner_label": owner_label, "comment_count": 0,
        }
        d["rows"].append(row)
        _settle(d)
        _write(d)
        return public(row)


def like(pid: str, *, voter: str, ip: str) -> dict[str, Any]:
    """좋아요 1. 이미 누른 브라우저면 그대로 돌려준다(already)."""
    v, i = _h("v|" + voter), _h("ip|" + ip)
    with _LOCK:
        d = _read()
        row = next((r for r in d["rows"] if r["id"] == pid and not r.get("hidden")), None)
        if not row:
            raise KeyError(pid)
        if v in row.setdefault("voters", []):
            return {"ok": True, "already": True, "like_count": int(row.get("like_count", 0))}
        ips = row.setdefault("ips", {})
        if int(ips.get(i, 0)) >= IP_LIKE_CAP:
            return {"ok": False, "already": True, "like_count": int(row.get("like_count", 0))}
        row["voters"].append(v)
        ips[i] = int(ips.get(i, 0)) + 1
        row["like_count"] = int(row.get("like_count", 0)) + 1
        _write(d)
        return {"ok": True, "already": False, "like_count": row["like_count"]}


def fill_missing(loader) -> None:
    """상세 조각(`snap`)이 없는 옛 줄을 관상 저장본으로 한 번 채운다. loader(shot) → 저장본 dict | None."""
    with _LOCK:
        d = _read()
        todo = [r for r in d["rows"] if "snap" not in r and r.get("shot")]
        if not todo:
            return
        for r in todo:
            try:
                res = loader(r["shot"]) or {}
            except Exception:                              # noqa: BLE001
                res = {}
            r["snap"] = snapshot(res)
        _write(d)


def hall(month: str | None = None, limit: int = 30, sort: str = "likes") -> dict[str, Any]:
    """목록. `sort=likes`(실시간 랭킹순) · `latest`(최신순).
    🛑 **순위(rank)는 정렬과 상관없이 좋아요 순위다** — 최신순으로 봐도 1~3위 왕관이 같은 아이에게 붙는다.
    진행 중인 달은 지금 1위에게 「이달의 관상왕」을 붙여 보여 준다."""
    m = month_of() if not month else month[:7]
    with _LOCK:
        d = _read()
        if _settle(d):
            _write(d)
        rows = _ranked([r for r in d["rows"] if r.get("month") == m and not r.get("hidden")])
        fixed = d["winners"].get(m)
    out = []
    for n, r in enumerate(rows):
        win = (r["id"] == fixed) if fixed is not None else (n == 0 and int(r.get("like_count", 0)) > 0)
        out.append({**public(r, winner=win), "rank": n + 1})
    if sort == "latest":
        out.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"month": m, "settled": fixed is not None, "sort": "latest" if sort == "latest" else "likes",
            "items": out[:max(1, min(limit, 100))]}


def hide(pid: str) -> bool:
    """관리자가 내린다. 🛑 지우지 않고 숨긴다 — 잘못 내렸을 때 되돌릴 수 있게."""
    with _LOCK:
        d = _read()
        for r in d["rows"]:
            if r["id"] == pid:
                r["hidden"] = True
                _write(d)
                return True
    return False


def exists(pid: str) -> bool:
    with _LOCK:
        return any(r["id"] == pid and not r.get("hidden") for r in _read()["rows"])


# ── 댓글 (기획서 `pet_gallery_comments`) ─────────────────────────────
COMMENT_NICK_MAX = 12
COMMENT_MAX = 200
COMMENT_IP_DAILY = 30
COMMENT_GAP_SEC = 10
_LINK = re.compile(r"(https?://|www\.|\.(com|kr|net|org|io|me|ly|gg)(/|\b))", re.I)


def _cfile() -> Path:
    return _dir() / "pet_gallery_comments.json"


def _cread() -> dict[str, Any]:
    try:
        return json.loads(_cfile().read_text(encoding="utf-8"))
    except Exception:                                    # noqa: BLE001
        return {"rows": []}


def _cwrite(d: dict[str, Any]) -> None:
    f = _cfile()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(f)


def _pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()


def _cpublic(c: dict[str, Any], *, voter: str, user: str) -> dict[str, Any]:
    mine = bool((voter and c.get("author") == _h("v|" + voter)) or (user and c.get("user") == _h(user)))
    return {"id": c["id"], "post_id": c["post_id"], "nickname": c.get("nickname", ""), "content": c.get("content", ""),
            "created_at": c.get("created_at", ""), "mine": mine, "has_pw": bool(c.get("pw"))}


def _set_count(pid: str, n: int) -> None:
    d = _read()
    for r in d["rows"]:
        if r["id"] == pid:
            r["comment_count"] = n
            _write(d)
            return


def comments(pid: str, *, voter: str = "", user: str = "") -> list[dict[str, Any]]:
    """오래된 것부터 (인스타그램처럼 아래로 쌓인다)."""
    with _LOCK:
        rows = [c for c in _cread()["rows"] if c.get("post_id") == pid and not c.get("hidden")]
    rows.sort(key=lambda c: c.get("created_at", ""))
    return [_cpublic(c, voter=voter, user=user) for c in rows]


def add_comment(pid: str, *, nickname: str, content: str, password: str = "", voter: str, ip: str,
                user: str = "") -> dict[str, Any]:
    nick = " ".join(str(nickname or "").split())[:COMMENT_NICK_MAX]
    text = " ".join(str(content or "").split())
    pw = str(password or "")
    if not nick:
        raise ValueError("닉네임을 적어 주세요.")
    if not text:
        raise ValueError("댓글 내용을 적어 주세요.")
    if len(text) > COMMENT_MAX:
        raise ValueError("댓글은 %d자까지 쓸 수 있어요." % COMMENT_MAX)
    if _LINK.search(text) or _LINK.search(nick):
        raise ValueError("댓글에는 주소(링크)를 넣을 수 없어요.")
    if pw and not (4 <= len(pw) <= 16):
        raise ValueError("비밀번호는 4~16자로 적어 주세요.")
    now = _now()
    v, i = _h("v|" + voter), _h("ip|" + ip)
    with _LOCK:
        if not any(r["id"] == pid and not r.get("hidden") for r in _read()["rows"]):
            raise KeyError(pid)
        d = _cread()
        today = now[:10]
        if sum(1 for c in d["rows"] if c.get("ip") == i and c.get("created_at", "")[:10] == today) >= COMMENT_IP_DAILY:
            raise PermissionError("오늘은 댓글을 여기까지 쓸 수 있어요. 내일 다시 써 주세요.")
        mine = [c for c in d["rows"] if c.get("author") == v]
        if mine:
            last = max(c.get("created_at", "") for c in mine)
            try:
                gap = (_dt.datetime.fromisoformat(now) - _dt.datetime.fromisoformat(last)).total_seconds()
            except ValueError:
                gap = COMMENT_GAP_SEC
            if gap < COMMENT_GAP_SEC:
                raise PermissionError("조금만 천천히 써 주세요. 잠시 뒤에 다시 올릴 수 있어요.")
        salt = uuid.uuid4().hex
        c = {"id": str(uuid.uuid4()), "post_id": pid, "nickname": nick, "content": text, "created_at": now,
             "author": v, "ip": i, "user": _h(user) if user else "", "salt": salt,
             "pw": _pw(pw, salt) if pw else "", "hidden": False}
        d["rows"].append(c)
        _cwrite(d)
        n = sum(1 for x in d["rows"] if x.get("post_id") == pid and not x.get("hidden"))
        _set_count(pid, n)
    return {"comment": _cpublic(c, voter=voter, user=user), "comment_count": n}


def delete_comment(pid: str, cid: str, *, voter: str = "", user: str = "", password: str = "",
                   admin: bool = False) -> int:
    """지운다(숨김). 🛑 쓴 브라우저 · 같은 계정 · 비밀번호 · 관리자 중 하나여야 한다. 남은 댓글 수를 돌려준다."""
    with _LOCK:
        d = _cread()
        c = next((x for x in d["rows"] if x["id"] == cid and x.get("post_id") == pid and not x.get("hidden")), None)
        if not c:
            raise KeyError(cid)
        ok = admin or (voter and c.get("author") == _h("v|" + voter)) or (user and c.get("user") == _h(user))
        if not ok and password and c.get("pw"):
            ok = hmac.compare_digest(_pw(str(password), c.get("salt", "")), c["pw"])
        if not ok:
            raise PermissionError("비밀번호가 맞지 않아요." if password else "내가 쓴 댓글만 지울 수 있어요.")
        c["hidden"] = True
        _cwrite(d)
        n = sum(1 for x in d["rows"] if x.get("post_id") == pid and not x.get("hidden"))
        _set_count(pid, n)
    return n
