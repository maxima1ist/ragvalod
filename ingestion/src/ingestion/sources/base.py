"""Data source adapter interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SourceDocument:
    """Normalized document produced by a DataSource adapter."""

    doc_id: str
    text: str
    source: str
    title: str = ""
    uri: str = ""
    modified_at: datetime | None = None
    content_type: str = "text"  # "markdown" | "text"
    metadata: dict[str, Any] = field(default_factory=dict)


class DataSource(ABC):
    """Thin adapter over a reader / API. Activated via factory when creds/config allow."""

    name: str
    description: str
    requires_credentials: bool = True

    @abstractmethod
    async def fetch(
        self,
        credentials: dict[str, str],
        options: dict[str, str],
    ) -> list[SourceDocument]:
        """Fetch documents. Credentials live only for the duration of the job."""
