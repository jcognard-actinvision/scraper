from __future__ import print_function

import base64
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    return service


def list_labels(service):
    results = service.users().labels().list(userId="me").execute()
    labels = results.get("labels", [])
    if not labels:
        print("Aucun label trouvé.")
        return []
    print("Labels disponibles :")
    for label in labels:
        print(f"{label['id']}: {label['name']}")
    return labels


def list_messages_in_label(service, label_id, max_results=50):
    messages = []
    request = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label_id], maxResults=max_results)
    )
    while request is not None:
        response = request.execute()
        messages.extend(response.get("messages", []))
        request = service.users().messages().list_next(request, response)
    return messages


def get_message_subject(service, msg_id):
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["Subject"])
        .execute()
    )
    headers = msg.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
    return subject


def get_message_content(service, msg_id):
    msg = (
        service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    )

    payload = msg.get("payload", {})
    text = extract_plain_text_from_payload(payload)
    return text


def extract_plain_text_from_payload(payload):
    mime_type = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    # Cas simple : directement text/plain sans sous-parties
    if mime_type == "text/plain" and data:
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8", errors="replace")

    # Cas multipart : on parcourt les sous-parts
    parts = payload.get("parts", [])
    if parts:
        texts = []
        for part in parts:
            text = extract_plain_text_from_payload(part)
            if text:
                texts.append(text)
        return "\n".join(texts)

    return ""


def main():
    service = get_service()
    labels = list_labels(service)

    label_name = input("\nNom du label à lister (exactement comme affiché) : ").strip()

    label_id = None
    for label in labels:
        if label["name"] == label_name:
            label_id = label["id"]
            break

    if not label_id:
        print("Label non trouvé.")
        return

    print(f"\nMessages dans le label '{label_name}' :")
    messages = list_messages_in_label(service, label_id)
    print(f"Nombre de messages: {len(messages)}")

    for msg in messages:
        subject = get_message_subject(service, msg["id"])
        content = get_message_content(service, msg["id"])
        print(f"- id={msg['id']} | subject={subject}")
        print(f"  content (text): {content[:300].replace('\n', ' ')}...")


if __name__ == "__main__":
    main()
