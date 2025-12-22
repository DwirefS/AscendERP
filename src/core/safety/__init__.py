"""
Safety module for ANTS.

NVIDIA NeMo Guardrails integration providing multi-layered safety validation:
- Input validation (jailbreak detection, PII screening)
- Output verification (hallucination detection, policy compliance)
- Topical rails (keep conversations on approved topics)
- Fact-checking (validate claims against context)

This ensures ANTS agents operate safely in production environments with
comprehensive protection against common LLM vulnerabilities.
"""
from src.core.safety.guardrails_client import (
    GuardrailsClient,
    ViolationType,
    ValidationResult,
    GuardrailViolation,
    InputValidationResult,
    OutputValidationResult,
    create_guardrails_client
)

__all__ = [
    "GuardrailsClient",
    "ViolationType",
    "ValidationResult",
    "GuardrailViolation",
    "InputValidationResult",
    "OutputValidationResult",
    "create_guardrails_client",
]
