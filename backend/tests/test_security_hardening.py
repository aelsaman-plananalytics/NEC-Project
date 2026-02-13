"""
Tests for Step 5B — Security hardening (API layer only).
File validation, request size, rate limit, API key, audit log.
"""

import json
import pytest
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import validate_programme as validate_programme_router
from app.security_middleware import SecurityMiddleware
from app.p6_engine.frozen_requirements import build_frozen_requirements


def _minimal_contract():
    contract_data = {"scope_items": [], "programme_compliance_model": {}, "constraints": []}
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


MINI_XER = b"""%T\tPROJWBS
%F\twbs_id\tparent_wbs_id\twbs_name
%R\t1\t\tDesign
%E\tPROJWBS

%T\tTASK
%F\ttask_id\ttask_name\twbs_id
%R\t1\tDesign\t1
%E\tTASK
"""


@pytest.fixture
def app_with_middleware():
    """App with SecurityMiddleware for rate limit and API key tests."""
    app = FastAPI()
    app.add_middleware(SecurityMiddleware)
    app.include_router(validate_programme_router.router)
    return app


@pytest.fixture
def client_no_middleware():
    """Client without security middleware (for file validation tests)."""
    app = FastAPI()
    app.include_router(validate_programme_router.router)
    return TestClient(app)


def test_invalid_file_extension_rejected(client_no_middleware):
    """Non-.xer upload is rejected with structured BAD_REQUEST."""
    contract = _minimal_contract()
    r = client_no_middleware.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.txt", BytesIO(b"not xer"), "text/plain"),
            "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
        },
    )
    assert r.status_code == 400
    body = r.json()
    assert body.get("error_code") == "BAD_REQUEST"
    assert "XER" in (body.get("error_message") or "")
    assert "details" in body


def test_empty_upload_rejected(client_no_middleware):
    """Empty XER upload is rejected with BAD_REQUEST."""
    contract = _minimal_contract()
    r = client_no_middleware.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(b""), "application/octet-stream"),
            "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
        },
    )
    assert r.status_code == 400
    body = r.json()
    assert body.get("error_code") == "BAD_REQUEST"
    assert "empty" in (body.get("error_message") or "").lower() or "Empty" in (body.get("error_message") or "")


def test_oversized_file_rejected(client_no_middleware):
    """XER larger than MAX_XER_FILE_SIZE is rejected with BAD_REQUEST."""
    contract = _minimal_contract()
    with patch("app.routers.validate_programme.MAX_XER_FILE_SIZE_BYTES", 5):
        r = client_no_middleware.post(
            "/api/v1/validate_programme",
            files={
                "xer_file": ("programme.xer", BytesIO(MINI_XER), "application/octet-stream"),
                "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
            },
        )
    assert r.status_code == 400
    body = r.json()
    assert body.get("error_code") == "BAD_REQUEST"
    assert "large" in (body.get("error_message") or "").lower() or "too" in (body.get("error_message") or "").lower()
    assert "details" in body


def test_rate_limit_triggered(app_with_middleware, tmp_path):
    """When rate limit is exceeded, 429 with RATE_LIMIT_EXCEEDED is returned."""
    rate_dir = tmp_path / "rate_limit"
    rate_dir.mkdir(parents=True, exist_ok=True)
    contract = _minimal_contract()
    files = {
        "xer_file": ("p.xer", BytesIO(MINI_XER), "application/octet-stream"),
        "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
    }
    with patch("app.rate_limit.RATE_LIMIT_PER_MINUTE", 2), patch(
        "app.security.rate_limit.RATE_LIMIT_PER_MINUTE", 2
    ), patch("app.rate_limit.rate_limit_dir", return_value=rate_dir), patch(
        "app.security.rate_limit.rate_limit_dir", return_value=rate_dir
    ):
        client = TestClient(app_with_middleware)
        r1 = client.post("/api/v1/validate_programme", files=files)
        r2 = client.post("/api/v1/validate_programme", files=files)
        r3 = client.post("/api/v1/validate_programme", files=files)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    body = r3.json()
    assert body.get("error_code") == "RATE_LIMIT_EXCEEDED"
    assert "details" in body


def test_missing_api_key_rejected(app_with_middleware):
    """When REQUIRE_API_KEY=true, request without X-API-Key returns 401."""
    with patch("app.security.security_config.REQUIRE_API_KEY", True), patch(
        "app.security.security_config.get_valid_api_keys", return_value={"test-key-123"}
    ), patch("app.security.security_middleware.REQUIRE_API_KEY", True), patch(
        "app.security.security_middleware.get_valid_api_keys", return_value={"test-key-123"}
    ):
        client = TestClient(app_with_middleware)
        contract = _minimal_contract()
        r = client.post(
            "/api/v1/validate_programme",
            files={
                "xer_file": ("p.xer", BytesIO(MINI_XER), "application/octet-stream"),
                "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
            },
        )
    assert r.status_code == 401
    body = r.json()
    assert body.get("error_code") == "UNAUTHORIZED"
    assert "details" in body or "error_message" in body


def test_invalid_api_key_rejected(app_with_middleware):
    """When REQUIRE_API_KEY=true, wrong X-API-Key returns 401."""
    with patch("app.security.security_config.REQUIRE_API_KEY", True), patch(
        "app.security.security_config.get_valid_api_keys", return_value={"valid-key"}
    ), patch("app.security.security_middleware.REQUIRE_API_KEY", True), patch(
        "app.security.security_middleware.get_valid_api_keys", return_value={"valid-key"}
    ):
        client = TestClient(app_with_middleware)
        contract = _minimal_contract()
        r = client.post(
            "/api/v1/validate_programme",
            headers={"X-API-Key": "wrong-key"},
            files={
                "xer_file": ("p.xer", BytesIO(MINI_XER), "application/octet-stream"),
                "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
            },
        )
    assert r.status_code == 401
    body = r.json()
    assert body.get("error_code") == "UNAUTHORIZED"


def test_audit_log_file_written(client_no_middleware, tmp_path):
    """After a validate_programme request, audit log contains timestamp, route, status."""
    from app.storage.local_storage import LocalStorage
    storage = LocalStorage(tmp_path)
    with patch("app.storage.get_storage", return_value=storage):
        contract = _minimal_contract()
        r = client_no_middleware.post(
            "/api/v1/validate_programme",
            files={
                "xer_file": ("p.xer", BytesIO(MINI_XER), "application/octet-stream"),
                "json_file": ("c.json", BytesIO(json.dumps(contract).encode()), "application/json"),
            },
        )
    assert r.status_code == 200
    log_path = tmp_path / "api_audit.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "/api/v1/validate_programme" in content or "validate_programme" in content
    assert "200" in content
