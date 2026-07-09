"""
OpenAI few-shot 기반 격식 있는 운행일지 생성
<<<<<<< HEAD
구조화 입력(주행거리·점심·오전/오후 장소) → AI가 시간·구간·문체 자동 작성
=======
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
API 키 없을 때 규칙 기반 폴백 생성기 제공
"""

from __future__ import annotations

import json
import re
<<<<<<< HEAD
from datetime import date
=======
from datetime import date, datetime
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
from typing import Any

from modules.config import FEW_SHOT_EXAMPLES, OPENAI_API_KEY, OPENAI_MODEL
from modules.validator import validate_log


SYSTEM_PROMPT = """당신은 대한민국 기업의 공식 업무용 '차량 운행일지'를 작성하는 전문 비서입니다.
<<<<<<< HEAD
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
6. 오전 방문지 → 점심 식당 → 오후 방문지 순으로 운행 구간(trips)을 구성합니다.
7. 보통 출발/복귀 기점은 본사(또는 설정 회사/자주 가는 곳 첫 항목)입니다.
8. 점심 식당 방문 구간 purpose는 사용자 습관에 맞는 표현(예: 중식, 중식 식사 등)으로 표기합니다.
9. 사용자가 명시하지 않은 시각·세부 목적은 업무용으로 자연스럽게 추론하되 과장하지 않습니다.
10. 회사 제출용으로 신뢰 가능한 수준을 유지합니다.
11. purpose, memo, summary 표현은 프로필의 어휘·호흡을 모방하세요. 일반적인 AI 문장투를 피하세요.
=======

규칙:
1. 반드시 JSON만 출력합니다. 설명·마크다운·코드펜스 금지.
2. 문체: 격식 있는 업무 문체 (개조식·간결).
3. 시간은 24시간제 HH:MM.
4. 거리는 km 단위 숫자(소수 1자리 가능).
5. 사용자가 명시하지 않은 정보는 합리적으로 추론하되, 과장하지 않습니다.
6. 점심시간(설정값)이 운행에 겹치면 이동 구간을 분리하거나 목적에 반영합니다.
7. 회사 제출용으로 신뢰 가능한 수준을 유지합니다.
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)

JSON 스키마:
{
  "date": "YYYY-MM-DD",
  "vehicle": "차량번호",
  "driver_name": "운전자",
  "company_name": "회사명",
<<<<<<< HEAD
  "odometer_start": 0.0,
  "odometer_end": 0.0,
=======
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
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
<<<<<<< HEAD
  "summary": "금일 운행 요약 (한 문장)",
  "lunch_place": "점심 식당명"
=======
  "summary": "금일 운행 요약 (한 문장)"
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
}
"""


<<<<<<< HEAD
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

    return {
        "odometer_start": odo_s,
        "odometer_end": odo_e,
        "lunch_restaurant": lunch,
        "morning_places": morning_list,
        "afternoon_places": afternoon_list,
        "vehicle_number": vehicle,
        "extra_note": (form.get("extra_note") or form.get("note") or "").strip(),
    }


def form_to_raw_text(form: dict) -> str:
    """구조화 입력 → 프롬프트용 자연어 블록."""
    f = normalize_form(form)
    morning = ", ".join(f["morning_places"]) or "(없음)"
    afternoon = ", ".join(f["afternoon_places"]) or "(없음)"
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
        f"- 점심 식당: {lunch}",
        f"- 오전 방문지: {morning}",
        f"- 오후 방문지: {afternoon}",
    ]
    if note:
        lines.append(f"- 추가 메모: {note}")
    lines.append("")
    lines.append(
        "위 정보를 바탕으로 시간·구간·목적을 채운 공식 운행일지 JSON을 작성하세요. "
        "누적 주행거리와 총 거리는 반드시 입력값을 따르세요."
    )
    return "\n".join(lines)


def _build_user_prompt(
    raw_text: str,
    settings: dict,
    form: dict | None = None,
    style_block: str = "",
) -> str:
=======
def _build_user_prompt(raw_text: str, settings: dict) -> str:
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    places = settings.get("frequent_places") or []
    places_str = ", ".join(
        f"{p.get('name')}" + (f"({p.get('address')})" if p.get("address") else "")
        for p in places
        if p.get("name")
    ) or "(없음)"

    few = FEW_SHOT_EXAMPLES[0] if FEW_SHOT_EXAMPLES else None
    few_block = ""
