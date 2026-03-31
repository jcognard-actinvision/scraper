import logging
from typing import Iterable, List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.labanquepostale")


LISTING_URLS = [
    "https://www.labanquepostale.com/newsroom-publications/etudes/etudes-economiques/rebond.p-1.html",
    "https://www.labanquepostale.com/newsroom-publications/etudes/etudes-economiques/actu-eco.p-1.html",
    "https://www.labanquepostale.com/newsroom-publications/etudes/etudes-economiques/etudes-thematiques.p-1.html",
    "https://www.labanquepostale.com/newsroom-publications/etudes/etudes-economiques/logement.p-1.html",
]


class LaBanquePostaleScraper(SiteScraper):
    base_url = "https://www.labanquepostale.com"

    def set_max_pages(self, max_pages: int | None):
        self.max_pages = max_pages

    def iter_listing_urls(self) -> Iterable[str]:
        """
        Pour chaque URL de base dans LISTING_URLS (rebond, actu-eco, etc.),
        on génère rebond.p-1.html, rebond.p-2.html, ... jusqu'à ce qu'il n'y ait plus de ressources
        ou qu'on atteigne max_pages.
        """
        max_pages = getattr(self, "max_pages", None)

        for base in LISTING_URLS:
            page = 1  # les URLs existantes sont déjà en .p-1.html

            while True:
                if max_pages is not None and page > max_pages:
                    break

                url = self._with_page(base, page)
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

        for push in soup.select("div.o-newslist__push"):
            link = push.select_one("a.u-link[href]")
            if not link:
                continue

            art_url = urljoin(self.base_url, link["href"])
            title = link.get_text(strip=True) or push.get_text(strip=True)
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
        resp = self.session.get(resource.url, timeout=30)
        resp.raise_for_status()
        data = resp.content
        resource.raw_content = data
        resource.meta = resource.meta or {}

        if resource.type == ResourceType.HTML:
            html = data.decode(resp.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            # Titre propre
            h1 = soup.find("h1")
            if h1:
                resource.title = h1.get_text(strip=True)

            # Contenu HTML (optionnel)
            main_container = soup.find("main") or soup.body or soup
            html_text = main_container.get_text(separator="\n", strip=True)
            resource.meta["html_text"] = html_text
            resource.text = html_text

            # Lien PDF
            pdf_link = soup.select_one("div.m-cta--download a.m-cta[href]")
            if pdf_link:
                pdf_url = urljoin(self.base_url, pdf_link["href"])
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = resource.url
                logger.info("Resource: %s | PDF: %s", resource.url, pdf_url)
            else:
                logger.info("Resource: %s | PDF: none", resource.url)

        elif resource.type == ResourceType.PDF:
            # Tu ne veux pas extraire le contenu PDF pour l'instant
            resource.text = None

        return resource

    def _with_page(self, base: str, page: int) -> str:
        """
        Transforme rebond.p-1.html -> rebond.p-<page>.html
        en remplaçant la partie .p-<n>.html de façon robuste.
        """
        parsed = urlparse(base)
        path = parsed.path

        if ".p-" in path and path.endswith(".html"):
            head, tail = path.rsplit(".p-", 1)
            new_path = f"{head}.p-{page}.html"
        else:
            if path.endswith(".html"):
                base_no_ext = path[:-5]
                new_path = f"{base_no_ext}.p-{page}.html"
            else:
                new_path = f"{path}.p-{page}.html"

        return parsed._replace(path=new_path).geturl()
