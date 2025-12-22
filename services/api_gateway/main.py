"""
ANTS API Gateway.
Main entry point for all agent interactions.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import structlog
import uuid

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from services.api_gateway.auth import (
    get_auth_context,
    get_optional_auth,
    require_scope,
    auth_service,
    AuthContext
)
from services.api_gateway.ratelimit import rate_limiter


logger = structlog.get_logger()


# Request/Response Models
class AgentRequest(BaseModel):
    """Request to invoke an agent."""
    agent_type: str = Field(..., description="Type of agent to invoke")
    input_data: Dict[str, Any] = Field(..., description="Input data for agent")
    tenant_id: str = Field(..., description="Tenant identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Response from agent invocation."""
    trace_id: str
    success: bool
    output: Any
    actions_taken: List[Dict[str, Any]] = []
    latency_ms: float
    tokens_used: int = 0
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    components: Dict[str, str]


# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    logger.info("api_gateway_starting")

    # Initialize dependencies
    # - Database connections
    # - Agent registry
    # - Memory substrate
    # - Policy engine

    yield

    # Shutdown
    logger.info("api_gateway_stopping")


# Create FastAPI app
app = FastAPI(
    title="ANTS API Gateway",
    description="AI-Agent Native Tactical System API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry instrumentation
FastAPIInstrumentor.instrument_app(app)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        components={
            "database": "healthy",
            "memory": "healthy",
            "policy": "healthy",
            "agents": "healthy"
        }
    )


@app.post("/v1/agents/invoke", response_model=AgentResponse)
async def invoke_agent(
    request: AgentRequest,
    http_request: Request,
    auth: AuthContext = Depends(require_scope("agent:invoke"))
):
    """
    Invoke an agent with the given input.
    Requires authentication and agent:invoke scope.
    """
    trace_id = str(uuid.uuid4())

    # Apply rate limiting
    await rate_limiter.check_rate_limit(http_request, auth.tenant_id)

    # Validate tenant_id matches auth context
    if request.tenant_id != auth.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant ID mismatch with authentication"
        )

    logger.info(
        "agent_invocation_started",
        trace_id=trace_id,
        agent_type=request.agent_type,
        tenant_id=request.tenant_id,
        user_id=auth.user_id
    )

    try:
        # Get agent from registry
        # agent = agent_registry.get(request.agent_type)

        # Create context
        # context = AgentContext(
        #     trace_id=trace_id,
        #     tenant_id=request.tenant_id,
        #     user_id=request.user_id,
        #     session_id=request.session_id,
        #     metadata=request.metadata
        # )

        # Run agent
        # result = await agent.run(request.input_data, context)

        # Placeholder response
        return AgentResponse(
            trace_id=trace_id,
            success=True,
            output={"message": "Agent executed successfully"},
            actions_taken=[],
            latency_ms=100.0,
            tokens_used=500
        )

    except Exception as e:
        logger.error(
            "agent_invocation_failed",
            trace_id=trace_id,
            error=str(e)
        )

        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {str(e)}"
        )


@app.post("/v1/auth/token")
async def create_token(
    tenant_id: str = Field(..., description="Tenant ID"),
    user_id: Optional[str] = Field(None, description="User ID"),
    scopes: List[str] = Field(default_factory=lambda: ["agent:invoke", "memory:read"])
):
    """
    Create a JWT token for authentication.
    In production, this would verify credentials first.
    """
    token = auth_service.create_jwt_token(
        tenant_id=tenant_id,
        user_id=user_id,
        scopes=scopes
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours
        "scopes": scopes
    }


@app.get("/v1/agents", response_model=List[Dict[str, Any]])
async def list_agents(
    auth: Optional[AuthContext] = Depends(get_optional_auth)
):
    """
    List available agents.
    Optional authentication for personalized results.
    """
    # In production, filter based on tenant permissions
    return [
        {
            "type": "finance.reconciliation",
            "name": "Reconciliation Agent",
            "description": "Automates financial reconciliation",
            "category": "finance"
        },
        {
            "type": "retail.inventory",
            "name": "Inventory Agent",
            "description": "Manages inventory levels and replenishment",
            "category": "retail"
        },
        {
            "type": "cybersecurity.defender",
            "name": "Defender Triage Agent",
            "description": "Triages security alerts",
            "category": "security"
        },
        {
            "type": "hr.recruitment",
            "name": "Recruitment Agent",
            "description": "Resume screening and candidate matching",
            "category": "hr"
        },
        {
            "type": "crm.lead_scoring",
            "name": "Lead Scoring Agent",
            "description": "Qualifies and prioritizes leads",
            "category": "crm"
        }
    ]


@app.get("/v1/memory/{tenant_id}/search")
async def search_memory(
    tenant_id: str,
    query: str,
    http_request: Request,
    memory_type: str = "semantic",
    limit: int = 10,
    auth: AuthContext = Depends(require_scope("memory:read"))
):
    """
    Search agent memory.
    Requires authentication and memory:read scope.
    """
    # Apply rate limiting
    await rate_limiter.check_rate_limit(http_request, auth.tenant_id)

    # Validate tenant_id matches auth
    if tenant_id != auth.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    # Placeholder
    return {
        "results": [],
        "total": 0,
        "query": query,
        "memory_type": memory_type
    }


@app.get("/v1/metrics/clear")
async def get_clear_metrics():
    """Get CLEAR metrics for all agents."""
    return {
        "cost": {
            "total_tokens": 1500000,
            "estimated_cost_usd": 30.50
        },
        "latency": {
            "p50_ms": 150,
            "p95_ms": 450,
            "p99_ms": 1200
        },
        "efficacy": {
            "success_rate": 0.95,
            "avg_confidence": 0.87
        },
        "assurance": {
            "policy_compliance_rate": 0.99,
            "audit_coverage": 1.0
        },
        "reliability": {
            "uptime": 0.999,
            "error_rate": 0.01
        }
    }


def run():
    """Run the API gateway."""
    import uvicorn
    uvicorn.run(
        "services.api_gateway.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


if __name__ == "__main__":
    run()
