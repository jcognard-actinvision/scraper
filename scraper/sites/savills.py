import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.savills")


class SavillsScraper(SiteScraper):
    base_url = "https://www.savills.fr"
    listing_base_url = (
        "https://www.savills.fr/etudes-and-opinions/etudes-and-recherche.aspx"
    )

    def iter_listing_urls(self) -> Iterable[str]:
        page = 1

        while True:
            if self.max_pages is not None and page > self.max_pages:
                break

            url = self.with_page_query(
                self.listing_base_url,
                page,
                extra_params={
                    "rc": "France",
                    "p": "",
                    "t": "",
                    "f": "date",
                    "q": "",
                },
            )

            try:
                resp = self.session.get(url, timeout=30)
            except Exception as e:
                logger.info(
                    "Stopping pagination on %s due to request error: %s", url, e
                )
                break

            if not resp.ok:
                logger.info(
                    "Stopping pagination on %s due to HTTP %s",
                    url,
                    resp.status_code,
                )
                break

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                logger.info("No resources found on %s, stopping pagination", url)
                break

            yield url
            page += 1

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen_urls: set[str] = set()

        for article in soup.select("article"):
            article_title = None

            title_node = article.select_one(".sv-card-title")
            if title_node:
                article_title = title_node.get_text(" ", strip=True)

            for link in article.select("a[href]"):
                href = link.get("href", "").strip()
                if not href:
                    continue

                full_url = urljoin(self.base_url, href)
                href_lower = full_url.lower()

                if ".pdf" not in href_lower:
                    continue

                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)

                title = article_title or full_url.rsplit("/", 1)[-1]

                resources.append(
                    Resource(
                        url=full_url,
                        type=ResourceType.PDF,
                        title=title,
                        meta={
                            "listing_url": url,
                            "pdf_url": full_url,
                            "article_url": None,
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
