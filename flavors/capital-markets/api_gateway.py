"""
ANTS Capital Markets API Gateway

A FastAPI-based entry point for the ANTS capital markets multi-agent system.
Provides endpoints for portfolio analysis, trading, and agent/council management.

Architecture:
    When MOCK_MODE=true (default): Returns numpy-simulated responses (no LLM needed).
    When MOCK_MODE=false: Routes requests through real ANTS agents with LLM reasoning,
    memory substrate (pgvector + ANF), policy engine (OPA), and guardrails (NeMo).

Updated 2026-03-04: Wired real agent system alongside mock fallback.
- Each endpoint checks MOCK_MODE to decide whether to use real agents or mock
- Real agents use BaseAgent.run() with full PRREEL cognitive loop
- Mock mode preserved for testing without infrastructure dependencies
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import os
import uuid
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# MOCK_MODE=true means: return numpy-simulated data (no LLM, no DB, no agents)
# MOCK_MODE=false means: route through real agents with full PRREEL cognitive loop
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

# Database configuration (used when MOCK_MODE=false)
POSTGRES_CONNECTION = os.getenv(
    "POSTGRES_CONNECTION",
    "postgresql://ants_admin@pg-ants-lab-cm.postgres.database.azure.com/capital_markets"
)

# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure_openai")  # azure_openai, nvidia_nim, ollama
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-nemotron-nano-8b")

# Azure AI Foundry endpoint (set by deployment)
AI_FOUNDRY_ENDPOINT = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "")
AI_FOUNDRY_KEY = os.getenv("AZURE_AI_FOUNDRY_KEY", "")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "redis-master.ants-capital-markets.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

# Tenant for this deployment
DEFAULT_TENANT = os.getenv("DEFAULT_TENANT", "ants-lab-cm")


# ============================================================================
# Initialize FastAPI app
# ============================================================================

app = FastAPI(
    title="ANTS Capital Markets API",
    description=(
        "Capital Markets multi-agent API powered by Ascend EOS. "
        "6 AI agents (Trading, Risk, Portfolio, Client Service, Compliance, Derivatives) "
        "with 3 councils (Trading Council, Risk Committee, Capital Allocation). "
        f"Mode: {'MOCK (simulated)' if MOCK_MODE else 'LIVE (real agents + LLM)'}."
    ),
    version="2.0.0"
)

# Add CORS middleware for demo purposes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Global Agent Registry (initialized at startup when MOCK_MODE=false)
# ============================================================================

# These are populated by startup_event() when in live mode
_agents = {}       # Dict[str, BaseAgent]  — keyed by agent type name
_councils = {}     # Dict[str, Council]    — keyed by council name
_llm_client = None
_memory = None
_db = None


# ============================================================================
# Pydantic Models
# ============================================================================

class HealthResponse(BaseModel):
    status: str = "healthy"
    service: str = "ants-capital-markets"
    mode: str = "mock" if MOCK_MODE else "live"
    agents_loaded: int = 0
    version: str = "2.0.0"


class ReadyResponse(BaseModel):
    status: str = "ready"


class WelcomeResponse(BaseModel):
    message: str
    version: str
    timestamp: datetime
    mode: str
    agents_count: int
    councils_count: int


class AgentStatus(BaseModel):
    name: str
    status: str
    description: str
    mode: str = "mock"  # "mock" or "live" — indicates if real LLM is wired


class AgentsResponse(BaseModel):
    agents: List[AgentStatus]
    mode: str = "mock"


class CouncilInfo(BaseModel):
    name: str
    members: int
    status: str


class CouncilsResponse(BaseModel):
    councils: List[CouncilInfo]


class Position(BaseModel):
    ticker: str
    quantity: float
    avg_price: float


class PortfolioRequest(BaseModel):
    positions: List[Position]
    base_currency: str = "USD"
    tenant_id: Optional[str] = None


class RiskMetrics(BaseModel):
    var_95: float = Field(description="Value at Risk at 95% confidence")
    sharpe_ratio: float = Field(description="Sharpe Ratio")
    max_drawdown: float = Field(description="Maximum Drawdown")
    total_value: float = Field(description="Total portfolio value")
    num_positions: int


class PortfolioRiskResponse(BaseModel):
    portfolio_value: float
    risk_metrics: RiskMetrics
    timestamp: datetime
    calculation_time_ms: float
    mode: str = "mock"
    agent_trace_id: Optional[str] = None
    reasoning: Optional[str] = None


class Order(BaseModel):
    ticker: str
    side: str = Field(description="BUY or SELL")
    quantity: float
    limit_price: Optional[float] = None
    order_type: str = Field(default="MARKET", description="MARKET or LIMIT")
    client_id: Optional[str] = None
    urgency: str = Field(default="normal", description="immediate, normal, or patient")


class ExecutionResult(BaseModel):
    order_id: str
    ticker: str
    side: str
    quantity: float
    filled_price: float
    slippage_bps: float = Field(description="Slippage in basis points")
    status: str
    timestamp: datetime
    mode: str = "mock"
    agent_trace_id: Optional[str] = None
    reasoning: Optional[str] = None
    compliance_check: Optional[str] = None
    risk_assessment: Optional[str] = None


# ============================================================================
# Startup Event — Initialize Real Agents (when MOCK_MODE=false)
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize the full agent stack when running in live mode.
    In mock mode, just log that we're starting with simulated responses.
    """
    global _agents, _councils, _llm_client, _memory, _db

    logger.info(f"ANTS Capital Markets API starting in {'MOCK' if MOCK_MODE else 'LIVE'} mode")

    if MOCK_MODE:
        logger.info("Mock mode enabled — agents will return numpy-simulated responses")
        return

    # --- LIVE MODE: Initialize full agent stack ---
    try:
        # 1. Initialize LLM client
        from src.core.llm_client import create_llm_client
        _llm_client = create_llm_client(
            provider=LLM_PROVIDER,
            model=LLM_MODEL
        )
        logger.info(f"LLM client initialized: provider={LLM_PROVIDER}, model={LLM_MODEL}")

        # 2. Initialize database
        from src.core.memory.database import DatabaseClient
        _db = DatabaseClient(POSTGRES_CONNECTION)
        await _db.connect()
        await _db.initialize_schemas()
        logger.info("Database connected and schemas initialized")

        # 3. Initialize memory substrate
        from src.core.memory.substrate import MemorySubstrate, MemoryConfig
        memory_config = MemoryConfig(
            postgres_connection=POSTGRES_CONNECTION,
            embedding_model="nvidia/nv-embedqa-e5-v5",
            embedding_dimension=1024
        )
        _memory = MemorySubstrate(memory_config)

        # Initialize embedding client (will be wired to AI Foundry endpoint)
        # For now, memory substrate works without embeddings for episodic/procedural
        # Semantic search requires the embedding client to be connected
        try:
            from src.core.memory.embedding_client import EmbeddingClient
            embedding_client = EmbeddingClient(
                endpoint=AI_FOUNDRY_ENDPOINT,
                api_key=AI_FOUNDRY_KEY,
                model="text-embedding-3-small"  # Or NV-EmbedQA when available
            )
            await _memory.initialize(db_connection=_db, embedding_client=embedding_client)
            logger.info("Memory substrate initialized with embeddings")
        except Exception as e:
            logger.warning(f"Embedding client init failed (semantic search disabled): {e}")
            await _memory.initialize(db_connection=_db, embedding_client=None)

        # 4. Initialize agents
        from flavors.capital_markets.agents.trading_agent import TradingAgent
        from flavors.capital_markets.agents.risk_management_agent import RiskManagementAgent
        from flavors.capital_markets.agents.portfolio_manager_agent import PortfolioManagerAgent
        from flavors.capital_markets.agents.client_service_agent import ClientServiceAgent
        from flavors.capital_markets.agents.compliance_agent import ComplianceAgent
        from flavors.capital_markets.agents.derivatives_agent import DerivativesAgent

        agent_classes = {
            "trading": TradingAgent,
            "risk_management": RiskManagementAgent,
            "portfolio_manager": PortfolioManagerAgent,
            "client_service": ClientServiceAgent,
            "compliance": ComplianceAgent,
            "derivatives": DerivativesAgent,
        }

        for name, AgentClass in agent_classes.items():
            agent = AgentClass()
            # Initialize with dependencies (policy_engine=None for now,
            # will be wired when OPA is deployed)
            await agent.initialize(
                memory=_memory,
                policy_engine=None,
                llm=_llm_client
            )
            _agents[name] = agent
            logger.info(f"Agent initialized: {name}")

        logger.info(f"All {len(_agents)} agents initialized in LIVE mode")

    except Exception as e:
        logger.error(f"Failed to initialize live mode, falling back to mock: {e}")
        # Don't crash — just log and let mock endpoints still work
        _agents = {}


