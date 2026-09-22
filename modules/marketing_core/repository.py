from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any

class MarketingRepository:
    def __init__(self, db_path: Path, tenant_id: str, legacy_tenant_id: str = "default"):
        self.db_path, self.tenant_id = Path(db_path), tenant_id
        if not legacy_tenant_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("legacy_tenant_id contains unsupported characters")
        self.legacy_tenant_id = legacy_tenant_id

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10); conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS marketing_content(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,product_id TEXT NOT NULL,product_name TEXT NOT NULL,platform TEXT NOT NULL,title TEXT NOT NULL,hook TEXT NOT NULL,body TEXT NOT NULL,cta TEXT NOT NULL,image_prompt TEXT NOT NULL,status TEXT NOT NULL,review_result TEXT NOT NULL,review_reasons_json TEXT NOT NULL DEFAULT '[]',fact_snapshot_json TEXT NOT NULL,estimated_cost_krw REAL,mode TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_approvals(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,content_id INTEGER NOT NULL,status TEXT NOT NULL,decision_note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,decided_at TEXT);
        CREATE TABLE IF NOT EXISTS marketing_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,mode TEXT NOT NULL,agent_id TEXT NOT NULL,product_id TEXT,status TEXT NOT NULL,input_tokens INTEGER NOT NULL DEFAULT 0,output_tokens INTEGER NOT NULL DEFAULT 0,estimated_cost_krw REAL,result_summary TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_sync(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,source_path TEXT NOT NULL,source_hash TEXT NOT NULL,product_count INTEGER NOT NULL,warning_count INTEGER NOT NULL,synced_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_bundles(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,product_id TEXT NOT NULL,product_name TEXT NOT NULL,customer_question TEXT NOT NULL,source_file TEXT NOT NULL,source_hash TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_automation(tenant_id TEXT PRIMARY KEY,enabled INTEGER NOT NULL DEFAULT 0);
        """)
        # Concurrent dashboard requests must not observe the same missing column
        # and both attempt ALTER TABLE. Lock before checking the schema.
        try:
            conn.execute("BEGIN IMMEDIATE")
            for table in ("marketing_content", "marketing_approvals", "marketing_runs", "marketing_sync"):
                if "tenant_id" not in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT '{self.legacy_tenant_id}'")
                conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant ON {table}(tenant_id)")
            if "bundle_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(marketing_content)")}:
                conn.execute("ALTER TABLE marketing_content ADD COLUMN bundle_id INTEGER")
            bundle_columns = {r["name"] for r in conn.execute("PRAGMA table_info(marketing_bundles)")}
            if "source_text" not in bundle_columns:
                conn.execute("ALTER TABLE marketing_bundles ADD COLUMN source_text TEXT NOT NULL DEFAULT ''")
            if "focus_result" not in bundle_columns:
                conn.execute("ALTER TABLE marketing_bundles ADD COLUMN focus_result TEXT NOT NULL DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_marketing_bundles_tenant ON marketing_bundles(tenant_id)")
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise
        return conn

    def record_sync(self, meta: dict[str, Any], count: int) -> None:
        with self.connect() as conn:
            last = conn.execute("SELECT source_hash FROM marketing_sync WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (self.tenant_id,)).fetchone()
            if not last or last["source_hash"] != meta["source_hash"]:
                conn.execute("INSERT INTO marketing_sync(tenant_id,source_path,source_hash,product_count,warning_count,synced_at) VALUES(?,?,?,?,?,?)", (self.tenant_id,meta["source_file"],meta["source_hash"],count,len(meta.get("warnings",[])),meta["synced_at"]))

    def usage(self, day: str) -> tuple[int, float]:
        with self.connect() as conn:
            r = conn.execute("SELECT COUNT(*) n,COALESCE(SUM(estimated_cost_krw),0) cost FROM marketing_runs WHERE tenant_id=? AND substr(created_at,1,10)=? AND mode='REAL'", (self.tenant_id,day)).fetchone()
        return int(r["n"]), float(r["cost"])

    def reserve_real_run(self, product_id: str, stamp: str, daily_limit: int, agent_limit: int, cost_limit: float, reservation_krw: float) -> int:
        """Reserve before the external request; a failed request still consumes the allowance."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT COUNT(*) n,COALESCE(SUM(estimated_cost_krw),0) cost FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND substr(created_at,1,10)=?", (self.tenant_id, stamp[:10])).fetchone()
            writer = conn.execute("SELECT COUNT(*) n FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id='content_writer' AND substr(created_at,1,10)=?", (self.tenant_id, stamp[:10])).fetchone()
            if row["n"] >= daily_limit or writer["n"] >= agent_limit or row["cost"] + reservation_krw > cost_limit:
                raise PermissionError("PAUSED_BY_BUDGET: 오늘 AI 요청 또는 예산 예약 한도를 넘었습니다.")
            return int(conn.execute("INSERT INTO marketing_runs(tenant_id,mode,agent_id,product_id,status,estimated_cost_krw,result_summary,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.tenant_id,"REAL","content_writer",product_id,"RUNNING",reservation_krw,"수동 AI 초안 생성 중",stamp)).lastrowid)

    def finish_real_run(self, run_id: int, status: str, summary: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE marketing_runs SET status=?,result_summary=?,input_tokens=?,output_tokens=? WHERE id=? AND tenant_id=? AND mode='REAL'", (status, summary[:120], input_tokens, output_tokens, run_id, self.tenant_id))

    def has_manual_real_success(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id='content_writer' AND status='COMPLETED' AND result_summary='수동 검수 통과' LIMIT 1", (self.tenant_id,)).fetchone()
        return row is not None

    def auto_real_enabled(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT enabled FROM marketing_automation WHERE tenant_id=?", (self.tenant_id,)).fetchone()
        return bool(row and row["enabled"])

    def set_auto_real(self, enabled: bool) -> None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if enabled and not conn.execute("SELECT 1 FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id='content_writer' AND status='COMPLETED' AND result_summary='수동 검수 통과' LIMIT 1", (self.tenant_id,)).fetchone():
                raise PermissionError("먼저 실제 AI 초안 1건을 수동 생성하고 검수를 통과해야 합니다.")
            conn.execute("INSERT INTO marketing_automation(tenant_id,enabled) VALUES(?,?) ON CONFLICT(tenant_id) DO UPDATE SET enabled=excluded.enabled", (self.tenant_id,int(enabled)))

    def group_trials(self, product: dict[str, Any], meta: dict[str, Any], question: str, source_text: str, focus_result: str, trials: list[dict[str, Any]], stamp: str) -> dict[str, Any]:
        with self.connect() as conn:
            bundle_id = int(conn.execute("INSERT INTO marketing_bundles(tenant_id,product_id,product_name,customer_question,source_file,source_hash,status,created_at,source_text,focus_result) VALUES(?,?,?,?,?,?,?,?,?,?)", (self.tenant_id, product["product_id"], product["name"], question, meta["source_file"], meta["source_hash"], "REAL_REVIEWED", stamp, source_text, focus_result)).lastrowid)
            for trial in trials:
                conn.execute("UPDATE marketing_content SET bundle_id=? WHERE id=? AND tenant_id=? AND mode='REAL'", (bundle_id, trial["content_id"], self.tenant_id))
        return {"bundle_id": bundle_id, "items": [{"content_id": t["content_id"], "approval_id": t["approval_id"], "platform": t["draft"]["platform"], "status": t["status"], "review_reasons": t["review"]["reasons"], "draft": t["draft"]} for t in trials]}

    def save_trial(self, product: dict[str, Any], meta: dict[str, Any], draft: dict[str, Any], reasons: list[str], now: str, mode: str = "REAL", reservation_krw: float | None = None) -> tuple[int,int|None]:
        passed = not reasons
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,review_reasons_json,fact_snapshot_json,estimated_cost_krw,mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (self.tenant_id,product["product_id"],product["name"],draft["platform"],draft["title"],draft["hook"],draft["body"],draft["cta"],draft["image_prompt"],"PENDING_APPROVAL" if passed else "REVISION_REQUESTED","상품 정본 및 표현 검수 통과" if passed else "검수 실패",json.dumps(reasons,ensure_ascii=False),json.dumps({**product,"source_file":meta["source_file"],"source_hash":meta["source_hash"]},ensure_ascii=False),reservation_krw,mode,now))
            cid, aid = int(cur.lastrowid), None
            if passed: aid = int(conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", (self.tenant_id,cid,"PENDING",now)).lastrowid)
        return cid, aid

    def approvals(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT a.*,c.product_name,c.platform,c.title,c.body,c.review_result FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id WHERE a.tenant_id=? ORDER BY a.id DESC LIMIT 100", (self.tenant_id,)).fetchall()
        return [dict(r) for r in rows]

    def bundles(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM marketing_bundles WHERE tenant_id=? ORDER BY id DESC LIMIT 30", (self.tenant_id,)).fetchall()
            results = []
            for row in rows:
                item = dict(row)
                item["contents"] = [dict(content) for content in conn.execute(
                    "SELECT id,platform,title,hook,body,cta,status,review_result,review_reasons_json,created_at FROM marketing_content WHERE tenant_id=? AND bundle_id=? ORDER BY id",
                    (self.tenant_id, item["id"])).fetchall()]
                results.append(item)
        return results

    def decide(self, approval_id: int, state: str, note: str, now: str) -> None:
        with self.connect() as conn:
            if not conn.execute("SELECT id FROM marketing_approvals WHERE id=? AND tenant_id=? AND status='PENDING'", (approval_id,self.tenant_id)).fetchone(): raise ValueError("처리할 승인 항목이 없습니다.")
            conn.execute("UPDATE marketing_approvals SET status=?,decision_note=?,decided_at=? WHERE id=? AND tenant_id=?", (state,note,now,approval_id,self.tenant_id))
