"""Evidence-first, deterministic strategy shortlist; never invent market metrics."""
from __future__ import annotations

import re
from typing import Any


def _tokens(value: str) -> set[str]:
    return {part for part in re.findall(r"[가-힣A-Za-z0-9]{2,}", value.lower()) if len(part) >= 2}


def content_gap(product: dict[str, Any], sources: list[dict], existing_titles: list[str]) -> dict:
    topic = product["name"]
    title_tokens = _tokens(topic)
    matching = [title for title in existing_titles if title_tokens and len(title_tokens & _tokens(title)) / len(title_tokens) >= .7]
    if matching:
        status = "DUPLICATE_RISK" if len(matching) > 1 else "UPDATE_OPPORTUNITY" if sources else "EXISTING_CONTENT"
    elif sources:
        status = "NEW_OPPORTUNITY"
    else:
        status = "UNKNOWN"
    return {"status": status, "topic": topic, "existingTitles": matching[:5],
            "basis": "제목 단어 겹침만 확인; 본문 의미·검색량은 미측정"}


def build_strategy(profile: dict, product: dict, sources: list[dict], previous: list[dict],
                   existing_titles: list[str], tools: dict) -> dict:
    stamp = profile.get("observed_at")
    opens = next((p.get("opens_all_time") for p in profile.get("products", []) if p["product_id"] == product["product_id"]), None)
    evidence = [{"type": "MEASURED", "source": profile.get("source", "UNKNOWN"), "value": f"상품 누적 열람 {opens}건 (방문·전환 아님)",
                 "url": None, "observedAt": stamp, "confidence": "HIGH"}]
    for row in sources[:5]:
        evidence.append({"type": "EXTERNAL_SOURCE", "source": row.get("source", "UNKNOWN"),
                         "value": row["title"], "url": row["url"], "observedAt": row["observedAt"], "confidence": "SOURCE_ONLY"})
    for campaign in previous[:3]:
        score = campaign.get("scorecard")
        if not score or campaign.get("product_id") != product["product_id"]:
            continue
        evidence.append({"type": "PAST_CAMPAIGN", "source": f"campaign:{campaign['id']}",
                         "value": f"방문 {score.get('visits')}건 · 가입 {score.get('signups')}건 · 구매 {score.get('purchases')}건",
                         "url": None, "observedAt": score.get("observed_at"), "confidence": "HIGH"})
    gap = content_gap(product, sources, existing_titles)
    evidence.append({"type": "AI_INFERENCE", "source": "제목 기반 중복 규칙", "value": gap["status"],
                     "url": None, "observedAt": stamp, "confidence": "LOW"})
    candidates = []
    specs = [
        ("SEO_CONTENT", "검색 질문에 답하는 블로그", "사이트 블로그", ["contentGeneration", "blogPublishing"], "UTM 방문·귀속 가입"),
        ("FAQ_CONTENT", "고객 질문 해설 블로그", "사이트 블로그", ["contentGeneration", "blogPublishing"], "UTM 방문·귀속 가입"),
        ("PRODUCT_PAGE_OPTIMIZATION", "상품 설명 개선", "상품 상세페이지", ["productPageEditing"], "가입·구매"),
        ("SOCIAL_IMAGE", "이미지 SNS 콘텐츠", "Instagram", ["imageGeneration", "publishing"], "게시물별 방문"),
        ("SHORT_FORM", "짧은 영상", "영상", ["videoGeneration", "publishing"], "영상별 방문"),
    ]
    for strategy, objective, channel, required, kpi in specs:
        executable = (strategy in {"SEO_CONTENT", "FAQ_CONTENT"}
                      and tools.get("contentGeneration", {}).get("status") in {"WORKING", "CONNECTED", "CONFIGURED_UNVERIFIED"}
                      and tools.get("blogPublishing", {}).get("status") == "WORKING")
        if gap["status"] in {"DUPLICATE_RISK", "EXISTING_CONTENT", "UPDATE_OPPORTUNITY"} and strategy in {"SEO_CONTENT", "FAQ_CONTENT"}:
            executable = False
        candidates.append({"strategy": strategy, "objective": objective, "targetProduct": product["product_id"],
                           "targetAudience": "사주 결과 항목이 궁금한 신규 방문자 (가설)", "channel": channel,
                           "requiredTools": required, "evidence": [item["type"] + ":" + item["source"] for item in evidence],
                           "expectedKpi": kpi, "risks": "미래 성과 미보장; 상품별 전환 미측정",
                           "executable": executable, "status": "EXECUTABLE" if executable else "BLOCKED_OPPORTUNITY"})
    selected = next((c for c in candidates if c["executable"]), None)
    reason = ("현재 확보된 근거에서 실행 가능한 블로그 후보를 우선합니다. 효과는 게시 후 실측으로 판단합니다."
              if selected else "중복 위험 또는 도구 미연결로 현재 실행 가능한 후보가 없습니다.")
    return {"selectedStrategy": selected["strategy"] if selected else None, "objective": selected["objective"] if selected else None,
            "targetProduct": product["product_id"], "targetAudience": selected["targetAudience"] if selected else None,
            "channel": selected["channel"] if selected else None, "reason": reason,
            "successMetrics": selected["expectedKpi"] if selected else None,
            "alternativeStrategies": [c["strategy"] for c in candidates if c is not selected],
            "candidates": candidates, "evidence": evidence, "contentGap": gap,
            "externalResearchAvailable": bool(sources), "observedQuestions": [s["title"] for s in sources if "?" in s["title"] or "까" in s["title"]],
            "inferredQuestions": []}
