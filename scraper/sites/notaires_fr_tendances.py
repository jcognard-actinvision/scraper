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

        data = resp.content
        resource.raw_content = data

        if resource.type == ResourceType.HTML:
            html = data.decode(resp.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

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
            resource.text = html_text

        elif resource.type == ResourceType.PDF:
            resource.text = None

        return resource
