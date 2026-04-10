from __future__ import annotations

import os

from dotenv import load_dotenv

from .gmail_client import get_gmail_service, list_labels

load_dotenv()


def main():
    creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "gmail_tokens/credentials.json")
    token_path = os.getenv("GMAIL_TOKEN_PATH", "gmail_tokens/token.json")
    user_id = os.getenv("GMAIL_USER_ID", "me")

    service = get_gmail_service(credentials_path=creds_path, token_path=token_path)
    labels = list_labels(service, user_id=user_id)

    for lab in labels:
        print(f"{lab['id']:30}  {lab.get('name', ''):50}  ({lab.get('type', '')})")


if __name__ == "__main__":
    main()
