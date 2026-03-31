import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.banque_france")


class BanqueFranceScraper(SiteScraper):
    base_url = "https://www.banque-france.fr"
    listing_base_url = (
        "https://www.banque-france.fr/fr/publications-et-statistiques/publications"
    )

    def iter_listing_urls(self) -> Iterable[str]:
        # Utilise la pagination générique basée sur ?page=N
        yield from self.iter_paginated_listing_urls(
            self.listing_base_url,
            self.extract_resources_from_listing,
            first_page=0,
        )

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
