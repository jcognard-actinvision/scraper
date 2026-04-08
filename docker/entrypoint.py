import os
import subprocess


def main():
    target = os.getenv("APP_TARGET", "scraper")

    if target == "scraper":
        cmd = ["python", "-m", "scraper.run"]
    elif target == "gmail_fetcher":
        cmd = ["python", "-m", "gmail_fetcher.fetch_gmail"]
    else:
        raise ValueError(f"Unknown APP_TARGET: {target}")

    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
