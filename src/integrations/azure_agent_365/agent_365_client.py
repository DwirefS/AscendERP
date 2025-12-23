"""
ANTS - Azure Agent 365 Integration
===================================

Integration module for Microsoft Azure Agent 365 platform.

Azure Agent 365 provides:
- Agent registration and lifecycle management
- Conversation orchestration
- Plugin/tool ecosystem
- Memory and state management
- Multi-turn conversation handling
- Agent collaboration features

This integration allows ANTS agents to:
1. Register with Azure Agent 365 ecosystem
2. Participate in Agent 365 conversations
3. Leverage Agent 365 plugins and tools
4. Share memory and context with Agent 365 agents
5. Coordinate with Microsoft 365 Copilot agents

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

from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Agent365Status(Enum):
    """Agent status in Azure Agent 365 ecosystem."""
    REGISTERING = "registering"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


class ConversationType(Enum):
    """Type of conversation in Agent 365."""
    SINGLE_TURN = "single_turn"
    MULTI_TURN = "multi_turn"
    COLLABORATIVE = "collaborative"  # Multiple agents
    HUMAN_IN_LOOP = "human_in_loop"


class PluginType(Enum):
    """Types of plugins available in Agent 365."""
    MICROSOFT_GRAPH = "microsoft_graph"  # Access to M365 data
    POWER_AUTOMATE = "power_automate"  # Workflow automation
    DATAVERSE = "dataverse"  # Business data platform
    CUSTOM_API = "custom_api"  # Custom REST APIs
    ANTS_NATIVE = "ants_native"  # ANTS-specific tools


@dataclass
class Agent365Config:
    """Configuration for Azure Agent 365 integration."""

    # Azure credentials
    endpoint: str  # Agent 365 endpoint URL
    credential: Optional[Any] = None  # Azure credential or API key

    # Agent registration
    agent_id: str = ""
    agent_name: str = ""
    agent_description: str = ""
    capabilities: List[str] = field(default_factory=list)

    # Conversation settings
    max_turns: int = 20  # Maximum conversation turns
    timeout_seconds: int = 300  # 5 minutes
    enable_memory: bool = True  # Share memory with Agent 365

    # Plugin configuration
    enabled_plugins: List[str] = field(default_factory=list)

    # Integration settings
    sync_interval_seconds: int = 60  # State sync interval
    enable_copilot_integration: bool = True  # M365 Copilot integration


@dataclass
class ConversationContext:
    """Context for an Agent 365 conversation."""
    conversation_id: str
    conversation_type: ConversationType
    participants: List[str]  # Agent IDs
    turn_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Agent365Message:
    """Message in Agent 365 conversation."""
    message_id: str
    conversation_id: str
    sender_id: str  # Agent ID or user ID
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Agent365Plugin:
    """Plugin configuration for Agent 365."""
    plugin_id: str
    plugin_type: PluginType
    name: str
    description: str
    enabled: bool = True
    configuration: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)


class Agent365Client:
    """
    Client for Azure Agent 365 integration.

    Enables ANTS agents to participate in the Azure Agent 365 ecosystem,
    collaborate with Microsoft 365 Copilot agents, and leverage Agent 365
    plugins and services.

    Example:
        ```python
        # Initialize Agent 365 client
        config = Agent365Config(
            endpoint="https://agent365.azure.com",
            agent_name="ANTS Finance Agent",
            agent_description="Financial reconciliation and compliance",
            capabilities=["invoice_processing", "fraud_detection"],
            enabled_plugins=["microsoft_graph", "dataverse"]
        )

        client = Agent365Client(config)
        await client.initialize()

        # Register agent
        await client.register_agent()

        # Start conversation
        conversation = await client.start_conversation(
            conversation_type=ConversationType.HUMAN_IN_LOOP,
            initial_message="I need help with Q4 reconciliation"
        )

        # Process messages
        async for message in client.listen_for_messages(conversation.conversation_id):
            response = await client.process_message(message)
            await client.send_message(conversation.conversation_id, response)
        ```
    """

    def __init__(self, config: Agent365Config):
        """
        Initialize Agent 365 client.

        Args:
            config: Agent 365 configuration
        """
        self.config = config
        self.status = Agent365Status.OFFLINE
        self.active_conversations: Dict[str, ConversationContext] = {}
        self.registered_plugins: Dict[str, Agent365Plugin] = {}
        self.message_handlers: Dict[str, Callable] = {}

        # Initialize credential if not provided
        if not self.config.credential:
            self.config.credential = DefaultAzureCredential()

        # Generate agent ID if not provided
        if not self.config.agent_id:
            self.config.agent_id = f"ants-agent-{uuid.uuid4().hex[:8]}"

        logger.info(f"Agent365Client initialized for agent: {self.config.agent_id}")

    async def initialize(self) -> bool:
        """
        Initialize connection to Azure Agent 365.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Initializing connection to Agent 365: {self.config.endpoint}")

            # In production, this would establish connection to Agent 365 service
            # For now, simulate initialization
            await asyncio.sleep(0.1)

            # Initialize plugins
            await self._initialize_plugins()

            self.status = Agent365Status.IDLE
            logger.info("Successfully connected to Agent 365")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Agent 365 client: {e}")
            self.status = Agent365Status.ERROR
            return False

    async def register_agent(self) -> Dict[str, Any]:
        """
        Register ANTS agent with Azure Agent 365 ecosystem.

        Returns:
            Registration response with agent details
        """
        try:
            self.status = Agent365Status.REGISTERING
            logger.info(f"Registering agent: {self.config.agent_name}")

            # Prepare registration payload
            registration_payload = {
                "agent_id": self.config.agent_id,
                "agent_name": self.config.agent_name,
                "agent_description": self.config.agent_description,
                "capabilities": self.config.capabilities,
                "enabled_plugins": self.config.enabled_plugins,
                "platform": "ANTS",
                "version": "1.0.0",
                "registered_at": datetime.utcnow().isoformat()
            }

            # In production, POST to Agent 365 registration endpoint
            # For now, simulate registration
            await asyncio.sleep(0.2)

            response = {
                "status": "registered",
                "agent_id": self.config.agent_id,
                "registration_token": f"reg-{uuid.uuid4().hex}",
                "capabilities_verified": self.config.capabilities,
                "plugins_enabled": list(self.registered_plugins.keys())
            }

            self.status = Agent365Status.ACTIVE
            logger.info(f"Agent registered successfully: {self.config.agent_id}")

            return response

        except Exception as e:
            logger.error(f"Failed to register agent: {e}")
            self.status = Agent365Status.ERROR
            raise

    async def start_conversation(
        self,
        conversation_type: ConversationType,
        initial_message: Optional[str] = None,
        participants: Optional[List[str]] = None
    ) -> ConversationContext:
        """
        Start a new conversation in Agent 365.

        Args:
            conversation_type: Type of conversation
            initial_message: Optional first message
            participants: Optional list of participant agent/user IDs

        Returns:
            Conversation context
        """
        try:
            conversation_id = f"conv-{uuid.uuid4().hex[:12]}"

            participants = participants or [self.config.agent_id]

            context = ConversationContext(
                conversation_id=conversation_id,
                conversation_type=conversation_type,
                participants=participants
            )

            # Add initial message to history if provided
            if initial_message:
                message = Agent365Message(
                    message_id=f"msg-{uuid.uuid4().hex[:8]}",
                    conversation_id=conversation_id,
                    sender_id=self.config.agent_id,
                    content=initial_message
                )
                context.history.append(self._message_to_dict(message))
                context.turn_count = 1

            self.active_conversations[conversation_id] = context

            logger.info(f"Started {conversation_type.value} conversation: {conversation_id}")

            return context

        except Exception as e:
            logger.error(f"Failed to start conversation: {e}")
            raise

    async def send_message(
        self,
        conversation_id: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Agent365Message:
        """
        Send message in Agent 365 conversation.

        Args:
            conversation_id: Conversation ID
            content: Message content
            attachments: Optional attachments (files, images, etc.)
            metadata: Optional message metadata

        Returns:
            Sent message
        """
        try:
            if conversation_id not in self.active_conversations:
                raise ValueError(f"Conversation not found: {conversation_id}")

            context = self.active_conversations[conversation_id]

            message = Agent365Message(
                message_id=f"msg-{uuid.uuid4().hex[:8]}",
                conversation_id=conversation_id,
                sender_id=self.config.agent_id,
                content=content,
                attachments=attachments or [],
                metadata=metadata or {}
            )

            # Add to conversation history
            context.history.append(self._message_to_dict(message))
            context.turn_count += 1

            # In production, POST to Agent 365 messaging endpoint
            await asyncio.sleep(0.05)

            logger.info(f"Sent message in conversation {conversation_id}: {content[:50]}...")

            return message

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def listen_for_messages(
        self,
        conversation_id: str,
        poll_interval: float = 1.0
    ):
        """
        Listen for incoming messages in a conversation.

        Args:
            conversation_id: Conversation ID to listen to
            poll_interval: How often to check for messages (seconds)

        Yields:
            Incoming messages
        """
        if conversation_id not in self.active_conversations:
            raise ValueError(f"Conversation not found: {conversation_id}")

        logger.info(f"Listening for messages in conversation: {conversation_id}")

        context = self.active_conversations[conversation_id]
        last_message_count = len(context.history)

        # In production, this would use WebSocket or Server-Sent Events
        # For now, simulate polling
        while context.turn_count < self.config.max_turns:
            await asyncio.sleep(poll_interval)

            # Check for new messages
            if len(context.history) > last_message_count:
                # Yield new messages
                for msg_dict in context.history[last_message_count:]:
                    # Only yield messages from others
                    if msg_dict["sender_id"] != self.config.agent_id:
                        yield self._dict_to_message(msg_dict)

                last_message_count = len(context.history)

    async def invoke_plugin(
        self,
        plugin_id: str,
        operation: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Invoke an Agent 365 plugin.

        Args:
            plugin_id: Plugin identifier
            operation: Operation to perform
            parameters: Operation parameters

        Returns:
            Plugin operation result
        """
        try:
            if plugin_id not in self.registered_plugins:
                raise ValueError(f"Plugin not registered: {plugin_id}")

            plugin = self.registered_plugins[plugin_id]

            if not plugin.enabled:
                raise ValueError(f"Plugin is disabled: {plugin_id}")

            logger.info(f"Invoking plugin {plugin_id}: {operation}")

            # In production, call actual plugin API
            # Simulate plugin execution
            await asyncio.sleep(0.1)

            result = {
                "plugin_id": plugin_id,
                "operation": operation,
                "status": "success",
                "result": f"Executed {operation} with {len(parameters)} parameters",
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Plugin {plugin_id} executed successfully")

            return result

        except Exception as e:
            logger.error(f"Failed to invoke plugin: {e}")
            raise

    async def sync_memory(
        self,
        memory_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Sync memory/state with Agent 365.

        Allows ANTS agents to share memory and context with Agent 365
        agents for seamless collaboration.

        Args:
            memory_type: Type of memory (episodic, semantic, procedural)
            data: Memory data to sync

        Returns:
            True if successful
        """
        try:
            if not self.config.enable_memory:
                logger.warning("Memory sync is disabled")
                return False

            logger.info(f"Syncing {memory_type} memory to Agent 365")

            # In production, POST to Agent 365 memory API
            await asyncio.sleep(0.1)

            logger.info(f"Successfully synced {memory_type} memory")
            return True

        except Exception as e:
            logger.error(f"Failed to sync memory: {e}")
            return False

    async def collaborate_with_copilot(
        self,
        copilot_type: str,
        request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Collaborate with Microsoft 365 Copilot agents.

        Args:
            copilot_type: Type of Copilot (excel, word, teams, etc.)
            request: Collaboration request

        Returns:
            Copilot response
        """
        try:
            if not self.config.enable_copilot_integration:
                raise ValueError("Copilot integration is disabled")

            logger.info(f"Collaborating with {copilot_type} Copilot")

            # In production, this would invoke Microsoft 365 Copilot APIs
            await asyncio.sleep(0.2)

            response = {
                "copilot_type": copilot_type,
                "status": "success",
                "result": f"Copilot processed request: {request.get('action', 'unknown')}",
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info(f"Successfully collaborated with {copilot_type} Copilot")

            return response

        except Exception as e:
            logger.error(f"Failed to collaborate with Copilot: {e}")
            raise

    async def get_conversation_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active conversations.

        Returns:
            Conversation statistics
        """
        total_conversations = len(self.active_conversations)
        total_messages = sum(
            len(conv.history) for conv in self.active_conversations.values()
        )

        by_type = {}
        for conv in self.active_conversations.values():
            conv_type = conv.conversation_type.value
            by_type[conv_type] = by_type.get(conv_type, 0) + 1

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "conversations_by_type": by_type,
            "agent_status": self.status.value,
            "active_plugins": len(self.registered_plugins)
        }

    async def shutdown(self) -> None:
        """Gracefully shutdown Agent 365 client."""
        logger.info("Shutting down Agent 365 client...")

        # Close active conversations
        for conv_id in list(self.active_conversations.keys()):
            logger.info(f"Closing conversation: {conv_id}")
            del self.active_conversations[conv_id]

        self.status = Agent365Status.OFFLINE
        logger.info("Agent 365 client shutdown complete")

    # Private helper methods

    async def _initialize_plugins(self) -> None:
        """Initialize configured plugins."""
        for plugin_name in self.config.enabled_plugins:
            try:
                # Map plugin name to type
                plugin_type_map = {
                    "microsoft_graph": PluginType.MICROSOFT_GRAPH,
                    "power_automate": PluginType.POWER_AUTOMATE,
                    "dataverse": PluginType.DATAVERSE,
                    "custom_api": PluginType.CUSTOM_API,
                    "ants_native": PluginType.ANTS_NATIVE
                }

                plugin_type = plugin_type_map.get(plugin_name, PluginType.CUSTOM_API)

                plugin = Agent365Plugin(
                    plugin_id=f"plugin-{plugin_name}",
                    plugin_type=plugin_type,
                    name=plugin_name,
                    description=f"{plugin_name} plugin for Agent 365",
                    enabled=True
                )

                self.registered_plugins[plugin.plugin_id] = plugin
                logger.info(f"Initialized plugin: {plugin_name}")

            except Exception as e:
                logger.error(f"Failed to initialize plugin {plugin_name}: {e}")

    def _message_to_dict(self, message: Agent365Message) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_id": message.message_id,
            "conversation_id": message.conversation_id,
            "sender_id": message.sender_id,
            "content": message.content,
            "timestamp": message.timestamp.isoformat(),
            "attachments": message.attachments,
            "metadata": message.metadata
        }

    def _dict_to_message(self, msg_dict: Dict[str, Any]) -> Agent365Message:
        """Convert dictionary to message."""
        return Agent365Message(
            message_id=msg_dict["message_id"],
            conversation_id=msg_dict["conversation_id"],
            sender_id=msg_dict["sender_id"],
            content=msg_dict["content"],
            timestamp=datetime.fromisoformat(msg_dict["timestamp"]),
            attachments=msg_dict.get("attachments", []),
            metadata=msg_dict.get("metadata", {})
        )


# Convenience factory function
def create_agent_365_client(
    endpoint: str,
    agent_name: str,
    agent_description: str,
    capabilities: List[str],
    enabled_plugins: Optional[List[str]] = None,
    **kwargs
) -> Agent365Client:
    """
    Create and configure Agent 365 client.

    Args:
        endpoint: Agent 365 endpoint URL
        agent_name: Name of the ANTS agent
        agent_description: Description of agent capabilities
        capabilities: List of agent capabilities
        enabled_plugins: Optional list of plugins to enable
        **kwargs: Additional configuration options

    Returns:
        Configured Agent365Client
    """
    config = Agent365Config(
        endpoint=endpoint,
        agent_name=agent_name,
        agent_description=agent_description,
        capabilities=capabilities,
        enabled_plugins=enabled_plugins or [],
        **kwargs
    )

    return Agent365Client(config)
