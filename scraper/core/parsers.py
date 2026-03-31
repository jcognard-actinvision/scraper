import logging

from bs4 import BeautifulSoup
from bs4.element import Tag

logger = logging.getLogger("scraper.parsers")


def clean_html_main(html, main_selector=None, remove_predicate=None) -> str:
    soup = BeautifulSoup(html, "html.parser")

    if main_selector:
        main = main_selector(soup)
    else:
        main = soup.find("main") or soup.body or soup

    if remove_predicate and isinstance(main, Tag):
        for tag in list(main.find_all(True)):
            if tag is None:
                continue
            try:
                if remove_predicate(tag):
                    snippet = tag.get_text(strip=True)[:80]
                    logger.debug(
                        "Removing tag <%s> classes=%s text=%r",
                        getattr(tag, "name", "?"),
                        getattr(tag, "get", lambda *_: None)("class"),
                        snippet,
                    )
                    tag.decompose()
            except Exception:
                # sécurité ultime: on ignore silencieusement
                continue

    return main.get_text(separator="\n", strip=True)


def extract_pdf_text(data: bytes) -> str:
    # Placeholder: implémenter avec pdfplumber/pypdf selon ton besoin
    return ""
