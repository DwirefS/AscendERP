"""
AG-UI Streaming API

FastAPI endpoints for real-time agent-user streaming communication.
Implements Server-Sent Events (SSE) following Microsoft Agent Framework patterns.

Reference: https://github.com/microsoft/agent-framework
"""

import asyncio
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.devtools.ag_ui_protocol import (
    AGUIProtocol,
    create_sse_response,
    ApprovalRequest,
    ApprovalStatus
)
from src.core.agent.base import AgentContext, AgentConfig
from src.core.observability import tracer

# Global AG-UI protocol instance
agui = AGUIProtocol()

# Agent registry (in production, use proper agent management)
agent_registry: Dict[str, Any] = {}


class AgentRequest(BaseModel):
    """Request to execute an agent."""
    agent_id: str = Field(..., description="Agent identifier to execute")
    input_data: Dict[str, Any] = Field(..., description="Input data for agent")
    tenant_id: str = Field(..., description="Tenant identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AgentResponse(BaseModel):
    """Response from agent execution."""
    session_id: str
    success: bool
    output: Any
    trace_id: str
    stream_url: str


# FastAPI app for agent streaming
app = FastAPI(
    title="ANTS AG-UI Streaming API",
    description="Real-time agent execution with Server-Sent Events streaming",
    version="1.0.0"
)


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "service": "ANTS AG-UI Streaming API",
        "version": "1.0.0",
        "endpoints": {
            "execute": "/agent/execute",
            "stream": "/agent/stream/{session_id}",
            "approve": "/agent/approve/{request_id}",
            "status": "/agent/status/{session_id}"
        }
    }


