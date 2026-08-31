import uuid
import pytest
import app.tasks as tasks
from app.db.models.workspace import Workspace
from app.db.models.feedback import Feedback
from app.db.models.rule_suggestion import RuleSuggestion
from app.db.models.model_version import ModelVersion
from app.db.models.dataset_version import DatasetVersion
from app.db.models.analysis_run import AnalysisRun

def create_base_fixtures(db):
    """Setup core testing state required for API routing relationships."""
    ws_id = f"ws-{uuid.uuid4().hex[:6]}"
    fb_id = f"fb-{uuid.uuid4().hex[:6]}"
    run_id = f"ar-{uuid.uuid4().hex[:6]}"
    sug_id = f"sug-{uuid.uuid4().hex[:6]}"

    workspace = Workspace(workspace_id=ws_id, name="Test WS", status="active")
    db.add(workspace)
    db.commit()

    feedback = Feedback(feedback_id=fb_id, workspace_id=ws_id, feedback_text="test", submitted_by="tester")
    db.add(feedback)
    
    run = AnalysisRun(analysis_run_id=run_id, feedback_id=fb_id, workspace_id=ws_id, processing_mode="realtime", status="completed")
    db.add(run)
    db.commit()

    sug = RuleSuggestion(
        suggestion_id=sug_id,
        workspace_id=ws_id,
        feedback_id=fb_id,
        analysis_run_id=run_id,
        review_status="pending_review"
    )
    db.add(sug)
    db.commit()

    return {"ws_id": ws_id, "fb_id": fb_id, "run_id": run_id, "sug_id": sug_id}


def test_clarifications_api(client, db):
    fixtures = create_base_fixtures(db)
    
    # 1. Generate a Clarification
    res = client.post("/v1/clarifications", json={
        "feedback_id": fixtures["fb_id"],
        "classification": {"confidence": 0.4},
        "extraction": {}
    })
    
    assert res.status_code == 200
    data = res.json()
    assert data["feedback_id"] == fixtures["fb_id"]
    
    clar_id = data["clarification_id"]
    if clar_id != "not-needed":
        assert data["status"] == "pending"

        # 2. Get Clarification
        res2 = client.get(f"/v1/clarifications/{clar_id}")
        assert res2.status_code == 200

        # 3. Respond to Clarification
        res3 = client.post(f"/v1/clarifications/{clar_id}/respond", json={"response": "This is a clarified metric."})
        assert res3.status_code == 200
        assert res3.json()["status"] == "answered"
        assert res3.json()["response"] == "This is a clarified metric."

def test_reviews_api(client, db):
    fixtures = create_base_fixtures(db)
    sug_id = fixtures["sug_id"]

    # 1. Create a manual Review
    res = client.post("/v1/reviews", json={
        "suggestion_id": sug_id,
        "reviewer_id": "reviewer-one",
        "priority": "high"
    })
    assert res.status_code == 200
    r_id = res.json()["review_id"]
    assert res.json()["status"] == "assigned"

    # 2. Complete Review
    res2 = client.post(f"/v1/reviews/{r_id}/complete", json={"decision": "approved", "notes": "LGTM"})
    assert res2.status_code == 200
    assert res2.json()["status"] == "completed"
    assert res2.json()["decision"] == "approved"

def test_evaluations_api(client, db):
    ws_id = f"ws-{uuid.uuid4().hex[:6]}"
    mv_id = f"mv-{uuid.uuid4().hex[:6]}"
    dv_id = f"dv-{uuid.uuid4().hex[:6]}"

    db.add(Workspace(workspace_id=ws_id, name="Test WS", status="active"))
    db.add(ModelVersion(model_version_id=mv_id, model_name="test", version="1", domain_pack_version="1", status="active", artifact_path="mock"))
    db.add(DatasetVersion(dataset_version_id=dv_id, dataset_name="test", version="1", domain_pack_version="1", annotation_version="1", source="manual", path="mock"))
    db.commit()

    # 1. Trigger Evaluation
    res = client.post("/v1/evaluations", json={"model_version_id": mv_id, "dataset_version_id": dv_id})
    assert res.status_code == 200
    eval_id = res.json()["evaluation_run_id"]
    assert res.json()["status"] == "pending"

    # 2. Force Celery Synchronous Execution
    tasks.run_evaluation_task(None, eval_id)

    # 3. Fetch Completed Evaluation with Metrics
    res2 = client.get(f"/v1/evaluations/{eval_id}")
    assert res2.status_code == 200
    data = res2.json()
    assert data["status"] == "completed"
    assert len(data["metrics"]) > 0
    assert data["metrics"][0]["metric_name"] == "accuracy"
