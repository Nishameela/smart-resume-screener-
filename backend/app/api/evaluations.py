from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import evaluation_repository
from app.schemas.evaluation import EvaluationCreate, EvaluationOut, EvaluationSummaryOut
from app.services.evaluation_service import get_or_create_evaluation

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.post("", response_model=EvaluationOut, status_code=201)
def create_evaluation(payload: EvaluationCreate, db: Session = Depends(get_db)) -> EvaluationOut:
    evaluation = get_or_create_evaluation(db, payload.resume_id, payload.jd_id)
    # Re-fetch with eager-loaded requirement_matches -> requirement relationships
    # so the response doesn't trigger N+1 lazy loads.
    full = evaluation_repository.get_by_id(db, evaluation.id)
    return EvaluationOut.from_orm_evaluation(full)


@router.get("", response_model=list[EvaluationSummaryOut])
def list_evaluations(jd_id: int = Query(...), db: Session = Depends(get_db)) -> list[EvaluationSummaryOut]:
    evaluations = evaluation_repository.list_for_jd(db, jd_id)
    return [EvaluationSummaryOut.from_orm_evaluation(e) for e in evaluations]


@router.get("/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: int, db: Session = Depends(get_db)) -> EvaluationOut:
    evaluation = evaluation_repository.get_by_id(db, evaluation_id)
    if evaluation is None:
        raise NotFoundError(f"Evaluation {evaluation_id} not found.")
    return EvaluationOut.from_orm_evaluation(evaluation)
