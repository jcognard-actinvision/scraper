from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ResourceType(str, Enum):
    HTML = "html"
    PDF = "pdf"


@dataclass
class Resource:
    url: str
    type: ResourceType
    title: str
    raw_content: bytes | None = None  # pour PDF ou HTML brut
    text: str | None = None  # texte extrait (HTML parsé, PDF OCR, etc.)
    meta: dict | None = None
