# Section6: Database Design

## Overview
The Rule Intelligence Engine(RIE) uses PostgreSQL as primary persistence layer, with pgvector for vector embeddings storage. Schema is designed for separation of feedback, suggestions, extracted rules, draft rules, active rules, with audit history and evaluation data tracked separately.

## 6.1 Database Overview

| Entity | Purpose |
|--------|---------|
| Feedback | Stores original feedback |
| Suggestion | Stores generated suggestions |
| Analysis Run | Records metadata for each execution |
| Extracted Rule | Stores structured rules extracted from suggestions |
| Business Rule | Stores approved business rules |
| Review | Stores review decisions |
| Rule Comparison | Stores duplicate and conflict analysis |
| Clarification Response | Stores clarification requests/responses |
| Background Job | Tracks asynchronous operations |
| Dataset Version | Tracks training and evaluation datasets |
| Model Version | Tracks trained ML models |
| Evaluation Run | Stores model evaluation results |
| Audit History | Stores audit logs |
| Workspace | Maintains tenant isolation |
| Domain Pack | Stores domain metadata |

## 6.2 Feedback Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| feedback_id | UUID | Unique identifier |
| workspace_id | UUID | Workspace reference |
| feedback_text | TEXT | Original feedback |
| submitted_by | UUID | User ID |
| created_at | TIMESTAMPTZ | Submission timestamp |
| processing_status | ENUM | RECEIVED, VALIDATED, PROCESSING, PROCESSED, ARCHIVED |

## 6.3 Suggestion Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| suggestion_id | UUID | Unique identifier |
| feedback_id | UUID | Reference to feedback |
| analysis_run_id | UUID | Reference to Analysis Run |
| feedback_type | VARCHAR | Predicted type |
| rule_category | VARCHAR | Predicted category |
| classification_result | JSONB | Classification output |
| extraction_result | VARCHAR | Completed, Partial, Failed |
| schema_validation_status | VARCHAR | PASS, PARTIAL, FAIL |
| duplicate_status | VARCHAR | Duplicate relation |
| conflict_status | VARCHAR | Conflict result |
| clarification_required | BOOLEAN | Clarification needed |
| review_status | VARCHAR | Current review status |
| created_at | TIMESTAMPTZ | Creation timestamp |

## 6.4 Business Rule Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| rule_id | UUID | Unique identifier |
| suggestion_id | UUID | Source suggestion |
| rule_name | VARCHAR | Human-readable name |
| rule_definition | JSONB | Structured rule logic |
| rule_status | VARCHAR | DRAFT, ACTIVE, DISABLED, ARCHIVED |
| activated_by | UUID | Administrator who activated |
| activated_at | TIMESTAMPTZ | Activation timestamp |

## 6.5 Review Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| review_id | UUID | Unique identifier |
| suggestion_id | UUID | Reviewed suggestion |
| reviewer_id | UUID | Reviewer |
| decision | VARCHAR | APPROVE, REJECT, CLARIFICATION, ARCHIVE |
| comments | TEXT | Optional remarks |
| reviewed_at | TIMESTAMPTZ | Review timestamp |

## 6.6 Audit History Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| audit_id | UUID | Unique record |
| entity_type | VARCHAR | Entity type |
| entity_id | UUID | Entity identifier |
| action | VARCHAR | Action performed |
| performed_by | VARCHAR | User or system |
| timestamp | TIMESTAMPTZ | Event timestamp |

## 6.7 Workspace Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| workspace_id | UUID | Unique ID |
| name | VARCHAR | Workspace name |
| description | TEXT | Description |
| created_at | TIMESTAMPTZ | Creation timestamp |
| status | VARCHAR | Status |

## 6.8 Domain Pack Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| domain_pack_id | UUID | Unique ID |
| workspace_id | UUID | Workspace reference |
| name | VARCHAR | Pack name |
| version | VARCHAR | Pack version |
| schema_metadata | JSONB | Schema info |
| business_glossary | JSONB | Glossary |
| configuration | JSONB | Configuration |

