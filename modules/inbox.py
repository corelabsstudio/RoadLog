# -*- coding: utf-8 -*-
"""손님에게 보내는 알림함.

왜: 가입하면 등불 300개와 무료 열람 1회권이 나가는데 **화면이 아무 말도 안 했다.**
서버는 `welcome: 300` 을 응답에 담아 보내는데 `account.js` 가 그 값을 받고 버렸다.
등불 내역에 「가입 선물」로만 남아서, 들어가 보지 않으면 받은 줄도 몰랐다.
받은 줄 모르면 준 게 아니다 (2026-09-08 온해님 지적 · 폭스바니는 편지 아이콘으로 알린다).

앞으로 쓸 곳
  · 가입 선물 지급          · 선착순 1회권 지급과 남은 자리
  · 친구 추천으로 등불 받음   · **결제가 열렸을 때 공지** (카드사 심사 통과 시)
  · 리포트를 다 썼을 때

🛑 **알림은 사람이 읽는 글이다.** 「지급 완료」 같은 전산 말투를 쓰지 않는다.
   무냥이 말투(~해요)로 쓰고, 무엇을 받았는지와 그걸로 무엇을 할 수 있는지까지 적는다.
🛑 **한 사람에게 같은 알림을 두 번 넣지 않는다.** `key` 로 막는다.
🛑 파일 하나에 다 넣는다. 회원 수가 만 명을 넘으면 그때 갈라도 늦지 않다.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

MAX_PER_USER = 50           # 한 사람당 이만큼만 남긴다. 오래된 것부터 버린다


def _path() -> Path:
    from modules.config import DATA_DIR
    d = Path(DATA_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d / "inbox.json"


def _read() -> dict[str, list[dict[str, Any]]]:
    p = _path()
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict[str, list[dict[str, Any]]]) -> None:
    p = _path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def _key(email: str) -> str:
    return (email or "").strip().lower()


def push(email: str, title: str, body: str = "", *, key: str = "",
         icon: str = "", link: str = "") -> bool:
    """알림 하나를 넣는다. `key` 가 이미 있으면 넣지 않고 False 를 준다."""
    e = _key(email)
    if not e or not title:
        return False
    data = _read()
    rows = data.get(e) or []
    if key and any(r.get("key") == key for r in rows):
        return False
    rows.append({
        "id": "%d-%d" % (int(time.time() * 1000), len(rows)),
        "key": key or "",
        "title": title,
        "body": body,
        "icon": icon or "",
        "link": link or "",
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "read": False,
    })
    data[e] = rows[-MAX_PER_USER:]
    _write(data)
    return True


def push_all(emails: list[str], title: str, body: str = "", *, key: str = "",
             icon: str = "", link: str = "") -> int:
    """여러 사람에게 같은 알림. 공지에 쓴다. 넣은 수를 준다."""
    n = 0
    data = _read()
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    for raw in emails:
        e = _key(raw)
        if not e:
            continue
        rows = data.get(e) or []
        if key and any(r.get("key") == key for r in rows):
            continue
        rows.append({
            "id": "%d-%d" % (int(time.time() * 1000), n),
            "key": key or "", "title": title, "body": body,
            "icon": icon or "", "link": link or "",
            "at": now, "read": False,
        })
        data[e] = rows[-MAX_PER_USER:]
        n += 1
    if n:
        _write(data)
    return n


def listing(email: str) -> dict[str, Any]:
    """그 사람의 알림. 새것부터."""
    rows = _read().get(_key(email)) or []
    rows = sorted(rows, key=lambda r: r.get("at") or "", reverse=True)
    return {"items": rows, "unread": sum(1 for r in rows if not r.get("read"))}


def mark_read(email: str, ids: list[str] | None = None) -> int:
    """읽음 표시. ids 가 없으면 전부."""
    e = _key(email)
    data = _read()
    rows = data.get(e) or []
    if not rows:
        return 0
    want = set(ids or [])
    n = 0
    for r in rows:
        if r.get("read"):
            continue
        if want and r.get("id") not in want:
            continue
        r["read"] = True
        n += 1
    if n:
        data[e] = rows
        _write(data)
    return n