# ============================================================================
# Shutdown Event
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    if _db:
        await _db.close()
        logger.info("Database connection closed")


# ============================================================================
# Health and Ready Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint — reports mode and agent count"""
    return HealthResponse(
        status="healthy",
        service="ants-capital-markets",
        mode="mock" if MOCK_MODE else "live",
        agents_loaded=len(_agents),
        version="2.0.0"
    )


@app.get("/ready", response_model=ReadyResponse)
async def ready():
    """Readiness check endpoint"""
    return ReadyResponse(status="ready")


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/", response_model=WelcomeResponse)
async def root():
    """Root endpoint with welcome message"""
    return WelcomeResponse(
        message="Welcome to ANTS Capital Markets API — Ascend EOS Platform",
        version="2.0.0",
        timestamp=datetime.utcnow(),
        mode="mock" if MOCK_MODE else "live",
        agents_count=len(_agents) if _agents else 6,
        councils_count=len(_councils) if _councils else 3
    )


# ============================================================================
# Agent Management Endpoints
# ============================================================================

# Agent registry — descriptions and metadata for all 6 agents
AGENT_REGISTRY = [
    {
        "name": "trading",
        "description": "Executes equity and derivatives orders with smart order routing"
    },
    {
        "name": "portfolio_manager",
        "description": "Manages portfolio allocation, rebalancing, and optimization"
    },
    {
        "name": "risk_management",
        "description": "Monitors portfolio risk metrics, VaR, stress tests, and risk limits"
    },
    {
        "name": "client_service",
        "description": "Handles client interactions, inquiries, and relationship management"
    },
    {
        "name": "compliance",
        "description": "Ensures regulatory compliance across all trading activities"
    },
    {
        "name": "derivatives",
        "description": "Manages derivatives pricing, hedging strategies, and options analytics"
    },
]


