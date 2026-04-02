from bs4 import BeautifulSoup


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def select_one_text(soup: BeautifulSoup, selector: str | None) -> str | None:
    if not selector:
        return None
    el = soup.select_one(selector)
    if not el:
        return None
    return el.get_text(strip=True) or None


def select_all_links(soup: BeautifulSoup, selector: str) -> list[str]:
    links: list[str] = []
    for a in soup.select(selector):
        href = a.get("href")
        if href:
            links.append(href)
    return links


def extract_main_text(soup: BeautifulSoup, selector: str | None) -> str | None:
    if not selector:
        return None
    node = soup.select_one(selector)
    if not node:
        return None
    text = node.get_text("\n", strip=True)
    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return text or None
