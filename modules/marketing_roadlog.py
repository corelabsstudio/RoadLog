from __future__ import annotations
import hashlib,json,os
from datetime import datetime,timezone
from pathlib import Path
from typing import Any
from modules import lamps

def _now() -> str: return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

class RoadLogCatalog:
    def __init__(self,web_root:Path): self.path=Path(web_root)/"admin"/"marketing-products.json"
    def load(self)->tuple[list[dict[str,Any]],dict[str,Any]]:
        raw=self.path.read_bytes(); payload=json.loads(raw.decode("utf-8")); products=[]; warnings=[]
        for source in payload.get("products",[]):
            item=dict(source); pid=item.get("product_id") or ""; issues=[]; free=pid in lamps.FREE_PRODUCTS; price=0 if free else lamps.PREMIUM_WON.get(pid)
            if item.get("price_won")!=price: issues.append(f"원화 가격 불일치: 화면 {item.get('price_won')}, 서버 {price if price is not None else 'UNKNOWN'}")
            if bool(item.get("free"))!=free: issues.append("무료 여부 불일치")
            if bool(item.get("premium"))!=(pid in lamps.PREMIUM_ONLY): issues.append("결제 전용 여부 불일치")
            item["lamp_price"]=0 if free else ("결제 전용" if pid in lamps.PREMIUM_ONLY else lamps.PRICES.get(pid,"UNKNOWN")); item["facts_status"]="VERIFIED" if not issues else "MISMATCH"; item["issues"]=issues
            products.append(item); warnings.extend(f"{pid}: {issue}" for issue in issues)
        return products,{"source_file":str(self.path),"source_hash":hashlib.sha256(raw).hexdigest(),"generated_at":payload.get("generated_at") or "UNKNOWN","synced_at":_now(),"warnings":warnings}

class RoadLogDemoProvider:
    name="Google Gemini"
    def __init__(self):
        self.model=os.getenv("SAJU_MODEL","gemini-3.8-flash"); self.connected=bool((os.getenv("GEMINI_API_KEY") or "").strip())
    def generate(self,product:dict[str,Any],platform:str)->dict[str,Any]:
        price="무료" if product["free"] else f"{product['price_won']:,}원"; feature=(product.get("confirmed_results") or ["확인된 결과 항목 없음"])[0]
        return {"platform":platform,"product_id":product["product_id"],"title":f"{product['name']}에서 확인할 수 있는 것","hook":f"지금 필요한 정보만 {price} 기준으로 확인해 보세요.","body":f"ROADLOG의 {product['name']}은 현재 {price}입니다. 확인된 결과 항목은 {feature}입니다.","cta":"상품 화면에서 현재 정보를 다시 확인해 주세요.","image_prompt":"ROADLOG 사주 결과를 차분하게 확인하는 장면, 글자와 가격 표기 없음","factual_claims":[feature] if product.get("confirmed_results") else [],"source_facts":product["product_id"],"uncertainty":[],"estimated_cost":None}
