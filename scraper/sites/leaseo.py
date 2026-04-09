import json
import logging
from typing import Iterable, List
from urllib.parse import urljoin

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.leaseo")


class LeaseoScraper(SiteScraper):
    base_url = "https://www.leaseo.fr"
    ajax_url = "https://www.leaseo.fr/actualitesMore"
    page_size = 6

    def iter_listing_urls(self) -> Iterable[str]:
        offset = 0

        while True:
            page_index = offset // self.page_size + 1
            if self.max_pages is not None and page_index > self.max_pages:
                break

            params = {
                "offset": str(offset),
                "categorie": "0",
            }

            resp = self.session.get(self.ajax_url, params=params, timeout=30)
            if not resp.ok:
                logger.info(
                    "Leaseo: stopping pagination at offset=%s due to HTTP %s",
                    offset,
                    resp.status_code,
                )
                break

            text = resp.text.strip()
            if not text:
                logger.info(
                    "Leaseo: stopping pagination at offset=%s (empty response)",
                    offset,
                )
                break

            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                logger.info(
                    "Leaseo: stopping pagination at offset=%s (invalid JSON)",
                    offset,
                )
                break

            if not payload:
                logger.info(
                    "Leaseo: stopping pagination at offset=%s (empty list)",
                    offset,
                )
                break

            yield resp.url
            offset += self.page_size

    def extract_resources_from_listing(
        self, html_or_json: str, url: str
    ) -> List[Resource]:
        resources: List[Resource] = []

        try:
            items = json.loads(html_or_json)
        except json.JSONDecodeError:
            logger.warning("Leaseo: invalid JSON on %s", url)
            return resources

        for item in items:
            detail_url = item.get("detailUrl")
            title = item.get("titre") or detail_url

            if not detail_url or not title:
                continue

            resources.append(
                Resource(
                    url=detail_url,
                    type=ResourceType.HTML,
                    title=title,
                    meta={
                        "listing_url": url,
                        "leaseo_id": item.get("id"),
                        "date_publication": item.get("datePublication"),
                        "image_540": (item.get("image") or {}).get("size_540"),
                    },
                )
            )

        logger.info("Leaseo: found %d resources on %s", len(resources), url)
        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        resp = self.safe_get(resource.url)
        if resp is None:
            resource.meta["fetch_error"] = "html_unavailable"
            resource.text = None
            return resource

        html = resp.content.decode(resp.encoding or "utf-8", errors="ignore")

        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        article_url = resource.url
        resource.meta["article_url"] = article_url

        title_node = soup.select_one("section.blocTitre h1")
        if title_node:
            resource.title = title_node.get_text(strip=True)

        content_node = soup.select_one("section.blocContenu")
        if content_node:
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
            logger.info("Leaseo resource: %s | PDF: %s", article_url, pdf_url)

            pdf_resp = self.safe_get(pdf_url)
            if pdf_resp is not None:
                resource.type = ResourceType.PDF
                resource.raw_content = pdf_resp.content
                resource.text = None
                return resource

            resource.meta["pdf_error"] = "pdf_unavailable"
        else:
            logger.info("Leaseo resource: %s | PDF: none", resource.url)

        resource.raw_content = resp.content
        resource.text = html_text
        return resource

    def _extract_pdf_url(self, soup) -> str | None:
        for link in soup.select("a[href]"):
            href = (link.get("href") or "").strip()
            if not href:
                continue

            href_lower = href.lower()
            if ".pdf" in href_lower:
                return urljoin(self.base_url, href)

        return None
