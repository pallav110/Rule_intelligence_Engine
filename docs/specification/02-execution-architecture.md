# Section 2: Execution-Level System Architecture

## Modular Monolith Architecture
The Rule Intelligence Engine (RIE) is implemented as a modular monolith using a single FastAPI application that contains multiple independent internal modules responsible for processing unstructured business feedback into structured business rule suggestions. Each module has a well-defined responsibility and communicates through internal service interfaces rather than separate network calls. This architecture simplifies development, deployment, testing, and maintenance while allowing individual modules to evolve independently within a single deployable application.

## Processing Pipeline
The system processes business feedback through a structured pipeline consisting of:
1. Feedback classification
2. Rule extraction
3. Schema validation
4. Duplicate detection
5. Conflict detection
6. Clarification handling
7. Review routing
8. Persistence

Long-running operations such as batch feedback analysis, model training, evaluation, and pgvector index management updates are executed asynchronously using Celery workers with Redis as the message broker, ensuring that API requests remain responsive while background tasks are processed reliably.

## Storage Layer
The system uses PostgreSQL as the primary transactional database, with pgvector for persistent vector storage and workspace-scoped semantic similarity search. Structured business rules are stored in normalized form and are compared using deterministic rule comparison after semantic candidate retrieval.

## Human Review Isolation
Human reviewers approve or reject AI-generated suggestions, while business rule creation and rule activation remain separate administrative workflows to prevent unintended modification of production business rules.

## Six Logical Layers
Each layer has clearly defined responsibilities to ensure separation of concerns, maintainability, security, traceability, and consistent enforcement of the business rule lifecycle:

1. **Client Layer** – browsers/dashboards, external systems
2. **API Layer** – FastAPI entry point
3. **Rule Intelligence Engine (RIE)** – core business logic modules
4. **Knowledge Sources** – glossary, schema, rule repository, domain packs, pgvector index
5. **Persistence Layer** – PostgreSQL + pgvector
6. **Human Review System** – reviewer interface and decision recording