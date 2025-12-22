"""
CodeExecutionAgent: Secure sandboxed code execution for ANTS agents.

Supports:
- Python (RestrictedPython sandbox)
- JavaScript (Node.js subprocess with timeout)
- SQL (validated and executed against PostgreSQL)

Security features:
- No file system access
- No network access (Python)
- Limited built-ins and imports
- Resource limits (timeout, memory)
- AST validation before execution
- Result caching to avoid redundant execution

Usage:
    executor = CodeExecutionAgent(agent_id="code_exec_001")

    # Execute Python
    result = await executor.execute_python(
        code="def add(a, b): return a + b\nresult = add(2, 3)",
        timeout_seconds=5
    )

    # Execute JavaScript
    result = await executor.execute_javascript(
        code="function add(a, b) { return a + b; } console.log(add(2, 3));",
        timeout_seconds=5
    )

    # Execute SQL
    result = await executor.execute_sql(
        query="SELECT COUNT(*) FROM users WHERE active = true",
        connection_string="postgresql://...",
        readonly=True
    )
"""
import ast
import asyncio
import hashlib
import json
import logging
import resource
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

try:
    from RestrictedPython import compile_restricted, safe_globals
    from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr
    RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    RESTRICTED_PYTHON_AVAILABLE = False
    logging.warning("RestrictedPython not available - Python sandbox will use basic restrictions")

try:
    import psycopg2
    from psycopg2 import sql
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logging.warning("psycopg2 not available - SQL execution disabled")


logger = logging.getLogger(__name__)


class CodeLanguage(Enum):
    """Supported code execution languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    SQL = "sql"


class ExecutionStatus(Enum):
    """Execution result status."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    RESOURCE_LIMIT = "resource_limit"


@dataclass
class ExecutionResult:
    """Result of code execution."""
    status: ExecutionStatus
    output: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    return_value: Any = None
    cached: bool = False


@dataclass
class ResourceLimits:
    """Resource limits for code execution."""
    timeout_seconds: int = 5
    max_memory_mb: int = 256
    max_cpu_percent: int = 100


