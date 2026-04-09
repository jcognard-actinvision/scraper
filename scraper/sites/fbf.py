import logging
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger("scraper.fbf")

LISTING_URLS = [
    "https://www.fbf.fr/fr/rubrique-etudes-et-chiffres-cles/autres-enquetes-et-etudes/",
    "https://www.fbf.fr/fr/rubrique-etudes-et-chiffres-cles/chiffres-cles/",
    "https://www.fbf.fr/fr/rubrique-etudes-et-chiffres-cles/emploi/",
    "https://www.fbf.fr/fr/rubrique-etudes-et-chiffres-cles/image-et-pratique-bancaire/",
    "https://www.fbf.fr/fr/rubrique-etudes-et-chiffres-cles/observatoire-des-credits-aux-menages/",
]


class FBFScraper(SiteScraper):
    base_url = "https://www.fbf.fr"

    def iter_listing_urls(self) -> Iterable[str]:
        for url in LISTING_URLS:
            yield url

    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        soup = BeautifulSoup(html, "html.parser")

        container = soup.find("div", class_="category__content")
        resources = self._extract_resources_from_container(container, url)
        resources += self._fetch_more_listing_pages(soup, url)

        return resources

    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        resp = self.safe_get(resource.url)
        if resp is None:
            resource.meta["fetch_error"] = "html_unavailable"
            resource.text = None
            return resource

        if resource.type == ResourceType.HTML:
            article_url = resource.url
            html = resp.content.decode(resp.encoding or "utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            resource.meta["article_url"] = article_url

            h1 = soup.find("h1")
            if h1:
                resource.title = h1.get_text(strip=True)

            container = soup.find("main") or soup.find("article") or soup.body or soup
            html_text = container.get_text(separator="\n", strip=True)
            resource.meta["html_text"] = html_text

            pdf_link = soup.find("a", href=lambda h: h and h.lower().endswith(".pdf"))
            if pdf_link:
                pdf_url = urljoin(self.base_url, pdf_link["href"])
                resource.meta["pdf_url"] = pdf_url
                resource.meta["source_html"] = article_url

                logger.info("PDF for %s: %s", article_url, pdf_url)

                pdf_resp = self.safe_get(pdf_url)
                if pdf_resp is not None:
                    resource.type = ResourceType.PDF
                    resource.raw_content = pdf_resp.content
                    resource.text = None
                    return resource

                resource.meta["pdf_error"] = "pdf_unavailable"

            resource.raw_content = resp.content
            resource.text = html_text
            return resource

        if resource.type == ResourceType.PDF:
            resource.raw_content = resp.content
            resource.text = None
            return resource

        resource.raw_content = resp.content
        resource.text = None
        return resource

    def _fetch_more_listing_pages(
        self, soup: BeautifulSoup, listing_url: str
    ) -> List[Resource]:
        form = soup.find("form", id="category-posts-filter")
        if not form:
            return []

        def _value(name: str, default: str | None = None) -> str | None:
            inp = form.find("input", {"name": name})
            if inp and inp.has_attr("value"):
                return inp["value"]
            return default

        category_id = _value("category_posts[categoryId]")
        sort = _value("category_posts[sort]", "post_date")
        token = _value("category_posts[_token]")

        if not category_id or not token:
            return []

        ajax_url = urljoin(self.base_url, "/fr/ajax-post/filtered-posts-page")

        page = 2
        all_resources: List[Resource] = []

        while True:
            data = {
                "category_posts[sort]": sort,
                "category_posts[categoryId]": category_id,
                "category_posts[page]": str(page),
                "category_posts[_token]": token,
            }

            resp = self.session.post(
                ajax_url,
                data=data,
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=30,
            )

            if not resp.ok:
                break

            html_fragment = resp.text.strip()
            if not html_fragment:
                break

            fragment_soup = BeautifulSoup(html_fragment, "html.parser")
            container = fragment_soup

            new_resources = self._extract_resources_from_container(
                container, listing_url
            )
            if not new_resources:
                break

            all_resources.extend(new_resources)
            page += 1

        return all_resources

    def _extract_resources_from_container(
        self, container, listing_url: str
    ) -> List[Resource]:
        resources: List[Resource] = []
        if not container:
            return resources

        for article in container.find_all("article"):
            link = article.find("a", class_="card__link", href=True)
            if not link:
                continue

            art_url = urljoin(self.base_url, link["href"])
            title = link.get_text(strip=True) or article.get_text(strip=True)
            if not title:
                continue

            resources.append(
                Resource(
                    url=art_url,
                    type=ResourceType.HTML,
                    title=title,
                    meta={"listing_url": listing_url},
                )
            )

        return resources
