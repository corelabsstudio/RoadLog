"""Read-only paid AI learning probe. Default mode makes no external calls."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="게시 후 실측→Learning→다음 Director 입력 확인")
    parser.add_argument("--campaign-id", type=int, required=True)
    parser.add_argument("--live-ai", action="store_true", help="실제 Gemini 1회 호출 가능: 명시적 선택")
    args = parser.parse_args()
    from modules import marketing_os
    from modules.marketing_core.agents import TASKS
    from modules.marketing_gemini import RoadLogGeminiProvider

    repo = marketing_os.MarketingRepository(marketing_os.DB, marketing_os.TENANT_ID)
    campaign = next((row for row in repo.recent_campaigns(100) if row["id"] == args.campaign_id), None)
    if not campaign or not campaign["scorecard"] or not any(p["status"] == "PUBLISHED" for p in campaign["publications"]):
        raise SystemExit("게시·귀속 점수표가 있는 캠페인 ID가 필요합니다. AI 호출 0건.")
    learning = next((row for row in repo.recent_learning() if row["campaign_id"] == args.campaign_id), None)
    if not learning:
        raise SystemExit("이 캠페인의 Learning이 없습니다. AI 호출 0건.")
    print(f"캠페인 #{args.campaign_id}: 게시·점수표·Learning 확인")
    print("실측 방문/가입/구매:", campaign["scorecard"].get("visits"), campaign["scorecard"].get("signups"), campaign["scorecard"].get("purchases"))
    if not args.live_ai:
        print("기본 모드: Gemini 호출 0건. 실제 1회 확인은 --live-ai가 필요합니다.")
        return 0
    provider = RoadLogGeminiProvider()
    if not provider.connected:
        raise SystemExit("Gemini 키가 없습니다. AI 호출 0건.")
    catalog = marketing_os.products(ROOT / "web")
    product = next((row for row in catalog["products"] if row["product_id"] == campaign["product_id"] and row["facts_status"] == "VERIFIED"), None)
    if not product:
        raise SystemExit("상품 정본을 확인하지 못했습니다. AI 호출 0건.")
    metrics = marketing_os.performance_snapshot()
    metrics["previous_learning"] = [learning]
    metrics["previous_campaigns"] = [{"id": campaign["id"], "product_id": campaign["product_id"],
                                       "status": campaign["status"], "scorecard": campaign["scorecard"]}]
    task = next(task for task in TASKS if task.agent_id == "marketing_director")
    result = provider.generate_role(task, {**product, "synced_at": catalog["sync"]["synced_at"],
                                           "source_file": catalog["sync"]["source_file"]}, metrics=metrics,
                                    context=["게시 후 실측 성과와 Learning을 검토하고 다음 행동 또는 NO_ACTION을 결정하세요."])
    print("Gemini 결정:", result.get("decision"), "· 요약:", result.get("summary"))
    print("공급자 토큰 사용량:", provider.usage)
    print("이 명령은 승인·게시·새 캠페인 생성을 실행하지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
