"""
ANTS - Azure Agent 365 Integration
===================================

Integration with Microsoft Azure Agent 365 platform for agent collaboration,
conversation orchestration, and M365 Copilot integration.
"""

from src.integrations.azure_agent_365.agent_365_client import (
    Agent365Client,
    Agent365Config,
    Agent365Status,
    ConversationType,
    PluginType,
    ConversationContext,
    Agent365Message,
    Agent365Plugin,
    create_agent_365_client
)

__all__ = [
    "Agent365Client",
    "Agent365Config",
    "Agent365Status",
    "ConversationType",
    "PluginType",
    "ConversationContext",
    "Agent365Message",
    "Agent365Plugin",
    "create_agent_365_client"
]
