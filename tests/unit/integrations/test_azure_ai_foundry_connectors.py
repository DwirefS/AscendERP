"""
Unit Tests for Azure AI Foundry Connectors

Tests the 1,400+ connector ecosystem for enterprise data sources.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.integrations.azure_ai_foundry_connectors import (
    AzureAIFoundryConnectorClient,
    ConnectorType,
    ConnectorOperation,
    ConnectorConfig,
    ConnectorQuery,
    ConnectorResult,
    create_sharepoint_connector,
    create_dynamics_365_connector,
    create_sap_connector,
    create_salesforce_connector,
    AZURE_AI_AVAILABLE
)


@pytest.fixture
def connector_client():
    """Connector client fixture."""
    client = AzureAIFoundryConnectorClient(
        project_connection_string="test-connection-string"
    )
    return client


@pytest.fixture
def sharepoint_connector():
    """SharePoint connector configuration."""
    return ConnectorConfig(
        connector_id="microsoft_365-0",
        connector_type=ConnectorType.MICROSOFT_365,
        name="SharePoint - Finance",
        description="Finance department SharePoint",
        endpoint="https://company.sharepoint.com/sites/finance",
        authentication={"type": "entra_id"},
        capabilities=["read_documents", "search_documents"]
    )


@pytest.fixture
def dynamics_connector():
    """Dynamics 365 connector configuration."""
    return ConnectorConfig(
        connector_id="dynamics_365-0",
        connector_type=ConnectorType.DYNAMICS_365,
        name="Dynamics 365 Finance",
        description="Dynamics 365 Finance module",
        endpoint="https://company.crm.dynamics.com/api/data/v9.2",
        authentication={"type": "entra_id"},
        capabilities=["read_invoices", "create_invoice"]
    )


class TestConnectorConfig:
    """Test connector configuration."""

    def test_config_creation(self, sharepoint_connector):
        """Test connector config creation."""
        assert sharepoint_connector.connector_id == "microsoft_365-0"
        assert sharepoint_connector.connector_type == ConnectorType.MICROSOFT_365
        assert sharepoint_connector.enabled is True
        assert sharepoint_connector.rate_limit == 100

    def test_config_capabilities(self, sharepoint_connector):
        """Test connector capabilities."""
        assert "read_documents" in sharepoint_connector.capabilities
        assert "search_documents" in sharepoint_connector.capabilities


class TestConnectorQuery:
    """Test connector query."""

    def test_query_creation(self):
        """Test query creation."""
        query = ConnectorQuery(
            connector_id="test-connector",
            operation=ConnectorOperation.SEARCH,
            resource_type="documents",
            filters={"department": "finance"},
            limit=50
        )

        assert query.connector_id == "test-connector"
        assert query.operation == ConnectorOperation.SEARCH
        assert query.resource_type == "documents"
        assert query.filters["department"] == "finance"
        assert query.limit == 50

    def test_query_with_sorting(self):
        """Test query with sorting."""
        query = ConnectorQuery(
            connector_id="test",
            operation=ConnectorOperation.LIST,
            resource_type="invoices",
            sort="date_desc",
            limit=100
        )

        assert query.sort == "date_desc"


class TestAzureAIFoundryConnectorClient:
    """Test Azure AI Foundry connector client."""

    async def test_client_initialization(self, connector_client):
        """Test client initialization."""
        assert connector_client.project_connection_string == "test-connection-string"
        assert connector_client.connectors == {}

    async def test_initialize(self, connector_client):
        """Test client initialize."""
        result = await connector_client.initialize()
        # Should succeed even without real Azure connection
        assert result is True

    async def test_register_connector(self, connector_client):
        """Test registering a connector."""
        await connector_client.initialize()

        config = await connector_client.register_connector(
            connector_type=ConnectorType.MICROSOFT_365,
            name="Test SharePoint",
            endpoint="https://test.sharepoint.com",
            authentication={"type": "entra_id"},
            description="Test connector"
        )

        assert config.connector_id
        assert config.name == "Test SharePoint"
        assert config.connector_type == ConnectorType.MICROSOFT_365
        assert config.connector_id in connector_client.connectors

    async def test_register_multiple_connectors(self, connector_client):
        """Test registering multiple connectors."""
        await connector_client.initialize()

        # Register SharePoint
        sp_config = await connector_client.register_connector(
            connector_type=ConnectorType.MICROSOFT_365,
            name="SharePoint",
            endpoint="https://sharepoint.com",
            authentication={"type": "entra_id"}
        )

        # Register Dynamics
        d365_config = await connector_client.register_connector(
            connector_type=ConnectorType.DYNAMICS_365,
            name="Dynamics 365",
            endpoint="https://dynamics.com",
            authentication={"type": "entra_id"}
        )

        assert len(connector_client.connectors) == 2
        assert sp_config.connector_id != d365_config.connector_id

    async def test_list_connectors(self, connector_client):
        """Test listing connectors."""
        await connector_client.initialize()

        # Register some connectors
        await connector_client.register_connector(
            ConnectorType.MICROSOFT_365, "SP1", "https://sp1.com", {"type": "entra_id"}
        )
        await connector_client.register_connector(
            ConnectorType.DYNAMICS_365, "D365", "https://d365.com", {"type": "entra_id"}
        )

        connectors = await connector_client.list_connectors()

        assert len(connectors) == 2

    async def test_get_connector(self, connector_client):
        """Test getting connector by ID."""
        await connector_client.initialize()

        config = await connector_client.register_connector(
            ConnectorType.SALESFORCE, "Salesforce", "https://sf.com", {"type": "oauth2"}
        )

        retrieved = await connector_client.get_connector(config.connector_id)

        assert retrieved is not None
        assert retrieved.connector_id == config.connector_id

    async def test_remove_connector(self, connector_client):
        """Test removing connector."""
        await connector_client.initialize()

        config = await connector_client.register_connector(
            ConnectorType.SAP, "SAP", "https://sap.com", {"type": "oauth2"}
        )

        result = await connector_client.remove_connector(config.connector_id)

        assert result is True
        assert config.connector_id not in connector_client.connectors


class TestMicrosoft365Connector:
    """Test Microsoft 365 connector queries."""

    async def test_query_sharepoint_documents(self, connector_client):
        """Test querying SharePoint documents."""
        await connector_client.initialize()

        # Register SharePoint connector
        sp_config = await connector_client.register_connector(
            ConnectorType.MICROSOFT_365,
            "SharePoint Finance",
            "https://company.sharepoint.com/sites/finance",
            {"type": "entra_id"}
        )

        # Query documents
        query = ConnectorQuery(
            connector_id=sp_config.connector_id,
            operation=ConnectorOperation.SEARCH,
            resource_type="documents",
            filters={"department": "finance", "year": 2024},
            limit=10
        )

        result = await connector_client.query(query)

        assert result.success
        assert result.record_count >= 0
        assert result.data is not None
        assert result.execution_time_ms > 0

    async def test_query_outlook_emails(self, connector_client):
        """Test querying Outlook emails."""
        await connector_client.initialize()

        outlook_config = await connector_client.register_connector(
            ConnectorType.MICROSOFT_365,
            "Outlook",
            "https://outlook.office365.com",
            {"type": "entra_id"}
        )

        query = ConnectorQuery(
            connector_id=outlook_config.connector_id,
            operation=ConnectorOperation.SEARCH,
            resource_type="emails",
            filters={"subject": "invoice"},
            limit=50
        )

        result = await connector_client.query(query)

        assert result.success


class TestDynamics365Connector:
    """Test Dynamics 365 connector queries."""

    async def test_query_invoices(self, connector_client):
        """Test querying Dynamics 365 invoices."""
        await connector_client.initialize()

        d365_config = await connector_client.register_connector(
            ConnectorType.DYNAMICS_365,
            "Dynamics 365 Finance",
            "https://company.crm.dynamics.com/api/data/v9.2",
            {"type": "entra_id"}
        )

        query = ConnectorQuery(
            connector_id=d365_config.connector_id,
            operation=ConnectorOperation.LIST,
            resource_type="invoices",
            filters={"status": "pending_approval"},
            limit=100
        )

        result = await connector_client.query(query)

        assert result.success
        assert result.record_count >= 0

        # Check invoice data structure
        if result.data and len(result.data) > 0:
            invoice = result.data[0]
            assert "invoice_id" in invoice
            assert "amount" in invoice
            assert "vendor_name" in invoice

    async def test_query_customers(self, connector_client):
        """Test querying Dynamics 365 customers."""
        await connector_client.initialize()

        d365_config = await connector_client.register_connector(
            ConnectorType.DYNAMICS_365,
            "Dynamics 365 Sales",
            "https://company.crm.dynamics.com",
            {"type": "entra_id"}
        )

        query = ConnectorQuery(
            connector_id=d365_config.connector_id,
            operation=ConnectorOperation.LIST,
            resource_type="customers",
            limit=50
        )

        result = await connector_client.query(query)

        assert result.success


class TestSAPConnector:
    """Test SAP connector queries."""

    async def test_query_purchase_orders(self, connector_client):
        """Test querying SAP purchase orders."""
        await connector_client.initialize()

        sap_config = await connector_client.register_connector(
            ConnectorType.SAP,
            "SAP ERP",
            "https://sap-erp.company.com",
            {"type": "oauth2"}
        )

        query = ConnectorQuery(
            connector_id=sap_config.connector_id,
            operation=ConnectorOperation.LIST,
            resource_type="purchase_orders",
            filters={"status": "released"},
            limit=25
        )

        result = await connector_client.query(query)

        assert result.success

        if result.data and len(result.data) > 0:
            po = result.data[0]
            assert "po_number" in po
            assert "vendor_name" in po
            assert "total_amount" in po

    async def test_query_materials(self, connector_client):
        """Test querying SAP materials."""
        await connector_client.initialize()

        sap_config = await connector_client.register_connector(
            ConnectorType.SAP,
            "SAP Materials",
            "https://sap.company.com",
            {"type": "oauth2"}
        )

        query = ConnectorQuery(
            connector_id=sap_config.connector_id,
            operation=ConnectorOperation.SEARCH,
            resource_type="materials",
            filters={"material_group": "ROH"},
            limit=100
        )

        result = await connector_client.query(query)

        assert result.success


class TestSalesforceConnector:
    """Test Salesforce connector queries."""

    async def test_query_opportunities(self, connector_client):
        """Test querying Salesforce opportunities."""
        await connector_client.initialize()

        sf_config = await connector_client.register_connector(
            ConnectorType.SALESFORCE,
            "Salesforce",
            "https://company.salesforce.com",
            {"type": "oauth2"}
        )

        query = ConnectorQuery(
            connector_id=sf_config.connector_id,
            operation=ConnectorOperation.LIST,
            resource_type="opportunities",
            filters={"stage": "Proposal/Price Quote"},
            limit=50
        )

        result = await connector_client.query(query)

        assert result.success

    async def test_query_cases(self, connector_client):
        """Test querying Salesforce support cases."""
        await connector_client.initialize()

        sf_config = await connector_client.register_connector(
            ConnectorType.SALESFORCE,
            "Salesforce Service",
            "https://company.salesforce.com",
            {"type": "oauth2"}
        )

        query = ConnectorQuery(
            connector_id=sf_config.connector_id,
            operation=ConnectorOperation.SEARCH,
            resource_type="cases",
            filters={"priority": "High"},
            limit=20
        )

        result = await connector_client.query(query)

        assert result.success


class TestServiceNowConnector:
    """Test ServiceNow connector queries."""

    async def test_query_incidents(self, connector_client):
        """Test querying ServiceNow incidents."""
        await connector_client.initialize()

        snow_config = await connector_client.register_connector(
            ConnectorType.SERVICENOW,
            "ServiceNow",
            "https://company.service-now.com",
            {"type": "oauth2"}
        )

        query = ConnectorQuery(
            connector_id=snow_config.connector_id,
            operation=ConnectorOperation.LIST,
            resource_type="incidents",
            filters={"state": "In Progress"},
            limit=25
        )

        result = await connector_client.query(query)

        assert result.success


class TestConnectorFactories:
    """Test connector factory functions."""

    @patch('src.integrations.azure_ai_foundry_connectors.AzureAIFoundryConnectorClient')
    async def test_create_sharepoint_connector(self, mock_client_class):
        """Test SharePoint connector factory."""
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock()
        mock_client.register_connector = AsyncMock(return_value=MagicMock())
        mock_client_class.return_value = mock_client

        config = await create_sharepoint_connector(
            site_url="https://company.sharepoint.com/sites/finance",
            library="Documents"
        )

        mock_client.initialize.assert_called_once()
        mock_client.register_connector.assert_called_once()

    @patch('src.integrations.azure_ai_foundry_connectors.AzureAIFoundryConnectorClient')
    async def test_create_dynamics_connector(self, mock_client_class):
        """Test Dynamics 365 connector factory."""
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock()
        mock_client.register_connector = AsyncMock(return_value=MagicMock())
        mock_client_class.return_value = mock_client

        config = await create_dynamics_365_connector(
            organization_url="https://company.crm.dynamics.com",
            module="finance"
        )

        mock_client.initialize.assert_called_once()

    @patch('src.integrations.azure_ai_foundry_connectors.AzureAIFoundryConnectorClient')
    async def test_create_sap_connector(self, mock_client_class):
        """Test SAP connector factory."""
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock()
        mock_client.register_connector = AsyncMock(return_value=MagicMock())
        mock_client_class.return_value = mock_client

        config = await create_sap_connector(
            sap_endpoint="https://sap.company.com",
            client_id="100",
            system_id="ERP"
        )

        mock_client.initialize.assert_called_once()


@pytest.mark.integration
class TestConnectorIntegration:
    """Integration tests for connectors."""

    async def test_multi_connector_query(self, connector_client):
        """Test querying multiple connectors."""
        await connector_client.initialize()

        # Register multiple connectors
        sp_config = await connector_client.register_connector(
            ConnectorType.MICROSOFT_365, "SharePoint", "https://sp.com", {"type": "entra_id"}
        )
        d365_config = await connector_client.register_connector(
            ConnectorType.DYNAMICS_365, "Dynamics", "https://d365.com", {"type": "entra_id"}
        )

        # Query both
        sp_result = await connector_client.query(ConnectorQuery(
            connector_id=sp_config.connector_id,
            operation=ConnectorOperation.SEARCH,
            resource_type="documents",
            limit=10
        ))

        d365_result = await connector_client.query(ConnectorQuery(
            connector_id=d365_config.connector_id,
            operation=ConnectorOperation.LIST,
            resource_type="invoices",
            limit=10
        ))

        assert sp_result.success
        assert d365_result.success

    async def test_error_handling_unknown_connector(self, connector_client):
        """Test error handling for unknown connector."""
        await connector_client.initialize()

        query = ConnectorQuery(
            connector_id="non-existent-connector",
            operation=ConnectorOperation.READ,
            resource_type="data"
        )

        result = await connector_client.query(query)

        assert result.success is False
        assert len(result.errors) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
