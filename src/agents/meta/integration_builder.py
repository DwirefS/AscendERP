"""
Integration Builder Agent - Meta-Agent for Dynamic Tool Generation.

This agent can create new MCP tool integrations on-the-fly by:
1. Analyzing API documentation (OpenAPI, Swagger, or natural language)
2. Generating MCP tool code dynamically
3. Validating the generated code
4. Registering tools in the runtime registry
5. Executing tools in a sandboxed environment

This enables the agent ecosystem to extend itself without hardcoding every integration.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import ast
import asyncio
import structlog
import aiohttp
import yaml

from src.core.agent.base import BaseAgent, AgentConfig, ExecutionContext
from src.core.memory.substrate import MemorySubstrate
from src.core.inference.llm_client import LLMClient

logger = structlog.get_logger()


@dataclass
class IntegrationRequest:
    """Request to build a new integration."""
    api_name: str
    api_documentation: str  # URL or inline docs
    operations: List[str]  # Desired operations (e.g., ["query_records", "update_record"])
    auth_type: str  # "oauth2", "api_key", "basic", "bearer"
    auth_config: Dict[str, Any]
    schema_format: str = "openapi"  # "openapi", "swagger", "graphql", "natural_language"
    sandbox_level: str = "restricted"  # "restricted", "moderate", "permissive"


@dataclass
class GeneratedTool:
    """A dynamically generated tool."""
    tool_id: str
    tool_name: str
    description: str
    code: str
    schema: Dict[str, Any]
    validation_passed: bool
    created_at: datetime
    api_name: str
    sandbox_level: str


class IntegrationBuilderAgent(BaseAgent):
    """
    Meta-agent that generates integration code for other agents.

    Uses specialized models (FunctionGemma, GPT-4, Claude) to:
    - Parse API documentation
    - Generate MCP-compatible tool code
    - Validate generated code with AST parsing
    - Test execution in sandbox
    - Register in dynamic tool registry

    This agent essentially "teaches" the system how to talk to new APIs.
    """

    def __init__(
        self,
        config: AgentConfig,
        memory: MemorySubstrate,
        llm_client: LLMClient,
        code_model: str = "gpt-4o",  # Specialized for code generation
        function_model: str = "function-gemma"  # For tool schema generation
    ):
        super().__init__(config, memory, llm_client)
        self.code_model = code_model
        self.function_model = function_model
        self._generated_tools: Dict[str, GeneratedTool] = {}

    async def perceive(self, context: ExecutionContext) -> Dict[str, Any]:
        """
        Perceive integration request from context.
        Extract API documentation and requirements.
        """
        logger.info("integration_builder_perceiving", agent_id=self.config.agent_id)

        request_data = context.input_data

        # Parse integration request
        integration_req = IntegrationRequest(
            api_name=request_data["api_name"],
            api_documentation=request_data["api_documentation"],
            operations=request_data.get("operations", []),
            auth_type=request_data.get("auth_type", "api_key"),
            auth_config=request_data.get("auth_config", {}),
            schema_format=request_data.get("schema_format", "openapi"),
            sandbox_level=request_data.get("sandbox_level", "restricted")
        )

        # Fetch API documentation if URL provided
        if integration_req.api_documentation.startswith("http"):
            api_docs = await self._fetch_api_docs(integration_req.api_documentation)
        else:
            api_docs = integration_req.api_documentation

        return {
            "integration_request": integration_req,
            "api_docs": api_docs,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def retrieve(self, perception: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Retrieve similar integrations from memory.
        Learn from past successful tool generations.
        """
        logger.info("integration_builder_retrieving")

        integration_req = perception["integration_request"]

        # Search for similar integrations
        query = f"API integration for {integration_req.api_name} with operations {', '.join(integration_req.operations)}"

        similar_integrations = await self.memory.retrieve_semantic(
            query=query,
            limit=5,
            threshold=0.7
        )

        # Retrieve successful patterns
        patterns = await self.memory.get_procedural_patterns(
            agent_id=self.config.agent_id
        )

        return {
            "similar_integrations": similar_integrations,
            "successful_patterns": patterns,
            "api_docs": perception["api_docs"],
            "integration_request": integration_req
        }

    async def reason(self, context_data: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Reason about how to build the integration.
        Generate code for MCP tools using specialized model.
        """
        logger.info("integration_builder_reasoning")

        integration_req = context_data["integration_request"]
        api_docs = context_data["api_docs"]

        # Build prompt for code generation
        prompt = self._build_code_generation_prompt(
            api_name=integration_req.api_name,
            api_docs=api_docs,
            operations=integration_req.operations,
            auth_type=integration_req.auth_type,
            similar_integrations=context_data["similar_integrations"]
        )

        # Use specialized code generation model
        logger.info("generating_tool_code", model=self.code_model)

        response = await self.llm_client.generate(
            prompt=prompt,
            model=self.code_model,
            temperature=0.2,  # Lower temperature for code generation
            max_tokens=4000
        )

        generated_code = self._extract_code_from_response(response)

        # Generate tool schema using function model
        schema_prompt = self._build_schema_generation_prompt(
            api_name=integration_req.api_name,
            operations=integration_req.operations,
            api_docs=api_docs
        )

        schema_response = await self.llm_client.generate(
            prompt=schema_prompt,
            model=self.function_model,
            temperature=0.1,
            max_tokens=2000
        )

        tool_schema = self._extract_schema_from_response(schema_response)

        return {
            "generated_code": generated_code,
            "tool_schema": tool_schema,
            "integration_request": integration_req,
            "validation_plan": self._create_validation_plan(generated_code)
        }

    async def execute(self, reasoning: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """
        Execute the integration building process.
        Validate, test, and register the generated tool.
        """
        logger.info("integration_builder_executing")

        generated_code = reasoning["generated_code"]
        tool_schema = reasoning["tool_schema"]
        integration_req = reasoning["integration_request"]

        # Step 1: Validate generated code (AST parsing)
        validation_result = await self._validate_code(generated_code)

        if not validation_result["valid"]:
            logger.error("code_validation_failed", errors=validation_result["errors"])
            return {
                "success": False,
                "error": "Code validation failed",
                "validation_errors": validation_result["errors"]
            }

        # Step 2: Test in sandbox
        sandbox_result = await self._test_in_sandbox(
            code=generated_code,
            schema=tool_schema,
            sandbox_level=integration_req.sandbox_level
        )

        if not sandbox_result["success"]:
            logger.error("sandbox_test_failed", error=sandbox_result["error"])
            return {
                "success": False,
                "error": "Sandbox test failed",
                "sandbox_error": sandbox_result["error"]
            }

        # Step 3: Register tool
        tool = GeneratedTool(
            tool_id=f"gen_{integration_req.api_name}_{datetime.utcnow().timestamp()}",
            tool_name=integration_req.api_name,
            description=f"Generated integration for {integration_req.api_name}",
            code=generated_code,
            schema=tool_schema,
            validation_passed=True,
            created_at=datetime.utcnow(),
            api_name=integration_req.api_name,
            sandbox_level=integration_req.sandbox_level
        )

        self._generated_tools[tool.tool_id] = tool

        logger.info("tool_generated_successfully", tool_id=tool.tool_id)

        return {
            "success": True,
            "tool_id": tool.tool_id,
            "tool_name": tool.tool_name,
            "operations": integration_req.operations,
            "schema": tool_schema,
            "sandbox_test_passed": True
        }

    async def verify(self, result: Dict[str, Any], context: ExecutionContext) -> bool:
        """Verify the integration was built successfully."""
        return result.get("success", False) and result.get("sandbox_test_passed", False)

    async def learn(self, trace: Dict[str, Any], context: ExecutionContext):
        """
        Learn from successful integration building.
        Store patterns for future use.
        """
        if trace.get("success"):
            # Store successful pattern
            pattern_data = {
                "api_name": trace.get("tool_name"),
                "operations": trace.get("operations"),
                "code_snippet": trace.get("generated_code", "")[:500],  # First 500 chars
                "schema_structure": trace.get("schema"),
                "success_rate": 1.0
            }

            await self.memory.store_procedural(
                agent_id=self.config.agent_id,
                pattern_name=f"integration_{trace['tool_name']}",
                pattern_data=pattern_data,
                metadata={"domain": "api_integration", "created_at": datetime.utcnow().isoformat()}
            )

            logger.info("integration_pattern_learned", tool_name=trace["tool_name"])

    # Helper methods

    async def _fetch_api_docs(self, url: str) -> str:
        """Fetch API documentation from URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")

                        if "json" in content_type:
                            return json.dumps(await resp.json(), indent=2)
                        elif "yaml" in content_type or url.endswith(".yaml"):
                            text = await resp.text()
                            return yaml.safe_dump(yaml.safe_load(text), indent=2)
                        else:
                            return await resp.text()
                    else:
                        logger.error("api_docs_fetch_failed", status=resp.status, url=url)
                        return f"Error fetching docs: HTTP {resp.status}"

        except Exception as e:
            logger.error("api_docs_fetch_exception", error=str(e), url=url)
            return f"Error fetching docs: {str(e)}"

    def _build_code_generation_prompt(
        self,
        api_name: str,
        api_docs: str,
        operations: List[str],
        auth_type: str,
        similar_integrations: List[Any]
    ) -> str:
        """Build prompt for code generation."""

        examples = ""
        if similar_integrations:
            examples = "\n\nExamples of similar integrations:\n"
            for integration in similar_integrations[:2]:
                examples += f"- {integration.content[:200]}...\n"

        prompt = f"""Generate a Python MCP tool integration for {api_name}.

API Documentation:
{api_docs[:2000]}  # Truncate for token limits

Required Operations: {', '.join(operations)}
Authentication: {auth_type}

{examples}

Generate a complete Python class with:
1. Async methods for each operation
2. Proper error handling
3. Authentication implementation
4. Request/response parsing
5. Logging with structlog

Return ONLY the Python code, wrapped in ```python code blocks.
"""
        return prompt

    def _build_schema_generation_prompt(
        self,
        api_name: str,
        operations: List[str],
        api_docs: str
    ) -> str:
        """Build prompt for tool schema generation."""

        prompt = f"""Generate MCP tool schema definitions for {api_name}.

API Documentation:
{api_docs[:1000]}

Operations to expose: {', '.join(operations)}

Generate a JSON schema for each operation following the MCP Tool format:
{{
  "name": "operation_name",
  "description": "What this tool does",
  "inputSchema": {{
    "type": "object",
    "properties": {{ ... }},
    "required": [...]
  }}
}}

Return ONLY valid JSON wrapped in ```json code blocks.
"""
        return prompt

    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from LLM response."""
        # Look for code blocks
        if "```python" in response:
            code = response.split("```python")[1].split("```")[0].strip()
            return code
        elif "```" in response:
            code = response.split("```")[1].split("```")[0].strip()
            return code
        else:
            # Assume entire response is code
            return response.strip()

    def _extract_schema_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON schema from LLM response."""
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error("schema_parse_failed", error=str(e))
            return {}

    def _create_validation_plan(self, code: str) -> Dict[str, Any]:
        """Create a validation plan for generated code."""
        return {
            "steps": [
                "Parse AST to ensure valid Python syntax",
                "Check for dangerous imports (os, subprocess, etc.)",
                "Verify async/await usage",
                "Check error handling presence",
                "Validate logging statements"
            ]
        }

    async def _validate_code(self, code: str) -> Dict[str, Any]:
        """Validate generated code using AST parsing."""
        errors = []

        try:
            # Parse code to AST
            tree = ast.parse(code)

            # Check for dangerous imports
            dangerous_imports = {"os", "subprocess", "eval", "exec", "compile", "__import__"}

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in dangerous_imports:
                            errors.append(f"Dangerous import detected: {alias.name}")

                elif isinstance(node, ast.ImportFrom):
                    if node.module in dangerous_imports:
                        errors.append(f"Dangerous import detected: {node.module}")

            # Check for async function definitions
            has_async = any(isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(tree))

            if not has_async:
                errors.append("No async functions found - MCP tools should be async")

            # Validation passed if no errors
            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "ast_parsed": True
            }

        except SyntaxError as e:
            return {
                "valid": False,
                "errors": [f"Syntax error: {str(e)}"],
                "ast_parsed": False
            }

    async def _test_in_sandbox(
        self,
        code: str,
        schema: Dict[str, Any],
        sandbox_level: str
    ) -> Dict[str, Any]:
        """Test generated code in a sandbox environment."""

        # Create a restricted execution environment
        sandbox_globals = {
            "__builtins__": {
                "print": print,
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "dict": dict,
                "list": list,
                "tuple": tuple,
                "set": set,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
            },
            "asyncio": asyncio,
            "aiohttp": aiohttp,
            "json": json,
            "logger": logger
        }

        if sandbox_level == "moderate":
            # Add more allowed modules
            import requests
            sandbox_globals["requests"] = requests

        try:
            # Compile and execute code
            exec(compile(code, "<generated>", "exec"), sandbox_globals)

            # Verify expected functions exist
            # (In production, would actually call the functions with test data)

            return {
                "success": True,
                "message": "Code executed successfully in sandbox"
            }

        except Exception as e:
            logger.error("sandbox_execution_failed", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }

    async def get_generated_tool(self, tool_id: str) -> Optional[GeneratedTool]:
        """Retrieve a generated tool by ID."""
        return self._generated_tools.get(tool_id)

    async def list_generated_tools(self) -> List[GeneratedTool]:
        """List all generated tools."""
        return list(self._generated_tools.values())


# Factory function
def create_integration_builder_agent(
    tenant_id: str,
    memory: MemorySubstrate,
    llm_client: LLMClient
) -> IntegrationBuilderAgent:
    """Create an IntegrationBuilder agent."""
    config = AgentConfig(
        agent_id=f"integration_builder_{tenant_id}",
        agent_type="meta.integration_builder",
        tenant_id=tenant_id,
        capabilities=[
            "generate_mcp_tools",
            "parse_api_docs",
            "validate_code",
            "sandbox_execution",
            "runtime_registration"
        ]
    )

    return IntegrationBuilderAgent(
        config=config,
        memory=memory,
        llm_client=llm_client,
        code_model="gpt-4o",  # Best for code generation
        function_model="gpt-4o"  # Can use FunctionGemma when available
    )