## 6.9 Extracted Rule Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| extracted_rule_id | UUID | Unique identifier |
| suggestion_id | UUID | Parent suggestion |
| rule_family_id | VARCHAR | Rule family |
| business_term | VARCHAR | Business concept |
| operation | VARCHAR | Rule operation |
| conditions | JSONB | Normalized conditions |
| scope | VARCHAR | Business scope |
| time_window | VARCHAR | Time period |
| affected_tables_columns | JSONB | Affected schema |
| extraction_confidence | DECIMAL | Confidence score |
| schema_validation_status | VARCHAR | Validation result |

## 6.10 Analysis Run Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| analysis_run_id | UUID | Unique ID |
| feedback_id | UUID | Feedback reference |
| model_version_id | UUID | Model used |
| dataset_version_id | UUID | Dataset version |
| started_at | TIMESTAMPTZ | Start time |
| completed_at | TIMESTAMPTZ | Completion time |
| status | VARCHAR | RUNNING, COMPLETED, FAILED |

## 6.11 Rule Comparison Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| comparison_id | UUID | Unique ID |
| extracted_rule_id | UUID | Rule being compared |
| compared_rule_id | UUID | Existing rule |
| relationship_type | VARCHAR | Relationship type |
| similarity_score | DECIMAL | Similarity score |
| comparison_summary | JSONB | Comparison result |

## 6.12 Clarification Response Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| clarification_id | UUID | Unique ID |
| suggestion_id | UUID | Associated suggestion |
| clarification_question | TEXT | Question |
| clarification_response | TEXT | Response |
| responded_by | UUID | User |
| responded_at | TIMESTAMPTZ | Timestamp |
| processing_status | VARCHAR | Status |

## 6.13 Background Job Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| job_id | UUID | Unique ID |
| job_type | VARCHAR | Operation type |
| status | VARCHAR | QUEUED, RUNNING, COMPLETED |
| progress | INTEGER | Completion % |
| created_at | TIMESTAMPTZ | Creation time |
| completed_at | TIMESTAMPTZ | Completion time |

## 6.14 Dataset Version Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| dataset_version_id | UUID | Version ID |
| version_name | VARCHAR | Name |
| version | VARCHAR | Version number |
| description | TEXT | Description |
| num_samples | INTEGER | Sample count |
| domain_pack_id | UUID | Domain pack |
| annotation_version | VARCHAR | Annotation version |
| created_at | TIMESTAMPTZ | Creation timestamp |

## 6.15 Model Version Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| model_version_id | UUID | ID |
| model_name | VARCHAR | Name |
| version | VARCHAR | Version |
| description | TEXT | Description |
| model_path | VARCHAR | Storage path |
| dataset_version_id | UUID | Training dataset |
| status | VARCHAR | CANDIDATE, APPROVED, ACTIVE |
| created_at | TIMESTAMPTZ | Timestamp |
| metrics | JSONB | Evaluation metrics |

## 6.16 Evaluation Run Entity

| Attribute | Type | Description |
|-----------|------|-------------|
| evaluation_run_id | UUID | Run ID |
| model_version_id | UUID | Model evaluated |
| dataset_version_id | UUID | Evaluation dataset |
| classification_accuracy | DECIMAL | Accuracy |
| classification_f1 | JSONB | Per-class F1 |
| complete_rule_accuracy | DECIMAL | Rule accuracy |
| duplicate_f1 | DECIMAL | Duplicate F1 |
| conflict_f1 | DECIMAL | Conflict F1 |
| calibration_error | DECIMAL | Calibration error |
| created_at | TIMESTAMPTZ | Timestamp |

## 6.17 Design Considerations
- Separation of feedback, suggestions, extracted rules, draft rules, active rules
- Every analysis recorded as Analysis Run
- Review decisions never directly create or activate production business rules
- Workspace membership validation enforces tenant isolation
- Audit history records every significant system and administrative event
- pgvector used for persistent semantic candidate retrieval
- Schema supports future extension without major structural changes
