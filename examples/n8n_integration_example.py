"""
ANTS - N8N Workflow Integration Examples
=========================================

Comprehensive examples demonstrating ANTS integration with n8n workflow
automation platform for building complex automation chains.

Scenarios:
1. Basic workflow trigger from ANTS agent
2. Invoice processing automation (ANTS + n8n)
3. Webhook-based event handling
4. Multi-step automation chain
5. Error handling and retries
6. Parallel workflow execution
7. Workflow analytics and monitoring

Author: ANTS Development Team
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from src.integrations.n8n import (
    N8NClient,
    N8NConfig,
    TriggerType,
    WorkflowStatus,
    create_n8n_client
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def scenario_1_basic_workflow_trigger():
    """
    Scenario 1: Basic Workflow Trigger from ANTS Agent

    Demonstrates how an ANTS agent can trigger a simple n8n workflow
    for data processing.
    """
    print("\n" + "="*80)
    print("SCENARIO 1: Basic Workflow Trigger")
    print("="*80 + "\n")

    # Create N8N client
    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key",
        webhook_base_url="https://ants.company.com"
    )

    await client.initialize()

    # Register workflow
    print("1. Registering n8n workflow...")
    workflow = await client.register_workflow(
        workflow_id="data-processing",
        workflow_name="Customer Data Processing",
        description="Process and validate customer data",
        trigger_type=TriggerType.MANUAL
    )
    print(f"   ✅ Registered workflow: {workflow.workflow_name}")

    # Trigger workflow with input data
    print("\n2. Triggering workflow from ANTS agent...")
    execution = await client.trigger_workflow(
        workflow_id="data-processing",
        input_data={
            "customer_id": "cust-12345",
            "email": "customer@example.com",
            "action": "validate_and_enrich"
        },
        wait_for_completion=True
    )

    print(f"   ✅ Workflow triggered: {execution.execution_id}")
    print(f"   - Status: {execution.status.value}")
    print(f"   - Duration: {(execution.completed_at - execution.started_at).total_seconds():.2f}s")

    # Get result
    result = await client.get_execution_result(execution.execution_id)
    print(f"\n3. Workflow result:")
    print(f"   {result}")

    await client.shutdown()
    print("\n✅ Scenario 1 complete\n")


async def scenario_2_invoice_processing_automation():
    """
    Scenario 2: Invoice Processing Automation (ANTS + n8n)

    Demonstrates end-to-end invoice processing combining ANTS AI agents
    with n8n automation for data extraction, validation, and ERP integration.

    Flow:
    1. ANTS agent extracts data from invoice PDF
    2. ANTS triggers n8n workflow for validation
    3. n8n validates data against business rules
    4. n8n posts validated invoice to ERP system
    5. n8n sends confirmation email
    6. n8n callbacks to ANTS for reconciliation
    """
    print("\n" + "="*80)
    print("SCENARIO 2: Invoice Processing Automation")
    print("="*80 + "\n")

    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key"
    )

    await client.initialize()

    # Register invoice processing workflow
    print("1. Setting up invoice processing workflow...")
    workflow = await client.register_workflow(
        workflow_id="invoice-processing",
        workflow_name="End-to-End Invoice Processing",
        description="Validate, post to ERP, send confirmation",
        trigger_type=TriggerType.MANUAL,
        tags=["finance", "automation", "erp"]
    )
    print(f"   ✅ Workflow ready: {workflow.workflow_name}")

    # Simulate ANTS agent extracting invoice data
    print("\n2. ANTS agent extracting invoice data from PDF...")
    invoice_data = {
        "invoice_id": "INV-2025-12345",
        "vendor": "Acme Corp",
        "amount": 5000.00,
        "currency": "USD",
        "due_date": "2026-01-15",
        "line_items": [
            {"description": "Consulting Services", "amount": 3500.00},
            {"description": "Software License", "amount": 1500.00}
        ],
        "pdf_url": "s3://invoices/INV-2025-12345.pdf"
    }
    print(f"   ✅ Extracted invoice: {invoice_data['invoice_id']}")
    print(f"   - Vendor: {invoice_data['vendor']}")
    print(f"   - Amount: ${invoice_data['amount']:,.2f}")

    # Trigger n8n workflow for validation and ERP posting
    print("\n3. Triggering n8n workflow for validation and ERP posting...")
    execution = await client.trigger_workflow(
        workflow_id="invoice-processing",
        input_data=invoice_data,
        wait_for_completion=True,
        timeout_seconds=60
    )

    print(f"   ✅ Workflow completed: {execution.status.value}")

    # Check result
    if execution.status == WorkflowStatus.SUCCESS:
        result = execution.output_data
        print(f"\n4. Invoice processing results:")
        print(f"   ✅ Validation: Passed")
        print(f"   ✅ Posted to ERP: Invoice #{invoice_data['invoice_id']}")
        print(f"   ✅ Confirmation email sent to vendor")
        print(f"   ✅ Ready for ANTS reconciliation agent")
    else:
        print(f"\n4. Invoice processing failed:")
        print(f"   ❌ Error: {execution.error_message}")

    await client.shutdown()
    print("\n✅ Scenario 2 complete\n")


async def scenario_3_webhook_event_handling():
    """
    Scenario 3: Webhook-Based Event Handling

    Demonstrates bidirectional integration where n8n workflows send
    webhook callbacks to ANTS agents when events occur.
    """
    print("\n" + "="*80)
    print("SCENARIO 3: Webhook-Based Event Handling")
    print("="*80 + "\n")

    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key",
        webhook_port=8765
    )

    await client.initialize()

    # Register webhook handlers
    print("1. Registering webhook handlers...")

    @client.webhook_handler("payment-received")
    async def handle_payment_received(data: Dict[str, Any]):
        """Handle payment received event from n8n."""
        print(f"\n   📨 Webhook received: payment-received")
        print(f"   - Payment ID: {data.get('payment_id')}")
        print(f"   - Amount: ${data.get('amount'):,.2f}")
        print(f"   - Invoice: {data.get('invoice_id')}")
        print(f"   ✅ Triggering ANTS reconciliation agent...")

    @client.webhook_handler("invoice-rejected")
    async def handle_invoice_rejected(data: Dict[str, Any]):
        """Handle invoice rejection from n8n."""
        print(f"\n   📨 Webhook received: invoice-rejected")
        print(f"   - Invoice ID: {data.get('invoice_id')}")
        print(f"   - Reason: {data.get('rejection_reason')}")
        print(f"   ✅ Triggering ANTS review agent...")

    print("   ✅ Webhook handlers registered")
    print(f"   - payment-received: http://localhost:8765/webhooks/n8n/payment-received")
    print(f"   - invoice-rejected: http://localhost:8765/webhooks/n8n/invoice-rejected")

    # Simulate webhooks from n8n (in production, n8n would call these)
    print("\n2. Simulating webhook events from n8n...")

    # Simulate payment received
    await handle_payment_received({
        "payment_id": "PAY-67890",
        "amount": 5000.00,
        "invoice_id": "INV-2025-12345",
        "payment_method": "wire_transfer"
    })

    # Simulate invoice rejection
    await asyncio.sleep(1)
    await handle_invoice_rejected({
        "invoice_id": "INV-2025-54321",
        "rejection_reason": "Amount exceeds approval threshold",
        "requires_approval_from": "CFO"
    })

    print("\n3. Webhook integration active and processing events...")

    await client.shutdown()
    print("\n✅ Scenario 3 complete\n")


async def scenario_4_multi_step_automation_chain():
    """
    Scenario 4: Multi-Step Automation Chain

    Demonstrates complex automation combining multiple n8n workflows
    orchestrated by ANTS agents.

    Chain:
    1. ANTS receives customer order
    2. Trigger n8n inventory check workflow
    3. If in stock -> Trigger n8n payment processing workflow
    4. If payment successful -> Trigger n8n shipping workflow
    5. ANTS agent handles exceptions at each step
    """
    print("\n" + "="*80)
    print("SCENARIO 4: Multi-Step Automation Chain")
    print("="*80 + "\n")

    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key"
    )

    await client.initialize()

    # Register workflows
    print("1. Registering automation workflows...")
    workflows = [
        ("inventory-check", "Inventory Availability Check"),
        ("payment-processing", "Payment Authorization"),
        ("shipping-fulfillment", "Shipping and Fulfillment")
    ]

    for wf_id, wf_name in workflows:
        await client.register_workflow(
            workflow_id=wf_id,
            workflow_name=wf_name,
            description=f"Automated {wf_name.lower()}",
            trigger_type=TriggerType.MANUAL
        )
        print(f"   ✅ {wf_name}")

    # Process order through automation chain
    print("\n2. Processing customer order through automation chain...")

    order = {
        "order_id": "ORD-2025-789",
        "customer_id": "cust-456",
        "items": [
            {"sku": "PROD-001", "quantity": 2, "price": 49.99},
            {"sku": "PROD-002", "quantity": 1, "price": 29.99}
        ],
        "total": 129.97
    }

    print(f"\n   Order: {order['order_id']}")
    print(f"   - Items: {len(order['items'])}")
    print(f"   - Total: ${order['total']:,.2f}")

    # Step 1: Check inventory
    print("\n3. Step 1: Checking inventory availability...")
    inventory_exec = await client.trigger_workflow(
        workflow_id="inventory-check",
        input_data={"order": order},
        wait_for_completion=True
    )

    if inventory_exec.status == WorkflowStatus.SUCCESS:
        print("   ✅ All items in stock")

        # Step 2: Process payment
        print("\n4. Step 2: Processing payment...")
        payment_exec = await client.trigger_workflow(
            workflow_id="payment-processing",
            input_data={
                "order_id": order["order_id"],
                "amount": order["total"],
                "payment_method": "credit_card"
            },
            wait_for_completion=True
        )

        if payment_exec.status == WorkflowStatus.SUCCESS:
            print("   ✅ Payment authorized")

            # Step 3: Fulfill shipping
            print("\n5. Step 3: Initiating shipping...")
            shipping_exec = await client.trigger_workflow(
                workflow_id="shipping-fulfillment",
                input_data={"order": order},
                wait_for_completion=True
            )

            if shipping_exec.status == WorkflowStatus.SUCCESS:
                print("   ✅ Shipping initiated")
                print(f"\n✅ Order {order['order_id']} processed successfully!")
        else:
            print("   ❌ Payment failed - ANTS agent handling refund...")
    else:
        print("   ❌ Items out of stock - ANTS agent notifying customer...")

    await client.shutdown()
    print("\n✅ Scenario 4 complete\n")


async def scenario_5_error_handling_and_retries():
    """
    Scenario 5: Error Handling and Retries

    Demonstrates robust error handling when n8n workflows fail,
    with automatic retries and ANTS agent fallback.
    """
    print("\n" + "="*80)
    print("SCENARIO 5: Error Handling and Retries")
    print("="*80 + "\n")

    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key",
        retry_attempts=3,
        retry_delay_seconds=2
    )

    await client.initialize()

    # Register potentially failing workflow
    print("1. Registering workflow with retry configuration...")
    workflow = await client.register_workflow(
        workflow_id="external-api-call",
        workflow_name="External API Integration",
        description="Calls external API (may fail)",
        trigger_type=TriggerType.MANUAL
    )
    print(f"   ✅ Workflow: {workflow.workflow_name}")
    print(f"   - Retry attempts: {client.config.retry_attempts}")
    print(f"   - Retry delay: {client.config.retry_delay_seconds}s")

    # Trigger workflow
    print("\n2. Triggering workflow (simulating potential failure)...")
    execution = await client.trigger_workflow(
        workflow_id="external-api-call",
        input_data={"api_endpoint": "https://api.example.com/data"},
        wait_for_completion=True
    )

    # Check result and handle errors
    print(f"\n3. Workflow result: {execution.status.value}")

    if execution.status == WorkflowStatus.FAILED:
        print(f"   ❌ Workflow failed: {execution.error_message}")
        print(f"   🔄 ANTS agent activating fallback procedure...")
        print(f"   ✅ Fallback: Using cached data instead of API call")
    else:
        print(f"   ✅ Workflow succeeded")

    await client.shutdown()
    print("\n✅ Scenario 5 complete\n")


async def scenario_6_parallel_workflow_execution():
    """
    Scenario 6: Parallel Workflow Execution

    Demonstrates executing multiple n8n workflows in parallel for
    improved performance.
    """
    print("\n" + "="*80)
    print("SCENARIO 6: Parallel Workflow Execution")
    print("="*80 + "\n")

    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key"
    )

    await client.initialize()

    # Register workflows
    print("1. Registering parallel workflows...")
    workflows = [
        ("email-notification", "Email Notification Service"),
        ("slack-notification", "Slack Notification Service"),
        ("sms-notification", "SMS Notification Service"),
        ("webhook-notification", "Webhook Notification Service")
    ]

    for wf_id, wf_name in workflows:
        await client.register_workflow(
            workflow_id=wf_id,
            workflow_name=wf_name,
            description=f"Send notifications via {wf_name.split()[0]}",
            trigger_type=TriggerType.MANUAL
        )
        print(f"   ✅ {wf_name}")

    # Execute all workflows in parallel
    print("\n2. Triggering all notification workflows in parallel...")

    notification_data = {
        "event": "order_shipped",
        "order_id": "ORD-2025-999",
        "customer": "John Doe",
        "message": "Your order has been shipped!"
    }

    # Create parallel tasks
    tasks = [
        client.trigger_workflow(wf_id, notification_data, wait_for_completion=True)
        for wf_id, _ in workflows
    ]

    # Execute in parallel
    start_time = datetime.utcnow()
    results = await asyncio.gather(*tasks)
    elapsed = (datetime.utcnow() - start_time).total_seconds()

    # Check results
    print(f"\n3. Parallel execution complete in {elapsed:.2f}s:")
    for (wf_id, wf_name), execution in zip(workflows, results):
        status_icon = "✅" if execution.status == WorkflowStatus.SUCCESS else "❌"
        print(f"   {status_icon} {wf_name}: {execution.status.value}")

    successful = sum(1 for r in results if r.status == WorkflowStatus.SUCCESS)
    print(f"\n   Success rate: {successful}/{len(workflows)} ({successful/len(workflows)*100:.0f}%)")

    await client.shutdown()
    print("\n✅ Scenario 6 complete\n")


async def scenario_7_workflow_analytics():
    """
    Scenario 7: Workflow Analytics and Monitoring

    Demonstrates collecting and analyzing workflow execution metrics.
    """
    print("\n" + "="*80)
    print("SCENARIO 7: Workflow Analytics and Monitoring")
    print("="*80 + "\n")

    client = create_n8n_client(
        n8n_url="https://n8n.company.com",
        api_key="your-n8n-api-key",
        enable_monitoring=True,
        log_executions=True
    )

    await client.initialize()

    # Create and execute multiple workflows
    print("1. Creating test workflows and executions...")

    workflows = [
        "data-processing",
        "report-generation",
        "backup-automation",
        "cleanup-tasks"
    ]

    for wf_id in workflows:
        await client.register_workflow(
            workflow_id=wf_id,
            workflow_name=wf_id.replace("-", " ").title(),
            description=f"Automated {wf_id}",
            trigger_type=TriggerType.MANUAL
        )

        # Execute each workflow multiple times
        for i in range(3):
            await client.trigger_workflow(
                workflow_id=wf_id,
                input_data={"run": i+1},
                wait_for_completion=True
            )

    print(f"   ✅ Created {len(workflows)} workflows")

    # Get analytics
    print("\n2. Analyzing workflow execution metrics...")
    stats = await client.get_workflow_stats()

    print(f"\n   📊 Workflow Analytics:")
    print(f"   - Total workflows: {stats['total_workflows']}")
    print(f"   - Total executions: {stats['total_executions']}")
    print(f"   - Success rate: {stats['success_rate_percent']}%")
    print(f"   - Active webhooks: {stats['active_webhooks']}")

    print(f"\n   📊 Executions by status:")
    for status, count in stats['executions_by_status'].items():
        percentage = (count / stats['total_executions'] * 100)
        print(f"   - {status}: {count} ({percentage:.1f}%)")

    # Calculate average execution time
    total_time = 0
    completed = 0
    for execution in client.executions.values():
        if execution.completed_at:
            duration = (execution.completed_at - execution.started_at).total_seconds()
            total_time += duration
            completed += 1

    if completed > 0:
        avg_time = total_time / completed
        print(f"\n   📊 Performance metrics:")
        print(f"   - Average execution time: {avg_time:.2f}s")
        print(f"   - Total execution time: {total_time:.2f}s")

    await client.shutdown()
    print("\n✅ Scenario 7 complete\n")


async def main():
    """Run all N8N integration scenarios."""
    print("\n" + "="*80)
    print("ANTS - N8N WORKFLOW INTEGRATION EXAMPLES")
    print("="*80)
    print("\nDemonstrating ANTS integration with n8n for building")
    print("complex automation chains combining AI agents with workflows.\n")

    scenarios = [
        ("Basic Workflow Trigger", scenario_1_basic_workflow_trigger),
        ("Invoice Processing Automation", scenario_2_invoice_processing_automation),
        ("Webhook Event Handling", scenario_3_webhook_event_handling),
        ("Multi-Step Automation Chain", scenario_4_multi_step_automation_chain),
        ("Error Handling and Retries", scenario_5_error_handling_and_retries),
        ("Parallel Workflow Execution", scenario_6_parallel_workflow_execution),
        ("Workflow Analytics", scenario_7_workflow_analytics)
    ]

    for name, scenario_func in scenarios:
        try:
            await scenario_func()
        except Exception as e:
            logger.error(f"Error in {name}: {e}")
            print(f"❌ Scenario failed: {e}\n")

    print("\n" + "="*80)
    print("ALL SCENARIOS COMPLETE")
    print("="*80)
    print("\nN8N integration enables ANTS agents to:")
    print("  ✅ Trigger complex workflows programmatically")
    print("  ✅ Receive webhook callbacks from workflows")
    print("  ✅ Build multi-step automation chains")
    print("  ✅ Integrate with 400+ services via n8n")
    print("  ✅ Handle errors and implement retries")
    print("  ✅ Execute workflows in parallel")
    print("  ✅ Monitor workflow analytics")
    print("\nCombining ANTS AI agents with n8n workflow automation")
    print("creates powerful hybrid automation systems.\n")


if __name__ == "__main__":
    asyncio.run(main())
