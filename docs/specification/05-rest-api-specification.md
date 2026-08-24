# Section 5: REST API Specification

The Rule Intelligence Engine exposes RESTful APIs through the FastAPI application to support feedback analysis, rule comparison, review management, taxonomy retrieval, and health monitoring. All APIs communicate using JSON and return standardized HTTP status codes along with structured response payloads.

Each request is associated with an authenticated user. Workspace access is determined by validating the authenticated user's workspace membership before request processing, ensuring complete tenant isolation, authorization, and auditability.

## 5.1 Authentication

All protected endpoints require authentication before processing requests.

Each request includes:
```
Authorization: Bearer <JWT Token>
Content-Type: application/json
```

Authentication is validated before any business processing begins. Unauthorized requests return an HTTP 401 Unauthorized response.

## 5.2 POST /v1/feedback/analyze

This endpoint accepts a single business feedback request and initiates the automated analysis workflow.

**Request:**
```json
{
  "workspace_id": "WS001",
  "feedback_text": "Revenue should exclude cancelled orders and test transactions.",
  "context": {
    "available_tables": ["orders", "payments"],
    "available_columns": ["orders.status", "orders.is_test", "payments.amount"]
  }
}
```

**Response:**
```json
{
  "suggestion_id": "SG1001",
  "status": "PENDING_REVIEW",
  "classification_result": "RULE_CHANGE",
  "extraction_result": "COMPLETED",
  "schema_validation": "PASS",
  "duplicate_status": "NONE",
  "conflict_status": "NONE",
  "clarification_required": false
}
```

## 5.3 POST /v1/feedback/batch-analyze

Processes multiple feedback requests asynchronously within a single API call.

The endpoint immediately returns HTTP 202 Accepted together with a Job ID. Batch analysis is executed asynchronously by Celery workers.

**Request:**
```json
{
  "workspace_id": "WS001",
  "feedback": [
    {"feedback_text": "Revenue should exclude cancelled orders."},
    {"feedback_text": "Managers should only access their assigned region."}
  ]
}
```

**Response:**
```json
{
  "job_id": "JOB1021",
  "status": "QUEUED"
}
```

## 5.4 POST /v1/rules/check-duplicate

Compares a proposed business rule with existing suggestions and active business rules to determine duplicate relationships.

**Response includes:**
- Duplicate Status
- Relationship Type
- Similar Rule IDs
- Similarity Candidates

## 5.5 POST /v1/rules/check-conflict

Determines whether a proposed business rule conflicts with existing active business rules.

**Response includes:**
- Conflict Status
- Conflict Type
- Conflicting Rule IDs
- Recommended Review Action

## 5.6 GET /v1/suggestions/{suggestion_id}

Returns the latest processing status of a previously generated suggestion.

## 5.7 POST /v1/reviews

Allows authorized reviewers to submit review decisions.

**Request:**
```json
{
  "suggestion_id": "SG1001",
  "decision": "APPROVE",
  "comments": "Business rule is valid."
}
```

## 5.8 POST /v1/rules

Creates a draft business rule from an approved suggestion.

## 5.9 POST /v1/rules/{rule_id}/activate

Activates an existing draft business rule. Only users with administrator permissions may invoke this endpoint.

## 5.10 Background Job Processing

Certain operations execute asynchronously through Celery workers using Redis as the message broker:
- Batch Feedback Processing
- Dataset Generation
- Model Training
- Evaluation Runs
- Pgvector index management Updates
- Bulk Rule Re-indexing

## 5.11-5.15 Background Job APIs
- POST /v1/jobs/train-model
- POST /v1/jobs/generate-dataset
- POST /v1/jobs/run-evaluation
- POST /v1/jobs/update-embedding-index
- GET /v1/jobs/{job_id}

## 5.16 POST /v1/clarifications/{suggestion_id}

Submits additional information requested during clarification.

## 5.17 GET /v1/taxonomy

Returns supported feedback categories, rule categories, duplicate relationships, conflict relationships, and review-routing options.

## 5.18 GET /health

Returns operational status.

## 5.19 Standard HTTP Response Codes

| Status | Description |
|--------|-------------|
| 200 OK | Request processed successfully |
| 201 Created | Resource created successfully |
| 400 Bad Request | Invalid request payload |
| 401 Unauthorized | Authentication failed |
| 403 Forbidden | User lacks required permissions |
| 404 Not Found | Requested resource does not exist |
| 409 Conflict | Duplicate request or conflicting resource |
| 422 Unprocessable Entity | Request validation failed |
| 429 Too Many Requests | Rate limit exceeded |
| 500 Internal Server Error | Unexpected server error |

## 5.20 API Design Principles

- All APIs are stateless and communicate using JSON
- Workspace access is validated using authenticated user's workspace membership
- Automated analysis returns immediately after storing suggestions or registering async jobs
- Suggestion approval, draft rule creation, and rule activation are separate APIs
- Every API request and background job is logged for auditing and traceability
