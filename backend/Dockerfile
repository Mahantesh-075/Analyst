FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies (curl for healthcheck, libmagic, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libmagic1 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installs
COPY --from=ghcr.io/astral-sh/uv:0.5.1 /uv /bin/uv

# Install dependencies first for caching
COPY pyproject.toml README.md /app/
RUN uv pip install --system -e ".[dev]"

# Copy source code
COPY . /app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
