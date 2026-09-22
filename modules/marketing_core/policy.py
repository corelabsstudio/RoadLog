from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

PRICE = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*|\d+)\s*원")

@dataclass(frozen=True)
class BrandPolicy:
    brand_names: tuple[str, ...]
    guarantee_pattern: str
    cliche_pattern: str
    discount_pattern: str = r"할인|쿠폰|이벤트|특가|세일"
    blocked_brand_pattern: str = ""

def review_draft(product: dict[str, Any], draft: dict[str, Any], policy: BrandPolicy) -> list[str]:
    full = "\n".join(str(draft.get(k) or "") for k in ("title", "hook", "body", "cta"))
    reasons: list[str] = []
    actual_price = product.get("price_won")
    prices = {int(value.replace(",", "")) for value in PRICE.findall(full)}
    if prices and (actual_price is None or prices != {int(actual_price)}): reasons.append("정본과 다른 가격이 있습니다.")
    if re.search(policy.discount_pattern, full): reasons.append("검증된 할인·쿠폰·이벤트 정보가 없습니다.")
    if re.search(policy.guarantee_pattern, full): reasons.append("효과·성과를 보장하는 표현이 있습니다.")
    if policy.blocked_brand_pattern and re.search(policy.blocked_brand_pattern, full, re.IGNORECASE): reasons.append("허용되지 않은 다른 브랜드 정보가 있습니다.")
    if re.search(policy.cliche_pattern, full): reasons.append("지나치게 AI가 쓴 것 같은 상투적 표현이 있습니다.")
    if not set(draft.get("factual_claims") or []).issubset(set(product.get("confirmed_results") or [])): reasons.append("정본에 없는 결과 항목이 있습니다.")
    if draft.get("source_facts") != product.get("product_id"): reasons.append("상품 정본 출처가 일치하지 않습니다.")
    return reasons
