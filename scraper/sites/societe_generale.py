import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.societe_generale")


class SocieteGeneraleScraper(SiteScraper):
    base_url = "https://www.societegenerale.com"
    listing_base_url = (
        "https://www.societegenerale.com/fr/etudes-economiques"
    )

    def iter_listing_urls(self) -> Iterable[str]:
        page = 0

        while self.max_pages is None or page < self.max_pages:
            url = self.with_page_query(
                self.listing_base_url,
                page,
                extra_params={
                    "type": "153",
                    "lock_type": "yes",
                },
            )
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                logger.info("No resources found on %s, stopping pagination", url)
                break

            yield url
            page += 1

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []

        for link in soup.select("ul.newsroom-list a.actu-thumb[href]"):
            art_url = urljoin(self.base_url, link["href"])
            title = self._extract_listing_title(link)

            if not title:
                title = link.get_text(" ", strip=True)

            if not title:
                continue

            resources.append(
                Resource(
                    url=art_url,
                    type=ResourceType.HTML,
                    title=title,
                    meta={"listing_url": url},
                )
            )

        logger.info("Found %d resources on %s", len(resources), url)
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

        if resource.type == ResourceType.HTML:
            html = data.decode(resp.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            h1 = soup.find("h1")
            if h1:
                resource.title = h1.get_text(strip=True)

            main_container = soup.find("main") or soup.body or soup
            html_text = main_container.get_text(separator="\n", strip=True)
            resource.meta["html_text"] = html_text
            resource.text = html_text

            pdf_link = soup.select_one(
                "div.bloc-element-de-contexte a.custom-download-link[href]"
            )
            if pdf_link:
                pdf_url = urljoin(self.base_url, pdf_link["href"])
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = resource.url
                logger.info("Resource: %s | PDF: %s", resource.url, pdf_url)
            else:
                logger.info("Resource: %s | PDF: none", resource.url)

        elif resource.type == ResourceType.PDF:
            resource.text = None

        return resource

    def _extract_listing_title(self, link) -> str:
        for selector in [
            "h2",
            "h3",
            ".title",
            ".actu-thumb__title",
            ".field-content",
        ]:
            node = link.select_one(selector)
            if node:
                txt = node.get_text(strip=True)
                if txt:
                    return txt

        return link.get_text(" ", strip=True)