#!/bin/bash
set -e
cd /home/spxlpt133/Desktop/Rule-intelligence-Engine
pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8000" 2>/dev/null || true
sleep 1
nohup .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/rie_api.log 2>&1 &
echo "API restarted on :8000, pid $!"
