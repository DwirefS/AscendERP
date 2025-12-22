"""
Tool Discovery Agent - Meta-Agent for API Exploration and Discovery.

This agent can autonomously explore APIs and discover integration opportunities:
1. Fetch and parse OpenAPI/Swagger specifications
2. Probe API endpoints to understand structure
3. Infer schemas from actual API responses
4. Discover authentication requirements
5. Map operations to agent capabilities
6. Feed discovered APIs to IntegrationBuilderAgent

This enables agents to find and integrate with new services autonomously.
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse
import json
import asyncio
import structlog
import aiohttp
import yaml
from bs4 import BeautifulSoup

from src.core.agent.base import BaseAgent, AgentConfig, ExecutionContext
from src.core.memory.substrate import MemorySubstrate
from src.core.inference.llm_client import LLMClient

logger = structlog.get_logger()


@dataclass
class DiscoveryRequest:
    """Request to discover an API."""
    target_url: str  # Base URL or documentation URL
    discovery_mode: str = "auto"  # "auto", "openapi", "swagger", "probe", "crawl"
    max_endpoints: int = 50
    include_authentication: bool = True
    follow_links: bool = True
    max_depth: int = 3


@dataclass
class APIEndpoint:
    """Discovered API endpoint."""
    path: str
    method: str
    description: str
    parameters: List[Dict[str, Any]]
    request_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    auth_required: bool = True
    auth_type: Optional[str] = None


@dataclass
class DiscoveredAPI:
    """A discovered API with all its endpoints."""
    api_id: str
    api_name: str
    base_url: str
    description: str
    endpoints: List[APIEndpoint]
    auth_config: Dict[str, Any]
    schema_format: str
    discovered_at: datetime
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolDiscoveryAgent(BaseAgent):
    """
    Meta-agent that discovers APIs and their capabilities autonomously.

    Uses multiple strategies:
    - OpenAPI/Swagger spec parsing
    - Endpoint probing and schema inference
    - Documentation crawling with LLM extraction
    - Response pattern analysis

    Discovered APIs can be automatically fed to IntegrationBuilderAgent
    for tool generation.
    """

    def __init__(
        self,
        config: AgentConfig,
        memory: MemorySubstrate,
        llm_client: LLMClient,
        schema_model: str = "gpt-4o-mini"  # Lighter model for schema inference
    ):
        super().__init__(config, memory, llm_client)
        self.schema_model = schema_model
        self._discovered_apis: Dict[str, DiscoveredAPI] = {}
        self._visited_urls: Set[str] = set()

    async def perceive(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Perceive the discovery request.
        Identify the discovery strategy based on target.
        """
        logger.info("tool_discovery_perceiving", agent_id=self.config.agent_id)

        request_data = context.input_data

        discovery_req = DiscoveryRequest(
            target_url=request_data["target_url"],
            discovery_mode=request_data.get("discovery_mode", "auto"),
            max_endpoints=request_data.get("max_endpoints", 50),
            include_authentication=request_data.get("include_authentication", True),
            follow_links=request_data.get("follow_links", True),
            max_depth=request_data.get("max_depth", 3)
        )

        # Determine discovery strategy
        strategy = await self._determine_strategy(discovery_req)

        return {
            "discovery_request": discovery_req,
            "strategy": strategy,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def retrieve(self, perception: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Retrieve similar APIs from memory.
        Learn from past discoveries.
        """
        logger.info("tool_discovery_retrieving")

        discovery_req = perception["discovery_request"]

        # Search for similar APIs
        domain = urlparse(discovery_req.target_url).netloc
        query = f"API discovery for {domain}"

        similar_apis = await self.memory.retrieve_semantic(
            query=query,
            limit=5,
            threshold=0.6
        )

        # Get successful discovery patterns
        patterns = await self.memory.get_procedural_patterns(
            agent_id=self.config.agent_id
        )

        return {
            "similar_apis": similar_apis,
            "discovery_patterns": patterns,
            "strategy": perception["strategy"],
            "discovery_request": discovery_req
        }

    async def reason(self, context_data: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Reason about how to discover the API.
        Execute discovery strategy and parse results.
        """
        logger.info("tool_discovery_reasoning")

        discovery_req = context_data["discovery_request"]
        strategy = context_data["strategy"]

        endpoints = []
        api_metadata = {}

        try:
            if strategy == "openapi" or strategy == "swagger":
                # Parse OpenAPI/Swagger specification
                endpoints, api_metadata = await self._parse_openapi_spec(discovery_req.target_url)

            elif strategy == "probe":
                # Probe API endpoints to infer structure
                endpoints, api_metadata = await self._probe_api(discovery_req)

            elif strategy == "crawl":
                # Crawl documentation and extract with LLM
                endpoints, api_metadata = await self._crawl_documentation(discovery_req)

            elif strategy == "auto":
                # Try all strategies in order
                try:
                    endpoints, api_metadata = await self._parse_openapi_spec(discovery_req.target_url)
                except Exception as e:
                    logger.info("openapi_failed_trying_probe", error=str(e))
                    try:
                        endpoints, api_metadata = await self._probe_api(discovery_req)
                    except Exception as e2:
                        logger.info("probe_failed_trying_crawl", error=str(e2))
                        endpoints, api_metadata = await self._crawl_documentation(discovery_req)

        except Exception as e:
            logger.error("discovery_failed", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "endpoints": [],
                "api_metadata": {}
            }

        # Infer authentication requirements
        auth_config = await self._infer_authentication(
            endpoints=endpoints,
            metadata=api_metadata,
            base_url=discovery_req.target_url
        )

        # Calculate confidence score
        confidence = self._calculate_confidence(endpoints, api_metadata, strategy)

        return {
            "success": True,
            "endpoints": endpoints,
            "api_metadata": api_metadata,
            "auth_config": auth_config,
            "confidence_score": confidence,
            "strategy_used": strategy,
            "discovery_request": discovery_req
        }

    async def execute(self, reasoning: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute the discovery process.
        Create DiscoveredAPI object and register it.
        """
        logger.info("tool_discovery_executing")

        if not reasoning.get("success"):
            return {
                "success": False,
                "error": reasoning.get("error", "Discovery failed")
            }

        discovery_req = reasoning["discovery_request"]
        endpoints = reasoning["endpoints"]
        api_metadata = reasoning["api_metadata"]
        auth_config = reasoning["auth_config"]

        # Create DiscoveredAPI object
        api_id = f"api_{urlparse(discovery_req.target_url).netloc}_{datetime.utcnow().timestamp()}"

        discovered_api = DiscoveredAPI(
            api_id=api_id,
            api_name=api_metadata.get("name", urlparse(discovery_req.target_url).netloc),
            base_url=api_metadata.get("base_url", discovery_req.target_url),
            description=api_metadata.get("description", ""),
            endpoints=endpoints,
            auth_config=auth_config,
            schema_format=reasoning.get("strategy_used", "unknown"),
            discovered_at=datetime.utcnow(),
            confidence_score=reasoning["confidence_score"],
            metadata=api_metadata
        )

        self._discovered_apis[api_id] = discovered_api

        logger.info(
            "api_discovered_successfully",
            api_id=api_id,
            endpoint_count=len(endpoints),
            confidence=reasoning["confidence_score"]
        )

        # Prepare integration suggestions
        integration_suggestions = await self._suggest_integrations(discovered_api)

        return {
            "success": True,
            "api_id": api_id,
            "api_name": discovered_api.api_name,
            "endpoint_count": len(endpoints),
            "confidence_score": discovered_api.confidence_score,
            "auth_type": auth_config.get("type", "unknown"),
            "integration_suggestions": integration_suggestions,
            "discovered_api": discovered_api
        }

    async def verify(self, result: Dict[str, Any], context: ExecutionContext) -> bool:
        """Verify the API was discovered successfully."""
        return (
            result.get("success", False) and
            result.get("endpoint_count", 0) > 0 and
            result.get("confidence_score", 0) > 0.5
        )

    async def learn(self, trace: Dict[str, Any], context: ExecutionContext):
        """
        Learn from successful API discoveries.
        Store patterns for future use.
        """
        if trace.get("success") and trace.get("confidence_score", 0) > 0.7:
            discovered_api = trace.get("discovered_api")

            if discovered_api:
                # Store successful discovery pattern
                pattern_data = {
                    "api_name": discovered_api.api_name,
                    "strategy": discovered_api.schema_format,
                    "endpoint_count": len(discovered_api.endpoints),
                    "auth_type": discovered_api.auth_config.get("type"),
                    "confidence": discovered_api.confidence_score
                }

                await self.memory.store_procedural(
                    agent_id=self.config.agent_id,
                    pattern_name=f"discovery_{discovered_api.api_name}",
                    pattern_data=pattern_data,
                    metadata={"domain": "api_discovery", "created_at": datetime.utcnow().isoformat()}
                )

                # Store API details in semantic memory for retrieval
                api_description = f"API: {discovered_api.api_name}. {discovered_api.description}. Endpoints: {', '.join([ep.path for ep in discovered_api.endpoints[:10]])}"

                await self.memory.store_episodic(
                    agent_id=self.config.agent_id,
                    content=api_description,
                    metadata={
                        "type": "api_discovery",
                        "api_id": discovered_api.api_id,
                        "confidence": discovered_api.confidence_score
                    }
                )

                logger.info("discovery_pattern_learned", api_name=discovered_api.api_name)

    # Discovery Strategy Methods

    async def _determine_strategy(self, request: DiscoveryRequest) -> str:
        """Determine the best discovery strategy for the target."""
        if request.discovery_mode != "auto":
            return request.discovery_mode

        url = request.target_url.lower()

        # Check for OpenAPI/Swagger indicators
        if any(indicator in url for indicator in ["swagger", "openapi", "api-docs", "v2/api-docs", "v3/api-docs"]):
            return "openapi"

        # Check for API base URL
        if any(indicator in url for indicator in ["/api/", "/v1/", "/v2/", "/rest/"]):
            return "probe"

        # Default to documentation crawling
        return "crawl"

    async def _parse_openapi_spec(self, spec_url: str) -> tuple[List[APIEndpoint], Dict[str, Any]]:
        """Parse OpenAPI/Swagger specification."""
        logger.info("parsing_openapi_spec", url=spec_url)

        async with aiohttp.ClientSession() as session:
            async with session.get(spec_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to fetch spec: HTTP {resp.status}")

                content_type = resp.headers.get("Content-Type", "")

                if "json" in content_type:
                    spec = await resp.json()
                elif "yaml" in content_type or spec_url.endswith((".yaml", ".yml")):
                    text = await resp.text()
                    spec = yaml.safe_load(text)
                else:
                    text = await resp.text()
                    try:
                        spec = json.loads(text)
                    except:
                        spec = yaml.safe_load(text)

        # Extract metadata
        api_metadata = {
            "name": spec.get("info", {}).get("title", "Unknown API"),
            "description": spec.get("info", {}).get("description", ""),
            "version": spec.get("info", {}).get("version", "1.0"),
            "base_url": spec.get("servers", [{}])[0].get("url", "") if "servers" in spec else spec.get("basePath", "")
        }

        # Parse endpoints
        endpoints = []
        paths = spec.get("paths", {})

        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    continue

                # Extract parameters
                parameters = []
                for param in operation.get("parameters", []):
                    parameters.append({
                        "name": param.get("name"),
                        "in": param.get("in"),  # query, header, path
                        "required": param.get("required", False),
                        "type": param.get("type", param.get("schema", {}).get("type", "string")),
                        "description": param.get("description", "")
                    })

                # Extract request body schema
                request_schema = None
                if "requestBody" in operation:
                    content = operation["requestBody"].get("content", {})
                    if "application/json" in content:
                        request_schema = content["application/json"].get("schema")

                # Extract response schema
                response_schema = None
                responses = operation.get("responses", {})
                if "200" in responses:
                    content = responses["200"].get("content", {})
                    if "application/json" in content:
                        response_schema = content["application/json"].get("schema")

                endpoint = APIEndpoint(
                    path=path,
                    method=method.upper(),
                    description=operation.get("summary", operation.get("description", "")),
                    parameters=parameters,
                    request_schema=request_schema,
                    response_schema=response_schema,
                    auth_required="security" in operation or "security" in spec,
                    auth_type=None  # Will be inferred later
                )

                endpoints.append(endpoint)

        logger.info("openapi_parsed", endpoint_count=len(endpoints))
        return endpoints, api_metadata

    async def _probe_api(self, request: DiscoveryRequest) -> tuple[List[APIEndpoint], Dict[str, Any]]:
        """Probe API endpoints to infer structure."""
        logger.info("probing_api", url=request.target_url)

        # Common API path patterns to try
        common_paths = [
            "/api/v1/",
            "/api/v2/",
            "/api/",
            "/v1/",
            "/v2/",
            "/rest/",
            "/graphql",
        ]

        endpoints = []
        base_url = request.target_url.rstrip("/")

        async with aiohttp.ClientSession() as session:
            for path in common_paths:
                test_url = urljoin(base_url, path)

                try:
                    async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            # Found an API endpoint
                            content = await resp.text()

                            # Try to parse as JSON
                            try:
                                data = json.loads(content)

                                # Infer schema from response
                                response_schema = self._infer_schema_from_data(data)

                                endpoint = APIEndpoint(
                                    path=path,
                                    method="GET",
                                    description=f"Discovered endpoint at {path}",
                                    parameters=[],
                                    response_schema=response_schema,
                                    auth_required=False  # Successful GET suggests no auth
                                )

                                endpoints.append(endpoint)

                            except json.JSONDecodeError:
                                # Not JSON, might be HTML or other format
                                pass

                except Exception as e:
                    logger.debug("probe_failed", path=path, error=str(e))
                    continue

        api_metadata = {
            "name": urlparse(base_url).netloc,
            "description": f"API discovered via probing at {base_url}",
            "base_url": base_url
        }

        logger.info("probing_complete", endpoint_count=len(endpoints))
        return endpoints, api_metadata

    async def _crawl_documentation(self, request: DiscoveryRequest) -> tuple[List[APIEndpoint], Dict[str, Any]]:
        """Crawl API documentation and extract with LLM."""
        logger.info("crawling_documentation", url=request.target_url)

        async with aiohttp.ClientSession() as session:
            async with session.get(request.target_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to fetch documentation: HTTP {resp.status}")

                html_content = await resp.text()

        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        text_content = soup.get_text(separator="\n", strip=True)[:10000]  # Limit to 10K chars

        # Use LLM to extract API information
        prompt = f"""Extract API endpoint information from this documentation:

{text_content}

Identify:
1. API name and description
2. Base URL
3. Available endpoints (paths and HTTP methods)
4. Parameters for each endpoint
5. Authentication requirements

Return a JSON structure with this information."""

        response = await self.llm_client.generate(
            prompt=prompt,
            model=self.schema_model,
            temperature=0.1,
            max_tokens=2000
        )

        # Parse LLM response
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            extracted_data = json.loads(json_str)
        except:
            logger.error("llm_extraction_failed")
            extracted_data = {"endpoints": []}

        # Convert to APIEndpoint objects
        endpoints = []
        for ep_data in extracted_data.get("endpoints", []):
            endpoint = APIEndpoint(
                path=ep_data.get("path", "/"),
                method=ep_data.get("method", "GET"),
                description=ep_data.get("description", ""),
                parameters=ep_data.get("parameters", []),
                auth_required=ep_data.get("auth_required", True)
            )
            endpoints.append(endpoint)

        api_metadata = {
            "name": extracted_data.get("name", "Unknown API"),
            "description": extracted_data.get("description", ""),
            "base_url": extracted_data.get("base_url", request.target_url)
        }

        logger.info("crawling_complete", endpoint_count=len(endpoints))
        return endpoints, api_metadata

    def _infer_schema_from_data(self, data: Any) -> Dict[str, Any]:
        """Infer JSON schema from actual data."""
        if isinstance(data, dict):
            properties = {}
            for key, value in data.items():
                properties[key] = self._infer_schema_from_data(value)

            return {
                "type": "object",
                "properties": properties
            }

        elif isinstance(data, list):
            if data:
                return {
                    "type": "array",
                    "items": self._infer_schema_from_data(data[0])
                }
            else:
                return {"type": "array"}

        elif isinstance(data, str):
            return {"type": "string"}

        elif isinstance(data, bool):
            return {"type": "boolean"}

        elif isinstance(data, int):
            return {"type": "integer"}

        elif isinstance(data, float):
            return {"type": "number"}

        else:
            return {"type": "string"}

    async def _infer_authentication(
        self,
        endpoints: List[APIEndpoint],
        metadata: Dict[str, Any],
        base_url: str
    ) -> Dict[str, Any]:
        """Infer authentication requirements."""

        # Check if any endpoint requires auth
        auth_required = any(ep.auth_required for ep in endpoints)

        if not auth_required:
            return {"type": "none"}

        # Common auth patterns
        if "oauth" in base_url.lower() or "oauth" in str(metadata).lower():
            return {"type": "oauth2", "flow": "client_credentials"}

        if "bearer" in str(metadata).lower():
            return {"type": "bearer"}

        # Default to API key
        return {"type": "api_key", "location": "header", "name": "X-API-Key"}

    def _calculate_confidence(
        self,
        endpoints: List[APIEndpoint],
        metadata: Dict[str, Any],
        strategy: str
    ) -> float:
        """Calculate confidence score for the discovery."""
        score = 0.0

        # Endpoint count (max 0.4)
        endpoint_factor = min(len(endpoints) / 20, 1.0) * 0.4
        score += endpoint_factor

        # Strategy reliability (max 0.3)
        strategy_scores = {
            "openapi": 0.3,
            "swagger": 0.3,
            "probe": 0.2,
            "crawl": 0.15,
            "auto": 0.25
        }
        score += strategy_scores.get(strategy, 0.1)

        # Metadata completeness (max 0.3)
        if metadata.get("name"):
            score += 0.1
        if metadata.get("description"):
            score += 0.1
        if metadata.get("base_url"):
            score += 0.1

        return min(score, 1.0)

    async def _suggest_integrations(self, api: DiscoveredAPI) -> List[Dict[str, Any]]:
        """Suggest which operations should be integrated."""
        suggestions = []

        # Group endpoints by common patterns
        for endpoint in api.endpoints[:10]:  # Top 10 endpoints
            suggestions.append({
                "operation_name": f"{endpoint.method.lower()}_{endpoint.path.replace('/', '_').strip('_')}",
                "endpoint": endpoint.path,
                "method": endpoint.method,
                "description": endpoint.description,
                "priority": "high" if endpoint.method in ["GET", "POST"] else "medium"
            })

        return suggestions

    async def get_discovered_api(self, api_id: str) -> Optional[DiscoveredAPI]:
        """Retrieve a discovered API by ID."""
        return self._discovered_apis.get(api_id)

    async def list_discovered_apis(self) -> List[DiscoveredAPI]:
        """List all discovered APIs."""
        return list(self._discovered_apis.values())


# Factory function
def create_tool_discovery_agent(
    tenant_id: str,
    memory: MemorySubstrate,
    llm_client: LLMClient
) -> ToolDiscoveryAgent:
    """Create a ToolDiscovery agent."""
    config = AgentConfig(
        agent_id=f"tool_discovery_{tenant_id}",
        agent_type="meta.tool_discovery",
        tenant_id=tenant_id,
        capabilities=[
            "parse_openapi",
            "probe_endpoints",
            "crawl_documentation",
            "infer_schemas",
            "discover_authentication"
        ]
    )

    return ToolDiscoveryAgent(
        config=config,
        memory=memory,
        llm_client=llm_client,
        schema_model="gpt-4o-mini"  # Efficient for schema inference
    )
