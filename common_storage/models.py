from dataclasses import dataclass, field
from typing import Any


@dataclass
class StoredDocument:
    source_name: str
    source_url: str | None
    document_url: str
    title: str | None
    document_type: str
    mime_type: str | None
    content: bytes | None = None
    text_content: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoredError:
    run_id: str
    source_name: str
    url: str | None
    step: str
    error_type: str
    error_message: str
    error_stack: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
