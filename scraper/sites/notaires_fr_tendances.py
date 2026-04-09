import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.notaires_fr_tendances")


class NotairesFranceTendancesScraper(SiteScraper):
    base_url = "https://www.notaires.fr"
    listing_url = "https://www.notaires.fr/fr/tendances-du-marche-immobilier-en-france"

    def iter_listing_urls(self) -> Iterable[str]:
        yield self.listing_url

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen_urls: set[str] = set()

        for link in soup.select("h3.content__title a[href]"):
            art_url = urljoin(self.base_url, link["href"])

            if art_url in seen_urls:
                continue
            seen_urls.add(art_url)

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

            article_url = resource.url
            resource.meta["article_url"] = article_url

            title_node = soup.select_one("h1.article-h1__title")
            if title_node:
                resource.title = title_node.get_text(strip=True)

            content_node = soup.select_one("div.article__content")
            if content_node:
                for selector in [
                    "div.social-share-selection",
                    "div.content-tools",
                    "iframe",
                ]:
                    for node in content_node.select(selector):
                        node.decompose()

                html_text = content_node.get_text(separator="\n", strip=True)
            else:
                html_text = (soup.find("main") or soup.body or soup).get_text(
                    separator="\n",
                    strip=True,
                )

            resource.meta["html_text"] = html_text

            pdf_url = self._extract_pdf_url(soup)
            if pdf_url:
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = article_url
                logger.info("Resource: %s | PDF: %s", article_url, pdf_url)

                pdf_resp = self.safe_get(pdf_url)
                if pdf_resp is not None:
                    resource.type = ResourceType.PDF
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

    def _extract_pdf_url(self, soup: BeautifulSoup) -> str | None:
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if not href:
                continue

            href_lower = href.lower()
            if ".pdf" in href_lower:
                return urljoin(self.base_url, href)

        return None
