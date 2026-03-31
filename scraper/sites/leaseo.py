import json
import logging
from typing import Iterable, List

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.leaseo")


class LeaseoScraper(SiteScraper):
    base_url = "https://www.leaseo.fr"
    ajax_url = "https://www.leaseo.fr/actualitesMore"
    page_size = 6  # 6 articles par page (offset = 0, 6, 12, ...)

    def iter_listing_urls(self) -> Iterable[str]:
        """
        Parcourt les pages via /actualitesMore?offset=N&categorie=0
        jusqu'à ce que le JSON soit vide ou que max_pages soit atteint.
        On ne fait ici que générer les URLs de listing.
        """
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

            # Si le JSON contient encore des articles, on traite ce "listing"
            # On réutilise l'URL complète (avec offset) comme identifiant
            yield resp.url

            offset += self.page_size

    def extract_resources_from_listing(
        self, html_or_json: str, url: str
    ) -> List[Resource]:
        """
        html_or_json est en réalité du JSON (liste d'objets comme dans ton exemple).
        On crée une Resource HTML par entrée.
        """
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
        """
        Extraction HTML :
        - titre : section.blocTitre h1
        - contenu : section.blocContenu (texte)
        """
        resource.meta = resource.meta or {}

        resp = self.safe_get(resource.url)
        if resp is None:
            resource.meta["fetch_error"] = "html_unavailable"
            resource.text = None
            return resource

        data = resp.content
        resource.raw_content = data

        html = data.decode(resp.encoding or "utf-8", errors="ignore")
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

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
        resource.text = html_text

        return resource
