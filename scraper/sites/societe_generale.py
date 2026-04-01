from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.content_strategies import DEFAULT_STRATEGIES, first_non_empty_text
from scraper.core.models import Resource, ResourceType


class SocieteGeneraleScraper(SiteScraper):
    base_url = "https://www.societegenerale.com"
    listing_base_url = (
        "https://www.societegenerale.com/fr/etudes-economiques"
        "?type=153&lock_type=yes&page=0"
    )

    def iter_listing_urls(self) -> Iterable[str]:
        """
        Listing paginé via le paramètre ?page=N
        """
        page = 0
        while self.max_pages is None or page < self.max_pages:
            url = self.with_page_query(self.listing_base_url, page)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                break

            yield url
            page += 1

    def with_page_query(
        self, url: str, page: int, extra_params: dict | None = None
    ) -> str:
        """
        Utilise le paramètre `page` (en conservant type=153&lock_type=yes).
        """
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        if extra_params:
            for k, v in extra_params.items():
                query.setdefault(k, v)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen: set[str] = set()

        # À ajuster en fonction du DOM réel, mais ce pattern marche souvent :
        for a in soup.select("article a[href], .node-teaser a[href]"):
            href = a.get("href")
            if not href:
                continue

            full_url = urljoin(self.base_url, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            title = a.get_text(" ", strip=True) or full_url

            resources.append(
                Resource(
                    url=full_url,
                    type=ResourceType.HTML,
                    title=title,
                    meta={"listing_url": url},
                )
            )

        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        resp = self.session.get(resource.url, timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        title = first_non_empty_text(
            soup,
            ["h1", "meta[property='og:title']", "title"],
        )
        if title:
            resource.title = title

        resource.meta["source_html"] = resource.url

        for strategy in DEFAULT_STRATEGIES:
            if strategy.matches(resource.url, soup):
                resource.meta["strategy"] = strategy.__class__.__name__
                return strategy.extract(resource, soup)

        resource.meta["run_error"] = "No extraction strategy matched"
        resource.text = None
        return resource
