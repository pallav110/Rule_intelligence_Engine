import os
import uuid
import sys
import json

os.environ["DATABASE_URL"] = "sqlite:///./prod_test.db"

from app.db.database import SessionLocal, engine
from app.db.models.workspace import Base

# Model imports
from app.db.models.workspace import Workspace
from app.db.models.feedback import Feedback
from app.db.models.rule_suggestion import RuleSuggestion
from app.db.models.model_version import ModelVersion
from app.db.models.dataset_version import DatasetVersion
from app.db.models.analysis_run import AnalysisRun

Base.metadata.create_all(bind=engine)

def create_base_fixtures():
    db = SessionLocal()
    ws_id = "ws-12345"
    fb_id = "fb-12345"
    run_id = "ar-12345"
    sug_id = "sug-12345"
    mv_id = "mv-12345"
    dv_id = "dv-12345"
    
    # Safe upsert
    if not db.get(Workspace, ws_id):
        db.add(Workspace(workspace_id=ws_id, name="Test WS", status="active"))
        db.commit()

    if not db.get(Feedback, fb_id):
        db.add(Feedback(feedback_id=fb_id, workspace_id=ws_id, feedback_text="test", submitted_by="tester"))
        db.commit()
    
    if not db.get(AnalysisRun, run_id):
        db.add(AnalysisRun(analysis_run_id=run_id, feedback_id=fb_id, workspace_id=ws_id, processing_mode="realtime", status="completed"))
        db.commit()

    if not db.get(RuleSuggestion, sug_id):
        db.add(RuleSuggestion(
            suggestion_id=sug_id,
            workspace_id=ws_id,
            feedback_id=fb_id,
            analysis_run_id=run_id,
            review_status="pending_review"
        ))
        db.commit()

    if not db.get(ModelVersion, mv_id):
        db.add(ModelVersion(model_version_id=mv_id, model_name="test", version="1", status="active", artifact_path="mock"))
        db.commit()

    if not db.get(DatasetVersion, dv_id):
        db.add(DatasetVersion(dataset_version_id=dv_id, dataset_name="test", version="1", domain_pack_version="1", annotation_version="1", source="manual", path="mock"))
        db.commit()

    db.close()
    
    # OUTPUT as JSON for bash script to ingest
    print(json.dumps({"ws_id": ws_id, "fb_id": fb_id, "run_id": run_id, "sug_id": sug_id, "mv_id": mv_id, "dv_id": dv_id}))

create_base_fixtures()
