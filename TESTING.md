# Week 3 Complete Testing Guide

## 🚀 Quick Start - One Command to Run Everything

```bash
# Start the complete stack
docker-compose up -d

# Wait for services to be healthy (30-40 seconds)
sleep 40

# Access dashboard
open http://localhost:8000
```

---

## ✅ Phase 1: System Health Checks

### 1.1 Verify All Services Running
```bash
docker-compose ps

# Expected output: All containers RUNNING ✓
```

### 1.2 Check API Health
```bash
curl -s http://localhost:8000/health | jq .
# Expected: {"status": "healthy"}

curl -s http://localhost:8000/ready | jq .
# Expected: {"status": "ready"}
```

### 1.3 Verify Database Connection
```bash
docker-compose exec db psql -U rie_user -d rule_intelligence_engine -c "\dt"
# Should list all tables
```

### 1.4 Verify Redis Connection
```bash
docker-compose exec redis redis-cli ping
# Expected: PONG
```

---

## 🧪 Phase 2: ML Pipeline Testing

### 2.1 Test Classification (TF-IDF + LR)
```bash
curl -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "Revenue calculation should exclude promotional discounts from the total amount",
    "feedback_id": "test-classify-001",
    "workspace_id": "default",
    "schema_context": {
      "available_tables": ["orders", "customers", "products"],
      "available_columns": ["order_id", "revenue", "discount", "customer_id"]
    }
  }' | jq .

# Expected Response:
# {
#   "feedback_type": "business_rule_correction",
#   "rule_category": "metric_definition",
#   "is_actionable": true,
#   "requires_clarification": false,
#   "confidence": 0.85,
#   "extracted_rules": {...},
#   "suggestion": {...},
#   "clarification": null
# }
```

### 2.2 Test Rule Extraction
```bash
curl -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "Customer retention metric must exclude inactive users marked with status=inactive and last_login < 90 days ago",
    "feedback_id": "test-extract-001",
    "workspace_id": "default",
    "schema_context": {
      "available_tables": ["customers"],
      "available_columns": ["customer_id", "status", "last_login"]
    }
  }' | jq '.extracted_rules'

# Expected: Rules with business_term, operation, conditions, scope, threshold
```

### 2.3 Test Confidence Scoring
```bash
# Low confidence (ambiguous text)
curl -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "something",
    "feedback_id": "test-conf-low",
    "workspace_id": "default",
    "schema_context": {"available_tables": [], "available_columns": []}
  }' | jq '.confidence'

# High confidence (clear text)
curl -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "Customer retention revenue metric should include only active subscribers with subscription_status=active and payment_status=current",
    "feedback_id": "test-conf-high",
    "workspace_id": "default",
    "schema_context": {"available_tables": ["subscriptions"], "available_columns": ["subscription_status", "payment_status"]}
  }' | jq '.confidence'
```

---

## 💡 Phase 3: Service Layer Testing

### 3.1 Test Suggestion Workflow
```bash
# Create suggestion
SUGG_ID=$(curl -s -X POST http://localhost:8000/v1/suggestions \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "default",
    "feedback_id": "fb-sugg-001",
    "suggested_rule": {
      "business_term": "revenue_metric",
      "operation": "exclude",
      "conditions": [{"field": "discount", "operator": ">", "value": 0}]
    },
    "confidence": 0.92
  }' | jq -r '.suggestion_id')

echo "Created suggestion: $SUGG_ID"

# Get suggestion
curl -s http://localhost:8000/v1/suggestions/$SUGG_ID | jq '.status'
# Expected: "pending_review"

# Approve suggestion
curl -s -X POST http://localhost:8000/v1/suggestions/$SUGG_ID/approve \
  -H "Content-Type: application/json" \
  -d '{"reviewer_id": "reviewer-1"}' | jq '.status'
# Expected: "approved"

# List suggestions
curl -s http://localhost:8000/v1/suggestions | jq 'length'
# Should show created suggestions
```

