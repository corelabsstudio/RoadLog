"""Offline cost-control regression. Never opens a paid network connection."""
from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import marketing_safety as safety
from modules.marketing_cost_guard import quote
from modules.marketing_core.job_queue import MarketingJobQueue
from modules.marketing_core.repository import MarketingRepository

BODY = {"contents": [{"parts": [{"text": "ROADLOG 상품 설명"}]}],
        "generationConfig": {"maxOutputTokens": 100}}
MODEL = "gemini-3.8-flash"


def main() -> None:
    old_db, old_hold, old_datetime = safety.DB, safety.RELEASE_HOLD, safety.datetime
    flags = ("MARKETING_EXTERNAL_API_ENABLED", "MARKETING_GEMINI_ENABLED")
    old_flags = {key: os.environ.get(key) for key in flags}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        try:
            safety.RELEASE_HOLD = False
            for key in flags: os.environ[key] = "true"
            def fresh(name: str) -> None:
                safety.DB = Path(folder) / (name + ".db")
                safety.update_cost_settings(paid_enabled=True)
            def call(agent: str = "writer", campaign: int = 0) -> int:
                return safety.before_call("gemini", "test", agent_id=agent, campaign_id=campaign,
                                          model=MODEL, request_body=BODY)
            def done(audit_id: int) -> None:
                safety.record_usage(audit_id, MODEL, {"promptTokenCount": 100,
                                                      "candidatesTokenCount": 50, "thoughtsTokenCount": 10})

            fresh("budget")
            price = quote(MODEL, BODY, datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())["reserved_cost_krw"]
            safety.update_cost_settings(daily_budget_krw=price)
            first = call(); done(first)
            assert safety.cost_status()["reserved_cost_krw"] == price
            assert safety.cost_status()["actual_cost_estimate_krw"] > 0
            try: call()
            except PermissionError: pass
            else: raise AssertionError("budget overrun")
            print("PASS below budget / over-budget blocked / actual usage separate")

            fresh("parallel")
            safety.update_cost_settings(daily_budget_krw=2 * price)
            with safety._connect() as db:
                db.execute("UPDATE marketing_cost_settings SET max_concurrent=10")
            with ThreadPoolExecutor(max_workers=10) as pool:
                futures = [pool.submit(call, f"worker-{n}") for n in range(10)]
                allowed = []
                for future in futures:
                    try: allowed.append(future.result())
                    except PermissionError: pass
            assert len(allowed) == 2 and safety.cost_status()["reserved_cost_krw"] == 2 * price
            for audit_id in allowed: done(audit_id)
            print("PASS ten concurrent attempts / atomic budget")

            fresh("concurrency")
            first_active = call("worker-1")
            second_active = call("worker-2")
            try: call("worker-3")
            except PermissionError: pass
            else: raise AssertionError("concurrent call limit bypassed")
            done(first_active)
            assert call("worker-3") > second_active
            print("PASS maximum two concurrent external calls")

            fresh("retry")
            for _ in range(3):
                audit_id = call(); safety.after_call(audit_id, "HTTP_503")
            assert safety.cost_status()["calls"] == 3
            assert safety.cost_status()["reserved_cost_krw"] == 3 * price
            try: call()
            except PermissionError: pass
            else: raise AssertionError("failure kill missing")
            assert safety.cost_status()["kill_reason"]
            print("PASS retries reserved individually / consecutive failure kill")

            fresh("restart")
            audit_id = call(); done(audit_id)
            assert safety.cost_status()["calls"] == 1
            safety.DB = Path(folder) / "restart.db"  # Simulated new process using the same durable DB.
            assert safety.cost_status()["calls"] == 1
            print("PASS restart persistence")

            fresh("kst")
            today = datetime.now(ZoneInfo("Asia/Seoul")).replace(hour=23, minute=59, second=0, microsecond=0)
            class BeforeMidnight(datetime):
                @classmethod
                def now(cls, tz=None): return today
            class AfterMidnight(datetime):
                @classmethod
                def now(cls, tz=None): return today + timedelta(minutes=2)
            safety.datetime = BeforeMidnight
            audit_id = call(); done(audit_id)
            safety.datetime = AfterMidnight
            assert safety.cost_status()["calls"] == 0
            assert call() > audit_id
            safety.datetime = old_datetime
            print("PASS KST date rollover")

            fresh("malformed")
            audit_id = call()
            try: safety.record_usage(audit_id, MODEL, {"promptTokenCount": "bad"})
            except PermissionError: pass
            else: raise AssertionError("malformed usage passed")
            assert safety.cost_status()["kill_reason"]
            try: call()
            except PermissionError: pass
            else: raise AssertionError("kill bypassed")
            print("PASS malformed usage fails closed / emergency kill")

            fresh("spike")
            audit_id = call()
            try: safety.record_usage(audit_id, MODEL, {"promptTokenCount": 100,
                                                        "candidatesTokenCount": 50_000, "thoughtsTokenCount": 0})
            except PermissionError: pass
            else: raise AssertionError("usage spike passed")
            assert safety.cost_status()["kill_reason"]
            print("PASS usage spike kill")

            fresh("legacy_unknown")
            with safety._connect() as db:
                stamp = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
                db.execute("INSERT INTO marketing_external_call_audit(campaign_id,provider,operation,agent_id,called_at,result) VALUES(0,'gemini','old','old',?,'SUCCESS')", (stamp,))
            try: call()
            except PermissionError: pass
            else: raise AssertionError("unpriced legacy call bypassed")
            print("PASS unpriced same-day legacy calls fail closed")

            fresh("request_limit")
            safety.update_cost_settings(daily_requests=1)
            audit_id = call(); done(audit_id)
            try: call()
            except PermissionError: pass
            else: raise AssertionError("daily call limit bypassed")
            print("PASS daily request limit")

            fresh("agent_limit")
            safety.update_cost_settings(per_agent_requests=1)
            audit_id = call("writer"); done(audit_id)
            try: call("writer")
            except PermissionError: pass
            else: raise AssertionError("agent limit bypassed")
            print("PASS team-member request limit")

            fresh("switches")
            safety.update_cost_settings(paid_enabled=False)
            try: call()
            except PermissionError: pass
            else: raise AssertionError("paid switch bypassed")
            safety.update_cost_settings(paid_enabled=True)
            try: safety.before_call("gemini", "test", model="unknown", request_body=BODY)
            except PermissionError: pass
            else: raise AssertionError("unknown model price bypassed")
            print("PASS paid switch / unknown model fail closed")

            repo = MarketingRepository(Path(folder) / "job.db", "roadlog")
            queue = MarketingJobQueue(repo)
            day = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
            assert queue.enqueue("campaign_daily", day) and not queue.enqueue("campaign_daily", day)
            print("PASS duplicate job idempotency")
        finally:
            safety.DB, safety.RELEASE_HOLD, safety.datetime = old_db, old_hold, old_datetime
            for key, value in old_flags.items():
                if value is None: os.environ.pop(key, None)
                else: os.environ[key] = value


if __name__ == "__main__": main()
