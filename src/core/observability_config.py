"""
ANTS Observability Configuration

Centralized configuration for OpenTelemetry, Azure Monitor, and development tools.
Based on Microsoft Agent Framework observability patterns.

Reference: https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/observability
"""

import os
import logging
from typing import Optional

from src.core.observability import (
    configure_otel_providers,
    configure_azure_monitor,
    enable_instrumentation
)

logger = logging.getLogger(__name__)


def setup_observability(
    environment: str = "development",
    enable_azure_monitor: bool = False,
    enable_aspire_dashboard: bool = False,
    enable_console_output: bool = False
) -> None:
    """
    Configure ANTS observability stack.

    Supports multiple deployment scenarios:
    1. Development: Aspire Dashboard + Console
    2. Staging/Production: Azure Monitor + OTLP
    3. Testing: Console only

    Args:
        environment: Deployment environment (development, staging, production)
        enable_azure_monitor: Enable Azure Monitor (Application Insights)
        enable_aspire_dashboard: Enable local Aspire Dashboard
        enable_console_output: Enable console exporters for debugging

    Environment Variables (precedence over parameters):
        ENVIRONMENT: development | staging | production
        ENABLE_INSTRUMENTATION: Enable all telemetry (default: false)
        ENABLE_AZURE_MONITOR: Enable Azure Monitor integration
        ENABLE_ASPIRE_DASHBOARD: Use Aspire Dashboard for development
        ENABLE_CONSOLE_EXPORTERS: Output telemetry to console
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4317)
        APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Monitor connection string

    Example Usage:
        # Development with Aspire Dashboard
        setup_observability(environment="development", enable_aspire_dashboard=True)

        # Production with Azure Monitor
        setup_observability(environment="production", enable_azure_monitor=True)

        # Testing with console output
        setup_observability(environment="test", enable_console_output=True)

    Docker Compose Example for Aspire Dashboard:
        services:
          aspire-dashboard:
            image: mcr.microsoft.com/dotnet/aspire-dashboard:latest
            ports:
              - "18888:18888"  # Web UI
              - "4317:18889"   # OTLP endpoint
            environment:
              - ASPNETCORE_URLS=http://+:18888

    Azure Monitor Setup:
        1. Create Application Insights resource in Azure Portal
        2. Copy connection string
        3. Set APPLICATIONINSIGHTS_CONNECTION_STRING environment variable
        4. Call: setup_observability(enable_azure_monitor=True)
    """
    # Check if instrumentation is globally enabled
    if not os.getenv("ENABLE_INSTRUMENTATION", "false").lower() == "true":
        logger.info("Observability disabled. Set ENABLE_INSTRUMENTATION=true to enable.")
        return

    logger.info(f"Configuring ANTS observability for {environment} environment")

    # Determine configuration from environment variables (takes precedence)
    env_azure_monitor = os.getenv("ENABLE_AZURE_MONITOR", "false").lower() == "true"
    env_aspire = os.getenv("ENABLE_ASPIRE_DASHBOARD", "false").lower() == "true"
    env_console = os.getenv("ENABLE_CONSOLE_EXPORTERS", "false").lower() == "true"

    enable_azure_monitor = env_azure_monitor or enable_azure_monitor
    enable_aspire_dashboard = env_aspire or enable_aspire_dashboard
    enable_console_output = env_console or enable_console_output

    # Configure based on environment
    if environment == "development":
        enable_console_output = True  # Always enable console in dev
        if not enable_aspire_dashboard and not os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
            logger.info("Development mode: Using Aspire Dashboard at http://localhost:4317")
            os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    elif environment in ["staging", "production"]:
        if not enable_azure_monitor:
            logger.warning(
                f"{environment} environment without Azure Monitor. "
                "Set ENABLE_AZURE_MONITOR=true for production observability."
            )

    # Configure Azure Monitor (if enabled)
    if enable_azure_monitor:
        try:
            configure_azure_monitor(enable_live_metrics=True)
            logger.info("Azure Monitor configured successfully")
        except Exception as e:
            logger.error(f"Azure Monitor configuration failed: {e}")

    # Configure OpenTelemetry
    try:
        configure_otel_providers(enable_console=enable_console_output)

        # Enable automatic instrumentation
        enable_instrumentation()

        logger.info(
            "Observability configured",
            azure_monitor=enable_azure_monitor,
            aspire_dashboard=enable_aspire_dashboard,
            console_output=enable_console_output
        )

    except Exception as e:
        logger.error(f"Observability configuration failed: {e}")


