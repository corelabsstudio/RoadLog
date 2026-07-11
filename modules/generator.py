"""
OpenAI few-shot 기반 격식 있는 운행일지 생성
구조화 입력(주행거리·점심·오전/오후 장소) → AI가 시간·구간·문체 자동 작성
API 키 없을 때 규칙 기반 폴백 생성기 제공
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from modules.config import (
    FEW_SHOT_EXAMPLES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    is_free_cost_mode,
    llm_configured,
    resolve_llm_config,
)
from modules.validator import validate_log


SYSTEM_PROMPT = """당신은 대한민국 기업의 공식 업무용 '차량 운행일지'를 작성하는 전문 비서입니다.
특히 각 사용자가 과거에 제출한 일지 샘플의 말투·서식을 학습해, 그 사용자가 직접 쓴 것처럼 작성합니다.

규칙:
1. 반드시 JSON만 출력합니다. 설명·마크다운·코드펜스 금지.
2. 문체: 기본은 업무용 격식체. 단, [이 사용자 전용 서식·말투 프로필]이 있으면 그 규칙을 최우선으로 따릅니다.
3. 시간은 24시간제 HH:MM. 사용자가 시간을 안 주면 합리적으로 배분합니다.
4. 거리는 km 단위 숫자(소수 1자리 가능).
5. 최초/종료 누적 주행거리가 있으면:
   - odometer_start, odometer_end 를 그대로 반영
   - total_distance_km = 종료 - 최초 (반올림 1자리)
   - 각 trip distance_km 합이 total_distance_km 과 맞도록 배분
6. 오전 방문지 → (선택) 중식 구간 → 오후 방문지 순으로 운행 구간(trips)을 구성합니다.
7. 보통 출발/복귀 기점은 본사(또는 설정 회사/자주 가는 곳 첫 항목)입니다.
8. 점심 시간대 제외는 설정으로 처리합니다. 식당명·점심 위치는 사생활이므로,
   [점심 장소 비노출] 지시가 있거나 사용자가 점심 식당을 주지 않으면
   lunch_place는 빈 문자열로 두고, 식당 방문 구간(중식 목적 trip)을 만들지 마세요.
9. 사용자가 명시하지 않은 시각·세부 목적은 업무용으로 자연스럽게 추론하되 과장하지 않습니다.
10. 회사 제출용으로 신뢰 가능한 수준을 유지합니다.
11. purpose, memo, summary 표현은 프로필의 어휘·호흡을 모방하세요. 일반적인 AI 문장투를 피하세요.
12. summary에 식당명·점심 위치를 적지 마세요 (중식 시간 제외 언급만 가능).