### 3.2 Test Clarification Workflow
```bash
# Create clarification
CLAR_ID=$(curl -s -X POST http://localhost:8000/v1/clarifications \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_id": "fb-clar-001",
    "classification_result": {
      "feedback_type": "data_quality_issue",
      "rule_category": "metric_definition"
    },
    "questions_needed": ["What is the exact threshold?", "How should edge cases be handled?"]
  }' | jq -r '.clarification_id')

echo "Created clarification: $CLAR_ID"

# Get clarification
curl -s http://localhost:8000/v1/clarifications/$CLAR_ID | jq '.status'

# Respond to clarification
curl -s -X POST http://localhost:8000/v1/clarifications/$CLAR_ID/respond \
  -H "Content-Type: application/json" \
  -d '{"response": "Threshold should be 90 days of inactivity"}' | jq '.status'
```

### 3.3 Test Review Workflow
```bash
# Create review
REVIEW_ID=$(curl -s -X POST http://localhost:8000/v1/reviews \
  -H "Content-Type: application/json" \
  -d '{
    "suggestion_id": "'$SUGG_ID'",
    "review_type": "manual"
  }' | jq -r '.review_id')

echo "Created review: $REVIEW_ID"

# Get review
curl -s http://localhost:8000/v1/reviews/$REVIEW_ID | jq '.status'

# Complete review
curl -s -X POST http://localhost:8000/v1/reviews/$REVIEW_ID/complete \
  -H "Content-Type: application/json" \
  -d '{
    "final_decision": "approved",
    "comments": "Rule looks good, ready for production"
  }' | jq '.status'
```

---

## 📊 Phase 4: Database Integration Testing

### 4.1 Verify Data Persistence
```bash
# Insert test data directly
docker-compose exec db psql -U rie_user -d rule_intelligence_engine -c "
  INSERT INTO feedbacks (feedback_id, workspace_id, feedback_text, status)
  VALUES ('test-db-001', 'default', 'Test feedback', 'processed');
"

# Retrieve data
docker-compose exec db psql -U rie_user -d rule_intelligence_engine -c "
  SELECT * FROM feedbacks WHERE feedback_id = 'test-db-001';
"
```

### 4.2 Verify Relationships
```bash
docker-compose exec db psql -U rie_user -d rule_intelligence_engine -c "
  SELECT 
    f.feedback_id,
    rs.suggestion_id,
    r.review_id
  FROM feedbacks f
  LEFT JOIN rule_suggestions rs ON f.feedback_id = rs.feedback_id
  LEFT JOIN reviews r ON rs.suggestion_id = r.suggestion_id
  LIMIT 5;
"
```

---

## 🎨 Phase 5: UI/Dashboard Testing

### 5.1 Test Dashboard Access
```bash
# Dashboard should load
curl -s http://localhost:8000 | head -20

# Check static files
curl -s http://localhost:8000/ui/dashboard.html | head -20
```

### 5.2 Interactive Testing
1. Open browser: `http://localhost:8000`
2. Navigate through pages:
   - ✓ Feedback Analysis page
   - ✓ Rule Extraction page
   - ✓ Suggestions page
   - ✓ Clarifications page
   - ✓ Reviews page
   - ✓ System Status page
3. Submit test forms and verify responses

---

## 🔄 Phase 6: End-to-End Pipeline Testing

### 6.1 Complete Workflow Test
```bash
#!/bin/bash

# Step 1: Analyze feedback
echo "Step 1: Analyzing feedback..."
FEEDBACK_ID="e2e-test-$(date +%s)"
ANALYSIS=$(curl -s -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "Customer revenue metric should exclude test transactions where merchant_id = 999",
    "feedback_id": "'$FEEDBACK_ID'",
    "workspace_id": "default",
    "schema_context": {
      "available_tables": ["transactions"],
      "available_columns": ["merchant_id", "amount"]
    }
  }')

echo $ANALYSIS | jq '.feedback_type, .is_actionable'

# Step 2: Create suggestion
echo "Step 2: Creating suggestion..."
SUGG_ID=$(echo $ANALYSIS | jq -r '.suggestion.suggestion_id // "null"')
if [ "$SUGG_ID" != "null" ]; then
  echo "Suggestion created: $SUGG_ID"
  
  # Step 3: Create review
  echo "Step 3: Creating review..."
  REVIEW=$(curl -s -X POST http://localhost:8000/v1/reviews \
    -H "Content-Type: application/json" \
    -d '{
      "suggestion_id": "'$SUGG_ID'",
      "review_type": "manual"
    }')
  
  REVIEW_ID=$(echo $REVIEW | jq -r '.review_id')
  echo "Review created: $REVIEW_ID"
  
  # Step 4: Complete review
  echo "Step 4: Completing review..."
  curl -s -X POST http://localhost:8000/v1/reviews/$REVIEW_ID/complete \
    -H "Content-Type: application/json" \
    -d '{
      "final_decision": "approved",
      "comments": "Automated E2E test - approved"
    }' | jq '.status'
  
  echo "✓ End-to-end workflow completed successfully!"
else
  echo "✗ No suggestion generated"
fi
```

