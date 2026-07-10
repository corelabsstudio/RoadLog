"""
운행시간 · 거리 검증 + 점심시간 자동 제외 로직
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any


TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def parse_hhmm(s: str) -> int | None:
    """HH:MM → 분 단위(0~1439). 실패 시 None."""
    if not s:
        return None
    s = str(s).strip()
    m = TIME_RE.match(s)
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        return None
    return h * 60 + mi


def minutes_to_hhmm(m: int) -> str:
    m = max(0, m) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def overlap_minutes(a0: int, a1: int, b0: int, b1: int) -> int:
    """두 구간 [a0,a1), [b0,b1) 교집합 분."""
    start = max(a0, b0)
    end = min(a1, b1)
    return max(0, end - start)


def exclude_lunch_from_duration(
    depart: str,
    arrive: str,
    lunch_start: str = "12:00",
    lunch_end: str = "13:00",
    exclude: bool = True,
) -> dict[str, Any]:
    """
    출발~도착 시간에서 점심 구간을 제외한 순수 운행 분 계산.
    자정 넘김은 단순 지원(+24h).
    """
    d = parse_hhmm(depart)
    a = parse_hhmm(arrive)
    ls = parse_hhmm(lunch_start) or 12 * 60
    le = parse_hhmm(lunch_end) or 13 * 60

    if d is None or a is None:
        return {
            "raw_minutes": 0,
            "lunch_minutes": 0,
            "net_minutes": 0,
            "valid": False,
            "message": "시간 형식이 올바르지 않습니다. (HH:MM)",
        }

    if a < d:
        a += 24 * 60  # 야간 운행

    raw = a - d
    lunch_hit = 0
    if exclude and le > ls:
        lunch_hit = overlap_minutes(d, a, ls, le)
        # 자정 넘김 시 다음날 점심도 고려
        if a > 24 * 60:
            lunch_hit += overlap_minutes(d, a, ls + 24 * 60, le + 24 * 60)

    net = max(0, raw - lunch_hit)
    return {
        "raw_minutes": raw,
        "lunch_minutes": lunch_hit,
        "net_minutes": net,
        "valid": True,
        "message": "ok",
    }


def validate_trip(trip: dict, settings: dict) -> list[str]:
    """단일 운행 구간 검증 메시지 목록 (비어 있으면 OK)."""
    errors: list[str] = []
    depart = str(trip.get("depart_time", "")).strip()
    arrive = str(trip.get("arrive_time", "")).strip()
    dist = trip.get("distance_km", 0)

    if parse_hhmm(depart) is None:
        errors.append(f"출발 시간 오류: {depart}")
    if parse_hhmm(arrive) is None:
        errors.append(f"도착 시간 오류: {arrive}")

    try:
        dist_f = float(dist)
        if dist_f < 0:
            errors.append("거리는 0 이상이어야 합니다.")
        if dist_f > 2000:
            errors.append(f"비정상적으로 긴 거리입니다: {dist_f} km")
    except (TypeError, ValueError):
        errors.append(f"거리 형식 오류: {dist}")

    if not str(trip.get("from", "")).strip():
        errors.append("출발지가 비어 있습니다.")
    if not str(trip.get("to", "")).strip():
        errors.append("도착지가 비어 있습니다.")

    # 평균 속도 합리성 (순수 운행시간 기준)
    dur = exclude_lunch_from_duration(
        depart,
        arrive,
        settings.get("lunch_start", "12:00"),
        settings.get("lunch_end", "13:00"),
        bool(settings.get("exclude_lunch", True)),
    )
    if dur["valid"] and dur["net_minutes"] > 0:
        try:
            dist_f = float(dist or 0)
            hours = dur["net_minutes"] / 60.0
            speed = dist_f / hours if hours > 0 else 0
            if speed > 160:
                errors.append(
                    f"평균 속도가 비현실적입니다 ({speed:.0f} km/h). 시간/거리를 확인하세요."
                )
            if dist_f > 1 and speed < 5 and dur["net_minutes"] > 30:
                errors.append(
                    f"평균 속도가 너무 낮습니다 ({speed:.1f} km/h). 시간/거리를 확인하세요."
                )
        except Exception:
            pass
    elif dur["valid"] and dur["net_minutes"] == 0 and float(dist or 0) > 0:
        errors.append("운행 시간이 0분인데 거리가 있습니다.")

    return errors


def validate_field_log(log: dict, settings: dict) -> dict[str, Any]:
    """
    외근·출장 일지 검증 (거리·속도 검증 없음).
    반환: { ok, errors, warnings, enriched_log }
    """
    errors: list[str] = []
    warnings: list[str] = []
    visits = list(log.get("visits") or [])
    if not visits:
        # trips 호환
        for t in log.get("trips") or []:
            if not isinstance(t, dict):
                continue
            place = str(t.get("to") or t.get("place") or "").strip()
            if place:
                visits.append(
                    {
                        "time": str(t.get("depart_time") or t.get("time") or "").strip(),
                        "place": place,
                        "purpose": str(t.get("purpose") or "업무 방문").strip(),
                        "result": str(t.get("result") or "").strip(),
                        "next_action": str(t.get("next_action") or "").strip(),
                        "memo": str(t.get("memo") or "").strip(),
                    }
                )

    if not visits:
        errors.append("방문 기록이 없습니다.")

    for i, v in enumerate(visits, start=1):
        if not str(v.get("place") or "").strip():
            errors.append(f"[{i}행] 방문처가 비어 있습니다.")
        if not str(v.get("purpose") or "").strip():
            v["purpose"] = settings.get("default_purpose", "업무 방문")

    enriched = dict(log)
    enriched["report_type"] = "field"
    enriched["visits"] = visits
    # 기존 다운로드 UI·export trips 경로 호환
    if not enriched.get("trips") and visits:
        origin = "본사"
        places = settings.get("frequent_places") or []
        if places and places[0].get("name"):
            origin = places[0]["name"]
        trips = []
        prev = origin
        for v in visits:
            t0 = str(v.get("time") or "09:30")
            trips.append(
                {
                    "depart_time": t0,
                    "arrive_time": t0,
                    "from": prev,
                    "to": v.get("place") or "",
                    "purpose": v.get("purpose") or "업무 방문",
                    "distance_km": 0,
                    "memo": " / ".join(
                        x
                        for x in (
                            f"결과: {v['result']}" if v.get("result") else "",
                            f"후속: {v['next_action']}" if v.get("next_action") else "",
                            v.get("memo") or "",
                        )
                        if x
                    ),
                    "result": v.get("result") or "",
                    "next_action": v.get("next_action") or "",
                    "raw_minutes": 0,
                    "lunch_excluded_minutes": 0,
                    "net_minutes": 0,
                    "duration_display": "-",
                }
            )
            prev = v.get("place") or prev
        enriched["trips"] = trips
    enriched["total_distance_km"] = float(enriched.get("total_distance_km") or 0)
    enriched["total_net_minutes"] = int(enriched.get("total_net_minutes") or 0)
    enriched["total_lunch_excluded_minutes"] = 0
    if settings.get("driver_name") and not enriched.get("driver_name"):
        enriched["driver_name"] = settings["driver_name"]
    if settings.get("company_name") and not enriched.get("company_name"):
        enriched["company_name"] = settings["company_name"]
    if not enriched.get("author_name"):
        enriched["author_name"] = enriched.get("driver_name") or ""

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "enriched_log": enriched,
    }


def validate_log(log: dict, settings: dict) -> dict[str, Any]:
    """
    전체 운행일지 검증 + 점심 제외 적용 필드 보강.
    반환: { ok, errors, warnings, enriched_log }
    """
    if str(log.get("report_type") or "").lower() in ("field", "field_visit", "outing"):
        return validate_field_log(log, settings)

    errors: list[str] = []
    warnings: list[str] = []
    trips = list(log.get("trips") or [])
    enriched_trips = []

    total_dist = 0.0
    total_net = 0
    total_lunch = 0

    prev_arrive = None
    for i, t in enumerate(trips, start=1):
        te = dict(t)
        errs = validate_trip(te, settings)
        for e in errs:
            errors.append(f"[{i}행] {e}")

        dur = exclude_lunch_from_duration(
            str(te.get("depart_time", "")),
            str(te.get("arrive_time", "")),
            settings.get("lunch_start", "12:00"),
            settings.get("lunch_end", "13:00"),
            bool(settings.get("exclude_lunch", True)),
        )
        te["raw_minutes"] = dur["raw_minutes"]
        te["lunch_excluded_minutes"] = dur["lunch_minutes"]
        te["net_minutes"] = dur["net_minutes"]
        te["duration_display"] = (
            f"{dur['net_minutes'] // 60}시간 {dur['net_minutes'] % 60}분"
            if dur["valid"]
            else "-"
        )

        try:
            total_dist += float(te.get("distance_km") or 0)
        except Exception:
            pass
        total_net += dur.get("net_minutes") or 0
        total_lunch += dur.get("lunch_minutes") or 0

        # 이전 도착 이후 출발인지
        if prev_arrive is not None:
            d = parse_hhmm(str(te.get("depart_time", "")))
            if d is not None and d + (24 * 60 if d < prev_arrive else 0) < prev_arrive:
                warnings.append(f"[{i}행] 이전 구간 도착 전에 출발한 것으로 보입니다.")
        pa = parse_hhmm(str(te.get("arrive_time", "")))
        if pa is not None:
            prev_arrive = pa

        if not str(te.get("purpose", "")).strip():
            te["purpose"] = settings.get("default_purpose", "업무 출장")

        enriched_trips.append(te)

    # 총 거리 정합
    declared = log.get("total_distance_km")
    try:
        if declared is not None and abs(float(declared) - total_dist) > 0.5:
            warnings.append(
                f"총 거리 불일치: 합계 {total_dist:.1f} km vs 표기 {float(declared):.1f} km → 합계로 보정"
            )
    except Exception:
        pass

    if not trips:
        errors.append("운행 구간이 없습니다.")

    enriched = dict(log)
    enriched["trips"] = enriched_trips
    enriched["total_distance_km"] = round(total_dist, 1)
    enriched["total_net_minutes"] = total_net
    enriched["total_lunch_excluded_minutes"] = total_lunch
    if settings.get("vehicle_number") and not enriched.get("vehicle"):
        enriched["vehicle"] = settings["vehicle_number"]
    if settings.get("driver_name"):
        enriched.setdefault("driver_name", settings["driver_name"])
    if settings.get("company_name"):
        enriched.setdefault("company_name", settings["company_name"])

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "enriched_log": enriched,
    }


def format_minutes_kr(m: int) -> str:
    h, mi = divmod(int(m), 60)
    if h and mi:
        return f"{h}시간 {mi}분"
    if h:
        return f"{h}시간"
    return f"{mi}분"
