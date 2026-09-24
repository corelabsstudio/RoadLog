"""Durable, tenant-scoped queue for scheduled marketing work.

An uncertain AI/API attempt is never replayed automatically. Only work which
failed before any external attempt may enter the bounded retry path.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .repository import MarketingRepository

KST = ZoneInfo("Asia/Seoul")


class MarketingJobQueue:
    def __init__(self, repository: MarketingRepository):
        self.repo = repository
        with self.repo.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS marketing_job_queue(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                job_key TEXT NOT NULL,
                run_date TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                run_after TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL,
                UNIQUE(tenant_id,idempotency_key)
            )""")

    def enqueue(self, job_key: str, day: str, when: datetime | None = None) -> bool:
        stamp = (when or datetime.now(KST)).isoformat(timespec="seconds")
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("INSERT OR IGNORE INTO marketing_job_queue(tenant_id,idempotency_key,job_key,run_date,status,run_after,updated_at) VALUES(?,?,?,?,?,?,?)",
                             (self.repo.tenant_id, f"{job_key}:{day}", job_key, day, "queued", stamp, stamp))
            return bool(row.rowcount)

    def exists(self, job_key: str, day: str) -> bool:
        with self.repo.connect() as db:
            return db.execute("SELECT 1 FROM marketing_job_queue WHERE tenant_id=? AND idempotency_key=?", (self.repo.tenant_id, f"{job_key}:{day}")).fetchone() is not None

    def recover_stale(self, when: datetime | None = None) -> int:
        """Do not replay a killed worker: the external billing outcome is unknown."""
        now = when or datetime.now(KST)
        cutoff = (now - timedelta(minutes=20)).isoformat(timespec="seconds")
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute("UPDATE marketing_job_queue SET status='waiting_approval',result='작업자 중단 · 외부 API 결과 확인 후 수동 판단 필요',updated_at=? WHERE tenant_id=? AND status='running' AND updated_at<?",
                                (now.isoformat(timespec="seconds"), self.repo.tenant_id, cutoff))
            return result.rowcount

    def claim_ready(self, when: datetime | None = None, *, job_prefix: str | None = None) -> dict | None:
        stamp = (when or datetime.now(KST)).isoformat(timespec="seconds")
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM marketing_job_queue WHERE tenant_id=? AND status='queued' AND run_after<=? AND (? IS NULL OR substr(job_key,1,length(?))=?) ORDER BY id LIMIT 1", (self.repo.tenant_id, stamp,job_prefix,job_prefix,job_prefix)).fetchone()
            if not row:
                return None
            db.execute("UPDATE marketing_job_queue SET status='running',attempts=attempts+1,updated_at=? WHERE id=? AND tenant_id=? AND status='queued'", (stamp, row['id'], self.repo.tenant_id))
            return dict(row)

    def cancel_queued(self, *, result: str = '관리자 종료') -> int:
        stamp = datetime.now(KST).isoformat(timespec='seconds')
        with self.repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed = db.execute("UPDATE marketing_job_queue SET status='skipped',result=?,updated_at=? WHERE tenant_id=? AND status='queued' AND job_key LIKE 'team_cycle_%'",(result,stamp,self.repo.tenant_id))
            return changed.rowcount

    def finish(self, job_id: int, *, success: bool, result: str, safe_to_retry: bool = False, when: datetime | None = None) -> str:
        now = when or datetime.now(KST)
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT attempts,max_attempts,status FROM marketing_job_queue WHERE id=? AND tenant_id=?", (job_id, self.repo.tenant_id)).fetchone()
            if not row or row['status'] != 'running':
                raise ValueError('실행 중인 작업이 아닙니다.')
            if success:
                status, next_run = 'completed', now
            elif safe_to_retry and row['attempts'] < row['max_attempts']:
                status, next_run = 'queued', now + timedelta(seconds=60 * 2 ** (row['attempts'] - 1))
            else:
                status, next_run = ('failed' if safe_to_retry else 'waiting_approval'), now
            db.execute("UPDATE marketing_job_queue SET status=?,run_after=?,result=?,updated_at=? WHERE id=? AND tenant_id=?",
                       (status, next_run.isoformat(timespec='seconds'), result[:400], now.isoformat(timespec='seconds'), job_id, self.repo.tenant_id))
            return status

    def recent(self, limit: int = 30) -> list[dict]:
        with self.repo.connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM marketing_job_queue WHERE tenant_id=? ORDER BY id DESC LIMIT ?", (self.repo.tenant_id, limit))]
