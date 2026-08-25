FROM python:3.11-slim

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_HOME=/app
ENV DATABASE_URL=postgresql://rie_user:rie_password@db:5432/rule_intelligence_engine

WORKDIR ${APP_HOME}

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install rie_ml package in development mode
COPY rie_ml/ ./rie_ml/
RUN pip install --no-cache-dir -e ./rie_ml/

# Copy application code
COPY app/ ./app/

# Create necessary directories
RUN mkdir -p ./rie_ml/models ./logs

# Train models on startup (if not already trained)
RUN python -c "from pathlib import Path; Path('./rie_ml/models/baseline_classifier.pkl').exists() or print('Models will be trained on first run')" 2>/dev/null || true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "python -c 'from app.db.database import engine; from app.db.models import Base; Base.metadata.create_all(bind=engine)' && uvicorn app.main:app --host 0.0.0.0 --port 8000"]