"""Storage abstraction for reports, idempotency, ledger, and audit."""

from app.storage.storage_interface import StorageInterface
from app.storage.local_storage import LocalStorage

__all__ = ["StorageInterface", "LocalStorage", "get_storage"]

_storage_instance: StorageInterface | None = None


def get_storage() -> StorageInterface:
    """Return the default storage instance (singleton)."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = LocalStorage()
    return _storage_instance
