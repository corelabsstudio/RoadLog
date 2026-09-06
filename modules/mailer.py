"""손님에게 보내는 메일.

🛑 **Railway 는 바깥으로 나가는 SMTP 포트를 막는 일이 잦다.** 웨이크어게인에서
실제로 그래서 Resend(HTTPS)로 옮겼다. 그래서 여기서도 순서가 이렇다:

    1) Resend  — HTTPS 라 막히지 않는다. 이쪽이 정본
    2) SMTP    — 폴백. 열려 있는 환경에서만 붙는다

`modules/notify.py` 는 **관리자 폰 푸시**(ntfy·텔레그램)라 이것과 쓰임이 다르다.
손님에게 가는 메일은 전부 여기를 지난다.

## Railway 환경변수

    RESEND_API_KEY   re_...                       ← 이것만 넣으면 돈다
    MAIL_FROM        로드로그 <noreply@roadlog.co.kr>
    MAIL_REPLY_TO    corelabs.studio@gmail.com    (선택)

발신 도메인(roadlog.co.kr)은 Resend 대시보드에서 도메인을 추가하고
가비아 DNS 에 TXT·DKIM 레코드를 넣어야 Verified 가 된다.
🛑 **루트 CNAME(Railway) 은 건드리지 말 것.**

SMTP 로 쓸 때 (폴백):

    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    SMTP_SSL=1 (465) / SMTP_TLS=1 (587)
"""
from __future__ import annotations

import json
import os
import smtplib
import socket
import ssl
import urllib.error
import urllib.request
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

DEFAULT_FROM = "로드로그 <noreply@roadlog.co.kr>"


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def _bool_env(name: str, default: str = "0") -> bool:
    return _env(name, default) in {"1", "true", "True", "yes", "YES"}


def mail_from() -> str:
    return _env("MAIL_FROM") or _env("RESEND_FROM") or _env("SMTP_FROM") or DEFAULT_FROM


def mail_configured() -> bool:
    """메일을 보낼 수 있는 상태인가. 화면에 안내 문구를 고를 때도 쓴다."""
    if _env("RESEND_API_KEY"):
        return True
    return bool(_env("SMTP_HOST") and (_env("MAIL_FROM") or _env("SMTP_FROM")))


# ── Resend (정본) ────────────────────────────────────


def _send_via_resend(to: str, subject: str, body: str, html: str | None) -> bool:
    api_key = _env("RESEND_API_KEY")
    if not api_key:
        return False
    payload: dict = {"from": mail_from(), "to": [to], "subject": subject, "text": body}
    if html:
        payload["html"] = html
    reply_to = _env("MAIL_REPLY_TO") or _env("SMTP_REPLY_TO")
    if reply_to:
        payload["reply_to"] = reply_to
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "RoadLog/1.0 (+https://roadlog.co.kr)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            raw = res.read().decode("utf-8", "replace")
        print(f"[mailer] Resend 보냄 → {to!r}: {raw[:120]}", flush=True)
        return True
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        print(f"[mailer] Resend 실패 HTTP {e.code}: {err[:300]}", flush=True)
        return False
    except Exception as e:
        print(f"[mailer] Resend 실패 to={to!r}: {type(e).__name__}: {e}", flush=True)
        return False


# ── SMTP (폴백) ──────────────────────────────────────


def _ipv4_connect(host: str, port: int, timeout: float) -> socket.socket:
    """IPv4 로만 붙는다 — Railway 는 IPv6 로 나갈 때 errno 101 이 잦다."""
    last: Exception | None = None
    for _family, socktype, proto, _canon, sockaddr in socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_STREAM
    ):
        sock = socket.socket(socket.AF_INET, socktype, proto)
        sock.settimeout(timeout)
        try:
            sock.connect(sockaddr)
            return sock
        except OSError as e:
            last = e
            try:
                sock.close()
            except Exception:
                pass
    if last:
        raise last
    raise OSError(f"IPv4 경로 없음 {host}:{port}")


def _send_via_smtp_port(
    to: str,
    msg: EmailMessage,
    *,
    host: str,
    port: int,
    use_ssl: bool,
    use_tls: bool,
    user: str,
    password: str,
    timeout: float,
) -> bool:
    context = ssl.create_default_context()
    raw: socket.socket | None = None
    try:
        raw = _ipv4_connect(host, port, timeout)
        if use_ssl:
            ssock = context.wrap_socket(raw, server_hostname=host)
            raw = None  # 소유권이 넘어갔다
            smtp = smtplib.SMTP_SSL()
            smtp.sock = ssock
        else:
            smtp = smtplib.SMTP()
            smtp.sock = raw
            raw = None
        smtp.file = None
        smtp._host = host  # type: ignore[attr-defined]
        try:
            smtp.ehlo()
            if not use_ssl and use_tls:
                smtp.starttls(context=context)
                smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass
        print(f"[mailer] SMTP 보냄 → {to!r} via {host}:{port} ssl={use_ssl}", flush=True)
        return True
    except Exception as e:
        print(f"[mailer] SMTP 실패 to={to!r} {host}:{port}: {type(e).__name__}: {e}", flush=True)
        if raw is not None:
            try:
                raw.close()
            except Exception:
                pass
        return False


