from __future__ import annotations
from datetime import datetime
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
            """)
            db.execute("INSERT OR IGNORE INTO marketing_state(tenant_id,status,updated_at) VALUES(?,?,?)",(self.repo.tenant_id,"STOPPED",now()))
            for aid,name,label in self.agent_defs:
                db.execute("INSERT OR IGNORE INTO marketing_agents(tenant_id,agent_id,name,label,status,last_activity) VALUES(?,?,?,?,?,?)",(self.repo.tenant_id,aid,name,label,"IDLE",now()))

    def dashboard(self) -> dict[str,Any]:
        with self.repo.connect() as db:
            agents=[dict(r) for r in db.execute("SELECT * FROM marketing_agents WHERE tenant_id=? ORDER BY rowid",(self.repo.tenant_id,))]
            activity=[dict(r) for r in db.execute("SELECT * FROM marketing_activity WHERE tenant_id=? ORDER BY id DESC LIMIT 30",(self.repo.tenant_id,))]
            state=db.execute("SELECT status,updated_at FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()
            content=[dict(r) for r in db.execute("SELECT id,product_name,platform,title,status,review_result,created_at FROM marketing_content WHERE tenant_id=? ORDER BY id DESC LIMIT 30",(self.repo.tenant_id,))]
            reports=[dict(r) for r in db.execute("SELECT * FROM marketing_reports WHERE tenant_id=? ORDER BY report_date DESC LIMIT 30",(self.repo.tenant_id,))]
            scheduled=[dict(r) for r in db.execute("SELECT * FROM marketing_scheduled_runs WHERE tenant_id=? ORDER BY run_date DESC,job_key LIMIT 20",(self.repo.tenant_id,))]
        return {"status":dict(state),"agents":agents,"activity":activity,"schedule":self.schedule_defs,"content":content,"reports":reports,"scheduled_runs":scheduled}

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
                cur = db.execute("INSERT OR IGNORE INTO marketing_scheduled_runs(tenant_id,run_date,job_key,status,updated_at) VALUES(?,?,?,?,?)",
                    (self.repo.tenant_id,day,item["job"],"RUNNING",now()))
                if cur.rowcount: claimed.append((day,item["job"]))
        return claimed

    def finish_due(self, day: str, job_key: str, result: str, *, failed: bool = False) -> None:
        stamp = now(); status = "FAILED" if failed else "COMPLETED"
        aid = "content_writer" if job_key == "content" else "marketing_director"
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_scheduled_runs SET status=?,result=?,updated_at=? WHERE tenant_id=? AND run_date=? AND job_key=?",
                (status,result,stamp,self.repo.tenant_id,day,job_key))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                (self.repo.tenant_id,aid,"예약 작업 실패" if failed else "예약 작업 완료",f"{day} {job_key}",result,"ERROR" if failed else "INFO",stamp))
            if failed:
                db.execute("UPDATE marketing_agents SET status='ERROR',current_task=?,progress=0,last_activity=? WHERE tenant_id=? AND agent_id=?",
                    (result,stamp,self.repo.tenant_id,aid))

    def record_kickoff(self, product_result: str) -> None:
        """Record only work the local DEMO bundle actually supports, and name missing integrations."""
        stamp = now()
        outcomes = (
            ("marketing_director", "DONE", "오늘 상품 정본 기반 작업 배정", product_result),
            ("market_researcher", "WAITING_DATA", "상품 정본 점검 · 외부 시장 데이터 미연결", "상품 사실은 확인했습니다. 시장 동향은 조사하지 않았습니다."),
            ("seo_specialist", "WAITING_DATA", "상품명 기반 주제 후보 확인 · 검색 API 미연결", "검색량·순위는 확인하지 않았습니다."),
            ("content_writer", "DONE", "상품 정본 DEMO 초안 생성", product_result),
            ("creative_director", "DONE", "영상 대본·카드뉴스 문안 준비", "내부 DEMO 묶음에 문안을 저장했습니다. 이미지·영상 제작은 하지 않았습니다."),
            ("social_manager", "WAITING_APPROVAL", "채널별 초안 정리 · 외부 게시 차단", "블로그·짧은 영상·카드뉴스 문안만 준비됐습니다. 외부 게시 없음."),
            ("quality_reviewer", "DONE", "상품 사실 검수 결과 저장", "채널별 검수 결과를 콘텐츠에 저장했습니다."),
            ("performance_analyst", "WAITING_DATA", "성과 데이터 연결 대기", "유입·가입·구매 성과 API 미연결. 성과 수치를 만들지 않았습니다."),
        )
        with self.repo.connect() as db:
            for aid, status, task, result in outcomes:
                db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=?,last_activity=? WHERE tenant_id=? AND agent_id=?",
                    (status,task,100 if status == "DONE" else 0,stamp,self.repo.tenant_id,aid))
                db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                    (self.repo.tenant_id,aid,task,"팀 시작 후 내부 DEMO 점검",result,"INFO",stamp))

    def record_report(self, day: str) -> None:
        stamp = now()
        with self.repo.connect() as db:
            counts = dict(db.execute("SELECT COUNT(*) total,COALESCE(SUM(status='PENDING_APPROVAL'),0) pending FROM marketing_content WHERE tenant_id=? AND date(created_at,'+9 hours')=?",(self.repo.tenant_id,day)).fetchone())
            body = (f"# 일일 마케팅 보고서\n\n날짜: {day}\n\n- DEMO 초안: {counts['total']}건\n"
                    f"- 승인 대기: {counts['pending']}건\n- 외부 성과 API: 연결되지 않음\n- 실제 게시: 실행하지 않음\n")
            db.execute("INSERT INTO marketing_reports(tenant_id,report_date,title,body,created_at) VALUES(?,?,?,?,?) ON CONFLICT(tenant_id,report_date) DO UPDATE SET body=excluded.body,created_at=excluded.created_at",
                (self.repo.tenant_id,day,f"{day} 일일 보고서",body,stamp))

    def control(self, action: str) -> dict[str,Any]:
        states={"start":"RUNNING","pause":"PAUSED","stop":"EMERGENCY_STOP"}
        if action not in states: raise ValueError("지원하지 않는 운영 명령입니다.")
        state=states[action]; stamp=now()
        with self.repo.connect() as db:
            current=db.execute("SELECT status FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()
            if current and current["status"] == state:
                return {"ok":True,"status":state}
            db.execute("UPDATE marketing_state SET status=?,updated_at=? WHERE tenant_id=?",(state,stamp,self.repo.tenant_id))
            if action=="start":
                db.execute("UPDATE marketing_agents SET status='WAITING_NEXT_RUN',current_task='기존 작업 기록 유지 · 다음 예약 대기',progress=0,last_activity=? WHERE tenant_id=? AND status='OFFLINE'",(stamp,self.repo.tenant_id))
            if action=="stop": db.execute("UPDATE marketing_agents SET status='OFFLINE',current_task=NULL,progress=0,last_activity=? WHERE tenant_id=?",(stamp,self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",(self.repo.tenant_id,"marketing_director",{"start":"AI 팀을 시작했습니다","pause":"AI 팀을 일시정지했습니다","stop":"긴급 정지를 실행했습니다"}[action],"관리자 요청","외부 게시 차단 유지","WARNING" if action=="stop" else "INFO",stamp))
        return {"ok":True,"status":state}

    def record_bundle(self, bundle_id: int, item_count: int) -> None:
        stamp = now()
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_agents SET status='DONE',current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id='content_writer'", (f"DEMO 묶음 #{bundle_id} · {item_count}건 생성",stamp,self.repo.tenant_id))
            db.execute("UPDATE marketing_agents SET status='DONE',current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id='quality_reviewer'", (f"DEMO 묶음 #{bundle_id} · 사실 검수 결과 저장",stamp,self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id, "content_writer", "원본·채널별 DEMO 초안", "관리자 수동 실행", f"묶음 #{bundle_id} · {item_count}건 생성 · 외부 게시 없음", "INFO", stamp))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",
                       (self.repo.tenant_id, "quality_reviewer", "채널별 사실 검수", "상품 정본과 비교", f"묶음 #{bundle_id} · 검수 결과를 콘텐츠별로 저장", "INFO", stamp))

    def run_job(self, job_key: str) -> dict[str,Any]:
        jobs={"market":("market_researcher","RESEARCHING","시장 흐름 조사","검색 API가 연결되지 않아 확인 대기로 기록했습니다."),"seo":("seo_specialist","RESEARCHING","검색 기회 점검","검색 성과가 연결되지 않아 수치를 만들지 않았습니다."),"content":("content_writer","WRITING","콘텐츠 초안 준비","상품 정본을 사용한 수동 DEMO 생성 대기입니다."),"review":("quality_reviewer","REVIEWING","사실 검수","승인 대기 콘텐츠의 상품 사실을 확인했습니다."),"report":("marketing_director","WORKING","일일 보고서","오늘 운영 기록을 정리했습니다.")}
        if job_key not in jobs: raise ValueError("지원하지 않는 작업입니다.")
        aid,status,task,result=jobs[job_key]; stamp=now()
        with self.repo.connect() as db:
            state=db.execute("SELECT status FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()[0]
            if state!="RUNNING": raise ValueError("먼저 AI 팀을 시작해 주세요.")
            db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id=?",(status,task,stamp,self.repo.tenant_id,aid))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",(self.repo.tenant_id,aid,task,"관리자 수동 실행",result,"INFO",stamp))
            final_status = "WAITING_DATA" if job_key in ("market", "seo") else "DONE"
            db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=?,last_activity=? WHERE tenant_id=? AND agent_id=?",(final_status,result,0 if final_status == "WAITING_DATA" else 100,stamp,self.repo.tenant_id,aid))
        if job_key=="report": self.record_report(datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
        return {"ok":True,"message":result}
