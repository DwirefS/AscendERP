"""
DevUI Server - Visual Agent Debugging

Provides real-time visualization of agent reasoning chains, memory state,
policy evaluation, and council deliberations.

Based on Microsoft Agent Framework's DevUI pattern for development and testing.
Reference: https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/devui
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, asdict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# OpenTelemetry integration
from opentelemetry import trace
tracer = trace.get_tracer(__name__)


@dataclass
class ReasoningStep:
    """Single step in agent reasoning chain."""
    timestamp: float
    agent_id: str
    step_type: str  # perceive, retrieve, reason, execute, verify, learn
    phase_number: int  # 1-6
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    memory_snapshot: Optional[Dict[str, Any]] = None
    policy_evaluation: Optional[Dict[str, Any]] = None
    token_usage: Optional[Dict[str, int]] = None
    latency_ms: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            **asdict(self),
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat()
        }


@dataclass
class CouncilDeliberation:
    """Council decision-making session."""
    timestamp: float
    council_id: str
    decision_type: str
    phase: str  # propose, critique, resolve, amplify, verify
    agent_contributions: List[Dict[str, Any]]
    consensus_score: Optional[float] = None
    final_decision: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            **asdict(self),
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat()
        }


class AgentDebugger:
    """
    Captures and broadcasts agent execution for visual debugging.

    This is the "X-ray of Agent behavior" - making reasoning visible.
    """

    def __init__(self):
        self.active_sessions: Dict[str, List[ReasoningStep]] = {}
        self.council_sessions: Dict[str, List[CouncilDeliberation]] = {}
        self.connected_clients: Set[WebSocket] = set()
        self.max_history = 1000  # Keep last 1000 steps per agent

    async def capture_reasoning_step(
        self,
        agent_id: str,
        step_type: str,
        phase_number: int,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Capture a single reasoning step for visualization.

        Args:
            agent_id: Unique agent identifier
            step_type: One of: perceive, retrieve, reason, execute, verify, learn
            phase_number: 1-6 (agent lifecycle phase)
            input_data: Input to this phase
            output_data: Output from this phase
            metadata: Optional metadata (memory, policy, tokens, latency)
        """
        with tracer.start_as_current_span("devui.capture_step") as span:
            span.set_attribute("agent.id", agent_id)
            span.set_attribute("step.type", step_type)

            metadata = metadata or {}

            step = ReasoningStep(
                timestamp=time.time(),
                agent_id=agent_id,
                step_type=step_type,
                phase_number=phase_number,
                input_data=input_data,
                output_data=output_data,
                memory_snapshot=metadata.get("memory_snapshot"),
                policy_evaluation=metadata.get("policy_result"),
                token_usage=metadata.get("tokens"),
                latency_ms=metadata.get("latency_ms"),
                error=metadata.get("error")
            )

            # Store in session history
            if agent_id not in self.active_sessions:
                self.active_sessions[agent_id] = []

            self.active_sessions[agent_id].append(step)

            # Trim history if too long
            if len(self.active_sessions[agent_id]) > self.max_history:
                self.active_sessions[agent_id] = self.active_sessions[agent_id][-self.max_history:]

            # Broadcast to connected WebSocket clients
            await self.broadcast_step(agent_id, step)

    async def capture_council_deliberation(
        self,
        council_id: str,
        decision_type: str,
        phase: str,
        agent_contributions: List[Dict[str, Any]],
        consensus_score: Optional[float] = None,
        final_decision: Optional[Dict[str, Any]] = None
    ):
        """
        Capture council deliberation for visualization.

        Shows the 5-phase collective decision-making process.
        """
        with tracer.start_as_current_span("devui.capture_council") as span:
            span.set_attribute("council.id", council_id)
            span.set_attribute("council.phase", phase)

            deliberation = CouncilDeliberation(
                timestamp=time.time(),
                council_id=council_id,
                decision_type=decision_type,
                phase=phase,
                agent_contributions=agent_contributions,
                consensus_score=consensus_score,
                final_decision=final_decision
            )

            # Store in council history
            if council_id not in self.council_sessions:
                self.council_sessions[council_id] = []

            self.council_sessions[council_id].append(deliberation)

            # Broadcast to clients
            await self.broadcast_council(council_id, deliberation)

    async def broadcast_step(self, agent_id: str, step: ReasoningStep):
        """Broadcast reasoning step to all connected clients."""
        if not self.connected_clients:
            return

        message = {
            "type": "reasoning_step",
            "agent_id": agent_id,
            "step": step.to_dict()
        }

        # Send to all connected WebSocket clients
        disconnected = set()
        for client in self.connected_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.add(client)

        # Remove disconnected clients
        self.connected_clients -= disconnected

    async def broadcast_council(self, council_id: str, deliberation: CouncilDeliberation):
        """Broadcast council deliberation to all connected clients."""
        if not self.connected_clients:
            return

        message = {
            "type": "council_deliberation",
            "council_id": council_id,
            "deliberation": deliberation.to_dict()
        }

        disconnected = set()
        for client in self.connected_clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.add(client)

        self.connected_clients -= disconnected

    def get_agent_history(self, agent_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent reasoning history for an agent."""
        if agent_id not in self.active_sessions:
            return []

        steps = self.active_sessions[agent_id][-limit:]
        return [step.to_dict() for step in steps]

    def get_council_history(self, council_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent deliberation history for a council."""
        if council_id not in self.council_sessions:
            return []

        deliberations = self.council_sessions[council_id][-limit:]
        return [d.to_dict() for d in deliberations]


# Global debugger instance
debugger = AgentDebugger()


# FastAPI application
app = FastAPI(
    title="ANTS DevUI",
    description="Visual agent debugging and introspection",
    version="1.0.0"
)


@app.websocket("/ws/agent/{agent_id}")
async def agent_debug_stream(websocket: WebSocket, agent_id: str):
    """
    Real-time WebSocket stream of agent reasoning steps.

    Clients connect here to watch agent execution in real-time.
    """
    await websocket.accept()
    debugger.connected_clients.add(websocket)

    try:
        # Send historical steps on connection
        history = debugger.get_agent_history(agent_id, limit=50)
        await websocket.send_json({
            "type": "history",
            "agent_id": agent_id,
            "steps": history
        })

        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle client commands (e.g., pause, inspect memory)
                if message.get("command") == "inspect_memory":
                    # Return current memory snapshot
                    await websocket.send_json({
                        "type": "memory_snapshot",
                        "data": {}  # Fetch from memory substrate
                    })

            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        debugger.connected_clients.discard(websocket)


@app.websocket("/ws/council/{council_id}")
async def council_debug_stream(websocket: WebSocket, council_id: str):
    """Real-time WebSocket stream of council deliberations."""
    await websocket.accept()
    debugger.connected_clients.add(websocket)

    try:
        # Send historical deliberations
        history = debugger.get_council_history(council_id, limit=20)
        await websocket.send_json({
            "type": "history",
            "council_id": council_id,
            "deliberations": history
        })

        while True:
            try:
                data = await websocket.receive_text()
                # Handle client commands
            except asyncio.TimeoutError:
                continue

    except WebSocketDisconnect:
        debugger.connected_clients.discard(websocket)


@app.get("/api/agents", response_class=JSONResponse)
async def list_active_agents():
    """Get list of all agents with active debug sessions."""
    return {
        "agents": [
            {
                "agent_id": agent_id,
                "step_count": len(steps),
                "last_active": steps[-1].timestamp if steps else None
            }
            for agent_id, steps in debugger.active_sessions.items()
        ]
    }


@app.get("/api/agent/{agent_id}/history", response_class=JSONResponse)
async def get_agent_history(agent_id: str, limit: int = 100):
    """Get reasoning history for specific agent."""
    return {
        "agent_id": agent_id,
        "steps": debugger.get_agent_history(agent_id, limit)
    }


@app.get("/api/councils", response_class=JSONResponse)
async def list_active_councils():
    """Get list of all councils with active sessions."""
    return {
        "councils": [
            {
                "council_id": council_id,
                "deliberation_count": len(deliberations),
                "last_active": deliberations[-1].timestamp if deliberations else None
            }
            for council_id, deliberations in debugger.council_sessions.items()
        ]
    }


@app.get("/", response_class=HTMLResponse)
async def devui_interface():
    """
    Serve the DevUI frontend.

    Modern React-style interface for visual agent debugging.
    """
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ANTS DevUI - Agent Debugging</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }

            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #0f172a;
                color: #e2e8f0;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }

            .header {
                background: linear-gradient(135deg, #6366f1, #8b5cf6);
                padding: 1rem 2rem;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
            }

            .header h1 {
                font-size: 1.5rem;
                font-weight: 700;
            }

            .header p {
                font-size: 0.875rem;
                opacity: 0.9;
                margin-top: 0.25rem;
            }

            .container {
                display: grid;
                grid-template-columns: 250px 1fr 300px;
                gap: 1rem;
                padding: 1rem;
                height: calc(100vh - 100px);
                overflow: hidden;
            }

            .sidebar {
                background: #1e293b;
                border-radius: 8px;
                padding: 1rem;
                overflow-y: auto;
            }

            .sidebar h2 {
                font-size: 1rem;
                margin-bottom: 1rem;
                color: #6366f1;
            }

            .agent-list {
                list-style: none;
            }

            .agent-item {
                padding: 0.75rem;
                margin-bottom: 0.5rem;
                background: #334155;
                border-radius: 6px;
                cursor: pointer;
                transition: background 0.2s;
            }

            .agent-item:hover {
                background: #475569;
            }

            .agent-item.active {
                background: #6366f1;
            }

            .main-panel {
                background: #1e293b;
                border-radius: 8px;
                padding: 1rem;
                overflow-y: auto;
            }

            .reasoning-chain {
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }

            .reasoning-step {
                background: #334155;
                border-left: 4px solid #6366f1;
                border-radius: 6px;
                padding: 1rem;
                position: relative;
            }

            .reasoning-step.phase-1 { border-left-color: #6366f1; }
            .reasoning-step.phase-2 { border-left-color: #8b5cf6; }
            .reasoning-step.phase-3 { border-left-color: #ec4899; }
            .reasoning-step.phase-4 { border-left-color: #f59e0b; }
            .reasoning-step.phase-5 { border-left-color: #10b981; }
            .reasoning-step.phase-6 { border-left-color: #3b82f6; }

            .step-header {
                display: flex;
                justify-content: space-between;
                margin-bottom: 0.75rem;
            }

            .step-type {
                font-weight: 600;
                text-transform: uppercase;
                font-size: 0.875rem;
            }

            .step-timestamp {
                font-size: 0.75rem;
                color: #94a3b8;
            }

            .step-content {
                font-size: 0.875rem;
                line-height: 1.5;
            }

            .step-metrics {
                display: flex;
                gap: 1rem;
                margin-top: 0.75rem;
                padding-top: 0.75rem;
                border-top: 1px solid #475569;
                font-size: 0.75rem;
                color: #94a3b8;
            }

            .inspector-panel {
                background: #1e293b;
                border-radius: 8px;
                padding: 1rem;
                overflow-y: auto;
            }

            .inspector-panel h2 {
                font-size: 1rem;
                margin-bottom: 1rem;
                color: #ec4899;
            }

            .memory-section, .policy-section {
                background: #334155;
                border-radius: 6px;
                padding: 1rem;
                margin-bottom: 1rem;
            }

            .memory-section h3, .policy-section h3 {
                font-size: 0.875rem;
                margin-bottom: 0.5rem;
                color: #10b981;
            }

            .json-display {
                background: #0f172a;
                border-radius: 4px;
                padding: 0.75rem;
                font-family: 'Courier New', monospace;
                font-size: 0.75rem;
                overflow-x: auto;
            }

            .status-badge {
                display: inline-block;
                padding: 0.25rem 0.75rem;
                border-radius: 12px;
                font-size: 0.75rem;
                font-weight: 600;
            }

            .status-badge.success { background: #10b981; color: white; }
            .status-badge.warning { background: #f59e0b; color: white; }
            .status-badge.error { background: #ef4444; color: white; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔬 ANTS DevUI - Agent Debugging</h1>
            <p>Visual introspection into agent reasoning chains and council deliberations</p>
        </div>

        <div class="container">
            <!-- Left Sidebar: Agent List -->
            <div class="sidebar">
                <h2>Active Agents</h2>
                <ul class="agent-list" id="agent-list">
                    <li class="agent-item">Loading agents...</li>
                </ul>
            </div>

            <!-- Main Panel: Reasoning Chain -->
            <div class="main-panel">
                <h2 style="margin-bottom: 1rem; color: #6366f1;">Reasoning Chain</h2>
                <div class="reasoning-chain" id="reasoning-chain">
                    <div style="text-align: center; color: #94a3b8; padding: 3rem;">
                        Select an agent to view its reasoning chain
                    </div>
                </div>
            </div>

            <!-- Right Panel: Inspector -->
            <div class="inspector-panel">
                <h2>Inspector</h2>

                <div class="memory-section">
                    <h3>Memory State</h3>
                    <div class="json-display" id="memory-display">
                        No step selected
                    </div>
                </div>

                <div class="policy-section">
                    <h3>Policy Evaluation</h3>
                    <div class="json-display" id="policy-display">
                        No step selected
                    </div>
                </div>
            </div>
        </div>

        <script>
            let currentAgent = null;
            let ws = null;

            // Fetch and display active agents
            async function loadAgents() {
                const response = await fetch('/api/agents');
                const data = await response.json();

                const agentList = document.getElementById('agent-list');
                agentList.innerHTML = '';

                if (data.agents.length === 0) {
                    agentList.innerHTML = '<li style="color: #94a3b8;">No active agents</li>';
                    return;
                }

                data.agents.forEach(agent => {
                    const li = document.createElement('li');
                    li.className = 'agent-item';
                    li.textContent = agent.agent_id;
                    li.onclick = () => selectAgent(agent.agent_id);
                    agentList.appendChild(li);
                });
            }

            // Select and watch an agent
            function selectAgent(agentId) {
                currentAgent = agentId;

                // Update UI
                document.querySelectorAll('.agent-item').forEach(item => {
                    item.classList.remove('active');
                    if (item.textContent === agentId) {
                        item.classList.add('active');
                    }
                });

                // Close existing WebSocket
                if (ws) {
                    ws.close();
                }

                // Connect to agent's WebSocket stream
                ws = new WebSocket(`ws://${window.location.host}/ws/agent/${agentId}`);

                ws.onmessage = (event) => {
                    const message = JSON.parse(event.data);

                    if (message.type === 'history') {
                        displayHistory(message.steps);
                    } else if (message.type === 'reasoning_step') {
                        appendReasoningStep(message.step);
                    }
                };
            }

            // Display historical reasoning steps
            function displayHistory(steps) {
                const chain = document.getElementById('reasoning-chain');
                chain.innerHTML = '';

                steps.forEach(step => {
                    chain.appendChild(createStepElement(step));
                });

                // Scroll to bottom
                chain.scrollTop = chain.scrollHeight;
            }

            // Append new reasoning step
            function appendReasoningStep(step) {
                const chain = document.getElementById('reasoning-chain');
                chain.appendChild(createStepElement(step));
                chain.scrollTop = chain.scrollHeight;
            }

            // Create step HTML element
            function createStepElement(step) {
                const div = document.createElement('div');
                div.className = `reasoning-step phase-${step.phase_number}`;

                const timestamp = new Date(step.timestamp_iso).toLocaleTimeString();

                div.innerHTML = `
                    <div class="step-header">
                        <span class="step-type">Phase ${step.phase_number}: ${step.step_type}</span>
                        <span class="step-timestamp">${timestamp}</span>
                    </div>
                    <div class="step-content">
                        <strong>Input:</strong> ${JSON.stringify(step.input_data).substring(0, 100)}...
                        <br><strong>Output:</strong> ${JSON.stringify(step.output_data).substring(0, 100)}...
                    </div>
                    <div class="step-metrics">
                        ${step.token_usage ? `<span>Tokens: ${step.token_usage.total || 'N/A'}</span>` : ''}
                        ${step.latency_ms ? `<span>Latency: ${step.latency_ms.toFixed(0)}ms</span>` : ''}
                        ${step.error ? `<span class="status-badge error">Error</span>` : '<span class="status-badge success">Success</span>'}
                    </div>
                `;

                // Click to inspect
                div.onclick = () => inspectStep(step);

                return div;
            }

            // Inspect step details
            function inspectStep(step) {
                document.getElementById('memory-display').textContent =
                    JSON.stringify(step.memory_snapshot || {}, null, 2);

                document.getElementById('policy-display').textContent =
                    JSON.stringify(step.policy_evaluation || {}, null, 2);
            }

            // Initialize
            loadAgents();
            setInterval(loadAgents, 5000);  // Refresh every 5 seconds
        </script>
    </body>
    </html>
    """


class DevUIServer:
    """DevUI server manager."""

    def __init__(self, host: str = "localhost", port: int = 8090):
        self.host = host
        self.port = port
        self.server = None

    async def start(self):
        """Start DevUI server."""
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        self.server = uvicorn.Server(config)
        await self.server.serve()

    def start_sync(self):
        """Start DevUI server (synchronous)."""
        uvicorn.run(app, host=self.host, port=self.port)


def run_devui(host: str = "localhost", port: int = 8090):
    """
    Run DevUI server.

    Usage:
        python -m src.devtools.devui_server

    Then open: http://localhost:8090
    """
    server = DevUIServer(host=host, port=port)
    print(f"🔬 ANTS DevUI starting at http://{host}:{port}")
    print("   Visual agent debugging interface")
    print("   Press Ctrl+C to stop")
    server.start_sync()


if __name__ == "__main__":
    run_devui()
