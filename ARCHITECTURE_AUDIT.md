# Complete Codebase Audit & Cleanup Plan

## 📊 File Count Summary
- **app/services/** - 21 files (TOO MANY)
- **app/db/** - 37 files (ORGANIZED BUT COMPLEX)
- **app/schemas/** - 9 files (NECESSARY)
- **tests/** - 17 files (UNCLEAR PURPOSE)

---

## 1️⃣ app/schemas/ - KEEP ALL (NECESSARY)

### What it does:
Pydantic models that define API request/response formats. These are **REQUIRED** for FastAPI.

```
schemas/
├── feedback.py          ← FeedbackAnalysisRequest, FeedbackAnalysisResponse
├── suggestion.py        ← SuggestionCreateRequest, SuggestionResponse
├── clarification.py     ← ClarificationCreateRequest, ClarificationResponse
├── review.py            ← ReviewCreateRequest, ReviewResponse
├── rule.py              ← RuleCreateRequest, RuleResponse
├── evaluation.py        ← EvaluationCreateRequest, EvaluationResponse
├── dataset.py           ← DatasetVersionCreateRequest, DatasetVersionResponse
├── model_version.py     ← ModelVersionCreateRequest, ModelVersionResponse
├── jobs.py              ← JobCreateRequest, JobResponse
└── __init__.py
```

**Status:** ✅ KEEP ALL - These define the API contract

---

## 2️⃣ app/db/ - ORGANIZED, UNDERSTAND IT

### Structure:
```
db/
├── database.py                  ← SQLAlchemy engine + session setup
├── migrations/                  ← Alembic migrations (versioned DB schema)
│   ├── env.py
│   ├── versions/
│   └── ...
└── models/                      ← SQLAlchemy ORM models
    ├── feedback.py              ← Feedback table
    ├── analysis_run.py          ← AnalysisRun table
    ├── rule_suggestion.py       ← RuleSuggestion table
    ├── clarification.py         ← Clarification table
    ├── review.py                ← Review table
    ├── rule.py                  ← Rule table
    ├── rule_comparison.py       ← RuleComparison table
    ├── extracted_rule.py        ← ExtractedRule table
    ├── background_job.py        ← BackgroundJob table
    ├── workspace.py             ← Workspace table
    ├── domain_pack.py           ← DomainPack table
    ├── model_version.py         ← ModelVersion table
    ├── dataset_version.py       ← DatasetVersion table
    ├── evaluation_run.py        ← EvaluationRun table
    ├── evaluation_metric.py     ← EvaluationMetric table
    ├── audit_history.py         ← AuditHistory table
    └── __init__.py
```

**Status:** ✅ KEEP ALL - These are the database schema

**Why so many tables?** 
- `feedback` - stores user feedback
- `analysis_run` - tracks each analysis execution
- `rule_suggestion` - extracted rules awaiting review
- `clarification` - clarification questions for ambiguous feedback
- `review` - human review tracking
- `rule` - approved business rules
- `rule_comparison` - conflict/duplicate detection results
- `extracted_rule` - intermediate extraction results
- `background_job` - async task tracking
- `workspace` - multi-tenant isolation
- `domain_pack` - domain versioning
- `model_version` - ML model versioning
- `dataset_version` - dataset versioning
- `evaluation_run` - model evaluation tracking
- `evaluation_metric` - evaluation metrics
- `audit_history` - compliance audit log

---

## 3️⃣ app/services/ - TOO MANY, NEEDS CLEANUP

### Current 21 files:

| File | Purpose | Status |
|------|---------|--------|
| `classifier.py` | Wraps ML classifier | ✅ KEEP |
| `rule_extractor.py` | Wraps ML extractor | ✅ KEEP |
| `domain_pack_loader.py` | Loads domain pack schema | ✅ KEEP |
| `entity_extractor.py` | NER using domain schema | ✅ KEEP |
| `feedback_preprocessor.py` | Normalize feedback | ✅ KEEP |
| `schema_validator.py` | Validate against schema | ✅ KEEP |
| `conflict_detection_service.py` | Conflict detection | ✅ KEEP |
| `duplicate_detection_service.py` | Duplicate detection | ✅ KEEP |
| `clarification_service.py` | Clarification lifecycle | ✅ KEEP |
| `review_routing_service.py` | Review routing logic | ✅ KEEP |
| `suggestion_service.py` | Pipeline orchestration | ✅ KEEP |
| `feedback_service.py` | DB operations | ✅ KEEP |
| `background_job_service.py` | Async task management | ⚠️ CHECK IF USED |
| `metrics_service.py` | Metrics tracking | ⚠️ CHECK IF USED |
| `evaluation_service.py` | Model evaluation | ⚠️ CHECK IF USED |
| `dataset_version_service.py` | Dataset versioning | ⚠️ CHECK IF USED |
| `model_version_service.py` | Model versioning | ⚠️ CHECK IF USED |
| `canonical_rule_service.py` | Canonical rules | ❌ DELETE - empty stub |
| `real_classifier_service.py` | DUPLICATE of classifier.py | ❌ DELETE |
| `rule_comparison_service.py` | DUPLICATE/WRAPPER | ⚠️ CHECK PURPOSE |

### Cleanup Plan:

#### DEFINITELY DELETE:
- `canonical_rule_service.py` - Empty, no purpose
- `real_classifier_service.py` - Duplicate of `classifier.py`

#### INVESTIGATE:
- `background_job_service.py` - Is it used?
- `metrics_service.py` - Is it used?
- `evaluation_service.py` - Is it used?
- `dataset_version_service.py` - Is it used?
- `model_version_service.py` - Is it used?
- `rule_comparison_service.py` - Is it still needed after fixing?

---

## 4️⃣ tests/ - UNCLEAR PURPOSE

### Current structure:
```
tests/
└── [17 files - purpose unclear]
```

**Questions:**
- Are these unit tests? Integration tests? End-to-end tests?
- Do they actually run?
- Are they used for CI/CD?
- Should they be kept or deleted?

---

## RECOMMENDATION: WEEK 1/2 FOCUS

For Week 1 & 2, **you should NOT need to understand**:
- Full evaluation pipeline
- Model versioning system
- Dataset versioning system
- Background job system
- Audit history system

**You ONLY need:**
1. ✅ Feedback classification
2. ✅ Rule extraction
3. ✅ Entity extraction
4. ✅ Schema validation
5. ✅ Conflict detection
6. ✅ Duplicate detection
7. ✅ Clarification routing
8. ✅ Review routing
9. ✅ Database persistence

---

## CLEANUP EXECUTION

### Phase 1: Immediate Deletions
```bash
# DELETE these files (empty/duplicate)
rm app/services/canonical_rule_service.py
rm app/services/real_classifier_service.py
```

### Phase 2: Investigate Usage
Check if these are actually used:
```bash
grep -r "background_job_service\|BackgroundJobService" app/main.py
grep -r "metrics_service\|MetricsService" app/main.py
grep -r "evaluation_service\|EvaluationService" app/main.py
grep -r "dataset_version_service\|DatasetVersionService" app/main.py
grep -r "model_version_service\|ModelVersionService" app/main.py
```

### Phase 3: Document Services
Create a simple README showing what each remaining service does and its dependencies.

### Phase 4: Tests
Determine if tests should be:
- ✅ KEPT and fixed
- ❌ DELETED (if they're obsolete/broken)
- 🔄 REWRITTEN (for Week 1/2 scope)

---

## WHAT MATTERS FOR WEEK 1/2

**IGNORE for now:**
- Evaluation metrics
- Model versioning
- Dataset versioning  
- Background jobs
- Audit history
- Tests folder

**FOCUS on:**
- Core feedback processing
- Database persistence
- API endpoints
- Domain pack integration

---

## FINAL RECOMMENDATION

**Do this in order:**

1. ✅ Delete `canonical_rule_service.py` (empty)
2. ✅ Delete `real_classifier_service.py` (duplicate)
3. ⏳ Check usage of 5 uncertain services
4. ⏳ Delete tests/ (unclear purpose for Week 1/2)
5. ⏳ Create services README
6. ⏳ Then focus on Week 1/2 implementation

Should I proceed?
