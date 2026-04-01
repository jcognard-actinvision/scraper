from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.core.models import Resource, ResourceType


def clean_text(text: str | None) -> str | None:
    if not text:
        return None
    text = "\n".join(line.strip() for line in text.splitlines())
    text = "\n".join(line for line in text.splitlines() if line)
    text = text.strip()
    return text or None


def extract_text_from_nodes(nodes: list) -> str | None:
    parts: list[str] = []
    for node in nodes:
        txt = clean_text(node.get_text("\n", strip=True))
        if txt:
            parts.append(txt)
    if not parts:
        return None
    return "\n\n".join(parts)


def first_non_empty_text(soup: BeautifulSoup, selectors: Iterable[str]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            txt = clean_text(node.get_text(" ", strip=True))
            if txt:
                return txt
    return None


def normalize_domain(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def set_pdf_resource(resource: Resource, pdf_url: str) -> Resource:
    resource.type = ResourceType.PDF
    resource.url = pdf_url
    resource.text = None
    resource.raw_content = None
    resource.meta = resource.meta or {}
    resource.meta["pdf_url"] = pdf_url
    resource.meta["content_source"] = "pdf_url"
    return resource


def set_html_resource(resource: Resource, text: str | None) -> Resource:
    resource.type = ResourceType.HTML
    resource.text = text
    resource.raw_content = None
    resource.meta = resource.meta or {}
    resource.meta["html_text"] = text
    resource.meta["content_source"] = "html"
    return resource


@dataclass
class ExtractionResult:
    matched: bool
    resource: Resource


class BaseStrategy:
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        raise NotImplementedError

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        raise NotImplementedError


class SocieteGeneraleScenarioEcoPdfStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return "societegenerale.com" in normalize_domain(url) and "scenario-eco" in url

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            label = clean_text(a.get_text(" ", strip=True)) or ""
            if (
                href.lower().endswith(".pdf")
                or "download" in label.lower()
                or "télécharger" in label.lower()
            ):
                pdf_url = urljoin(resource.url, href)
                return set_pdf_resource(resource, pdf_url)
        resource.meta = resource.meta or {}
        resource.meta["pdf_error"] = "No scenario-eco PDF link found"
        return resource


class SocieteGeneraleCkeContentStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return (
            "societegenerale.com" in normalize_domain(url)
            and soup.select_one("div.cke-content") is not None
        )

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        text = extract_text_from_nodes(list(soup.select("div.cke-content")))
        return set_html_resource(resource, text)


class ConfrontationsPdfStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return "confrontations.org" in normalize_domain(url)

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        for a in soup.select("a.wp-block-button__link[href]"):
            label = clean_text(a.get_text(" ", strip=True)) or ""
            if (
                "télécharger l’article" in label.lower()
                or "telecharger l’article" in label.lower()
                or "télécharger" in label.lower()
            ):
                pdf_url = urljoin(resource.url, a["href"])
                return set_pdf_resource(resource, pdf_url)
        resource.meta = resource.meta or {}
        resource.meta["pdf_error"] = "No Confrontations PDF button found"
        return resource


class WanSquareHtmlStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return (
            "wansquare.com" in normalize_domain(url)
            and soup.select_one("div.mediumcontent") is not None
        )

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        text = extract_text_from_nodes(list(soup.select("div.mediumcontent")))
        return set_html_resource(resource, text)


class AgefiHtmlStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return (
            "agefi.fr" in normalize_domain(url)
            and soup.select_one("div.Article") is not None
        )

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        text = extract_text_from_nodes(list(soup.select("div.Article")))
        return set_html_resource(resource, text)


class RevueBanqueHtmlStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return "revue-banque.fr" in normalize_domain(url) and (
            soup.select_one("div.firstBlockDetail") is not None
            or soup.select_one("div.secondBlockDetail") is not None
        )

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        nodes = []
        first = soup.select_one("div.firstBlockDetail")
        second = soup.select_one("div.secondBlockDetail")
        if first:
            nodes.append(first)
        if second:
            nodes.append(second)
        text = extract_text_from_nodes(nodes)
        return set_html_resource(resource, text)


class WholesaleSocieteGeneraleHtmlStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return (
            "wholesale.banking.societegenerale.com" in normalize_domain(url)
            and soup.select_one("div.containerContent") is not None
        )

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        text = extract_text_from_nodes(list(soup.select("div.containerContent")))
        return set_html_resource(resource, text)


class GenericPdfLinkStrategy(BaseStrategy):
    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").lower()
            if ".pdf" in href:
                return True
        return False

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if ".pdf" in href.lower():
                return set_pdf_resource(resource, urljoin(resource.url, href))
        resource.meta = resource.meta or {}
        resource.meta["pdf_error"] = "No generic PDF link found"
        return resource


class GenericArticleHtmlStrategy(BaseStrategy):
    HTML_SELECTORS = [
        "div.cke-content",
        "div.mediumcontent",
        "div.Article",
        "div.containerContent",
        "article",
        "main",
    ]

    def matches(self, url: str, soup: BeautifulSoup) -> bool:
        return any(soup.select_one(sel) is not None for sel in self.HTML_SELECTORS)

    def extract(self, resource: Resource, soup: BeautifulSoup) -> Resource:
        for sel in self.HTML_SELECTORS:
            nodes = list(soup.select(sel))
            if not nodes:
                continue
            text = extract_text_from_nodes(nodes)
            if text and len(text) > 80:
                resource.meta = resource.meta or {}
                resource.meta["html_selector"] = sel
                return set_html_resource(resource, text)
        resource.meta = resource.meta or {}
        resource.meta["html_error"] = "No usable HTML content found"
        return resource


DEFAULT_STRATEGIES = [
    SocieteGeneraleScenarioEcoPdfStrategy(),
    SocieteGeneraleCkeContentStrategy(),
    ConfrontationsPdfStrategy(),
    WanSquareHtmlStrategy(),
    AgefiHtmlStrategy(),
    RevueBanqueHtmlStrategy(),
    WholesaleSocieteGeneraleHtmlStrategy(),
    GenericPdfLinkStrategy(),
    GenericArticleHtmlStrategy(),
]
