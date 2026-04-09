from abc import ABC, abstractmethod

from common_runtime.notifications import send_error_notification
from common_storage.models import StoredDocument, StoredError


class StorageBackend(ABC):
    @abstractmethod
    def start_run(self, source_name: str, metadata: dict | None = None) -> str: ...

    @abstractmethod
    def exists(
        self,
        source_name: str,
        external_id: str | None = None,
        document_url: str | None = None,
    ) -> bool: ...

    @abstractmethod
    def save_document(self, doc: StoredDocument) -> None: ...

    @abstractmethod
    def log_error(self, err: StoredError) -> None: ...

    @abstractmethod
    def finish_run(
        self, run_id: str, status: str, stats: dict, message: str | None = None
    ) -> None: ...

    def log_and_notify_error(storage, error):
        if hasattr(storage, "log_error"):
            storage.log_error(error)

        try:
            send_error_notification(
                source_name=error.source_name,
                step=error.step,
                error_type=error.error_type,
                error_message=error.error_message,
                run_id=error.run_id,
                url=error.url,
                metadata=error.metadata,
            )
        except Exception:
            pass
