from __future__ import annotations

from pathlib import Path

import yaml

from .models import (
    ListingConfig,
    ListingPaginationConfig,
    PdfConfig,
    SiteConfig,
    SiteSelectors,
)


def load_sites_config(path: str | Path = "config/sites.yaml") -> list[SiteConfig]:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sites_cfg: list[SiteConfig] = []

    for raw in data.get("sites", []):
        pag_raw = (raw.get("listing") or {}).get("pagination")
        pagination = None
        if pag_raw:
            pagination = ListingPaginationConfig(
                type=pag_raw.get("type", "none"),
                param=pag_raw.get("param"),
                start=pag_raw.get("start", 1),
                max_pages=pag_raw.get("max_pages", 1),
            )

        listing = ListingConfig(
            url=raw["listing"]["url"],
            pagination=pagination,
        )

        selectors = SiteSelectors(
            item_link=raw["selectors"]["item_link"],
            title=raw["selectors"].get("title"),
            content=raw["selectors"].get("content"),
        )

        pdf = PdfConfig(
            link_selectors=raw["pdf"].get("link_selectors", []),
            follow_redirects=raw["pdf"].get("follow_redirects", True),
        )

        sites_cfg.append(
            SiteConfig(
                id=raw["id"],
                enabled=raw.get("enabled", True),
                base_url=raw["base_url"],
                listing=listing,
                selectors=selectors,
                pdf=pdf,
                adapter=raw.get("adapter"),
            )
        )

    return sites_cfg
