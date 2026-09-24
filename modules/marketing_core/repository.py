from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
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
        CREATE TABLE IF NOT EXISTS marketing_instagram_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,approval_id INTEGER NOT NULL,content_id INTEGER NOT NULL,image_url TEXT NOT NULL,status TEXT NOT NULL,media_id TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(tenant_id,approval_id));
        CREATE TABLE IF NOT EXISTS marketing_campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,product_id TEXT NOT NULL,objective TEXT NOT NULL,status TEXT NOT NULL,trigger_type TEXT NOT NULL,decision TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,completed_at TEXT);
        CREATE TABLE IF NOT EXISTS marketing_campaign_events(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,agent_id TEXT NOT NULL,run_id INTEGER,status TEXT NOT NULL,summary TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_learning(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,product_id TEXT NOT NULL,evidence_type TEXT NOT NULL,observation TEXT NOT NULL,recommendation TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_site_profiles(tenant_id TEXT PRIMARY KEY,catalog_hash TEXT NOT NULL,profile_json TEXT NOT NULL,observed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_research_sources(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,title TEXT NOT NULL,url TEXT NOT NULL,summary TEXT NOT NULL,observed_at TEXT NOT NULL,source_type TEXT NOT NULL,query_text TEXT NOT NULL DEFAULT '',provider TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS marketing_provider_diagnostics(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,provider TEXT NOT NULL,test_day TEXT NOT NULL,administrator TEXT NOT NULL,query_text TEXT NOT NULL,status TEXT NOT NULL,request_count INTEGER NOT NULL DEFAULT 0,tested_at TEXT NOT NULL,error_kind TEXT NOT NULL DEFAULT '',UNIQUE(tenant_id,provider,test_day));
        CREATE TABLE IF NOT EXISTS marketing_strategy_decisions(tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,decision_json TEXT NOT NULL,PRIMARY KEY(tenant_id,campaign_id));
        CREATE TABLE IF NOT EXISTS marketing_search_cache(tenant_id TEXT NOT NULL,query_text TEXT NOT NULL,provider TEXT NOT NULL,items_json TEXT NOT NULL,observed_at TEXT NOT NULL,PRIMARY KEY(tenant_id,query_text,provider));
        CREATE TABLE IF NOT EXISTS marketing_search_usage(tenant_id TEXT NOT NULL,day TEXT NOT NULL,used INTEGER NOT NULL,PRIMARY KEY(tenant_id,day));
        CREATE TABLE IF NOT EXISTS marketing_assets(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,content_id INTEGER NOT NULL,kind TEXT NOT NULL,mime TEXT NOT NULL,filename TEXT NOT NULL,bytes INTEGER NOT NULL,sha256 TEXT NOT NULL,origin TEXT NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_publications(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,content_id INTEGER NOT NULL,channel TEXT NOT NULL,status TEXT NOT NULL,tracking_url TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(tenant_id,content_id));
        CREATE TABLE IF NOT EXISTS marketing_revisions(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,content_id INTEGER NOT NULL,previous_content_id INTEGER,revision_no INTEGER NOT NULL,feedback TEXT NOT NULL,outcome TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_scorecards(tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,period_days INTEGER NOT NULL,visits INTEGER,cta_clicks INTEGER,signups INTEGER,purchases INTEGER,revenue_krw INTEGER,observed_at TEXT NOT NULL,PRIMARY KEY(tenant_id,campaign_id));
        CREATE TABLE IF NOT EXISTS marketing_blog_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,publication_id INTEGER NOT NULL UNIQUE,slug TEXT NOT NULL UNIQUE,title TEXT NOT NULL,hook TEXT NOT NULL,body TEXT NOT NULL,cta TEXT NOT NULL,tracking_url TEXT NOT NULL,published_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marketing_attribution_visits(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,visitor_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,publication_id INTEGER NOT NULL,source TEXT NOT NULL,medium TEXT NOT NULL,landing_page TEXT NOT NULL,first_seen_at TEXT NOT NULL,last_seen_at TEXT NOT NULL,view_count INTEGER NOT NULL DEFAULT 1,UNIQUE(tenant_id,visitor_id,campaign_id,publication_id));
        CREATE TABLE IF NOT EXISTS marketing_attribution_signups(tenant_id TEXT NOT NULL,account_key TEXT NOT NULL,visitor_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,publication_id INTEGER NOT NULL,signed_up_at TEXT NOT NULL,PRIMARY KEY(tenant_id,account_key));
        CREATE TABLE IF NOT EXISTS marketing_attribution_purchases(tenant_id TEXT NOT NULL,payment_key TEXT NOT NULL,account_key TEXT NOT NULL,campaign_id INTEGER NOT NULL,publication_id INTEGER NOT NULL,product_id TEXT NOT NULL,kind TEXT NOT NULL,revenue_krw INTEGER NOT NULL,paid_at TEXT NOT NULL,PRIMARY KEY(tenant_id,payment_key));
        CREATE TABLE IF NOT EXISTS marketing_campaign_learning(tenant_id TEXT NOT NULL,campaign_id INTEGER NOT NULL,score_fingerprint TEXT NOT NULL,product_id TEXT NOT NULL,strategy_type TEXT NOT NULL,channel TEXT NOT NULL,evidence_type TEXT NOT NULL,measured_json TEXT NOT NULL,analysis_json TEXT NOT NULL,interpretation TEXT NOT NULL,recommendation TEXT NOT NULL,reason_for_retry TEXT NOT NULL,confidence TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(tenant_id,campaign_id));
        CREATE INDEX IF NOT EXISTS ix_marketing_assets_content ON marketing_assets(tenant_id,content_id);
        CREATE INDEX IF NOT EXISTS ix_marketing_campaigns_product ON marketing_campaigns(tenant_id,product_id,created_at);
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
            if "workflow_state" not in {r["name"] for r in conn.execute("PRAGMA table_info(marketing_content)")}:
                conn.execute("ALTER TABLE marketing_content ADD COLUMN workflow_state TEXT NOT NULL DEFAULT 'DRAFT'")
            if "stage" not in {r["name"] for r in conn.execute("PRAGMA table_info(marketing_campaigns)")}:
                conn.execute("ALTER TABLE marketing_campaigns ADD COLUMN stage TEXT NOT NULL DEFAULT 'IDLE'")
            publication_columns = {r["name"] for r in conn.execute("PRAGMA table_info(marketing_publications)")}
            for name in ("external_content_id", "published_url", "published_at", "publish_error"):
                if name not in publication_columns:
                    conn.execute(f"ALTER TABLE marketing_publications ADD COLUMN {name} TEXT")
            score_columns = {r["name"] for r in conn.execute("PRAGMA table_info(marketing_scorecards)")}
            for name, data_type in (("unique_visitors","INTEGER"),("signup_conversion_rate","REAL"),("purchase_conversion_rate","REAL"),("revenue_per_visitor","REAL")):
                if name not in score_columns:
                    conn.execute(f"ALTER TABLE marketing_scorecards ADD COLUMN {name} {data_type}")
            if "refunded_at" not in {r["name"] for r in conn.execute("PRAGMA table_info(marketing_attribution_purchases)")}:
                conn.execute("ALTER TABLE marketing_attribution_purchases ADD COLUMN refunded_at TEXT")
            bundle_columns = {r["name"] for r in conn.execute("PRAGMA table_info(marketing_bundles)")}
            if "source_text" not in bundle_columns:
                conn.execute("ALTER TABLE marketing_bundles ADD COLUMN source_text TEXT NOT NULL DEFAULT ''")
            if "focus_result" not in bundle_columns:
                conn.execute("ALTER TABLE marketing_bundles ADD COLUMN focus_result TEXT NOT NULL DEFAULT ''")
            research_columns = {r["name"] for r in conn.execute("PRAGMA table_info(marketing_research_sources)")}
            if "query_text" not in research_columns:
                conn.execute("ALTER TABLE marketing_research_sources ADD COLUMN query_text TEXT NOT NULL DEFAULT ''")
            if "provider" not in research_columns:
                conn.execute("ALTER TABLE marketing_research_sources ADD COLUMN provider TEXT NOT NULL DEFAULT ''")
            if "origin" not in research_columns:
                conn.execute("ALTER TABLE marketing_research_sources ADD COLUMN origin TEXT NOT NULL DEFAULT 'CAMPAIGN'")
            campaign_columns = {r["name"] for r in conn.execute("PRAGMA table_info(marketing_campaigns)")}
            if "mode" not in campaign_columns:
                conn.execute("ALTER TABLE marketing_campaigns ADD COLUMN mode TEXT NOT NULL DEFAULT 'PRODUCTION'")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_marketing_bundles_tenant ON marketing_bundles(tenant_id)")
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            raise
        return conn

    def save_site_profile(self, profile: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO marketing_site_profiles(tenant_id,catalog_hash,profile_json,observed_at) VALUES(?,?,?,?) ON CONFLICT(tenant_id) DO UPDATE SET catalog_hash=excluded.catalog_hash,profile_json=excluded.profile_json,observed_at=excluded.observed_at",
                         (self.tenant_id, profile["catalog_hash"], json.dumps(profile, ensure_ascii=False), profile["observed_at"]))

    def site_profile(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT profile_json FROM marketing_site_profiles WHERE tenant_id=?", (self.tenant_id,)).fetchone()
        return json.loads(row["profile_json"]) if row else None

    def save_research_sources(self, campaign_id: int, items: list[dict[str, Any]], *, origin: str = "CAMPAIGN") -> None:
        if origin not in {"CAMPAIGN", "PROVIDER_DIAGNOSTIC"}:
            raise ValueError("지원하지 않는 조사 출처")
        with self.connect() as conn:
            for item in items:
                conn.execute("INSERT INTO marketing_research_sources(tenant_id,campaign_id,title,url,summary,observed_at,source_type,query_text,provider,origin) VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (self.tenant_id,campaign_id,item["title"],item["url"],item["summary"],item["observedAt"],item["sourceType"],item.get("query", ""),item.get("source", ""),origin))

    def save_strategy(self, campaign_id: int, decision: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO marketing_strategy_decisions(tenant_id,campaign_id,decision_json) VALUES(?,?,?)",
                         (self.tenant_id,campaign_id,json.dumps(decision,ensure_ascii=False)))

    def strategy(self, campaign_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT decision_json FROM marketing_strategy_decisions WHERE tenant_id=? AND campaign_id=?",(self.tenant_id,campaign_id)).fetchone()
        return json.loads(row["decision_json"]) if row else None

    def search_with_budget(self, query: str, provider: Any, daily_limit: int = 10, cache_hours: int = 6, campaign_id: int = 0) -> list[dict[str, Any]]:
        """Cache only configured provider results; reserve daily calls before network I/O."""
        now = datetime.now(ZoneInfo("Asia/Seoul"))
        with self.connect() as conn:
            row = conn.execute("SELECT items_json,observed_at FROM marketing_search_cache WHERE tenant_id=? AND query_text=? AND provider=?",
                               (self.tenant_id,query,"Tavily Search")).fetchone()
            if row and now - datetime.fromisoformat(row["observed_at"]) < timedelta(hours=cache_hours):
                return json.loads(row["items_json"])
            conn.execute("BEGIN IMMEDIATE")
            used = conn.execute("SELECT used FROM marketing_search_usage WHERE tenant_id=? AND day=?",(self.tenant_id,now.date().isoformat())).fetchone()
            if used and used["used"] >= daily_limit:
                raise PermissionError("일일 외부 검색 한도 도달")
            conn.execute("INSERT INTO marketing_search_usage(tenant_id,day,used) VALUES(?,?,1) ON CONFLICT(tenant_id,day) DO UPDATE SET used=used+1",
                         (self.tenant_id,now.date().isoformat()))
        items = provider.search(query, max_results=5, campaign_id=campaign_id)
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO marketing_search_cache(tenant_id,query_text,provider,items_json,observed_at) VALUES(?,?,?,?,?)",
                         (self.tenant_id,query,"Tavily Search",json.dumps(items,ensure_ascii=False),now.isoformat(timespec="seconds")))
        return items

    def research_sources(self, campaign_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT title,url,summary,observed_at,source_type,query_text,provider,origin FROM marketing_research_sources WHERE tenant_id=? AND campaign_id=? ORDER BY id", (self.tenant_id,campaign_id)).fetchall()
        return [dict(row) for row in rows]

    def claim_provider_diagnostic(self, provider: str, day: str, administrator: str, query: str, stamp: str) -> int | None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("INSERT OR IGNORE INTO marketing_provider_diagnostics(tenant_id,provider,test_day,administrator,query_text,status,tested_at) VALUES(?,?,?,?,?,'ATTEMPTED',?)",
                               (self.tenant_id,provider,day,administrator,query,stamp))
            return int(row.lastrowid) if row.rowcount else None

    def finish_provider_diagnostic(self, diagnostic_id: int, status: str, request_count: int, error_kind: str = "") -> None:
        with self.connect() as conn:
            conn.execute("UPDATE marketing_provider_diagnostics SET status=?,request_count=?,error_kind=? WHERE tenant_id=? AND id=? AND status='ATTEMPTED'",
                         (status,request_count,error_kind[:60],self.tenant_id,diagnostic_id))

    def provider_diagnostic(self, provider: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT id,provider,test_day,status,query_text,request_count,tested_at,error_kind FROM marketing_provider_diagnostics WHERE tenant_id=? AND provider=? ORDER BY id DESC LIMIT 1",
                               (self.tenant_id,provider)).fetchone()
        return dict(row) if row else None

    def record_sync(self, meta: dict[str, Any], count: int) -> None:
        with self.connect() as conn:
            last = conn.execute("SELECT source_hash FROM marketing_sync WHERE tenant_id=? ORDER BY id DESC LIMIT 1", (self.tenant_id,)).fetchone()
            if not last or last["source_hash"] != meta["source_hash"]:
                conn.execute("INSERT INTO marketing_sync(tenant_id,source_path,source_hash,product_count,warning_count,synced_at) VALUES(?,?,?,?,?,?)", (self.tenant_id,meta["source_file"],meta["source_hash"],count,len(meta.get("warnings",[])),meta["synced_at"]))

    def begin_campaign(self, product_id: str, trigger_type: str, stamp: str) -> int:
        if trigger_type not in {"MANUAL", "DAILY"}:
            raise ValueError("지원하지 않는 캠페인 실행 유형")
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            return int(conn.execute(
                "INSERT INTO marketing_campaigns(tenant_id,product_id,objective,status,trigger_type,decision,reason,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (self.tenant_id,product_id,"검증된 상품 사실에 기반한 콘텐츠 기회 확인","RUNNING",trigger_type,"RESEARCH","내부 상품·성과 점검",stamp)
            ).lastrowid)

    def save_test_campaign(self, product_id: str, plan: dict[str, Any], stamp: str) -> int:
        """TEST is permanently isolated from approvals, publications and learning."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            campaign_id = int(conn.execute(
                "INSERT INTO marketing_campaigns(tenant_id,product_id,objective,status,trigger_type,decision,reason,created_at,completed_at,stage,mode) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (self.tenant_id, product_id, "안전한 실행 계획 검증", "DRY_RUN_COMPLETE", "TEST", "NO_EXTERNAL_CALL",
                 "외부 API·게시 0건", stamp, stamp, "DRY_RUN_COMPLETE", "TEST")).lastrowid)
            conn.execute("INSERT INTO marketing_strategy_decisions(tenant_id,campaign_id,decision_json) VALUES(?,?,?)",
                         (self.tenant_id, campaign_id, json.dumps(plan, ensure_ascii=False)))
            for stage, agent, summary in plan["stages"]:
                conn.execute("INSERT INTO marketing_campaign_events(tenant_id,campaign_id,agent_id,run_id,status,summary,created_at) VALUES(?,?,?,?,?,?,?)",
                             (self.tenant_id,campaign_id,agent,None,stage,summary[:300],stamp))
            return campaign_id

    def campaign_event(self, campaign_id: int, agent_id: str, run_id: int | None, status: str, summary: str, stamp: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO marketing_campaign_events(tenant_id,campaign_id,agent_id,run_id,status,summary,created_at) VALUES(?,?,?,?,?,?,?)",
                         (self.tenant_id,campaign_id,agent_id,run_id,status,summary[:300],stamp))

    def campaign_stage(self, campaign_id: int, stage: str) -> None:
        allowed = {"ANALYZING", "RESEARCHING", "PLANNING", "CREATING", "REVIEWING", "READY_TO_PUBLISH", "WAITING_APPROVAL", "MEASURING", "LEARNING", "BLOCKED", "FAILED"}
        if stage not in allowed: raise ValueError("지원하지 않는 실행 단계")
        with self.connect() as conn:
            conn.execute("UPDATE marketing_campaigns SET stage=? WHERE tenant_id=? AND id=?", (stage,self.tenant_id,campaign_id))

    def record_revision(self, campaign_id: int, content_id: int, previous_content_id: int | None, revision_no: int, feedback: str, outcome: str, stamp: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO marketing_revisions(tenant_id,campaign_id,content_id,previous_content_id,revision_no,feedback,outcome,created_at) VALUES(?,?,?,?,?,?,?,?)",
                         (self.tenant_id,campaign_id,content_id,previous_content_id,revision_no,feedback[:500],outcome,stamp))

    def prepare_publication(self, campaign_id: int, content_id: int, stamp: str, base_url: str = "https://roadlog.co.kr/") -> dict[str, Any]:
        """Only a final, fact-checked text with all channel assets can enter approval."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            campaign = conn.execute("SELECT mode FROM marketing_campaigns WHERE tenant_id=? AND id=?", (self.tenant_id,campaign_id)).fetchone()
            if not campaign or campaign["mode"] != "PRODUCTION":
                raise PermissionError("TEST 캠페인은 게시 준비·승인 대기로 이동할 수 없습니다.")
            row = conn.execute("SELECT * FROM marketing_content WHERE tenant_id=? AND id=? AND mode='REAL'", (self.tenant_id,content_id)).fetchone()
            existing = conn.execute("SELECT id,status,tracking_url FROM marketing_publications WHERE tenant_id=? AND content_id=?", (self.tenant_id,content_id)).fetchone()
            if existing and row and row["workflow_state"] == "READY_TO_PUBLISH": return dict(existing)
            if not row or row["workflow_state"] != "FINAL" or row["review_reasons_json"] != "[]":
                raise ValueError("최종 사실·품질 검수 통과본이 아닙니다.")
            facts = json.loads(row["fact_snapshot_json"])
            if (facts.get("facts_status") != "VERIFIED" or not facts.get("source_file") or
                not all(str(row[key]).strip() for key in ("product_id","platform","title","body","cta"))):
                raise ValueError("상품 정본 또는 게시 필수 데이터가 없습니다.")
            channel = row["platform"]
            if channel not in {"블로그", "인스타그램"}:
                raise ValueError("게시 payload가 정의되지 않은 채널입니다.")
            if channel == "인스타그램":
                asset = conn.execute("SELECT id FROM marketing_assets WHERE tenant_id=? AND content_id=? AND kind='image' AND mime='image/jpeg' AND status='VERIFIED' LIMIT 1", (self.tenant_id,content_id)).fetchone()
                if not asset:
                    conn.execute("UPDATE marketing_content SET workflow_state='BLOCKED_ASSET_REQUIRED' WHERE tenant_id=? AND id=?", (self.tenant_id,content_id))
                    return {"status":"BLOCKED_ASSET_REQUIRED", "reason":"검증된 JPEG 이미지가 필요합니다."}
            cur = conn.execute("INSERT INTO marketing_publications(tenant_id,campaign_id,content_id,channel,status,tracking_url,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                               (self.tenant_id,campaign_id,content_id,channel,"PREPARING","","{}",stamp))
            publication_id = int(cur.lastrowid)
            query = urlencode({"utm_source":"roadlog_blog" if channel == "블로그" else "instagram", "utm_medium":"owned" if channel == "블로그" else "social", "utm_campaign":f"rl-{campaign_id}", "rl_campaign_id":campaign_id, "rl_publication_id":publication_id})
            url = base_url.rstrip("/") + "/?" + query
            payload = {"channel":channel,"title":row["title"],"hook":row["hook"],"body":row["body"],"cta":row["cta"],"tracking_url":url}
            conn.execute("UPDATE marketing_publications SET status='READY_TO_PUBLISH',tracking_url=?,payload_json=? WHERE id=?", (url,json.dumps(payload,ensure_ascii=False),publication_id))
            conn.execute("UPDATE marketing_content SET workflow_state='READY_TO_PUBLISH' WHERE tenant_id=? AND id=?", (self.tenant_id,content_id))
            conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", (self.tenant_id,content_id,"PENDING",stamp))
        return {"id":publication_id,"status":"READY_TO_PUBLISH","tracking_url":url,"payload":payload}

    def publish_blog(self, approval_id: int, stamp: str, origin: str) -> dict[str, Any]:
        """An approved publication and its public blog record commit together."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT p.*,c.title,c.hook,c.body,c.cta,c.workflow_state,a.status approval_status "
                               "FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id "
                               "JOIN marketing_publications p ON p.content_id=c.id AND p.tenant_id=c.tenant_id "
                               "WHERE a.tenant_id=? AND a.id=? AND p.channel='블로그'",(self.tenant_id,approval_id)).fetchone()
            if not row or row["approval_status"] != "APPROVED" or row["workflow_state"] != "READY_TO_PUBLISH" or row["status"] != "READY_TO_PUBLISH":
                raise ValueError("게시 준비와 관리자 승인이 모두 필요합니다.")
            slug = f"ai-{row['id']}"
            url = origin.rstrip("/") + f"/blog/{slug}.html"
            conn.execute("INSERT INTO marketing_blog_posts(tenant_id,publication_id,slug,title,hook,body,cta,tracking_url,published_at) VALUES(?,?,?,?,?,?,?,?,?)",
                         (self.tenant_id,row["id"],slug,row["title"],row["hook"],row["body"],row["cta"],row["tracking_url"],stamp))
            post = conn.execute("SELECT id,slug,published_at FROM marketing_blog_posts WHERE tenant_id=? AND publication_id=?",(self.tenant_id,row["id"])).fetchone()
            if not post: raise RuntimeError("블로그 게시물 저장을 확인하지 못했습니다.")
            conn.execute("UPDATE marketing_publications SET status='PUBLISHED',external_content_id=?,published_url=?,published_at=?,publish_error=NULL WHERE tenant_id=? AND id=?",
                         (str(post["id"]),url,stamp,self.tenant_id,row["id"]))
            conn.execute("UPDATE marketing_content SET workflow_state='PUBLISHED' WHERE tenant_id=? AND id=?",(self.tenant_id,row["content_id"]))
            conn.execute("UPDATE marketing_campaigns SET status='PUBLISHED',stage='MEASURING' WHERE tenant_id=? AND id=?",(self.tenant_id,row["campaign_id"]))
            return {"publication_id":row["id"],"external_content_id":post["id"],"published_url":url,"published_at":stamp,"campaign_id":row["campaign_id"],"status":"PUBLISHED"}

    def approval_publication(self, approval_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT p.id,p.status,p.channel,a.status approval_status FROM marketing_approvals a JOIN marketing_publications p ON p.content_id=a.content_id AND p.tenant_id=a.tenant_id WHERE a.tenant_id=? AND a.id=?",(self.tenant_id,approval_id)).fetchone()
        return dict(row) if row else None

    def fail_blog_publish(self, approval_id: int, reason: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE marketing_publications SET status='PUBLISH_FAILED',publish_error=? WHERE tenant_id=? AND content_id=(SELECT content_id FROM marketing_approvals WHERE tenant_id=? AND id=?) AND status='READY_TO_PUBLISH'",
                         (reason[:200],self.tenant_id,self.tenant_id,approval_id))

    def blog_post(self, slug: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT b.*,p.campaign_id,p.status publication_status FROM marketing_blog_posts b JOIN marketing_publications p ON p.id=b.publication_id AND p.tenant_id=b.tenant_id WHERE b.tenant_id=? AND b.slug=? AND p.status='PUBLISHED'",(self.tenant_id,slug)).fetchone()
        return dict(row) if row else None

    def blog_posts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT b.slug,b.title,b.hook,b.published_at FROM marketing_blog_posts b JOIN marketing_publications p ON p.id=b.publication_id AND p.tenant_id=b.tenant_id WHERE b.tenant_id=? AND p.status='PUBLISHED' ORDER BY b.id DESC LIMIT ?",(self.tenant_id,limit)).fetchall()
        return [dict(row) for row in rows]

    def published_tracking(self, campaign_id: int, publication_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT id,campaign_id,status,tracking_url FROM marketing_publications WHERE tenant_id=? AND id=? AND campaign_id=? AND status='PUBLISHED'",(self.tenant_id,publication_id,campaign_id)).fetchone()
        return dict(row) if row else None

    def record_attributed_visit(self, visitor_id: str, campaign_id: int, publication_id: int, source: str, medium: str, landing_page: str, stamp: str) -> bool:
        if not self.published_tracking(campaign_id,publication_id): return False
        with self.connect() as conn:
            conn.execute("INSERT INTO marketing_attribution_visits(tenant_id,visitor_id,campaign_id,publication_id,source,medium,landing_page,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?) "
                         "ON CONFLICT(tenant_id,visitor_id,campaign_id,publication_id) DO UPDATE SET last_seen_at=excluded.last_seen_at,view_count=view_count+1",
                         (self.tenant_id,visitor_id,campaign_id,publication_id,source[:40],medium[:40],landing_page[:200],stamp,stamp))
        return True

    def record_attributed_signup(self, account_key: str, visitor_id: str, stamp: str, window_days: int = 30) -> bool:
        cut = (datetime.fromisoformat(stamp)-timedelta(days=window_days)).isoformat()
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            visit = conn.execute("SELECT campaign_id,publication_id FROM marketing_attribution_visits WHERE tenant_id=? AND visitor_id=? AND last_seen_at>=? AND last_seen_at<=? ORDER BY last_seen_at DESC,id DESC LIMIT 1",(self.tenant_id,visitor_id,cut,stamp)).fetchone()
            if not visit: return False
            conn.execute("INSERT OR IGNORE INTO marketing_attribution_signups(tenant_id,account_key,visitor_id,campaign_id,publication_id,signed_up_at) VALUES(?,?,?,?,?,?)",(self.tenant_id,account_key,visitor_id,visit["campaign_id"],visit["publication_id"],stamp))
            return True

    def record_attributed_purchase(self, payment_key: str, account_key: str, product_id: str, kind: str, amount: int, stamp: str, window_days: int = 30) -> bool:
        if kind not in {"charge","premium"} or amount <= 0: return False
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            signup = conn.execute("SELECT s.campaign_id,s.publication_id,v.last_seen_at FROM marketing_attribution_signups s JOIN marketing_attribution_visits v ON v.tenant_id=s.tenant_id AND v.visitor_id=s.visitor_id AND v.campaign_id=s.campaign_id AND v.publication_id=s.publication_id WHERE s.tenant_id=? AND s.account_key=?",(self.tenant_id,account_key)).fetchone()
            if not signup or not timedelta(0) <= datetime.fromisoformat(stamp)-datetime.fromisoformat(signup["last_seen_at"]) <= timedelta(days=window_days): return False
            conn.execute("INSERT OR IGNORE INTO marketing_attribution_purchases(tenant_id,payment_key,account_key,campaign_id,publication_id,product_id,kind,revenue_krw,paid_at) VALUES(?,?,?,?,?,?,?,?,?)",(self.tenant_id,payment_key,account_key,signup["campaign_id"],signup["publication_id"],product_id,kind,amount,stamp))
        return True

    def refund_attributed_purchase(self, payment_key: str, stamp: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE marketing_attribution_purchases SET refunded_at=? WHERE tenant_id=? AND payment_key=? AND refunded_at IS NULL",(stamp,self.tenant_id,payment_key))

    def finish_campaign(self, campaign_id: int, status: str, reason: str, stamp: str) -> None:
        if status not in {"AWAITING_APPROVAL", "NEEDS_REVISION", "FAILED", "NO_ACTION"}:
            raise ValueError("지원하지 않는 캠페인 상태")
        with self.connect() as conn:
            conn.execute("UPDATE marketing_campaigns SET status=?,decision=?,reason=?,completed_at=? WHERE tenant_id=? AND id=? AND status='RUNNING'",
                         (status,"CREATE" if status == "AWAITING_APPROVAL" else status,reason[:300],stamp,self.tenant_id,campaign_id))

    def recent_campaigns(self, limit: int = 15, *, production_only: bool = False) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM marketing_campaigns WHERE tenant_id=? AND (?=0 OR mode='PRODUCTION') ORDER BY id DESC LIMIT ?",(self.tenant_id,int(production_only),limit)).fetchall()
            return [{**dict(row),"publications":[dict(item) for item in conn.execute("SELECT id,content_id,channel,status,tracking_url,published_url,published_at,external_content_id FROM marketing_publications WHERE tenant_id=? AND campaign_id=?",(self.tenant_id,row["id"]))],
                     "scorecard":dict(score) if (score := conn.execute("SELECT * FROM marketing_scorecards WHERE tenant_id=? AND campaign_id=?",(self.tenant_id,row["id"])).fetchone()) else None,
                     "revisions":[dict(rev) for rev in conn.execute("SELECT content_id,previous_content_id,revision_no,feedback,outcome,created_at FROM marketing_revisions WHERE tenant_id=? AND campaign_id=? ORDER BY id",(self.tenant_id,row["id"]))],
                     "sources":self.research_sources(row["id"]),"strategy":self.strategy(row["id"]),"events":[dict(event) for event in conn.execute(
                "SELECT agent_id,run_id,status,summary,created_at FROM marketing_campaign_events WHERE tenant_id=? AND campaign_id=? ORDER BY id",
                (self.tenant_id,row["id"]))]} for row in rows]

    def save_scorecard(self, campaign_id: int, metrics: dict[str, Any], stamp: str) -> dict[str, Any]:
        """All-time first-party funnel, never site-wide inferred conversion."""
        with self.connect() as conn:
            campaign = conn.execute("SELECT mode FROM marketing_campaigns WHERE tenant_id=? AND id=?",(self.tenant_id,campaign_id)).fetchone()
            if not campaign or campaign["mode"] != "PRODUCTION":
                raise PermissionError("TEST 캠페인은 성과 집계 대상이 아닙니다.")
            visits_row = conn.execute("SELECT COALESCE(SUM(view_count),0) visits,COUNT(DISTINCT visitor_id) unique_visitors FROM marketing_attribution_visits WHERE tenant_id=? AND campaign_id=?",(self.tenant_id,campaign_id)).fetchone()
            signups = conn.execute("SELECT COUNT(*) n FROM marketing_attribution_signups WHERE tenant_id=? AND campaign_id=?",(self.tenant_id,campaign_id)).fetchone()["n"]
            purchase_row = conn.execute("SELECT COUNT(*) n,COALESCE(SUM(revenue_krw),0) revenue FROM marketing_attribution_purchases WHERE tenant_id=? AND campaign_id=? AND refunded_at IS NULL",(self.tenant_id,campaign_id)).fetchone()
            visits,unique = int(visits_row["visits"]),int(visits_row["unique_visitors"])
            purchases,revenue = int(purchase_row["n"]),int(purchase_row["revenue"])
            signup_rate = signups/unique if unique else None
            purchase_rate = purchases/unique if unique else None
            revenue_per = revenue/unique if unique else None
            conn.execute("INSERT INTO marketing_scorecards(tenant_id,campaign_id,period_days,visits,unique_visitors,signups,purchases,revenue_krw,signup_conversion_rate,purchase_conversion_rate,revenue_per_visitor,observed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?) "
                         "ON CONFLICT(tenant_id,campaign_id) DO UPDATE SET period_days=excluded.period_days,visits=excluded.visits,unique_visitors=excluded.unique_visitors,signups=excluded.signups,purchases=excluded.purchases,revenue_krw=excluded.revenue_krw,signup_conversion_rate=excluded.signup_conversion_rate,purchase_conversion_rate=excluded.purchase_conversion_rate,revenue_per_visitor=excluded.revenue_per_visitor,observed_at=excluded.observed_at",
                         (self.tenant_id,campaign_id,0,visits,unique,signups,purchases,revenue,signup_rate,purchase_rate,revenue_per,stamp))
        return {"campaign_id":campaign_id,"period_days":0,"visits":visits,"unique_visitors":unique,"cta_clicks":None,"signups":signups,"purchases":purchases,"revenue_krw":revenue,"signup_conversion_rate":signup_rate,"purchase_conversion_rate":purchase_rate,"revenue_per_visitor":revenue_per}

    def recent_campaign_product_ids(self, since: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute("SELECT DISTINCT product_id FROM marketing_campaigns WHERE tenant_id=? AND mode='PRODUCTION' AND created_at>=?",(self.tenant_id,since)).fetchall()
        return {row["product_id"] for row in rows}

    def recent_learning(self, limit: int = 5) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT campaign_id,product_id,strategy_type,channel,evidence_type,measured_json,analysis_json,interpretation,recommendation,reason_for_retry,confidence,created_at FROM marketing_campaign_learning WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",(self.tenant_id,limit)).fetchall()
        return [{**dict(row),"measured":json.loads(row["measured_json"]),"analysis":json.loads(row["analysis_json"])} for row in rows]

    def learn_from_scorecard(self, campaign_id: int, stamp: str) -> dict[str, Any] | None:
        import hashlib
        with self.connect() as conn:
            row = conn.execute("SELECT c.product_id,s.visits,s.unique_visitors,s.signups,s.purchases,s.revenue_krw FROM marketing_campaigns c JOIN marketing_scorecards s ON s.tenant_id=c.tenant_id AND s.campaign_id=c.id WHERE c.tenant_id=? AND c.id=? AND c.mode='PRODUCTION' AND EXISTS(SELECT 1 FROM marketing_publications p WHERE p.tenant_id=c.tenant_id AND p.campaign_id=c.id AND p.status='PUBLISHED')",(self.tenant_id,campaign_id)).fetchone()
            if not row: return None
            measured = {key:int(row[key] or 0) for key in ("visits","unique_visitors","signups","purchases","revenue_krw")}
            evidence = json.dumps(measured,sort_keys=True)
            fingerprint = hashlib.sha256(evidence.encode()).hexdigest()
            existing = conn.execute("SELECT score_fingerprint FROM marketing_campaign_learning WHERE tenant_id=? AND campaign_id=?",(self.tenant_id,campaign_id)).fetchone()
            if existing and existing["score_fingerprint"] == fingerprint:
                return None
            if measured["unique_visitors"] < 20:
                interpretation = "표본이 20명 미만이라 성과의 원인을 판단할 수 없습니다."
                recommendation = "동일 전략 반복 또는 중단을 결정하지 말고 추가 유입을 관찰합니다."
                retry = "표본 부족. 다시 시도하려면 목표 고객·제목·채널을 바꾸는 근거를 제시합니다."
            elif measured["signups"] == 0:
                interpretation = "확인된 방문은 있으나 귀속 가입은 없습니다. 원인은 확인되지 않았습니다."
                recommendation = "가입 흐름과 CTA를 점검하고 다른 메시지를 시험합니다."
                retry = "기존 메시지 반복 금지. CTA 또는 대상 가설을 변경한 이유가 필요합니다."
            else:
                interpretation = "방문과 귀속 가입이 관측됐습니다. 인과 효과는 검증되지 않았습니다."
                recommendation = "유입 대비 가입·구매 비율을 비교하며 다른 문안으로 검증합니다."
                retry = "기존 전략과 다른 문안·타깃 가설을 제시해야 합니다."
            published = conn.execute("SELECT channel FROM marketing_publications WHERE tenant_id=? AND campaign_id=? AND status='PUBLISHED' ORDER BY id DESC LIMIT 1",(self.tenant_id,campaign_id)).fetchone()
            channel = published["channel"] if published else "UNKNOWN"
            analysis = {"whatWorked":"가입 발생" if measured["signups"] else "확인되지 않음","whatDidNotWork":"가입 미발생" if measured["unique_visitors"] >= 20 and not measured["signups"] else "확인되지 않음","possibleExplanation":interpretation,"nextRecommendation":recommendation}
            conn.execute("INSERT INTO marketing_campaign_learning(tenant_id,campaign_id,score_fingerprint,product_id,strategy_type,channel,evidence_type,measured_json,analysis_json,interpretation,recommendation,reason_for_retry,confidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,campaign_id) DO UPDATE SET score_fingerprint=excluded.score_fingerprint,measured_json=excluded.measured_json,analysis_json=excluded.analysis_json,interpretation=excluded.interpretation,recommendation=excluded.recommendation,reason_for_retry=excluded.reason_for_retry,confidence=excluded.confidence,created_at=excluded.created_at",(self.tenant_id,campaign_id,fingerprint,row["product_id"],"BLOG_CONTENT",channel,"MEASURED_PLUS_RULE_INFERENCE",evidence,json.dumps(analysis,ensure_ascii=False),interpretation,recommendation,retry,"LOW" if measured["unique_visitors"] < 20 else "MEDIUM",stamp))
            conn.execute("INSERT INTO marketing_campaign_events(tenant_id,campaign_id,agent_id,run_id,status,summary,created_at) VALUES(?,?,?,?,?,?,?)",(self.tenant_id,campaign_id,"performance_analyst",None,"DONE","실측 성과를 집계하고 규칙 기반 해석을 Learning에 저장했습니다.",stamp))
            return {"campaign_id":campaign_id,"measured":measured,"interpretation":interpretation,"recommendation":recommendation,"reason_for_retry":retry}

    def record_learning(self, campaign_id: int, product_id: str, observation: str, stamp: str) -> None:
        with self.connect() as conn:
            conn.execute("INSERT INTO marketing_learning(tenant_id,campaign_id,product_id,evidence_type,observation,recommendation,created_at) VALUES(?,?,?,?,?,?,?)",
                         (self.tenant_id,campaign_id,product_id,"MEASURED",observation[:300],"실제 게시·캠페인 성과 연결 전까지 원인을 단정하지 않습니다.",stamp))

    def usage(self, day: str) -> tuple[int, float]:
        with self.connect() as conn:
            r = conn.execute("SELECT COUNT(*) n,COALESCE(SUM(estimated_cost_krw),0) cost FROM marketing_runs WHERE tenant_id=? AND substr(created_at,1,10)=? AND mode='REAL'", (self.tenant_id,day)).fetchone()
        return int(r["n"]), float(r["cost"])

    def reserve_real_run(self, product_id: str, stamp: str, daily_limit: int, agent_limit: int, cost_limit: float, reservation_krw: float, agent_id: str = "content_writer") -> int:
        """Reserve before the external request; a failed request still consumes the allowance."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT COUNT(*) n,COALESCE(SUM(estimated_cost_krw),0) cost FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND substr(created_at,1,10)=?", (self.tenant_id, stamp[:10])).fetchone()
            agent = conn.execute("SELECT COUNT(*) n FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id=? AND substr(created_at,1,10)=?", (self.tenant_id, agent_id, stamp[:10])).fetchone()
            if row["n"] >= daily_limit or agent["n"] >= agent_limit or row["cost"] + reservation_krw > cost_limit:
                raise PermissionError("PAUSED_BY_BUDGET: 오늘 AI 요청 또는 예산 예약 한도를 넘었습니다.")
            return int(conn.execute("INSERT INTO marketing_runs(tenant_id,mode,agent_id,product_id,status,estimated_cost_krw,result_summary,created_at) VALUES(?,?,?,?,?,?,?,?)", (self.tenant_id,"REAL",agent_id,product_id,"RUNNING",reservation_krw,"AI 역할 작업 중",stamp)).lastrowid)

    def finalize_agent_review(self, content_id: int, passed: bool, stamp: str) -> bool:
        """AI review must finish before any new team draft appears in approvals."""
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT review_reasons_json,status FROM marketing_content WHERE id=? AND tenant_id=?", (content_id, self.tenant_id)).fetchone()
            if not row or row["status"] != "AWAITING_AI_REVIEW":
                raise ValueError("검수 대기 콘텐츠를 찾지 못했습니다.")
            reasons = json.loads(row["review_reasons_json"])
            if not passed: reasons.append("AI 품질 검수 미통과 또는 실행 실패")
            approved = not reasons
            conn.execute("UPDATE marketing_content SET status=?,workflow_state=?,review_result=?,review_reasons_json=? WHERE id=? AND tenant_id=?",
                         ("PENDING_APPROVAL" if approved else "REVISION_REQUESTED", "FINAL" if approved else "NEEDS_REVISION", "상품 정본 및 AI 검수 통과" if approved else "검수 실패", json.dumps(reasons, ensure_ascii=False), content_id, self.tenant_id))
            return approved

    def finish_real_run(self, run_id: int, status: str, summary: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE marketing_runs SET status=?,result_summary=?,input_tokens=?,output_tokens=? WHERE id=? AND tenant_id=? AND mode='REAL'", (status, summary[:120], input_tokens, output_tokens, run_id, self.tenant_id))

    def has_manual_real_success(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id='content_writer' AND status='COMPLETED' AND result_summary='수동 검수 통과' LIMIT 1", (self.tenant_id,)).fetchone()
        return row is not None

    def has_real_provider_response(self) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id='content_writer' AND status='COMPLETED' LIMIT 1", (self.tenant_id,)).fetchone()
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

    def save_trial(self, product: dict[str, Any], meta: dict[str, Any], draft: dict[str, Any], reasons: list[str], now: str, mode: str = "REAL", reservation_krw: float | None = None, defer_approval: bool = False) -> tuple[int,int|None]:
        passed = not reasons
        with self.connect() as conn:
            cur = conn.execute("INSERT INTO marketing_content(tenant_id,product_id,product_name,platform,title,hook,body,cta,image_prompt,status,review_result,review_reasons_json,fact_snapshot_json,estimated_cost_krw,mode,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (self.tenant_id,product["product_id"],product["name"],draft["platform"],draft["title"],draft["hook"],draft["body"],draft["cta"],draft["image_prompt"],"AWAITING_AI_REVIEW" if defer_approval else "PENDING_APPROVAL" if passed else "REVISION_REQUESTED","AI 품질 검수 대기" if defer_approval else "상품 정본 및 표현 검수 통과" if passed else "검수 실패",json.dumps(reasons,ensure_ascii=False),json.dumps({**product,"source_file":meta["source_file"],"source_hash":meta["source_hash"]},ensure_ascii=False),reservation_krw,mode,now))
            cid, aid = int(cur.lastrowid), None
            conn.execute("UPDATE marketing_content SET workflow_state=? WHERE tenant_id=? AND id=?", ("REVIEWING" if defer_approval else "FINAL" if passed else "NEEDS_REVISION",self.tenant_id,cid))
            if passed and not defer_approval: aid = int(conn.execute("INSERT INTO marketing_approvals(tenant_id,content_id,status,created_at) VALUES(?,?,?,?)", (self.tenant_id,cid,"PENDING",now)).lastrowid)
        return cid, aid

    def approvals(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT a.*,c.product_name,c.platform,c.title,c.hook,c.body,c.cta,c.review_result,p.status publication_status,p.published_url FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id LEFT JOIN marketing_publications p ON p.content_id=c.id AND p.tenant_id=c.tenant_id WHERE a.tenant_id=? AND c.mode='REAL' ORDER BY a.id DESC LIMIT 100", (self.tenant_id,)).fetchall()
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
            if not conn.execute("SELECT a.id FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id WHERE a.id=? AND a.tenant_id=? AND a.status='PENDING' AND c.mode='REAL'", (approval_id,self.tenant_id)).fetchone(): raise ValueError("처리할 REAL 승인 항목이 없습니다.")
            conn.execute("UPDATE marketing_approvals SET status=?,decision_note=?,decided_at=? WHERE id=? AND tenant_id=?", (state,note,now,approval_id,self.tenant_id))

    def begin_instagram_post(self, approval_id: int, image_url: str, stamp: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT a.content_id,c.platform,c.mode,c.title,c.hook,c.body,c.cta "
                               "FROM marketing_approvals a JOIN marketing_content c ON c.id=a.content_id AND c.tenant_id=a.tenant_id "
                               "WHERE a.id=? AND a.tenant_id=? AND a.status='APPROVED' AND c.status='PENDING_APPROVAL'",
                               (approval_id,self.tenant_id)).fetchone()
            if not row or row["mode"] != "REAL" or row["platform"] != "인스타그램":
                raise ValueError("게시 가능한 인스타그램 승인 항목이 아닙니다.")
            if conn.execute("SELECT 1 FROM marketing_instagram_posts WHERE tenant_id=? AND approval_id=?", (self.tenant_id,approval_id)).fetchone():
                raise ValueError("이 항목은 이미 게시 요청했습니다. 중복 게시를 차단했습니다.")
            conn.execute("INSERT INTO marketing_instagram_posts(tenant_id,approval_id,content_id,image_url,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                         (self.tenant_id,approval_id,row["content_id"],image_url,"STARTED",stamp,stamp))
            return dict(row)

    def finish_instagram_post(self, approval_id: int, status: str, stamp: str, media_id: str | None = None) -> None:
        if status not in {"PUBLISHED", "UNCERTAIN"}:
            raise ValueError("지원하지 않는 게시 상태")
        with self.connect() as conn:
            conn.execute("UPDATE marketing_instagram_posts SET status=?,media_id=?,updated_at=? WHERE tenant_id=? AND approval_id=? AND status='STARTED'",
                         (status,media_id,stamp,self.tenant_id,approval_id))

    def instagram_posts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT approval_id,status,media_id,image_url,created_at,updated_at FROM marketing_instagram_posts WHERE tenant_id=? ORDER BY id DESC LIMIT 30", (self.tenant_id,)).fetchall()
        return [dict(row) for row in rows]
