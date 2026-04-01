from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType


class BNPPREMarketFranceScraper(SiteScraper):
    """
    Études de marché France – BNP Paribas Real Estate.

    Listing :
      https://www.realestate.bnpparibas.fr/fr/etudes-tendances/etudes-de-marche-France?page=0

    Pagination via paramètre `page` (0,1,2,...)

    Sur chaque page :
      - liens d’articles : div.content article a
      - dans la page article : PDFs via article div.file-download a
        → on prend le premier lien (PDF).
    """

    listing_base_url = "https://www.realestate.bnpparibas.fr/fr/etudes-tendances/etudes-de-marche-France"

    def iter_listing_urls(self) -> Iterable[str]:
        """
        Pagination par paramètre `page`, à partir de 0.
        On s'arrête quand une page ne renvoie plus aucun article.
        """
        page = 0
        while self.max_pages is None or page < self.max_pages:
            url = self.with_page_query(self.listing_base_url, page)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                break

            yield url
            page += 1

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        """
        Récupère les URLs d’articles à partir de la page de listing.
        On ne connaît pas encore les PDFs ici.
        """
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []

        # Tous les liens d’article dans le bloc de contenu
        for a in soup.select("div.content article a[href]"):
            href = a.get("href")
            if not href:
                continue

            article_url = urljoin(self.listing_base_url, href)
            title = a.get_text(strip=True) or article_url

            resources.append(
                Resource(
                    url=article_url,
                    type=ResourceType.HTML,
                    title=title,
                    meta={
                        "listing_url": url,
                    },
                )
            )

        return resources

    def extract_content(self, resource: Resource) -> Resource:
        """
        Charge la page article, repère le premier lien dans
        `article div.file-download a`, et ne conserve que l’URL PDF.
        """
        resource.meta = resource.meta or {}

        resp = self.session.get(resource.url, timeout=30)
        resp.raise_for_status()
        html = resp.text

        soup = BeautifulSoup(html, "html.parser")

        # Titre plus propre si disponible
        h1 = soup.select_one("article h1, h1.page-title, h1")
        if h1:
            title = h1.get_text(strip=True)
            if title:
                resource.title = title

        pdf_link = soup.select_one("article div.file-download a[href]")
        if not pdf_link:
            # Pas de PDF détecté : on garde la page comme HTML sans texte
            resource.meta["pdf_error"] = "No file-download link found"
            resource.text = None
            resource.raw_content = None
            return resource

        pdf_url = urljoin(resource.url, pdf_link.get("href"))
        resource.meta["pdf_url"] = pdf_url

        # On ne télécharge pas le PDF ici, on ne renvoie que l’URL
        resource.type = ResourceType.PDF
        resource.url = pdf_url
        resource.raw_content = None
        resource.text = None

        return resource