def start_devui_server(
    host: str = "localhost",
    port: int = 8090,
    background: bool = False
) -> Optional['DevUIServer']:
    """
    Start DevUI visual debugging server.

    Based on Microsoft Agent Framework DevUI pattern.
    Reference: https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/devui

    Args:
        host: Server host (default: localhost)
        port: Server port (default: 8090)
        background: Run in background thread (default: False)

    Returns:
        DevUIServer instance if started, None otherwise

    Environment Variables:
        ANTS_DEVUI_ENABLED: Enable DevUI server (default: false)
        DEVUI_HOST: Override host
        DEVUI_PORT: Override port

    Usage:
        # Start DevUI server
        devui = start_devui_server()

        # Then open browser to: http://localhost:8090
        # Agents will automatically stream reasoning steps to DevUI
    """
    devui_enabled = os.getenv("ANTS_DEVUI_ENABLED", "false").lower() == "true"

    if not devui_enabled:
        logger.info("DevUI disabled. Set ANTS_DEVUI_ENABLED=true to enable.")
        return None

    try:
        from src.devtools.devui_server import DevUIServer

        # Override from environment
        host = os.getenv("DEVUI_HOST", host)
        port = int(os.getenv("DEVUI_PORT", port))

        server = DevUIServer(host=host, port=port)

        if background:
            import threading
            thread = threading.Thread(target=server.start_sync, daemon=True)
            thread.start()
            logger.info(f"DevUI server started in background at http://{host}:{port}")
        else:
            logger.info(f"Starting DevUI server at http://{host}:{port}")
            # Blocking call
            server.start_sync()

        return server

    except ImportError:
        logger.error("DevUI not available. Install with: pip install fastapi uvicorn websockets")
        return None


def get_aspire_dashboard_url() -> str:
    """
    Get Aspire Dashboard URL for local development.

    Returns URL where telemetry can be viewed in real-time.

    Returns:
        Aspire Dashboard web UI URL (default: http://localhost:18888)
    """
    return os.getenv("ASPIRE_DASHBOARD_URL", "http://localhost:18888")


def print_observability_status():
    """
    Print current observability configuration status.

    Useful for debugging and confirming setup.
    """
    print("=" * 60)
    print("ANTS Observability Status")
    print("=" * 60)

    instrumentation = os.getenv("ENABLE_INSTRUMENTATION", "false")
    print(f"Instrumentation: {instrumentation}")

    if instrumentation.lower() == "true":
        print(f"  Azure Monitor: {os.getenv('ENABLE_AZURE_MONITOR', 'false')}")
        print(f"  Console Output: {os.getenv('ENABLE_CONSOLE_EXPORTERS', 'false')}")
        print(f"  Sensitive Data: {os.getenv('ENABLE_SENSITIVE_DATA', 'false')}")
        print(f"  OTLP Endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'not set')}")

        if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
            print("  Application Insights: Configured ✓")
        else:
            print("  Application Insights: Not configured")

    devui = os.getenv("ANTS_DEVUI_ENABLED", "false")
    print(f"\nDevUI: {devui}")
    if devui.lower() == "true":
        port = os.getenv("DEVUI_PORT", "8090")
        print(f"  URL: http://localhost:{port}")

    print("=" * 60)
