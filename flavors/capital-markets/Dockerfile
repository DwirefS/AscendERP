################################################################################
# ANTS Capital Markets — Dockerfile (Full Stack v2)
#
# PURPOSE:
#   Multi-stage Docker build for the Capital Markets multi-agent API service.
#   Includes the full ANTS core framework (agents, memory, LLM client) plus
#   the Capital Markets flavor (6 agents, 3 councils, 4 workflows).
#
# BUILD CONTEXT:
#   *** IMPORTANT: Build context is now the REPO ROOT (not this directory) ***
#   This is required to include src/core/ in the image.
#
#   For Cloud Shell (no local Docker daemon), use:
#       cd /path/to/AscendERP
#       az acr build --registry antscmlab \
#           --image ants-capital-markets:latest \
#           -f flavors/capital-markets/Dockerfile .
#
#   For local Docker builds:
#       docker build -t antscmlab.azurecr.io/ants-capital-markets:latest \
#           -f flavors/capital-markets/Dockerfile .
#
# MODES:
#   MOCK_MODE=true  (default) — numpy simulations, no LLM/DB needed
#   MOCK_MODE=false — real agents with PRREEL loop, LLM, pgvector, ANF
#
# DEPLOYMENT TARGET:
#   AKS cluster ants-cm-lab-aks in RG DNvidiaBTANF (East US 2)
#
# HISTORY:
#   2026-03-04 — Initial creation (mock API only)
#   2026-03-04 — GAP #6 fix: Removed invalid ../../src/core COPY
#   2026-03-04 — v2: Build context changed to repo root, full stack included
################################################################################

# ==============================================================================
# Stage 1: Builder — Install all Python dependencies
# ==============================================================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Build-time system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from the capital-markets flavor directory
# (build context is repo root, so path is relative to repo root)
COPY flavors/capital-markets/requirements.txt .

# Create venv and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# ==============================================================================
# Stage 2: Runtime — Lean image with only app code and pre-built venv
# ==============================================================================
FROM python:3.11-slim

WORKDIR /app

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built venv from builder
COPY --from=builder /opt/venv /opt/venv

# --- Copy ANTS Core Framework ---
# These are the shared modules used by all flavors:
#   - src/core/agent/base.py — BaseAgent with PRREEL loop
#   - src/core/llm_client.py — LLM inference (Azure AI Foundry, NIM, Ollama)
#   - src/core/memory/ — Memory substrate (pgvector + ANF)
#   - src/core/safety/ — Guardrails client
#   - src/core/observability.py — OpenTelemetry integration
COPY src/core/ /app/src/core/

# --- Copy integrations ---
# Azure AI Foundry client for managed model endpoints
COPY src/integrations/ /app/src/integrations/

# --- Copy Capital Markets flavor ---
# Agents, councils, workflows, configs, api_gateway, sample data
COPY flavors/capital-markets/ /app/flavors/capital-markets/

# --- Copy AI configs (NIM models, NeMo guardrails) ---
COPY ai/ /app/ai/

# --- Symlink api_gateway to app root for uvicorn CMD ---
# uvicorn expects the module at the PYTHONPATH root
RUN ln -sf /app/flavors/capital-markets/api_gateway.py /app/api_gateway.py

# Create __init__.py files for Python package imports
RUN touch /app/src/__init__.py && \
    touch /app/src/core/__init__.py && \
    touch /app/src/integrations/__init__.py && \
    touch /app/flavors/__init__.py && \
    touch /app/flavors/capital-markets/__init__.py || true
# Note: capital-markets has a hyphen which isn't valid for Python imports.
# The api_gateway.py uses underscore imports (flavors.capital_markets.agents.*)
# We handle this by creating a symlink:
RUN ln -sf /app/flavors/capital-markets /app/flavors/capital_markets

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    MOCK_MODE=true

# Create non-root user (CIS Docker Benchmark 4.1)
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()" || exit 1

# Run API gateway
CMD ["uvicorn", "api_gateway:app", "--host", "0.0.0.0", "--port", "8000"]
