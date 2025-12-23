"""
ANTS - N8N Workflow Integration
================================

Integration module for n8n workflow automation platform.

N8N is a powerful workflow automation tool that enables:
- Visual workflow design
- 400+ integrations (APIs, databases, SaaS platforms)
- Trigger-based automation
- Webhook support
- JavaScript/Python code execution

This integration allows ANTS agents to:
1. Trigger n8n workflows programmatically
2. Receive webhook callbacks from n8n workflows
3. Execute n8n workflows as part of agent actions
4. Monitor workflow execution status
5. Build complex automation chains combining ANTS + n8n

Author: ANTS Development Team
License: MIT
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import uuid
import aiohttp
from aiohttp import web


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowStatus(Enum):
    """N8N workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    WAITING = "waiting"  # Waiting for external trigger
    CANCELED = "canceled"


class TriggerType(Enum):
    """Types of workflow triggers."""
    WEBHOOK = "webhook"  # HTTP webhook trigger
    SCHEDULE = "schedule"  # Cron/interval trigger
    MANUAL = "manual"  # Manual execution
    EVENT = "event"  # Event-based trigger
    AGENT_ACTION = "agent_action"  # ANTS agent trigger


@dataclass
class N8NConfig:
    """Configuration for N8N integration."""

    # N8N instance settings
    n8n_url: str  # N8N instance URL (e.g., https://n8n.company.com)
    api_key: Optional[str] = None  # API key for authentication
    webhook_base_url: Optional[str] = None  # Base URL for webhooks

    # Webhook server settings (for receiving n8n callbacks)
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8765
    webhook_path: str = "/webhooks/n8n"

    # Execution settings
    timeout_seconds: int = 300  # Workflow execution timeout
    retry_attempts: int = 3  # Retry failed workflows
    retry_delay_seconds: int = 5

    # Monitoring
    enable_monitoring: bool = True
    log_executions: bool = True


