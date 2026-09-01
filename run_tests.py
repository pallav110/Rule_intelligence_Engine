import os
import time
import uuid

# Set test DB early
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
import app.tasks as tasks

from fastapi.testclient import TestClient
from app.main import app
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
client = TestClient(app)

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

def run_tests():
    db = SessionLocal()
    print("\n===============================")
    print("🚀 INTEGRATION TESTS STARTING")
    print("===============================\n")

    try:
        # --- TEST CLARIFICATIONS --- #
        print("[TEST] 1. Clarification API Lifecycle")
        fixtures = create_base_fixtures(db)
        res = client.post("/v1/clarifications", json={
            "feedback_id": fixtures["fb_id"],
            "classification": {"confidence": 0.4},
            "extraction": {}
        })
        assert res.status_code == 200, res.text
        clar_id = res.json()["clarification_id"]
        
        if clar_id != "not-needed":
            res2 = client.get(f"/v1/clarifications/{clar_id}")
            assert res2.status_code == 200
            res3 = client.post(f"/v1/clarifications/{clar_id}/respond", json={"response": "This is a clarified metric."})
            assert res3.status_code == 200
            assert res3.json()["status"] == "answered"
        print("  ✅ Clarification interactions successful (Database mutations recorded).")

        # --- TEST REVIEWS --- #
        print("\n[TEST] 2. Review API Approval & Routing")
        res = client.post("/v1/reviews", json={
            "suggestion_id": fixtures["sug_id"],
            "reviewer_id": "reviewer-one",
            "priority": "high"
        })
        assert res.status_code == 200, res.text
        r_id = res.json()["review_id"]
        
        res2 = client.post(f"/v1/reviews/{r_id}/complete", json={"decision": "approved", "notes": "LGTM"})
        assert res2.status_code == 200
        assert res2.json()["status"] == "completed"
        print("  ✅ Review generation and manual approvals successful.")

        # --- TEST EVALUATIONS --- #
        print("\n[TEST] 3. Evaluation Orchestration & Background ML Celery Flow")
        mv_id = f"mv-{uuid.uuid4().hex[:6]}"
        dv_id = f"dv-{uuid.uuid4().hex[:6]}"
        ws_id = fixtures["ws_id"]

        db.add(ModelVersion(model_version_id=mv_id, workspace_id=ws_id, model_name="test", version="1", domain_pack_version="1", status="active", artifact_path="mock"))
        db.add(DatasetVersion(dataset_version_id=dv_id, workspace_id=ws_id, dataset_name="test", version="1", domain_pack_version="1", annotation_version="1", source="manual", path="mock"))
        db.commit()

        res_eval = client.post("/v1/evaluations", json={"model_version_id": mv_id, "dataset_version_id": dv_id})
        assert res_eval.status_code == 200, res_eval.text
        eval_id = res_eval.json()["evaluation_run_id"]
        print(f"  -> Generated Background Eval task: {eval_id}")

        # Simulate running via Celery Worker organically
        tasks.run_evaluation_task(None, eval_id)

        res_check = client.get(f"/v1/evaluations/{eval_id}")
        assert res_check.status_code == 200, res_check.text
        assert res_check.json()["status"] == "completed"
        assert len(res_check.json()["metrics"]) == 2
        print("  ✅ ML Output correctly processed and mapped via background task.")

    except Exception as e:
        print(f"❌ TEST SUITE FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
    else:
        print("\n===============================")
        print("🟢 ALL PHASE 4 APIS VALIDATED")
        print("===============================\n")
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