---

## ⚡ Phase 7: Load & Performance Testing

### 7.1 Response Time Testing
```bash
# Test API response time
time curl -s -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "feedback_text": "Test feedback",
    "feedback_id": "perf-test-1",
    "workspace_id": "default",
    "schema_context": {"available_tables": [], "available_columns": []}
  }' > /dev/null

# Expected: < 200ms for classification
# Expected: < 500ms for full pipeline
```

### 7.2 Concurrent Requests (Apache Bench)
```bash
# Test with 100 requests, 10 concurrent
ab -n 100 -c 10 http://localhost:8000/health

# Expected: Success rate 100%, avg response time < 50ms
```

### 7.3 Stress Test (wrk)
```bash
# Install wrk: brew install wrk (Mac) or apt-get install wrk (Linux)

wrk -t4 -c100 -d30s http://localhost:8000/health

# Expected: Handle 1000+ req/sec
```

---

## 🐛 Phase 8: Error Handling Testing

### 8.1 Invalid Input
```bash
# Missing required field
curl -s -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{}' | jq '.detail'

# Expected: Validation error message
```

### 8.2 Non-existent Resource
```bash
curl -s http://localhost:8000/v1/suggestions/non-existent-id | jq '.detail'

# Expected: 404 error
```

### 8.3 Database Connection Error
```bash
# Stop database
docker-compose stop db

# Try API call
curl -s http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{"feedback_text": "test"}' | jq '.detail'

# Restart database
docker-compose start db
```

---

## 📈 Phase 9: Logging & Monitoring

### 9.1 View Application Logs
```bash
# Real-time logs
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api

# Filter by level
docker-compose logs api | grep ERROR
docker-compose logs api | grep WARNING
```

### 9.2 Check Resource Usage
```bash
# CPU, Memory, Network
docker stats

# Specific service
docker stats rie_api
```

---

## ✅ Test Checklist

- [ ] All services running (docker-compose ps)
- [ ] API health checks passing (/health, /ready)
- [ ] Database connectivity verified
- [ ] Classification working (confidence > 0)
- [ ] Rule extraction producing valid output
- [ ] Suggestion CRUD operations working
- [ ] Clarification workflow functional
- [ ] Review workflow complete
- [ ] Database persistence verified
- [ ] Dashboard loads and is interactive
- [ ] End-to-end pipeline successful
- [ ] Response times acceptable (< 500ms)
- [ ] Error handling working
- [ ] Logging operational
- [ ] All 15+ endpoints tested

---

## 🎯 Success Criteria

✅ **Phase 1 (System Health)**: All services healthy and connected  
✅ **Phase 2 (ML Pipeline)**: Classification accuracy ≥ 75%, extraction working  
✅ **Phase 3 (Services)**: All CRUD operations functional  
✅ **Phase 4 (Database)**: Data persists, relationships maintained  
✅ **Phase 5 (UI)**: Dashboard loads, interactive, responsive  
✅ **Phase 6 (E2E)**: Complete workflow from feedback to review  
✅ **Phase 7 (Performance)**: Response times < 500ms, handles 100+ concurrent  
✅ **Phase 8 (Error Handling)**: Graceful error messages  
✅ **Phase 9 (Monitoring)**: Logs available, metrics tracked  

---

## 🚀 Next Steps After Testing

1. **Document Results** - Record test outcomes
2. **Fix Issues** - Address any failures
3. **Performance Optimization** - Tune slow components
4. **Security Audit** - Review auth and data handling
5. **Prepare for Week 4** - Background jobs and versioning

---

**Last Updated**: August 24, 2026  
**Status**: Week 3 Complete ✅  
**Ready for Week 4**: Yes 🚀
