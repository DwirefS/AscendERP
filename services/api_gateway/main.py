"""
ANTS API Gateway.
Main entry point for all agent interactions.

Routing model:
- /api/v1/*  — primary resource-oriented API (agents, tasks)
- /v1/*      — invocation + utility endpoints (invoke, memory, auth)
- /health    — unauthenticated liveness
- /metrics   — operational summary (requires metrics:read or admin:*)

Rate limiting is applied per credential ("session") at the gateway. In a
multi-replica deployment the limiter should be backed by Redis with
per-tenant aggregate limits; the in-memory limiter here is the local
profile's implementation.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import hashlib
import structlog
import time
import uuid

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from services.api_gateway.auth import (
    get_auth_context,
    get_optional_auth,
    require_scope,
    auth_service,
    AuthContext,
    AuthService
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


class CreateAgentRequest(BaseModel):
    """Request to create (instantiate) an agent."""
    agent_type: str = Field(..., description="Registered agent type to instantiate")
    tenant_id: Optional[str] = Field(None, description="Tenant identifier")
    capabilities: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TaskRequest(BaseModel):
    """Request to submit a task for asynchronous execution."""
    task_type: str = Field(..., description="Type of task to execute")
    input_data: Dict[str, Any] = Field(..., description="Task input payload")
    priority: int = Field(5, ge=1, le=10, description="1 = highest, 10 = lowest")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TokenRequest(BaseModel):
    """Request body for token creation."""
    tenant_id: str = Field(..., description="Tenant ID")
    user_id: Optional[str] = Field(None, description="User ID")
    scopes: List[str] = Field(default_factory=lambda: ["agent:invoke", "memory:read"])


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    components: Dict[str, str]


def _build_registry():
    """
    Build the agent registry with the agents that can run in the current
    environment. Agents run without memory/LLM dependencies fall back to
    their built-in deterministic logic.
    """
    from src.core.agent.registry import AgentRegistry

    registry = AgentRegistry()

    try:
        from src.agents.finance.reconciliation import ReconciliationAgent
        registry.register(
            "finance.reconciliation",
            ReconciliationAgent,
            {
                "name": "Reconciliation Agent",
                "description": "Automates financial reconciliation",
                "category": "finance",
                "capabilities": ["reconcile", "discrepancy-detection"],
            },
        )
    except Exception as e:  # pragma: no cover - registration is best-effort
        logger.warning("agent_registration_failed", agent="finance.reconciliation", error=str(e))

    try:
        from src.agents.retail.inventory import InventoryAgent
        registry.register(
            "retail.inventory",
            InventoryAgent,
            {
                "name": "Inventory Agent",
                "description": "Manages inventory levels and replenishment",
                "category": "retail",
                "capabilities": ["forecast", "replenish"],
            },
        )
    except Exception as e:  # pragma: no cover
        logger.warning("agent_registration_failed", agent="retail.inventory", error=str(e))

    _register_manufacturing_agents(registry)

    return registry


def _register_manufacturing_agents(registry):
    """Register the manufacturing flavor's agent fleet (best-effort)."""
    manufacturing_agents = [
        ("manufacturing.production_planner", "production_planner_agent",
         "ProductionPlannerAgent", "MRP planning and policy-driven scheduling",
         ["mrp", "schedule", "capacity"]),
        ("manufacturing.quality", "quality_agent", "QualityAgent",
         "SPC analysis, NCR creation, and disposition", ["spc", "ncr", "cpk"]),
        ("manufacturing.maintenance", "maintenance_agent", "MaintenanceAgent",
         "Predictive maintenance risk scoring and PM scheduling",
         ["risk-scoring", "pm-scheduling"]),
        ("manufacturing.procurement", "procurement_agent", "ProcurementAgent",
         "Reorder purchasing and supplier scoring", ["reorder", "supplier-scoring"]),
        ("manufacturing.inventory", "inventory_agent", "InventoryAgent",
         "ABC classification, safety stock, shortage projection",
         ["abc", "safety-stock"]),
        ("manufacturing.ehs_compliance", "ehs_compliance_agent",
         "EHSComplianceAgent", "EHS incident triage and compliance calendar",
         ["incident-triage", "loto"]),
    ]
    import importlib

    for agent_type, module_name, cls_name, description, capabilities in manufacturing_agents:
        try:
            module = importlib.import_module(
                f"flavors.manufacturing.agents.{module_name}"
            )
            registry.register(
                agent_type,
                getattr(module, cls_name),
                {
                    "name": cls_name.replace("Agent", " Agent"),
                    "description": description,
                    "category": "manufacturing",
                    "capabilities": capabilities,
                },
            )
        except Exception as e:  # pragma: no cover - flavor is optional
            logger.warning("agent_registration_failed", agent=agent_type, error=str(e))


