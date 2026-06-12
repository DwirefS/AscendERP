# ANTS - AI-Agent Native Tactical System
# Multi-stage Docker build (core dependencies only; cloud/ML extras are not installed)

# Stage 1: Build stage
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata and source (required to build the wheel)
COPY pyproject.toml README.md ./
COPY src/ src/
COPY ants_platform/ ants_platform/
COPY services/ services/
COPY ants_mcp/ ants_mcp/
COPY data/ data/

# Build wheels for the project and its core dependencies
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels .

# Stage 2: Runtime stage
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ants && useradd -r -g ants ants

# Install application + dependencies from prebuilt wheels
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

# Copy application code (ants_mcp and data are not part of the wheel;
# src/services/ants_platform are copied too so PYTHONPATH=/app resolves them directly)
COPY src/ /app/src/
COPY services/ /app/services/
COPY ants_platform/ /app/ants_platform/
COPY ants_mcp/ /app/ants_mcp/
COPY data/ /app/data/

# Set ownership
RUN chown -R ants:ants /app

USER ants

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Labels
LABEL org.opencontainers.image.title="ANTS" \
      org.opencontainers.image.description="AI-Agent Native Tactical System" \
      org.opencontainers.image.version="1.0.0"