<<<<<<< HEAD
    if few and not style_block.strip():
        # 사용자 스타일이 없을 때만 기본 few-shot 사용
=======
    if few:
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        few_block = (
            "\n[Few-shot 예시]\n"
            f"입력: {few['input']}\n"
            f"출력: {json.dumps(few['output'], ensure_ascii=False)}\n"
        )

<<<<<<< HEAD
    form_block = ""
    if form:
        form_block = "\n" + form_to_raw_text(form) + "\n"

    return f"""{style_block}
{few_block}
=======
    return f"""{few_block}
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
[사용자 설정]
- 오늘 날짜: {date.today().isoformat()}
- 차량번호: {settings.get('vehicle_number') or '(미설정)'}
- 운전자: {settings.get('driver_name') or '(미설정)'}
- 회사: {settings.get('company_name') or '(미설정)'}
- 점심시간: {settings.get('lunch_start', '12:00')} ~ {settings.get('lunch_end', '13:00')} (제외={settings.get('exclude_lunch', True)})
- 기본 목적: {settings.get('default_purpose', '업무 출장')}
- 자주 가는 곳: {places_str}
<<<<<<< HEAD
{form_block}
[추가 자유 입력]
{raw_text or '(없음)'}

위 내용을 공식 운행일지 JSON으로 변환하세요.
회사 서식 프로필이 있으면:
- 해당 회사 양식의 항목·표현 습관에 맞출 것
- purpose/memo/summary 를 그 말투로 쓸 것
- 컬럼에 대응하는 필드를 trips/meta에 충실히 채울 것
=======

[사용자 입력 — 자연어 운행 내용]
{raw_text}

