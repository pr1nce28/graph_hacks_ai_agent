FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for sentence-transformers and healthcheck tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install \
        "falkordb>=1.0" \
        "anthropic>=0.40" \
        "fastapi>=0.110" \
        "uvicorn[standard]>=0.30" \
        "pydantic>=2.7" \
        "sentence-transformers>=3.0" \
        "pyyaml>=6.0" \
        "httpx>=0.27" \
        "ruff>=0.5" \
        "pytest>=8.0" \
        "mcp>=0.5"

# App code
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]