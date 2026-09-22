from __future__ import annotations
from datetime import date
from typing import Any
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
        return {"status":dict(state),"agents":agents,"activity":activity,"schedule":self.schedule_defs,"content":content,"reports":reports}

    def control(self, action: str) -> dict[str,Any]:
        states={"start":"RUNNING","pause":"PAUSED","stop":"EMERGENCY_STOP"}
        if action not in states: raise ValueError("지원하지 않는 운영 명령입니다.")
        state=states[action]; stamp=now()
        with self.repo.connect() as db:
            db.execute("UPDATE marketing_state SET status=?,updated_at=? WHERE tenant_id=?",(state,stamp,self.repo.tenant_id))
            if action=="stop": db.execute("UPDATE marketing_agents SET status='OFFLINE',current_task=NULL,progress=0,last_activity=? WHERE tenant_id=?",(stamp,self.repo.tenant_id))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",(self.repo.tenant_id,"marketing_director",{"start":"AI 팀을 시작했습니다","pause":"AI 팀을 일시정지했습니다","stop":"긴급 정지를 실행했습니다"}[action],"관리자 요청","외부 게시 차단 유지","WARNING" if action=="stop" else "INFO",stamp))
        return {"ok":True,"status":state}

    def run_job(self, job_key: str) -> dict[str,Any]:
        jobs={"market":("market_researcher","RESEARCHING","시장 흐름 조사","검색 API가 연결되지 않아 확인 대기로 기록했습니다."),"seo":("seo_specialist","RESEARCHING","검색 기회 점검","검색 성과가 연결되지 않아 수치를 만들지 않았습니다."),"content":("content_writer","WRITING","콘텐츠 초안 준비","상품 정본을 사용한 수동 DEMO 생성 대기입니다."),"review":("quality_reviewer","REVIEWING","사실 검수","승인 대기 콘텐츠의 상품 사실을 확인했습니다."),"report":("marketing_director","WORKING","일일 보고서","오늘 운영 기록을 정리했습니다.")}
        if job_key not in jobs: raise ValueError("지원하지 않는 작업입니다.")
        aid,status,task,result=jobs[job_key]; stamp=now()
        with self.repo.connect() as db:
            state=db.execute("SELECT status FROM marketing_state WHERE tenant_id=?",(self.repo.tenant_id,)).fetchone()[0]
            if state!="RUNNING": raise ValueError("먼저 AI 팀을 시작해 주세요.")
            db.execute("UPDATE marketing_agents SET status=?,current_task=?,progress=100,last_activity=? WHERE tenant_id=? AND agent_id=?",(status,task,stamp,self.repo.tenant_id,aid))
            db.execute("INSERT INTO marketing_activity(tenant_id,agent_id,action,reason,result,level,created_at) VALUES(?,?,?,?,?,?,?)",(self.repo.tenant_id,aid,task,"관리자 수동 실행",result,"INFO",stamp))
            db.execute("UPDATE marketing_agents SET status='IDLE',current_task=NULL,progress=0,last_activity=? WHERE tenant_id=? AND agent_id=?",(stamp,self.repo.tenant_id,aid))
            if job_key=="report":
                today=date.today().isoformat(); body=f"# 일일 마케팅 보고서\n\n날짜: {today}\n\n- 외부 성과 API: 연결되지 않음\n- 실제 게시: 실행하지 않음\n- 운영 상태: {state}\n"
                db.execute("INSERT INTO marketing_reports(tenant_id,report_date,title,body,created_at) VALUES(?,?,?,?,?) ON CONFLICT(tenant_id,report_date) DO UPDATE SET body=excluded.body,created_at=excluded.created_at",(self.repo.tenant_id,today,f"{today} 일일 보고서",body,stamp))
        return {"ok":True,"message":result}
