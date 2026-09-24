"""Fail-closed gate for every ROADLOG marketing network provider."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.config import DATA_DIR
from modules.marketing_cost_guard import quote, usage_cost

DB = Path(DATA_DIR) / "marketing_os.db"
FLAGS = {"gemini": "MARKETING_GEMINI_ENABLED", "research": "MARKETING_RESEARCH_ENABLED",
         "image": "MARKETING_IMAGE_ENABLED", "video": "MARKETING_VIDEO_ENABLED",
         "sns": "MARKETING_SNS_ENABLED"}
LIMITS = {"gemini": 10, "research": 5, "image": 0, "video": 0, "sns": 0}
# Fail closed until the operator explicitly releases this gate in production.
# The global and per-provider switches below are still required after release.
RELEASE_HOLD = os.getenv("MARKETING_RELEASE_HOLD", "true").strip().lower() != "false"


def on(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() == "true"


def enabled(provider: str) -> bool:
    return not RELEASE_HOLD and on("MARKETING_EXTERNAL_API_ENABLED") and on(FLAGS[provider])


def board() -> dict:
    return {"external_api_enabled": not RELEASE_HOLD and on("MARKETING_EXTERNAL_API_ENABLED"),
            "release_hold": RELEASE_HOLD,
            "providers": {key: {"enabled": enabled(key), "configured": on(flag), "max_calls_per_campaign": LIMITS[key]}
                          for key, flag in FLAGS.items()},
            "automatic_publishing_enabled": enabled("sns") and on("MARKETING_AUTO_PUBLISH_ENABLED"),
            "limits": {"gemini": 10, "research": 5, "image": 0},
            "actual_calls_recorded": audit_count(), "cost_control": cost_status()}


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS marketing_external_call_audit ("
                 "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, provider TEXT NOT NULL, "
                 "operation TEXT NOT NULL, agent_id TEXT NOT NULL, called_at TEXT NOT NULL, "
                 "result TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS marketing_cost_settings ("
                 "id INTEGER PRIMARY KEY CHECK(id=1),paid_enabled INTEGER NOT NULL DEFAULT 0,"
                 "daily_budget_krw INTEGER NOT NULL DEFAULT 3000,daily_requests INTEGER NOT NULL DEFAULT 20,"
                 "per_agent_requests INTEGER NOT NULL DEFAULT 5,max_concurrent INTEGER NOT NULL DEFAULT 2)")
    conn.execute("INSERT OR IGNORE INTO marketing_cost_settings(id) VALUES(1)")
    conn.execute("CREATE TABLE IF NOT EXISTS marketing_cost_kill (day TEXT PRIMARY KEY,reason TEXT NOT NULL,created_at TEXT NOT NULL)")
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(marketing_external_call_audit)")}
    for name, kind in (("model","TEXT"),("estimated_cost_krw","REAL"),("reserved_cost_krw","REAL"),
                       ("actual_cost_estimate_krw","REAL"),("thought_tokens","INTEGER"),
                       ("input_token_ceiling","INTEGER"),("output_token_ceiling","INTEGER")):
        if name not in columns:
            conn.execute(f"ALTER TABLE marketing_external_call_audit ADD COLUMN {name} {kind}")
    conn.commit()
    return conn


def cost_settings() -> dict:
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        return dict(conn.execute("SELECT * FROM marketing_cost_settings WHERE id=1").fetchone())


def update_cost_settings(*, paid_enabled: bool | None = None, daily_budget_krw: int | None = None,
                         daily_requests: int | None = None, per_agent_requests: int | None = None) -> dict:
    values = {"paid_enabled": paid_enabled, "daily_budget_krw": daily_budget_krw,
              "daily_requests": daily_requests, "per_agent_requests": per_agent_requests}
    bounds = {"daily_budget_krw": (1, 3000), "daily_requests": (1, 20), "per_agent_requests": (1, 5)}
    for key, value in values.items():
        if value is None: continue
        if key == "paid_enabled" and type(value) is not bool: raise ValueError("유료 API 설정 형식 오류")
        if key != "paid_enabled" and (type(value) is not int or not bounds[key][0] <= value <= bounds[key][1]):
            raise ValueError("안전 한도 범위를 벗어났습니다.")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for key, value in values.items():
            if value is not None:
                conn.execute(f"UPDATE marketing_cost_settings SET {key}=? WHERE id=1", (int(value),))
    return cost_settings()


def cost_status() -> dict:
    day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        settings = dict(conn.execute("SELECT * FROM marketing_cost_settings WHERE id=1").fetchone())
        total = conn.execute("SELECT COUNT(*),COALESCE(SUM(reserved_cost_krw),0),COALESCE(SUM(actual_cost_estimate_krw),0) "
                             "FROM marketing_external_call_audit WHERE substr(called_at,1,10)=? AND provider IN ('gemini','research')", (day,)).fetchone()
        killed = conn.execute("SELECT reason FROM marketing_cost_kill WHERE day=?", (day,)).fetchone()
    return {**settings, "day": day, "calls": total[0], "reserved_cost_krw": total[1],
            "actual_cost_estimate_krw": total[2], "kill_reason": killed[0] if killed else None,
            "actual_billed_cost_krw": None}


def trip_kill(reason: str) -> None:
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("INSERT OR IGNORE INTO marketing_cost_kill(day,reason,created_at) VALUES(?,?,?)", (stamp[:10],reason[:120],stamp))


def audit_count() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit").fetchone()[0])


def diagnostic_audit_count(diagnostic_id: int) -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE campaign_id=? AND provider='research' AND operation='diagnostic:tavily_search'",
                                (-diagnostic_id,)).fetchone()[0])


def before_call(provider: str, operation: str, *, campaign_id: int = 0, agent_id: str = "manual",
                model: str | None = None, request_body: dict | None = None) -> int:
    if not enabled(provider):
        raise PermissionError("마케팅 외부 API가 비활성화되어 있습니다.")
    if provider in {"image", "video"} and LIMITS[provider] == 0:
        raise PermissionError("이미지·영상 외부 호출 한도는 0건입니다.")
    if provider == "sns":
        raise PermissionError("SNS 외부 게시 한도는 0건입니다.")
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    day = stamp[:10]
    if provider == "gemini":
        try: estimate = quote(model or "", request_body, day)
        except (PermissionError, ValueError, TypeError):
            trip_kill("Gemini 비용 사전 계산 실패")
            raise PermissionError("PAUSED_BY_BUDGET: Gemini 비용을 계산할 수 없습니다.")
    elif provider == "research" and operation in {"tavily_search", "diagnostic:tavily_search"}:
        estimate = {"estimated_cost_krw": 16, "reserved_cost_krw": 32}
    elif provider == "research":
        trip_kill("검색 공급자 비용 미확인")
        raise PermissionError("PAUSED_BY_BUDGET: 검색 비용을 계산할 수 없습니다.")
    else:
        estimate = {"estimated_cost_krw": 0, "reserved_cost_krw": 0}
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if provider in {"gemini", "research"}:
            settings = conn.execute("SELECT paid_enabled,daily_budget_krw,daily_requests,per_agent_requests,max_concurrent FROM marketing_cost_settings WHERE id=1").fetchone()
            if not settings[0]: raise PermissionError("유료 외부 API가 관리자 설정에서 꺼져 있습니다.")
            if conn.execute("SELECT 1 FROM marketing_cost_kill WHERE day=?", (day,)).fetchone():
                raise PermissionError("PAUSED_BY_BUDGET: 오늘 유료 외부 API가 긴급 차단됐습니다.")
            if conn.execute("SELECT 1 FROM marketing_external_call_audit WHERE substr(called_at,1,10)=? AND provider IN ('gemini','research') AND reserved_cost_krw IS NULL LIMIT 1", (day,)).fetchone():
                raise PermissionError("PAUSED_BY_BUDGET: 기존 호출의 비용 예약 기록이 없어 오늘 유료 API 차단")
            counters = conn.execute("SELECT COUNT(*),COALESCE(SUM(reserved_cost_krw),0) FROM marketing_external_call_audit WHERE substr(called_at,1,10)=? AND provider IN ('gemini','research')", (day,)).fetchone()
            if counters[1] >= settings[1]:
                conn.execute("INSERT OR IGNORE INTO marketing_cost_kill(day,reason,created_at) VALUES(?,?,?)", (day,"내부 일일 예산 도달",stamp))
                conn.commit()
                raise PermissionError("PAUSED_BY_BUDGET: 오늘 내부 예산 도달")
            agent_calls = conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE substr(called_at,1,10)=? AND provider IN ('gemini','research') AND agent_id=?", (day,agent_id)).fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE provider IN ('gemini','research') AND result='ATTEMPTED'").fetchone()[0]
            if counters[0] >= settings[2] or agent_calls >= settings[3] or active >= settings[4] or counters[1] + estimate["reserved_cost_krw"] > settings[1]:
                raise PermissionError("PAUSED_BY_BUDGET: 일일 비용·호출·팀원·동시 실행 한도 도달")
            recent = [row[0] for row in conn.execute("SELECT result FROM marketing_external_call_audit WHERE substr(called_at,1,10)=? AND provider IN ('gemini','research') ORDER BY id DESC LIMIT 3", (day,))]
            if len(recent) == 3 and all(value in {"TIMEOUT", "TRANSPORT_ERROR", "USAGE_INVALID", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504"} for value in recent):
                conn.execute("INSERT OR IGNORE INTO marketing_cost_kill(day,reason,created_at) VALUES(?,?,?)", (day,"연속 외부 API 실패 3회",stamp))
                conn.commit()
                raise PermissionError("PAUSED_BY_BUDGET: 연속 실패로 오늘 유료 호출 차단")
        if campaign_id:
            count = conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE campaign_id=? AND provider=?",
                                 (campaign_id, provider)).fetchone()[0]
        else:
            count = conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE campaign_id=0 AND provider=? AND substr(called_at,1,10)=?",
                                 (provider, day)).fetchone()[0]
        if count >= LIMITS[provider]:
            raise PermissionError("PAUSED_BY_BUDGET: 캠페인별 외부 API 호출 한도에 도달했습니다.")
        row = conn.execute("INSERT INTO marketing_external_call_audit(campaign_id,provider,operation,agent_id,called_at,result,model,estimated_cost_krw,reserved_cost_krw,input_token_ceiling,output_token_ceiling) "
                           "VALUES(?,?,?,?,?,'ATTEMPTED',?,?,?,?,?)", (campaign_id, provider, operation, agent_id, stamp, model, estimate["estimated_cost_krw"], estimate["reserved_cost_krw"], estimate.get("input_token_ceiling"), estimate.get("output_token_ceiling")))
        return int(row.lastrowid)


def after_call(audit_id: int, result: str, *, input_tokens: int | None = None, output_tokens: int | None = None,
               thought_tokens: int | None = None, actual_cost_estimate_krw: float | None = None) -> None:
    with _connect() as conn:
        conn.execute("UPDATE marketing_external_call_audit SET result=?,input_tokens=?,output_tokens=?,thought_tokens=?,actual_cost_estimate_krw=? WHERE id=?",
                     (result[:40], input_tokens, output_tokens, thought_tokens, actual_cost_estimate_krw, audit_id))
        failures = {"TIMEOUT", "TRANSPORT_ERROR", "USAGE_INVALID", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504"}
        if result in failures:
            row = conn.execute("SELECT substr(called_at,1,10) FROM marketing_external_call_audit WHERE id=?", (audit_id,)).fetchone()
            if row:
                recent = [item[0] for item in conn.execute("SELECT result FROM marketing_external_call_audit WHERE substr(called_at,1,10)=? AND provider IN ('gemini','research') ORDER BY id DESC LIMIT 3", (row[0],))]
                if len(recent) == 3 and all(value in failures for value in recent):
                    conn.execute("INSERT OR IGNORE INTO marketing_cost_kill(day,reason,created_at) VALUES(?,?,?)", (row[0],"연속 외부 API 실패 3회",datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")))


def record_usage(audit_id: int, model: str, usage: dict) -> dict:
    try:
        values = usage_cost(model, usage, datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
    except (ValueError, PermissionError, TypeError):
        after_call(audit_id, "USAGE_INVALID")
        trip_kill("AI 사용량 응답 누락 또는 오류")
        raise PermissionError("PAUSED_BY_BUDGET: AI 사용량을 확인할 수 없습니다.")
    with _connect() as conn:
        row = conn.execute("SELECT reserved_cost_krw,input_token_ceiling,output_token_ceiling FROM marketing_external_call_audit WHERE id=? AND provider='gemini'", (audit_id,)).fetchone()
    if not row or values["actual_cost_estimate_krw"] > row[0] or values["input_tokens"] > row[1] or values["output_tokens"] > row[2]:
        after_call(audit_id, "USAGE_SPIKE", **values)
        trip_kill("AI 사용량이 사전 예약 범위를 초과")
        raise PermissionError("PAUSED_BY_BUDGET: AI 사용량 급증으로 오늘 유료 호출 차단")
    after_call(audit_id, "SUCCESS", **values)
    return values
