# ANTS - AI-Agent Native Tactical System
# Multi-stage Docker build

# Stage 1: Build stage
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --wheel-dir /wheels -e .

# Stage 2: Runtime stage
FROM python:3.11-slim as runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r ants && useradd -r -g ants ants

# Copy wheels from builder
COPY --from=builder /wheels /wheels

# Install application
RUN pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Copy application code
COPY src/ /app/src/
COPY services/ /app/services/
COPY platform/ /app/platform/
COPY mcp/ /app/mcp/

# Set ownership
RUN chown -R ants:ants /app

USER ants

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "-m", "uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Labels
LABEL org.opencontainers.image.title="ANTS" \
      org.opencontainers.image.description="AI-Agent Native Tactical System" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.vendor="Your Organization"
