from sqlalchemy.orm import Session
from app.db.models.analysis_run import AnalysisRun

class AnalysisRunService:
    def get_analysis_run(self, db: Session, run_id: str) -> AnalysisRun:
        """Fetch an analysis run by ID."""
        run = db.query(AnalysisRun).filter(AnalysisRun.analysis_run_id == run_id).first()
        if not run:
            raise ValueError(f"AnalysisRun not found: {run_id}")
        return run
