"""
Local filesystem implementation of StorageInterface.
Uses RUNTIME_DIR as base; paths are relative to base.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from app.storage.storage_interface import StorageInterface
from app.runtime_paths import RUNTIME_DIR


class LocalStorage(StorageInterface):
    """Store and load under a base directory (default RUNTIME_DIR)."""

    def __init__(self, base_dir: Path | None = None):
        self._base = Path(base_dir) if base_dir is not None else RUNTIME_DIR

    def _full_path(self, path: str) -> Path:
        """Resolve path relative to base. Normalize to prevent escape."""
        p = (self._base / path).resolve()
        base = self._base.resolve()
        if not str(p).startswith(str(base)):
            raise ValueError(f"Path escapes base: {path}")
        return p

    def save_json(self, path: str, data: Dict[str, Any]) -> None:
        full = self._full_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_json(self, path: str) -> Dict[str, Any] | None:
        full = self._full_path(path)
        if not full.exists():
            return None
        try:
            with open(full, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def save_bytes(self, path: str, data: bytes) -> None:
        full = self._full_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)

    def load_bytes(self, path: str) -> bytes | None:
        full = self._full_path(path)
        if not full.exists():
            return None
        try:
            with open(full, "rb") as f:
                return f.read()
        except OSError:
            return None

    def exists(self, path: str) -> bool:
        return self._full_path(path).exists()

    def delete(self, path: str) -> None:
        full = self._full_path(path)
        if full.exists():
            full.unlink()

    def list_paths(self, prefix: str) -> List[str]:
        """List paths under prefix. Returns paths relative to base (e.g. idempotency/foo.json)."""
        full_prefix = self._full_path(prefix)
        if not full_prefix.exists() or not full_prefix.is_dir():
            return []
        base = self._base.resolve()
        out = []
        for p in full_prefix.rglob("*"):
            if p.is_file():
                try:
                    rel = p.relative_to(base)
                    out.append(str(rel).replace("\\", "/"))
                except ValueError:
                    pass
        return sorted(out)

    def append_line(self, path: str, line: str) -> None:
        full = self._full_path(path)
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "a", encoding="utf-8") as f:
            f.write(line if line.endswith("\n") else line + "\n")
