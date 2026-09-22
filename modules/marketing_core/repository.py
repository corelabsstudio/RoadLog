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

    def save_trial(self, product: dict[str, Any], meta: dict[str, Any], draft: dict[str, Any], reasons: list[str], now: str) -> tuple[int,int|None]:
        passed = not reasons
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,review_reasons_json,fact_snapshot_json,estimated_cost_krw,mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (self.tenant_id,product["product_id"],product["name"],draft["platform"],draft["title"],draft["hook"],draft["body"],draft["cta"],draft["image_prompt"],"PENDING_APPROVAL" if passed else "REVISION_REQUESTED","상품 정본 및 표현 검수 통과" if passed else "검수 실패",json.dumps(reasons,ensure_ascii=False),json.dumps({**product,"source_file":meta["source_file"],"source_hash":meta["source_hash"]},ensure_ascii=False),None,"DEMO",now))
            cid, aid = int(cur.lastrowid), None
            if passed: aid = int(conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", (self.tenant_id,cid,"PENDING",now)).lastrowid)
            conn.execute("INSERT INTO marketing_runs(tenant_id,mode,agent_id,product_id,status,result_summary,created_at) VALUES(?,?,?,?,?,?,?)", (self.tenant_id,"DEMO","content_writer",product["product_id"],"COMPLETED","검수 통과" if passed else "수정 대기",now))
        return cid, aid

    def approvals(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT a.*,c.product_name,c.platform,c.title,c.body,c.review_result FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id WHERE a.tenant_id=? ORDER BY a.id DESC LIMIT 100", (self.tenant_id,)).fetchall()
        return [dict(r) for r in rows]

    def save_bundle(self, product: dict[str, Any], meta: dict[str, Any], question: str, source_text: str, focus_result: str,
                    drafts: list[tuple[dict[str, Any], list[str]]], stamp: str) -> dict[str, Any]:
        with self.connect() as conn:
            bundle_id = int(conn.execute(
                "INSERT INTO marketing_bundles(tenant_id,product_id,product_name,customer_question,source_file,source_hash,status,created_at,source_text,focus_result) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (self.tenant_id, product["product_id"], product["name"], question, meta["source_file"], meta["source_hash"], "DEMO_REVIEWED", stamp, source_text, focus_result),
            ).lastrowid)
            results = []
            for index, (draft, reasons) in enumerate(drafts):
                passed = not reasons
                status = "SOURCE" if index == 0 else ("PENDING_APPROVAL" if passed else "REVISION_REQUESTED")
                cid = int(conn.execute(
                    "INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,review_reasons_json,fact_snapshot_json,estimated_cost_krw,mode,created_at,bundle_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (self.tenant_id, product["product_id"], product["name"], draft["platform"], draft["title"], draft["hook"], draft["body"], draft["cta"], draft["image_prompt"], status,
                     "상품 정본 및 표현 검수 통과" if passed else "검수 실패", json.dumps(reasons, ensure_ascii=False),
                     json.dumps({**product, "source_file": meta["source_file"], "source_hash": meta["source_hash"]}, ensure_ascii=False), None, "DEMO", stamp, bundle_id),
                ).lastrowid)
                aid = None
                if index and passed:
                    aid = int(conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", (self.tenant_id, cid, "PENDING", stamp)).lastrowid)
                results.append({"content_id": cid, "approval_id": aid, "platform": draft["platform"], "status": status, "review_reasons": reasons, "draft": draft})
        return {"bundle_id": bundle_id, "items": results}

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
