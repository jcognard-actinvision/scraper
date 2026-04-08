import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.catella")


class CatellaScraper(SiteScraper):
    base_url = "https://www.catella.com"
    listing_url = "https://www.catella.com/fr/france/corporate-finance/etudes-de-marche"

    def iter_listing_urls(self) -> Iterable[str]:
        yield self.listing_url

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen_urls: set[str] = set()

        for link in soup.select("div.textimageblock a[href]"):
            pdf_url = urljoin(self.base_url, link["href"])

            if pdf_url in seen_urls:
                continue
            seen_urls.add(pdf_url)

            if not pdf_url.lower().endswith(".pdf"):
                continue

            title = link.get_text(" ", strip=True)
            if not title:
                title = pdf_url.rsplit("/", 1)[-1]

            resources.append(
                Resource(
                    url=pdf_url,
                    type=ResourceType.PDF,
                    title=title,
                    meta={
                        "listing_url": url,
                        "pdf_url": pdf_url,
                    },
                )
            )

        logger.info("Found %d PDF resources on %s", len(resources), url)
        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        resp = self.safe_get(resource.url)
        if resp is None:
            resource.meta["fetch_error"] = "pdf_unavailable"
            resource.text = None
            return resource

        resource.raw_content = resp.content
        resource.text = None
        resource.meta.setdefault("pdf_url", resource.url)
        return resource