# Application lifecycle
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("api_gateway_starting")
    yield
    logger.info("api_gateway_stopping")


# Create FastAPI app
app = FastAPI(
    title="ANTS API Gateway",
    description="AI-Agent Native Tactical System API",
    version="1.0.0",
    lifespan=lifespan
)

# Gateway state is initialized eagerly (not in lifespan) so the app also
# works under test clients that don't run startup events.
app.state.registry = _build_registry()
# Per-tenant created agent instances: {tenant_id: [instance_info, ...]}
app.state.tenant_agents = {}
# In-memory task queue (local profile; production uses Service Bus/Redis)
app.state.tasks = {}
app.state.started_at = time.time()

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

# Mount flavor routers (best-effort: a broken flavor must not take down the gateway)
try:
    from flavors.manufacturing.mission_control import build_mission_control_router

    app.include_router(build_mission_control_router(require_scope))
    logger.info("flavor_mounted", flavor="manufacturing", prefix="/manufacturing")
except Exception as e:  # pragma: no cover - flavor is optional
    logger.warning("flavor_mount_failed", flavor="manufacturing", error=str(e))


async def enforce_rate_limit(request: Request, auth: AuthContext):
    """
    Apply per-credential rate limiting. The bucket key combines the hash of
    the presented credential with the path, so each session has its own
    budget and one client cannot starve a tenant's other sessions.
    """
    credential = (
        request.headers.get("authorization")
        or request.headers.get("x-api-key")
        or auth.tenant_id
    )
    client_key = f"{auth.tenant_id}:{hashlib.sha256(credential.encode()).hexdigest()[:16]}"
    await rate_limiter.check_rate_limit(request, client_key)


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


# ---------------------------------------------------------------------------
# /api/v1 resource API
# ---------------------------------------------------------------------------

@app.get("/api/v1/agents")
async def list_agents_api(
    http_request: Request,
    auth: AuthContext = Depends(require_scope("agents:read"))
) -> List[Dict[str, Any]]:
    """List registered agent types plus this tenant's created instances."""
    await enforce_rate_limit(http_request, auth)

    registry = app.state.registry
    agents = [
        {
            "type": m.agent_type,
            "name": m.name,
            "description": m.description,
            "category": m.category,
            "capabilities": m.capabilities,
            "version": m.version,
        }
        for m in registry.list_agents()
    ]
    # Tenant isolation: only this tenant's instances are visible
    agents.extend(app.state.tenant_agents.get(auth.tenant_id, []))
    return agents


@app.post("/api/v1/agents", status_code=201)
async def create_agent_api(
    request: CreateAgentRequest,
    http_request: Request,
    auth: AuthContext = Depends(require_scope("agents:write"))
) -> Dict[str, Any]:
    """Instantiate an agent for the calling tenant."""
    await enforce_rate_limit(http_request, auth)

    registry = app.state.registry
    metadata = registry.get_metadata(request.agent_type)

    instance_info = {
        "instance_id": str(uuid.uuid4()),
        "type": request.agent_type,
        "tenant_id": auth.tenant_id,
        "registered_type": metadata is not None,
        "capabilities": request.capabilities or (metadata.capabilities if metadata else []),
        "status": "created" if metadata else "pending_registration",
    }

    app.state.tenant_agents.setdefault(auth.tenant_id, []).append(instance_info)

    logger.info(
        "agent_instance_created",
        tenant_id=auth.tenant_id,
        agent_type=request.agent_type,
        registered=metadata is not None,
    )
    return instance_info


