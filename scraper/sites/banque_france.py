import logging
import time
from typing import Iterable, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.banque_france")


class BanqueFranceScraper(SiteScraper):
    base_url = "https://www.banque-france.fr"
    listing_base_url = (
        "https://www.banque-france.fr/fr/publications-et-statistiques/publications"
    )

    def set_max_pages(self, max_pages: int | None):
        self.max_pages = max_pages

    def iter_listing_urls(self) -> Iterable[str]:
        page = 0

        while self.max_pages is None or page < self.max_pages:
            url = self._with_page(self.listing_base_url, page)
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

        for container in soup.select("div.col.d-flex"):
            link = container.select_one("a.card[href]")
            if not link:
                continue

            art_url = urljoin(self.base_url, link["href"])
            title = self._extract_card_title(link) or link.get_text(strip=True)
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

        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        resp = self._safe_get(resource.url)
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
                "div.paragraph--type--espaces2-telecharger-document a.card-download[href]"
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

    def _safe_get(self, url: str, retries: int = 2, delay: float = 1.5):
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return resp
            except Exception:
                if attempt < retries:
                    time.sleep(delay * (attempt + 1))

        return None

    def _with_page(self, url: str, page: int) -> str:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _extract_card_title(self, link) -> str:
        for selector in [
            ".card-title",
            ".field--name-title",
            "h2",
            "h3",
            ".fr-card__title",
        ]:
            node = link.select_one(selector)
            if node:
                txt = node.get_text(strip=True)
                if txt:
                    return txt

        return link.get_text(" ", strip=True)
