"""
ANTS - Azure Agent 365 Integration Examples
============================================

Comprehensive examples demonstrating ANTS integration with Azure Agent 365
for agent collaboration, conversation orchestration, and M365 Copilot integration.

Scenarios:
1. Register ANTS agent with Agent 365
2. Human-in-the-loop conversation
3. Multi-agent collaboration
4. Microsoft Graph plugin usage
5. M365 Copilot integration
6. Memory synchronization
7. Conversation analytics

Author: ANTS Development Team
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from src.integrations.azure_agent_365 import (
    Agent365Client,
    Agent365Config,
    ConversationType,
    create_agent_365_client
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def scenario_1_register_agent():
    """
    Scenario 1: Register ANTS Agent with Azure Agent 365

    Demonstrates how to register an ANTS agent in the Agent 365 ecosystem,
    making it discoverable and available for collaboration with other agents
    and Microsoft 365 Copilot.
    """
    print("\n" + "="*80)
    print("SCENARIO 1: Register ANTS Agent with Azure Agent 365")
    print("="*80 + "\n")

    # Create Agent 365 client for a Finance agent
    client = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Finance Reconciliation Agent",
        agent_description="Automated financial reconciliation, invoice processing, and fraud detection",
        capabilities=[
            "invoice_processing",
            "payment_reconciliation",
            "fraud_detection",
            "compliance_reporting",
            "anomaly_detection"
        ],
        enabled_plugins=[
            "microsoft_graph",  # Access to M365 data
            "dataverse",        # Business data platform
            "ants_native"       # ANTS-specific tools
        ]
    )

    # Initialize connection
    print("1. Initializing connection to Azure Agent 365...")
    success = await client.initialize()
    if not success:
        print("   ❌ Failed to initialize connection")
        return

    print("   ✅ Connected to Agent 365")

    # Register agent
    print("\n2. Registering ANTS agent...")
    registration = await client.register_agent()

    print(f"\n   ✅ Agent registered successfully!")
    print(f"   - Agent ID: {registration['agent_id']}")
    print(f"   - Status: {registration['status']}")
    print(f"   - Capabilities verified: {', '.join(registration['capabilities_verified'])}")
    print(f"   - Plugins enabled: {', '.join(registration['plugins_enabled'])}")
    print(f"   - Registration token: {registration['registration_token'][:20]}...")

    # Get stats
    stats = await client.get_conversation_stats()
    print(f"\n3. Agent status:")
    print(f"   - Status: {stats['agent_status']}")
    print(f"   - Active plugins: {stats['active_plugins']}")

    # Shutdown
    await client.shutdown()
    print("\n✅ Scenario 1 complete\n")


async def scenario_2_human_in_loop_conversation():
    """
    Scenario 2: Human-in-the-Loop Conversation

    Demonstrates a conversation where an ANTS agent collaborates with a human
    user through the Agent 365 platform, processing financial queries with
    human oversight.
    """
    print("\n" + "="*80)
    print("SCENARIO 2: Human-in-the-Loop Conversation")
    print("="*80 + "\n")

    # Create client
    client = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Finance Agent",
        agent_description="Financial analysis and reporting",
        capabilities=["financial_analysis", "reporting"],
        enabled_plugins=["microsoft_graph", "dataverse"]
    )

    await client.initialize()
    await client.register_agent()

    print("1. Starting human-in-the-loop conversation...")

    # Start conversation
    conversation = await client.start_conversation(
        conversation_type=ConversationType.HUMAN_IN_LOOP,
        initial_message="I need help analyzing Q4 revenue discrepancies",
        participants=["user-12345", client.config.agent_id]
    )

    print(f"   ✅ Conversation started: {conversation.conversation_id}")
    print(f"   - Type: {conversation.conversation_type.value}")
    print(f"   - Participants: {len(conversation.participants)}")

    # Simulate agent processing and responding
    print("\n2. Processing user request...")

    # Agent analyzes and responds
    response_1 = await client.send_message(
        conversation_id=conversation.conversation_id,
        content="I'll analyze the Q4 revenue data. Let me access your financial records...",
        metadata={"action": "data_access", "source": "microsoft_graph"}
    )
    print(f"   ✅ Agent response sent: {response_1.content[:60]}...")

    # Invoke Microsoft Graph plugin to access data
    print("\n3. Accessing financial data via Microsoft Graph plugin...")
    graph_result = await client.invoke_plugin(
        plugin_id="plugin-microsoft_graph",
        operation="get_financial_records",
        parameters={
            "period": "Q4_2025",
            "data_types": ["revenue", "expenses", "transactions"]
        }
    )
    print(f"   ✅ Data retrieved: {graph_result['status']}")

    # Send analysis results
    response_2 = await client.send_message(
        conversation_id=conversation.conversation_id,
        content="I found 3 discrepancies totaling $45,230. The main issue is duplicate invoice entries in November. Would you like me to generate a detailed report?",
        attachments=[
            {
                "type": "analysis_summary",
                "data": {
                    "discrepancies_found": 3,
                    "total_amount": 45230,
                    "primary_issue": "duplicate_invoices"
                }
            }
        ]
    )
    print(f"\n4. Analysis complete:")
    print(f"   ✅ {response_2.content}")

    # Get conversation stats
    stats = await client.get_conversation_stats()
    print(f"\n5. Conversation statistics:")
    print(f"   - Total conversations: {stats['total_conversations']}")
    print(f"   - Total messages: {stats['total_messages']}")

    await client.shutdown()
    print("\n✅ Scenario 2 complete\n")


async def scenario_3_multi_agent_collaboration():
    """
    Scenario 3: Multi-Agent Collaboration

    Demonstrates multiple ANTS agents collaborating on a complex task
    through Agent 365, with each agent contributing specialized expertise.
    """
    print("\n" + "="*80)
    print("SCENARIO 3: Multi-Agent Collaboration")
    print("="*80 + "\n")

    # Create Finance agent
    finance_agent = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Finance Agent",
        agent_description="Financial analysis",
        capabilities=["financial_analysis", "reporting"],
        enabled_plugins=["dataverse"]
    )

    # Create Security agent
    security_agent = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Security Agent",
        agent_description="Fraud detection and compliance",
        capabilities=["fraud_detection", "compliance_check"],
        enabled_plugins=["dataverse"]
    )

    # Initialize both agents
    print("1. Initializing agents...")
    await finance_agent.initialize()
    await finance_agent.register_agent()
    print("   ✅ Finance agent ready")

    await security_agent.initialize()
    await security_agent.register_agent()
    print("   ✅ Security agent ready")

    # Start collaborative conversation
    print("\n2. Starting collaborative conversation...")
    conversation = await finance_agent.start_conversation(
        conversation_type=ConversationType.COLLABORATIVE,
        initial_message="Need to investigate suspicious transaction pattern in Q4",
        participants=[
            finance_agent.config.agent_id,
            security_agent.config.agent_id,
            "user-supervisor"
        ]
    )
    print(f"   ✅ Collaborative session: {conversation.conversation_id}")

    # Finance agent shares findings
    print("\n3. Finance agent analyzing transactions...")
    await finance_agent.send_message(
        conversation_id=conversation.conversation_id,
        content="I've identified 47 transactions with unusual patterns. Total value: $234,500. Flagging for security review."
    )
    print("   ✅ Finance agent shared analysis")

    # Security agent performs fraud check
    print("\n4. Security agent performing fraud analysis...")

    # Use conversation context from security agent's perspective
    # (In production, Agent 365 would sync this automatically)
    security_agent.active_conversations[conversation.conversation_id] = conversation

    await security_agent.send_message(
        conversation_id=conversation.conversation_id,
        content="Fraud analysis complete. 12 transactions flagged as high-risk. Patterns match known invoice fraud scheme. Recommend immediate review and account freeze."
    )
    print("   ✅ Security agent completed fraud check")

    # Get final stats
    stats = await finance_agent.get_conversation_stats()
    print(f"\n5. Collaboration results:")
    print(f"   - Total agents: 2")
    print(f"   - Messages exchanged: {stats['total_messages']}")
    print(f"   - Status: Investigation complete, awaiting supervisor action")

    # Shutdown both agents
    await finance_agent.shutdown()
    await security_agent.shutdown()
    print("\n✅ Scenario 3 complete\n")


async def scenario_4_microsoft_graph_integration():
    """
    Scenario 4: Microsoft Graph Plugin Usage

    Demonstrates using the Microsoft Graph plugin to access M365 data
    (emails, calendar, files, etc.) through Agent 365.
    """
    print("\n" + "="*80)
    print("SCENARIO 4: Microsoft Graph Plugin Usage")
    print("="*80 + "\n")

    client = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Data Integration Agent",
        agent_description="Integrates data from Microsoft 365",
        capabilities=["data_integration", "email_processing"],
        enabled_plugins=["microsoft_graph"]
    )

    await client.initialize()
    await client.register_agent()

    print("1. Accessing Microsoft Graph API...")

    # Get user emails
    print("\n2. Retrieving emails with invoices...")
    email_result = await client.invoke_plugin(
        plugin_id="plugin-microsoft_graph",
        operation="list_messages",
        parameters={
            "filter": "hasAttachments eq true and subject contains 'Invoice'",
            "top": 10,
            "orderBy": "receivedDateTime desc"
        }
    )
    print(f"   ✅ {email_result['status']}: {email_result['result']}")

    # Access SharePoint files
    print("\n3. Accessing financial reports from SharePoint...")
    files_result = await client.invoke_plugin(
        plugin_id="plugin-microsoft_graph",
        operation="list_drive_items",
        parameters={
            "drive_id": "finance-reports",
            "path": "/Q4_2025/",
            "file_type": "xlsx"
        }
    )
    print(f"   ✅ {files_result['status']}: {files_result['result']}")

    # Get calendar events
    print("\n4. Checking calendar for financial review meetings...")
    calendar_result = await client.invoke_plugin(
        plugin_id="plugin-microsoft_graph",
        operation="list_events",
        parameters={
            "filter": "subject contains 'Financial Review'",
            "start_date": "2025-12-01",
            "end_date": "2025-12-31"
        }
    )
    print(f"   ✅ {calendar_result['status']}: {calendar_result['result']}")

    await client.shutdown()
    print("\n✅ Scenario 4 complete\n")


async def scenario_5_copilot_integration():
    """
    Scenario 5: Microsoft 365 Copilot Integration

    Demonstrates ANTS agents collaborating with Microsoft 365 Copilot
    (Excel Copilot, Teams Copilot, etc.) for enhanced productivity.
    """
    print("\n" + "="*80)
    print("SCENARIO 5: Microsoft 365 Copilot Integration")
    print("="*80 + "\n")

    client = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Report Generator",
        agent_description="Generates financial reports",
        capabilities=["report_generation", "data_visualization"],
        enabled_plugins=["microsoft_graph"],
        enable_copilot_integration=True
    )

    await client.initialize()
    await client.register_agent()

    # Collaborate with Excel Copilot
    print("1. Collaborating with Excel Copilot for report generation...")
    excel_response = await client.collaborate_with_copilot(
        copilot_type="excel",
        request={
            "action": "create_financial_report",
            "data_source": "Q4_revenue_data.xlsx",
            "report_type": "executive_summary",
            "include_charts": True,
            "include_pivot_tables": True
        }
    )
    print(f"   ✅ Excel Copilot: {excel_response['result']}")

    # Collaborate with Teams Copilot
    print("\n2. Collaborating with Teams Copilot to share results...")
    teams_response = await client.collaborate_with_copilot(
        copilot_type="teams",
        request={
            "action": "post_message",
            "channel": "finance-team",
            "message": "Q4 financial report is ready for review",
            "attach_file": "Q4_Executive_Summary.xlsx"
        }
    )
    print(f"   ✅ Teams Copilot: {teams_response['result']}")

    # Collaborate with Word Copilot
    print("\n3. Collaborating with Word Copilot to draft report narrative...")
    word_response = await client.collaborate_with_copilot(
        copilot_type="word",
        request={
            "action": "draft_document",
            "template": "quarterly_report",
            "data": {
                "quarter": "Q4 2025",
                "revenue": "$2.4M",
                "growth": "12%"
            }
        }
    )
    print(f"   ✅ Word Copilot: {word_response['result']}")

    await client.shutdown()
    print("\n✅ Scenario 5 complete\n")


async def scenario_6_memory_synchronization():
    """
    Scenario 6: Memory Synchronization with Agent 365

    Demonstrates how ANTS agents sync memory and context with Agent 365
    for seamless collaboration and consistent agent behavior.
    """
    print("\n" + "="*80)
    print("SCENARIO 6: Memory Synchronization")
    print("="*80 + "\n")

    client = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS CRM Agent",
        agent_description="Customer relationship management",
        capabilities=["customer_service", "crm"],
        enabled_plugins=["dataverse"],
        enable_memory=True
    )

    await client.initialize()
    await client.register_agent()

    print("1. Syncing episodic memory (conversation history)...")
    episodic_sync = await client.sync_memory(
        memory_type="episodic",
        data={
            "conversation_id": "conv-12345",
            "customer_id": "cust-67890",
            "summary": "Customer reported billing issue, resolved with refund",
            "timestamp": datetime.utcnow().isoformat(),
            "sentiment": "positive",
            "resolution": "refund_issued"
        }
    )
    print(f"   ✅ Episodic memory synced: {episodic_sync}")

    print("\n2. Syncing semantic memory (knowledge base)...")
    semantic_sync = await client.sync_memory(
        memory_type="semantic",
        data={
            "entity_type": "customer",
            "entity_id": "cust-67890",
            "attributes": {
                "tier": "premium",
                "lifetime_value": 50000,
                "preferred_contact": "email",
                "issues_resolved": 3
            }
        }
    )
    print(f"   ✅ Semantic memory synced: {semantic_sync}")

    print("\n3. Syncing procedural memory (learned patterns)...")
    procedural_sync = await client.sync_memory(
        memory_type="procedural",
        data={
            "pattern_type": "billing_dispute_resolution",
            "success_rate": 0.94,
            "avg_resolution_time_minutes": 15,
            "best_practices": [
                "Acknowledge issue immediately",
                "Check account history",
                "Offer refund for valid disputes"
            ]
        }
    )
    print(f"   ✅ Procedural memory synced: {procedural_sync}")

    print("\n4. Memory sync complete. Agent 365 ecosystem has shared context.")

    await client.shutdown()
    print("\n✅ Scenario 6 complete\n")


async def scenario_7_conversation_analytics():
    """
    Scenario 7: Conversation Analytics

    Demonstrates collecting and analyzing conversation metrics across
    the Agent 365 ecosystem.
    """
    print("\n" + "="*80)
    print("SCENARIO 7: Conversation Analytics")
    print("="*80 + "\n")

    client = create_agent_365_client(
        endpoint="https://agent365.azure.com",
        agent_name="ANTS Analytics Agent",
        agent_description="Conversation analytics",
        capabilities=["analytics", "reporting"],
        enabled_plugins=["dataverse"]
    )

    await client.initialize()
    await client.register_agent()

    print("1. Creating multiple conversations for analytics...")

    # Create various conversation types
    conv_types = [
        ConversationType.SINGLE_TURN,
        ConversationType.MULTI_TURN,
        ConversationType.COLLABORATIVE,
        ConversationType.HUMAN_IN_LOOP
    ]

    for i, conv_type in enumerate(conv_types):
        conv = await client.start_conversation(
            conversation_type=conv_type,
            initial_message=f"Test conversation {i+1}"
        )

        # Add some messages
        for j in range(3):
            await client.send_message(
                conversation_id=conv.conversation_id,
                content=f"Message {j+1} in {conv_type.value} conversation"
            )

        print(f"   ✅ Created {conv_type.value} conversation")

    # Get comprehensive analytics
    print("\n2. Analyzing conversation patterns...")
    stats = await client.get_conversation_stats()

    print(f"\n   📊 Conversation Analytics:")
    print(f"   - Total conversations: {stats['total_conversations']}")
    print(f"   - Total messages: {stats['total_messages']}")
    print(f"   - Agent status: {stats['agent_status']}")
    print(f"   - Active plugins: {stats['active_plugins']}")

    print(f"\n   📊 Conversations by type:")
    for conv_type, count in stats['conversations_by_type'].items():
        print(f"   - {conv_type}: {count}")

    # Calculate metrics
    avg_messages = stats['total_messages'] / stats['total_conversations'] if stats['total_conversations'] > 0 else 0
    print(f"\n   📊 Derived metrics:")
    print(f"   - Average messages per conversation: {avg_messages:.1f}")
    print(f"   - Most common type: {max(stats['conversations_by_type'].items(), key=lambda x: x[1])[0]}")

    await client.shutdown()
    print("\n✅ Scenario 7 complete\n")


async def main():
    """Run all Azure Agent 365 integration scenarios."""
    print("\n" + "="*80)
    print("ANTS - AZURE AGENT 365 INTEGRATION EXAMPLES")
    print("="*80)
    print("\nDemonstrating ANTS integration with Microsoft Azure Agent 365")
    print("for agent collaboration, M365 Copilot integration, and orchestration.\n")

    scenarios = [
        ("Register ANTS Agent", scenario_1_register_agent),
        ("Human-in-the-Loop Conversation", scenario_2_human_in_loop_conversation),
        ("Multi-Agent Collaboration", scenario_3_multi_agent_collaboration),
        ("Microsoft Graph Integration", scenario_4_microsoft_graph_integration),
        ("M365 Copilot Integration", scenario_5_copilot_integration),
        ("Memory Synchronization", scenario_6_memory_synchronization),
        ("Conversation Analytics", scenario_7_conversation_analytics)
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
    print("\nAzure Agent 365 integration enables ANTS agents to:")
    print("  ✅ Participate in Agent 365 ecosystem")
    print("  ✅ Collaborate with M365 Copilot agents")
    print("  ✅ Access Microsoft Graph data")
    print("  ✅ Orchestrate multi-agent workflows")
    print("  ✅ Share memory and context")
    print("  ✅ Enable human-in-the-loop oversight")
    print("\nThis integration positions ANTS as a first-class citizen")
    print("in the Microsoft AI agent ecosystem.\n")


if __name__ == "__main__":
    asyncio.run(main())