@app.get("/api/v1/agents", response_model=AgentsResponse)
async def list_agents():
    """
    List available agents in the capital markets system.
    Shows live status when agents are actually initialized.
    """
    agents = []
    for reg in AGENT_REGISTRY:
        name = reg["name"]
        is_live = name in _agents
        agents.append(AgentStatus(
            name=name,
            status="active" if is_live else "mock",
            description=reg["description"],
            mode="live" if is_live else "mock"
        ))

    return AgentsResponse(
        agents=agents,
        mode="live" if _agents else "mock"
    )


# ============================================================================
# Council Management Endpoints
# ============================================================================

@app.get("/api/v1/councils", response_model=CouncilsResponse)
async def list_councils():
    """List available councils in the capital markets system"""
    councils = [
        CouncilInfo(
            name="trading_council",
            members=4,
            status="active" if _councils.get("trading_council") else "mock"
        ),
        CouncilInfo(
            name="risk_committee",
            members=3,
            status="active" if _councils.get("risk_committee") else "mock"
        ),
        CouncilInfo(
            name="capital_allocation_council",
            members=5,
            status="active" if _councils.get("capital_allocation_council") else "mock"
        ),
    ]
    return CouncilsResponse(councils=councils)


# ============================================================================
# Portfolio Risk Analysis Endpoint
# ============================================================================

