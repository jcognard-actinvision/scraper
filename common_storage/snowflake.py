import hashlib
import io
import json
import os
import uuid
from datetime import UTC, datetime

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from common_runtime.settings import Settings
from common_storage.base import StorageBackend
from common_storage.models import StoredDocument, StoredError


class SnowflakeStorage(StorageBackend):
    def __init__(
        self,
        conn,
        stage_root: str,
        scraped_documents_table: str,
        runs_table: str,
        errors_table: str,
    ):
        self.conn = conn
        self.stage_root = stage_root.rstrip("/")
        self.scraped_documents_table = scraped_documents_table
        self.runs_table = runs_table
        self.errors_table = errors_table

    @classmethod
    def from_env(cls):
        private_key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
        private_key_passphrase = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")

        if not private_key_path:
            raise ValueError("SNOWFLAKE_PRIVATE_KEY_PATH is required for key-pair auth")

        with open(private_key_path, "rb") as key:
            private_key = serialization.load_pem_private_key(
                key.read(),
                password=private_key_passphrase.encode()
                if private_key_passphrase
                else None,
                backend=default_backend(),
            )

        private_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        params = {
            "account": Settings.snowflake_account,
            "user": Settings.snowflake_user,
            "warehouse": Settings.snowflake_warehouse,
            "database": Settings.snowflake_database,
            "schema": Settings.snowflake_schema,
        }
        if getattr(Settings, "snowflake_role", None):
            params["role"] = Settings.snowflake_role

        conn = snowflake.connector.connect(**params, private_key=private_key_bytes)

        return cls(
            conn=conn,
            stage_root=Settings.stage_root,
            scraped_documents_table=Settings.scraped_documents_table,
            runs_table=Settings.runs_table,
            errors_table=Settings.errors_table,
        )

    # ---------- helpers ----------

    def _utc_now(self):
        return datetime.now(UTC).replace(tzinfo=None)

    def _execute(self, sql: str, params: tuple | None = None):
        with self.conn.cursor() as cur:
            cur.execute(sql, params or ())
            return cur

    def _put_content(self, stage_path: str, content: bytes):
        stage_dir, filename = stage_path.rsplit("/", 1)
        with self.conn.cursor() as cur:
            cur.execute(
                f"PUT file://ignored/{filename} {stage_dir} AUTO_COMPRESS=FALSE OVERWRITE=TRUE",
                file_stream=io.BytesIO(content),
            )

    def _build_stage_path(self, doc: StoredDocument) -> str | None:
        if not doc.content:
            return None

        now = self._utc_now()
        ext = {
            "application/pdf": ".pdf",
            "text/html": ".html",
            "application/json": ".json",
        }.get(doc.mime_type or "", "")

        filename = f"{uuid.uuid4()}{ext}"
        return f"{self.stage_root}/{doc.source_name}/{now:%Y/%m/%d}/{filename}"

    def _safe_metadata(self, metadata: dict | None) -> str:
        if not metadata:
            return "{}"

        allowed = {
            "click_uri",
            "printable_uri",
            "clickable_uri",
            "sys_clickable_uri",
            "sys_uri",
            "api_uri",
            "filetype",
            "category",
            "template",
            "date",
            "language",
            "summary",
            "has_html_version",
            "has_mobile_html_version",
            "listing_url",
            "fetched_url",
            "final_url",
            "summary_text",
            "message_id",
            "attachment_id",
            "filename",
            "subject",
            "date",
            "from",
            "label_id",
            "body_text",
            "body_html",
        }

        cleaned = {k: v for k, v in metadata.items() if k in allowed}
        return json.dumps(cleaned, ensure_ascii=True)

    # ---------- implémentations StorageBackend ----------

    def start_run(self, source_name: str, metadata: dict | None = None) -> str:
        run_id = str(uuid.uuid4())
        self._execute(
            f"""
            INSERT INTO {self.runs_table}
            (
                RUN_ID,
                SOURCE_NAME,
                STARTED_AT,
                STATUS,
                PROCESSED_COUNT,
                INSERTED_COUNT,
                SKIPPED_COUNT,
                ERROR_COUNT,
                MESSAGE
            )
            VALUES (%s, %s, %s, %s, 0, 0, 0, 0, NULL)
            """,
            (
                run_id,
                source_name,
                self._utc_now(),
                "RUNNING",
            ),
        )
        return run_id

    def exists(
        self,
        source_name: str,
        external_id: str | None = None,
        document_url: str | None = None,
    ) -> bool:
        clauses = ["SOURCE_NAME = %s"]
        params = [source_name]

        if document_url:
            clauses.append("DOCUMENT_URL = %s")
            params.append(document_url)
        else:
            return False

        sql = f"""
        SELECT 1
        FROM {self.scraped_documents_table}
        WHERE {" AND ".join(clauses)}
        LIMIT 1
        """
        cur = self._execute(sql, tuple(params))
        return cur.fetchone() is not None

    def save_document(self, doc: StoredDocument) -> None:
        stage_path = self._build_stage_path(doc)
        sha256 = None

        if doc.content and stage_path:
            self._put_content(stage_path, doc.content)
            sha256 = hashlib.sha256(doc.content).hexdigest()

        extra_json = self._safe_metadata(doc.metadata)

        self._execute(
            f"""
            INSERT INTO {self.scraped_documents_table}
            (
                ID,
                SOURCE_NAME,
                SOURCE_URL,
                DOCUMENT_URL,
                TITLE,
                DOCUMENT_TYPE,
                STAGE_PATH,
                MIME_TYPE,
                HTTP_STATUS,
                SHA256,
                SCRAPED_AT,
                EXTRA
            )
            SELECT
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s)
            """,
            (
                str(uuid.uuid4()),
                doc.source_name,
                doc.source_url,
                doc.document_url,
                doc.title,
                doc.document_type,
                stage_path,
                doc.mime_type,
                getattr(doc, "http_status", None),
                sha256,
                self._utc_now(),
                extra_json,
            ),
        )

    def log_error(self, err: StoredError) -> None:
        self._execute(
            f"""
            INSERT INTO {self.errors_table}
            (
                RUN_ID,
                SOURCE_NAME,
                URL,
                STEP,
                ERROR_TYPE,
                ERROR_MESSAGE,
                ERROR_STACK,
                CREATED_AT
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                err.run_id,
                err.source_name,
                err.url,
                err.step,
                err.error_type,
                err.error_message,
                err.error_stack,
                self._utc_now(),
            ),
        )

    def finish_run(
        self, run_id: str, status: str, stats: dict, message: str | None = None
    ) -> None:
        self._execute(
            f"""
            UPDATE {self.runs_table}
            SET FINISHED_AT = %s,
                STATUS = %s,
                PROCESSED_COUNT = %s,
                INSERTED_COUNT = %s,
                SKIPPED_COUNT = %s,
                ERROR_COUNT = %s,
                MESSAGE = %s
            WHERE RUN_ID = %s
            """,
            (
                self._utc_now(),
                status,
                stats.get("processed", 0),
                stats.get("inserted", 0),
                stats.get("skipped", 0),
                stats.get("errors", 0),
                message,
                run_id,
            ),
        )
