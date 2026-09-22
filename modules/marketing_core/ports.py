from __future__ import annotations
from typing import Any, Protocol

class CatalogProvider(Protocol):
    def load(self) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...

class ContentProvider(Protocol):
    name: str
    model: str
    connected: bool
    def generate(self, product: dict[str, Any], platform: str) -> dict[str, Any]: ...
