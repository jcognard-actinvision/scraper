from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import yaml  # pip install pyyaml

from .gmail_client import (
    decode_body_part,
    get_gmail_service,
    get_message_full,
    iter_messages_by_label,
)


def load_config(path: str = "gmail_fetcher/config.yaml") -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_main_body(payload: dict) -> dict[str, str | None]:
    """
    Renvoie un dict { 'text': ..., 'html': ... } en parcourant les parties.
    """
    text_parts: list[str] = []
    html_parts: list[str] = []

    def walk(part: dict):
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            txt = decode_body_part(part)
            if txt:
                text_parts.append(txt)
        elif mime == "text/html":
            txt = decode_body_part(part)
            if txt:
                html_parts.append(txt)
        elif mime.startswith("multipart/"):
            for sub in part.get("parts", []) or []:
                walk(sub)

    walk(payload)

    text = "\n\n".join(text_parts).strip() if text_parts else None
    html = "\n\n".join(html_parts).strip() if html_parts else None
    return {"text": text, "html": html}


def iter_attachments_pdf(service, user_id: str, msg: dict):
    """
    Itère sur les pièces jointes PDF d'un message (full).
    """
    msg_id = msg["id"]
    payload = msg.get("payload", {}) or {}

    parts = payload.get("parts", []) or []
    stack = list(parts)

    while stack:
        part = stack.pop()
        mime = part.get("mimeType", "")
        filename = part.get("filename") or ""

        if mime.startswith("multipart/") and part.get("parts"):
            stack.extend(part["parts"])
            continue

        body = part.get("body", {}) or {}
        attach_id = body.get("attachmentId")

        if not attach_id:
            continue

        if not filename.lower().endswith(".pdf") and "pdf" not in mime.lower():
            continue

        attachment = (
            service.users()
            .messages()
            .attachments()
            .get(userId=user_id, messageId=msg_id, id=attach_id)
            .execute()
        )
        data = attachment.get("data")
        if not data:
            continue
        file_bytes = base64.urlsafe_b64decode(data.encode("utf-8"))
        yield filename or f"{msg_id}.pdf", file_bytes


def main():
    cfg = load_config()
    user_id = cfg.get("user_id", "me")
    label_id = cfg["label_id"]
    creds_path = cfg.get("credentials_path", "credentials.json")
    token_path = cfg.get("token_path", "token.json")
    output_dir = ensure_dir(Path(cfg.get("output_dir", "gmail_output")))

    service = get_gmail_service(credentials_path=creds_path, token_path=token_path)

    results: list[dict[str, Any]] = []

    for msg_meta in iter_messages_by_label(service, user_id, label_id):
        msg_id = msg_meta["id"]
        full = get_message_full(service, user_id, msg_id)

        headers = {
            h["name"].lower(): h["value"]
            for h in full.get("payload", {}).get("headers", []) or []
        }
        subject = headers.get("subject")
        date = headers.get("date")
        frm = headers.get("from")

        # Corps
        body = extract_main_body(full.get("payload", {}) or {})

        # Pièces jointes PDF
        pdf_files = []
        for filename, data in iter_attachments_pdf(service, user_id, full):
            safe_name = f"{msg_id}_{filename}".replace("/", "_")
            pdf_path = output_dir / safe_name
            pdf_path.write_bytes(data)
            pdf_files.append(str(pdf_path.name))

        result = {
            "id": msg_id,
            "subject": subject,
            "date": date,
            "from": frm,
            "label_id": label_id,
            "body_text": body["text"],
            "body_html": body["html"],
            "pdf_attachments": pdf_files,
        }
        results.append(result)

    # Dump global JSON
    out_json = output_dir / "gmail_label_dump.json"
    out_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
