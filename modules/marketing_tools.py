"""Capability inventory. A key or an interface alone is not proof of operation."""
from __future__ import annotations

from typing import Any

from modules.marketing_creative import GeminiImageProvider
from modules.marketing_gemini import RoadLogGeminiProvider
from modules.marketing_instagram import configured as instagram_configured, publishing_enabled
from modules.marketing_research import TavilyResearchProvider


def tool_registry() -> dict[str, dict[str, Any]]:
    research = TavilyResearchProvider()
    content = RoadLogGeminiProvider()
    instagram = instagram_configured() and publishing_enabled()
    return {
        "research": {"status": "CONFIGURED_UNVERIFIED" if research.connected else "CONFIG_REQUIRED", "provider": "Tavily Search"},
        "search": {"status": "CONFIGURED_UNVERIFIED" if research.connected else "CONFIG_REQUIRED", "provider": "Tavily Search", "search_volume": "NOT_CONNECTED"},
        "siteAnalytics": {"status": "AUTO", "provider": "ROADLOG internal aggregates", "product_attribution": "NOT_CONNECTED"},
        "contentGeneration": {"status": "CONFIGURED_UNVERIFIED" if content.connected else "CONFIG_REQUIRED", "provider": content.name},
        "blogPublishing": {"status": "WORKING", "provider": "ROADLOG blog", "approval": "EACH_POST_REQUIRED"},
        "imageGeneration": {"status": "PAUSED_APPROVAL", "provider": "Gemini Image", "billing": "PAID_API_ON_HOLD", "model": None},
        "videoGeneration": {"status": "CONFIG_REQUIRED", "provider": None, "note": "FFmpeg still-image conversion is not AI video generation"},
        "publishing": {"status": "CONFIGURED_UNVERIFIED" if instagram else "CONFIG_REQUIRED", "provider": "Instagram Graph API", "approval": "EACH_POST_REQUIRED"},
        "performanceTracking": {"status": "WORKING", "provider": "ROADLOG first-party UTM attribution", "campaign_attribution": "CONNECTED_AFTER_PUBLISH"},
    }
