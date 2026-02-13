"""
Tests for optional previous programme XER upload (submission comparison) on /api/v1/validate_programme.

Submission comparison is observational only; does not affect acceptability, persistence, or ledger.
"""

import json
import pytest
from io import BytesIO
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import validate_programme as validate_programme_router
from app.p6_engine.frozen_requirements import build_frozen_requirements

_app = FastAPI()
_app.include_router(validate_programme_router.router)

# Minimal XER: one WBS "Design", one task. No Temporary Works.
XER_NO_TW = b"""%T\tPROJWBS
%F\twbs_id\tparent_wbs_id\twbs_name
%R\t1\t\tDesign
%E\tPROJWBS

%T\tTASK
%F\ttask_id\ttask_name\twbs_id
%R\t1\tDesign\t1
%E\tTASK
"""

# Minimal XER: Design + Temporary Works.
XER_WITH_TW = b"""%T\tPROJWBS
%F\twbs_id\tparent_wbs_id\twbs_name
%R\t1\t\tDesign
%R\t2\t\tTemporary Works
%E\tPROJWBS

%T\tTASK
%F\ttask_id\ttask_name\twbs_id
%R\t1\tDesign\t1
%R\t2\tTW activity\t2
%E\tTASK
"""


def _contract_json():
    contract_data = {
        "scope_items": [],
        "programme_compliance_model": {},
        "constraints": [],
    }
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


@pytest.fixture
def client():
    return TestClient(_app)


@pytest.fixture
def contract_json():
    return _contract_json()


def test_upload_current_and_previous_contains_submission_comparison(
    client: TestClient,
    contract_json: dict,
):
    """Upload current + previous_xer_file → response contains submission_comparison with expected shape."""
    json_bytes = json.dumps(contract_json).encode("utf-8")
    response = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("current.xer", BytesIO(XER_WITH_TW), "application/octet-stream"),
            "previous_xer_file": ("previous.xer", BytesIO(XER_NO_TW), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    comp = body.get("submission_comparison")
    assert comp is not None
    assert comp.get("comparison_mode") == "file_upload"
    assert comp.get("previous_programme_name") == "previous.xer"
    assert "status_change" in comp
    assert "became_aligned" in comp
    assert "became_unaligned" in comp
    assert isinstance(comp["became_aligned"], list)
    assert isinstance(comp["became_unaligned"], list)


def test_upload_only_current_submission_comparison_null(
    client: TestClient,
    contract_json: dict,
):
    """Upload only current (no previous_xer_file) → submission_comparison is null."""
    json_bytes = json.dumps(contract_json).encode("utf-8")
    response = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_WITH_TW), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("submission_comparison") is None


def test_idempotency_same_key_different_previous_xer_returns_409(
    client: TestClient,
    contract_json: dict,
):
    """Same Idempotency-Key + different previous_xer_file → 409 conflict."""
    json_bytes = json.dumps(contract_json).encode("utf-8")
    key = "test-idem-different-previous"
    headers = {"Idempotency-Key": key}
    # First request: current + previous
    r1 = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("current.xer", BytesIO(XER_WITH_TW), "application/octet-stream"),
            "previous_xer_file": ("previous.xer", BytesIO(XER_NO_TW), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    # Second request: same current, different previous (no previous this time)
    r2 = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("current.xer", BytesIO(XER_WITH_TW), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
        headers=headers,
    )
    assert r2.status_code == 409, r2.text
    err = r2.json()
    assert err.get("error_code") == "IDEMPOTENCY_CONFLICT"
    assert "error_message" in err
    assert "details" in err


def test_previous_xer_invalid_extension_returns_400(
    client: TestClient,
    contract_json: dict,
):
    """previous_xer_file with non-.xer extension → 400."""
    json_bytes = json.dumps(contract_json).encode("utf-8")
    response = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("current.xer", BytesIO(XER_WITH_TW), "application/octet-stream"),
            "previous_xer_file": ("previous.txt", BytesIO(XER_NO_TW), "text/plain"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body.get("error_code") == "BAD_REQUEST"
    assert "previous" in (body.get("error_message") or "").lower() or "previous_xer_file" in str(body.get("details", ""))


def test_previous_xer_empty_returns_400(
    client: TestClient,
    contract_json: dict,
):
    """previous_xer_file empty → 400."""
    json_bytes = json.dumps(contract_json).encode("utf-8")
    response = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("current.xer", BytesIO(XER_WITH_TW), "application/octet-stream"),
            "previous_xer_file": ("previous.xer", BytesIO(b""), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )
    assert response.status_code == 400, response.text
    body = response.json()
    assert body.get("error_code") == "BAD_REQUEST"
    assert "empty" in (body.get("error_message") or "").lower() or "empty" in str(body.get("details", "")).lower()