JSON 스키마:
{
  "date": "YYYY-MM-DD",
  "vehicle": "차량번호",
  "driver_name": "운전자",
  "company_name": "회사명",
  "odometer_start": 0.0,
  "odometer_end": 0.0,
  "trips": [
    {
      "depart_time": "HH:MM",
      "arrive_time": "HH:MM",
      "from": "출발지",
      "to": "도착지",
      "purpose": "운행 목적",
      "distance_km": 0.0,
      "memo": "비고"
    }
  ],
  "total_distance_km": 0.0,
  "summary": "금일 운행 요약 (한 문장)",
  "lunch_place": "",
  "fuel_refueled": false,
  "fuel_amount_krw": null,
  "fuel_liters": null
}
"""

_LUNCH_PURPOSE_RE = re.compile(r"중식|점심|식사|런치|lunch", re.IGNORECASE)
_LUNCH_SUMMARY_RE = re.compile(
    r"(?:중식|점심|식사)\s*[\(（][^)）]{0,40}[\)）]|"
    r"(?:중식|점심)\s*[:：]?\s*[가-힣A-Za-z0-9\s]{1,20}",
    re.IGNORECASE,
)


def scrub_fuel_if_disallowed(log: dict | None, *, allow_fuel: bool) -> dict:
    """회사 서식에 주유 칸이 없으면 주유 관련 필드를 제거."""
    if not isinstance(log, dict):
        return {}
    out = dict(log)
    if allow_fuel:
        return out
    out["fuel_refueled"] = False
    out["fuel_amount_krw"] = None
    out["fuel_liters"] = None
    # 요약에 주유 언급이 끼면 가볍게 정리
    summary = str(out.get("summary") or "")
    if summary and re.search(r"주유|유류|연료|급유", summary):
        cleaned = re.sub(r"[^.]*?(주유|유류|연료|급유)[^.]*\.?", "", summary)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ·,;/")
        out["summary"] = cleaned
    return out


def omit_lunch_place_enabled(settings: dict | None) -> bool:
    """기본 True — 점심 장소를 일지/제출물에 넣지 않음."""
    if not settings:
        return True
    if "omit_lunch_place" in settings:
        return bool(settings.get("omit_lunch_place"))
    # 구 설정 호환: include_lunch_place 가 명시 True 일 때만 기록
    if settings.get("include_lunch_place") is True:
        return False
    return True


def scrub_lunch_place_privacy(log: dict | None, settings: dict | None = None) -> dict:
    """
    제출용 일지에서 점심 장소(식당·위치)와 중식 전용 구간을 제거.
    점심 '시간' 제외(검증)와 별개 — 사생활 위치만 숨김.
    """
    if not isinstance(log, dict):
        return {}
    out = dict(log)
    if not omit_lunch_place_enabled(settings):
        return out

    out["lunch_place"] = ""
    trips_in = out.get("trips") or []
    trips_out: list[dict] = []
    removed_dist = 0.0
    for t in trips_in:
        if not isinstance(t, dict):
            continue
        purpose = str(t.get("purpose") or "")
        memo = str(t.get("memo") or "")
        if _LUNCH_PURPOSE_RE.search(purpose) or _LUNCH_PURPOSE_RE.search(memo):
            try:
                removed_dist += float(t.get("distance_km") or 0)
            except (TypeError, ValueError):
                pass
            continue
        trips_out.append(dict(t))
    out["trips"] = trips_out

    # summary 에서 중식(○○) 등 위치 힌트 제거
    summary = str(out.get("summary") or "")
    if summary:
        cleaned = _LUNCH_SUMMARY_RE.sub("", summary)
        cleaned = re.sub(r"\s*및\s*(?=후\b)", " ", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ·,;/")
        out["summary"] = cleaned

    # 거리 재합산 (누적 입력이 없을 때만)
    if trips_out and not (
        out.get("odometer_start") not in (None, "")
        and out.get("odometer_end") not in (None, "")
    ):
        try:
            total = round(sum(float(t.get("distance_km") or 0) for t in trips_out), 1)
            out["total_distance_km"] = total
        except (TypeError, ValueError):
            pass
    elif removed_dist and out.get("total_distance_km") is not None:
        try:
            out["total_distance_km"] = round(
                max(0.0, float(out.get("total_distance_km") or 0) - removed_dist), 1
            )
        except (TypeError, ValueError):
            pass
    return out


def _parse_places(text: str) -> list[str]:
    """쉼표/줄바꿈/·/및 으로 구분된 장소 목록."""
    if not text or not str(text).strip():
        return []
    parts = re.split(r"[\n,，、/·]| 및 | 그리고 |→|->", str(text))
    return [p.strip() for p in parts if p and p.strip()]


def normalize_form(form: dict | None) -> dict[str, Any]:
    """프론트/API 구조화 입력을 정규화."""
    form = form or {}
    try:
        odo_s = float(form.get("odometer_start") if form.get("odometer_start") not in (None, "") else 0)
    except (TypeError, ValueError):
        odo_s = 0.0
    try:
        odo_e = float(form.get("odometer_end") if form.get("odometer_end") not in (None, "") else 0)
    except (TypeError, ValueError):
        odo_e = 0.0

    morning = form.get("morning_places") or form.get("morning") or ""
    afternoon = form.get("afternoon_places") or form.get("afternoon") or ""
    lunch = (form.get("lunch_restaurant") or form.get("lunch_place") or "").strip()

    if isinstance(morning, list):
        morning_list = [str(x).strip() for x in morning if str(x).strip()]
    else:
        morning_list = _parse_places(str(morning))

    if isinstance(afternoon, list):
        afternoon_list = [str(x).strip() for x in afternoon if str(x).strip()]
    else:
        afternoon_list = _parse_places(str(afternoon))

    vehicle = (
        form.get("vehicle_number")
        or form.get("vehicle")
        or ""
    )
    if isinstance(vehicle, str):
        vehicle = vehicle.strip()
    else:
        vehicle = str(vehicle or "").strip()

    # 주유
    refueled_raw = form.get("fuel_refueled")
    if isinstance(refueled_raw, str):
        fuel_refueled = refueled_raw.strip().lower() in ("1", "true", "yes", "y", "네", "예")
    else:
        fuel_refueled = bool(refueled_raw)
    try:
        fuel_amount = form.get("fuel_amount_krw")
        if fuel_amount in (None, ""):
            fuel_amount_krw = None
        else:
            fuel_amount_krw = float(fuel_amount)
            if fuel_amount_krw < 0:
                fuel_amount_krw = None
    except (TypeError, ValueError):
        fuel_amount_krw = None
    try:
        fuel_l = form.get("fuel_liters")
        if fuel_l in (None, ""):
            fuel_liters = None
        else:
            fuel_liters = float(fuel_l)
            if fuel_liters < 0:
                fuel_liters = None
    except (TypeError, ValueError):
        fuel_liters = None
    if not fuel_refueled:
        fuel_amount_krw = None
        fuel_liters = None

    return {
        "odometer_start": odo_s,
        "odometer_end": odo_e,
        "lunch_restaurant": lunch,
        "morning_places": morning_list,
        "afternoon_places": afternoon_list,
        "vehicle_number": vehicle,
        "extra_note": (form.get("extra_note") or form.get("note") or "").strip(),
        "fuel_refueled": fuel_refueled,
        "fuel_amount_krw": fuel_amount_krw,
        "fuel_liters": fuel_liters,
    }


def form_to_raw_text(form: dict, settings: dict | None = None) -> str:
    """구조화 입력 → 프롬프트용 자연어 블록."""
    f = normalize_form(form)
    morning = ", ".join(f["morning_places"]) or "(없음)"
    afternoon = ", ".join(f["afternoon_places"]) or "(없음)"
    hide_lunch = omit_lunch_place_enabled(settings)
    lunch = f["lunch_restaurant"] or "(미기재)"
    vehicle = f.get("vehicle_number") or "(미기재)"
    dist = max(0.0, f["odometer_end"] - f["odometer_start"])
    note = f["extra_note"]

    lines = [
        "[구조화 운행 입력]",
        f"- 차량번호: {vehicle}",
        f"- 최초 누적 주행거리: {f['odometer_start']} km",
        f"- 운행 종료 주행거리: {f['odometer_end']} km",
        f"- 금일 주행거리(종료-최초): {round(dist, 1)} km",
    ]
    if hide_lunch:
        lines.append("- [점심 장소 비노출] 식당명·점심 위치를 일지에 쓰지 말 것. lunch_place=\"\". 중식 목적 trip 생성 금지.")
        lines.append(
            f"- 점심 시간대(참고·시간 제외용): {settings.get('lunch_start', '12:00') if settings else '12:00'}"
            f" ~ {settings.get('lunch_end', '13:00') if settings else '13:00'} (장소 비공개)"
        )
    else:
        lines.append(f"- 점심 식당: {lunch}")
    lines.extend(
        [
            f"- 오전 방문지: {morning}",
            f"- 오후 방문지: {afternoon}",
        ]
    )
    # 서식에 주유 칸이 있을 때만 프롬프트에 주유 정보 포함
    if f.get("_allow_fuel"):
        if f.get("fuel_refueled"):
            amt = f.get("fuel_amount_krw")
            liters = f.get("fuel_liters")
            fuel_bits = ["오늘 주유함"]
            if amt is not None:
                try:
                    fuel_bits.append(
                        f"금액 {int(amt):,}원"
                        if float(amt) == int(float(amt))
                        else f"금액 {amt}원"
                    )
                except (TypeError, ValueError):
                    fuel_bits.append(f"금액 {amt}원")
            if liters is not None:
                fuel_bits.append(f"주유량 {liters}L")
            lines.append("- 주유: " + ", ".join(fuel_bits) + " (서식에 주유 칸 있음 — JSON fuel_* 반영)")
        else:
            lines.append("- 주유: 안 함 (서식에 주유 칸 있음 — fuel_refueled=false)")
    else:
        lines.append(
            "- [주유 칸 없음] 회사 서식에 주유 항목이 없습니다. "
            "fuel_refueled/fuel_amount_krw/fuel_liters 를 null/false 로 두고 "
            "요약·구간에 주유 내용을 쓰지 마세요."
        )
    if note:
        lines.append(f"- 추가 메모: {note}")
    lines.append("")
    lines.append(
        "위 정보를 바탕으로 시간·구간·목적을 채운 공식 운행일지 JSON을 작성하세요. "
        "누적 주행거리와 총 거리는 반드시 입력값을 따르세요. "
        "주유 여부와 금액이 있으면 JSON에 fuel_refueled, fuel_amount_krw, fuel_liters 필드로 반영하세요."
    )
    return "\n".join(lines)


def _build_user_prompt(
    raw_text: str,
    settings: dict,
    form: dict | None = None,
    style_block: str = "",
) -> str:
    places = settings.get("frequent_places") or []
    places_str = ", ".join(
        f"{p.get('name')}" + (f"({p.get('address')})" if p.get("address") else "")
        for p in places
        if p.get("name")
    ) or "(없음)"

    few = FEW_SHOT_EXAMPLES[0] if FEW_SHOT_EXAMPLES else None
    few_block = ""
    if few and not style_block.strip():
        # 사용자 스타일이 없을 때만 기본 few-shot 사용
        few_block = (
            "\n[Few-shot 예시]\n"
            f"입력: {few['input']}\n"
            f"출력: {json.dumps(few['output'], ensure_ascii=False)}\n"
        )

    form_block = ""
    if form:
        form_block = "\n" + form_to_raw_text(form) + "\n"

    return f"""{style_block}
{few_block}
[사용자 설정]
- 오늘 날짜: {date.today().isoformat()}
- 차량번호: {settings.get('vehicle_number') or '(미설정)'}
- 운전자: {settings.get('driver_name') or '(미설정)'}
- 회사: {settings.get('company_name') or '(미설정)'}
- 점심시간: {settings.get('lunch_start', '12:00')} ~ {settings.get('lunch_end', '13:00')} (제외={settings.get('exclude_lunch', True)})
- 기본 목적: {settings.get('default_purpose', '업무 출장')}
- 자주 가는 곳: {places_str}
{form_block}
[추가 자유 입력]
{raw_text or '(없음)'}