@app.post("/agent/execute", response_model=AgentResponse)
async def execute_agent(
    request: AgentRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute an agent with real-time SSE streaming.

    Returns a session_id and stream_url. Client should connect to stream_url
    to receive real-time updates via Server-Sent Events.

    Args:
        request: Agent execution request

    Returns:
        Session ID and streaming URL

    Example:
        POST /agent/execute
        {
            "agent_id": "finance-agent-1",
            "input_data": {"action": "reconcile_invoices", "date": "2024-01"},
            "tenant_id": "tenant-123",
            "user_id": "user-456"
        }

        Response:
        {
            "session_id": "sess-abc123",
            "stream_url": "/agent/stream/sess-abc123"
        }

        Then connect to: GET /agent/stream/sess-abc123
    """
    # Create session
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    trace_id = f"trace-{uuid.uuid4().hex}"

    # Create agent context
    context = AgentContext(
        trace_id=trace_id,
        tenant_id=request.tenant_id,
        user_id=request.user_id,
        session_id=session_id,
        metadata=request.metadata
    )

    # Schedule agent execution in background
    background_tasks.add_task(
        execute_agent_with_streaming,
        session_id=session_id,
        agent_id=request.agent_id,
        input_data=request.input_data,
        context=context
    )

    return AgentResponse(
        session_id=session_id,
        success=True,
        output={"status": "started"},
        trace_id=trace_id,
        stream_url=f"/agent/stream/{session_id}"
    )


@app.get("/agent/stream/{session_id}")
async def stream_agent_execution(session_id: str):
    """
    Server-Sent Events stream for agent execution.

    Connect to this endpoint to receive real-time updates:
    - Agent thinking/reasoning
    - Tool invocations
    - Tool results
    - Final response
    - Errors

    Args:
        session_id: Session identifier from /agent/execute

    Returns:
        Server-Sent Events stream

    Example:
        GET /agent/stream/sess-abc123

        Events:
        data: {"message_type": "thinking", "content": {"thought": "Analyzing data..."}}

        data: {"message_type": "tool_use", "content": {"tool": "search", "input": {...}}}

        data: {"message_type": "tool_result", "content": {"tool": "search", "result": {...}}}

        data: {"message_type": "response", "content": {"response": "Analysis complete"}}
    """
    with tracer.start_as_current_span("agent_stream") as span:
        span.set_attribute("session.id", session_id)

        return create_sse_response(agui, session_id)


@app.post("/agent/approve/{request_id}")
async def approve_action(
    request_id: str,
    approved: bool,
    feedback: Optional[str] = None
):
    """
    Respond to human-in-the-loop approval request.

    When an agent requests approval for a high-risk action, the user
    receives an approval_request message via SSE. Use this endpoint
    to respond.

    Args:
        request_id: Approval request ID from approval_request message
        approved: Whether to approve (true) or reject (false) the action
        feedback: Optional user feedback

    Returns:
        Approval status

    Example:
        POST /agent/approve/approve-payment-123
        {
            "approved": true,
            "feedback": "Verified with vendor"
        }
    """
    with tracer.start_as_current_span("approval_response") as span:
        span.set_attribute("request.id", request_id)
        span.set_attribute("approved", approved)

        await agui.handle_approval_response(
            request_id=request_id,
            approved=approved,
            feedback=feedback
        )

        return {
            "request_id": request_id,
            "status": "approved" if approved else "rejected",
            "feedback": feedback
        }


@app.get("/agent/status/{session_id}")
async def get_session_status(session_id: str):
    """
    Get session status and metadata.

    Args:
        session_id: Session identifier

    Returns:
        Session status information
    """
    # In production, query from database
    return {
        "session_id": session_id,
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }


async def execute_agent_with_streaming(
    session_id: str,
    agent_id: str,
    input_data: Dict[str, Any],
    context: AgentContext
):
    """
    Execute agent with AG-UI streaming.

    This function runs in the background and streams progress to the client
    via Server-Sent Events.

    Args:
        session_id: Session identifier for streaming
        agent_id: Agent to execute
        input_data: Input data
        context: Execution context
    """
    with tracer.start_as_current_span("agent_execution_background") as span:
        span.set_attribute("session.id", session_id)
        span.set_attribute("agent.id", agent_id)

        try:
            # Get agent from registry
            if agent_id not in agent_registry:
                await agui.send_error(
                    session_id,
                    f"Agent not found: {agent_id}"
                )
                await agui.close_stream(session_id)
                return

            agent = agent_registry[agent_id]

            # Stream thinking
            await agui.send_thinking(
                session_id,
                f"Starting {agent.config.name}..."
            )

            # Simulate agent execution with streaming
            # In production, integrate with actual agent.run()
            await asyncio.sleep(0.5)

            await agui.send_thinking(
                session_id,
                "Analyzing input data..."
            )

            await asyncio.sleep(0.5)

            # Simulate tool use
            await agui.send_tool_use(
                session_id,
                "vector_search",
                {"query": str(input_data), "top_k": 5}
            )

            await asyncio.sleep(1.0)

            # Simulate tool result
            await agui.send_tool_result(
                session_id,
                "vector_search",
                {"results": ["result1", "result2"], "count": 2},
                success=True
            )

            # Check if high-risk action requires approval
            if input_data.get("requires_approval"):
                await agui.send_thinking(
                    session_id,
                    "Requesting approval for high-risk action..."
                )

                approval_request = ApprovalRequest(
                    request_id=f"approve-{session_id}",
                    action=input_data.get("action", "execute"),
                    description="Execute high-risk operation",
                    risk_level="high",
                    context=input_data,
                    timeout_seconds=60
                )

                approval_status = await agui.request_approval(
                    session_id,
                    approval_request
                )

                if approval_status != ApprovalStatus.APPROVED.value:
                    await agui.send_response(
                        session_id,
                        "Action cancelled: approval denied or timeout"
                    )
                    await agui.close_stream(session_id)
                    return

            # Send final response
            await agui.send_response(
                session_id,
                f"Agent {agent_id} completed successfully. Processed: {input_data}"
            )

            # Close stream
            await agui.close_stream(session_id)

            span.set_attribute("success", True)

        except Exception as e:
            span.record_exception(e)
            span.set_attribute("success", False)

            await agui.send_error(session_id, str(e))
            await agui.close_stream(session_id)


@app.on_event("startup")
async def startup():
    """Initialize agent registry on startup."""
    # In production, load agents from database or agent factory
    # For now, create placeholder registry
    pass


@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown."""
    # Close all active streams
    for session_id in list(agui.active_streams.keys()):
        await agui.close_stream(session_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
