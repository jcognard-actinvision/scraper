import json
import re
from pathlib import Path


class LocalStorage:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, value: str) -> str:
        return re.sub(r"[^a-zA-Z0-9._-]+", "_", value)

    def _source_dir(self, source_name: str) -> Path:
        path = self.output_dir / self._safe_name(source_name)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def exists(
        self,
        source_name: str,
        external_id: str | None = None,
        document_url: str | None = None,
    ) -> bool:
        key = external_id or document_url
        if not key:
            return False
        filename = self._safe_name(key)
        meta_file = self._source_dir(source_name) / f"{filename}.json"
        return meta_file.exists()

    def save_document(self, doc) -> None:
        key = doc.external_id or doc.document_url
        filename = self._safe_name(key)
        source_dir = self._source_dir(doc.source_name)

        meta = {
            "source_name": doc.source_name,
            "source_url": doc.source_url,
            "document_url": doc.document_url,
            "title": doc.title,
            "document_type": doc.document_type,
            "mime_type": doc.mime_type,
            "external_id": doc.external_id,
            "text_content": doc.text_content,
            "metadata": doc.metadata,
        }

        meta_file = source_dir / f"{filename}.json"
        meta_file.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if doc.content:
            if doc.mime_type == "application/pdf":
                ext = ".pdf"
            elif doc.mime_type == "text/html":
                ext = ".html"
            elif doc.mime_type == "application/json":
                ext = ".json.bin"
            else:
                ext = ".bin"

            content_file = source_dir / f"{filename}{ext}"
            content_file.write_bytes(doc.content)

    def start_run(self, source_name: str, metadata: dict | None = None) -> str:
        return "local-run"

    def log_error(self, err) -> None:
        err_dir = self.output_dir / "_errors"
        err_dir.mkdir(parents=True, exist_ok=True)
        err_file = err_dir / f"{self._safe_name(err.source_name)}.log"
        with err_file.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "source_name": err.source_name,
                        "url": err.url,
                        "step": err.step,
                        "error_type": err.error_type,
                        "error_message": err.error_message,
                        "metadata": err.metadata,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    def finish_run(
        self, run_id: str, status: str, stats: dict, message: str | None = None
    ) -> None:
        runs_dir = self.output_dir / "_runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        run_file = runs_dir / f"{run_id}.json"
        run_file.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "status": status,
                    "stats": stats,
                    "message": message,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
