"""First-party marketing diagnosis. Never infer product conversion from site totals."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def build_profile(products: list[dict[str, Any]], metrics: dict[str, Any], source_hash: str) -> dict[str, Any]:
    opens = {row["product_id"]: row["opens"] for row in metrics.get("by_product", [])}
    today = metrics.get("today") or {}
    month = metrics.get("month") or {}
    observed = []
    for product in products:
        if product.get("facts_status") != "VERIFIED":
            continue
        pid = product["product_id"]
        observed.append({
            "product_id": pid, "name": product["name"], "price_won": product.get("price_won"),
            "free": product.get("free"), "confirmed_results": product.get("confirmed_results") or [],
            "opens_all_time": opens.get(pid, 0), "visits": None, "purchases": None,
            "conversion_rate": None, "evidence_type": "MEASURED",
            "limitation": "상품별 방문·결제 연결이 없어 상품 전환율을 계산할 수 없음",
        })
    return {
        "schema": "SiteMarketingProfile.v1", "catalog_hash": source_hash,
        "observed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": metrics.get("source", "UNKNOWN"), "period_days": metrics.get("period_days"),
        "site_today": {key: today.get(key) for key in ("uv", "pv", "signups", "charges", "sales")},
        "site_month": {key: month.get(key) for key in ("uv", "pv", "signups", "charges", "sales")},
        "products": observed,
        "limitations": ["상품 열람은 누적값이며 상품 방문·구매 전환율과 같지 않음", "사이트 전체 가입·결제를 특정 상품에 귀속할 수 없음"],
    }


def diagnose(profile: dict[str, Any], recent_ids: set[str]) -> dict[str, Any]:
    products = [p for p in profile["products"] if p.get("confirmed_results")]
    if not products:
        return {"decision": "NO_ACTION", "reason": "검증된 상품 정본이 없습니다.", "product_id": None, "evidence_type": "MEASURED"}
    # Rotation is only a tie breaker; do not present opens as visits or conversion.
    candidates = [p for p in products if p["product_id"] not in recent_ids] or products
    product = min(candidates, key=lambda p: (p["opens_all_time"], p["product_id"]))
    uv = profile["site_month"].get("uv")
    signups = profile["site_month"].get("signups")
    if uv is None or signups is None:
        objective = "CUSTOMER_EDUCATION"
        reason = "사이트 유입·가입 측정값이 없어 전환/유입 우선순위를 단정할 수 없습니다."
    elif uv >= 30 and signups == 0:
        objective = "PRODUCT_PAGE_IMPROVEMENT"
        reason = f"이번 달 사이트 전체 방문 {uv}건, 가입 0건입니다. 유입 확대보다 가입 동선 점검이 우선입니다. 상품별 전환은 미측정입니다."
    elif uv < 30:
        objective = "BRAND_AWARENESS"
        reason = f"이번 달 사이트 전체 방문 {uv}건으로 표본이 적습니다. 상품별 전환은 미측정이며 유입 가설을 검증해야 합니다."
    else:
        objective = "CUSTOMER_EDUCATION"
        reason = f"이번 달 사이트 전체 방문 {uv}건·가입 {signups}건입니다. 상품별 전환이 없어 우선 고객 질문을 검증해야 합니다."
    candidates = [
        {"channel": "사이트 블로그", "goal": "고객 질문에 답하고 검색 유입 가설 검증", "kpi": "UTM 방문·가입", "evidence_type": "AI_INFERENCE", "risk": "검색량·게시 성과가 아직 연결되지 않음", "ready": False},
        {"channel": "상품 상세페이지", "goal": "가입·구매 동선 점검", "kpi": "사이트 가입·결제", "evidence_type": "AI_INFERENCE", "risk": "상품별 전환율을 아직 측정할 수 없음", "ready": False},
        {"channel": "Instagram", "goal": "상품 인지도 확대", "kpi": "게시물별 방문", "evidence_type": "AI_INFERENCE", "risk": "이미지 자산·Meta 계정 연결이 필요", "ready": False},
    ]
    selected = "상품 상세페이지" if objective == "PRODUCT_PAGE_IMPROVEMENT" else "사이트 블로그"
    return {"decision": "RESEARCH", "objective": objective, "product_id": product["product_id"],
            "product_name": product["name"], "reason": reason, "evidence_type": "MEASURED",
            "product_opens_all_time": product["opens_all_time"], "candidates": candidates,
            "selected_channel": selected, "selection_reason": "실측 진단 방향과 맞는 후보. 채널 성과·ROI는 검증 전"}
