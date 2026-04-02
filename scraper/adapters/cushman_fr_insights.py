from __future__ import annotations

import html
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests

from ..models import SiteConfig
from .base import BaseSiteAdapter

logger = logging.getLogger(__name__)


class CushmanFrInsightsAdapter(BaseSiteAdapter):
    """
    Adapter Cushman & Wakefield France Insights, basé sur l'ancien scraper
    C&W Coveo mais adapté au nouveau pipeline.

    - iter_item_urls interroge l'API Coveo et renvoie une liste d'URLs d'articles
      publics (www.cushmanwakefield.com).
    - build_document est hérité de BaseSiteAdapter (title + content via
      les sélecteurs YAML).
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

    def __init__(self, cfg: SiteConfig) -> None:
        super().__init__(cfg)
        self.session = requests.Session()
        for k, v in self.DEFAULT_HEADERS.items():
            self.session.headers.setdefault(k, v)

    # ------------------------------------------------------------------
    # Pagination Coveo → URLs d’articles
    # ------------------------------------------------------------------
    def _build_search_payload(
        self, first_result: int, number_of_results: int
    ) -> dict[str, Any]:
        # Copié de l'ancien scraper, inchangé
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

    def _prefer_public_cw_url(self, url: str | None) -> str | None:
        """
        Nettoie la string et remplace sitecore-www.cushmanwakefield.com par
        www.cushmanwakefield.com (copié de l'ancien code).
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

    def _should_skip_path(self, path: str) -> bool:
        """
        Filtre quelques URLs non pertinentes (people, properties).
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

    def _url_from_result(self, item: dict[str, Any]) -> str | None:
        raw = item.get("raw", {}) or {}

        click_uri = item.get("clickUri") or raw.get("clickuri")
        printable_uri = item.get("printableUri") or raw.get("printableuri")
        clickable_uri = raw.get("clickableuri")
        sys_clickable_uri = raw.get("sysclickableuri")
        sys_uri = raw.get("sysuri")
        uri = item.get("uri") or raw.get("uri")

        url = self._prefer_public_cw_url(
            click_uri
            or printable_uri
            or clickable_uri
            or sys_clickable_uri
            or sys_uri
            or uri
        )
        if not url:
            return None

        path = urlparse(url).path.lower()
        if self._should_skip_path(path):
            return None

        return url

    def iter_item_urls(self, cfg: SiteConfig) -> list[str]:
        """
        Appelle l’API Coveo, pagine, et renvoie la liste des URLs d’articles.
        """
        urls: list[str] = []

        page_size = 12
        first_result = 0
        page_index = 1
        total_count: int | None = None

        max_pages = cfg.listing.pagination.max_pages if cfg.listing.pagination else None

        while True:
            if max_pages is not None and page_index > max_pages:
                logger.info(
                    "C&W: stop pagination page_index=%s > max_pages=%s",
                    page_index,
                    max_pages,
                )
                break

            payload = self._build_search_payload(
                first_result=first_result,
                number_of_results=page_size,
            )

            logger.info("C&W: calling Coveo API, firstResult=%s", first_result)
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
                "C&W: %s results for firstResult=%s",
                len(results),
                first_result,
            )

            if not results:
                break

            kept = 0
            for item in results:
                url = self._url_from_result(item)
                if not url:
                    continue
                urls.append(url)
                kept += 1

            if kept == 0:
                logger.info("C&W: no usable URLs kept for firstResult=%s", first_result)

            page_size_returned = len(results)
            first_result += page_size_returned
            page_index += 1

            if page_size_returned < page_size:
                logger.info(
                    "C&W: stop pagination returned=%s < page_size=%s",
                    page_size_returned,
                    page_size,
                )
                break

            if total_count is not None and first_result >= total_count:
                logger.info(
                    "C&W: stop pagination firstResult=%s >= totalCount=%s",
                    first_result,
                    total_count,
                )
                break

        logger.info("C&W: total article URLs collected: %s", len(urls))
        return urls

    # ------------------------------------------------------------------
    # Optionnel : parse_date si tu as encore un champ date dans SiteConfig
    # ------------------------------------------------------------------
    def parse_date(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        month_map = {
            "janvier": 1,
            "février": 2,
            "fevrier": 2,
            "mars": 3,
            "avril": 4,
            "mai": 5,
            "juin": 6,
            "juillet": 7,
            "août": 8,
            "aout": 8,
            "septembre": 9,
            "octobre": 10,
            "novembre": 11,
            "décembre": 12,
            "decembre": 12,
        }
        parts = raw.split()
        if len(parts) == 3:
            try:
                day = int(parts[0])
                month = month_map.get(parts[1].lower(), 1)
                year = int(parts[2])
                return datetime(year, month, day)
            except ValueError:
                return None
        return None
