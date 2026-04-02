from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ScrapedDocument:
    id: str
    source_id: str
    url: str
    title: str | None = None
    text: str | None = None
    pdf_files: list[str] = field(default_factory=list)
    raw_html_path: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ListingPaginationConfig:
    type: str  # "page_param" | "none" ...
    param: str | None = None
    start: int = 1
    max_pages: int = 1


@dataclass
class ListingConfig:
    url: str
    pagination: ListingPaginationConfig | None = None


@dataclass
class SiteSelectors:
    item_link: str
    title: str | None = None
    content: str | None = None


@dataclass
class PdfConfig:
    link_selectors: list[str]
    follow_redirects: bool = True


@dataclass
class SiteConfig:
    id: str
    enabled: bool
    base_url: str
    listing: ListingConfig
    selectors: SiteSelectors
    pdf: PdfConfig
    adapter: str | None = None  # "scraper.adapters.cushman_fr:CushmanFrAdapter"