위 내용을 공식 운행일지 JSON으로 변환하세요.
회사 서식 프로필이 있으면:
- 해당 회사 양식의 항목·표현 습관에 맞출 것
- purpose/memo/summary 를 그 말투로 쓸 것
- 컬럼에 대응하는 필드를 trips/meta에 충실히 채울 것
"""


def _extract_json(text: str) -> dict:
    """모델 응답에서 JSON 객체 추출."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise


def _make_llm_client(cfg: dict[str, str] | None = None):
    """OpenAI SDK 클라이언트 (공식 OpenAI 또는 xAI 등 호환 엔드포인트)."""
    from openai import OpenAI

    cfg = cfg or resolve_llm_config()
    key = cfg.get("api_key") or ""
    if not key:
        raise RuntimeError("LLM API key not configured")
    kwargs: dict[str, Any] = {"api_key": key}
    base = (cfg.get("base_url") or "").strip()
    if base:
        kwargs["base_url"] = base
    return OpenAI(**kwargs), cfg


def generate_with_openai(
    raw_text: str,
    settings: dict,
    form: dict | None = None,
    style_block: str = "",
) -> dict[str, Any]:
    """LLM Chat Completions 호출 (OpenAI / xAI 호환)."""
    client, cfg = _make_llm_client()
    model = cfg.get("model") or OPENAI_MODEL or "gpt-4o-mini"
    # 스타일 학습 시 창의성 약간 낮춤 (일관성)
    temp = 0.25 if style_block.strip() else 0.3
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temp,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(raw_text, settings, form, style_block),
            },
        ],
    }
    # xAI 등 일부 엔드포인트는 response_format 미지원일 수 있음
    if (cfg.get("provider") or "") in ("openai", "openai_compatible", ""):
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception:
        # response_format 미지원 시 재시도
        kwargs.pop("response_format", None)
        resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or "{}"
    return _extract_json(content)


def classify_openai_failure(exc: BaseException | None = None, *, no_key: bool = False) -> dict[str, str]:
    """
    OpenAI 미사용/실패 사유를 사용자용 안내로 변환.
    returns: { code, title, detail, user_message }
    """
    if no_key:
        if is_free_cost_mode():
            return {
                "code": "free_mode",
                "title": "무료 모드 · 스마트 초안",
                "detail": "COST_MODE=free — 외부 AI API를 호출하지 않습니다.",
                "user_message": (
                    "**무료 모드**로 **스마트 초안**을 작성했습니다. "
                    "OpenAI 등 유료 API 비용이 발생하지 않습니다. "
                    "제출 전 시간·구간·목적을 한 번 확인해 주세요."
                ),
            }
        return {
            "code": "no_api_key",
            "title": "AI 미연결",
            "detail": "서버에 OpenAI API 키가 설정되지 않았습니다.",
            "user_message": (
                "AI 키가 연결되지 않아 **규칙 기반 초안**으로 작성했습니다. "
                "내용은 사용할 수 있지만, 문체·시간 배분은 직접 한 번 확인해 주세요. "
                "관리자에게 OpenAI API 키 설정을 요청하면 AI 생성으로 전환됩니다."
            ),
        }

    text = f"{type(exc).__name__ if exc else ''}: {exc or ''}".lower()
    raw = str(exc or "")

    # 1) 할당량/결제 (429 + insufficient_quota 포함)
    if any(
        k in text
        for k in (
            "insufficient_quota",
            "exceeded your current quota",
            "billing hard limit",
            "quota_exceeded",
        )
    ) or ("quota" in text and "rate_limit_error" not in text and "rate limit" not in text):
        return {
            "code": "quota_exceeded",
            "title": "AI 사용량 한도 초과",
            "detail": "OpenAI 계정 크레딧·결제 한도가 소진되었습니다.",
            "user_message": (
                "AI 사용량(할당량)이 초과되어 **규칙 기반 초안**으로 작성했습니다. "
                "일지는 다운로드·제출용으로 쓸 수 있으니 구간·시간을 확인해 주세요. "
                "고품질 AI 생성을 쓰려면 OpenAI 결제/크레딧을 충전해야 합니다."
            ),
        }

    # 2) 속도 제한
    if any(k in text for k in ("rate_limit", "rate limit", "too many requests")) or (
        "429" in text and "quota" not in text
    ):
        return {
            "code": "rate_limit",
            "title": "AI 일시 혼잡",
            "detail": "요청이 많아 잠시 제한되었습니다.",
            "user_message": (
                "AI 서버가 잠시 바빠 **규칙 기반 초안**으로 작성했습니다. "
                "잠시 후 다시 생성하면 AI 품질로 받을 수 있습니다. "
                "지금 초안도 수정·다운로드 가능합니다."
            ),
        }

    # 3) 인증
    if any(
        k in text
        for k in (
            "invalid_api_key",
            "authentication",
            "unauthorized",
            "incorrect api key",
            "permission denied",
            "401",
        )
    ):
        return {
            "code": "auth_error",
            "title": "AI 키 오류",
            "detail": "API 키가 유효하지 않거나 권한이 없습니다.",
            "user_message": (
                "AI 키 인증에 실패해 **규칙 기반 초안**으로 작성했습니다. "
                "관리자에게 `.env`의 OPENAI_API_KEY 확인을 요청해 주세요. "
                "초안은 그대로 사용·수정할 수 있습니다."
            ),
        }

    # 4) 네트워크
    if any(k in text for k in ("timeout", "timed out", "connection", "network", "connecterror")):
        return {
            "code": "network_error",
            "title": "AI 연결 실패",
            "detail": "네트워크 또는 타임아웃 오류",
            "user_message": (
                "AI 서버에 연결하지 못해 **규칙 기반 초안**으로 작성했습니다. "
                "네트워크 상태를 확인한 뒤 다시 생성해 보세요. "
                "초안은 지금 바로 수정·다운로드할 수 있습니다."
            ),
        }

    # 5) 기타
    short = re.sub(r"sk-[a-zA-Z0-9\-_]+", "sk-***", raw)[:160]
    return {
        "code": "api_error",
        "title": "AI 일시 오류",
        "detail": short or "OpenAI API 오류",
        "user_message": (
            "AI 생성 중 오류가 나 **규칙 기반 초안**으로 작성했습니다. "
            "구간·시간·목적을 확인한 뒤 제출해 주세요. "
            "문제가 계속되면 잠시 후 다시 시도해 주세요."
        ),
    }