def _send_via_smtp(to: str, msg: EmailMessage) -> bool:
    host = _env("SMTP_HOST")
    if not host:
        return False
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS").replace(" ", "")
    # 짧게 끊는다. Railway 가 막고 있으면 여기서 50초씩 매달릴 이유가 없다
    timeout = float(_env("SMTP_TIMEOUT", "8") or "8")
    pref_port = int(_env("SMTP_PORT", "465") or "465")
    pref_ssl = _bool_env("SMTP_SSL", "1" if pref_port == 465 else "0") or pref_port == 465
    pref_tls = _bool_env("SMTP_TLS", "0" if pref_ssl else "1")

    attempts: list[tuple[int, bool, bool]] = [(pref_port, pref_ssl, pref_tls and not pref_ssl)]
    alt = (587, False, True) if pref_port == 465 else (465, True, False)
    if alt not in attempts:
        attempts.append(alt)

    for port, use_ssl, use_tls in attempts:
        if _send_via_smtp_port(
            to, msg, host=host, port=port, use_ssl=use_ssl,
            use_tls=use_tls, user=user, password=password, timeout=timeout,
        ):
            return True
    return False


# ── 보내기 ───────────────────────────────────────────


def send_mail(to: str, subject: str, body: str, *, html: str | None = None) -> bool:
    to = (to or "").strip()
    if not to:
        print("[mailer] 받는 사람이 없다", flush=True)
        return False
    # 카카오가 이메일을 안 주면 우리가 만들어 붙인 주소다. 보낼 곳이 아니다.
    if to.lower().endswith(".local"):
        print(f"[mailer] 보낼 수 없는 주소 {to!r} (소셜 전용)", flush=True)
        return False

    if _env("RESEND_API_KEY") and _send_via_resend(to, subject, body, html):
        return True

    if _env("SMTP_HOST"):
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = mail_from()
        msg["To"] = to
        msg["Date"] = formatdate(localtime=False)
        msg["Message-ID"] = make_msgid(domain="roadlog.co.kr")
        reply_to = _env("MAIL_REPLY_TO") or _env("SMTP_REPLY_TO")
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body)
        if html:
            msg.add_alternative(html, subtype="html")
        if _send_via_smtp(to, msg):
            return True

    print(f"[mailer] 모든 경로 실패 {to!r}", flush=True)
    return False


# ── 문안 ─────────────────────────────────────────────
# 무냥이 말투(~해요). 약관·개인정보만 합쇼체다.

_WRAP = (
    "<div style='font-family:Pretendard,-apple-system,BlinkMacSystemFont,system-ui,sans-serif;"
    "max-width:520px;margin:0 auto;padding:28px 24px;color:#2f2d3a;line-height:1.75;"
    "word-break:keep-all'>{body}"
    "<p style='margin-top:28px;padding-top:16px;border-top:1px solid #ebe6dc;"
    "color:#7a7785;font-size:.82rem'>로드로그 · 코어랩스<br/>"
    "<a href='https://roadlog.co.kr' style='color:#6f5bd3'>roadlog.co.kr</a></p></div>"
)


