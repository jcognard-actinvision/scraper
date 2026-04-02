import random
import time

import requests

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "StonelakeScraper/1.0 (+https://github.com/jcognard-actinvision/scraper)"
    }
)


def fetch_html(url: str, *, max_retries: int = 3, backoff_base: float = 0.5) -> str:
    for i in range(max_retries):
        resp = session.get(url, timeout=30)
        if resp.ok:
            return resp.text
        sleep = backoff_base * (2**i) + random.random() * 0.1
        time.sleep(sleep)
    resp.raise_for_status()
    return ""  # pragma: no cover


def fetch_binary(url: str, *, max_retries: int = 3) -> bytes:
    for _ in range(max_retries):
        resp = session.get(url, timeout=60)
        if resp.ok:
            return resp.content
        time.sleep(1)
    resp.raise_for_status()
    return b""
