from __future__ import annotations

import base64
import os.path
from typing import Iterable

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
):
    creds = None

    # 1) Charger un éventuel token existant
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # 2) Si pas de creds ou invalides → essayer de refresh, sinon réauth
    if not creds or not creds.valid:
        need_reauth = False

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # refresh_token invalide / révoqué → on force une réauth
                need_reauth = True
        else:
            need_reauth = True

        if need_reauth:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)

        # 3) Sauvegarde (nouveau token ou token rafraîchi)
        with open(token_path, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    # 4) Construction du service
    service = build("gmail", "v1", credentials=creds)
    return service


def iter_messages_by_label(service, user_id: str, label_id: str) -> Iterable[dict]:
    """
    Itère sur tous les messages d'un label donné (en mode 'full' ensuite).
    """
    page_token = None
    while True:
        response = (
            service.users()
            .messages()
            .list(userId=user_id, labelIds=[label_id], pageToken=page_token)
            .execute()
        )
        for msg in response.get("messages", []):
            yield msg

        page_token = response.get("nextPageToken")
        if not page_token:
            break


def get_message_full(service, user_id: str, msg_id: str) -> dict:
    return (
        service.users()
        .messages()
        .get(userId=user_id, id=msg_id, format="full")
        .execute()
    )


def decode_body_part(part: dict) -> str | None:
    """
    Décodage base64 d'une partie de message (text/plain ou text/html).
    """
    data = part.get("body", {}).get("data")
    if not data:
        return None
    decoded_bytes = base64.urlsafe_b64decode(data.encode("utf-8"))
    try:
        return decoded_bytes.decode("utf-8", errors="replace")
    except Exception:
        return decoded_bytes.decode("latin-1", errors="replace")


def list_labels(service, user_id: str = "me") -> list[dict]:
    """
    Retourne la liste brute des labels Gmail.
    Chaque item contient au moins: id, name, type.
    """
    resp = service.users().labels().list(userId=user_id).execute()
    return resp.get("labels", []) or []
