from __future__ import annotations
from typing import Any, Protocol

class CatalogProvider(Protocol):
    def load(self) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...

class ContentProvider(Protocol):
    name: str
    model: str
    connected: bool
    def generate(self, product: dict[str, Any], platform: str) -> dict[str, Any]: ...

class ResearchProvider(Protocol):
    connected: bool
    def search(self, query: str) -> list[dict[str, Any]]: ...

class CreativeProvider(Protocol):
    connected: bool
    def generate_image(self, brief: dict[str, Any]) -> dict[str, Any]: ...
    def generate_video(self, brief: dict[str, Any]) -> dict[str, Any]: ...
    def generation_status(self, job_id: str) -> dict[str, Any]: ...

class AnalyticsProvider(Protocol):
    connected: bool
    def snapshot(self, days: int) -> dict[str, Any]: ...

class PublishingProvider(Protocol):
    connected: bool
    def publish(self, approved_content_id: int, *, confirmed: bool) -> dict[str, Any]: ...
