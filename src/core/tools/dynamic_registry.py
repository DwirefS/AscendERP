"""
Dynamic Tool Registry - Runtime Registration and Execution of Generated Tools.

This registry enables:
1. Runtime tool registration from IntegrationBuilderAgent
2. Sandboxed tool execution with security levels
3. Tool discovery and search
4. Caching of generated tools
5. Tool versioning and updates
6. Usage analytics and monitoring

This is the runtime infrastructure that makes the meta-agent framework work.
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import hashlib
import json
import structlog
import ast
from collections import defaultdict

logger = structlog.get_logger()


class SandboxLevel(Enum):
    """Security levels for tool execution."""
    RESTRICTED = "restricted"  # Minimal permissions
    MODERATE = "moderate"  # Standard permissions
    PERMISSIVE = "permissive"  # Extended permissions (use with caution)


class ToolStatus(Enum):
    """Status of a registered tool."""
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    DISABLED = "disabled"
    TESTING = "testing"


@dataclass
class ToolExecutionContext:
    """Context for tool execution."""
    tool_id: str
    caller_agent_id: str
    arguments: Dict[str, Any]
    sandbox_level: SandboxLevel
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolExecutionResult:
    """Result of tool execution."""
    success: bool
    result: Any
    execution_time_ms: float
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegisteredTool:
    """A tool registered in the dynamic registry."""
    tool_id: str
    tool_name: str
    description: str
    code: str
    schema: Dict[str, Any]
    version: str
    status: ToolStatus
    sandbox_level: SandboxLevel
    created_at: datetime
    created_by: str  # Agent ID that created it
    last_used: Optional[datetime] = None
    usage_count: int = 0
    success_rate: float = 1.0
    average_execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Compiled code cache
    _compiled_code: Optional[Any] = None
    _compiled_globals: Optional[Dict[str, Any]] = None


class DynamicToolRegistry:
    """
    Central registry for dynamically generated tools.

    Provides:
    - Thread-safe tool registration
    - Sandboxed execution environment
    - Tool versioning and updates
    - Usage tracking and analytics
    - Caching for performance
    """

    def __init__(self):
        self._tools: Dict[str, RegisteredTool] = {}
        self._tools_by_name: Dict[str, List[str]] = defaultdict(list)
        self._execution_stats: Dict[str, List[ToolExecutionResult]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def register_tool(
        self,
        tool_name: str,
        description: str,
        code: str,
        schema: Dict[str, Any],
        created_by: str,
        sandbox_level: SandboxLevel = SandboxLevel.RESTRICTED,
        status: ToolStatus = ToolStatus.TESTING,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new tool in the registry.

        Returns: tool_id
        """
        async with self._lock:
            # Generate tool ID
            code_hash = hashlib.sha256(code.encode()).hexdigest()[:12]
            tool_id = f"{tool_name}_{code_hash}"

            # Check if tool already exists
            if tool_id in self._tools:
                logger.info("tool_already_registered", tool_id=tool_id)
                return tool_id

            # Validate code before registration
            validation = await self._validate_tool_code(code, sandbox_level)

            if not validation["valid"]:
                raise ValueError(f"Code validation failed: {validation['errors']}")

            # Create registered tool
            tool = RegisteredTool(
                tool_id=tool_id,
                tool_name=tool_name,
                description=description,
                code=code,
                schema=schema,
                version="1.0.0",
                status=status,
                sandbox_level=sandbox_level,
                created_at=datetime.utcnow(),
                created_by=created_by,
                metadata=metadata or {}
            )

            # Pre-compile code for performance
            tool._compiled_code, tool._compiled_globals = await self._compile_tool_code(
                code, sandbox_level
            )

            # Register tool
            self._tools[tool_id] = tool
            self._tools_by_name[tool_name].append(tool_id)

            logger.info(
                "tool_registered",
                tool_id=tool_id,
                tool_name=tool_name,
                created_by=created_by,
                sandbox_level=sandbox_level.value
            )

            return tool_id

    async def execute_tool(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        caller_agent_id: str,
        timeout: int = 30
    ) -> ToolExecutionResult:
        """
        Execute a registered tool with given arguments.

        Returns: ToolExecutionResult
        """
        # Get tool
        tool = self._tools.get(tool_id)

        if not tool:
            return ToolExecutionResult(
                success=False,
                result=None,
                execution_time_ms=0,
                error=f"Tool not found: {tool_id}"
            )

        if tool.status == ToolStatus.DISABLED:
            return ToolExecutionResult(
                success=False,
                result=None,
                execution_time_ms=0,
                error=f"Tool is disabled: {tool_id}"
            )

        # Create execution context
        context = ToolExecutionContext(
            tool_id=tool_id,
            caller_agent_id=caller_agent_id,
            arguments=arguments,
            sandbox_level=tool.sandbox_level,
            timeout=timeout
        )

        # Execute in sandbox
        start_time = datetime.utcnow()

        try:
            result = await self._execute_in_sandbox(tool, context)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            execution_result = ToolExecutionResult(
                success=True,
                result=result,
                execution_time_ms=execution_time,
                metadata={"tool_name": tool.tool_name}
            )

            # Update tool statistics
            await self._update_tool_stats(tool_id, execution_result)

            logger.info(
                "tool_executed_successfully",
                tool_id=tool_id,
                execution_time_ms=execution_time,
                caller=caller_agent_id
            )

            return execution_result

        except asyncio.TimeoutError:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            execution_result = ToolExecutionResult(
                success=False,
                result=None,
                execution_time_ms=execution_time,
                error=f"Tool execution timeout after {timeout}s"
            )

            await self._update_tool_stats(tool_id, execution_result)

            return execution_result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            execution_result = ToolExecutionResult(
                success=False,
                result=None,
                execution_time_ms=execution_time,
                error=str(e)
            )

            await self._update_tool_stats(tool_id, execution_result)

            logger.error("tool_execution_failed", tool_id=tool_id, error=str(e))

            return execution_result

    async def get_tool(self, tool_id: str) -> Optional[RegisteredTool]:
        """Get a tool by ID."""
        return self._tools.get(tool_id)

    async def search_tools(
        self,
        query: Optional[str] = None,
        tool_name: Optional[str] = None,
        created_by: Optional[str] = None,
        status: Optional[ToolStatus] = None,
        limit: int = 10
    ) -> List[RegisteredTool]:
        """Search for tools matching criteria."""
        results = []

        # Filter by name first if specified
        if tool_name:
            tool_ids = self._tools_by_name.get(tool_name, [])
            candidates = [self._tools[tid] for tid in tool_ids if tid in self._tools]
        else:
            candidates = list(self._tools.values())

        # Apply filters
        for tool in candidates:
            if created_by and tool.created_by != created_by:
                continue

            if status and tool.status != status:
                continue

            if query:
                # Simple text search in name and description
                if query.lower() not in tool.tool_name.lower() and \
                   query.lower() not in tool.description.lower():
                    continue

            results.append(tool)

        # Sort by usage and success rate
        results.sort(
            key=lambda t: (t.usage_count * t.success_rate, -t.average_execution_time_ms),
            reverse=True
        )

        return results[:limit]

    async def update_tool_status(
        self,
        tool_id: str,
        status: ToolStatus
    ) -> bool:
        """Update the status of a tool."""
        async with self._lock:
            tool = self._tools.get(tool_id)

            if not tool:
                return False

            tool.status = status

            logger.info("tool_status_updated", tool_id=tool_id, status=status.value)

            return True

    async def deprecate_tool(
        self,
        tool_id: str,
        replacement_tool_id: Optional[str] = None
    ):
        """Deprecate a tool, optionally specifying a replacement."""
        async with self._lock:
            tool = self._tools.get(tool_id)

            if not tool:
                return

            tool.status = ToolStatus.DEPRECATED

            if replacement_tool_id:
                tool.metadata["replacement_tool_id"] = replacement_tool_id

            logger.info("tool_deprecated", tool_id=tool_id, replacement=replacement_tool_id)

    async def get_tool_stats(self, tool_id: str) -> Dict[str, Any]:
        """Get execution statistics for a tool."""
        tool = self._tools.get(tool_id)

        if not tool:
            return {}

        recent_executions = self._execution_stats.get(tool_id, [])

        return {
            "tool_id": tool_id,
            "tool_name": tool.tool_name,
            "total_executions": tool.usage_count,
            "success_rate": tool.success_rate,
            "average_execution_time_ms": tool.average_execution_time_ms,
            "last_used": tool.last_used.isoformat() if tool.last_used else None,
            "recent_executions": len(recent_executions),
            "status": tool.status.value,
            "created_at": tool.created_at.isoformat()
        }

    async def list_all_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools."""
        return [
            {
                "tool_id": tool.tool_id,
                "tool_name": tool.tool_name,
                "description": tool.description,
                "status": tool.status.value,
                "sandbox_level": tool.sandbox_level.value,
                "usage_count": tool.usage_count,
                "success_rate": tool.success_rate,
                "created_at": tool.created_at.isoformat()
            }
            for tool in self._tools.values()
        ]

    # Private methods

    async def _validate_tool_code(
        self,
        code: str,
        sandbox_level: SandboxLevel
    ) -> Dict[str, Any]:
        """Validate tool code for security and correctness."""
        errors = []

        try:
            # Parse code to AST
            tree = ast.parse(code)

            # Security checks based on sandbox level
            dangerous_imports = {"os", "subprocess", "eval", "exec", "compile", "__import__"}

            if sandbox_level == SandboxLevel.RESTRICTED:
                # Very strict - no system access
                dangerous_imports.update({"sys", "importlib", "builtins"})

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in dangerous_imports:
                            errors.append(f"Dangerous import not allowed: {alias.name}")

                elif isinstance(node, ast.ImportFrom):
                    if node.module in dangerous_imports:
                        errors.append(f"Dangerous import not allowed: {node.module}")

                # Check for exec/eval calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ["eval", "exec", "compile", "__import__"]:
                            errors.append(f"Dangerous function call: {node.func.id}")

            # Ensure there's at least one function definition
            has_function = any(isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef)
                             for node in ast.walk(tree))

            if not has_function:
                errors.append("No function definitions found in code")

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

    async def _compile_tool_code(
        self,
        code: str,
        sandbox_level: SandboxLevel
    ) -> tuple[Any, Dict[str, Any]]:
        """Compile tool code and prepare execution environment."""
        # Create sandboxed globals
        sandbox_globals = self._create_sandbox_globals(sandbox_level)

        # Compile code
        compiled = compile(code, "<generated_tool>", "exec")

        # Execute to define functions
        exec(compiled, sandbox_globals)

        return compiled, sandbox_globals

    def _create_sandbox_globals(self, sandbox_level: SandboxLevel) -> Dict[str, Any]:
        """Create a sandboxed global namespace."""
        import aiohttp
        import structlog

        # Base allowed builtins
        allowed_builtins = {
            "print": print,
            "len": len,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "dict": dict,
            "list": list,
            "tuple": tuple,
            "set": set,
            "frozenset": frozenset,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "min": min,
            "max": max,
            "sum": sum,
            "any": any,
            "all": all,
            "abs": abs,
            "round": round,
            "isinstance": isinstance,
            "issubclass": issubclass,
            "hasattr": hasattr,
            "getattr": getattr,
            "setattr": setattr,
            "type": type,
            "Exception": Exception,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "IndexError": IndexError,
        }

        # Base allowed modules
        allowed_modules = {
            "json": json,
            "asyncio": asyncio,
            "aiohttp": aiohttp,
            "datetime": datetime,
            "logger": structlog.get_logger()
        }

        if sandbox_level in [SandboxLevel.MODERATE, SandboxLevel.PERMISSIVE]:
            # Add more modules for moderate/permissive
            import requests
            import re
            import hashlib

            allowed_modules.update({
                "requests": requests,
                "re": re,
                "hashlib": hashlib
            })

        if sandbox_level == SandboxLevel.PERMISSIVE:
            # Add even more for permissive (use with caution)
            import urllib
            import base64

            allowed_modules.update({
                "urllib": urllib,
                "base64": base64
            })

        return {
            "__builtins__": allowed_builtins,
            **allowed_modules
        }

    async def _execute_in_sandbox(
        self,
        tool: RegisteredTool,
        context: ToolExecutionContext
    ) -> Any:
        """Execute tool code in sandboxed environment."""
        # Use pre-compiled code if available
        if tool._compiled_globals:
            sandbox_globals = tool._compiled_globals.copy()
        else:
            # Compile on demand
            _, sandbox_globals = await self._compile_tool_code(
                tool.code,
                tool.sandbox_level
            )

        # Find the main function to call
        # Convention: look for function matching tool name or 'execute' or 'run'
        main_function = None

        for name, obj in sandbox_globals.items():
            if callable(obj) and not name.startswith("_"):
                # Prefer function with tool name
                if name == tool.tool_name or name == "execute" or name == "run":
                    main_function = obj
                    break

        if not main_function:
            # Just take the first callable
            for name, obj in sandbox_globals.items():
                if callable(obj) and not name.startswith("_"):
                    main_function = obj
                    break

        if not main_function:
            raise ValueError("No callable function found in tool code")

        # Execute with timeout
        if asyncio.iscoroutinefunction(main_function):
            result = await asyncio.wait_for(
                main_function(**context.arguments),
                timeout=context.timeout
            )
        else:
            # Run sync function in executor
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: main_function(**context.arguments)),
                timeout=context.timeout
            )

        return result

    async def _update_tool_stats(
        self,
        tool_id: str,
        execution_result: ToolExecutionResult
    ):
        """Update tool execution statistics."""
        async with self._lock:
            tool = self._tools.get(tool_id)

            if not tool:
                return

            # Update usage count
            tool.usage_count += 1
            tool.last_used = datetime.utcnow()

            # Update success rate (exponential moving average)
            alpha = 0.1  # Weight for new data
            if execution_result.success:
                tool.success_rate = (1 - alpha) * tool.success_rate + alpha * 1.0
            else:
                tool.success_rate = (1 - alpha) * tool.success_rate + alpha * 0.0

            # Update average execution time
            tool.average_execution_time_ms = (
                (1 - alpha) * tool.average_execution_time_ms +
                alpha * execution_result.execution_time_ms
            )

            # Store execution result (keep last 100)
            self._execution_stats[tool_id].append(execution_result)
            if len(self._execution_stats[tool_id]) > 100:
                self._execution_stats[tool_id] = self._execution_stats[tool_id][-100:]

            # Auto-promote from testing to active if success rate is high
            if tool.status == ToolStatus.TESTING and tool.usage_count >= 10:
                if tool.success_rate >= 0.9:
                    tool.status = ToolStatus.ACTIVE
                    logger.info("tool_auto_promoted", tool_id=tool_id)


# Global registry instance
_global_registry: Optional[DynamicToolRegistry] = None


def get_global_registry() -> DynamicToolRegistry:
    """Get the global tool registry instance."""
    global _global_registry

    if _global_registry is None:
        _global_registry = DynamicToolRegistry()

    return _global_registry
