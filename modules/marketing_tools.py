"""Capability inventory. A key or an interface alone is not proof of operation."""
from __future__ import annotations

from typing import Any

from modules.marketing_creative import GeminiImageProvider
from modules.marketing_gemini import RoadLogGeminiProvider
from modules.marketing_instagram import configured as instagram_configured, publishing_enabled
from modules.marketing_research import BraveResearchProvider


def tool_registry() -> dict[str, dict[str, Any]]:
    research = BraveResearchProvider()
    image = GeminiImageProvider()
    content = RoadLogGeminiProvider()
    instagram = instagram_configured() and publishing_enabled()
    return {
        "research": {"status": "CONFIGURED_UNVERIFIED" if research.connected else "CONFIG_REQUIRED", "provider": "Brave Web Search"},
        "search": {"status": "CONFIGURED_UNVERIFIED" if research.connected else "CONFIG_REQUIRED", "provider": "Brave Web Search", "search_volume": "NOT_CONNECTED"},
        "siteAnalytics": {"status": "AUTO", "provider": "ROADLOG internal aggregates", "product_attribution": "NOT_CONNECTED"},
        "contentGeneration": {"status": "CONFIGURED_UNVERIFIED" if content.connected else "CONFIG_REQUIRED", "provider": content.name},
        "imageGeneration": {"status": "CONFIGURED_UNVERIFIED" if image.connected else "CONFIG_REQUIRED", "provider": image.name, "billing": "PAID_API_POSSIBLE", "model": image.model},
        "videoGeneration": {"status": "CONFIG_REQUIRED", "provider": None, "note": "FFmpeg still-image conversion is not AI video generation"},
        "publishing": {"status": "CONFIGURED_UNVERIFIED" if instagram else "CONFIG_REQUIRED", "provider": "Instagram Graph API", "approval": "EACH_POST_REQUIRED"},
        "performanceTracking": {"status": "PARTIAL", "provider": "ROADLOG internal aggregates", "campaign_attribution": "NOT_CONNECTED"},
    }
