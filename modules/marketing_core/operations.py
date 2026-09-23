from __future__ import annotations
from datetime import datetime, timedelta
import json
from typing import Any
from zoneinfo import ZoneInfo
from .repository import MarketingRepository
from .service import now

class TeamOperations:
    def __init__(self, repository: MarketingRepository, agents: list[tuple[str,str,str]], schedule: list[dict[str,str]]):
        self.repo, self.agent_defs, self.schedule_defs = repository, agents, schedule
        self._migrate()

    def _migrate(self) -> None:
        with self.repo.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS marketing_agents(tenant_id TEXT NOT NULL,agent_id TEXT NOT NULL,name TEXT NOT NULL,label TEXT NOT NULL,status TEXT NOT NULL,current_task TEXT,progress INTEGER NOT NULL DEFAULT 0,last_activity TEXT NOT NULL,PRIMARY KEY(tenant_id,agent_id));
            CREATE TABLE IF NOT EXISTS marketing_activity(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,agent_id TEXT,action TEXT NOT NULL,reason TEXT,result TEXT,level TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS marketing_state(tenant_id TEXT PRIMARY KEY,status TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS marketing_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,report_date TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(tenant_id,report_date));
            CREATE TABLE IF NOT EXISTS marketing_scheduled_runs(tenant_id TEXT NOT NULL,run_date TEXT NOT NULL,job_key TEXT NOT NULL,status TEXT NOT NULL,result TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL,PRIMARY KEY(tenant_id,run_date,job_key));
            CREATE TABLE IF NOT EXISTS marketing_agent_outputs(id INTEGER PRIMARY KEY AUTOINCREMENT,tenant_id TEXT NOT NULL,agent_id TEXT NOT NULL,run_id INTEGER NOT NULL,product_id TEXT NOT NULL,status TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL);
            """)
            db.execute("INSERT OR IGNORE INTO marketing_state(tenant_id,status,updated_at) VALUES(?,?,?)",(self.repo.tenant_id,"STOPPED",now()))
            for aid,name,label in self.agent_defs:
                db.execute("INSERT OR IGNORE INTO marketing_agents(tenant_id,agent_id,name,label,status,last_activity) VALUES(?,?,?,?,?,?)",(self.repo.tenant_id,aid,name,label,"IDLE",now()))
            db.execute("UPDATE marketing_agents SET status='WAITING_AI',current_task='실제 AI 생성 검증 대기',progress=0 WHERE tenant_id=? AND current_task LIKE '%DEMO%'", (self.repo.tenant_id,))
            db.execute("UPDATE marketing_agents SET status='WAITING_CONTENT',current_task='실제 AI 초안 대기',progress=0 WHERE tenant_id=? AND current_task IN ('영상 대본·카드뉴스 문안 준비','채널별 초안 정리 · 외부 게시 차단','상품 사실 검수 결과 저장')", (self.repo.tenant_id,))
            db.execute("UPDATE marketing_agents SET status='WAITING_AI',current_task='실제 AI 작업 계획 대기',progress=0 WHERE tenant_id=? AND current_task='오늘 상품 정본 기반 작업 배정'", (self.repo.tenant_id,))

    def dashboard(self) -> dict[str,Any]:
        with self.repo.connect() as db:
            agents=[dict(r) for r in db.execute("SELECT * FROM marketing_agents WHERE tenant_id=? ORDER BY rowid",(self.repo.tenant_id,))]
            activity=[dict(r) for r in db.execute("SELECT * FROM marketing_activity WHERE tenant_id=? ORDER BY id DESC LIMIT 30",(self.repo.tenant_id,))]
            state=db.execute("SELECT status,updated_at FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()
            content=[dict(r) for r in db.execute("SELECT id,product_name,platform,title,status,review_result,created_at FROM marketing_content WHERE tenant_id=? ORDER BY id DESC LIMIT 30",(self.repo.tenant_id,))]
            reports=[dict(r) for r in db.execute("SELECT * FROM marketing_reports WHERE tenant_id=? ORDER BY report_date DESC LIMIT 30",(self.repo.tenant_id,))]
            scheduled=[dict(r) for r in db.execute("SELECT * FROM marketing_scheduled_runs WHERE tenant_id=? ORDER BY run_date DESC,job_key LIMIT 20",(self.repo.tenant_id,))]
            outputs=[dict(r) for r in db.execute("SELECT o.*,r.input_tokens,r.output_tokens,r.estimated_cost_krw FROM marketing_agent_outputs o LEFT JOIN marketing_runs r ON r.id=o.run_id AND r.tenant_id=o.tenant_id WHERE o.tenant_id=? ORDER BY o.id DESC LIMIT 30",(self.repo.tenant_id,))]
        return {"status":dict(state),"agents":agents,"activity":activity,"schedule":self.schedule_defs,"content":content,"reports":reports,"scheduled_runs":scheduled,"agent_outputs":outputs}

    def record_agent_output(self, agent_id: str, run_id: int, product_id: str, status: str, result: dict[str, Any]) -> None:
        stamp = now()
        summary = str(result.get("summary") or "AI 작업 실패")[:300]
        with self.repo.connect() as db:
            db.execute("INSERT INTO marketing_agent_outputs(tenant_id,agent_id,run_id,product_id,status,result_json,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id,agent_id,run_id,product_id,status,json.dumps(result,ensure_ascii=False),stamp))
            db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=?,last_activity=? WHERE tenant_id=? AND agent_id=?",
                       (status,summary,100 if status == "DONE" else 0,stamp,self.repo.tenant_id,agent_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id,agent_id,"독립 AI 작업 완료" if status == "DONE" else "독립 AI 작업 실패",product_id,summary,"INFO" if status == "DONE" else "ERROR",stamp))

    def mark_ai_unavailable(self) -> None:
        stamp = now()
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_agents SET status='WAITING_AI',current_task='Gemini API 키 미연결 · 유료 요청 없음',progress=0,last_activity=? WHERE tenant_id=?",
                       (stamp,self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id,None,"8명 AI 작업 대기","Gemini API 키 미연결","유료 API 요청 없음", "WARNING",stamp))

    def claim_due(self, when: datetime | None = None) -> list[tuple[str,str]]:
        local = (when or datetime.now(ZoneInfo("Asia/Seoul"))).astimezone(ZoneInfo("Asia/Seoul"))
        day, clock = local.date().isoformat(), local.strftime("%H:%M")
        claimed = []
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = db.execute("SELECT status FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()
            if not state or state["status"] != "RUNNING": return []
            for item in self.schedule_defs:
                if not item.get("automatic") or clock < item["time"]: continue
                if item["job"] == "content":
                    enabled = db.execute("SELECT enabled FROM marketing_automation WHERE tenant_id=?", (self.repo.tenant_id,)).fetchone()
                    success = db.execute("SELECT 1 FROM marketing_runs WHERE tenant_id=? AND mode='REAL' AND agent_id='content_writer' AND status='COMPLETED' AND result_summary='수동 검수 통과' LIMIT 1", (self.repo.tenant_id,)).fetchone()
                    if not enabled or not enabled["enabled"] or not success: continue
                cur = db.execute("INSERT OR IGNORE INTO marketing_scheduled_runs(tenant_id,run_date,job_key,status,updated_at) VALUES(?,?,?,?,?)",
                    (self.repo.tenant_id,day,item["job"],"RUNNING",now()))
                if cur.rowcount: claimed.append((day,item["job"]))
        return claimed

    def claim_start_content(self, day: str) -> bool:
        """At most one paid start-triggered draft per KST day, even across workers."""
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM marketing_state WHERE tenant_id=?", (self.repo.tenant_id,)).fetchone()
            if not row or row["status"] != "RUNNING": return False
            cur = db.execute("INSERT OR IGNORE INTO marketing_scheduled_runs(tenant_id,run_date,job_key,status,updated_at) VALUES(?,?,?,?,?)",
                (self.repo.tenant_id, day, "start_content", "RUNNING", now()))
            return bool(cur.rowcount)

    def claim_team_start(self, day: str) -> bool:
        """Exactly one eight-agent batch per KST day across web workers."""
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status FROM marketing_state WHERE tenant_id=?", (self.repo.tenant_id,)).fetchone()
            if not row or row["status"] != "RUNNING": return False
            previous = db.execute("SELECT status,updated_at FROM marketing_scheduled_runs WHERE tenant_id=? AND run_date=? AND job_key='team_8'",
                                  (self.repo.tenant_id,day)).fetchone()
            if previous:
                if previous["status"] != "RUNNING": return False
                try:
                    stale = datetime.fromisoformat(previous["updated_at"]) < datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(minutes=10)
                except ValueError:
                    stale = False
                if not stale: return False
                db.execute("UPDATE marketing_scheduled_runs SET status='FAILED',result='작업자 재시작으로 중단; 관리자 재실행',updated_at=? WHERE tenant_id=? AND run_date=? AND job_key='team_8'",
                           (now(),self.repo.tenant_id,day))
                # A killed worker must not leave its unfinished draft approvable.
                db.execute("UPDATE marketing_content SET status='REVISION_REQUESTED',review_result='AI 검수 작업 중단' WHERE tenant_id=? AND status='AWAITING_AI_REVIEW'",
                           (self.repo.tenant_id,))
                db.execute("UPDATE marketing_scheduled_runs SET status='RUNNING',result='',updated_at=? WHERE tenant_id=? AND run_date=? AND job_key='team_8'",
                           (now(),self.repo.tenant_id,day))
                return True
            cur = db.execute("INSERT OR IGNORE INTO marketing_scheduled_runs(tenant_id,run_date,job_key,status,updated_at) VALUES(?,?,?,?,?)",
                             (self.repo.tenant_id,day,"team_8","RUNNING",now()))
            return bool(cur.rowcount)

    def finish_due(self, day: str, job_key: str, result: str, *, failed: bool = False) -> None:
        stamp = now(); status = "FAILED" if failed else "COMPLETED"
        aid = "content_writer" if job_key == "content" else "team_8" if job_key == "team_8" else "marketing_director"
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_scheduled_runs SET status=?,result=?,updated_at=? WHERE tenant_id=? AND run_date=? AND job_key=?",
                (status,result,stamp,self.repo.tenant_id,day,job_key))
            action = ("팀 시작 작업 실패" if failed else "팀 시작 작업 완료") if job_key == "start_content" else ("예약 작업 실패" if failed else "예약 작업 완료")
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                (self.repo.tenant_id,aid,action,f"{day} {job_key}",result,"ERROR" if failed else "INFO",stamp))
            if failed:
                db.execute("UPDATE marketing_agents SET status='ERROR',current_task=?,progress=0,last_activity=? WHERE tenant_id=? AND agent_id=?",
                    (result,stamp,self.repo.tenant_id,aid))

    def record_kickoff(self, product_result: str, ai_ready: bool) -> None:
        """Record verified catalog checks; never claim an AI draft was produced here."""
        stamp = now()
        outcomes = (
            ("marketing_director", "DONE", "오늘 상품 정본 점검", product_result),
            ("market_researcher", "WAITING_DATA", "상품 정본 점검 · 외부 시장 데이터 미연결", "상품 사실은 확인했습니다. 시장 동향은 조사하지 않았습니다."),
            ("seo_specialist", "WAITING_DATA", "상품명 기반 주제 후보 확인 · 검색 API 미연결", "검색량·순위는 확인하지 않았습니다."),
            ("content_writer", "WORKING" if ai_ready else "WAITING_AI", "상품 정본 기반 AI 초안 생성 중" if ai_ready else "AI 연결 대기", "AI 초안 생성 결과는 잠시 뒤 기록됩니다." if ai_ready else "AI 키가 없어 초안을 생성하지 않았습니다."),
            ("creative_director", "WAITING_CONTENT", "영상 대본·카드뉴스 실제 초안 대기", "이미지·영상 제작은 연결되지 않았습니다."),
            ("social_manager", "WAITING_CONTENT", "실제 초안 대기 · 외부 게시 차단", "외부 게시는 실행하지 않았습니다."),
            ("quality_reviewer", "WAITING_CONTENT", "실제 초안의 사실 검수 대기", "검수할 새 AI 콘텐츠가 없습니다."),
            ("performance_analyst", "WAITING_DATA", "성과 데이터 연결 대기", "유입·가입·구매 성과 API 미연결. 성과 수치를 만들지 않았습니다."),
        )
        with self.repo.connect() as db:
            for aid, status, task, result in outcomes:
                db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=?,last_activity=? WHERE tenant_id=? AND agent_id=?",
                    (status,task,100 if status == "DONE" else 0,stamp,self.repo.tenant_id,aid))
                db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                    (self.repo.tenant_id,aid,task,"팀 시작 후 정본 점검",result,"INFO",stamp))

    def record_real_content(self, content_id: int, passed: bool, product_name: str) -> None:
        stamp = now()
        with self.repo.connect() as db:
            for aid, state, task in (
                ("content_writer", "DONE", f"실제 AI 초안 #{content_id} 생성 · {product_name}"),
                ("quality_reviewer", "DONE", "실제 AI 초안 정본 검수 " + ("통과" if passed else "차단")),
                ("social_manager", "WAITING_APPROVAL" if passed else "WAITING_CONTENT", "승인 대기 · 외부 게시 차단" if passed else "검수 통과 초안 대기"),
            ):
                db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=?,last_activity=? WHERE tenant_id=? AND agent_id=?", (state,task,100 if state == "DONE" else 0,stamp,self.repo.tenant_id,aid))
                db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)", (self.repo.tenant_id,aid,task,"실제 Gemini 생성·정본 검수",f"콘텐츠 #{content_id} · 외부 게시 없음","INFO",stamp))

    def record_content_skipped(self, reason: str) -> None:
        stamp = now()
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_agents SET status='WAITING_AI',current_task=?,progress=0,last_activity=? WHERE tenant_id=? AND agent_id='content_writer'", (reason, stamp, self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                (self.repo.tenant_id, "content_writer", "AI 초안 생성 건너뜀", "팀 즉시 실행", reason, "INFO", stamp))

    def record_report(self, day: str) -> None:
        stamp = now()
        with self.repo.connect() as db:
            counts = dict(db.execute("SELECT COUNT(*) total,COALESCE(SUM(status='PENDING_APPROVAL'),0) pending FROM marketing_content WHERE tenant_id=? AND mode='REAL' AND substr(created_at,1,10)=?",(self.repo.tenant_id,day)).fetchone())
            body = (f"# 일일 마케팅 보고서\n\n날짜: {day}\n\n- 실제 AI 초안: {counts['total']}건\n"
                    f"- 승인 대기: {counts['pending']}건\n- 외부 성과 API: 연결되지 않음\n- 실제 게시: 실행하지 않음\n")
            db.execute("INSERT INTO marketing_reports(tenant_id,report_date,title,body,created_at) VALUES(?,?,?,?,?) ON CONFLICT(tenant_id,report_date) DO UPDATE SET body=excluded.body,created_at=excluded.created_at",
                (self.repo.tenant_id,day,f"{day} 일일 보고서",body,stamp))

    def control(self, action: str) -> dict[str,Any]:
        states={"start":"RUNNING","pause":"PAUSED","stop":"EMERGENCY_STOP"}
        if action not in states: raise ValueError("지원하지 않는 운영 명령입니다.")
        state=states[action]; stamp=now()
        with self.repo.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current=db.execute("SELECT status FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()
            if current and current["status"] == state:
                return {"ok":True,"status":state,"changed":False}
            db.execute("UPDATE marketing_state SET status=?,updated_at=? WHERE tenant_id=?",(state,stamp,self.repo.tenant_id))
            if action=="start":
                db.execute("UPDATE marketing_agents SET status='WAITING_NEXT_RUN',current_task='기존 작업 기록 유지 · 다음 예약 대기',progress=0,last_activity=? WHERE tenant_id=? AND status='OFFLINE'",(stamp,self.repo.tenant_id))
            if action=="stop": db.execute("UPDATE marketing_agents SET status='OFFLINE',current_task=NULL,progress=0,last_activity=? WHERE tenant_id=?",(stamp,self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",(self.repo.tenant_id,"marketing_director",{"start":"AI 팀을 시작했습니다","pause":"AI 팀을 일시정지했습니다","stop":"긴급 정지를 실행했습니다"}[action],"관리자 요청","외부 게시 차단 유지","WARNING" if action=="stop" else "INFO",stamp))
        return {"ok":True,"status":state,"changed":True}

    def record_bundle(self, bundle_id: int, item_count: int) -> None:
        stamp = now()
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_agents SET status='DONE',current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id='content_writer'", (f"실제 AI 묶음 #{bundle_id} · {item_count}건 생성",stamp,self.repo.tenant_id))
            db.execute("UPDATE marketing_agents SET status='DONE',current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id='quality_reviewer'", (f"실제 AI 묶음 #{bundle_id} · 사실 검수 결과 저장",stamp,self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id, "content_writer", "채널별 실제 AI 초안", "관리자 수동 실행", f"묶음 #{bundle_id} · {item_count}건 생성 · 외부 게시 없음", "INFO", stamp))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id, "quality_reviewer", "채널별 사실 검수", "상품 정본과 비교", f"묶음 #{bundle_id} · 검수 결과를 콘텐츠별로 저장", "INFO", stamp))

    def run_job(self, job_key: str) -> dict[str,Any]:
        jobs={"market":("market_researcher","WAITING_DATA","시장 데이터 연결 대기","시장 데이터 API가 연결되지 않아 조사 결과를 만들지 않았습니다."),"seo":("seo_specialist","WAITING_DATA","검색 데이터 연결 대기","검색 API가 연결되지 않아 검색량·순위를 만들지 않았습니다."),"review":("quality_reviewer","WAITING_CONTENT","실제 초안 사실 검수 대기","새 콘텐츠 생성 시 정본 검수를 실행합니다."),"report":("marketing_director","WORKING","일일 보고서","오늘 운영 기록을 정리했습니다.")}
        if job_key not in jobs: raise ValueError("지원하지 않는 작업입니다.")
        aid,status,task,result=jobs[job_key]; stamp=now()
        with self.repo.connect() as db:
            state=db.execute("SELECT status FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()[0]
            if state!="RUNNING": raise ValueError("먼저 AI 팀을 시작해 주세요.")
            db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id=?",(status,task,stamp,self.repo.tenant_id,aid))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",(self.repo.tenant_id,aid,task,"관리자 수동 실행",result,"INFO",stamp))
            final_status = "DONE" if job_key == "report" else status
            db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=?,last_activity=? WHERE tenant_id=? AND agent_id=?",(final_status,result,100 if final_status == "DONE" else 0,stamp,self.repo.tenant_id,aid))
        if job_key=="report": self.record_report(datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
        return {"ok":True,"message":result}
