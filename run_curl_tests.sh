#!/bin/bash
set -e

echo "====================================="
echo "🚀 INITIATING CURL INTEGRATION TESTS"
echo "====================================="

export DATABASE_URL="sqlite:///./prod_test.db"
export PYTHONPATH="."

# Cleanup old test state safely
rm -f prod_test.db
echo "[System] Cleared old test database."

# Start background services
echo "[System] Starting Uvicorn API Server..."
.venv/bin/python -m uvicorn app.main:app > uvicorn.log 2>&1 &
UVICORN_PID=$!

echo "[System] Starting Celery ML Background Worker..."
.venv/bin/celery -A app.worker.celery_app worker --loglevel=info > celery.log 2>&1 &
CELERY_PID=$!

echo "[System] Waiting 4 seconds for services to boot..."
sleep 4

# Generate fixtures
echo "[System] Provisioning base DB schemas and test fixtures..."
FIXTURE_JSON=$(PYTHONPATH=. .venv/bin/python setup_curl_fixtures.py)

# Extract using python json module directly
FB_ID=$(echo $FIXTURE_JSON | PYTHONPATH=. .venv/bin/python -c "import sys, json; print(json.load(sys.stdin)['fb_id'])")
SUG_ID=$(echo $FIXTURE_JSON | PYTHONPATH=. .venv/bin/python -c "import sys, json; print(json.load(sys.stdin)['sug_id'])")
MV_ID=$(echo $FIXTURE_JSON | PYTHONPATH=. .venv/bin/python -c "import sys, json; print(json.load(sys.stdin)['mv_id'])")
DV_ID=$(echo $FIXTURE_JSON | PYTHONPATH=. .venv/bin/python -c "import sys, json; print(json.load(sys.stdin)['dv_id'])")

# Run tests
echo ""
echo "--- TEST 1: Clarification API ---"
echo "POST /v1/clarifications"
CLAR_RES=$(curl -s -X 'POST' 'http://127.0.0.1:8000/v1/clarifications' -H 'accept: application/json' -H 'Content-Type: application/json' -d "{\"feedback_id\": \"$FB_ID\", \"classification\": {\"confidence\": 0.4}, \"extraction\": {}}")
echo "Response: $CLAR_RES"
CLAR_ID=$(echo $CLAR_RES | PYTHONPATH=. .venv/bin/python -c "import sys, json; d=json.load(sys.stdin); print(d.get('clarification_id', 'ERROR'))")

echo "POST /v1/clarifications/$CLAR_ID/respond"
curl -s -X 'POST' "http://127.0.0.1:8000/v1/clarifications/$CLAR_ID/respond" -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"response": "Human answer: employees only."}'
echo -e "\n✅ Clarifications tested"

echo ""
echo "--- TEST 2: Review API ---"
echo "POST /v1/reviews"
REV_RES=$(curl -s -X 'POST' 'http://127.0.0.1:8000/v1/reviews' -H 'accept: application/json' -H 'Content-Type: application/json' -d "{\"suggestion_id\": \"$SUG_ID\", \"reviewer_id\": \"test_user\", \"priority\": \"normal\"}")
echo "Response: $REV_RES"
REV_ID=$(echo $REV_RES | PYTHONPATH=. .venv/bin/python -c "import sys, json; d=json.load(sys.stdin); print(d.get('review_id', 'ERROR'))")

echo "POST /v1/reviews/$REV_ID/complete"
curl -s -X 'POST' "http://127.0.0.1:8000/v1/reviews/$REV_ID/complete" -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"decision": "approved", "notes": "Approved curl tests"}'
echo -e "\n✅ Reviews tested"

echo ""
echo "--- TEST 3: Evaluation Background Celery Queue ---"
echo "POST /v1/evaluations"
EVAL_RES=$(curl -s -X 'POST' 'http://127.0.0.1:8000/v1/evaluations' -H 'accept: application/json' -H 'Content-Type: application/json' -d "{\"model_version_id\": \"$MV_ID\", \"dataset_version_id\": \"$DV_ID\"}")
echo "Response: $EVAL_RES"
EVAL_ID=$(echo $EVAL_RES | PYTHONPATH=. .venv/bin/python -c "import sys, json; d=json.load(sys.stdin); print(d.get('evaluation_run_id', 'ERROR'))")

echo "[System] Sleeping 5s to allow Celery worker to consume the task natively..."
sleep 5

echo "GET /v1/evaluations/$EVAL_ID"
GET_EVAL_RES=$(curl -s -X 'GET' "http://127.0.0.1:8000/v1/evaluations/$EVAL_ID" -H 'accept: application/json')
echo "Response: $GET_EVAL_RES"
echo -e "\n✅ Evaluations background jobs matched"

# Cleanup
echo ""
echo "[System] Shutting down FastApi and Celery..."
kill $UVICORN_PID || true
kill $CELERY_PID || true
rm -f prod_test.db
echo "====================================="
echo "🟢 API INTEGRATION COMPLETE"
echo "====================================="
