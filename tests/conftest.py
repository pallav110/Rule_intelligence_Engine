import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

# Mock the database URL before importing anything else
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.main import app, get_db
from app.db.models.workspace import Base

# Setup in-memory database for testing
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all relational tables required by the models."""
    # Ensure all models are imported so metadata knows about them
    from app.db.models import workspace, suggestion_audit, rule_suggestion, rule_embedding, rule_comparison, rule, review, model_version, feedback, extracted_rule, evaluation_run, evaluation_metric, domain_pack, dataset_version, clarification, background_job, analysis_run, audit_history
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    """Yield a database session and rollback after each test."""
    db_session = TestingSessionLocal()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()

@pytest.fixture
def client(db):
    """Override FastAPI dependency to use test DB session."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
