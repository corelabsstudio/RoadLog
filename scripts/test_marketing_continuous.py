"""No-network start/stop and durable cadence checks."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules import marketing_os, marketing_safety
from modules.marketing_core.job_queue import MarketingJobQueue
from modules.marketing_core.repository import MarketingRepository


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        old_db, old_safety_db = marketing_os.DB, marketing_safety.DB
        old_enabled, old_thread = marketing_safety.enabled, marketing_os.Thread
        old_key = os.environ.get("GEMINI_API_KEY")
        started = []

        class DormantThread:
            def __init__(self, **kwargs):
                started.append(kwargs)
            def start(self):
                pass

        try:
            marketing_os.DB = Path(directory) / "team.db"
            marketing_safety.DB = marketing_os.DB
            marketing_safety.enabled = lambda provider: provider == "gemini"
            marketing_os.Thread = DormantThread
            os.environ["GEMINI_API_KEY"] = "test-not-sent"
            assert marketing_safety.cost_status()["paid_enabled"] == 0
            result = marketing_os.control("start")
            assert result["status"] == "RUNNING"
            assert marketing_safety.cost_status()["paid_enabled"] == 1
            assert len(started) == 1
            assert marketing_os.operations().dashboard()["continuous"]["enabled"] == 1
            repo = MarketingRepository(marketing_os.DB,"roadlog")
            queue = MarketingJobQueue(repo)
            first = queue.recent()[0]
            assert first["status"] == "running"
            marketing_os.run_due(Path(directory))
            assert len(started) == 1
            try:
                marketing_os.control("start")
                raise AssertionError("중복 팀 시작 허용")
            except PermissionError:
                pass
            marketing_os.operations().finish_due(first["run_date"],first["job_key"],"모의 작업 완료")
            queue.finish(first["id"],success=True,result="모의 작업 완료")
            later=datetime.fromisoformat(first["updated_at"])+timedelta(hours=2,minutes=1)
            marketing_os.run_due(Path(directory),later)
            assert len(started) == 2
            queue.enqueue("team_cycle_future",later.date().isoformat(),later+timedelta(hours=4))
            assert marketing_os.control("stop")["status"] == "STOPPED"
            assert marketing_safety.cost_status()["paid_enabled"] == 0
            assert next(j for j in queue.recent() if j["job_key"] == "team_cycle_future")["status"] == "skipped"
            marketing_os.run_due(Path(directory),later+timedelta(hours=3))
            assert len(started) == 2
            assert marketing_os.operations().dashboard()["continuous"]["enabled"] == 0
            try:
                marketing_os.control("start")
                raise AssertionError("이전 작업 완료 전 새 팀 가동 허용")
            except PermissionError:
                pass
        finally:
            marketing_os.DB, marketing_safety.DB = old_db, old_safety_db
            marketing_safety.enabled, marketing_os.Thread = old_enabled, old_thread
            if old_key is None: os.environ.pop("GEMINI_API_KEY", None)
            else: os.environ["GEMINI_API_KEY"] = old_key


if __name__ == "__main__":
    main()
