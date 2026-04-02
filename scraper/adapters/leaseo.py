from __future__ import annotations

from urllib.parse import urljoin

import requests

from ..models import SiteConfig
from .base import BaseSiteAdapter


class LeaseoAdapter(BaseSiteAdapter):
    def iter_item_urls(self, cfg: SiteConfig) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()

        pagination = cfg.listing.pagination
        if pagination is None:
            return urls

        offset = pagination.start
        base = cfg.listing.url

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "StonelakeScraper/1.0",
                "Accept": "application/json, text/javascript, */*; q=0.01",
            }
        )

        for _ in range(pagination.max_pages):
            resp = session.get(base, params={"offset": offset}, timeout=30)
            resp.raise_for_status()

            data = resp.json()
            items = data if isinstance(data, list) else data.get("items", [])
            if not items:
                break

            added_count = 0

            for it in items:
                href = it.get("detailUrl")
                if not href:
                    continue

                full_url = urljoin(cfg.base_url, href)
                if full_url in seen:
                    continue

                seen.add(full_url)
                urls.append(full_url)
                added_count += 1

            if added_count == 0:
                break

            offset += len(items)

        return urls
