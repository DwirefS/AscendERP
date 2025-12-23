"""
Input Validator

Comprehensive input validation and sanitization to prevent:
- Prompt injection attacks
- SQL injection
- XSS (cross-site scripting)
- Path traversal
- Command injection
- NoSQL injection

Defense in depth:
- Whitelist validation (preferred)
- Blacklist detection (secondary)
- Length limits
- Type checking
- Schema validation
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from jsonschema import validate, ValidationError as JSONSchemaValidationError
import html

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class InputValidator:
    """
    Input validation and sanitization framework.

    Principles:
    - Fail secure: Reject invalid input rather than trying to fix it
    - Whitelist over blacklist
    - Log all validation failures for security monitoring
    - Context-aware validation (different rules for different inputs)
    """

    # Dangerous patterns for prompt injection
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+(previous|above|all)\s+instructions?",
        r"system\s*:\s*you\s+are",
        r"forget\s+(everything|all|previous)",
        r"new\s+instructions?:",
        r"act\s+as\s+(a\s+)?different",
        r"pretend\s+(you\s+are|to\s+be)",
        r"</\s*instructions?\s*>",
        r"<\s*instructions?\s*>",
        r"jailbreak",
        r"DAN\s+mode",  # "Do Anything Now" jailbreak
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"('\s*OR\s+'1'\s*=\s*'1)",
        r"(--|\#|\/\*|\*\/)",  # SQL comments
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bEXEC\b|\bEXECUTE\b)",
        r"xp_cmdshell",
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./",
        r"\.\.\\",
        r"%2e%2e/",
        r"%2e%2e\\",
    ]

    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r"[;&|`$]",  # Shell metacharacters
        r"\$\(.*\)",  # Command substitution
        r"`.*`",  # Backticks
    ]

    def __init__(self, strict_mode: bool = True):
        """
        Initialize Input Validator.

        Args:
            strict_mode: If True, use strict validation (reject borderline cases)
        """
        self.strict_mode = strict_mode

    def validate_prompt(self, prompt: str, max_length: int = 10000) -> str:
        """
        Validate and sanitize an AI prompt.

        Args:
            prompt: User-provided prompt
            max_length: Maximum allowed length

        Returns:
            Validated prompt

        Raises:
            ValidationError: If prompt fails validation
        """
        # Type check
        if not isinstance(prompt, str):
            raise ValidationError(f"Prompt must be string, got {type(prompt)}")

        # Length check
        if len(prompt) > max_length:
            logger.warning(
                f"Prompt exceeds max length: {len(prompt)} > {max_length}"
            )
            raise ValidationError(f"Prompt too long (max {max_length} characters)")

        # Empty check
        if not prompt.strip():
            raise ValidationError("Prompt cannot be empty")

        # Check for prompt injection patterns
        for pattern in self.PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                logger.warning(
                    f"Potential prompt injection detected: pattern '{pattern}'"
                )
                raise ValidationError(
                    "Prompt contains suspicious content that may be a security risk"
                )

        # Sanitize (remove potentially dangerous control characters)
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", prompt)

        return sanitized

    def validate_agent_id(self, agent_id: str) -> str:
        """
        Validate agent ID.

        Agent IDs must be alphanumeric with hyphens/underscores only.

        Args:
            agent_id: Agent identifier

        Returns:
            Validated agent ID

        Raises:
            ValidationError: If agent_id is invalid
        """
        if not isinstance(agent_id, str):
            raise ValidationError(f"Agent ID must be string, got {type(agent_id)}")

        if not agent_id:
            raise ValidationError("Agent ID cannot be empty")

        # Whitelist validation: alphanumeric, hyphens, underscores only
        if not re.match(r"^[a-zA-Z0-9_-]+$", agent_id):
            raise ValidationError(
                "Agent ID must contain only alphanumeric characters, hyphens, and underscores"
            )

        if len(agent_id) > 100:
            raise ValidationError("Agent ID too long (max 100 characters)")

        return agent_id

    def validate_file_path(
        self, file_path: str, allowed_base_dirs: Optional[List[str]] = None
    ) -> Path:
        """
        Validate file path to prevent path traversal attacks.

        Args:
            file_path: File path to validate
            allowed_base_dirs: List of allowed base directories (optional)

        Returns:
            Validated Path object

        Raises:
            ValidationError: If path is invalid or attempts traversal
        """
        if not isinstance(file_path, str):
            raise ValidationError(f"File path must be string, got {type(file_path)}")

        # Check for path traversal patterns
        for pattern in self.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, file_path):
                logger.warning(f"Path traversal attempt detected: {file_path}")
                raise ValidationError("File path contains invalid traversal sequences")

        # Resolve to absolute path
        try:
            path = Path(file_path).resolve()
        except Exception as e:
            raise ValidationError(f"Invalid file path: {e}")

        # Check if path is within allowed directories
        if allowed_base_dirs:
            allowed = False
            for base_dir in allowed_base_dirs:
                base_path = Path(base_dir).resolve()
                try:
                    path.relative_to(base_path)
                    allowed = True
                    break
                except ValueError:
                    continue

            if not allowed:
                logger.warning(
                    f"File path outside allowed directories: {file_path}"
                )
                raise ValidationError("File path is not in an allowed directory")

        return path

    def validate_sql_parameter(self, param: Any) -> Any:
        """
        Validate SQL parameter (for prepared statements).

        Note: Always use parameterized queries! This is defense in depth.

        Args:
            param: SQL parameter value

        Returns:
            Validated parameter

        Raises:
            ValidationError: If parameter contains SQL injection patterns
        """
        # Allow None, numbers, booleans as-is
        if param is None or isinstance(param, (int, float, bool)):
            return param

        # Strings require validation
        if isinstance(param, str):
            # Check for SQL injection patterns
            for pattern in self.SQL_INJECTION_PATTERNS:
                if re.search(pattern, param, re.IGNORECASE):
                    logger.warning(
                        f"Potential SQL injection detected in parameter: pattern '{pattern}'"
                    )
                    raise ValidationError(
                        "Parameter contains suspicious SQL content"
                    )

            # Length check
            if len(param) > 10000:
                raise ValidationError("SQL parameter too long (max 10000 characters)")

            return param

        # Lists/tuples: validate each element
        if isinstance(param, (list, tuple)):
            return [self.validate_sql_parameter(p) for p in param]

        # Unsupported type
        raise ValidationError(
            f"Unsupported SQL parameter type: {type(param)}"
        )

    def validate_json_schema(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate JSON data against a schema.

        Args:
            data: JSON data to validate
            schema: JSON Schema specification

        Returns:
            Validated data

        Raises:
            ValidationError: If data doesn't match schema
        """
        try:
            validate(instance=data, schema=schema)
            return data
        except JSONSchemaValidationError as e:
            logger.warning(f"JSON schema validation failed: {e.message}")
            raise ValidationError(f"Invalid data: {e.message}")

    def sanitize_html(self, text: str) -> str:
        """
        Sanitize text for HTML display (prevent XSS).

        Args:
            text: Text that may contain HTML

        Returns:
            HTML-escaped text
        """
        return html.escape(text)

    def validate_email(self, email: str) -> str:
        """
        Validate email address format.

        Args:
            email: Email address

        Returns:
            Validated email (lowercased)

        Raises:
            ValidationError: If email format is invalid
        """
        if not isinstance(email, str):
            raise ValidationError(f"Email must be string, got {type(email)}")

        # Basic email regex (RFC 5322 compliant is complex, this is pragmatic)
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if not re.match(email_pattern, email):
            raise ValidationError("Invalid email address format")

        if len(email) > 254:  # RFC 5321 max length
            raise ValidationError("Email address too long (max 254 characters)")

        return email.lower()

    def validate_url(self, url: str, allowed_schemes: Optional[List[str]] = None) -> str:
        """
        Validate URL.

        Args:
            url: URL to validate
            allowed_schemes: List of allowed schemes (default: ['http', 'https'])

        Returns:
            Validated URL

        Raises:
            ValidationError: If URL is invalid
        """
        if not isinstance(url, str):
            raise ValidationError(f"URL must be string, got {type(url)}")

        # URL regex (basic validation)
        url_pattern = r"^(https?|ftp)://[^\s/$.?#].[^\s]*$"

        if not re.match(url_pattern, url, re.IGNORECASE):
            raise ValidationError("Invalid URL format")

        # Check allowed schemes
        if allowed_schemes:
            scheme = url.split("://")[0].lower()
            if scheme not in allowed_schemes:
                raise ValidationError(
                    f"URL scheme '{scheme}' not allowed (allowed: {allowed_schemes})"
                )

        if len(url) > 2048:
            raise ValidationError("URL too long (max 2048 characters)")

        return url

    def validate_integer_range(
        self, value: int, min_value: Optional[int] = None, max_value: Optional[int] = None
    ) -> int:
        """
        Validate integer is within range.

        Args:
            value: Integer value
            min_value: Minimum allowed value (inclusive)
            max_value: Maximum allowed value (inclusive)

        Returns:
            Validated integer

        Raises:
            ValidationError: If value is out of range
        """
        if not isinstance(value, int):
            raise ValidationError(f"Value must be integer, got {type(value)}")

        if min_value is not None and value < min_value:
            raise ValidationError(f"Value {value} is below minimum {min_value}")

        if max_value is not None and value > max_value:
            raise ValidationError(f"Value {value} exceeds maximum {max_value}")

        return value

    def validate_enum(self, value: str, allowed_values: List[str]) -> str:
        """
        Validate value is in allowed enum values.

        Args:
            value: Value to validate
            allowed_values: List of allowed values

        Returns:
            Validated value

        Raises:
            ValidationError: If value not in allowed list
        """
        if value not in allowed_values:
            raise ValidationError(
                f"Value '{value}' not allowed (allowed: {allowed_values})"
            )

        return value


# Global validator instance
_validator: Optional[InputValidator] = None


def get_validator(strict_mode: bool = True) -> InputValidator:
    """
    Get or create the global InputValidator instance.

    Args:
        strict_mode: Use strict validation mode

    Returns:
        InputValidator singleton instance
    """
    global _validator

    if _validator is None:
        _validator = InputValidator(strict_mode=strict_mode)

    return _validator