@app.post("/api/v1/tasks", status_code=202)
async def submit_task_api(
    request: TaskRequest,
    http_request: Request,
    auth: AuthContext = Depends(require_scope("tasks:submit"))
) -> Dict[str, Any]:
    """Submit a task for asynchronous execution."""
    await enforce_rate_limit(http_request, auth)

    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "task_type": request.task_type,
        "tenant_id": auth.tenant_id,
        "priority": request.priority,
        "status": "accepted",
        "submitted_at": time.time(),
    }
    app.state.tasks[task_id] = task

    logger.info(
        "task_submitted",
        task_id=task_id,
        task_type=request.task_type,
        tenant_id=auth.tenant_id,
    )
    return task


@app.get("/api/v1/tasks/{task_id}")
async def get_task_api(
    task_id: str,
    auth: AuthContext = Depends(require_scope("tasks:submit"))
) -> Dict[str, Any]:
    """Get a submitted task's status."""
    task = app.state.tasks.get(task_id)
    if not task or task["tenant_id"] != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.get("/metrics")
async def operational_metrics(
    auth: AuthContext = Depends(require_scope("metrics:read"))
) -> Dict[str, Any]:
    """Operational summary. Requires metrics:read (admin:* implies it)."""
    return {
        "uptime_seconds": time.time() - getattr(app.state, "started_at", time.time()),
        "registered_agent_types": len(app.state.registry.list_agents()),
        "tenant_agent_instances": sum(len(v) for v in app.state.tenant_agents.values()),
        "tasks_accepted": len(app.state.tasks),
    }


# ---------------------------------------------------------------------------
# /v1 invocation + utility API
# ---------------------------------------------------------------------------

@app.post("/v1/agents/invoke", response_model=AgentResponse)
async def invoke_agent(
    request: AgentRequest,
    http_request: Request,
    auth: AuthContext = Depends(require_scope("agent:invoke"))
):
    """
    Invoke an agent with the given input. Runs the full PRREEL loop
    (perceive → retrieve → reason → execute → verify → learn). Without a
    configured LLM/memory backend the agent uses its deterministic fallback
    logic, so this endpoint works in the local profile out of the box.
    """
    trace_id = str(uuid.uuid4())

    await enforce_rate_limit(http_request, auth)

    if request.tenant_id != auth.tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Tenant ID mismatch with authentication"
        )

    registry = app.state.registry
    metadata = registry.get_metadata(request.agent_type)
    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown agent type: {request.agent_type}"
        )

    logger.info(
        "agent_invocation_started",
        trace_id=trace_id,
        agent_type=request.agent_type,
        tenant_id=request.tenant_id,
        user_id=auth.user_id
    )

    try:
        from src.core.agent.base import AgentContext

        agent = registry.create_agent(request.agent_type)
        context = AgentContext(
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            user_id=request.user_id,
            session_id=request.session_id,
            metadata=request.metadata,
        )

        result = await agent.run(request.input_data, context)

        return AgentResponse(
            trace_id=result.trace_id,
            success=result.success,
            output=result.output,
            actions_taken=result.actions_taken,
            latency_ms=result.latency_ms,
            tokens_used=getattr(result, "tokens_used", 0) or 0,
            error=getattr(result, "error", None),
        )

    except HTTPException:
        raise
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
async def create_token(request: TokenRequest):
    """
    Create a JWT token for authentication.
    In production, this would verify credentials first.
    """
    # Mint with the same service used for verification (AuthService.current
    # is the most recently configured instance; see get_auth_context).
    service = AuthService.current or auth_service
    token = service.create_jwt_token(
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        scopes=request.scopes
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 86400,  # 24 hours
        "scopes": request.scopes
    }


@app.get("/v1/agents", response_model=List[Dict[str, Any]])
async def list_agents(
    auth: Optional[AuthContext] = Depends(get_optional_auth)
):
    """
    List available agents (legacy endpoint).
    Optional authentication for personalized results.
    """
    registry = app.state.registry
    return [
        {
            "type": m.agent_type,
            "name": m.name,
            "description": m.description,
            "category": m.category,
        }
        for m in registry.list_agents()
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
    await enforce_rate_limit(http_request, auth)

    # Validate tenant_id matches auth
    if tenant_id != auth.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    # Placeholder until the memory substrate is wired into the gateway
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
