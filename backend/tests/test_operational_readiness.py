"""
Tests for Step 5C — Operational production readiness.
Startup config validation, health endpoint, structured logging. No engine changes.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.startup_checks import run_config_validation, run_integrity_self_check, check_ledger_accessible
from app.api_audit import log_api_request


def test_startup_fails_on_invalid_config():
    """Startup config validation raises RuntimeError when MAX_XER_FILE_SIZE is 0."""
    with patch("startup.startup_checks.MAX_XER_FILE_SIZE_BYTES", 0):
        with pytest.raises(RuntimeError) as exc_info:
            run_config_validation()
        assert "MAX_XER_FILE_SIZE" in str(exc_info.value) or "> 0" in str(exc_info.value)


def test_startup_fails_when_request_limit_less_than_xer_limit():
    """Startup fails when REQUEST_SIZE_LIMIT_MB < MAX_XER_FILE_SIZE_MB."""
    with patch("startup.startup_checks.MAX_XER_FILE_SIZE_BYTES", 100), patch(
        "startup.startup_checks.REQUEST_SIZE_LIMIT_BYTES", 50
    ):
        with pytest.raises(RuntimeError) as exc_info:
            run_config_validation()
        assert "REQUEST_SIZE_LIMIT" in str(exc_info.value) or ">=" in str(exc_info.value)


def test_startup_fails_when_rate_limit_zero():
    """Startup fails when RATE_LIMIT_PER_MINUTE is 0."""
    with patch("startup.startup_checks.RATE_LIMIT_PER_MINUTE", 0):
        with pytest.raises(RuntimeError) as exc_info:
            run_config_validation()
        assert "RATE_LIMIT" in str(exc_info.value) or "> 0" in str(exc_info.value)


def test_api_key_required_but_not_configured_startup_error():
    """When REQUIRE_API_KEY=true and VALID_API_KEYS empty, startup fails."""
    with patch("startup.startup_checks.REQUIRE_API_KEY", True), patch(
        "startup.startup_checks.get_valid_api_keys", return_value=set()
    ):
        with pytest.raises(RuntimeError) as exc_info:
            run_config_validation()
        assert "REQUIRE_API_KEY" in str(exc_info.value) or "VALID_API_KEYS" in str(exc_info.value)


def _health_app():
    """Minimal app with only /api/v1/health to avoid pulling full main (db, config)."""
    app = FastAPI()
    @app.get("/api/v1/health")
    async def health_v1():
        from app.startup_checks import check_ledger_accessible
        from app.api_errors import structured_error_response, INTERNAL_ERROR
        try:
            check_ledger_accessible()
        except RuntimeError as e:
            return structured_error_response(
                500,
                INTERNAL_ERROR,
                "Health check failed: ledger verification failed.",
                details=str(e),
            )
        return {
            "status": "healthy",
            "version": "v1",
            "integrity": "ok",
            "ledger_chain_check": "ok",
        }
    return app


def test_health_returns_healthy():
    """GET /api/v1/health returns 200 with status, version, integrity, ledger_chain_check."""
    app = _health_app()
    client = TestClient(app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "healthy"
    assert body.get("version") == "v1"
    assert body.get("integrity") == "ok"
    assert body.get("ledger_chain_check") == "ok"


def test_health_fails_if_ledger_corrupted():
    """When ledger check raises, health returns 500 with structured error."""
    app = _health_app()
    with patch("app.startup_checks.check_ledger_accessible", side_effect=RuntimeError("Ledger dir missing")):
        client = TestClient(app)
        r = client.get("/api/v1/health")
    assert r.status_code == 500
    body = r.json()
    assert body.get("error_code") == "INTERNAL_ERROR"
    assert "error_message" in body
    assert "details" in body


def test_structured_log_format_valid_json(tmp_path):
    """Audit log writes valid JSON lines with required fields."""
    from app.storage.local_storage import LocalStorage
    storage = LocalStorage(base_dir=tmp_path)
    with patch("app.storage.get_storage", return_value=storage):
        log_api_request(
            ip="192.168.1.1",
            route="/api/v1/validate_programme",
            status_code=200,
            idempotency_key="key-1",
            response_signature="abc123",
        )
    log_path = tmp_path / "api_audit.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in content.strip().split("\n") if ln.strip()]
    assert len(lines) >= 1
    for line in lines:
        obj = json.loads(line)
        assert "timestamp" in obj
        assert "ip" in obj
        assert "route" in obj
        assert "status" in obj
        assert "response_signature" in obj
        assert "idempotency_key" in obj
    obj = json.loads(lines[-1])
    assert obj["ip"] == "192.168.1.1"
    assert obj["route"] == "/api/v1/validate_programme"
    assert obj["status"] == 200
    assert obj["response_signature"] == "abc123"
    assert obj["idempotency_key"] == "key-1"
