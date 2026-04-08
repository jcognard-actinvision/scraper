import html
import json
import logging
import re
from typing import Any, Iterable
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup

from scraper.core.base_site import SiteScraper
from scraper.core.models import Resource, ResourceType

logger = logging.getLogger(__name__)


class CushmanWakefieldScraper(SiteScraper):
    """
    Scraper Cushman & Wakefield via l'API Coveo.

    - Pagination sur /coveo/rest/search/v2
    - Priorité à clickUri (domaine public www.cushmanwakefield.com)
    - Fallback sur printableUri
    - Normalisation des URLs sitecore-www -> www
    - Extraction de texte HTML (summary + contenu)
    """

    SEARCH_URL = "https://www.cushmanwakefield.com/coveo/rest/search/v2"

    DEFAULT_HEADERS = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.cushmanwakefield.com",
        "Referer": "https://www.cushmanwakefield.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for key, value in self.DEFAULT_HEADERS.items():
            self.session.headers.setdefault(key, value)

    # ------------------------------------------------------------------
    # Pipeline d’URLs de listing
    # ------------------------------------------------------------------
    def iter_listing_urls(self) -> Iterable[str]:
        """
        On ne renvoie qu’une pseudo-URL "API" : le run.py va faire un GET dessus.
        On gère la pagination à l’intérieur d'extract_resources_from_listing().
        """
        yield self.SEARCH_URL

    def extract_resources_from_listing(
        self, html_text: str, url: str
    ) -> list[Resource]:
        """
        Ici, `html_text` est en réalité une string vide (GET sur l’URL API),
        on ignore ce paramètre et on appelle l’API Coveo nous-mêmes via POST.

        On pagine jusqu’à self.max_pages ou jusqu’à épuisement des résultats.
        """
        all_resources: list[Resource] = []

        page_size = 12
        first_result = 0
        page_index = 1
        total_count = None

        while True:
            if self.max_pages is not None and page_index > self.max_pages:
                logger.info(
                    "C&W: stopping pagination because page_index=%s > max_pages=%s",
                    page_index,
                    self.max_pages,
                )
                break

            payload = self._build_search_payload(
                first_result=first_result,
                number_of_results=page_size,
            )

            logger.info("C&W: calling Coveo listing API, firstResult=%s", first_result)
            resp = self.session.post(
                self.SEARCH_URL,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()

            data = resp.json()
            results = data.get("results", []) or []
            total_count = data.get("totalCount", total_count)

            logger.info(
                "C&W: found %s results for firstResult=%s",
                len(results),
                first_result,
            )

            if not results:
                break

            kept = 0
            for item in results:
                res = self._resource_from_result(item, listing_url=self.SEARCH_URL)
                if not res:
                    continue
                all_resources.append(res)
                kept += 1

            if kept == 0:
                logger.info(
                    "C&W: no usable resources kept for firstResult=%s", first_result
                )

            page_size_returned = len(results)
            first_result += page_size_returned
            page_index += 1

            if page_size_returned < page_size:
                logger.info(
                    "C&W: stopping pagination because returned=%s < page_size=%s",
                    page_size_returned,
                    page_size,
                )
                break

            if total_count is not None and first_result >= total_count:
                logger.info(
                    "C&W: stopping pagination because firstResult=%s >= totalCount=%s",
                    first_result,
                    total_count,
                )
                break

        logger.info(
            "C&W: total resources collected across pages: %s", len(all_resources)
        )
        return all_resources

    # ------------------------------------------------------------------
    # Téléchargement / extraction de contenu
    # ------------------------------------------------------------------
    def extract_content(self, resource: Resource) -> Resource:
        resource.meta = resource.meta or {}

        # Cas PDF : on télécharge juste le binaire, sans extraction de texte
        if resource.type == ResourceType.PDF:
            primary_url = self._prefer_public_cw_url(resource.url)
            if not primary_url:
                resource.meta["fetch_error"] = "no_pdf_url"
                resource.text = None
                return resource

            logger.info("C&W: fetching PDF %s", primary_url)
            try:
                resp = self.session.get(primary_url, timeout=30)
                resp.raise_for_status()
            except Exception as exc:
                logger.warning("C&W: failed to fetch PDF %s: %s", primary_url, exc)
                resource.meta["fetch_error"] = str(exc)
                resource.text = None
                return resource

            resource.url = primary_url
            resource.raw_content = resp.content
            resource.meta["fetched_url"] = primary_url
            resource.meta["final_url"] = resp.url
            resource.text = None
            return resource

        # Cas HTML : logique actuelle inchangée
        primary_url = self._prefer_public_cw_url(resource.url)
        fallback_url = self._prefer_public_cw_url(resource.meta.get("printable_uri"))

        candidate_urls: list[str] = []
        for u in [primary_url, fallback_url]:
            if u and u not in candidate_urls:
                candidate_urls.append(u)

        last_error: Exception | None = None
        resp = None
        fetched_url: str | None = None

        for u in candidate_urls:
            logger.info("C&W: fetching article %s", u)
            try:
                resp = self.session.get(u, timeout=20)
                resp.raise_for_status()
                fetched_url = u
                break
            except Exception as exc:
                last_error = exc
                logger.warning("C&W: failed on article %s: %s", u, exc)

        if resp is None:
            resource.meta["fetch_error"] = (
                str(last_error) if last_error else "unknown fetch error"
            )
            resource.text = None
            return resource

        resource.url = fetched_url or resource.url
        resource.raw_content = resp.content
        resource.meta["fetched_url"] = fetched_url
        resource.meta["final_url"] = resp.url

        soup = BeautifulSoup(resp.text, "html.parser")

        title = self._first_text(
            soup,
            [
                "h1",
                ".mix_hero-pageTitle h1",
                ".page-title",
                "meta[property='og:title']",
            ],
        )
        if title:
            resource.title = title

        def clean_node(node):
            if not node:
                return None

            for bad in node.select(
                """
                .social-share,
                .share,
                .share-block,
                .share-links,
                .addtoany,
                [class*="share"],
                [aria-label*="share" i],
                a[href*="facebook.com"],
                a[href*="twitter.com"],
                a[href*="x.com"],
                a[href*="linkedin.com"]
                """
            ):
                bad.decompose()

            for bad in node.find_all(
                string=re.compile(
                    r"(Share:|Share on Facebook|Share on Twitter|Share on LinkedIn)",
                    re.I,
                )
            ):
                parent = bad.parent
                if parent:
                    parent.decompose()

            return node

        summary_node = clean_node(soup.select_one("div.page-summary"))
        content_node = clean_node(soup.select_one("div.page-content-body"))

        summary_text = (
            self._clean_text(summary_node.get_text(separator="\n", strip=True))
            if summary_node
            else ""
        )
        content_text = (
            self._clean_text(content_node.get_text(separator="\n", strip=True))
            if content_node
            else ""
        )

        parts = []
        if summary_text:
            parts.append(summary_text)
        if content_text:
            parts.append(content_text)

        if not parts:
            fallback_candidates = [
                ".article-body",
                ".rich-text",
                "article",
                "main",
            ]

            for selector in fallback_candidates:
                node = clean_node(soup.select_one(selector))
                if not node:
                    continue

                txt = self._clean_text(node.get_text(separator="\n", strip=True))
                if txt and len(txt) > 120:
                    parts.append(txt)
                    resource.meta["html_fallback_selector"] = selector
                    break

        text = "\n\n".join(parts).strip()

        resource.text = text or None
        resource.meta["html_text"] = resource.text
        resource.meta["summary_text"] = summary_text or None
        resource.meta["content_text"] = content_text or None

        return resource

    # ------------------------------------------------------------------
    # Helpers API / mapping
    # ------------------------------------------------------------------
    def _build_search_payload(
        self, first_result: int, number_of_results: int
    ) -> dict[str, Any]:
        return {
            "aq": "",
            "cq": '(@z95xlanguage=="fr-FR") (@z95xlatestversion==1) (@source=="Coveo_cw-prod-amrgws-cd-web_index - PRODUCTION")',
            "searchHub": "Insights Search",
            "tab": "All",
            "locale": "fr",
            "timezone": "Europe/Paris",
            "firstResult": first_result,
            "numberOfResults": number_of_results,
            "sortCriteria": "@publishz32xdisplayz32xdate descending",
            "enableDidYouMean": False,
            "excerptLength": 200,
            "pipeline": "Insights",
            "context": {"device": "Default", "isAnonymous": "true"},
            "facets": [],
            "fieldsToInclude": [
                "clickUri",
                "printableUri",
                "title",
                "excerpt",
                "firstSentences",
                "hasHtmlVersion",
                "hasMobileHtmlVersion",
                "filetype",
                "language",
                "date",
                "articlepublishedyear",
                "articlecategory",
                "pagez32xsummary",
                "pagez32xtitle",
                "sysuri",
                "sysclickableuri",
                "sysprintableuri",
                "clickableuri",
                "urllink",
                "category",
                "z95xtemplatename",
            ],
            "q": "",
        }

    def _resource_from_result(
        self, item: dict[str, Any], listing_url: str
    ) -> Resource | None:
        raw = item.get("raw", {}) or {}

        click_uri = item.get("clickUri") or raw.get("clickuri")
        printable_uri = item.get("printableUri") or raw.get("printableuri")
        clickable_uri = raw.get("clickableuri")
        sys_clickable_uri = raw.get("sysclickableuri")
        sys_uri = raw.get("sysuri")
        uri = item.get("uri") or raw.get("uri")

        title = (
            item.get("title")
            or raw.get("systitle")
            or raw.get("ftitle9708")
            or raw.get("Title")
        )

        url = self._prefer_public_cw_url(
            click_uri
            or printable_uri
            or clickable_uri
            or sys_clickable_uri
            or sys_uri
            or uri
        )

        if not url:
            logger.debug("C&W: skipping item without usable URL: %s", title)
            return None

        path = urlparse(url).path.lower()
        if self._should_skip_path(path):
            logger.info("C&W: skipping non-article path %s", url)
            return None

        filetype = (raw.get("filetype") or item.get("filetype") or "").lower()

        summary = (
            item.get("excerpt")
            or item.get("firstSentences")
            or raw.get("pagez32xsummary")
            or ""
        )
        summary = self._clean_text(summary)

        meta = {
            "click_uri": self._prefer_public_cw_url(click_uri),
            "printable_uri": self._prefer_public_cw_url(printable_uri),
            "clickable_uri": self._prefer_public_cw_url(clickable_uri),
            "sys_clickable_uri": self._prefer_public_cw_url(sys_clickable_uri),
            "sys_uri": self._prefer_public_cw_url(sys_uri),
            "api_uri": uri,
            "filetype": filetype,
            "category": raw.get("category") or item.get("category"),
            "template": raw.get("z95xtemplatename"),
            "date": item.get("date") or raw.get("date"),
            "language": raw.get("language") or item.get("language"),
            "summary": summary,
            "has_html_version": item.get("hasHtmlVersion"),
            "has_mobile_html_version": item.get("hasMobileHtmlVersion"),
            "listing_url": listing_url,
        }

        logger.info(
            "C&W: resource url=%s | click=%s | printable=%s | filetype=%s",
            url,
            meta["click_uri"],
            meta["printable_uri"],
            filetype,
        )

        # Si Coveo indique un PDF, on crée directement une ressource PDF
        if filetype == "pdf" or url.lower().endswith(".pdf"):
            return Resource(
                url=url,
                type=ResourceType.PDF,
                title=self._clean_text(title) or url,
                text=None,
                meta=meta,
            )

        # Sinon, ressource HTML comme avant
        return Resource(
            url=url,
            type=ResourceType.HTML,
            title=self._clean_text(title) or url,
            text=summary or None,
            meta=meta,
        )

    # ------------------------------------------------------------------
    # Helpers utilitaires
    # ------------------------------------------------------------------
    def _should_skip_path(self, path: str) -> bool:
        """
        Filtre quelques URLs non pertinentes (people, properties).
        À adapter selon ton besoin.
        """
        skip_prefixes = (
            "/en/united-states/people/",
            "/en/people/",
            "/fr-fr/france/people/",
            "/en/united-states/properties/",
            "/en/properties/",
            "/fr-fr/france/properties/",
        )
        return path.startswith(skip_prefixes)

    def _prefer_public_cw_url(self, url: str | None) -> str | None:
        """
        - nettoie la string,
        - remplace sitecore-www.cushmanwakefield.com par www.cushmanwakefield.com.
        """
        if not url:
            return None

        url = html.unescape(str(url).strip())
        if not url:
            return None

        parsed = urlparse(url)
        netloc = parsed.netloc.lower()

        if netloc == "sitecore-www.cushmanwakefield.com":
            parsed = parsed._replace(netloc="www.cushmanwakefield.com")
            url = urlunparse(parsed)

        return url

    def _first_text(self, soup: BeautifulSoup, selectors: list[str]) -> str | None:
        for selector in selectors:
            if selector.startswith("meta["):
                node = soup.select_one(selector)
                if node and node.get("content"):
                    txt = self._clean_text(node.get("content"))
                    if txt:
                        return txt
                continue

            node = soup.select_one(selector)
            if node:
                txt = self._clean_text(node.get_text(separator=" ", strip=True))
                if txt:
                    return txt
        return None

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""

        if not isinstance(value, str):
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            else:
                value = str(value)

        value = html.unescape(value)
        value = re.sub(r"<[^>]+>", " ", value)
        value = value.replace("\xa0", " ")
        value = re.sub(r"\s+", " ", value).strip()
        return value
