# 🧠 Rule Intelligence Engine (RIE)

> Turn raw business feedback into **validated, de-duplicated, conflict-checked rule suggestions** — ready for human review, not guesswork.

RIE is a FastAPI service that runs a deterministic **8-step analysis pipeline** over business feedback text and produces *rule suggestions* that a human reviewer can act on with confidence. It ships with three pre-trained transformer classifiers (DistilBERT, BERT, RoBERTa) and three domain packs.

---

## ✨ What it does

Feed it a line of feedback and it will:

1. **Preprocess** — domain-aware normalization of the raw text
2. **Classify** — feedback type & rule category (DistilBERT / BERT / RoBERTa, TF-IDF fallback)
3. **Extract** — pull candidate rules & field values from text (token extractor + regex)
4. **Validate against schema** — check every table/column against the real domain schema
5. **De-duplicate** — find semantically similar existing rules (pgvector)
6. **Detect conflicts** — flag rules that contradict existing ones
7. **Clarify** — surface what's ambiguous or incomplete
8. **Route to review** — policy-driven routing for human review

Result: a structured analysis with the pieces a reviewer needs to approve, edit, or reject — fast.

---

## 🏗️ Architecture

```
  Feedback ──▶ Preprocess ──▶ Classify ──▶ Extract
                                            │
                                  Schema Validation ◀── domain pack schema
                                            │
                              Duplicate Detection (pgvector / baseline)
                                            │
                              Conflict Detection (semantic / baseline)
                                            │
                       Clarification Generation (completeness + ambiguity)
                                            │
                              Review Routing (policy engine)
                                            ▼
                              Rule Suggestion for human review
```

**Dual-model architecture everywhere:** every ML-dependent step has a deterministic `Baseline*` service (TF-IDF / regex / JSON) *and* a semantic `Real*` service (DistilBERT / pgvector). When no model is ACTIVE in the registry, the system degrades gracefully to the baselines.

**Stack:** FastAPI · PostgreSQL + **[pgvector](https://github.com/pgvector/pgvector)** · Redis · Celery · Sentence-BERT embeddings

---

## 📦 Project layout

```
app/                 FastAPI service — routes, services, models, migrations
rie_ml/              pip-installable ML package (`rie-ml`)
 ├─ src/ml_models/   DistilBERT/BERT/RoBERTa classifiers + model loader
 ├─ src/model_registry/  on-disk model lifecycle (EXPERIMENTAL → PRODUCTION)
 ├─ src/evaluation/  metrics storage (JSON on disk + DB)
 ├─ domain-packs/    per-domain schema/, taxonomy/, rules/, docs/, feedback/
 ├─ dataset_generation/  synthetic dataset generator (rule-family-aware split)
 ├─ scripts/         training/, evaluation/, registration/, utils/
 └─ models/          trained checkpoints + registry (checkpoints gitignored)
docs/specification/  the formal spec (§-referenced throughout the code)
```

### Domain packs

Each domain (`ecommerce`, `saas_subscription`, `customer_support`) is self-contained:

- `schema/schema.json` — tables/columns with synonyms + business meaning (drives the glossary)
- `taxonomy/labels.json` — valid business terms & operations
- `rules/active_rules.json` + `conflicting_rules.json` — baseline detection + seeding
- `documentation/` — business glossary + annotation guide

---

## 🚀 Quickstart

```bash
# 1. Start infra (Postgres + pgvector, Redis)
docker compose up -d db redis

# 2. Run migrations against the local DB
alembic upgrade head

# 3. Start the API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 4. (optional) background worker for async jobs
celery -A app.tasks worker --loglevel=info
```

Analyze a feedback string:

```bash
curl -X POST http://localhost:8000/v1/feedback/analyze \
  -H "Content-Type: application/json" \
  -d '{"feedback_text": "Customers get a 10% discount when they sign up for a yearly plan.", "domain": "ecommerce"}'
```

`model` query param: `active` (default, uses the registry) vs `baseline` (forces deterministic methods).

🔗 **Full REST spec:** `docs/specification/05-rest-api-specification.md`

---

## 🤖 ML models

Multi-task text classifiers — four heads on one backbone:

| Head | Type | Classes |
|------|------|---------|
| `feedback_type` | classification | 5 |
| `rule_category` | classification | 7 |
| `is_actionable` | binary | 2 |
| `requires_clarification` | binary | 2 |

Three trained candidates (all CPU-reloadable, metadata-embedded for handoff):

| Model | Checkpoint | Params |
|-------|-----------|--------|
| **DistilBERT** | `distilbert_candidate/checkpoints/best_model.pt` | ~67 M |
| **BERT** | `bert_candidate/checkpoints/best_model.pt` | ~110 M |
| **RoBERTa** | `roberta_candidate/checkpoints/best_model.pt` | ~126 M |

> ⚠️ Checkpoints are **gitignored** — train or download them. See `rie_ml/MODEL_REGISTRY_GUIDE.md`.

**Train** (GPU recommended):

```bash
PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
  rie_ml/scripts/training/train_distilbert_classifier.py   # or bert / roberta
```

**Evaluate, rank & promote:**

```bash
rie_ml/scripts/evaluation/compare_all_candidates.py    # baseline vs candidates
rie_ml/scripts/evaluation/rank_and_promote.py          # promote the best to ACTIVE
```

**Registry lifecycle:** on-disk (`EXPERIMENTAL → STAGING → PRODUCTION`) and DB-backed (`CANDIDATE → APPROVED → ACTIVE`). Only one model per type may be ACTIVE — promoting archives the prior one.

---

## 🔍 The 8 steps, in depth

Read the formal spec docs (code comments reference these by §):

| Step | Service | § |
|------|---------|---|
| Preprocessing | `feedback_preprocessor.py` | §3 |
| Classification | `MLModelService.classify()` | §8 |
| Extraction | `MLModelService.extract()` + `EnhancedRuleExtractor` | §8 |
| Schema validation | `SchemaValidationService` | §8 |
| Duplicate detection | `RealDuplicateDetectionService` (pgvector) | §8 |
| Conflict detection | baseline / semantic | §8 |
| Clarification | `CompletenessChecker` + `AmbiguityDetector` | §7 |
| Review routing | `RealReviewRoutingService` | §7 |

---

## 🧪 Testing

The "tests" are smoke scripts that POST feedback to a **running API** and write JSON/HTML results:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000   # first
.venv/bin/python tests/smoke_test_45v2.py        # then run the smoke test
```

> These are not `pytest` suites — they exercise the live service end-to-end and dump results to `tests/smoke_test_results*.json` + an HTML dashboard.

---

## 🩺 Diagnostics

```bash
./db_shell.sh        # psql shell into the running Postgres container
./restart_api.sh     # kill & restart uvicorn
```

---

## 📚 Further reading

- `docs/specification/` — the formal 11-section spec
- `issues.md` — live regression/issue tracker tied to spec sections
- `rie_ml/MODEL_REGISTRY_GUIDE.md` — model registration & promotion
- `rie_ml/dataset_generation/README.md` — generating synthetic datasets

---

*Built with FastAPI, PyTorch, and pgvector. Dual-path determinism + semantic intelligence.* ✅