import os


class Settings:
    backend = os.getenv("SCRAPER_BACKEND", "snowflake")
    source = os.getenv("SCRAPER_SOURCE", "cushman")
    max_pages = int(os.getenv("SCRAPER_MAX_PAGES", "5"))

    snowflake_account = os.getenv("SNOWFLAKE_ACCOUNT")
    snowflake_user = os.getenv("SNOWFLAKE_USER")
    snowflake_password = os.getenv("SNOWFLAKE_PASSWORD")
    snowflake_private_key = os.getenv("SNOWFLAKE_PRIVATE_KEY")
    snowflake_private_key_passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    snowflake_warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    snowflake_database = os.getenv("SNOWFLAKE_DATABASE")
    snowflake_schema = os.getenv("SNOWFLAKE_SCHEMA")

    email_to = os.getenv("SCRAPER_EMAIL_TO")
    email_enabled = os.getenv("SCRAPER_EMAIL_ENABLED", "false").lower() == "true"
