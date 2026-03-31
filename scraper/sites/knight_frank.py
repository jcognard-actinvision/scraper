import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.knight_frank")


class KnightFrankScraper(SiteScraper):
    base_url = "https://www.knightfrank.fr"
    listing_base_url = "https://www.knightfrank.fr/etudes/"

    def iter_listing_urls(self) -> Iterable[str]:
        page = 1

        while True:
            if self.max_pages is not None and page > self.max_pages:
                break

            url = self.with_page_query(self.listing_base_url, page)

            resp = self.session.get(url, timeout=30)
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

        for card_link in soup.select("div.publiCard a[href]"):
            article_url = urljoin(self.base_url, card_link["href"])

            if article_url in seen_urls:
                continue
            seen_urls.add(article_url)

            title = (
                card_link.get_text(" ", strip=True) or article_url.rsplit("/", 1)[-1]
            )

            resources.append(
                Resource(
                    url=article_url,
                    type=ResourceType.HTML,
                    title=title,
                    meta={"listing_url": url},
                )
            )

        logger.info("Found %d article resources on %s", len(resources), url)
        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        resp = self.safe_get(resource.url)
        if resp is None:
            resource.meta["fetch_error"] = "html_unavailable"
            resource.text = None
            return resource

        data = resp.content
        resource.raw_content = data

        html = data.decode(resp.encoding or "utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")

        title_node = soup.select_one("div.detailPublications h1")
        if title_node:
            resource.title = title_node.get_text(strip=True)

        btn = soup.select_one("a.btnRead[href]")
        if btn:
            pdf_url = urljoin(self.base_url, btn["href"])
            resource.meta["pdf_url"] = pdf_url
            resource.meta["source_html"] = resource.url
            logger.info("Resource: %s | PDF: %s", resource.url, pdf_url)
        else:
            logger.info("Resource: %s | PDF: none", resource.url)

        resource.text = None
        return resource
