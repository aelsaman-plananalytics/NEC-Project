"""
Tests for Production Hardening Phase 2.
Covers: preferences snapshot, retention scheduler, storage abstraction,
run-level immutability, plan gating, health endpoint, performance logging.
Does NOT modify comprehensive_validator, acceptability logic, or evidence modes.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from sqlalchemy.orm import Session
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.analysis_run import AnalysisRun
from app.database import get_db
from app.storage.local_storage import LocalStorage


# --- Storage abstraction ---

def test_local_storage_save_load_json(tmp_path):
    """Storage abstraction: save_json and load_json round-trip."""
    storage = LocalStorage(base_dir=tmp_path)
    path = "test_data/foo.json"
    data = {"a": 1, "b": "two"}
    storage.save_json(path, data)
    assert storage.exists(path)
    loaded = storage.load_json(path)
    assert loaded == data
    storage.delete(path)
    assert not storage.exists(path)
    assert storage.load_json(path) is None


def test_local_storage_save_load_bytes(tmp_path):
    """Storage abstraction: save_bytes and load_bytes round-trip."""
    storage = LocalStorage(base_dir=tmp_path)
    path = "blobs/bar.bin"
    payload = b"hello world"
    storage.save_bytes(path, payload)
    assert storage.exists(path)
    assert storage.load_bytes(path) == payload
    storage.delete(path)
    assert not storage.exists(path)


def test_local_storage_list_paths(tmp_path):
    """Storage abstraction: list_paths returns relative paths under prefix."""
    storage = LocalStorage(base_dir=tmp_path)
    storage.save_json("dir/a.json", {})
    storage.save_json("dir/b.json", {})
    storage.save_json("other/c.json", {})
    listed = storage.list_paths("dir")
    assert len(listed) == 2
    assert "dir/a.json" in listed or "a.json" in listed or any("a.json" in p for p in listed)
    assert "dir/b.json" in listed or "b.json" in listed or any("b.json" in p for p in listed)


# --- Run-level immutability (validation_result) ---

def test_validation_result_immutability_raises_on_update():
    """Attempting to modify validation_result after insert raises RuntimeError (event listener)."""
    from app.models.analysis_run import _reject_validation_result_update, AnalysisRun

    mapper = MagicMock()
    mapper.class_ = AnalysisRun
    target = MagicMock()
    # Simulate attribute history: validation_result was modified (has_changes=True, modified non-empty)
    hist = MagicMock(has_changes=MagicMock(return_value=True), modified=(1, 2), deleted=())
    with patch("app.models.analysis_run.attributes.get_history", return_value=hist):
        with pytest.raises(RuntimeError) as exc_info:
            _reject_validation_result_update(mapper, None, target)
        assert "immutable" in str(exc_info.value).lower() or "validation_result" in str(exc_info.value)


# --- Health endpoint extended fields ---

def test_health_v1_includes_extended_fields():
    """GET /api/v1/health returns storage_check, scheduler_running, database_connected."""
    from app.main import app
    client = TestClient(app)
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "version" in body
    assert "integrity" in body
    assert "ledger_chain_check" in body
    assert "storage_check" in body
    assert "scheduler_running" in body
    assert "database_connected" in body


# --- Retention not run on startup ---

def test_startup_calls_scheduler_not_retention_directly():
    """On startup (lifespan), start_scheduler is used; run_retention_cleanup is not called directly."""
    with patch("app.scheduler.start_scheduler") as mock_start:
        with patch("app.scheduler.shutdown_scheduler"):
            with patch("app.services.retention_job.run_retention_cleanup") as mock_retention:
                from app.main import lifespan
                import asyncio
                async def run_lifespan():
                    async with lifespan(None):
                        pass
                asyncio.run(run_lifespan())
                mock_start.assert_called_once()
                mock_retention.assert_not_called()


# --- Plan limit enforcement ---

def test_plan_limit_exceeded_returns_403():
    """When authenticated user has runs_this_month >= monthly_run_limit, validate_programme returns 403."""
    from app.routers import validate_programme as vp_router
    from app.routers.auth import get_current_user_optional

    app = FastAPI()
    app.include_router(vp_router.router)

    limited_user = MagicMock()
    limited_user.id = 1
    limited_user.plan_type = "free"
    limited_user.monthly_run_limit = 10
    limited_user.runs_this_month = 10
    limited_user.runs_reset_date = date.today() + timedelta(days=30)

    def override_user():
        return limited_user

    mock_db = MagicMock(spec=Session)

    def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user_optional] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        contract = {
            "programme_compliance_model": {"required_activities": []},
            "contract_dates": {},
            "obligation_entities": {"frozen_requirements_version": 7, "obligations": []},
        }
        xer_minimal = b"""%T\tPROJWBS\n%F\twbs_id\tparent_wbs_id\twbs_name\n%R\t1\t\tDesign\n%E\tPROJWBS\n%T\tTASK\n%F\ttask_id\ttask_name\twbs_id\n%R\t1\tDesign\t1\n%E\tTASK\n"""
        payload = {
            "xer_file": ("test.xer", xer_minimal, "application/octet-stream"),
            "json_file": ("contract.json", json.dumps(contract).encode(), "application/json"),
        }
        r = client.post("/api/v1/validate_programme", files=payload)
        assert r.status_code == 403
        body = r.json()
        assert body.get("error_code") == "PLAN_LIMIT_EXCEEDED"
    finally:
        app.dependency_overrides.clear()


# --- Preferences snapshot (run stores snapshot) ---

def test_run_has_preferences_snapshot_field():
    """AnalysisRun model has preferences_snapshot column (schema/usage)."""
    assert hasattr(AnalysisRun, "preferences_snapshot")
