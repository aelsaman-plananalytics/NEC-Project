"""
Tamper-evident integrity hashing for persistence records.

Deterministic SHA-256 hash over canonical JSON. Used to detect modification
of submission and acceptance records after save.
"""

import hashlib
import json
from typing import Any, Dict


def compute_record_hash(record_dict: dict) -> str:
    """
    Compute a deterministic SHA-256 hash of a record for integrity verification.
    The "record_hash" field is excluded before hashing so the hash is reproducible.
    """
    payload = dict(record_dict)
    payload.pop("record_hash", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
