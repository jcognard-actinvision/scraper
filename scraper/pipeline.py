from __future__ import annotations

import importlib
import logging
from pathlib import Path
from urllib.parse import urljoin

from .adapters.base import BaseSiteAdapter
from .http import fetch_binary, fetch_html
from .models import ScrapedDocument, SiteConfig
from .parsing import make_soup, select_all_links
from .storage import init_site_output, save_document, save_raw_html

logger = logging.getLogger("scraper.pipeline")


def load_adapter(cfg: SiteConfig) -> BaseSiteAdapter:
    if not cfg.adapter:
        from .adapters.base import BaseSiteAdapter

        return BaseSiteAdapter(cfg)

    module_name, class_name = cfg.adapter.split(":")
    mod = importlib.import_module(module_name)
    cls = getattr(mod, class_name)
    return cls(cfg)


def generate_listing_urls(cfg: SiteConfig) -> list[str]:
    urls = []
    listing = cfg.listing
    if listing.pagination and listing.pagination.type == "page_param":
        for page in range(
            listing.pagination.start,
            listing.pagination.start + listing.pagination.max_pages,
        ):
            sep = "&" if "?" in listing.url else "?"
            urls.append(f"{listing.url}{sep}{listing.pagination.param}={page}")
    else:
        urls.append(listing.url)
    return urls


def iter_item_urls(cfg: SiteConfig) -> list[str]:
    urls = []
    for page_url in generate_listing_urls(cfg):
        html = fetch_html(page_url)
        soup = make_soup(html)
        for href in select_all_links(soup, cfg.selectors.item_link):
            urls.append(urljoin(cfg.base_url, href))
    return urls


def scrape_item(url: str, cfg: SiteConfig, adapter: BaseSiteAdapter) -> ScrapedDocument:
    html = fetch_html(url)
    soup = make_soup(html)

    raw_html_path = save_raw_html(cfg.id, url, html)

    pdf_urls: list[str] = []
    for sel in cfg.pdf.link_selectors:
        for href in select_all_links(soup, sel):
            pdf_urls.append(urljoin(cfg.base_url, href))

    pdf_files: list[str] = []
    output_dir = Path("scraper_output") / cfg.id
    output_dir.mkdir(parents=True, exist_ok=True)

    for pdf_url in pdf_urls:
        data = fetch_binary(pdf_url)
        filename = pdf_url.split("/")[-1] or "document.pdf"
        path = output_dir / filename
        path.write_bytes(data)
        pdf_files.append(str(path.relative_to(output_dir.parent)))

    doc = adapter.build_document(
        url=url, soup=soup, pdf_files=pdf_files, raw_html_path=raw_html_path
    )
    return doc


def run_site_scraper(cfg: SiteConfig) -> None:
    init_site_output(cfg.id)
    adapter = load_adapter(cfg)

    # si l'adapter a sa propre iter_item_urls, on l'utilise
    if hasattr(adapter, "iter_item_urls"):
        item_urls = adapter.iter_item_urls(cfg)  # type: ignore[arg-type]
    else:
        item_urls = iter_item_urls(cfg)

    logger.info("Site %s: %d item URLs", cfg.id, len(item_urls))
    for url in item_urls:
        doc = scrape_item(url, cfg, adapter)
        save_document(doc)
