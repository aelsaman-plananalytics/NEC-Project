"""
Storage abstraction interface.
Implementations may use local filesystem, object storage, etc.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class StorageInterface(ABC):
    """Abstract interface for file/blob storage. Enables multi-instance deployment."""

    @abstractmethod
    def save_json(self, path: str, data: Dict[str, Any]) -> None:
        """Persist JSON-serializable data at path. Overwrites if exists."""
        ...

    @abstractmethod
    def load_json(self, path: str) -> Dict[str, Any] | None:
        """Load JSON from path. Returns None if not found or invalid."""
        ...

    @abstractmethod
    def save_bytes(self, path: str, data: bytes) -> None:
        """Persist raw bytes at path. Overwrites if exists."""
        ...

    @abstractmethod
    def load_bytes(self, path: str) -> bytes | None:
        """Load raw bytes from path. Returns None if not found."""
        ...

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Return True if path exists."""
        ...

    @abstractmethod
    def delete(self, path: str) -> None:
        """Delete path if it exists. No-op if missing."""
        ...

    @abstractmethod
    def list_paths(self, prefix: str) -> List[str]:
        """List paths under prefix (e.g. directory). Returns relative paths or full paths depending on impl."""
        ...

    def append_line(self, path: str, line: str) -> None:
        """Append a single line (e.g. JSON log line) to path. Optional; default impl may raise."""
        raise NotImplementedError("append_line")
