from typing import Any, Dict
from uuid import uuid4
from datetime import datetime

from sqlalchemy.orm import Session
from app.db.models.evaluation_run import EvaluationRun
from app.db.models.evaluation_metric import EvaluationMetric

class EvaluationService:
    def create_evaluation_run(
        self,
        db: Session,
        model_version_id: str,
        dataset_version_id: str
    ) -> EvaluationRun:
        evaluation_run_id = str(uuid4())
        
        run = EvaluationRun(
            evaluation_run_id=evaluation_run_id,
            model_version_id=model_version_id,
            dataset_version_id=dataset_version_id,
            status="pending",
            created_at=datetime.utcnow()
        )
        
        db.add(run)
        db.commit()
        db.refresh(run)

        # Trigger Celery Background Job
        try:
            from app.tasks import run_evaluation_task
            run_evaluation_task.delay(evaluation_run_id=evaluation_run_id)
        except Exception as e:
            print(f"Warning: Failed to enqueue celery task: {e}")
            
        return run

    def get_evaluation_run(self, db: Session, evaluation_run_id: str) -> Dict[str, Any]:
        run = db.query(EvaluationRun).filter_by(evaluation_run_id=evaluation_run_id).first()
        if not run:
            raise ValueError(f"EvaluationRun {evaluation_run_id} not found")

        metrics = db.query(EvaluationMetric).filter_by(evaluation_run_id=evaluation_run_id).all()
        
        return {
            "evaluation_run_id": run.evaluation_run_id,
            "model_version_id": run.model_version_id,
            "dataset_version_id": run.dataset_version_id,
            "status": run.status,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "metrics": [
                {
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "metric_details": m.metric_details
                }
                for m in metrics
            ]
        }