def generate_fallback(raw_text: str, settings: dict, form: dict | None = None) -> dict[str, Any]:
    """
    API 키 없을 때 규칙 기반 생성.
    구조화 입력이 있으면 오전→점심→오후 구간을 구성합니다.
    """
    f = normalize_form(form)
    origin = "본사"
    places = settings.get("frequent_places") or []
    if places and places[0].get("name"):
        origin = places[0]["name"]
    if settings.get("company_name"):
        # 회사명이 있으면 기점 표기에 병기하지 않고 본사 유지, 설정 회사는 메타에만
        pass

    vehicle = f.get("vehicle_number") or settings.get("vehicle_number") or ""
    purpose = settings.get("default_purpose", "업무 출장")
    lunch_start = settings.get("lunch_start", "12:00") or "12:00"
    lunch_end = settings.get("lunch_end", "13:00") or "13:00"

    odo_s = f["odometer_start"]
    odo_e = f["odometer_end"]
    total_dist = round(max(0.0, odo_e - odo_s), 1) if (odo_e or odo_s) else 0.0

    # 구조화 입력 없을 때 기존 텍스트 파싱
    if not f["morning_places"] and not f["afternoon_places"] and (raw_text or "").strip():
        text = raw_text.strip()
        times = re.findall(r"(\d{1,2})\s*[:시]\s*(\d{2})?", text)
        hhmm_list = []
        for h, m in times:
            mi = int(m) if m else 0
            hhmm_list.append(f"{int(h):02d}:{mi:02d}")
        if len(hhmm_list) >= 2:
            t0, t1 = hhmm_list[0], hhmm_list[1]
        elif len(hhmm_list) == 1:
            t0, t1 = hhmm_list[0], _add_minutes(hhmm_list[0], 50)
        else:
            t0, t1 = "09:00", "10:00"
        dest = "거래처"
        m = re.search(
            r"([가-힣A-Za-z0-9\s]+?)(?:에서|출발).*?([가-힣A-Za-z0-9\s]+?)(?:까지|로|에\s|도착|미팅)",
            text,
        )
        if m:
            origin = m.group(1).strip()[:30] or origin
            dest = m.group(2).strip()[:30] or dest
        dm = re.search(r"(\d+(?:\.\d+)?)\s*km", text, re.I)
        if dm and total_dist <= 0:
            total_dist = float(dm.group(1))
        trips = [
            {
                "depart_time": t0,
                "arrive_time": t1,
                "from": origin,
                "to": dest,
                "purpose": purpose,
                "distance_km": total_dist or 15.0,
                "memo": "",
            }
        ]
        return _pack_log(
            settings,
            f.get("vehicle_number") or vehicle,
            trips,
            total_dist or 15.0,
            odo_s,
            odo_e,
            f["lunch_restaurant"],
        )

    # 오전 / 점심 / 오후 구간 구성
    morning = f["morning_places"] or []
    afternoon = f["afternoon_places"] or []
    lunch = f["lunch_restaurant"]

    stops: list[tuple[str, str]] = []  # (place, purpose)
    for p in morning:
        stops.append((p, purpose))
    if lunch:
        stops.append((lunch, "중식"))
    for p in afternoon:
        stops.append((p, purpose if purpose else "업무 출장"))

    # 경로: 본사 → stops... → 본사
    path = [origin] + [s[0] for s in stops] + [origin]
    purposes = [s[1] for s in stops] + ["업무 복귀"]

    # 시간 배분
    n_legs = max(1, len(path) - 1)
    # 오전 출발 08:40, 점심 전 구간, 점심, 오후, 복귀
    times = _build_schedule(n_legs, lunch_start, lunch_end, has_lunch=bool(lunch))

    if total_dist <= 0:
        total_dist = round(8.0 * n_legs, 1)

    leg_base = round(total_dist / n_legs, 1)
    legs_dist = [leg_base] * n_legs
    # 합 맞추기
    diff = round(total_dist - sum(legs_dist), 1)
    legs_dist[-1] = round(legs_dist[-1] + diff, 1)

    trips = []
    for i in range(n_legs):
        dep, arr = times[i]
        trips.append(
            {
                "depart_time": dep,
                "arrive_time": arr,
                "from": path[i],
                "to": path[i + 1],
                "purpose": purposes[i] if i < len(purposes) else purpose,
                "distance_km": max(0.1, legs_dist[i]),
                # 제출용 문서에는 내부 엔진 안내 문구를 넣지 않음 (UI 경고만 사용)
                "memo": "",
            }
        )

    summary_parts = []
    if morning:
        summary_parts.append("오전 " + "·".join(morning) + " 방문")
    if lunch:
        summary_parts.append(f"중식({lunch})")
    if afternoon:
        summary_parts.append("오후 " + "·".join(afternoon) + " 방문")
    summary = ", ".join(summary_parts) if summary_parts else f"{origin} 기점 업무 운행"

    return _pack_log(settings, vehicle, trips, total_dist, odo_s, odo_e, lunch, summary)


