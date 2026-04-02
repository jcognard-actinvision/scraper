from __future__ import annotations

from datetime import datetime

from .base import BaseSiteAdapter


class CushmanFrAdapter(BaseSiteAdapter):
    def parse_date(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        # ex: "27 mars 2026" -> adapter avec dateutil ou mapping FR
        month_map = {
            "janvier": 1,
            "février": 2,
            "mars": 3,
            "avril": 4,
            "mai": 5,
            "juin": 6,
            "juillet": 7,
            "août": 8,
            "septembre": 9,
            "octobre": 10,
            "novembre": 11,
            "décembre": 12,
        }
        parts = raw.split()
        if len(parts) == 3:
            day = int(parts[0])
            month = month_map.get(parts[1].lower(), 1)
            year = int(parts[2])
            return datetime(year, month, day)
        return None
