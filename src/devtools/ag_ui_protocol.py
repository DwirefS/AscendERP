"""
AG-UI Protocol - Standardized Agent-User Interface

Implements Server-Sent Events (SSE) streaming and human-in-the-loop approvals
following Microsoft Agent Framework patterns for consistent agent UX.

Reference: https://github.com/microsoft/agent-framework
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, Callable, AsyncIterator
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
from sse_starlette.sse import EventSourceResponse


class MessageType(Enum):
    """AG-UI message types."""
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    RESPONSE = "response"
    ERROR = "error"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"


class ApprovalStatus(Enum):
    """Human-in-the-loop approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class AGUIMessage:
    """Standardized AG-UI message."""
    message_type: str
    content: Any
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    def to_sse(self) -> str:
        """Convert to Server-Sent Events format."""
        return f"data: {json.dumps(self.to_dict())}\n\n"


@dataclass
class ApprovalRequest:
    """Human-in-the-loop approval request."""
    request_id: str
    action: str
    description: str
    risk_level: str  # low, medium, high, critical
    context: Dict[str, Any]
    timeout_seconds: int = 30
    auto_approve: bool = False


class AGUIProtocol:
    """
    AG-UI Protocol implementation.

    Provides:
    - Server-Sent Events streaming
    - Human-in-the-loop approval mechanism
    - Standardized message format
    - Progress tracking
    """

    def __init__(self):
        self.active_streams: Dict[str, asyncio.Queue] = {}
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_callbacks: Dict[str, Callable] = {}

    async def create_stream(self, session_id: str) -> AsyncIterator[str]:
        """
        Create SSE stream for agent-user communication.

        Args:
            session_id: Unique session identifier

        Yields:
            Server-Sent Events formatted messages
        """
        # Create message queue for this session
        queue = asyncio.Queue()
        self.active_streams[session_id] = queue

        try:
            while True:
                # Wait for next message
                message = await queue.get()

                # Check for stream termination
                if message is None:
                    break

                # Convert to SSE format and yield
                if isinstance(message, AGUIMessage):
                    yield message.to_sse()
                else:
                    # Wrap raw data in AGUIMessage
                    sse_msg = AGUIMessage(
                        message_type=MessageType.RESPONSE.value,
                        content=message
                    )
                    yield sse_msg.to_sse()

        finally:
            # Clean up
            if session_id in self.active_streams:
                del self.active_streams[session_id]

    async def send_message(
        self,
        session_id: str,
        message_type: MessageType,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Send message to client via SSE stream.

        Args:
            session_id: Session to send to
            message_type: Type of message
            content: Message content
            metadata: Optional metadata
        """
        if session_id not in self.active_streams:
            # Session not active
            return

        message = AGUIMessage(
            message_type=message_type.value,
            content=content,
            metadata=metadata
        )

        await self.active_streams[session_id].put(message)

    async def send_thinking(self, session_id: str, thought: str):
        """Send agent thinking/reasoning to client."""
        await self.send_message(
            session_id,
            MessageType.THINKING,
            {"thought": thought}
        )

    async def send_tool_use(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict[str, Any]
    ):
        """Notify client of tool invocation."""
        await self.send_message(
            session_id,
            MessageType.TOOL_USE,
            {
                "tool": tool_name,
                "input": tool_input
            }
        )

    async def send_tool_result(
        self,
        session_id: str,
        tool_name: str,
        result: Any,
        success: bool = True
    ):
        """Send tool execution result to client."""
        await self.send_message(
            session_id,
            MessageType.TOOL_RESULT,
            {
                "tool": tool_name,
                "result": result,
                "success": success
            }
        )

    async def send_response(self, session_id: str, response: str):
        """Send final response to client."""
        await self.send_message(
            session_id,
            MessageType.RESPONSE,
            {"response": response}
        )

    async def send_error(self, session_id: str, error: str):
        """Send error message to client."""
        await self.send_message(
            session_id,
            MessageType.ERROR,
            {"error": error}
        )

    async def request_approval(
        self,
        session_id: str,
        request: ApprovalRequest,
        callback: Optional[Callable] = None
    ) -> str:
        """
        Request human approval for an action.

        Args:
            session_id: Session to request approval from
            request: Approval request details
            callback: Optional callback on approval/rejection

        Returns:
            Approval status (approved, rejected, timeout)
        """
        # Store request
        self.pending_approvals[request.request_id] = request
        if callback:
            self.approval_callbacks[request.request_id] = callback

        # Send approval request to client
        await self.send_message(
            session_id,
            MessageType.APPROVAL_REQUEST,
            {
                "request_id": request.request_id,
                "action": request.action,
                "description": request.description,
                "risk_level": request.risk_level,
                "context": request.context,
                "timeout_seconds": request.timeout_seconds
            }
        )

        # Wait for approval with timeout
        start_time = time.time()
        while time.time() - start_time < request.timeout_seconds:
            if request.request_id not in self.pending_approvals:
                # Approval received
                return ApprovalStatus.APPROVED.value

            await asyncio.sleep(0.5)

        # Timeout - check auto_approve
        if request.auto_approve:
            return ApprovalStatus.APPROVED.value
        else:
            return ApprovalStatus.TIMEOUT.value

    async def handle_approval_response(
        self,
        request_id: str,
        approved: bool,
        feedback: Optional[str] = None
    ):
        """
        Handle approval response from user.

        Args:
            request_id: Request being responded to
            approved: Whether user approved the action
            feedback: Optional user feedback
        """
        if request_id not in self.pending_approvals:
            return

        request = self.pending_approvals.pop(request_id)

        # Call callback if exists
        if request_id in self.approval_callbacks:
            callback = self.approval_callbacks.pop(request_id)
            await callback(approved, feedback)

    async def close_stream(self, session_id: str):
        """Close SSE stream for session."""
        if session_id in self.active_streams:
            # Send termination signal
            await self.active_streams[session_id].put(None)


# FastAPI integration helpers
def create_sse_response(protocol: AGUIProtocol, session_id: str):
    """
    Create FastAPI SSE response for AG-UI streaming.

    Usage:
        @app.get("/agent/stream/{session_id}")
        async def stream_agent(session_id: str):
            return create_sse_response(agui_protocol, session_id)
    """
    return EventSourceResponse(protocol.create_stream(session_id))


class StreamingResponse:
    """
    Convenience wrapper for AG-UI streaming responses.

    Example:
        async with StreamingResponse(agui_protocol, session_id) as stream:
            await stream.thinking("Planning approach...")
            await stream.tool_use("search", {"query": "Azure AI"})
            result = execute_search("Azure AI")
            await stream.tool_result("search", result)
            await stream.response("Found 10 results about Azure AI")
    """

    def __init__(self, protocol: AGUIProtocol, session_id: str):
        self.protocol = protocol
        self.session_id = session_id

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.protocol.close_stream(self.session_id)

    async def thinking(self, thought: str):
        """Send thinking message."""
        await self.protocol.send_thinking(self.session_id, thought)

    async def tool_use(self, tool_name: str, tool_input: Dict[str, Any]):
        """Send tool use notification."""
        await self.protocol.send_tool_use(self.session_id, tool_name, tool_input)

    async def tool_result(self, tool_name: str, result: Any, success: bool = True):
        """Send tool result."""
        await self.protocol.send_tool_result(
            self.session_id, tool_name, result, success
        )

    async def response(self, response: str):
        """Send final response."""
        await self.protocol.send_response(self.session_id, response)

    async def error(self, error: str):
        """Send error."""
        await self.protocol.send_error(self.session_id, error)

    async def request_approval(
        self,
        request: ApprovalRequest,
        callback: Optional[Callable] = None
    ) -> str:
        """Request human approval."""
        return await self.protocol.request_approval(
            self.session_id, request, callback
        )


# Global AG-UI protocol instance
agui_protocol = AGUIProtocol()


def get_agui_protocol() -> AGUIProtocol:
    """Get global AG-UI protocol instance."""
    return agui_protocol