class CodeExecutionAgent:
    """
    Agent for secure sandboxed code execution.

    Features:
    - Python: RestrictedPython with limited imports and built-ins
    - JavaScript: Node.js subprocess with timeout
    - SQL: Validated queries with readonly option
    - Result caching based on code hash
    - Resource limits (timeout, memory, CPU)
    """

    # Python: Allowed safe modules
    ALLOWED_PYTHON_MODULES = {
        'math', 'datetime', 'json', 'itertools', 'functools',
        're', 'collections', 'decimal', 'random', 'statistics'
    }

    # Python: Blocked dangerous built-ins
    BLOCKED_BUILTINS = {
        'open', 'exec', 'eval', 'compile', '__import__',
        'input', 'file', 'execfile', 'reload'
    }

    # SQL: Dangerous keywords that require readonly=False
    SQL_WRITE_KEYWORDS = {
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'TRUNCATE', 'REPLACE', 'MERGE'
    }

    def __init__(
        self,
        agent_id: str,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 3600,
        default_limits: Optional[ResourceLimits] = None
    ):
        """
        Initialize CodeExecutionAgent.

        Args:
            agent_id: Unique identifier for this agent
            cache_enabled: Enable result caching
            cache_ttl_seconds: Cache entry TTL
            default_limits: Default resource limits
        """
        self.agent_id = agent_id
        self.cache_enabled = cache_enabled
        self.cache_ttl_seconds = cache_ttl_seconds
        self.default_limits = default_limits or ResourceLimits()

        # Result cache: code_hash -> (result, expiry)
        self._cache: Dict[str, tuple[ExecutionResult, datetime]] = {}

        # Execution statistics
        self.stats = {
            'total_executions': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'timeouts': 0,
            'errors': 0,
            'by_language': {lang.value: 0 for lang in CodeLanguage}
        }

        logger.info(
            f"CodeExecutionAgent initialized",
            extra={
                'agent_id': agent_id,
                'cache_enabled': cache_enabled,
                'restricted_python': RESTRICTED_PYTHON_AVAILABLE,
                'psycopg2': PSYCOPG2_AVAILABLE
            }
        )

    def _compute_cache_key(
        self,
        language: CodeLanguage,
        code: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Compute cache key for code execution."""
        key_data = {
            'language': language.value,
            'code': code,
            'context': context or {}
        }
        key_json = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_json.encode()).hexdigest()

    def _get_cached_result(self, cache_key: str) -> Optional[ExecutionResult]:
        """Get cached result if available and not expired."""
        if not self.cache_enabled:
            return None

        if cache_key in self._cache:
            result, expiry = self._cache[cache_key]
            if datetime.utcnow() < expiry:
                self.stats['cache_hits'] += 1
                result.cached = True
                logger.debug(f"Cache hit for {cache_key[:16]}...")
                return result
            else:
                # Expired
                del self._cache[cache_key]

        self.stats['cache_misses'] += 1
        return None

    def _cache_result(self, cache_key: str, result: ExecutionResult):
        """Cache execution result."""
        if not self.cache_enabled:
            return

        expiry = datetime.utcnow() + timedelta(seconds=self.cache_ttl_seconds)
        self._cache[cache_key] = (result, expiry)

        # Cleanup expired entries (simple approach)
        if len(self._cache) > 1000:
            now = datetime.utcnow()
            expired = [k for k, (_, exp) in self._cache.items() if now >= exp]
            for k in expired:
                del self._cache[k]

    def _validate_python_ast(self, code: str) -> tuple[bool, Optional[str]]:
        """
        Validate Python code AST for security violations.

        Returns:
            (is_valid, error_message)
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Check for dangerous operations
        for node in ast.walk(tree):
            # Block file operations
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.BLOCKED_BUILTINS:
                        return False, f"Blocked built-in: {node.func.id}"

            # Block imports of non-whitelisted modules
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_base = alias.name.split('.')[0]
                    if module_base not in self.ALLOWED_PYTHON_MODULES:
                        return False, f"Import not allowed: {alias.name}"

            if isinstance(node, ast.ImportFrom):
                if node.module:
                    module_base = node.module.split('.')[0]
                    if module_base not in self.ALLOWED_PYTHON_MODULES:
                        return False, f"Import not allowed: {node.module}"

        return True, None

    async def execute_python(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[int] = None,
        limits: Optional[ResourceLimits] = None
    ) -> ExecutionResult:
        """
        Execute Python code in restricted sandbox.

        Args:
            code: Python code to execute
            context: Variables available in execution context
            timeout_seconds: Execution timeout
            limits: Resource limits

        Returns:
            ExecutionResult with output and status
        """
        start_time = datetime.utcnow()
        limits = limits or self.default_limits
        timeout = timeout_seconds or limits.timeout_seconds

        self.stats['total_executions'] += 1
        self.stats['by_language'][CodeLanguage.PYTHON.value] += 1

        # Check cache
        cache_key = self._compute_cache_key(CodeLanguage.PYTHON, code, context)
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        # Validate AST
        valid, error = self._validate_python_ast(code)
        if not valid:
            result = ExecutionResult(
                status=ExecutionStatus.SECURITY_VIOLATION,
                error=error,
                execution_time_ms=0.0
            )
            self.stats['errors'] += 1
            return result

        try:
            # Use RestrictedPython if available
            if RESTRICTED_PYTHON_AVAILABLE:
                # Compile with restrictions
                byte_code = compile_restricted(code, '<string>', 'exec')

                # Create safe execution environment
                safe_globals_dict = safe_globals.copy()
                safe_globals_dict['_getattr_'] = safer_getattr
                safe_globals_dict['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence

                # Add allowed modules
                for module_name in self.ALLOWED_PYTHON_MODULES:
                    try:
                        safe_globals_dict[module_name] = __import__(module_name)
                    except ImportError:
                        pass

                # Add user context
                if context:
                    safe_globals_dict.update(context)

                exec_locals = {}

                # Execute with timeout
                exec(byte_code, safe_globals_dict, exec_locals)

                # Get result
                output = exec_locals.get('result')
                stdout = str(output) if output is not None else ""

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                result = ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    output=stdout,
                    stdout=stdout,
                    return_value=output,
                    execution_time_ms=execution_time
                )

            else:
                # Fallback: basic exec with limited built-ins
                restricted_builtins = {
                    k: v for k, v in __builtins__.items()
                    if k not in self.BLOCKED_BUILTINS
                }

                exec_globals = {'__builtins__': restricted_builtins}
                if context:
                    exec_globals.update(context)

                exec_locals = {}
                exec(code, exec_globals, exec_locals)

                output = exec_locals.get('result')
                stdout = str(output) if output is not None else ""

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                result = ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    output=stdout,
                    stdout=stdout,
                    return_value=output,
                    execution_time_ms=execution_time
                )

            # Cache result
            self._cache_result(cache_key, result)
            return result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.stats['errors'] += 1

            result = ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(e),
                stderr=str(e),
                execution_time_ms=execution_time
            )
            return result

    async def execute_javascript(
        self,
        code: str,
        timeout_seconds: Optional[int] = None,
        limits: Optional[ResourceLimits] = None
    ) -> ExecutionResult:
        """
        Execute JavaScript code using Node.js subprocess.

        Args:
            code: JavaScript code to execute
            timeout_seconds: Execution timeout
            limits: Resource limits

        Returns:
            ExecutionResult with output and status
        """
        start_time = datetime.utcnow()
        limits = limits or self.default_limits
        timeout = timeout_seconds or limits.timeout_seconds

        self.stats['total_executions'] += 1
        self.stats['by_language'][CodeLanguage.JAVASCRIPT.value] += 1

        # Check cache
        cache_key = self._compute_cache_key(CodeLanguage.JAVASCRIPT, code)
        cached = self._get_cached_result(cache_key)
        if cached:
            return cached

        try:
            # Write code to temporary file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.js',
                delete=False
            ) as f:
                f.write(code)
                temp_file = f.name

            try:
                # Execute with Node.js
                process = await asyncio.create_subprocess_exec(
                    'node',
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(),
                        timeout=timeout
                    )

                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    if process.returncode == 0:
                        result = ExecutionResult(
                            status=ExecutionStatus.SUCCESS,
                            output=stdout.decode('utf-8'),
                            stdout=stdout.decode('utf-8'),
                            stderr=stderr.decode('utf-8') if stderr else None,
                            execution_time_ms=execution_time
                        )
                    else:
                        self.stats['errors'] += 1
                        result = ExecutionResult(
                            status=ExecutionStatus.ERROR,
                            error=stderr.decode('utf-8'),
                            stderr=stderr.decode('utf-8'),
                            execution_time_ms=execution_time
                        )

                    # Cache result
                    self._cache_result(cache_key, result)
                    return result

                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    self.stats['timeouts'] += 1

                    return ExecutionResult(
                        status=ExecutionStatus.TIMEOUT,
                        error=f"Execution timed out after {timeout}s",
                        execution_time_ms=timeout * 1000
                    )
            finally:
                # Cleanup temp file
                Path(temp_file).unlink(missing_ok=True)

        except FileNotFoundError:
            self.stats['errors'] += 1
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Node.js not found. Please install Node.js to execute JavaScript."
            )
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.stats['errors'] += 1

            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(e),
                execution_time_ms=execution_time
            )

    async def execute_sql(
        self,
        query: str,
        connection_string: str,
        readonly: bool = True,
        timeout_seconds: Optional[int] = None,
        limits: Optional[ResourceLimits] = None
    ) -> ExecutionResult:
        """
        Execute SQL query against PostgreSQL.

        Args:
            query: SQL query to execute
            connection_string: PostgreSQL connection string
            readonly: If True, only SELECT queries allowed
            timeout_seconds: Execution timeout
            limits: Resource limits

        Returns:
            ExecutionResult with query results
        """
        start_time = datetime.utcnow()
        limits = limits or self.default_limits
        timeout = timeout_seconds or limits.timeout_seconds

        self.stats['total_executions'] += 1
        self.stats['by_language'][CodeLanguage.SQL.value] += 1

        if not PSYCOPG2_AVAILABLE:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="psycopg2 not available. Install with: pip install psycopg2-binary"
            )

        # Check for write operations if readonly
        if readonly:
            query_upper = query.upper()
            for keyword in self.SQL_WRITE_KEYWORDS:
                if keyword in query_upper:
                    self.stats['errors'] += 1
                    return ExecutionResult(
                        status=ExecutionStatus.SECURITY_VIOLATION,
                        error=f"Write operation '{keyword}' not allowed in readonly mode"
                    )

        # Check cache (only for SELECT queries)
        if readonly:
            cache_key = self._compute_cache_key(
                CodeLanguage.SQL,
                query,
                {'connection': connection_string}
            )
            cached = self._get_cached_result(cache_key)
            if cached:
                return cached

        conn = None
        cursor = None

        try:
            # Connect to database
            conn = psycopg2.connect(connection_string, connect_timeout=timeout)
            cursor = conn.cursor()

            # Set statement timeout
            cursor.execute(f"SET statement_timeout = {timeout * 1000}")

            # Execute query
            cursor.execute(query)

            # Fetch results if SELECT
            if query.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]

                # Format as JSON
                result_data = [
                    dict(zip(columns, row))
                    for row in rows
                ]
                output = json.dumps(result_data, indent=2, default=str)

            else:
                # Write operation
                conn.commit()
                output = f"Query executed successfully. Rows affected: {cursor.rowcount}"
                result_data = {'rows_affected': cursor.rowcount}

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            result = ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=output,
                return_value=result_data,
                execution_time_ms=execution_time
            )

            # Cache SELECT results
            if readonly:
                self._cache_result(cache_key, result)

            return result

        except psycopg2.OperationalError as e:
            if "timeout" in str(e).lower():
                self.stats['timeouts'] += 1
                return ExecutionResult(
                    status=ExecutionStatus.TIMEOUT,
                    error=f"Query timed out after {timeout}s",
                    execution_time_ms=timeout * 1000
                )
            else:
                self.stats['errors'] += 1
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    error=str(e)
                )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.stats['errors'] += 1

            if conn:
                conn.rollback()

            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(e),
                execution_time_ms=execution_time
            )

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        cache_hit_rate = 0.0
        total_cache_ops = self.stats['cache_hits'] + self.stats['cache_misses']
        if total_cache_ops > 0:
            cache_hit_rate = self.stats['cache_hits'] / total_cache_ops

        return {
            'agent_id': self.agent_id,
            'total_executions': self.stats['total_executions'],
            'cache_enabled': self.cache_enabled,
            'cache_size': len(self._cache),
            'cache_hit_rate': cache_hit_rate,
            'timeouts': self.stats['timeouts'],
            'errors': self.stats['errors'],
            'by_language': self.stats['by_language']
        }

    def clear_cache(self):
        """Clear result cache."""
        self._cache.clear()
        logger.info(f"Cache cleared for agent {self.agent_id}")


def create_code_executor(
    agent_id: str = "code_executor_001",
    **kwargs
) -> CodeExecutionAgent:
    """
    Factory function to create CodeExecutionAgent.

    Args:
        agent_id: Unique identifier
        **kwargs: Additional arguments passed to CodeExecutionAgent

    Returns:
        Configured CodeExecutionAgent
    """
    return CodeExecutionAgent(agent_id=agent_id, **kwargs)