def _build_schedule(
    n_legs: int, lunch_start: str, lunch_end: str, has_lunch: bool
) -> list[tuple[str, str]]:
    """구간 수에 맞춰 출발·도착 시각 목록 생성."""
    # 단순: 08:50부터 시작, 구간당 이동 35분, 체류 40분
    t = "08:50"
    result: list[tuple[str, str]] = []
    for i in range(n_legs):
        arr = _add_minutes(t, 35)
        # 점심 구간 근처면 점심 시간대 맞춤
        if has_lunch and i == max(0, n_legs // 2 - 1):
            # 점심 식당으로 가는 구간
            t = _add_minutes(lunch_start, -40) if i > 0 else t
            arr = lunch_start
        if has_lunch and i == n_legs // 2:
            t = lunch_end
            arr = _add_minutes(lunch_end, 35)
        result.append((t, arr))
        t = _add_minutes(arr, 40)  # 체류 후 다음 출발
    return result


def _pack_log(
    settings: dict,
    vehicle: str,
    trips: list,
    total_dist: float,
    odo_s: float,
    odo_e: float,
    lunch: str = "",
    summary: str = "",
) -> dict[str, Any]:
    if not summary and trips:
        summary = f"{trips[0].get('from')} 기점 업무 운행"
    return {
        "date": date.today().isoformat(),
        "vehicle": vehicle or settings.get("vehicle_number") or "",
        "driver_name": settings.get("driver_name", ""),
        "company_name": settings.get("company_name", ""),
        "odometer_start": odo_s if odo_s else None,
        "odometer_end": odo_e if odo_e else None,
        "lunch_place": lunch or "",
        "trips": trips,
        "total_distance_km": round(total_dist, 1),
        "summary": summary,
        # 내부 전용 — scrub_submission_log 에서 제거
        "_engine": "fallback",
    }


# 제출 문서에 절대 남기면 안 되는 내부 안내(전체 문장·부분 구절)
_INTERNAL_MEMO_FULL_RE = re.compile(
    r"규칙\s*기반\s*초안|"
    r"OpenAI\s*키|"
    r"고품질\s*생성|"
    r"API\s*키\s*설정|"
    r"user_style_fallback|"
    r"fallback\s*draft",
    re.IGNORECASE,
)
_INTERNAL_LOG_KEYS = (
    "_engine",
    "_openai_error",
    "_saved_id",
    "memo_style_note",
)


def scrub_submission_log(log: dict | None) -> dict:
    """
    회사 제출용 문서·저장본에서 내부 디버그/엔진 안내를 제거.
    사용자에게 보이는 warnings 는 API 응답 메타에만 남깁니다.
    """
    if not isinstance(log, dict):
        return {}
    out = dict(log)
    for k in _INTERNAL_LOG_KEYS:
        out.pop(k, None)

    def _clean_text(val: object) -> str:
        s = str(val or "").strip()
        if not s:
            return ""
        # 내부 엔진/키 관련 안내가 포함되면 제출 본문에서 통째로 제거
        if _INTERNAL_MEMO_FULL_RE.search(s):
            return ""
        return s

    trips = out.get("trips")
    if isinstance(trips, list):
        cleaned_trips = []
        for t in trips:
            if not isinstance(t, dict):
                continue
            tt = dict(t)
            tt["memo"] = _clean_text(tt.get("memo"))
            cleaned_trips.append(tt)
        out["trips"] = cleaned_trips

    visits = out.get("visits")
    if isinstance(visits, list):
        cleaned_visits = []
        for v in visits:
            if not isinstance(v, dict):
                continue
            vv = dict(v)
            vv["memo"] = _clean_text(vv.get("memo"))
            cleaned_visits.append(vv)
        out["visits"] = cleaned_visits

    out["summary"] = _clean_text(out.get("summary")) if out.get("summary") else out.get("summary", "")
    return out


def _add_minutes(hhmm: str, add: int) -> str:
    h, m = map(int, str(hhmm).split(":")[:2])
    total = h * 60 + m + add
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


def _apply_odometer(log: dict, form: dict | None) -> dict:
    """누적 주행거리·차량번호·주유 등 폼 입력 강제 반영."""
    f = normalize_form(form)
    if f["odometer_start"] or f["odometer_end"]:
        log["odometer_start"] = f["odometer_start"]
        log["odometer_end"] = f["odometer_end"]
        if f["odometer_end"] >= f["odometer_start"] and (f["odometer_end"] or f["odometer_start"]):
            dist = round(f["odometer_end"] - f["odometer_start"], 1)
            log["total_distance_km"] = dist
    # 작성 폼 차량번호가 있으면 설정값보다 우선
    if f.get("vehicle_number"):
        log["vehicle"] = f["vehicle_number"]
    # 주유 기록 (폼 값이 소스 오브 트루스)
    log["fuel_refueled"] = bool(f.get("fuel_refueled"))
    if f.get("fuel_refueled"):
        log["fuel_amount_krw"] = f.get("fuel_amount_krw")
        log["fuel_liters"] = f.get("fuel_liters")
    else:
        log["fuel_amount_krw"] = None
        log["fuel_liters"] = None
    return log


def generate_driving_log(
    raw_text: str = "",
    settings: dict | None = None,
    form: dict | None = None,
    user_email: str | None = None,
    report_type: str = "driving",
) -> dict[str, Any]:
    """
    메인 엔트리.
    report_type: driving(운행일지) | field(외근·출장 일지)
    form: odometer_start, odometer_end, lunch_restaurant, morning_places, afternoon_places
          또는 field: visits_text, work_summary, next_actions, department
    user_email: 있으면 해당 사용자 서식·말투 프로필을 적용
    """
    if str(report_type or "driving").lower().strip() in ("field", "field_visit", "outing", "외근"):
        return generate_field_visit_log(
            raw_text=raw_text,
            settings=settings,
            form=form,
            user_email=user_email,
        )

    settings = settings or {}
    f = normalize_form(form)
    # 사생활 보호: 기본으로 점심 장소 입력을 생성 파이프라인에서 제거
    if omit_lunch_place_enabled(settings):
        f = {**f, "lunch_restaurant": ""}

    # 회사 서식에 주유 칸이 없으면 주유 정보 전부 제외 (AI도 넣지 않음)
    allow_fuel = False
    if user_email:
        try:
            from modules.style_learn import profile_has_fuel_field

            allow_fuel = profile_has_fuel_field(user_email)
        except Exception:
            allow_fuel = False
    if not allow_fuel:
        f = {
            **f,
            "fuel_refueled": False,
            "fuel_amount_krw": None,
            "fuel_liters": None,
            "_allow_fuel": False,
        }
    else:
        f = {**f, "_allow_fuel": True}

    has_form = bool(
        f["morning_places"]
        or f["afternoon_places"]
        or f["lunch_restaurant"]
        or f["odometer_start"]
        or f["odometer_end"]
    )
    if not has_form and not (raw_text or "").strip():
        return {
            "success": False,
            "log": None,
            "errors": ["오전/오후 방문지 또는 주행거리를 입력해 주세요."],
            "warnings": [],
            "engine": None,
            "message": "입력 없음",
        }

    if has_form and f["odometer_end"] and f["odometer_start"] and f["odometer_end"] < f["odometer_start"]:
        return {
            "success": False,
            "log": None,
            "errors": ["운행 종료 주행거리는 최초 누적 주행거리보다 크거나 같아야 합니다."],
            "warnings": [],
            "engine": None,
            "message": "주행거리 오류",
        }

    # 사용자 스타일 블록
    style_block = ""
    style_applied = False
    if user_email:
        try:
            from modules.style_learn import build_style_prompt_block, load_profile

            style_block = build_style_prompt_block(user_email)
            prof = load_profile(user_email)
            style_applied = bool(prof.get("learned") and prof.get("samples"))
        except Exception:
            style_block = ""
            style_applied = False

    # 구조화 입력이 있으면 raw_text 보강
    prompt_text = raw_text or ""
    if has_form:
        prompt_text = form_to_raw_text(f, settings) + ("\n" + raw_text if raw_text else "")

    engine = "openai"
    engine_info: dict[str, str] | None = None
    openai_exc: BaseException | None = None
    # 무료 모드: 키가 있어도 LLM API를 호출하지 않음 (비용 0)
    has_key = llm_configured() and not is_free_cost_mode()

    try:
        if has_key:
            raw_log = generate_with_openai(prompt_text, settings, f, style_block)
            engine = "openai"
            try:
                eng = resolve_llm_config().get("provider") or "openai"
                if eng == "xai":
                    engine = "xai"
            except Exception:
                pass
        else:
            engine = "fallback"
            engine_info = classify_openai_failure(no_key=True)
            raw_log = generate_fallback(prompt_text, settings, f)
            raw_log = _apply_style_to_fallback(raw_log, user_email)
    except Exception as e:
        engine = "fallback"
        openai_exc = e
        engine_info = classify_openai_failure(e)
        raw_log = generate_fallback(prompt_text, settings, f)
        raw_log = _apply_style_to_fallback(raw_log, user_email)

    # 내부 디버그 필드는 응답 log 에 남기지 않음
    if isinstance(raw_log, dict):
        raw_log.pop("_openai_error", None)

    # 설정·주행거리 보강 (폼 차량번호는 _apply_odometer 에서 우선)
    if f.get("vehicle_number"):
        raw_log["vehicle"] = f["vehicle_number"]
    elif settings.get("vehicle_number") and not raw_log.get("vehicle"):
        raw_log["vehicle"] = settings["vehicle_number"]
    if settings.get("driver_name") and not raw_log.get("driver_name"):
        raw_log["driver_name"] = settings["driver_name"]
    else:
        raw_log.setdefault("driver_name", settings.get("driver_name", ""))
    if settings.get("company_name") and not raw_log.get("company_name"):
        raw_log["company_name"] = settings["company_name"]
    else:
        raw_log.setdefault("company_name", settings.get("company_name", ""))
    if not raw_log.get("date"):
        raw_log["date"] = date.today().isoformat()
    raw_log = _apply_odometer(raw_log, f)

    # 생성 직후·검증 전 점심 장소 스크럽 (AI가 식당을 지어내도 제거)
    raw_log = scrub_lunch_place_privacy(raw_log, settings)
    if not allow_fuel:
        raw_log = scrub_fuel_if_disallowed(raw_log, allow_fuel=False)
    raw_log = scrub_submission_log(raw_log)

    validated = validate_log(raw_log, settings)
    # odometer·차량번호 필드 유지
    if validated.get("enriched_log") is not None:
        validated["enriched_log"] = _apply_odometer(validated["enriched_log"], f)
        if f.get("vehicle_number"):
            validated["enriched_log"]["vehicle"] = f["vehicle_number"]
        if settings.get("driver_name") and not validated["enriched_log"].get("driver_name"):
            validated["enriched_log"]["driver_name"] = settings["driver_name"]
        if settings.get("company_name") and not validated["enriched_log"].get(
            "company_name"
        ):
            validated["enriched_log"]["company_name"] = settings["company_name"]
        validated["enriched_log"] = scrub_lunch_place_privacy(
            validated["enriched_log"], settings
        )
        if not allow_fuel:
            validated["enriched_log"] = scrub_fuel_if_disallowed(
                validated["enriched_log"], allow_fuel=False
            )
        # 제출용 본문에서 내부 키·엔진 안내 제거
        validated["enriched_log"] = scrub_submission_log(validated["enriched_log"])

    warnings = list(validated["warnings"] or [])
    if engine == "fallback" and engine_info:
        warnings.insert(0, engine_info["user_message"])
    if style_applied:
        warnings.insert(0 if engine != "fallback" else 1, "내 서식·말투 학습이 적용되었습니다.")
    elif user_email and not style_applied:
        warnings.append(
            "서식 학습 전이거나 샘플이 부족합니다. [내 서식 학습]에서 기존 일지 3~5장을 올려 주세요."
        )

    if engine == "openai":
        message = (
            "AI로 일지를 생성했습니다. 시간·구간을 한 번 확인해 주세요."
            if validated["ok"]
            else "검증 오류가 있습니다. 내용을 확인해 주세요."
        )
        engine_reason = "ok"
        engine_title = "AI 생성"
    else:
        info = engine_info or classify_openai_failure(openai_exc)
        engine_reason = info["code"]
        engine_title = info["title"]
        message = (
            info["user_message"]
            if validated["ok"]
            else f"{info['user_message']} 또한 검증 오류가 있으니 내용을 확인해 주세요."
        )

    return {
        "success": validated["ok"],
        "log": validated["enriched_log"],
        "errors": validated["errors"],
        "warnings": warnings,
        "engine": engine,
        "engine_reason": engine_reason,
        "engine_title": engine_title,
        "engine_detail": (engine_info or {}).get("detail", "") if engine == "fallback" else "",
        "style_applied": style_applied,
        "message": message,
    }


def _apply_style_to_fallback(log: dict, user_email: str | None) -> dict:
    """폴백 생성에도 학습된 목적/요약 습관을 가볍게 반영."""
    if not user_email:
        return log
    try:
        from modules.style_learn import load_profile

        prof = load_profile(user_email)
        phrases = prof.get("purpose_phrases") or []
        if phrases and log.get("trips"):
            for t in log["trips"]:
                if t.get("purpose") in ("업무 출장", "업무 복귀", "중식") and phrases:
                    # 중식/복귀는 유지, 일반 업무만 대체
                    if t.get("purpose") == "업무 출장" and phrases[0]:
                        t["purpose"] = phrases[0]
        if prof.get("summary_style") and log.get("summary") and not log["summary"].endswith("."):
            pass
        if prof.get("style_summary") and log.get("trips"):
            log.setdefault("memo_style_note", "user_style_fallback")
    except Exception:
        pass
    return log


# ── 외근·출장 일지 ───────────────────────────────────────

FIELD_SYSTEM_PROMPT = """당신은 대한민국 기업의 공식 업무용 '외근·출장 일지(방문 보고서)'를 작성하는 전문 비서입니다.
사용자가 남긴 방문 메모를 회사 제출용 격식 문서로 정리합니다.

규칙:
1. 반드시 JSON만 출력합니다. 설명·마크다운·코드펜스 금지.
2. 문체: 업무용 격식체. [이 사용자 전용 서식·말투 프로필]이 있으면 최우선.
3. 시간은 24시간제 HH:MM. 없으면 합리적으로 배분(오전 09:30~, 오후 14:00~ 등).
4. 과장·허위 성과 금지. 입력에 없는 계약 체결·매출 수치를 지어내지 마세요.
5. 방문이 여러 곳이면 visits 배열에 시간순으로 넣습니다.
6. purpose(목적)·result(결과)·next_action(후속)을 짧게 명확히 씁니다.

JSON 스키마:
{
  "report_type": "field",
  "date": "YYYY-MM-DD",
  "author_name": "작성자",
  "department": "부서",
  "company_name": "회사명",
  "driver_name": "작성자(호환)",
  "vehicle": "",
  "visits": [
    {
      "time": "HH:MM",
      "place": "방문처",
      "purpose": "방문 목적",
      "result": "진행 결과·논의 요지",
      "next_action": "후속 조치",
      "memo": "비고"
    }
  ],
  "summary": "금일 외근 요약 (한두 문장)",
  "trips": []
}
trips는 비워 두거나, 호환용으로 방문 구간을 넣어도 됩니다. 서버가 보정합니다.
"""


def normalize_field_form(form: dict | None) -> dict[str, Any]:
    """외근 일지 입력 정규화."""
    form = form or {}
    visits_raw = form.get("visits_text") or form.get("visits") or form.get("places") or ""
    if isinstance(visits_raw, list):
        # [{place, purpose, ...}] 또는 문자열 리스트
        lines = []
        for v in visits_raw:
            if isinstance(v, dict):
                place = str(v.get("place") or v.get("to") or "").strip()
                purpose = str(v.get("purpose") or "").strip()
                result = str(v.get("result") or "").strip()
                if place:
                    bit = place
                    if purpose:
                        bit += f" — {purpose}"
                    if result:
                        bit += f" / {result}"
                    lines.append(bit)
            else:
                s = str(v).strip()
                if s:
                    lines.append(s)
        visits_text = "\n".join(lines)
    else:
        visits_text = str(visits_raw or "").strip()

    return {
        "visits_text": visits_text,
        "work_summary": str(form.get("work_summary") or form.get("summary_note") or "").strip(),
        "next_actions": str(form.get("next_actions") or form.get("follow_up") or "").strip(),
        "department": str(form.get("department") or "").strip(),
        "extra_note": str(form.get("extra_note") or form.get("note") or form.get("raw_text") or "").strip(),
        "author_name": str(form.get("author_name") or form.get("driver_name") or "").strip(),
    }


def field_form_to_raw_text(form: dict) -> str:
    f = normalize_field_form(form)
    lines = [
        "[구조화 외근·출장 입력]",
        f"- 방문·업무 메모:\n{f['visits_text'] or '(없음)'}",
    ]
    if f["work_summary"]:
        lines.append(f"- 오늘 업무 한줄 요약: {f['work_summary']}")
    if f["next_actions"]:
        lines.append(f"- 후속 조치: {f['next_actions']}")
    if f["department"]:
        lines.append(f"- 부서: {f['department']}")
    if f["extra_note"]:
        lines.append(f"- 추가 메모: {f['extra_note']}")
    lines.append("")
    lines.append(
        "위 정보를 바탕으로 회사 제출용 외근·출장 일지 JSON을 작성하세요. "
        "방문처·목적·결과·후속을 빠짐없이 visits에 정리하세요."
    )
    return "\n".join(lines)


def _visits_to_trips(visits: list[dict], origin: str = "본사") -> list[dict]:
    """내보내기·기존 UI 호환용 trips 변환 (거리는 0)."""
    trips: list[dict] = []
    prev = origin
    for i, v in enumerate(visits):
        place = str(v.get("place") or "방문처").strip() or "방문처"
        t0 = str(v.get("time") or "").strip() or _add_minutes("09:30", i * 90)
        t1 = _add_minutes(t0, 50)
        memo_parts = []
        if v.get("result"):
            memo_parts.append(f"결과: {v['result']}")
        if v.get("next_action"):
            memo_parts.append(f"후속: {v['next_action']}")
        if v.get("memo"):
            memo_parts.append(str(v["memo"]))
        trips.append(
            {
                "depart_time": t0,
                "arrive_time": t1,
                "from": prev,
                "to": place,
                "purpose": str(v.get("purpose") or "업무 방문").strip(),
                "distance_km": 0,
                "memo": " / ".join(memo_parts),
                "result": v.get("result") or "",
                "next_action": v.get("next_action") or "",
            }
        )
        prev = place
    return trips


def _normalize_field_log(raw: dict, settings: dict, f: dict) -> dict[str, Any]:
    """AI/폴백 출력을 통일 스키마로 정리."""
    log = dict(raw or {})
    log["report_type"] = "field"
    if not log.get("date"):
        log["date"] = date.today().isoformat()

    author = (
        f.get("author_name")
        or log.get("author_name")
        or log.get("driver_name")
        or settings.get("driver_name")
        or ""
    )
    log["author_name"] = author
    log["driver_name"] = author
    log["department"] = f.get("department") or log.get("department") or ""
    log["company_name"] = log.get("company_name") or settings.get("company_name") or ""
    log["vehicle"] = log.get("vehicle") or ""
    log["odometer_start"] = None
    log["odometer_end"] = None
    log["lunch_place"] = log.get("lunch_place") or ""
    log["total_distance_km"] = log.get("total_distance_km") if log.get("total_distance_km") not in (None, "") else 0

    visits = log.get("visits")
    if not isinstance(visits, list):
        visits = []
    cleaned: list[dict] = []
    for v in visits:
        if not isinstance(v, dict):
            continue
        place = str(v.get("place") or v.get("to") or "").strip()
        if not place:
            continue
        cleaned.append(
            {
                "time": str(v.get("time") or v.get("depart_time") or "").strip(),
                "place": place,
                "purpose": str(v.get("purpose") or "업무 방문").strip(),
                "result": str(v.get("result") or "").strip(),
                "next_action": str(v.get("next_action") or "").strip(),
                "memo": str(v.get("memo") or "").strip(),
            }
        )

    # visits 없고 trips만 있으면 역변환
    if not cleaned and log.get("trips"):
        for t in log.get("trips") or []:
            if not isinstance(t, dict):
                continue
            place = str(t.get("to") or t.get("place") or "").strip()
            if not place:
                continue
            cleaned.append(
                {
                    "time": str(t.get("depart_time") or t.get("time") or "").strip(),
                    "place": place,
                    "purpose": str(t.get("purpose") or "업무 방문").strip(),
                    "result": str(t.get("result") or "").strip(),
                    "next_action": str(t.get("next_action") or "").strip(),
                    "memo": str(t.get("memo") or "").strip(),
                }
            )

    origin = "본사"
    places = settings.get("frequent_places") or []
    if places and places[0].get("name"):
        origin = places[0]["name"]

    log["visits"] = cleaned
    log["trips"] = _visits_to_trips(cleaned, origin=origin) if cleaned else []
    if not log.get("summary") and cleaned:
        places_s = "·".join(v["place"] for v in cleaned[:4])
        log["summary"] = f"{places_s} 등 외근 업무 수행"
    return log


def generate_field_fallback(settings: dict, form: dict | None = None) -> dict[str, Any]:
    """API 키 없을 때 규칙 기반 외근 일지."""
    f = normalize_field_form(form)
    settings = settings or {}
    lines = [ln.strip() for ln in re.split(r"[\n;；]", f["visits_text"]) if ln.strip()]
    if not lines and f["work_summary"]:
        lines = [f["work_summary"]]
    if not lines:
        lines = ["거래처 방문"]

    visits: list[dict] = []
    t0 = "09:30"
    for i, line in enumerate(lines):
        # "장소 — 목적 / 결과" 또는 "장소, 목적"
        place, purpose, result = line, "업무 방문", ""
        if "—" in line or " - " in line:
            parts = re.split(r"\s*[—\-]\s*", line, maxsplit=1)
            place = parts[0].strip()
            rest = parts[1].strip() if len(parts) > 1 else ""
            if "/" in rest:
                purpose, result = [x.strip() for x in rest.split("/", 1)]
            else:
                purpose = rest or purpose
        elif "," in line or "，" in line:
            parts = re.split(r"[,，]", line, maxsplit=1)
            place = parts[0].strip()
            purpose = parts[1].strip() if len(parts) > 1 else purpose
        next_act = ""
        if i == len(lines) - 1 and f["next_actions"]:
            next_act = f["next_actions"]
        visits.append(
            {
                "time": _add_minutes(t0, i * 100),
                "place": place[:80],
                "purpose": purpose[:80] or "업무 방문",
                "result": result[:200] or (f["work_summary"] if i == 0 and f["work_summary"] else "협의 진행"),
                "next_action": next_act[:120],
                "memo": "",
            }
        )

    summary = f["work_summary"] or (
        "·".join(v["place"] for v in visits[:3]) + " 외근 업무 수행"
    )
    raw = {
        "report_type": "field",
        "date": date.today().isoformat(),
        "author_name": f.get("author_name") or settings.get("driver_name") or "",
        "department": f.get("department") or "",
        "company_name": settings.get("company_name") or "",
        "visits": visits,
        "summary": summary,
        "_engine": "fallback",
    }
    return _normalize_field_log(raw, settings, f)


def _build_field_user_prompt(
    raw_text: str,
    settings: dict,
    form: dict | None = None,
    style_block: str = "",
) -> str:
    places = settings.get("frequent_places") or []
    places_str = ", ".join(
        f"{p.get('name')}" + (f"({p.get('address')})" if p.get("address") else "")
        for p in places
        if p.get("name")
    ) or "(없음)"
    form_block = field_form_to_raw_text(form or {}) if form else ""
    return f"""{style_block}

[사용자 설정]
- 오늘 날짜: {date.today().isoformat()}
- 작성자: {settings.get('driver_name') or '(미설정)'}
- 회사: {settings.get('company_name') or '(미설정)'}
- 기본 목적: {settings.get('default_purpose', '업무 출장')}
- 자주 가는 곳: {places_str}

{form_block}

[추가 자유 입력]
{raw_text or '(없음)'}

위 내용을 공식 외근·출장 일지 JSON으로 변환하세요.
"""


def generate_field_with_openai(
    raw_text: str,
    settings: dict,
    form: dict | None = None,
    style_block: str = "",
) -> dict[str, Any]:
    client, cfg = _make_llm_client()
    model = cfg.get("model") or OPENAI_MODEL or "gpt-4o-mini"
    temp = 0.25 if style_block.strip() else 0.3
    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temp,
        "messages": [
            {"role": "system", "content": FIELD_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_field_user_prompt(raw_text, settings, form, style_block),
            },
        ],
    }
    if (cfg.get("provider") or "") in ("openai", "openai_compatible", ""):
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception:
        kwargs.pop("response_format", None)
        resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content or "{}"
    return _extract_json(content)


