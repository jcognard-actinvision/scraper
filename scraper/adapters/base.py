from __future__ import annotations

from datetime import datetime

from bs4 import BeautifulSoup

from ..models import ScrapedDocument, SiteConfig
from ..parsing import extract_main_text, select_one_text


class BaseSiteAdapter:
    def __init__(self, cfg: SiteConfig) -> None:
        self.cfg = cfg

    def parse_date(self, raw: str | None) -> datetime | None:
        return None

    def build_document(
        self,
        url: str,
        soup: BeautifulSoup,
        pdf_files: list[str],
        raw_html_path: str | None = None,
    ) -> ScrapedDocument:
        title = select_one_text(soup, self.cfg.selectors.title)
        text = extract_main_text(soup, self.cfg.selectors.content)

        return ScrapedDocument(
            id=url,
            source_id=self.cfg.id,
            url=url,
            title=title,
            text=text,
            pdf_files=pdf_files,
            raw_html_path=raw_html_path,
            extra={},
        )
