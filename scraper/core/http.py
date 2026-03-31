from typing import Optional

import requests


def get_session(user_agent: Optional[str] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {"User-Agent": user_agent or "Mozilla/5.0 (compatible; GenericScraper/1.0)"}
    )
    return s