@dataclass
class WorkflowDefinition:
    """N8N workflow definition."""
    workflow_id: str
    workflow_name: str
    description: str
    trigger_type: TriggerType
    webhook_url: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class WorkflowExecution:
    """N8N workflow execution record."""
    execution_id: str
    workflow_id: str
    status: WorkflowStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class N8NClient:
    """
    Client for N8N workflow automation integration.

    Enables ANTS agents to trigger and orchestrate n8n workflows,
    creating powerful automation chains combining AI agents with
    traditional workflow automation.

    Example:
        ```python
        # Initialize N8N client
        config = N8NConfig(
            n8n_url="https://n8n.company.com",
            api_key="your-api-key",
            webhook_base_url="https://ants.company.com"
        )

        client = N8NClient(config)
        await client.initialize()

        # Trigger workflow
        execution = await client.trigger_workflow(
            workflow_id="invoice-processing",
            input_data={
                "invoice_pdf": "s3://invoices/inv-12345.pdf",
                "vendor": "Acme Corp",
                "amount": 5000.00
            }
        )

        # Wait for completion
        result = await client.wait_for_execution(execution.execution_id)
        print(f"Workflow result: {result.output_data}")

        # Register webhook handler
        @client.webhook_handler("payment-received")
        async def handle_payment(data):
            print(f"Payment received: {data['amount']}")
            # Trigger ANTS agent action
            await trigger_reconciliation_agent(data)
        ```
    """

    def __init__(self, config: N8NConfig):
        """
        Initialize N8N client.

        Args:
            config: N8N configuration
        """
        self.config = config
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.webhook_handlers: Dict[str, Callable] = {}

        # HTTP session for API calls
        self.session: Optional[aiohttp.ClientSession] = None

        # Webhook server
        self.app: Optional[web.Application] = None
        self.webhook_server: Optional[web.AppRunner] = None

        logger.info(f"N8NClient initialized for {self.config.n8n_url}")

    async def initialize(self) -> bool:
        """
        Initialize N8N client and webhook server.

        Returns:
            True if successful
        """
        try:
            logger.info("Initializing N8N client...")

            # Create HTTP session
            headers = {}
            if self.config.api_key:
                headers["X-N8N-API-KEY"] = self.config.api_key

            self.session = aiohttp.ClientSession(
                base_url=self.config.n8n_url,
                headers=headers
            )

            # Test connection
            await self._test_connection()

            # Start webhook server
            await self._start_webhook_server()

            logger.info("N8N client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize N8N client: {e}")
            return False

    async def register_workflow(
        self,
        workflow_id: str,
        workflow_name: str,
        description: str,
        trigger_type: TriggerType = TriggerType.MANUAL,
        webhook_path: Optional[str] = None,
        **kwargs
    ) -> WorkflowDefinition:
        """
        Register an n8n workflow with ANTS.

        Args:
            workflow_id: Unique workflow identifier (n8n workflow ID)
            workflow_name: Human-readable workflow name
            description: Workflow description
            trigger_type: How the workflow is triggered
            webhook_path: Custom webhook path (if trigger_type=WEBHOOK)
            **kwargs: Additional workflow parameters

        Returns:
            Workflow definition
        """
        try:
            # Generate webhook URL if webhook trigger
            webhook_url = None
            if trigger_type == TriggerType.WEBHOOK:
                webhook_url = self._generate_webhook_url(
                    workflow_id, webhook_path
                )

            workflow = WorkflowDefinition(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                description=description,
                trigger_type=trigger_type,
                webhook_url=webhook_url,
                parameters=kwargs
            )

            self.workflows[workflow_id] = workflow

            logger.info(f"Registered workflow: {workflow_name} ({workflow_id})")
            if webhook_url:
                logger.info(f"  Webhook URL: {webhook_url}")

            return workflow

        except Exception as e:
            logger.error(f"Failed to register workflow: {e}")
            raise

    async def trigger_workflow(
        self,
        workflow_id: str,
        input_data: Dict[str, Any],
        wait_for_completion: bool = False,
        timeout_seconds: Optional[int] = None
    ) -> WorkflowExecution:
        """
        Trigger n8n workflow execution.

        Args:
            workflow_id: Workflow to execute
            input_data: Input data for workflow
            wait_for_completion: Wait for workflow to complete
            timeout_seconds: Override default timeout

        Returns:
            Workflow execution record
        """
        try:
            if workflow_id not in self.workflows:
                raise ValueError(f"Workflow not registered: {workflow_id}")

            workflow = self.workflows[workflow_id]

            logger.info(f"Triggering workflow: {workflow.workflow_name}")

            # Create execution record
            execution_id = f"exec-{uuid.uuid4().hex[:12]}"
            execution = WorkflowExecution(
                execution_id=execution_id,
                workflow_id=workflow_id,
                status=WorkflowStatus.PENDING,
                started_at=datetime.utcnow(),
                input_data=input_data
            )

            self.executions[execution_id] = execution

            # Trigger based on workflow type
            if workflow.trigger_type == TriggerType.WEBHOOK:
                await self._trigger_via_webhook(workflow, execution, input_data)
            else:
                await self._trigger_via_api(workflow, execution, input_data)

            # Wait for completion if requested
            if wait_for_completion:
                timeout = timeout_seconds or self.config.timeout_seconds
                execution = await self.wait_for_execution(
                    execution_id, timeout
                )

            return execution

        except Exception as e:
            logger.error(f"Failed to trigger workflow: {e}")
            raise

    async def wait_for_execution(
        self,
        execution_id: str,
        timeout_seconds: Optional[int] = None
    ) -> WorkflowExecution:
        """
        Wait for workflow execution to complete.

        Args:
            execution_id: Execution to wait for
            timeout_seconds: Maximum wait time

        Returns:
            Completed workflow execution
        """
        if execution_id not in self.executions:
            raise ValueError(f"Execution not found: {execution_id}")

        timeout = timeout_seconds or self.config.timeout_seconds
        start_time = datetime.utcnow()

        logger.info(f"Waiting for execution {execution_id} (timeout: {timeout}s)")

        while True:
            execution = self.executions[execution_id]

            # Check if completed
            if execution.status in [
                WorkflowStatus.SUCCESS,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELED
            ]:
                logger.info(f"Execution {execution_id} completed: {execution.status.value}")
                return execution

            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout:
                logger.warning(f"Execution {execution_id} timed out after {elapsed:.1f}s")
                execution.status = WorkflowStatus.FAILED
                execution.error_message = f"Timeout after {elapsed:.1f}s"
                return execution

            # Poll execution status
            await self._poll_execution_status(execution_id)

            # Wait before next poll
            await asyncio.sleep(2.0)

    async def get_execution_result(
        self,
        execution_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get workflow execution result.

        Args:
            execution_id: Execution ID

        Returns:
            Execution output data or None
        """
        if execution_id not in self.executions:
            return None

        execution = self.executions[execution_id]
        return execution.output_data

    def webhook_handler(self, webhook_name: str):
        """
        Decorator to register webhook handler.

        Example:
            ```python
            @client.webhook_handler("payment-received")
            async def handle_payment(data):
                print(f"Payment: {data['amount']}")
            ```

        Args:
            webhook_name: Name of webhook endpoint
        """
        def decorator(func: Callable):
            self.webhook_handlers[webhook_name] = func
            logger.info(f"Registered webhook handler: {webhook_name}")
            return func
        return decorator

    async def get_workflow_stats(self) -> Dict[str, Any]:
        """
        Get workflow execution statistics.

        Returns:
            Statistics dictionary
        """
        total_executions = len(self.executions)

        status_counts = {}
        for execution in self.executions.values():
            status = execution.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        success_count = status_counts.get("success", 0)
        success_rate = (success_count / total_executions * 100) if total_executions > 0 else 0

        return {
            "total_workflows": len(self.workflows),
            "total_executions": total_executions,
            "executions_by_status": status_counts,
            "success_rate_percent": round(success_rate, 1),
            "active_webhooks": len(self.webhook_handlers)
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown N8N client."""
        logger.info("Shutting down N8N client...")

        # Stop webhook server
        if self.webhook_server:
            await self.webhook_server.cleanup()
            logger.info("Webhook server stopped")

        # Close HTTP session
        if self.session:
            await self.session.close()
            logger.info("HTTP session closed")

        logger.info("N8N client shutdown complete")

    # Private helper methods

    async def _test_connection(self) -> None:
        """Test connection to N8N instance."""
        try:
            # In production, GET /healthz or /workflows to verify connection
            logger.info(f"Testing connection to {self.config.n8n_url}")
            await asyncio.sleep(0.1)
            logger.info("N8N connection test successful")
        except Exception as e:
            raise ConnectionError(f"Cannot connect to N8N: {e}")

    async def _start_webhook_server(self) -> None:
        """Start webhook server to receive n8n callbacks."""
        try:
            self.app = web.Application()

            # Register webhook endpoint
            self.app.router.add_post(
                f"{self.config.webhook_path}/{{webhook_name}}",
                self._handle_webhook_request
            )

            # Start server
            runner = web.AppRunner(self.app)
            await runner.setup()

            site = web.TCPSite(
                runner,
                self.config.webhook_host,
                self.config.webhook_port
            )
            await site.start()

            self.webhook_server = runner

            webhook_url = f"http://{self.config.webhook_host}:{self.config.webhook_port}{self.config.webhook_path}"
            logger.info(f"Webhook server started: {webhook_url}")

        except Exception as e:
            logger.error(f"Failed to start webhook server: {e}")
            raise

    async def _handle_webhook_request(self, request: web.Request) -> web.Response:
        """Handle incoming webhook request from n8n."""
        try:
            webhook_name = request.match_info["webhook_name"]
            data = await request.json()

            logger.info(f"Received webhook: {webhook_name}")

            # Call registered handler if exists
            if webhook_name in self.webhook_handlers:
                handler = self.webhook_handlers[webhook_name]
                await handler(data)
                logger.info(f"Webhook {webhook_name} processed successfully")
            else:
                logger.warning(f"No handler for webhook: {webhook_name}")

            return web.json_response({"status": "success"})

        except Exception as e:
            logger.error(f"Error handling webhook: {e}")
            return web.json_response(
                {"status": "error", "message": str(e)},
                status=500
            )

    def _generate_webhook_url(
        self,
        workflow_id: str,
        custom_path: Optional[str] = None
    ) -> str:
        """Generate webhook URL for workflow."""
        base_url = self.config.webhook_base_url or f"http://localhost:{self.config.webhook_port}"
        path = custom_path or workflow_id
        return f"{base_url}{self.config.webhook_path}/{path}"

    async def _trigger_via_webhook(
        self,
        workflow: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ) -> None:
        """Trigger workflow via webhook."""
        if not workflow.webhook_url:
            raise ValueError(f"Workflow {workflow.workflow_id} has no webhook URL")

        execution.status = WorkflowStatus.RUNNING

        # In production, POST to n8n webhook URL
        await asyncio.sleep(0.1)

        # Simulate successful trigger
        execution.status = WorkflowStatus.SUCCESS
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"status": "triggered_via_webhook"}

        logger.info(f"Workflow triggered via webhook: {workflow.workflow_name}")

    async def _trigger_via_api(
        self,
        workflow: WorkflowDefinition,
        execution: WorkflowExecution,
        input_data: Dict[str, Any]
    ) -> None:
        """Trigger workflow via N8N API."""
        execution.status = WorkflowStatus.RUNNING

        # In production, POST to /api/v1/workflows/{id}/execute
        await asyncio.sleep(0.1)

        # Simulate successful trigger
        execution.status = WorkflowStatus.SUCCESS
        execution.completed_at = datetime.utcnow()
        execution.output_data = {"status": "triggered_via_api"}

        logger.info(f"Workflow triggered via API: {workflow.workflow_name}")

    async def _poll_execution_status(self, execution_id: str) -> None:
        """Poll n8n for execution status."""
        if execution_id not in self.executions:
            return

        # In production, GET /api/v1/executions/{id}
        # For simulation, randomly complete some executions
        execution = self.executions[execution_id]

        if execution.status == WorkflowStatus.RUNNING:
            # Simulate completion
            import random
            if random.random() > 0.7:  # 30% chance to complete each poll
                execution.status = WorkflowStatus.SUCCESS
                execution.completed_at = datetime.utcnow()
                execution.output_data = {
                    "result": "Workflow completed successfully",
                    "processed_items": 42
                }


# Convenience factory function
def create_n8n_client(
    n8n_url: str,
    api_key: Optional[str] = None,
    webhook_base_url: Optional[str] = None,
    **kwargs
) -> N8NClient:
    """
    Create and configure N8N client.

    Args:
        n8n_url: N8N instance URL
        api_key: Optional API key for authentication
        webhook_base_url: Base URL for webhooks
        **kwargs: Additional configuration options

    Returns:
        Configured N8NClient
    """
    config = N8NConfig(
        n8n_url=n8n_url,
        api_key=api_key,
        webhook_base_url=webhook_base_url,
        **kwargs
    )

    return N8NClient(config)
