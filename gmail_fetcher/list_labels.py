from __future__ import annotations

from typing import Any

import yaml

from .gmail_client import get_gmail_service, list_labels


def load_config(path: str = "gmail_fetcher/config.yaml") -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg = load_config()
    creds_path = cfg.get("credentials_path", "credentials.json")
    token_path = cfg.get("token_path", "token.json")
    service = get_gmail_service(credentials_path=creds_path, token_path=token_path)
    labels = list_labels(service, user_id="me")

    for lab in labels:
        print(f"{lab['id']:30}  {lab.get('name', ''):50}  ({lab.get('type', '')})")


if __name__ == "__main__":
    main()
