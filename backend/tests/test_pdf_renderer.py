"""
Tests for PDF renderer (Step 4B.2). Pure rendering only; no validator.
Requires reportlab (see requirements.txt). Uses pdfplumber for text extraction in assertions.
"""

import io
import pytest
import pdfplumber

from app.review.pdf_export_builder import build_pdf_export_input


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes for assertions (content is compressed in stream)."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
        return " ".join(p.extract_text() or "" for p in doc.pages)
from app.review.pdf_renderer import render_programme_review_pdf
from app.review.programme_review_pack import build_programme_review_pack
from app.persistence.submission_store import SubmissionStore, create_submission_record
from app.persistence.acceptance_store import AcceptanceStore
from app.storage.local_storage import LocalStorage
from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics
from app.evolution.submission_evolution import build_submission_evolution
from app.guidance.planner_guidance import build_planner_guidance


def _export_payload_not_acceptable(submission_store, acceptance_store, submission_id: str = "sub-not") -> dict:
    """Build export payload for NOT_ACCEPTABLE with one blocker."""
    vr = {
        "acceptability_status": "NOT_ACCEPTABLE",
        "overall_status": "fail",
        "obligations_report": [
            {
                "id": "OBL-001",
                "aligned": False,
                "mandatory_for_acceptance": True,
                "original_contract_text": "Temporary Works",
                "evidence_mode": "WBS_ONLY",
                "canonical_match_string": "temporary works",
                "required_action": "Add WBS containing 'temporary works'",
            },
        ],
        "obligations_not_represented_but_mandatory": [
            {"id": "OBL-001", "original_contract_text": "Temporary Works", "required_action": "Add WBS containing 'temporary works'"},
        ],
    }
    rec = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id=submission_id,
    )
    submission_store.save(rec)
    pack = build_programme_review_pack(submission_id, submission_store, acceptance_store)
    return build_pdf_export_input(pack)


def _export_payload_acceptable(submission_store, acceptance_store, submission_id: str = "sub-acc") -> dict:
    """Build export payload for ACCEPTABLE, no blockers."""
    vr = {
        "acceptability_status": "ACCEPTABLE",
        "overall_status": "pass",
        "obligations_report": [
            {"id": "OBL-001", "aligned": True, "mandatory_for_acceptance": True, "original_contract_text": "Temporary Works"},
        ],
        "obligations_not_represented_but_mandatory": [],
    }
    rec = create_submission_record(
        project_id="proj-1",
        programme_name="Programme A",
        submission_stage="initial",
        validation_response=vr,
        planner_assumptions_used=[],
        diagnostics_output=build_obligation_diagnostics(vr),
        evolution_output=build_submission_evolution(vr),
        planner_guidance_output=build_planner_guidance(vr),
        submission_id=submission_id,
    )
    submission_store.save(rec)
    pack = build_programme_review_pack(submission_id, submission_store, acceptance_store)
    return build_pdf_export_input(pack)


@pytest.fixture
def tmp_dirs(tmp_path):
    sub_dir = tmp_path / "submissions"
    acc_dir = tmp_path / "acceptance"
    sub_dir.mkdir()
    acc_dir.mkdir()
    return sub_dir, acc_dir


@pytest.fixture
def submission_store(tmp_dirs):
    return SubmissionStore(storage=LocalStorage(tmp_dirs[0]))


@pytest.fixture
def acceptance_store(tmp_dirs, submission_store):
    return AcceptanceStore(storage=LocalStorage(tmp_dirs[1]), submission_store=submission_store)


def test_renders_not_acceptable_with_blockers(submission_store, acceptance_store, request):
    """Renders NOT_ACCEPTABLE with blockers; PDF is valid and non-empty."""
    sid = f"sub-not-{request.node.name}"
    payload = _export_payload_not_acceptable(submission_store, acceptance_store, submission_id=sid)
    pdf_bytes = render_programme_review_pdf(payload)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")
    text = _pdf_text(pdf_bytes)
    assert "NOT_ACCEPTABLE" in text or "NOT ACCEPTABLE" in text
    assert "Temporary Works" in text
    assert "Add WBS" in text or "temporary works" in text


def test_renders_acceptable_cleanly(submission_store, acceptance_store, request):
    """Renders ACCEPTABLE submission; PDF is valid, no blockers table content."""
    sid = f"sub-acc-{request.node.name}"
    payload = _export_payload_acceptable(submission_store, acceptance_store, submission_id=sid)
    pdf_bytes = render_programme_review_pdf(payload)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF-")
    text = _pdf_text(pdf_bytes)
    assert "ACCEPTABLE" in text
    assert payload["mandatory_obligations_status"]["not_represented"] == []


def test_governance_visible_does_not_alter_acceptability(
    submission_store,
    acceptance_store,
    request,
):
    """Governance section visible in PDF; acceptability remains NOT_ACCEPTABLE."""
    sid = f"sub-not-{request.node.name}"
    payload = _export_payload_not_acceptable(submission_store, acceptance_store, submission_id=sid)
    from app.governance.acceptance_records import create_acceptance_record
    acc = create_acceptance_record(
        submission_id=sid,
        project_id="proj-1",
        decision="ACCEPT_WITH_COMMENTS",
        decided_by="PM",
        comments="Accepted with exceptions.",
    )
    acceptance_store.save_acceptance(acc)
    pack = build_programme_review_pack(sid, submission_store, acceptance_store)
    payload = build_pdf_export_input(pack)

    assert payload["legal_acceptability"]["acceptability_status"] == "NOT_ACCEPTABLE"
    assert payload["governance"]["latest_acceptance_decision"] == "ACCEPT_WITH_COMMENTS"

    pdf_bytes = render_programme_review_pdf(payload)
    text = _pdf_text(pdf_bytes)
    assert "ACCEPT_WITH_COMMENTS" in text or "ACCEPT WITH COMMENTS" in text
    assert "NOT_ACCEPTABLE" in text or "NOT ACCEPTABLE" in text


def test_missing_sections_runtime_error():
    """Missing required sections → RuntimeError; no silent continue."""
    with pytest.raises(RuntimeError) as exc_info:
        render_programme_review_pdf({})
    assert "Missing" in str(exc_info.value) or "section" in str(exc_info.value).lower()

    with pytest.raises(RuntimeError) as exc_info:
        render_programme_review_pdf({"cover": {}, "legal_acceptability": {}})
    assert "Missing" in str(exc_info.value) or "section" in str(exc_info.value).lower()

    with pytest.raises(RuntimeError):
        render_programme_review_pdf(None)
    with pytest.raises(RuntimeError):
        render_programme_review_pdf("not a dict")
