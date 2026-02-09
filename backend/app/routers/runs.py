"""
Analysis runs router: list, create, get, delete.
All endpoints are scoped to the current user.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.analysis_run import AnalysisRun
from app.schemas.run import RunCreate, RunListItem, RunDetail
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("", response_model=list[RunListItem])
def list_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List the current user's analysis runs, newest first."""
    runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.user_id == current_user.id)
        .order_by(AnalysisRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return runs


@router.post("", response_model=RunListItem, status_code=status.HTTP_201_CREATED)
def create_run(
    data: RunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a new analysis run for the current user."""
    run = AnalysisRun(
        user_id=current_user.id,
        contract_name=data.contract_name.strip() or "Contract",
        programme_name=data.programme_name.strip() if data.programme_name else None,
        contract_analysis=data.contract_analysis,
        validation_result=data.validation_result,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/export")
def export_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(500, ge=1, le=1000),
):
    """Export analysis history (summary list) for the current user. Does not include full payloads by default."""
    runs = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.user_id == current_user.id)
        .order_by(AnalysisRun.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "contract_name": r.contract_name,
            "programme_name": r.programme_name,
        }
        for r in runs
    ]


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get one run by id. Returns 404 if not found or not owned by current user."""
    run = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.id == run_id, AnalysisRun.user_id == current_user.id)
        .first()
    )
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis run not found.",
        )
    return run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run(
    run_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an analysis run. No-op if not found or not owned by current user."""
    run = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.id == run_id, AnalysisRun.user_id == current_user.id)
        .first()
    )
    if run:
        db.delete(run)
        db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_runs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete all analysis runs for the current user."""
    db.query(AnalysisRun).filter(AnalysisRun.user_id == current_user.id).delete()
    db.commit()
