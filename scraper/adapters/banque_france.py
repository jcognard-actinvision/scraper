from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseSiteAdapter


class BanqueFranceAdapter(BaseSiteAdapter):
    def parse_date(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        # ex: "27/03/2026" ou "27 mars 2026" => adapter selon le site
        try:
            return datetime.strptime(raw.strip(), "%d/%m/%Y")
        except ValueError:
            return None

    def build_document(
        self,
        url: str,
        soup: BeautifulSoup,
        pdf_files: list[str],
    ):
        doc = super().build_document(url, soup, pdf_files)
        # Exemple: extraire des tags si besoin
        # tags = [...]
        # doc.tags = tags
        return doc
