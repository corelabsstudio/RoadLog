"""Generic, tenant-neutral role contracts for an eight-worker marketing team."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentTask:
    agent_id: str
    objective: str
    missing_data: str


TASKS = (
    AgentTask("marketing_director", "상품 사실과 ROADLOG의 실제 유입·상품 열람 집계로 오늘의 목표와 작업 우선순위를 정한다", "외부 시장 데이터 미연결"),
    AgentTask("market_researcher", "ROADLOG 상품별 실제 열람 집계로 내부 관심도를 분석하고 타깃 질문 가설을 만든다. 외부 시장 조사라고 주장하지 않는다", "외부 시장 데이터 미연결"),
    AgentTask("seo_specialist", "상품 사실에 기반한 검색 주제 가설을 만든다. 검색량·순위는 추정하지 않는다", "검색 API 미연결"),
    AgentTask("content_writer", "상품 사실에 맞는 블로그 초안을 작성한다", "실제 검색·성과 데이터 미연결"),
    AgentTask("creative_director", "콘텐츠를 위한 이미지·짧은 영상의 제작 지시안을 만든다. 제작 완료라고 주장하지 않는다", "이미지·영상 생성기 미연결"),
    AgentTask("social_manager", "허용 채널 후보와 게시 전 확인 사항을 정리한다. 게시하지 않는다", "채널 계정·게시 API 미연결"),
    AgentTask("quality_reviewer", "작성된 초안과 상품 정본을 비교하여 사실 위험을 지적한다", "외부 사실 검증 데이터 미연결"),
    AgentTask("performance_analyst", "ROADLOG 사이트의 실제 방문·유입·가입·결제 집계를 분석한다. 제공된 값 이외 숫자는 만들지 않는다", "인스타·검색 노출 성과 API 미연결"),
)
