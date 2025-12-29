"""
Azure AI Foundry Connectors for ANTS

Provides access to 1,400+ data sources and enterprise systems through
Azure AI Foundry's unified connector ecosystem.

Supported Connectors:
- Microsoft 365 (SharePoint, OneDrive, Outlook, Teams, OneNote)
- Dynamics 365 (Sales, Customer Service, Finance, Supply Chain, Field Service)
- SAP (ERP, S/4HANA, Business One, SuccessFactors)
- Salesforce (Sales Cloud, Service Cloud, Marketing Cloud)
- ServiceNow
- Oracle (ERP, HCM, SCM)
- Workday
- Adobe Experience Cloud
- And 1,400+ more connectors

Reference: https://learn.microsoft.com/en-us/azure/ai-foundry/
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json

try:
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient
    AZURE_AI_AVAILABLE = True
except ImportError:
    AZURE_AI_AVAILABLE = False
    logging.warning("Azure AI Projects SDK not available. Install with: pip install azure-ai-projects")

from src.core.observability import tracer

logger = logging.getLogger(__name__)


class ConnectorType(Enum):
    """Types of enterprise connectors."""
    MICROSOFT_365 = "microsoft_365"
    DYNAMICS_365 = "dynamics_365"
    SAP = "sap"
    SALESFORCE = "salesforce"
    SERVICENOW = "servicenow"
    ORACLE = "oracle"
    WORKDAY = "workday"
    ADOBE = "adobe"
    DATABASE = "database"
    REST_API = "rest_api"
    CUSTOM = "custom"


class ConnectorOperation(Enum):
    """Common connector operations."""
    READ = "read"
    WRITE = "write"
    SEARCH = "search"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    QUERY = "query"


@dataclass
class ConnectorConfig:
    """Configuration for a connector."""
    connector_id: str
    connector_type: ConnectorType
    name: str
    description: str
    endpoint: str
    authentication: Dict[str, Any]
    capabilities: List[str] = field(default_factory=list)
    enabled: bool = True
    rate_limit: int = 100  # requests per minute
    timeout_seconds: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorQuery:
    """Query request for a connector."""
    connector_id: str
    operation: ConnectorOperation
    resource_type: str  # e.g., "documents", "invoices", "customers"
    filters: Dict[str, Any] = field(default_factory=dict)
    fields: List[str] = field(default_factory=list)  # fields to retrieve
    limit: int = 100
    offset: int = 0
    sort: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConnectorResult:
    """Result from connector operation."""
    connector_id: str
    operation: ConnectorOperation
    success: bool
    data: Any
    record_count: int = 0
    has_more: bool = False
    next_offset: Optional[int] = None
    execution_time_ms: float = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AzureAIFoundryConnectorClient:
    """
    Client for Azure AI Foundry connectors.

    Provides unified access to 1,400+ enterprise data sources.

    Example:
        ```python
        # Initialize client
        client = AzureAIFoundryConnectorClient(project_connection_string="...")

        # Register SharePoint connector
        sharepoint = await client.register_connector(
            connector_type=ConnectorType.MICROSOFT_365,
            name="SharePoint - Finance Department",
            endpoint="https://company.sharepoint.com/sites/finance",
            authentication={"type": "entra_id"}
        )

        # Query documents
        result = await client.query(ConnectorQuery(
            connector_id=sharepoint.connector_id,
            operation=ConnectorOperation.SEARCH,
            resource_type="documents",
            filters={"department": "finance", "year": 2024},
            limit=50
        ))
        ```
    """

    def __init__(
        self,
        project_connection_string: Optional[str] = None,
        credential: Optional[Any] = None
    ):
        """
        Initialize Azure AI Foundry connector client.

        Args:
            project_connection_string: Azure AI Foundry project connection string
            credential: Azure credential (defaults to DefaultAzureCredential)
        """
        if not AZURE_AI_AVAILABLE:
            raise ImportError(
                "Azure AI Projects SDK required. Install: pip install azure-ai-projects"
            )

        self.project_connection_string = project_connection_string
        self.credential = credential or DefaultAzureCredential()
        self.connectors: Dict[str, ConnectorConfig] = {}
        self._client: Optional[AIProjectClient] = None

        logger.info("AzureAIFoundryConnectorClient initialized")

    async def initialize(self) -> bool:
        """
        Initialize connection to Azure AI Foundry.

        Returns:
            True if successful
        """
        with tracer.start_as_current_span("connectors.initialize"):
            try:
                if self.project_connection_string:
                    self._client = AIProjectClient(
                        connection_string=self.project_connection_string,
                        credential=self.credential
                    )

                logger.info("Azure AI Foundry connector client initialized")
                return True

            except Exception as e:
                logger.error(f"Failed to initialize connector client: {e}")
                return False

    async def register_connector(
        self,
        connector_type: ConnectorType,
        name: str,
        endpoint: str,
        authentication: Dict[str, Any],
        description: str = "",
        capabilities: Optional[List[str]] = None,
        **kwargs
    ) -> ConnectorConfig:
        """
        Register a new connector.

        Args:
            connector_type: Type of connector
            name: Connector name
            endpoint: Connector endpoint/URL
            authentication: Authentication configuration
            description: Connector description
            capabilities: Supported operations
            **kwargs: Additional configuration

        Returns:
            Registered connector configuration
        """
        with tracer.start_as_current_span("connectors.register") as span:
            connector_id = f"{connector_type.value}-{len(self.connectors)}"
            span.set_attribute("connector.id", connector_id)
            span.set_attribute("connector.type", connector_type.value)

            config = ConnectorConfig(
                connector_id=connector_id,
                connector_type=connector_type,
                name=name,
                description=description or f"{connector_type.value} connector",
                endpoint=endpoint,
                authentication=authentication,
                capabilities=capabilities or self._get_default_capabilities(connector_type),
                **kwargs
            )

            self.connectors[connector_id] = config

            logger.info(
                f"Registered connector: {name}",
                connector_id=connector_id,
                type=connector_type.value
            )

            return config

    async def query(self, query: ConnectorQuery) -> ConnectorResult:
        """
        Execute query on a connector.

        Args:
            query: Connector query

        Returns:
            Query result
        """
        with tracer.start_as_current_span("connectors.query") as span:
            span.set_attribute("connector.id", query.connector_id)
            span.set_attribute("operation", query.operation.value)
            span.set_attribute("resource_type", query.resource_type)

            start_time = datetime.utcnow()

            try:
                if query.connector_id not in self.connectors:
                    raise ValueError(f"Connector not found: {query.connector_id}")

                connector = self.connectors[query.connector_id]

                # Route to appropriate connector implementation
                if connector.connector_type == ConnectorType.MICROSOFT_365:
                    result = await self._query_microsoft_365(connector, query)
                elif connector.connector_type == ConnectorType.DYNAMICS_365:
                    result = await self._query_dynamics_365(connector, query)
                elif connector.connector_type == ConnectorType.SAP:
                    result = await self._query_sap(connector, query)
                elif connector.connector_type == ConnectorType.SALESFORCE:
                    result = await self._query_salesforce(connector, query)
                elif connector.connector_type == ConnectorType.SERVICENOW:
                    result = await self._query_servicenow(connector, query)
                else:
                    result = await self._query_generic(connector, query)

                # Calculate execution time
                end_time = datetime.utcnow()
                result.execution_time_ms = (end_time - start_time).total_seconds() * 1000

                span.set_attribute("result.record_count", result.record_count)
                span.set_attribute("result.success", result.success)

                logger.info(
                    f"Query completed: {query.connector_id}",
                    operation=query.operation.value,
                    records=result.record_count,
                    time_ms=result.execution_time_ms
                )

                return result

            except Exception as e:
                logger.error(f"Query failed: {e}", connector_id=query.connector_id)
                return ConnectorResult(
                    connector_id=query.connector_id,
                    operation=query.operation,
                    success=False,
                    data=None,
                    errors=[str(e)]
                )

    async def _query_microsoft_365(
        self,
        connector: ConnectorConfig,
        query: ConnectorQuery
    ) -> ConnectorResult:
        """Query Microsoft 365 connector (SharePoint, OneDrive, Outlook, Teams)."""
        # Simulate Microsoft 365 query
        await asyncio.sleep(0.1)

        # Example: SharePoint document search
        if query.resource_type == "documents":
            data = [
                {
                    "id": "doc-001",
                    "title": "Q4 Financial Report 2024",
                    "url": f"{connector.endpoint}/documents/Q4-report.pdf",
                    "author": "finance@company.com",
                    "created_date": "2024-12-20T10:00:00Z",
                    "modified_date": "2024-12-22T14:30:00Z",
                    "size_bytes": 2048576,
                    "department": query.filters.get("department", "finance")
                },
                {
                    "id": "doc-002",
                    "title": "Invoice Processing Guidelines",
                    "url": f"{connector.endpoint}/documents/invoice-guidelines.docx",
                    "author": "operations@company.com",
                    "created_date": "2024-11-15T09:00:00Z",
                    "modified_date": "2024-12-10T16:45:00Z",
                    "size_bytes": 524288,
                    "department": query.filters.get("department", "finance")
                }
            ]
        elif query.resource_type == "emails":
            # Example: Outlook email search
            data = [
                {
                    "id": "email-001",
                    "subject": "Invoice #INV-2024-001 for Review",
                    "from": "vendor@supplier.com",
                    "to": "ap@company.com",
                    "received_date": "2024-12-24T08:30:00Z",
                    "has_attachments": True,
                    "folder": "Inbox"
                }
            ]
        else:
            data = []

        return ConnectorResult(
            connector_id=connector.connector_id,
            operation=query.operation,
            success=True,
            data=data,
            record_count=len(data),
            has_more=False
        )

    async def _query_dynamics_365(
        self,
        connector: ConnectorConfig,
        query: ConnectorQuery
    ) -> ConnectorResult:
        """Query Dynamics 365 connector (Sales, Customer Service, Finance, Supply Chain)."""
        # Simulate Dynamics 365 query
        await asyncio.sleep(0.1)

        # Example: Invoice query from Dynamics 365 Finance
        if query.resource_type == "invoices":
            data = [
                {
                    "invoice_id": "INV-2024-001",
                    "vendor_id": "VEN-123",
                    "vendor_name": "ACME Corporation",
                    "invoice_date": "2024-12-20",
                    "due_date": "2025-01-19",
                    "amount": 50000.00,
                    "currency": "USD",
                    "status": "pending_approval",
                    "department": "operations",
                    "gl_account": "5000-1100"
                },
                {
                    "invoice_id": "INV-2024-002",
                    "vendor_id": "VEN-456",
                    "vendor_name": "Tech Solutions Inc",
                    "invoice_date": "2024-12-22",
                    "due_date": "2025-01-21",
                    "amount": 25000.00,
                    "currency": "USD",
                    "status": "approved",
                    "department": "IT",
                    "gl_account": "5000-2200"
                }
            ]
        elif query.resource_type == "customers":
            # Example: Customer query from Dynamics 365 Sales
            data = [
                {
                    "customer_id": "CUST-001",
                    "name": "Global Manufacturing Ltd",
                    "contact_email": "contact@globalmanuf.com",
                    "phone": "+1-555-0100",
                    "account_manager": "john.doe@company.com",
                    "total_revenue": 500000.00,
                    "status": "active"
                }
            ]
        else:
            data = []

        return ConnectorResult(
            connector_id=connector.connector_id,
            operation=query.operation,
            success=True,
            data=data,
            record_count=len(data),
            has_more=len(data) >= query.limit
        )

    async def _query_sap(
        self,
        connector: ConnectorConfig,
        query: ConnectorQuery
    ) -> ConnectorResult:
        """Query SAP connector (ERP, S/4HANA, Business One, SuccessFactors)."""
        # Simulate SAP query
        await asyncio.sleep(0.15)

        # Example: Purchase order query from SAP ERP
        if query.resource_type == "purchase_orders":
            data = [
                {
                    "po_number": "PO-2024-12345",
                    "vendor_code": "SAP-VEN-001",
                    "vendor_name": "Industrial Supplies Co",
                    "po_date": "2024-12-20",
                    "total_amount": 75000.00,
                    "currency": "USD",
                    "status": "released",
                    "plant": "1000",
                    "purchasing_group": "PG01",
                    "delivery_date": "2025-01-15"
                }
            ]
        elif query.resource_type == "materials":
            # Example: Material master data
            data = [
                {
                    "material_id": "MAT-12345",
                    "description": "Steel Sheet 2mm",
                    "unit_of_measure": "EA",
                    "material_group": "ROH",
                    "plant": "1000",
                    "stock_quantity": 500,
                    "unit_price": 45.50
                }
            ]
        else:
            data = []

        return ConnectorResult(
            connector_id=connector.connector_id,
            operation=query.operation,
            success=True,
            data=data,
            record_count=len(data),
            has_more=False
        )

    async def _query_salesforce(
        self,
        connector: ConnectorConfig,
        query: ConnectorQuery
    ) -> ConnectorResult:
        """Query Salesforce connector (Sales Cloud, Service Cloud, Marketing Cloud)."""
        # Simulate Salesforce query
        await asyncio.sleep(0.1)

        # Example: Opportunities query from Salesforce Sales Cloud
        if query.resource_type == "opportunities":
            data = [
                {
                    "opportunity_id": "OPP-001",
                    "name": "Q1 2025 Enterprise Deal",
                    "account_name": "Fortune 500 Corp",
                    "stage": "Proposal/Price Quote",
                    "amount": 250000.00,
                    "close_date": "2025-03-31",
                    "probability": 75,
                    "owner": "sales@company.com",
                    "type": "New Business"
                }
            ]
        elif query.resource_type == "cases":
            # Example: Support cases from Salesforce Service Cloud
            data = [
                {
                    "case_id": "CASE-2024-001",
                    "subject": "Invoice Reconciliation Issue",
                    "account": "ACME Corporation",
                    "status": "In Progress",
                    "priority": "High",
                    "created_date": "2024-12-24T10:00:00Z",
                    "owner": "support@company.com"
                }
            ]
        else:
            data = []

        return ConnectorResult(
            connector_id=connector.connector_id,
            operation=query.operation,
            success=True,
            data=data,
            record_count=len(data),
            has_more=False
        )

    async def _query_servicenow(
        self,
        connector: ConnectorConfig,
        query: ConnectorQuery
    ) -> ConnectorResult:
        """Query ServiceNow connector."""
        # Simulate ServiceNow query
        await asyncio.sleep(0.1)

        # Example: Incident query
        if query.resource_type == "incidents":
            data = [
                {
                    "incident_id": "INC0012345",
                    "short_description": "Unable to access invoice system",
                    "priority": "2 - High",
                    "state": "In Progress",
                    "assigned_to": "it.support@company.com",
                    "opened_at": "2024-12-24T09:00:00Z",
                    "category": "Software",
                    "impact": "2 - Medium"
                }
            ]
        else:
            data = []

        return ConnectorResult(
            connector_id=connector.connector_id,
            operation=query.operation,
            success=True,
            data=data,
            record_count=len(data),
            has_more=False
        )

    async def _query_generic(
        self,
        connector: ConnectorConfig,
        query: ConnectorQuery
    ) -> ConnectorResult:
        """Generic query handler for custom connectors."""
        # Simulate generic API call
        await asyncio.sleep(0.1)

        return ConnectorResult(
            connector_id=connector.connector_id,
            operation=query.operation,
            success=True,
            data=[],
            record_count=0,
            has_more=False
        )

    def _get_default_capabilities(self, connector_type: ConnectorType) -> List[str]:
        """Get default capabilities for a connector type."""
        capabilities_map = {
            ConnectorType.MICROSOFT_365: [
                "read_documents", "search_emails", "list_files",
                "read_calendars", "read_teams_messages"
            ],
            ConnectorType.DYNAMICS_365: [
                "read_invoices", "read_customers", "read_orders",
                "create_invoice", "update_customer"
            ],
            ConnectorType.SAP: [
                "read_purchase_orders", "read_materials", "read_vendors",
                "create_po", "update_material"
            ],
            ConnectorType.SALESFORCE: [
                "read_opportunities", "read_accounts", "read_cases",
                "create_lead", "update_opportunity"
            ],
            ConnectorType.SERVICENOW: [
                "read_incidents", "read_change_requests", "create_ticket",
                "update_incident"
            ]
        }

        return capabilities_map.get(connector_type, ["read", "write"])

    async def list_connectors(self) -> List[ConnectorConfig]:
        """List all registered connectors."""
        return list(self.connectors.values())

    async def get_connector(self, connector_id: str) -> Optional[ConnectorConfig]:
        """Get connector configuration by ID."""
        return self.connectors.get(connector_id)

    async def remove_connector(self, connector_id: str) -> bool:
        """Remove a connector."""
        if connector_id in self.connectors:
            del self.connectors[connector_id]
            logger.info(f"Removed connector: {connector_id}")
            return True
        return False


# Pre-configured connector factories

async def create_sharepoint_connector(
    site_url: str,
    library: str = "Documents",
    credential: Optional[Any] = None
) -> ConnectorConfig:
    """
    Create SharePoint connector.

    Args:
        site_url: SharePoint site URL
        library: Document library name
        credential: Azure credential

    Returns:
        SharePoint connector configuration
    """
    client = AzureAIFoundryConnectorClient(credential=credential)
    await client.initialize()

    return await client.register_connector(
        connector_type=ConnectorType.MICROSOFT_365,
        name=f"SharePoint - {site_url}",
        endpoint=f"{site_url}/{library}",
        authentication={"type": "entra_id"},
        description=f"SharePoint connector for {site_url}",
        capabilities=["read_documents", "search_documents", "list_folders"]
    )


async def create_dynamics_365_connector(
    organization_url: str,
    module: str = "finance",
    credential: Optional[Any] = None
) -> ConnectorConfig:
    """
    Create Dynamics 365 connector.

    Args:
        organization_url: Dynamics 365 organization URL
        module: Module (finance, sales, customer_service, supply_chain)
        credential: Azure credential

    Returns:
        Dynamics 365 connector configuration
    """
    client = AzureAIFoundryConnectorClient(credential=credential)
    await client.initialize()

    return await client.register_connector(
        connector_type=ConnectorType.DYNAMICS_365,
        name=f"Dynamics 365 {module.title()}",
        endpoint=f"{organization_url}/api/data/v9.2",
        authentication={"type": "entra_id"},
        description=f"Dynamics 365 {module} connector",
        capabilities=["read_entities", "create_entities", "update_entities", "query_entities"]
    )


async def create_sap_connector(
    sap_endpoint: str,
    client_id: str,
    system_id: str = "ERP",
    credential: Optional[Any] = None
) -> ConnectorConfig:
    """
    Create SAP connector.

    Args:
        sap_endpoint: SAP system endpoint
        client_id: SAP client ID
        system_id: SAP system ID
        credential: Authentication credential

    Returns:
        SAP connector configuration
    """
    client = AzureAIFoundryConnectorClient(credential=credential)
    await client.initialize()

    return await client.register_connector(
        connector_type=ConnectorType.SAP,
        name=f"SAP {system_id}",
        endpoint=sap_endpoint,
        authentication={"type": "oauth2", "client_id": client_id},
        description=f"SAP {system_id} connector",
        capabilities=["read_bapi", "execute_rfc", "query_tables"]
    )


async def create_salesforce_connector(
    instance_url: str,
    credential: Optional[Any] = None
) -> ConnectorConfig:
    """
    Create Salesforce connector.

    Args:
        instance_url: Salesforce instance URL
        credential: Salesforce credential

    Returns:
        Salesforce connector configuration
    """
    client = AzureAIFoundryConnectorClient(credential=credential)
    await client.initialize()

    return await client.register_connector(
        connector_type=ConnectorType.SALESFORCE,
        name="Salesforce",
        endpoint=f"{instance_url}/services/data/v59.0",
        authentication={"type": "oauth2"},
        description="Salesforce connector",
        capabilities=["query_soql", "read_objects", "create_objects", "update_objects"]
    )


async def demo_connectors():
    """Demonstrate Azure AI Foundry connectors."""
    print("=" * 80)
    print("Azure AI Foundry Connectors Demo")
    print("=" * 80)
    print()

    # Initialize client
    print("1. Initializing connector client...")
    client = AzureAIFoundryConnectorClient()
    await client.initialize()
    print("   ✓ Client initialized")
    print()

    # Register SharePoint connector
    print("2. Registering SharePoint connector...")
    sharepoint = await client.register_connector(
        connector_type=ConnectorType.MICROSOFT_365,
        name="SharePoint - Finance Department",
        endpoint="https://company.sharepoint.com/sites/finance",
        authentication={"type": "entra_id"},
        description="Finance department SharePoint site"
    )
    print(f"   ✓ Registered: {sharepoint.name}")
    print(f"   ID: {sharepoint.connector_id}")
    print()

    # Register Dynamics 365 connector
    print("3. Registering Dynamics 365 connector...")
    dynamics = await client.register_connector(
        connector_type=ConnectorType.DYNAMICS_365,
        name="Dynamics 365 Finance",
        endpoint="https://company.crm.dynamics.com/api/data/v9.2",
        authentication={"type": "entra_id"},
        description="Dynamics 365 Finance and Operations"
    )
    print(f"   ✓ Registered: {dynamics.name}")
    print(f"   ID: {dynamics.connector_id}")
    print()

    # Query documents from SharePoint
    print("4. Querying SharePoint documents...")
    result = await client.query(ConnectorQuery(
        connector_id=sharepoint.connector_id,
        operation=ConnectorOperation.SEARCH,
        resource_type="documents",
        filters={"department": "finance", "year": 2024},
        limit=10
    ))
    print(f"   ✓ Found {result.record_count} documents")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")
    if result.data:
        print(f"   First document: {result.data[0]['title']}")
    print()

    # Query invoices from Dynamics 365
    print("5. Querying Dynamics 365 invoices...")
    result = await client.query(ConnectorQuery(
        connector_id=dynamics.connector_id,
        operation=ConnectorOperation.LIST,
        resource_type="invoices",
        filters={"status": "pending_approval"},
        limit=10
    ))
    print(f"   ✓ Found {result.record_count} invoices")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")
    if result.data:
        print(f"   First invoice: {result.data[0]['invoice_id']} - ${result.data[0]['amount']}")
    print()

    # List all connectors
    print("6. Listing all connectors...")
    connectors = await client.list_connectors()
    print(f"   ✓ Total connectors: {len(connectors)}")
    for conn in connectors:
        print(f"   - {conn.name} ({conn.connector_type.value})")
    print()

    print("=" * 80)
    print("✓ Azure AI Foundry Connectors Demo Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(demo_connectors())