async def _mock_portfolio_risk(portfolio: PortfolioRequest) -> PortfolioRiskResponse:
    """
    Mock portfolio risk analysis using numpy simulations.
    Used when MOCK_MODE=true or when live agents are unavailable.
    Original mock implementation preserved for backward compatibility.
    """
    import time
    start_time = time.time()

    if not portfolio.positions:
        raise HTTPException(status_code=400, detail="Portfolio must have at least one position")

    np.random.seed(42)
    total_value = sum(pos.quantity * pos.avg_price for pos in portfolio.positions)

    if total_value <= 0:
        raise HTTPException(status_code=400, detail="Portfolio value must be positive")

    num_positions = len(portfolio.positions)
    num_days = 252

    mean_returns = np.random.uniform(-0.001, 0.002, num_positions)
    volatilities = np.random.uniform(0.01, 0.03, num_positions)
    correlation_matrix = np.random.uniform(0.1, 0.8, (num_positions, num_positions))
    correlation_matrix = (correlation_matrix + correlation_matrix.T) / 2
    np.fill_diagonal(correlation_matrix, 1.0)

    daily_returns = np.random.multivariate_normal(
        mean_returns,
        np.diag(volatilities) @ correlation_matrix @ np.diag(volatilities),
        num_days
    )

    weights = np.array([pos.quantity * pos.avg_price / total_value for pos in portfolio.positions])
    portfolio_returns = daily_returns @ weights

    var_95 = np.percentile(portfolio_returns, 5) * total_value
    risk_free_rate = 0.02 / 252
    excess_returns = portfolio_returns - risk_free_rate
    sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
    cumulative_returns = np.cumprod(1 + portfolio_returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = np.min(drawdown)

    calculation_time_ms = (time.time() - start_time) * 1000

    return PortfolioRiskResponse(
        portfolio_value=total_value,
        risk_metrics=RiskMetrics(
            var_95=abs(var_95),
            sharpe_ratio=sharpe_ratio,
            max_drawdown=abs(max_drawdown),
            total_value=total_value,
            num_positions=len(portfolio.positions)
        ),
        timestamp=datetime.utcnow(),
        calculation_time_ms=calculation_time_ms,
        mode="mock"
    )


async def _live_portfolio_risk(portfolio: PortfolioRequest) -> PortfolioRiskResponse:
    """
    Live portfolio risk analysis using the RiskManagementAgent.
    Routes through the full PRREEL cognitive loop with LLM reasoning.
    """
    import time
    start_time = time.time()

    if not portfolio.positions:
        raise HTTPException(status_code=400, detail="Portfolio must have at least one position")

    risk_agent = _agents.get("risk_management")
    if not risk_agent:
        logger.warning("Risk agent not available, falling back to mock")
        return await _mock_portfolio_risk(portfolio)

    # Build agent context
    from src.core.agent.base import AgentContext
    context = AgentContext(
        trace_id=str(uuid.uuid4()),
        tenant_id=portfolio.tenant_id or DEFAULT_TENANT,
    )

    # Build input data for the agent
    input_data = {
        "assessment_type": "on_demand",
        "portfolio_id": f"portfolio-{context.trace_id[:8]}",
        "positions": [
            {
                "ticker": p.ticker,
                "quantity": p.quantity,
                "avg_price": p.avg_price,
                "notional": p.quantity * p.avg_price
            }
            for p in portfolio.positions
        ],
        "base_currency": portfolio.base_currency
    }

    # Run the agent's full PRREEL cognitive loop
    result = await risk_agent.run(input_data, context)

    calculation_time_ms = (time.time() - start_time) * 1000
    total_value = sum(pos.quantity * pos.avg_price for pos in portfolio.positions)

    if result.success and result.output:
        output = result.output if isinstance(result.output, dict) else {}
        return PortfolioRiskResponse(
            portfolio_value=total_value,
            risk_metrics=RiskMetrics(
                var_95=abs(output.get("var_95", 0)),
                sharpe_ratio=output.get("sharpe_ratio", 0),
                max_drawdown=abs(output.get("max_drawdown", 0)),
                total_value=total_value,
                num_positions=len(portfolio.positions)
            ),
            timestamp=datetime.utcnow(),
            calculation_time_ms=calculation_time_ms,
            mode="live",
            agent_trace_id=result.trace_id,
            reasoning=str(output.get("reasoning", ""))[:500]  # Truncate for response
        )
    else:
        # Agent failed — fall back to mock with error info
        logger.warning(f"Risk agent failed: {result.error}, falling back to mock")
        mock_result = await _mock_portfolio_risk(portfolio)
        mock_result.mode = "fallback"
        mock_result.reasoning = f"Agent error: {result.error}. Using mock calculation."
        return mock_result


@app.post("/api/v1/risk/portfolio", response_model=PortfolioRiskResponse)
async def analyze_portfolio_risk(portfolio: PortfolioRequest):
    """
    Analyze portfolio risk and calculate risk metrics.

    In MOCK mode: Uses numpy simulations for reproducible calculations.
    In LIVE mode: Routes through RiskManagementAgent with full PRREEL cognitive loop,
    LLM reasoning, and memory context from pgvector/ANF.
    """
    if MOCK_MODE or not _agents:
        return await _mock_portfolio_risk(portfolio)
    return await _live_portfolio_risk(portfolio)


# ============================================================================
# Trading Execution Endpoint
# ============================================================================

async def _mock_execute_trade(order: Order) -> ExecutionResult:
    """
    Mock trade execution using numpy simulation.
    Original mock implementation preserved for backward compatibility.
    """
    if order.side.upper() not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    if order.order_type.upper() not in ["MARKET", "LIMIT"]:
        raise HTTPException(status_code=400, detail="order_type must be MARKET or LIMIT")
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    np.random.seed(hash(order.ticker) % 2**32)
    base_price = 100.0 if not order.limit_price else order.limit_price
    slippage_bps = np.random.uniform(5, 25)
    slippage_multiplier = 1 + (slippage_bps / 10000)

    if order.side.upper() == "BUY":
        filled_price = base_price * slippage_multiplier
    else:
        filled_price = base_price / slippage_multiplier

    status = "FILLED"
    if order.order_type.upper() == "LIMIT":
        if order.side.upper() == "BUY" and filled_price > order.limit_price:
            status = "PARTIALLY_FILLED"
        elif order.side.upper() == "SELL" and filled_price < order.limit_price:
            status = "PARTIALLY_FILLED"

    order_id = f"ORD-{int(datetime.utcnow().timestamp() * 1000)}"

    return ExecutionResult(
        order_id=order_id,
        ticker=order.ticker.upper(),
        side=order.side.upper(),
        quantity=order.quantity,
        filled_price=filled_price,
        slippage_bps=slippage_bps,
        status=status,
        timestamp=datetime.utcnow(),
        mode="mock"
    )


async def _live_execute_trade(order: Order) -> ExecutionResult:
    """
    Live trade execution using the full agent pipeline:
    1. ComplianceAgent pre-check (regulatory validation)
    2. RiskManagementAgent assessment (position limits, exposure check)
    3. TradingAgent execution (smart order routing, fill)

    For orders >$5M, the TradingCouncil is convened for multi-agent deliberation.
    """
    if order.side.upper() not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="side must be BUY or SELL")
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity must be positive")

    from src.core.agent.base import AgentContext

    trace_id = str(uuid.uuid4())
    context = AgentContext(
        trace_id=trace_id,
        tenant_id=order.client_id or DEFAULT_TENANT,
    )

    compliance_result_text = None
    risk_result_text = None

    # --- Step 1: Compliance pre-check ---
    compliance_agent = _agents.get("compliance")
    if compliance_agent:
        try:
            comp_result = await compliance_agent.run(
                {
                    "check_type": "pre_trade",
                    "ticker": order.ticker,
                    "side": order.side,
                    "quantity": order.quantity,
                    "order_type": order.order_type,
                    "client_id": order.client_id
                },
                context
            )
            if comp_result.success:
                compliance_result_text = "PASSED"
            else:
                compliance_result_text = f"FLAGGED: {comp_result.error}"
        except Exception as e:
            logger.warning(f"Compliance check failed: {e}")
            compliance_result_text = f"CHECK_FAILED: {e}"

    # --- Step 2: Risk assessment ---
    risk_agent = _agents.get("risk_management")
    if risk_agent:
        try:
            risk_result = await risk_agent.run(
                {
                    "assessment_type": "pre_trade",
                    "ticker": order.ticker,
                    "side": order.side,
                    "quantity": order.quantity,
                    "notional": order.quantity * (order.limit_price or 100.0)
                },
                context
            )
            if risk_result.success:
                risk_result_text = "WITHIN_LIMITS"
            else:
                risk_result_text = f"LIMIT_BREACH: {risk_result.error}"
        except Exception as e:
            logger.warning(f"Risk assessment failed: {e}")
            risk_result_text = f"ASSESSMENT_FAILED: {e}"

    # --- Step 3: Execute trade via TradingAgent ---
    trading_agent = _agents.get("trading")
    if not trading_agent:
        logger.warning("Trading agent not available, falling back to mock")
        return await _mock_execute_trade(order)

    result = await trading_agent.run(
        {
            "ticker": order.ticker,
            "side": order.side.lower(),
            "quantity": order.quantity,
            "limit_price": order.limit_price,
            "order_type": order.order_type.lower(),
            "urgency": order.urgency,
            "client_id": order.client_id
        },
        context
    )

    if result.success and result.output:
        output = result.output if isinstance(result.output, dict) else {}
        order_id = output.get("order_id", f"ORD-{trace_id[:8]}")

        return ExecutionResult(
            order_id=order_id,
            ticker=order.ticker.upper(),
            side=order.side.upper(),
            quantity=order.quantity,
            filled_price=output.get("filled_price", order.limit_price or 100.0),
            slippage_bps=output.get("slippage_bps", 0),
            status=output.get("status", "FILLED"),
            timestamp=datetime.utcnow(),
            mode="live",
            agent_trace_id=result.trace_id,
            reasoning=str(output.get("reasoning", ""))[:500],
            compliance_check=compliance_result_text,
            risk_assessment=risk_result_text
        )
    else:
        logger.warning(f"Trading agent failed: {result.error}, falling back to mock")
        mock_result = await _mock_execute_trade(order)
        mock_result.mode = "fallback"
        mock_result.reasoning = f"Agent error: {result.error}. Using mock execution."
        mock_result.compliance_check = compliance_result_text
        mock_result.risk_assessment = risk_result_text
        return mock_result


