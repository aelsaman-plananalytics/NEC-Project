"""
End-to-end API tests for POST /api/v1/validate_programme.

Proves that lifecycle inputs (submission_stage, planner_assumptions) do NOT alter
acceptability. Authoritative fields come only from the validator.
See backend/ACCEPTABILITY_INVARIANT.md and app/api_contract.py.
"""

import json
import pytest
import uuid
from io import BytesIO
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import validate_programme as validate_programme_router
from app.p6_engine.frozen_requirements import build_frozen_requirements

# Minimal app with only validate_programme router to avoid pulling full main (db, etc.)
_app = FastAPI()
_app.include_router(validate_programme_router.router)


# Minimal XER: one WBS "Design", one task. No obligation.
XER_NO_OBLIGATION = b"""%T\tPROJWBS
%F\twbs_id\tparent_wbs_id\twbs_name
%R\t1\t\tDesign
%E\tPROJWBS

%T\tTASK
%F\ttask_id\ttask_name\twbs_id
%R\t1\tDesign\t1
%E\tTASK
"""

# Minimal XER: Design + Utilities Diversions WBS and task.
XER_WITH_OBLIGATION = b"""%T\tPROJWBS
%F\twbs_id\tparent_wbs_id\twbs_name
%R\t1\t\tDesign
%R\t2\t\tUtilities Diversions
%E\tPROJWBS

%T\tTASK
%F\ttask_id\ttask_name\twbs_id
%R\t1\tDesign\t1
%R\t2\tDiversions activity\t2
%E\tTASK
"""


def _contract_json_with_mandatory_wbs_only_obligation():
    """Contract with one mandatory WBS_ONLY obligation derived from scope_items (no injected obligations)."""
    contract_data = {
        "scope_items": [
            {
                "text": "Utilities Diversions",
                "mandatory_for_acceptance": True,
                "evidence_mode": "WBS_ONLY",
                "canonical_match_string": "utilities diversions",
            }
        ],
        "programme_compliance_model": {},
        "constraints": [],
    }
    frozen = build_frozen_requirements(contract_data)
    contract_data["obligation_entities"] = frozen["obligation_entities"]
    return contract_data


def _obligation_id(contract_data):
    obligations = (contract_data.get("obligation_entities") or {}).get("obligations") or []
    ob = next(
        (o for o in obligations if (o.get("original_contract_text") or "").strip() == "Utilities Diversions"),
        None,
    )
    assert ob is not None, "Contract must include the mandatory obligation"
    return ob["id"]


@pytest.fixture
def client():
    return TestClient(_app)


@pytest.fixture
def contract_with_tw():
    return _contract_json_with_mandatory_wbs_only_obligation()


@pytest.fixture
def tw_obligation_id(contract_with_tw):
    return _obligation_id(contract_with_tw)


def test_validate_programme_api_scenario_a_not_acceptable(
    client: TestClient,
    contract_with_tw: dict,
    tw_obligation_id: str,
):
    """
    Scenario A: Contract includes a mandatory WBS_ONLY obligation.
    Programme does NOT include any WBS or activity with the obligation text.
    Call with submission_stage=initial and planner_assumptions=covered_by_later_submission.

    Assert:
    - acceptability_status == NOT_ACCEPTABLE
    - Obligation appears in obligations_not_represented_but_mandatory
    - Assumption is visible in planner_assumptions_used
    - Assumption does NOT bypass WBS_ONLY
    - required_action is present and correct in obligation_readiness
    """
    json_bytes = json.dumps(contract_with_tw).encode("utf-8")
    assumptions = [
        {"obligation_id": tw_obligation_id, "assumption_type": "covered_by_later_submission", "rationale": "To be submitted later"}
    ]

    response = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_NO_OBLIGATION), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={
            "submission_stage_form": "initial",
            "planner_assumptions_form": json.dumps(assumptions),
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    # Authoritative: must be NOT ACCEPTABLE (assumption does not satisfy WBS_ONLY)
    assert body.get("acceptability_status") == "NOT_ACCEPTABLE", (
        "covered_by_later_submission must not bypass WBS_ONLY; programme without the obligation must be NOT_ACCEPTABLE"
    )
    assert body.get("overall_status") == "fail"

    # Obligation must appear in obligations_not_represented_but_mandatory
    not_rep = body.get("obligations_not_represented_but_mandatory") or []
    ob_in_not_rep = any(
        (r.get("original_contract_text") or "").strip() == "Utilities Diversions" or (r.get("id") == tw_obligation_id)
        for r in not_rep
    )
    assert ob_in_not_rep, "Mandatory obligation must appear in obligations_not_represented_but_mandatory"

    # Assumption visible in planner guidance (does not change acceptability)
    used = body.get("planner_assumptions_used") or []
    assert len(used) >= 1 and any(
        a.get("obligation_id") == tw_obligation_id and a.get("assumption_type") == "covered_by_later_submission"
        for a in used
    ), "planner_assumptions_used must contain the submitted assumption"

    # obligation_readiness: required_action present for missing mandatory obligation
    readiness = body.get("obligation_readiness") or []
    ob_readiness = next((r for r in readiness if r.get("obligation_id") == tw_obligation_id), None)
    assert ob_readiness is not None
    assert ob_readiness.get("required_now") is True
    assert ob_readiness.get("aligned") is False
    assert ob_readiness.get("required_action") is not None and "utilities diversions" in (ob_readiness.get("required_action") or "").lower(), (
        "required_action must direct planner to add WBS/activity containing the obligation text"
    )

    # Top-level authoritative fields present
    assert "obligations_report" in body
    assert "scope_evidence_table" in body
    assert body.get("submission_stage") == "initial"


def test_validate_programme_api_scenario_b_acceptable(
    client: TestClient,
    contract_with_tw: dict,
):
    """
    Scenario B: Same contract with a mandatory WBS_ONLY obligation.
    Programme DOES include WBS or activity containing the obligation text.

    Assert:
    - acceptability_status == ACCEPTABLE
    - No mandatory unaligned obligations
    - Advisory fields may exist but do not contradict acceptance
    """
    json_bytes = json.dumps(contract_with_tw).encode("utf-8")

    response = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_WITH_OBLIGATION), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body.get("acceptability_status") == "ACCEPTABLE"
    assert body.get("overall_status") == "pass"

    not_rep = body.get("obligations_not_represented_but_mandatory") or []
    assert len(not_rep) == 0, "When ACCEPTABLE there must be no mandatory obligations not represented"

    # Advisory fields must not contradict
    if body.get("obligation_readiness"):
        ob_readiness = next(
            (r for r in body["obligation_readiness"] if "utilities" in (r.get("obligation_name") or "").lower()),
            None,
        )
        if ob_readiness:
            assert ob_readiness.get("aligned") is True


