# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Rule Intelligence Engine (RIE)** — a FastAPI service that ingests business feedback text and runs an 8-step pipeline to turn it into validated, de-duplicated, conflict-checked *rule suggestions* for human review. A separate `rie_ml` Python package handles ML model training, evaluation, and domain-specific data.

Things that define this codebase (learned the hard way, see git history):

- **No pytest test suite.** The "tests" live in `tests/` as smoke scripts (`smoke_test_45v2.py`) that POST feedback to a **running API** on `localhost:8000` and write JSON/HTML results. They are not runnable via pytest against a test DB.
- **Dual-model architecture everywhere.** Every ML-dependent step (classification, extraction, duplicate, conflict) has a `Baseline*` service (deterministic: TF-IDF/regex/JSON) and a "Real" semantic service (DistilBERT / pgvector) — plus `RealClassifier`/`RealDuplicateDetectionService` etc. façade classes. Unless you're specifically working on baselines, you almost always want the `*Service`/`Real*` façade, not the `Baseline*`.
- **Spec docs drive the code.** Comments reference a formal spec by § number (`§8.4`, `§8.9`, `§8.11`). The canonical docs live in `docs/specification/`. When a task references a §, read the corresponding doc there first — it defines the expected output shapes and lifecycle rules.

## Running the App

Local development uses Docker for infra (Postgres+pgvector, Redis) and runs the API from the repo root with the `.venv`:

```bash
docker compose up -d db redis        # Postgres (pgvector) on :5432, Redis on :6379
alembic upgrade head                 # run migrations against the local DB
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`app/worker.py` sets up **Celery** (broker/backend = Redis, task module `app.tasks`). Start the worker with `celery -A app.tasks worker --loglevel=info`. Full stack (API + worker + db + redis + pgAdmin on :5050) via `docker compose up --build`.

DB details (`docker-compose.yml`): user `rie_user`, password `rie_password`, db `rule_intelligence_engine`. `db_shell.sh` opens a psql shell into the running `rie_postgres` container; `restart_api.sh` kills and restarts uvicorn.

> ⚠️ **Path portability:** `restart_api.sh` and `tests/smoke_test_45v2.py` hardcode the original developer's Linux home dir (`/home/spxlpt133/Desktop/Rule-intelligence-Engine`) and Linux paths. On this Windows machine (`C:\Users\pallav\...`), these scripts need their output paths/mkdirs fixed before use. The smoke test also uses `.venv/bin/python` style CLIs.

## The 8-Step Analysis Pipeline

`POST /v1/feedback/analyze` (`app/main.py`, `analyze_feedback`) is the core endpoint. It builds a `FeedbackAnalysisResponse` by running, in order:

1. **Preprocessing** — `app/services/feedback_preprocessor.py` (domain-aware normalization)
2. **Classification** — `MLModelService.classify()` (DistilBERT if ACTIVE in registry → TF-IDF baseline fallback)
3. **Rule Extraction** — `MLModelService.extract()` (DistilBERT token classifier → `EnhancedRuleExtractor` regex fallback). Schema is loaded into `full_schema_context["domain_pack_schema"]` **before** extraction so the extractor resolves table/columns against real entities.
4. **Schema Validation** — `SchemaValidationService` against the domain pack's `schema/schema.json` (deterministic). Gated on `is_actionable` — non-actionable feedback gets status `"N/A"`, not `"FAIL"`.
5. **Duplicate Detection** — `RealDuplicateDetectionService` (pgvector semantic) or `BaselineDuplicateDetectionService` (domain-pack JSON)
6. **Conflict Detection** — same baseline/real split
7. **Clarification Generation** — `CompletenessChecker` + `AmbiguityDetector` (deterministic)
8. **Review Routing** — `RealReviewRoutingService` policy engine

`model` query param: `active` (default, uses registry) vs `baseline` (forces old methods). There's also an **orchestrator** at `app/services/analysis_orchestrator.py` — a newer, cleaner implementation of the same pipeline used by background jobs and re-analysis. Prefer it when adding behavior that shouldn't live in `main.py`.

A critical detail: `main.py` applies `_post_extraction_cross_validate()` after extraction — it **prunes hallucinated** tables/columns against the real schema, infers conditions from feedback text, and flags unresolvable fields with `needs_clarification`. Recent regression work (see `issues.md` and git log) heavily depends on this step; don't remove it or reorder extraction before schema loading.

## Architecture Overview

```
app/
  main.py              # ALL routes + the analyze/re-analyze flow (2784 lines)
  worker.py            # Celery app
  tasks.py             # Celery tasks: process_background_job, run_evaluation_task
  routes/init_routes.py# admin seeding endpoints (conflicting rules)
  services/            # ~33 services — the business logic layer
  db/                  # SQLAlchemy models, database.py, alembic migrations
  schemas/             # Pydantic request/response models (mirror spec output shapes)
  static/              # Custom HTML test dashboards (dashboard.html, phase2/3-test.html)
