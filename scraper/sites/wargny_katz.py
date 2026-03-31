import logging
from typing import Iterable, List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.wargny_katz")


class WargnyKatzScraper(SiteScraper):
    base_url = "https://www.wargny-katz.com"
    veille_base_url = (
        "https://www.wargny-katz.com/category/veille-juridique/page/1/?et_blog"
    )
    newsletter_url = "https://www.wargny-katz.com/category/newsletter/"

    def iter_listing_urls(self) -> Iterable[str]:
        page = 1

        while True:
            if self.max_pages is not None and page > self.max_pages:
                break

            url = self._with_page(self.veille_base_url, page)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = self.extract_resources_from_listing(resp.text, url)
            if not resources:
                logger.info("No resources found on %s, stopping pagination", url)
                break

            yield url
            page += 1

        yield self.newsletter_url

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")
        resources: List[Resource] = []
        seen_urls: set[str] = set()

        for link in soup.select("h2.entry-title a[href]"):
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

            title_node = soup.select_one("h3.entry-title") or soup.select_one(
                "h1.entry-title"
            )
            if title_node:
                resource.title = title_node.get_text(strip=True)

            content_node = soup.select_one("div.et_pb_post_content")
            if content_node:
                html_text = content_node.get_text(separator="\n", strip=True)
            else:
                html_text = (soup.find("main") or soup.body or soup).get_text(
                    separator="\n",
                    strip=True,
                )

            resource.meta["html_text"] = html_text
            resource.text = html_text

            pdf_link = self._extract_pdf_link(soup)
            if pdf_link:
                pdf_url = urljoin(self.base_url, pdf_link)
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = resource.url
                logger.info("Resource: %s | PDF: %s", resource.url, pdf_url)
            else:
                logger.info("Resource: %s | PDF: none", resource.url)

        elif resource.type == ResourceType.PDF:
            resource.text = None

        return resource

    def _extract_pdf_link(self, soup: BeautifulSoup) -> str | None:
        for link in soup.select("div.et_pb_post_content a[href]"):
            href = link.get("href")
            if not href:
                continue

            return href

        return None

    def _with_page(self, base: str, page: int) -> str:
        parsed = urlparse(base)
        path = parsed.path.rstrip("/")

        if "/page/" in path:
            head, _ = path.rsplit("/page/", 1)
            new_path = f"{head}/page/{page}/"
        else:
            new_path = f"{path}/page/{page}/"

        return parsed._replace(path=new_path).geturl()