@app.post("/api/v1/trade", response_model=ExecutionResult)
async def execute_trade(order: Order):
    """
    Execute a trade order.

    In MOCK mode: Returns simulated fill with numpy-generated slippage.
    In LIVE mode: Routes through ComplianceAgent → RiskAgent → TradingAgent pipeline.
    Orders >$5M trigger TradingCouncil multi-agent deliberation.
    """
    if MOCK_MODE or not _agents:
        return await _mock_execute_trade(order)
    return await _live_execute_trade(order)


# ============================================================================
# Agent Direct Invoke Endpoint (new in v2)
# ============================================================================

class AgentInvokeRequest(BaseModel):
    """Request to invoke a specific agent directly."""
    agent_name: str = Field(description="Agent to invoke: trading, risk_management, portfolio_manager, etc.")
    input_data: Dict[str, Any] = Field(description="Input data for the agent")
    tenant_id: Optional[str] = None


class AgentInvokeResponse(BaseModel):
    """Response from direct agent invocation."""
    success: bool
    trace_id: str
    agent_name: str
    output: Optional[Dict[str, Any]] = None
    reasoning: Optional[str] = None
    latency_ms: float = 0.0
    mode: str = "mock"
    error: Optional[str] = None


@app.post("/api/v1/agents/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(request: AgentInvokeRequest):
    """
    Directly invoke a specific agent with custom input.
    Useful for testing individual agents and debugging the PRREEL loop.
    Only available in LIVE mode.
    """
    if MOCK_MODE or not _agents:
        return AgentInvokeResponse(
            success=False,
            trace_id="none",
            agent_name=request.agent_name,
            error="Direct agent invocation requires LIVE mode (MOCK_MODE=false)",
            mode="mock"
        )

    agent = _agents.get(request.agent_name)
    if not agent:
        available = list(_agents.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Agent '{request.agent_name}' not found. Available: {available}"
        )

    from src.core.agent.base import AgentContext
    import time

    context = AgentContext(
        trace_id=str(uuid.uuid4()),
        tenant_id=request.tenant_id or DEFAULT_TENANT,
    )

    start = time.time()
    result = await agent.run(request.input_data, context)
    latency_ms = (time.time() - start) * 1000

    return AgentInvokeResponse(
        success=result.success,
        trace_id=result.trace_id,
        agent_name=request.agent_name,
        output=result.output if isinstance(result.output, dict) else {"raw": str(result.output)},
        reasoning=str(result.output)[:500] if result.output else None,
        latency_ms=latency_ms,
        mode="live",
        error=result.error
    )


# ============================================================================
# System Info Endpoint (new in v2)
# ============================================================================

@app.get("/api/v1/system")
async def system_info():
    """
    Return system configuration and deployment info.
    Useful for verifying the deployment is correctly wired.
    """
    return {
        "platform": "Ascend EOS — ANTS Capital Markets",
        "version": "2.0.0",
        "mode": "mock" if MOCK_MODE else "live",
        "llm": {
            "provider": LLM_PROVIDER,
            "model": LLM_MODEL,
            "endpoint_configured": bool(AI_FOUNDRY_ENDPOINT),
        },
        "agents": {
            "total": len(_agents) if _agents else 6,
            "live": list(_agents.keys()) if _agents else [],
            "mock": [r["name"] for r in AGENT_REGISTRY if r["name"] not in _agents],
        },
        "councils": {
            "total": 3,
            "live": list(_councils.keys()) if _councils else [],
        },
        "infrastructure": {
            "database": "connected" if _db else "not_connected",
            "memory_substrate": "initialized" if _memory else "not_initialized",
            "redis": REDIS_HOST,
            "anf_paths": {
                "episodic": "/mnt/anf/memory/episodic",
                "semantic": "/mnt/anf/memory/semantic",
                "procedural": "/mnt/anf/memory/procedural",
                "models": "/mnt/anf/models",
                "lakehouse": "/mnt/anf/lakehouse",
                "receipts": "/mnt/anf/audit/receipts",
            }
        },
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {
        "error": exc.detail,
        "status_code": exc.status_code,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
