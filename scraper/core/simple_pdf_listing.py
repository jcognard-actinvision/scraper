from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType


@dataclass
class PdfListingConfig:
    listing_base_url: str
    page_param: str  # "page", "_paged", etc.
    link_selector: str  # CSS pour les liens du listing (vers article OU pdf direct)
    pdf_selector: str | None = None  # si None => lien direct pdf
    base_url_for_join: str | None = None


class SimplePdfListingScraper(SiteScraper):
    """
    Scraper générique pour :
      - pagination paramétrée (page_param)
      - extraction des liens dans le listing
      - optionnellement, récupération du 1er PDF dans la page article
    """

    config: PdfListingConfig

    def iter_listing_urls(self) -> Iterable[str]:
        page = 0
        while self.max_pages is None or page < self.max_pages:
            url = self.with_page_query(self.config.listing_base_url, page)
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
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query[self.config.page_param] = str(page)
        if extra_params:
            for k, v in extra_params.items():
                query.setdefault(k, v)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen: set[str] = set()

        for a in soup.select(self.config.link_selector):
            href = a.get("href")
            if not href:
                continue

            base = self.config.base_url_for_join or url
            full_url = urljoin(base, href)
            if full_url in seen:
                continue
            seen.add(full_url)

            title = a.get_text(strip=True) or full_url

            resources.append(
                Resource(
                    url=full_url,
                    type=ResourceType.PDF
                    if self.config.pdf_selector is None
                    else ResourceType.HTML,
                    title=title,
                    meta={"listing_url": url},
                )
            )

        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        if self.config.pdf_selector is None:
            # lien direct PDF
            resp = self.safe_get(resource.url)
            if resp is None:
                resource.meta["fetch_error"] = "pdf_unavailable"
                resource.text = None
                resource.raw_content = None
                return resource

            resource.raw_content = resp.content
            resource.text = None
            resource.meta["pdf_url"] = resource.url
            return resource

        # Sinon, on doit aller chercher le PDF dans la page article
        resp = self.safe_get(resource.url)
        if resp is None:
            resource.meta["fetch_error"] = "html_unavailable"
            resource.text = None
            resource.raw_content = None
            return resource

        soup = BeautifulSoup(resp.text, "html.parser")
        resource.meta["article_url"] = resource.url

        pdf_link = soup.select_one(self.config.pdf_selector)
        if not pdf_link or not pdf_link.get("href"):
            resource.meta["pdf_error"] = "PDF link not found with selector"
            resource.text = None
            resource.raw_content = resp.content
            return resource

        pdf_url = urljoin(resource.url, pdf_link["href"])
        pdf_resp = self.safe_get(pdf_url)
        if pdf_resp is None:
            resource.meta["pdf_url"] = pdf_url
            resource.meta["pdf_error"] = "pdf_unavailable"
            resource.text = None
            resource.raw_content = resp.content
            return resource

        resource.url = pdf_url
        resource.type = ResourceType.PDF
        resource.meta["pdf_url"] = pdf_url
        resource.meta["source_html"] = resource.meta.get("article_url")
        resource.text = None
        resource.raw_content = pdf_resp.content
        return resource
