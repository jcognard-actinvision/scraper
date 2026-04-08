from abc import ABC, abstractmethod

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
