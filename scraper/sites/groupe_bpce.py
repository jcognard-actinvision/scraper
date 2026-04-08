import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.groupe_bpce")


class GroupeBPCEScraper(SiteScraper):
    base_url = "https://www.groupebpce.com"
    listing_url = "https://www.groupebpce.com/etudes-economiques/"

    def iter_listing_urls(self) -> Iterable[str]:
        yield self.listing_url

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen_urls: set[str] = set()

        selectors = [
            "a.listPostFeatured[href]",
            "div.listPostList a[href]",
        ]

        for selector in selectors:
            for link in soup.select(selector):
                art_url = urljoin(self.base_url, link["href"])

                if art_url in seen_urls:
                    continue
                seen_urls.add(art_url)

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

        if resource.type == ResourceType.HTML:
            html = resp.content.decode(resp.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            resource.meta["article_url"] = resource.url

            h1 = soup.find("h1")
            if h1:
                resource.title = h1.get_text(strip=True)

            main_container = soup.find("main") or soup.body or soup
            html_text = main_container.get_text(separator="\n", strip=True)
            resource.meta["html_text"] = html_text

            pdf_link = soup.select_one("a.download-link[href]")
            if pdf_link and pdf_link.get("href"):
                pdf_url = urljoin(self.base_url, pdf_link["href"])
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = resource.url
                logger.info("Resource: %s | PDF: %s", resource.url, pdf_url)

                pdf_resp = self.safe_get(pdf_url)
                if pdf_resp is not None:
                    resource.type = ResourceType.PDF
                    resource.url = pdf_url
                    resource.raw_content = pdf_resp.content
                    resource.text = None
                    return resource

                resource.meta["pdf_error"] = "pdf_unavailable"
            else:
                logger.info("Resource: %s | PDF: none", resource.url)

            resource.raw_content = resp.content
            resource.text = html_text
            return resource

        elif resource.type == ResourceType.PDF:
            resource.raw_content = resp.content
            resource.text = None
            return resource

        resource.raw_content = resp.content
        resource.text = None
        return resource

    def _extract_listing_title(self, link) -> str:
        for selector in [
            "h2",
            "h3",
            "h4",
            ".title",
            ".post-title",
            ".listPostTitle",
            ".elementor-heading-title",
        ]:
            node = link.select_one(selector)
            if node:
                txt = node.get_text(strip=True)
                if txt:
                    return txt

        return link.get_text(" ", strip=True)
