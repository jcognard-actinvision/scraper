import os


class Settings:
    app_target = os.getenv("APP_TARGET", "scraper")
    storage_backend = os.getenv("STORAGE_BACKEND", "snowflake")

    snowflake_account = os.getenv("SNOWFLAKE_ACCOUNT")
    snowflake_user = os.getenv("SNOWFLAKE_USER")
    snowflake_password = os.getenv("SNOWFLAKE_PASSWORD")
    snowflake_warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    snowflake_database = os.getenv("SNOWFLAKE_DATABASE")
    snowflake_schema = os.getenv("SNOWFLAKE_SCHEMA")
    snowflake_role = os.getenv("SNOWFLAKE_ROLE")

    stage_root = os.getenv("SNOWFLAKE_STAGE_ROOT", "@SCRAPER_STAGE")
    scraped_documents_table = os.getenv("SCRAPED_DOCUMENTS_TABLE", "SCRAPED_DOCUMENTS")
    runs_table = os.getenv("SCRAPER_RUNS_TABLE", "SCRAPER_RUNS")
    errors_table = os.getenv("SCRAPER_ERRORS_TABLE", "SCRAPER_ERRORS")