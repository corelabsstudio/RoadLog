"""Fail-closed gate for every ROADLOG marketing network provider."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from modules.config import DATA_DIR

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
            "actual_calls_recorded": audit_count()}


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute("CREATE TABLE IF NOT EXISTS marketing_external_call_audit ("
                 "id INTEGER PRIMARY KEY, campaign_id INTEGER NOT NULL, provider TEXT NOT NULL, "
                 "operation TEXT NOT NULL, agent_id TEXT NOT NULL, called_at TEXT NOT NULL, "
                 "result TEXT NOT NULL, input_tokens INTEGER, output_tokens INTEGER)")
    return conn


def audit_count() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit").fetchone()[0])


def diagnostic_audit_count(diagnostic_id: int) -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE campaign_id=? AND provider='research' AND operation='diagnostic:tavily_search'",
                                (-diagnostic_id,)).fetchone()[0])


def before_call(provider: str, operation: str, *, campaign_id: int = 0, agent_id: str = "manual") -> int:
    if not enabled(provider):
        raise PermissionError("마케팅 외부 API가 비활성화되어 있습니다.")
    if provider in {"image", "video"} and LIMITS[provider] == 0:
        raise PermissionError("이미지·영상 외부 호출 한도는 0건입니다.")
    if provider == "sns":
        raise PermissionError("SNS 외부 게시 한도는 0건입니다.")
    stamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute("SELECT COUNT(*) FROM marketing_external_call_audit WHERE campaign_id=? AND provider=?",
                             (campaign_id, provider)).fetchone()[0]
        if count >= LIMITS[provider]:
            raise PermissionError("PAUSED_BY_BUDGET: 캠페인별 외부 API 호출 한도에 도달했습니다.")
        row = conn.execute("INSERT INTO marketing_external_call_audit(campaign_id,provider,operation,agent_id,called_at,result) "
                           "VALUES(?,?,?,?,?,'ATTEMPTED')", (campaign_id, provider, operation, agent_id, stamp))
        return int(row.lastrowid)


def after_call(audit_id: int, result: str, *, input_tokens: int | None = None, output_tokens: int | None = None) -> None:
    with _connect() as conn:
        conn.execute("UPDATE marketing_external_call_audit SET result=?,input_tokens=?,output_tokens=? WHERE id=?",
                     (result[:40], input_tokens, output_tokens, audit_id))
