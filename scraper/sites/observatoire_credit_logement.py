import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.observatoire")


class ObservatoireCreditLogementScraper(SiteScraper):
    base_url = "https://www.lobservatoirecreditlogement.fr"

    def iter_listing_urls(self) -> Iterable[str]:
        yield urljoin(self.base_url, "/historique")

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")

        header = soup.find(
            lambda tag: (
                tag.name in ["h2", "h3"]
                and "Analyses du marché immobilier mensuelles" in tag.get_text()
            )
        )
        if not header:
            return []

        resources: List[Resource] = []
        for tag in header.find_all_next():
            if (
                tag.name in ["h2", "h3"]
                and "Analyses du marché immobilier mensuelles" not in tag.get_text()
                and "Analyses du marché immobilier trimestrielles" in tag.get_text()
            ):
                break

            if tag.name == "h3":
                mois = tag.get_text(strip=True)
                link_tag = tag.find_next(
                    "a", class_="link_suite", title="En savoir plus"
                )
                if link_tag and link_tag.get("href"):
                    art_url = urljoin(self.base_url, link_tag["href"])
                    resources.append(
                        Resource(
                            url=art_url,
                            type=ResourceType.HTML,
                            title=mois,
                            meta={"listing_url": url},
                        )
                    )

        logger.info("Found %d resources on %s", len(resources), url)
        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resp = self.session.get(resource.url, timeout=30)
        resp.raise_for_status()

        resource.meta = resource.meta or {}

        if resource.type == ResourceType.HTML:
            article_url = resource.url

            html = resp.content.decode(resp.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            resource.meta["article_url"] = article_url

            title_tag = soup.find(["h1", "h2"])
            if title_tag:
                resource.title = title_tag.get_text(strip=True)

            container = (
                soup.find("div", id="page-publications")
                or soup.find("main")
                or soup.body
                or soup
            )
            html_text = container.get_text(separator="\n", strip=True)
            resource.meta["html_text"] = html_text

            pdf_url = None
            box = soup.find("div", class_="box-download")
            if box:
                a = box.find("a", href=True)
                if a and a["href"]:
                    candidate = urljoin(self.base_url, a["href"])
                    if candidate.lower().endswith(".pdf"):
                        pdf_url = candidate

            if pdf_url:
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = article_url
                logger.info("PDF for %s: %s", article_url, pdf_url)

                try:
                    pdf_resp = self.session.get(pdf_url, timeout=30)
                    pdf_resp.raise_for_status()

                    resource.type = ResourceType.PDF
                    resource.raw_content = pdf_resp.content
                    resource.text = None
                    return resource

                except Exception as e:
                    logger.warning("Failed to fetch PDF %s: %s", pdf_url, e)

            resource.raw_content = resp.content
            resource.text = html_text
            return resource