def send_password_reset_link(to: str, link: str, *, minutes: int = 30) -> bool:
    text = (
        "로드로그 비밀번호를 다시 정하시려는 거 맞죠?\n\n"
        f"아래 주소를 열면 새 비밀번호를 정하실 수 있어요.\n{link}\n\n"
        f"이 주소는 {minutes}분 뒤에 닫히고, 한 번 쓰면 다시 열리지 않아요.\n"
        "누르지 않으시면 지금 비밀번호는 그대로예요.\n\n"
        "요청하신 적이 없다면 이 메일은 그냥 두셔도 돼요.\n"
        "충전해 두신 등불은 그대로 있어요.\n\n"
        "— 로드로그 · 코어랩스\n"
    )
    html = _WRAP.format(
        body=(
            "<h2 style='font-size:1.15rem;margin:0 0 14px;color:#2f2d3a'>비밀번호를 다시 정할게요</h2>"
            "<p style='margin:0 0 20px'>아래 단추를 누르면 새 비밀번호를 정하는 화면이 열려요.</p>"
            f"<p style='margin:0 0 20px'><a href='{link}' "
            "style='display:inline-block;background:#6f5bd3;color:#fff;text-decoration:none;"
            "font-weight:700;padding:14px 26px;border-radius:10px'>새 비밀번호 정하기</a></p>"
            f"<p style='margin:0 0 8px;color:#7a7785;font-size:.88rem'>이 주소는 {minutes}분 뒤에 닫혀요. "
            "한 번 쓰면 다시 열리지 않아요.</p>"
            "<p style='margin:0 0 8px;color:#7a7785;font-size:.88rem'>요청하신 적이 없다면 그냥 두셔도 돼요. "
            "누르지 않으면 지금 비밀번호는 그대로고, 충전해 두신 등불도 그대로예요.</p>"
            "<p style='margin:16px 0 0;color:#9b96a9;font-size:.78rem;word-break:break-all'>"
            f"단추가 안 눌리면 이 주소를 붙여 넣으세요<br/>{link}</p>"
        )
    )
    return send_mail(to, "[로드로그] 비밀번호 다시 정하기", text, html=html)


_SOCIAL_LABEL = {"kakao": "카카오", "google": "구글"}


def send_social_only_notice(to: str, provider: str) -> bool:
    """비밀번호 없이 소셜로만 들어오시는 분께.

    🛑 화면에서 「이 계정은 카카오예요」라고 알려 주면 남의 이메일로 가입 여부를
    캐낼 수 있다. 그래서 그 안내는 **본인만 볼 수 있는 메일 안에** 둔다.
    """
    label = _SOCIAL_LABEL.get(provider, provider or "소셜")
    text = (
        f"이 계정은 {label}로 만드신 계정이에요.\n\n"
        "따로 정해 둔 비밀번호가 없어서 다시 정할 것도 없어요.\n"
        f"로드로그에서 「{label}로 시작하기」를 누르시면 그대로 들어오실 수 있어요.\n\n"
        "https://roadlog.co.kr\n\n"
        "충전해 두신 등불은 그대로 있어요.\n\n"
        "— 로드로그 · 코어랩스\n"
    )
    html = _WRAP.format(
        body=(
            "<h2 style='font-size:1.15rem;margin:0 0 14px;color:#2f2d3a'>"
            f"{label}로 만드신 계정이에요</h2>"
            "<p style='margin:0 0 16px'>따로 정해 둔 비밀번호가 없어서, 다시 정할 것도 없어요. "
            f"로드로그에서 <b>{label}로 시작하기</b>를 누르시면 그대로 들어오실 수 있어요.</p>"
            "<p style='margin:0 0 20px'><a href='https://roadlog.co.kr' "
            "style='display:inline-block;background:#6f5bd3;color:#fff;text-decoration:none;"
            "font-weight:700;padding:14px 26px;border-radius:10px'>로드로그 열기</a></p>"
            "<p style='margin:0;color:#7a7785;font-size:.88rem'>충전해 두신 등불은 그대로 있어요.</p>"
        )
    )
    return send_mail(to, "[로드로그] 로그인하시는 방법", text, html=html)


def send_password_changed(to: str) -> bool:
    text = (
        "로드로그 비밀번호가 방금 바뀌었어요.\n\n"
        "다른 기기에 로그인돼 있던 것은 모두 끊었어요. 새 비밀번호로 다시 들어와 주세요.\n"
        "충전해 두신 등불은 그대로 있어요.\n\n"
        "본인이 바꾼 게 아니라면 바로 알려 주세요 — corelabs.studio@gmail.com\n\n"
        "— 로드로그 · 코어랩스\n"
    )
    html = _WRAP.format(
        body=(
            "<h2 style='font-size:1.15rem;margin:0 0 14px;color:#2f2d3a'>비밀번호가 바뀌었어요</h2>"
            "<p style='margin:0 0 16px'>다른 기기에 로그인돼 있던 것은 모두 끊었어요. "
            "새 비밀번호로 다시 들어와 주세요. 충전해 두신 등불은 그대로 있어요.</p>"
            "<p style='margin:0;color:#a33d3d;font-size:.88rem'>본인이 바꾼 게 아니라면 바로 알려 주세요 — "
            "<a href='mailto:corelabs.studio@gmail.com' style='color:#a33d3d'>corelabs.studio@gmail.com</a></p>"
        )
    )
    return send_mail(to, "[로드로그] 비밀번호가 바뀌었어요", text, html=html)
