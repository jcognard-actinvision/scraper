import time
from abc import ABC, abstractmethod
from typing import Callable, Iterable, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

from .models import Resource


class SiteScraper(ABC):
    base_url: str

    def __init__(self, session: requests.Session | None = None):
        from .http import get_session

        self.session = session or get_session()
        self.max_pages: int | None = None

    def set_max_pages(self, max_pages: int | None):
        """Optionnel : limite de pages pour les scrapers paginés."""
        self.max_pages = max_pages

    @abstractmethod
    def iter_listing_urls(self) -> Iterable[str]:
        """
        Renvoie les URLs des pages 'listing' (historique, archives, etc.)
        Pour ton cas Observatoire: une seule URL 'historique'.
        """
        ...

    @abstractmethod
    def extract_resources_from_listing(self, html: str, url: str) -> List[Resource]:
        """
        À partir d’une page de listing, renvoie la liste des Resources (HTML/PDF).
        """
        ...

    @abstractmethod
    def extract_content(self, resource: Resource) -> Resource:
        """
        Télécharge une Resource (HTML ou PDF) et remplit .raw_content et .text.
        """
        ...

    def safe_get(self, url: str, retries: int = 2, delay: float = 1.5):
        """GET avec retry simple, à réutiliser dans les sous-classes."""
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                return resp
            except Exception:
                if attempt < retries:
                    time.sleep(delay * (attempt + 1))
        return None

    def with_page_query(
        self, url: str, page: int, extra_params: dict | None = None
    ) -> str:
        """
        Ajoute/modifie le paramètre ?page=N + params supplémentaires.
        Utilisé par Banque de France / Crédit Agricole Immobilier.
        """
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        if extra_params:
            for k, v in extra_params.items():
                query.setdefault(k, v)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def iter_paginated_listing_urls(
        self,
        base_url: str,
        extract_resources_fn: Callable[[str, str], List[Resource]],
        first_page: int = 0,
    ) -> Iterable[str]:
        """
        Boucle de pagination générique:
        - GET base_url?page=N
        - s'arrête quand extract_resources_fn renvoie une liste vide
        ou qu'on a atteint self.max_pages.
        """
        page = first_page
        while self.max_pages is None or page < self.max_pages:
            url = self.with_page_query(base_url, page)
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()

            resources = extract_resources_fn(resp.text, url)
            if not resources:
                break

            yield url
            page += 1

    # ------------------------------
    # Pipeline par défaut
    # ------------------------------
    def run(self) -> List[Resource]:
        all_resources: List[Resource] = []
        for listing_url in self.iter_listing_urls():
            resp = self.session.get(listing_url, timeout=30)
            resp.raise_for_status()
            resources = self.extract_resources_from_listing(resp.text, listing_url)
            all_resources.extend(resources)

        completed: List[Resource] = []
        for res in all_resources:
            completed.append(self.extract_content(res))
        return completed