위 내용을 공식 운행일지 JSON으로 변환하세요.
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
"""


def _extract_json(text: str) -> dict:
    """모델 응답에서 JSON 객체 추출."""
    text = text.strip()
<<<<<<< HEAD
=======
    # 코드펜스 제거
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
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


<<<<<<< HEAD
def generate_with_openai(
    raw_text: str,
    settings: dict,
    form: dict | None = None,
    style_block: str = "",
) -> dict[str, Any]:
=======
def generate_with_openai(raw_text: str, settings: dict) -> dict[str, Any]:
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    """OpenAI Chat Completions 호출."""
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
<<<<<<< HEAD
    # 스타일 학습 시 창의성 약간 낮춤 (일관성)
    temp = 0.25 if style_block.strip() else 0.3
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=temp,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(raw_text, settings, form, style_block),
            },
=======
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(raw_text, settings)},
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        ],
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    return _extract_json(content)


<<<<<<< HEAD
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

    vehicle = settings.get("vehicle_number") or ""
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
                "memo": "규칙 기반 초안",
            }
        ]
        return _pack_log(settings, vehicle, trips, total_dist or 15.0, odo_s, odo_e, f["lunch_restaurant"])

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
                "memo": "규칙 기반 초안 (OpenAI 키 설정 시 고품질 생성)" if i == 0 else "",
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
=======
def generate_fallback(raw_text: str, settings: dict) -> dict[str, Any]:
    """
    API 키 없을 때 규칙 기반 간단 생성.
    시간·장소 키워드를 파싱해 최소 1~2개 구간 생성.
    """
    text = raw_text.strip()
    times = re.findall(r"(\d{1,2})\s*[:시]\s*(\d{2})?", text)
    hhmm_list = []
    for h, m in times:
        mi = int(m) if m else 0
        hhmm_list.append(f"{int(h):02d}:{mi:02d}")

    # 출발/도착 추정
    if len(hhmm_list) >= 2:
        t0, t1 = hhmm_list[0], hhmm_list[1]
    elif len(hhmm_list) == 1:
        t0, t1 = hhmm_list[0], _add_minutes(hhmm_list[0], 50)
    else:
        t0, t1 = "09:00", "10:00"

    # 장소 힌트
    places = settings.get("frequent_places") or []
    place_names = [p.get("name") for p in places if p.get("name")]
    origin = place_names[0] if place_names else "본사"
    dest = place_names[1] if len(place_names) > 1 else "거래처"

    # 텍스트에서 '에서/까지/→' 패턴
    m = re.search(r"([가-힣A-Za-z0-9\s]+?)(?:에서|출발).*?([가-힣A-Za-z0-9\s]+?)(?:까지|로|에\s|도착|미팅)", text)
    if m:
        origin = m.group(1).strip()[:30] or origin
        dest = m.group(2).strip()[:30] or dest

    vehicle = settings.get("vehicle_number") or ""
    vm = re.search(r"(\d{2,3}[가-힣]\d{4})", text)
    if vm:
        vehicle = vm.group(1)

    purpose = settings.get("default_purpose", "업무 출장")
    if "미팅" in text or "회의" in text:
        purpose = "고객/업무 미팅"
    elif "납품" in text or "배송" in text:
        purpose = "납품/배송"
    elif "복귀" in text:
        purpose = "업무 복귀"

    # 거리 추정 (텍스트에 km 있으면 사용)
    dist_total = 15.0
    dm = re.search(r"(\d+(?:\.\d+)?)\s*km", text, re.I)
    if dm:
        dist_total = float(dm.group(1))

    is_round = any(k in text for k in ("복귀", "돌아", "왕복"))
    # "왕복 37km"처럼 총거리를 말한 경우 편도 절반 배분
    leg_dist = round(dist_total / 2, 1) if is_round and dist_total > 0 else dist_total

    trips = [
        {
            "depart_time": t0,
            "arrive_time": t1,
            "from": origin,
            "to": dest,
            "purpose": purpose,
            "distance_km": leg_dist,
            "memo": "규칙 기반 초안 (OpenAI 키 설정 시 고품질 생성)",
        }
    ]

    # 복귀 언급 시 왕복
    if is_round:
        t2 = hhmm_list[2] if len(hhmm_list) > 2 else _add_minutes(t1, 180)
        t3 = hhmm_list[3] if len(hhmm_list) > 3 else _add_minutes(t2, 50)
        trips.append(
            {
                "depart_time": t2,
                "arrive_time": t3,
                "from": dest,
                "to": origin,
                "purpose": "업무 복귀",
                "distance_km": leg_dist,
                "memo": "",
            }
        )

    total = sum(float(t["distance_km"]) for t in trips)
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    return {
        "date": date.today().isoformat(),
        "vehicle": vehicle,
        "driver_name": settings.get("driver_name", ""),
        "company_name": settings.get("company_name", ""),
<<<<<<< HEAD
        "odometer_start": odo_s if odo_s else None,
        "odometer_end": odo_e if odo_e else None,
        "lunch_place": lunch or "",
        "trips": trips,
        "total_distance_km": round(total_dist, 1),
        "summary": summary,
=======
        "trips": trips,
        "total_distance_km": round(total, 1),
        "summary": f"{origin} → {dest} 업무 운행" + (" (왕복)" if len(trips) > 1 else ""),
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        "_engine": "fallback",
    }


def _add_minutes(hhmm: str, add: int) -> str:
<<<<<<< HEAD
    h, m = map(int, str(hhmm).split(":")[:2])
=======
    h, m = map(int, hhmm.split(":"))
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    total = h * 60 + m + add
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"


<<<<<<< HEAD
def _apply_odometer(log: dict, form: dict | None) -> dict:
    """누적 주행거리·차량번호 등 폼 입력 강제 반영."""
    f = normalize_form(form)
    if f["odometer_start"] or f["odometer_end"]:
        log["odometer_start"] = f["odometer_start"]
        log["odometer_end"] = f["odometer_end"]
        if f["odometer_end"] >= f["odometer_start"] and (f["odometer_end"] or f["odometer_start"]):
            dist = round(f["odometer_end"] - f["odometer_start"], 1)
            log["total_distance_km"] = dist
    if f["lunch_restaurant"]:
        log["lunch_place"] = f["lunch_restaurant"]
    # 작성 폼 차량번호가 있으면 설정값보다 우선
    if f.get("vehicle_number"):
        log["vehicle"] = f["vehicle_number"]
    return log


def generate_driving_log(
    raw_text: str = "",
    settings: dict | None = None,
    form: dict | None = None,
    user_email: str | None = None,
) -> dict[str, Any]:
    """
    메인 엔트리.
    form: odometer_start, odometer_end, lunch_restaurant, morning_places, afternoon_places
    user_email: 있으면 해당 사용자 서식·말투 프로필을 적용
    """
    settings = settings or {}
    f = normalize_form(form)

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
=======
def generate_driving_log(raw_text: str, settings: dict) -> dict[str, Any]:
    """
    메인 엔트리.
    반환: {
      success, log, errors, warnings, engine, message
    }
    """
    if not (raw_text or "").strip():
        return {
            "success": False,
            "log": None,
            "errors": ["운행 내용을 입력해 주세요."],
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
            "warnings": [],
            "engine": None,
            "message": "입력 없음",
        }

<<<<<<< HEAD
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
        prompt_text = form_to_raw_text(f) + ("\n" + raw_text if raw_text else "")

    engine = "openai"
    try:
        if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-xxxx"):
            raw_log = generate_with_openai(prompt_text, settings, f, style_block)
        else:
            engine = "fallback"
            raw_log = generate_fallback(prompt_text, settings, f)
            raw_log = _apply_style_to_fallback(raw_log, user_email)
    except Exception as e:
        engine = "fallback"
        raw_log = generate_fallback(prompt_text, settings, f)
        raw_log = _apply_style_to_fallback(raw_log, user_email)
        raw_log["_openai_error"] = str(e)

    # 설정·주행거리 보강 (폼 차량번호는 _apply_odometer 에서 우선)
    if f.get("vehicle_number"):
        raw_log["vehicle"] = f["vehicle_number"]
    elif settings.get("vehicle_number") and not raw_log.get("vehicle"):
=======
    engine = "openai"
    try:
        if OPENAI_API_KEY and not OPENAI_API_KEY.startswith("sk-xxxx"):
            raw_log = generate_with_openai(raw_text, settings)
        else:
            engine = "fallback"
            raw_log = generate_fallback(raw_text, settings)
    except Exception as e:
        # OpenAI 실패 시 폴백
        engine = "fallback"
        raw_log = generate_fallback(raw_text, settings)
        raw_log["_openai_error"] = str(e)

    # 설정값 보강
    if settings.get("vehicle_number") and not raw_log.get("vehicle"):
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
        raw_log["vehicle"] = settings["vehicle_number"]
    raw_log.setdefault("driver_name", settings.get("driver_name", ""))
    raw_log.setdefault("company_name", settings.get("company_name", ""))
    if not raw_log.get("date"):
        raw_log["date"] = date.today().isoformat()
<<<<<<< HEAD
    raw_log = _apply_odometer(raw_log, f)

    validated = validate_log(raw_log, settings)
    # odometer·차량번호 필드 유지
    if validated.get("enriched_log") is not None:
        validated["enriched_log"] = _apply_odometer(validated["enriched_log"], f)
        if f["lunch_restaurant"]:
            validated["enriched_log"]["lunch_place"] = f["lunch_restaurant"]
        if f.get("vehicle_number"):
            validated["enriched_log"]["vehicle"] = f["vehicle_number"]

    warnings = list(validated["warnings"] or [])
    if style_applied:
        warnings.insert(0, "내 서식·말투 학습이 적용되었습니다.")
    elif user_email and not style_applied:
        warnings.insert(
            0,
            "서식 학습 전이거나 샘플이 부족합니다. [내 서식 학습]에서 기존 일지 3~5장을 올려 주세요.",
        )

=======

    validated = validate_log(raw_log, settings)
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
    return {
        "success": validated["ok"],
        "log": validated["enriched_log"],
        "errors": validated["errors"],
<<<<<<< HEAD
        "warnings": warnings,
        "engine": engine,
        "style_applied": style_applied,
        "message": "생성 완료" if validated["ok"] else "검증 오류가 있습니다. 내용을 확인해 주세요.",
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
=======
        "warnings": validated["warnings"],
        "engine": engine,
        "message": "생성 완료" if validated["ok"] else "검증 오류가 있습니다. 내용을 확인해 주세요.",
    }
>>>>>>> 1e1d5d4d (운행일지 v2 저장 지점)