def generate_field_visit_log(
    raw_text: str = "",
    settings: dict | None = None,
    form: dict | None = None,
    user_email: str | None = None,
) -> dict[str, Any]:
    """외근·출장 일지 생성 엔트리."""
    settings = settings or {}
    f = normalize_field_form(form)
    if raw_text and not f["extra_note"]:
        f["extra_note"] = raw_text.strip()

    has_input = bool(
        f["visits_text"] or f["work_summary"] or f["next_actions"] or f["extra_note"] or (raw_text or "").strip()
    )
    if not has_input:
        return {
            "success": False,
            "log": None,
            "errors": ["방문처·업무 내용 중 하나 이상 입력해 주세요."],
            "warnings": [],
            "engine": None,
            "message": "입력 없음",
        }

    style_block = ""
    style_applied = False
    if user_email:
        try:
            from modules.style_learn import build_style_prompt_block, load_profile

            style_block = build_style_prompt_block(user_email)
            prof = load_profile(user_email)
            style_applied = bool(prof.get("learned") and prof.get("samples"))
        except Exception:
            style_block = ""
            style_applied = False

    prompt_text = field_form_to_raw_text(f)
    if raw_text:
        prompt_text += "\n" + raw_text

    engine = "openai"
    engine_info: dict[str, str] | None = None
    openai_exc: BaseException | None = None
    has_key = llm_configured() and not is_free_cost_mode()

    try:
        if has_key:
            raw_log = generate_field_with_openai(prompt_text, settings, f, style_block)
        else:
            engine = "fallback"
            engine_info = classify_openai_failure(no_key=True)
            raw_log = generate_field_fallback(settings, f)
    except Exception as e:
        engine = "fallback"
        openai_exc = e
        engine_info = classify_openai_failure(e)
        raw_log = generate_field_fallback(settings, f)

    if isinstance(raw_log, dict):
        raw_log.pop("_openai_error", None)

    log = _normalize_field_log(raw_log, settings, f)

    # 외근은 거리 검증 없이 방문 유무만 확인
    from modules.validator import validate_field_log

    validated = validate_field_log(log, settings)

    warnings = list(validated["warnings"] or [])
    if engine == "fallback" and engine_info:
        warnings.insert(0, engine_info["user_message"])
    if style_applied:
        warnings.insert(0 if engine != "fallback" else 1, "내 서식·말투 학습이 적용되었습니다.")

    if engine == "openai":
        message = (
            "AI로 외근일지를 생성했습니다. 방문·결과를 한 번 확인해 주세요."
            if validated["ok"]
            else "검증 오류가 있습니다. 내용을 확인해 주세요."
        )
        engine_reason = "ok"
        engine_title = "AI 생성"
    else:
        info = engine_info or classify_openai_failure(openai_exc)
        engine_reason = info["code"]
        engine_title = info["title"]
        message = info["user_message"] if validated["ok"] else f"{info['user_message']} 내용을 확인해 주세요."

    return {
        "success": validated["ok"],
        "log": validated["enriched_log"],
        "errors": validated["errors"],
        "warnings": warnings,
        "engine": engine,
        "engine_reason": engine_reason,
        "engine_title": engine_title,
        "engine_detail": (engine_info or {}).get("detail", "") if engine == "fallback" else "",
        "style_applied": style_applied,
        "message": message,
        "report_type": "field",
    }
