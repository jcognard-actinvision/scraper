from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable


def _is_true(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_recipients(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def smtp_is_configured() -> bool:
    if not _is_true(os.getenv("SMTP_ENABLED", "false")):
        return False

    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_FROM", "SMTP_TO"]
    return all(os.getenv(name) for name in required)


def send_email(
    *,
    subject: str,
    body: str,
    to_addrs: Iterable[str] | None = None,
) -> None:
    if not smtp_is_configured():
        return

    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", "")
    subject_prefix = os.getenv("SMTP_SUBJECT_PREFIX", "[Stonelake]")
    use_tls = _is_true(os.getenv("SMTP_USE_TLS", "true"))
    use_ssl = _is_true(os.getenv("SMTP_USE_SSL", "false"))

    recipients = (
        list(to_addrs)
        if to_addrs is not None
        else _parse_recipients(os.getenv("SMTP_TO"))
    )
    if not recipients:
        return

    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"{subject_prefix} {subject}"
    msg.set_content(body)

    context = ssl.create_default_context()

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            if username and password:
                server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=context)
                server.ehlo()
            if username and password:
                server.login(username, password)
            server.send_message(msg)


def send_error_notification(
    *,
    source_name: str,
    step: str,
    error_type: str,
    error_message: str,
    run_id: str | None = None,
    url: str | None = None,
    metadata: dict | None = None,
) -> None:
    if not smtp_is_configured():
        return

    body_lines = [
        "Une erreur Stonelake a été détectée.",
        "",
        f"source_name: {source_name}",
        f"step: {step}",
        f"error_type: {error_type}",
        f"error_message: {error_message}",
    ]

    if run_id:
        body_lines.append(f"run_id: {run_id}")
    if url:
        body_lines.append(f"url: {url}")
    if metadata:
        body_lines.extend(
            [
                "",
                "metadata:",
                str(metadata),
            ]
        )

    send_email(
        subject=f"Erreur {source_name}",
        body="\n".join(body_lines),
    )
