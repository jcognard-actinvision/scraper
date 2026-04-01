import logging
from typing import Iterable, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger(__name__)


class AspimScraper(SiteScraper):
    """
    Scraper ASPIM – Documentation publique.

    URL de base :
    https://www.aspim.fr/documentation/?_restriction=public&_sorting=date_desc&_paged=1

    Pagination : paramètre `_paged` (1, 2, 3, ...)
    Liens PDF : div.card-document h3 a.no-icon (href = URL PDF directe)
    """

    listing_base_url = (
        "https://www.aspim.fr/documentation/"
        "?_restriction=public&_sorting=date_desc&_paged=1"
    )

    def iter_listing_urls(self) -> Iterable[str]:
        """
        Gestion de la pagination ASPIM en incrémentant `_paged`.
        On utilise le même pattern que Crédit Agricole Immobilier.
        """
        page = 1
        while self.max_pages is None or page < self.max_pages + 1:
            url = self.with_page_query(self.listing_base_url, page)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                break

            logger.info("ASPIM: page %s -> %d resources", page, len(resources))
            yield url
            page += 1

    def with_page_query(
        self, url: str, page: int, extra_params: dict | None = None
    ) -> str:
        """
        Surcharge pour utiliser `_paged` au lieu de `page`.
        """
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["_paged"] = str(page)
        if extra_params:
            for k, v in extra_params.items():
                query.setdefault(k, v)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        """
        Sur une page de listing, extrait tous les liens PDF.
        """
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []

        for a in soup.select("div.card-document h3 a.no-icon[href]"):
            href = a.get("href")
            if not href:
                continue

            pdf_url = urljoin(url, href)
            title = a.get_text(strip=True) or pdf_url

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

        return resources

    def extract_content(self, resource: Resource) -> Resource:
        """
        Comme pour Crédit Agricole Immobilier :
        on télécharge le PDF (optionnel) mais on ne remplit pas `text`.
        """
        resp = self.session.get(resource.url, timeout=30)
        resp.raise_for_status()
        data = resp.content

        resource.raw_content = data
        resource.text = None
        return resource
