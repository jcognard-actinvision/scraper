from typing import Iterable, List
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType


class CreditAgricoleImmobilierScraper(SiteScraper):
    base_url = "https://etudes-economiques.credit-agricole.com"
    listing_base_url = "https://etudes-economiques.credit-agricole.com/fr/recherche"

    def set_max_pages(self, max_pages: int | None):
        self.max_pages = max_pages

    def iter_listing_urls(self) -> Iterable[str]:
        """
        Paginer sur ?search_api_fulltext=immobilier&search_mode=all&page=N
        jusqu'à ce qu'une page ne contienne plus de résultats
        ou jusqu'à max_pages si défini.
        """
        page = 0

        while self.max_pages is None or page < self.max_pages:
            url = self._with_page(self.listing_base_url, page)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                break

            yield url
            page += 1

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []

        for row in soup.select("div.search-engine-result-row"):
            pdf_link = row.select_one("a.btn-download[href]")
            if not pdf_link:
                continue

            pdf_url = urljoin(self.base_url, pdf_link["href"])
            title = self._extract_row_title(row)
            if not title:
                title = pdf_link.get_text(strip=True) or row.get_text(strip=True)

            if not title:
                continue

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
        Pour l'instant, on ne fait que récupérer le binaire du PDF, sans extraction texte.
        """
        resp = self.session.get(resource.url, timeout=30)
        resp.raise_for_status()
        data = resp.content

        resource.raw_content = data
        resource.text = None

        return resource

    def _with_page(self, url: str, page: int) -> str:
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))

        query.setdefault("search_api_fulltext", "immobilier")
        query.setdefault("search_mode", "all")
        query["page"] = str(page)

        return urlunparse(parsed._replace(query=urlencode(query)))

    def _extract_row_title(self, row) -> str:
        for selector in [
            ".search-engine-result-title",
            "h2",
            "h3",
            "a",
        ]:
            node = row.select_one(selector)
            if node:
                txt = node.get_text(strip=True)
                if txt:
                    return txt

        return row.get_text(" ", strip=True)