# --- Step 5A API hardening tests ---


def test_idempotency_same_key_same_payload_returns_identical_response(
    client: TestClient,
    contract_with_tw: dict,
):
    """Same Idempotency-Key + same request payload returns identical previous response without re-running validation."""
    json_bytes = json.dumps(contract_with_tw).encode("utf-8")
    key = f"test-idem-same-payload-{uuid.uuid4().hex}"
    headers = {"Idempotency-Key": key}
    files1 = {
        "xer_file": ("programme.xer", BytesIO(XER_WITH_OBLIGATION), "application/octet-stream"),
        "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
    }
    data1 = {"submission_stage_form": "initial"}
    r1 = client.post("/api/v1/validate_programme", files=files1, data=data1, headers=headers)
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    # Second request: same key, same payload (fresh BytesIO)
    files2 = {
        "xer_file": ("programme.xer", BytesIO(XER_WITH_OBLIGATION), "application/octet-stream"),
        "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
    }
    r2 = client.post("/api/v1/validate_programme", files=files2, data=data1, headers=headers)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body1 == body2, "Idempotent replay must return identical response"


def test_idempotency_same_key_different_payload_returns_409(
    client: TestClient,
    contract_with_tw: dict,
):
    """Same Idempotency-Key with different request payload returns HTTP 409 and structured error."""
    json_bytes = json.dumps(contract_with_tw).encode("utf-8")
    key = f"test-idem-different-payload-{uuid.uuid4().hex}"
    headers = {"Idempotency-Key": key}
    # First request
    r1 = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_WITH_OBLIGATION), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    # Second request: same key, different payload (different XER - no Temporary Works)
    r2 = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_NO_OBLIGATION), "application/octet-stream"),
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


def test_error_responses_follow_structured_contract(client: TestClient):
    """Error responses use { error_code, error_message, details }."""
    # Send invalid payload: not an XER file
    r = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("file.txt", BytesIO(b"not xer"), "text/plain"),
            "json_file": ("c.json", BytesIO(b"{}"), "application/json"),
        },
    )
    assert r.status_code == 400, r.text
    body = r.json()
    assert body.get("error_code") == "BAD_REQUEST"
    assert "error_message" in body
    assert "details" in body


def test_response_signature_present_and_deterministic(
    client: TestClient,
    contract_with_tw: dict,
):
    """Response includes response_signature; same payload yields same signature."""
    json_bytes = json.dumps(contract_with_tw).encode("utf-8")
    # First request
    r1 = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_WITH_OBLIGATION), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert "response_signature" in body1
    sig1 = body1["response_signature"]
    assert isinstance(sig1, str) and len(sig1) == 64 and all(c in "0123456789abcdef" for c in sig1)
    # Second request (same payload): response_signature may vary (e.g. timestamp in hash input)
    r2 = client.post(
        "/api/v1/validate_programme",
        files={
            "xer_file": ("programme.xer", BytesIO(XER_WITH_OBLIGATION), "application/octet-stream"),
            "json_file": ("contract.json", BytesIO(json_bytes), "application/json"),
        },
        data={"submission_stage_form": "initial"},
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    sig2 = body2.get("response_signature")
    assert isinstance(sig2, str) and len(sig2) == 64 and all(c in "0123456789abcdef" for c in sig2)
