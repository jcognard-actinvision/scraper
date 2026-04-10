from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from common_runtime.settings import Settings
from common_storage.local import LocalStorage
from common_storage.models import StoredDocument, StoredError
from common_storage.snowflake import SnowflakeStorage

from .gmail_client import (
    decode_body_part,
    get_gmail_service,
    get_message_full,
    iter_messages_by_label,
)

load_dotenv()


def load_config() -> dict[str, Any]:
    return {
        "source_name": os.getenv("GMAIL_SOURCE_NAME", "gmail_fetcher"),
        "user_id": os.getenv("GMAIL_USER_ID", "me"),
        "label_id": os.getenv("GMAIL_LABEL_ID"),
        "credentials_path": os.getenv(
            "GMAIL_CREDENTIALS_PATH", "gmail_tokens/credentials.json"
        ),
        "token_path": os.getenv("GMAIL_TOKEN_PATH", "gmail_tokens/token.json"),
        "output_dir": os.getenv("GMAIL_OUTPUT_DIR", "gmail_output"),
    }


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


def email_to_document(source_name: str, message: dict) -> StoredDocument:
    message_id = message["id"]
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    return StoredDocument(
        source_name=source_name,
        source_url=None,
        document_url=f"gmail://message/{message_id}",
        title=message.get("subject"),
        document_type="json",
        mime_type="application/json",
        content=payload,
        text_content=message.get("body_text"),
        external_id=message_id,
        metadata=message,
    )


def attachment_to_document(
    source_name: str, message_id: str, attachment: dict
) -> StoredDocument:
    attachment_id = attachment["attachment_id"]
    return StoredDocument(
        source_name=source_name,
        source_url=None,
        document_url=f"gmail://message/{message_id}/attachment/{attachment_id}",
        title=attachment.get("filename"),
        document_type="pdf",
        mime_type="application/pdf",
        content=attachment["content"],
        text_content=None,
        external_id=f"{message_id}:{attachment_id}",
        metadata={
            "message_id": message_id,
            "attachment_id": attachment_id,
            "filename": attachment.get("filename"),
            "subject": attachment.get("subject"),
            "date": attachment.get("date"),
            "from": attachment.get("from"),
            "label_id": attachment.get("label_id"),
            "body_text": attachment.get("body_text"),
            "body_html": attachment.get("body_html"),
        },
    )


def run_gmail_fetcher():
    processed = 0
    inserted = 0
    skipped = 0
    errors = 0

    cfg = load_config()
    source_name = cfg.get("source_name", "gmail_fetcher")
    user_id = cfg.get("user_id", "me")
    label_id = cfg["label_id"]
    creds_path = cfg.get("credentials_path", "credentials.json")
    token_path = cfg.get("token_path", "token.json")
    output_dir = ensure_dir(Path(cfg.get("output_dir", "gmail_output")))

    if Settings.storage_backend == "snowflake":
        storage = SnowflakeStorage.from_env()
    else:
        storage = LocalStorage(output_dir=output_dir)

    service = get_gmail_service(credentials_path=creds_path, token_path=token_path)

    results: list[dict[str, Any]] = []
    processed = inserted = skipped = errors = 0

    run_id = None
    if hasattr(storage, "start_run"):
        try:
            run_id = storage.start_run(
                source_name=source_name,
                metadata={"label_id": label_id},
            )
        except Exception:
            run_id = None

    try:
        for msg_meta in iter_messages_by_label(service, user_id, label_id):
            msg_id = msg_meta["id"]

            try:
                if hasattr(
                    storage, "has_processed_message"
                ) and storage.has_processed_message(
                    source_name=source_name,
                    external_id=msg_id,
                ):
                    skipped += 1
                    continue

                full = get_message_full(service, user_id, msg_id)

                headers = {
                    h["name"].lower(): h["value"]
                    for h in full.get("payload", {}).get("headers", []) or []
                }
                subject = headers.get("subject")
                date = headers.get("date")
                frm = headers.get("from")

                body = extract_main_body(full.get("payload", {}) or {})

                pdf_attachments: list[dict[str, Any]] = []
                for idx, (filename, data) in enumerate(
                    iter_attachments_pdf(service, user_id, full),
                    start=1,
                ):
                    pdf_attachments.append(
                        {
                            "attachment_id": str(idx),
                            "filename": filename,
                            "content": data,
                        }
                    )

                result = {
                    "id": msg_id,
                    "subject": subject,
                    "date": date,
                    "from": frm,
                    "label_id": label_id,
                    "body_text": body["text"],
                    "body_html": body["html"],
                    "pdf_attachments": [a["filename"] for a in pdf_attachments],
                }
                results.append(result)
                processed += 1

                for attachment in pdf_attachments:
                    att_doc = {
                        "attachment_id": attachment["attachment_id"],
                        "filename": attachment["filename"],
                        "content": attachment["content"],
                        "message_id": msg_id,
                        "subject": subject,
                        "date": date,
                        "from": frm,
                        "label_id": label_id,
                        "body_text": body["text"],
                        "body_html": body["html"],
                    }

                    storage.save_document(
                        attachment_to_document(source_name, msg_id, att_doc)
                    )
                    inserted += 1

                if hasattr(storage, "mark_message_processed"):
                    storage.mark_message_processed(
                        source_name=source_name,
                        external_id=msg_id,
                        metadata={
                            "label_id": label_id,
                            "subject": subject,
                            "date": date,
                            "from": frm,
                            "attachment_count": len(pdf_attachments),
                        },
                    )

            except Exception as e:
                errors += 1
                storage.log_and_notify_error(
                    StoredError(
                        run_id=run_id or "",
                        source_name=source_name,
                        url=f"gmail://message/{msg_id}",
                        step="gmail_fetcher.main",
                        error_type=type(e).__name__,
                        error_message=str(e),
                        error_stack="",
                        metadata={"label_id": label_id},
                    )
                )

    finally:
        if run_id and hasattr(storage, "finish_run"):
            try:
                storage.finish_run(
                    run_id=run_id,
                    status="SUCCESS" if errors == 0 else "PARTIAL_SUCCESS",
                    stats={
                        "processed": processed,
                        "inserted": inserted,
                        "skipped": skipped,
                        "errors": errors,
                    },
                    message=None,
                )
            except Exception:
                pass

    out_json = output_dir / "gmail_label_dump.json"
    out_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(
        f"[gmail_fetcher] processed={processed}, inserted={inserted}, "
        f"skipped={skipped}, errors={errors}"
    )

    return {
        "processed": processed,
        "inserted": inserted,
        "skipped": skipped,
        "errors": errors,
    }


if __name__ == "__main__":
    result = run_gmail_fetcher()
    print(result)
