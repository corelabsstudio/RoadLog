"""
로드로그 (RoadLog) — 프리미엄 웹 서버
FastAPI + 정적 프론트엔드 + 기존 modules 재사용

실행:
  .venv\\Scripts\\python.exe -m uvicorn server:app --reload --port 8501
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from fastapi import FastAPI, File, Header, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from modules import db
from modules.config import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    ALLOW_DEMO_BILLING_UPGRADE,
    APP_FULL,
    APP_TAGLINE,
    APP_TITLE,
    CONTACT_EMAIL,
    CONTACT_FORM_URL,
    DATA_DIR,
    DEFAULT_USER_SETTINGS,
    ENTERPRISE_PAYMENT_URL,
    ENTERPRISE_PRICE_KRW,
    FREE_MONTHLY_LIMIT,
    OPENAI_API_KEY,
    PRO_PAYMENT_URL,
    PRO_PRICE_KRW,
    STUDIO_NAME,
    STUDIO_NAME_EN,
)
from modules.export import export_docx, export_excel, export_pdf
from modules.generator import generate_driving_log
from modules import style_learn
from modules import admin_ops
from modules.validator import validate_log

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

app = FastAPI(title=APP_FULL, version="3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 토큰 세션 — 메모리 + 디스크 영속화 (재접속 시 자동 로그인 유지)
_sessions: dict[str, dict] = {}
_SESSIONS_PATH = DATA_DIR / "sessions.json"


def _load_sessions_from_disk() -> None:
    """재시작 후에도 localStorage 토큰이 유효하도록 세션 복원."""
    if not _SESSIONS_PATH.exists():
        return
    try:
        raw = json.loads(_SESSIONS_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        for token, meta in raw.items():
            if not token or not isinstance(meta, dict):
                continue
            email = (meta.get("email") or "").strip().lower()
            if not email:
                continue
            user = db.get_user(email)
            if user:
                _sessions[token] = admin_ops.enrich_user_flags(user) or user
    except Exception:
        pass


def _persist_sessions() -> None:
    try:
        payload = {}
        for token, user in _sessions.items():
            email = (user.get("email") or "").strip().lower()
            if email:
                payload[token] = {
                    "email": email,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
        _SESSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SESSIONS_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# 관리자(소유자) 계정 자동 생성 — 회원가입 없이 admin 로그인 가능
try:
    db.ensure_admin_owner()
except Exception:
    pass

_load_sessions_from_disk()


def _token_user(authorization: str | None) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "로그인이 필요합니다.")
    token = authorization.removeprefix("Bearer ").strip()
    user = _sessions.get(token)
    if not user:
        # 디스크에서 재로드 시도 (다른 워커/재시작 직후)
        _load_sessions_from_disk()
        user = _sessions.get(token)
    if not user:
        raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인해 주세요.")
    # plan / VIP 최신화
    fresh = db.get_user(user["email"])
    if fresh:
        user = admin_ops.enrich_user_flags(fresh)
        _sessions[token] = user
    else:
        user = admin_ops.enrich_user_flags(user) or user
        _sessions[token] = user
    return user


def _require_admin(authorization: str | None) -> dict:
    user = _token_user(authorization)
    if not user.get("is_admin"):
        raise HTTPException(403, "관리자만 접근할 수 있습니다.")
    return user


# ── Models ────────────────────────────────────────────


class AuthBody(BaseModel):
    email: str
    password: str
    name: str = ""


class GenerateBody(BaseModel):
    """구조화 입력 우선. raw_text는 선택(추가 메모)."""
    raw_text: str = ""
    settings: dict[str, Any] | None = None
    # 구조화 필드 (권장)
    vehicle_number: str = ""
    odometer_start: float | None = None
    odometer_end: float | None = None
    lunch_restaurant: str = ""
    morning_places: str = ""
    afternoon_places: str = ""
    form: dict[str, Any] | None = None


class SettingsBody(BaseModel):
    settings: dict[str, Any]


class ExportBody(BaseModel):
    log: dict[str, Any]
    format: str  # excel | pdf | docx


class StyleTextBody(BaseModel):
    title: str = "붙여넣기 일지"
    text: str


# ── API ───────────────────────────────────────────────


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "app": APP_TITLE,
        "storage": db.supabase_status(),
        "openai": bool(OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-xxxx")),
    }


@app.get("/api/meta")
def meta():
    billing = admin_ops.load_billing_config()
    return {
        "title": APP_TITLE,
        "tagline": APP_TAGLINE,
        "full": APP_FULL,
        "studio": STUDIO_NAME,
        "studio_en": STUDIO_NAME_EN,
        "contact_email": CONTACT_EMAIL,
        "contact_form_url": CONTACT_FORM_URL or "",
        "free_limit": FREE_MONTHLY_LIMIT,
        "pro_price": int(billing.get("pro_price_krw") or PRO_PRICE_KRW),
        "enterprise_price": int(
            billing.get("enterprise_price_krw") or ENTERPRISE_PRICE_KRW
        ),
        "pro_url": PRO_PAYMENT_URL,
        "enterprise_url": ENTERPRISE_PAYMENT_URL,
        "demo_billing_upgrade": ALLOW_DEMO_BILLING_UPGRADE,
        "default_settings": DEFAULT_USER_SETTINGS,
        "default_templates_url": "/assets/templates/manifest.json",
    }


class UpgradeBody(BaseModel):
    plan: str  # pro | enterprise


@app.post("/api/billing/upgrade")
def billing_upgrade(body: UpgradeBody, authorization: str | None = Header(default=None)):
    """
    요금제 업그레이드.

    기본: 비활성 (결제 없이 plan 변경 불가).
    로컬 데모에서만 ALLOW_DEMO_BILLING_UPGRADE=true 로 허용.
    운영에서는 결제 웹훅/관리자 수동 등록으로 plan을 변경하세요.
    """
    user = _token_user(authorization)
    if not ALLOW_DEMO_BILLING_UPGRADE:
        raise HTTPException(
            403,
            "결제가 확인된 뒤 요금제가 적용됩니다. 아래 결제 링크로 진행하거나 문의해 주세요.",
        )

    plan = (body.plan or "").strip().lower()
    email = user["email"]
    if plan == "pro":
        ok = db.upgrade_to_pro(email, note="웹 요금제 Pro 업그레이드 (데모)")
    elif plan in ("enterprise", "ent"):
        ok = db.upgrade_to_enterprise(email, note="웹 요금제 Enterprise 업그레이드 (데모)")
    else:
        raise HTTPException(400, "plan은 pro 또는 enterprise 여야 합니다.")
    if not ok:
        raise HTTPException(500, "업그레이드 처리에 실패했습니다.")
    fresh = db.get_user(email) or user
    fresh = admin_ops.enrich_user_flags(fresh) or fresh
    # 세션 갱신
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        if token in _sessions:
            _sessions[token] = fresh
    return {
        "ok": True,
        "user": fresh,
        "message": "Enterprise로 전환되었습니다. (데모)"
        if plan in ("enterprise", "ent")
        else "Pro로 전환되었습니다. (데모)",
        "demo": True,
    }


@app.get("/api/templates/defaults")
def default_templates():
    """사이트 기본 제공 운행일지 서식 목록 (로그인 불필요)."""
    import json
    from pathlib import Path

    path = WEB / "assets" / "templates" / "manifest.json"
    if not path.exists():
        return {"templates": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"templates": data}
    except Exception:
        return {"templates": []}


@app.post("/api/auth/register")
def register(body: AuthBody):
    ok, msg = db.register_user(body.email, body.password, body.name)
    if not ok:
        raise HTTPException(400, msg)
    return {"ok": True, "message": msg}


def _issue_session(user: dict, message: str) -> dict:
    user = admin_ops.enrich_user_flags(user) or user
    token = secrets.token_urlsafe(32)
    _sessions[token] = user
    _persist_sessions()
    used = db.get_usage(user["email"])
    limit = FREE_MONTHLY_LIMIT
    unlimited = (
        user.get("plan") == "pro"
        or user.get("is_admin")
        or user.get("is_vip")
    )
    return {
        "ok": True,
        "token": token,
        "user": user,
        "usage": used,
        "limit": limit,
        "unlimited": unlimited,
        "message": message,
    }


def _shorten_korean_address(display_name: str, raw: dict | None = None) -> str:
    """
    긴 Nominatim 주소를 일지용 짧은 표기로 축약.
    우선: 건물/시설명 + 동(洞) 단위.
    예) 한일유앤아이아파트, 후평2동
    """
    import re

    raw = raw or {}
    # 1) 구조화 필드 우선
    place_keys = (
        "building",
        "amenity",
        "tourism",
        "leisure",
        "shop",
        "office",
        "highway",  # 최후
        "road",
    )
    dong_keys = (
        "suburb",
        "neighbourhood",
        "neighborhood",
        "quarter",
        "city_district",
        "borough",
        "hamlet",
        "village",
    )
    place = ""
    for k in place_keys:
        v = (raw.get(k) or "").strip()
        if not v:
            continue
        # 도로명만 있는 경우 제외 (로/길 등) — 아래 문자열 파서로 넘김
        if k in ("highway", "road") and re.search(r"(로|길|대로|거리)$", v):
            continue
        place = v
        break
    dong = ""
    for k in dong_keys:
        v = (raw.get(k) or "").strip()
        if v and re.search(r"(동|가|리|읍|면)$", v):
            dong = v
            break
    if not dong:
        for k in dong_keys:
            v = (raw.get(k) or "").strip()
            if v:
                dong = v
                break

    if place and dong and place != dong:
        return f"{place}, {dong}"
    if place:
        return place
    if dong:
        return dong

    # 2) display_name 파싱 폴백
    text = (display_name or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in re.split(r"[,/|]", text) if p.strip()]
    if not parts:
        return text

    drop_exact = {
        "대한민국",
        "한국",
        "korea",
        "south korea",
        "republic of korea",
    }
    drop_re = re.compile(
        r"("
        r"특별자치도|광역시|특별시|자치시|"
        r"도$|시$|군$|"  # 광역/기초 행정구역
        r"^\d{4,6}$|"  # 우편번호
        r"^[A-Za-z\s]+$"  # 영문 국가명 등
        r")"
    )
    road_re = re.compile(r"(로|길|대로|거리|로\d*번길)$")
    dong_re = re.compile(r"(동|가|리|읍|면)$")
    building_hint = re.compile(
        r"(아파트|APT|빌라|타워|오피스텔|센터|빌딩|병원|학교|마트|역|터미널|공원|시장|교회|성당|사찰)"
    )

    kept: list[str] = []
    dongs: list[str] = []
    buildings: list[str] = []
    for p in parts:
        pl = p.lower()
        if pl in drop_exact:
            continue
        if re.fullmatch(r"\d{4,6}", p):
            continue
        if drop_re.search(p) and not dong_re.search(p) and not building_hint.search(p):
            # '춘천시', '강원특별자치도' 등 제거 (동 단위는 유지)
            if re.search(r"(시|군|도|특별|광역)$", p) and not dong_re.search(p):
                continue
        if road_re.search(p) and not building_hint.search(p):
            continue  # 후만로 등 도로명 제외
        if dong_re.search(p):
            dongs.append(p)
        elif building_hint.search(p) or len(p) >= 3:
            buildings.append(p)
        else:
            kept.append(p)

    short_parts: list[str] = []
    if buildings:
        short_parts.append(buildings[0])
    if dongs:
        short_parts.append(dongs[0])
    if not short_parts and kept:
        short_parts = kept[:2]
    if not short_parts and parts:
        # 최후: 앞쪽 의미 있는 1~2토큰 (국가/우편 제외 후)
        filtered = [
            p
            for p in parts
            if p.lower() not in drop_exact and not re.fullmatch(r"\d{4,6}", p)
        ]
        short_parts = filtered[:2] if filtered else parts[:1]
    return ", ".join(short_parts)


@app.get("/api/geo/reverse")
def geo_reverse(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    """GPS 좌표 → 주소 문자열 (OpenStreetMap Nominatim). short_address 포함."""
    try:
        with httpx.Client(timeout=12.0) as client:
            res = client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "jsonv2",
                    "accept-language": "ko",
                    "zoom": 18,
                    "addressdetails": 1,
                },
                headers={
                    "User-Agent": "RoadLog/1.0 (CoreLabs; corelabs.studio@gmail.com)",
                    "Accept": "application/json",
                },
            )
        if res.status_code != 200:
            raise HTTPException(502, "주소 변환 서비스에 일시적으로 연결할 수 없습니다.")
        data = res.json()
        raw = data.get("address") or {}
        address = (data.get("display_name") or "").strip()
        if not address:
            address = f"{lat:.5f}, {lon:.5f}"
        short = _shorten_korean_address(address, raw if isinstance(raw, dict) else {})
        if not short:
            short = address
        return {
            "ok": True,
            "lat": lat,
            "lon": lon,
            "address": short,  # 일지·리스트 기본값 = 짧은 주소
            "address_full": address,
            "short_address": short,
            "raw": raw if isinstance(raw, dict) else {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"주소 변환 실패: {e}") from e


@app.post("/api/auth/login")
def login(body: AuthBody):
    """일반 로그인. 관리자 ID/PW면 자동으로 관리자(Pro) 세션."""
    ok, user, msg = db.authenticate(body.email, body.password)
    if not ok or not user:
        raise HTTPException(401, msg)
    return _issue_session(user, msg)


@app.get("/api/me")
def me(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    used = db.get_usage(user["email"])
    settings = db.load_settings(user["email"])
    unlimited = (
        user.get("plan") == "pro"
        or user.get("is_admin")
        or user.get("is_vip")
    )
    return {
        "user": user,
        "usage": used,
        "limit": FREE_MONTHLY_LIMIT,
        "settings": settings,
        "unlimited": unlimited,
        "remain": None
        if unlimited
        else max(0, FREE_MONTHLY_LIMIT - used),
    }


@app.get("/api/settings")
def get_settings(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return {"settings": db.load_settings(user["email"])}


@app.put("/api/settings")
def put_settings(body: SettingsBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    ok = db.save_settings(user["email"], body.settings)
    if not ok:
        raise HTTPException(500, "설정 저장 실패")
    return {"ok": True, "settings": db.load_settings(user["email"])}


@app.post("/api/generate")
def generate(body: GenerateBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    plan = user.get("plan") or "free"
    used = db.get_usage(user["email"])
    unlimited = plan == "pro" or user.get("is_admin") or user.get("is_vip")

    if not unlimited and used >= FREE_MONTHLY_LIMIT:
        raise HTTPException(
            403,
            f"이번 달 Free 한도({FREE_MONTHLY_LIMIT}회)를 모두 사용했습니다. Pro로 업그레이드해 주세요.",
        )

    settings = body.settings or db.load_settings(user["email"])
    form = body.form or {
        "vehicle_number": body.vehicle_number,
        "odometer_start": body.odometer_start,
        "odometer_end": body.odometer_end,
        "lunch_restaurant": body.lunch_restaurant,
        "morning_places": body.morning_places,
        "afternoon_places": body.afternoon_places,
        "extra_note": body.raw_text,
    }
    result = generate_driving_log(
        body.raw_text or "",
        settings,
        form=form,
        user_email=user["email"],
    )

    if result.get("log") and result.get("log", {}).get("trips"):
        used = db.increment_usage(user["email"], 1)

    return {
        **result,
        "usage": used,
        "limit": FREE_MONTHLY_LIMIT,
        "plan": plan,
    }


@app.post("/api/validate")
def validate(body: ExportBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    settings = db.load_settings(user["email"])
    v = validate_log(body.log, settings)
    return {
        "ok": v["ok"],
        "log": v["enriched_log"],
        "errors": v["errors"],
        "warnings": v["warnings"],
    }


@app.post("/api/export")
def export(body: ExportBody, authorization: str | None = Header(default=None)):
    _token_user(authorization)
    fmt = (body.format or "").lower().strip()
    try:
        if fmt == "excel":
            data, name = export_excel(body.log)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif fmt == "pdf":
            data, name = export_pdf(body.log)
            media = "application/pdf"
        elif fmt == "docx":
            data, name = export_docx(body.log)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            raise HTTPException(400, "format은 excel | pdf | docx 중 하나여야 합니다.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"문서 생성 오류: {e}") from e

    # 한글 파일명은 latin-1 HTTP 헤더에 못 들어가 Content-Disposition 500 유발
    # → ASCII fallback + RFC 5987 filename* (UTF-8)
    safe_ascii = re.sub(r"[^\w.\-]+", "_", name, flags=re.ASCII).strip("._") or "roadlog.bin"
    if not re.search(r"\.\w+$", safe_ascii):
        # 확장자 보존
        ext = Path(name).suffix or ""
        safe_ascii = f"roadlog{ext}" if ext else "roadlog.bin"
    cd = f"attachment; filename=\"{safe_ascii}\"; filename*=UTF-8''{quote(name)}"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": cd},
    )


# ── 서식·말투 학습 ─────────────────────────────────────


@app.get("/api/style")
def style_status(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    return style_learn.list_style_status(user["email"])


@app.post("/api/style/upload")
async def style_upload(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    user = _token_user(authorization)
    data = await file.read()
    try:
        return style_learn.add_sample_from_upload(
            user["email"],
            file.filename or "upload.bin",
            data,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, f"업로드 처리 오류: {e}") from e


@app.post("/api/style/paste")
def style_paste(body: StyleTextBody, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        return style_learn.add_sample_from_text(user["email"], body.title, body.text)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/style/learn")
def style_learn_now(authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        result = style_learn.learn_style(user["email"])
        status = style_learn.list_style_status(user["email"])
        status["learn"] = result
        return status
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/style/samples/{sample_id}")
def style_delete(sample_id: str, authorization: str | None = Header(default=None)):
    user = _token_user(authorization)
    try:
        return style_learn.delete_sample(user["email"], sample_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/style/samples/{sample_id}/activate")
def style_activate(sample_id: str, authorization: str | None = Header(default=None)):
    """주 사용 회사 서식으로 지정."""
    user = _token_user(authorization)
    try:
        return style_learn.set_active_sample(user["email"], sample_id)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ── 관리자 운영 ───────────────────────────────────────


class BillingBody(BaseModel):
    pro_price_krw: int
    enterprise_price_krw: int


class VipBody(BaseModel):
    id: str
    email: str = ""
    note: str = ""


@app.get("/api/admin/dashboard")
def admin_dashboard(
    authorization: str | None = Header(default=None),
    date_from: str | None = None,
    date_to: str | None = None,
):
    """매출 대시보드. date_from / date_to = YYYY-MM-DD (기간 합산·날짜별)."""
    _require_admin(authorization)
    return admin_ops.revenue_dashboard(date_from=date_from, date_to=date_to)


@app.put("/api/admin/billing")
def admin_billing(body: BillingBody, authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    try:
        cfg = admin_ops.save_billing_config(
            body.pro_price_krw,
            body.enterprise_price_krw,
            updated_by=admin.get("email") or "",
        )
        return {"ok": True, "billing": cfg}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/admin/vip")
def admin_vip_list(authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    return {"vip_members": admin_ops.load_vip_members()}


@app.post("/api/admin/vip")
def admin_vip_add(body: VipBody, authorization: str | None = Header(default=None)):
    admin = _require_admin(authorization)
    try:
        row = admin_ops.add_vip(
            body.id,
            email=body.email,
            note=body.note,
            added_by=admin.get("email") or "",
        )
        return {"ok": True, "member": row, "vip_members": admin_ops.load_vip_members()}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/admin/vip/{member_id}")
def admin_vip_remove(member_id: str, authorization: str | None = Header(default=None)):
    _require_admin(authorization)
    ok = admin_ops.remove_vip(member_id)
    if not ok:
        raise HTTPException(404, "VIP 회원을 찾을 수 없습니다.")
    return {"ok": True, "vip_members": admin_ops.load_vip_members()}


# ── 정적 파일 ─────────────────────────────────────────

if WEB.exists():
    app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/{path:path}")
def spa_fallback(path: str):
    # API는 위에서 처리. 나머지 정적 파일 or index
    candidate = WEB / path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(WEB / "index.html")