rie_ml/                # ML training/eval/data (pip-installable package, `rie-ml`)
  src/baseline/        # deterministic baseline classifier/extractor/validator
  src/ml_models/       # DistilBERT classifier + token extractor + model loader
  src/model_registry/  # on-disk model registry (lifecycle EXPERIMENTAL→PRODUCTION)
  src/evaluation/      # metrics storage (JSON on disk + DB), used by evaluation APIs
  domain-packs/        # per-domain: schema/, taxonomy/, rules/, documentation/, feedback/
  dataset_generation/  # synthetic dataset generator from seed + domain pack
  scripts/             # training/, evaluation/, registration/, datasets/, utils/
  models/              # trained artifacts + registry/index.json (checkpoints gitignored)
docs/specification/    # the formal spec (01–11) referenced by § comments throughout code
issues.md              # living regression/issue tracker tied to spec sections
```

### Domain Packs

`rie_ml/domain-packs/<domain>/` is the source of truth for a business domain (`ecommerce`, `saas_subscription`, `customer_support`). Each contains `domain_config.json` plus:
- `schema/schema.json` — tables/columns with `synonyms`, `description`, `business_meaning` (the glossary is derived from these fields)
- `taxonomy/labels.json` — valid business terms/operations
- `rules/active_rules.json` + `conflicting_rules.json` — used by baseline duplicate/conflict detection and seeded into Postgres
- `documentation/business_glossary.md`, `annotation_guide.md`

`DomainPackLoader` (`app/services/domain_pack_loader.py`) is the typed loader. Detection of which domain feedback belongs to: `domain_pack_detector.py`.

### ML Model Flow & Registry

Two registries coexist:
- **On-disk** (`rie_ml/src/model_registry/`, statuses EXPERIMENTAL→STAGING→PRODUCTION) — managed via `rie_ml/scripts/registration/` + `promote_model.py`. Documented in `rie_ml/MODEL_REGISTRY_GUIDE.md`.
- **DB-backed** (`app/db/models/model_version.py`, statuses CANDIDATE→APPROVED→ACTIVE per §8.11) — managed by `ModelVersionService` via `/v1/model-versions` endpoints. `MLModelService` queries this for the ACTIVE per-type model and falls back to baselines. **Only one model per type may be ACTIVE** — promoting a new ACTIVE archives the prior one.

Training scripts (in `rie_ml/scripts/training/`): `train_distilbert_classifier.py`, `train_distilbert_token_classifier.py`, `train_baseline_unified.py`, plus BERT/RoBERTa variants. Evaluation scripts (`rie_ml/scripts/evaluation/`) compare baseline vs candidate, persist metrics, and rank/promote. Datasets are generated from seed feedback via `rie_ml/dataset_generation/` (rule-family-aware splitting prevents data leakage).

## Common Workflows

- **Train/evaluate a model** — run a script from `rie_ml/scripts/training/` or `rie_ml/scripts/evaluation/`, then register/promote via the API or `rie_ml/scripts/registration/`.
- **Generate synthetic datasets** — `rie_ml/dataset_generation/run_pipeline.py` (README in that dir).
- **Admin/seeding** — `POST /v1/admin/init/seed-conflicting-rules` seeds `conflicting_rules.json` into the DB (also `app/db/migrations/seed_conflicting_rules.py`).
- **Run migrations** — `alembic revision --autogenerate -m "..."` then `alembic upgrade head`. Migrations live in `app/db/migrations/versions/`.

## Gotchas

- DB bootstrap SQL lives in `database/init.sql` (mounted only on first container start — changes require `docker compose down -v` to re-run).
- pgvector semantic retrieval (`pgvector_service.py`) assumes the `pgvector` extension is enabled; embeddings are generated by `embedding_service.py` (Sentence-BERT `all-MiniLM-L6-v2`).
- `main.py` is large and accreted — new pipeline logic generally belongs in `analysis_orchestrator.py` or a service, not new inline code in `main.py`.
- Models/checkpoints (`*.pt`) and generated datasets are gitignored; `rie_ml/models/registry/index.json` and model metadata are committed.