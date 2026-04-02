from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import ScrapedDocument

OUTPUT_DIR = Path("scraper_output")


def init_site_output(source_id: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{source_id}.jsonl"
    out_path.write_text("", encoding="utf-8")
    return out_path


def _site_dir(source_id: str) -> Path:
    path = OUTPUT_DIR / source_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_raw_html(source_id: str, url: str, html: str) -> str:
    html_dir = _site_dir(source_id) / "raw_html"
    html_dir.mkdir(parents=True, exist_ok=True)

    slug = hashlib.sha1(url.encode("utf-8")).hexdigest()
    out_path = html_dir / f"{slug}.html"
    out_path.write_text(html, encoding="utf-8")

    return str(out_path)


def save_document(doc: ScrapedDocument) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{doc.source_id}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")


def save_documents(source_id: str, docs: Iterable[ScrapedDocument]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"{source_id}.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        for doc in docs:
            if doc.source_id != source_id:
                continue
            f.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")
