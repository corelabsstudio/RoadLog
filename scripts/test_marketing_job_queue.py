"""No-network checks for durable marketing orchestration."""
from __future__ import annotations

import tempfile
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.marketing_core.job_queue import MarketingJobQueue
from modules.marketing_core.repository import MarketingRepository
from modules import marketing_os


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        repo = MarketingRepository(Path(directory) / 'marketing.db', 'roadlog')
        queue = MarketingJobQueue(repo)
        now = datetime.now(ZoneInfo('Asia/Seoul'))
        day = now.date().isoformat()
        assert queue.enqueue('campaign_daily', day, now)
        assert not queue.enqueue('campaign_daily', day, now)
        job = queue.claim_ready(now)
        assert job and job['status'] == 'queued'
        assert queue.claim_ready(now) is None
        assert queue.finish(job['id'], success=False, result='preflight failure', safe_to_retry=True, when=now) == 'queued'
        assert queue.claim_ready(now) is None
        retry = queue.claim_ready(now + timedelta(seconds=61))
        assert retry and retry['id'] == job['id']
        assert queue.finish(job['id'], success=False, result='uncertain external attempt', when=now + timedelta(seconds=61)) == 'waiting_approval'
        assert queue.claim_ready(now + timedelta(days=1)) is None
        assert queue.enqueue('campaign_daily', (now + timedelta(days=1)).date().isoformat(), now)
        claimed = queue.claim_ready(now)
        assert claimed
        assert queue.recover_stale(now + timedelta(minutes=21)) == 1
        assert queue.recent()[0]['status'] == 'waiting_approval'
        third_day = (now + timedelta(days=2)).date().isoformat()
        assert queue.enqueue('campaign_daily', third_day, now)
        for attempt, seconds in enumerate((0, 61, 182), start=1):
            retry_job = queue.claim_ready(now + timedelta(seconds=seconds))
            assert retry_job and retry_job['run_date'] == third_day
            state = queue.finish(retry_job['id'], success=False, result='safe preflight failure', safe_to_retry=True,
                                 when=now + timedelta(seconds=seconds))
            assert state == ('failed' if attempt == 3 else 'queued')
        assert queue.claim_ready(now + timedelta(days=3)) is None
        old_db, old_on = marketing_os.DB, marketing_os.marketing_safety.on
        old_enabled, old_thread = marketing_os.marketing_safety.enabled, marketing_os.Thread
        old_safety_db = marketing_os.marketing_safety.DB
        try:
            marketing_os.DB = Path(directory) / 'auto-on.db'
            marketing_os.marketing_safety.DB = Path(directory) / 'safety.db'
            marketing_os.marketing_safety.update_cost_settings(paid_enabled=True)
            marketing_os.marketing_safety.on = lambda name: name == 'MARKETING_AUTO_TEAM_ENABLED'
            marketing_os.marketing_safety.enabled = lambda name: name == 'gemini'
            auto_repo = MarketingRepository(marketing_os.DB, 'roadlog')
            with auto_repo.connect() as db:
                db.execute("INSERT INTO marketing_runs(tenant_id,mode,agent_id,status,result_summary,created_at) VALUES(?,?,?,?,?,?)",
                           ('roadlog', 'REAL', 'content_writer', 'COMPLETED', '수동 검수 통과', now.isoformat()))
            try:
                marketing_os.set_auto_real(True)
                raise AssertionError('폐기된 매일 09시 작업이 켜졌습니다.')
            except ValueError:
                pass
            assert not auto_repo.recent_campaigns()
            launched = []
            class NoBrowserThread:
                def __init__(self, **kwargs):
                    launched.append(kwargs)
                def start(self):
                    pass
            marketing_os.Thread = NoBrowserThread
            due = now.replace(hour=9, minute=1, second=0, microsecond=0)
            marketing_os.run_due(Path(directory), due)
            marketing_os.run_due(Path(directory), due)
            assert len(launched) == 0
            marketing_os.operations().control('emergency')
            try:
                marketing_os.set_auto_real(True)
                raise AssertionError('긴급정지 중 자동 운영이 재개됐습니다.')
            except ValueError:
                pass
        finally:
            marketing_os.DB, marketing_os.marketing_safety.on = old_db, old_on
            marketing_os.marketing_safety.enabled, marketing_os.Thread = old_enabled, old_thread
            marketing_os.marketing_safety.DB = old_safety_db
    print('marketing job queue: idempotency, bounded safe retry, uncertain-call hold, stale recovery OK')


if __name__ == '__main__':
    main()
