from abc import ABC, abstractmethod
from typing import Iterable, List

import requests

from .models import Resource


class SiteScraper(ABC):
    base_url: str

    def __init__(self, session: requests.Session | None = None):
        from .http import get_session

        self.session = session or get_session()

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

    def run(self) -> List[Resource]:
        """
        Pipeline par défaut: parcours des listings puis extraction du contenu.
        """
        all_resources: List[Resource] = []
        for listing_url in self.iter_listing_urls():
            resp = self.session.get(listing_url, timeout=30)
            resp.raise_for_status()
            resources = self.extract_resources_from_listing(resp.text, listing_url)
            all_resources.extend(resources)

        # télécharger et parser le contenu
        completed: List[Resource] = []
        for res in all_resources:
            completed.append(self.extract_content(res))
        return completed
