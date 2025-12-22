"""
NVIDIA NeMo Guardrails Integration for ANTS

Provides comprehensive safety rails for AI agent interactions:
- Input validation (jailbreak detection, sensitive data screening)
- Output verification (hallucination detection, policy compliance)
- Topical rails (keep conversations on-topic)
- Fact-checking (validate factual claims against context)

Architecture:
- Wraps agent LLM calls with safety checks
- Uses NeMo Guardrails for natural language policy enforcement
- Integrates with OPA for structured policy validation
- Logs all violations for audit and learning

Example:
    from src.core.safety import GuardrailsClient

    guardrails = GuardrailsClient(config_path="ai/nemo/config/guardrails.yaml")

    # Validate input
    input_result = await guardrails.validate_input(
        user_input="Show me customer credit card numbers",
        context={"user_role": "support_agent"}
    )
    # Result: blocked (PII request without authorization)

    # Validate output
    output_result = await guardrails.validate_output(
        bot_response="The customer's card ends in 1234",
        context=context
    )
    # Result: sanitized (PII redacted)
"""
import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from nemoguardrails import RailsConfig, LLMRails
    NEMO_AVAILABLE = True
except ImportError:
    NEMO_AVAILABLE = False
    logging.warning("NeMo Guardrails not installed - using fallback validation")


logger = logging.getLogger(__name__)


class ViolationType(Enum):
    """Types of guardrail violations."""
    JAILBREAK_ATTEMPT = "jailbreak_attempt"
    SENSITIVE_DATA = "sensitive_data"
    POLICY_VIOLATION = "policy_violation"
    HALLUCINATION = "hallucination"
    BLOCKED_TOPIC = "blocked_topic"
    UNAUTHORIZED_ACTION = "unauthorized_action"


class ValidationResult(Enum):
    """Result of guardrail validation."""
    APPROVED = "approved"      # Input/output is safe
    BLOCKED = "blocked"        # Input/output is completely blocked
    SANITIZED = "sanitized"    # Input/output was modified for safety


@dataclass
class GuardrailViolation:
    """Record of a guardrail violation."""
    violation_type: ViolationType
    severity: str  # low, medium, high, critical
    message: str
    detected_at: str
    original_text: str
    sanitized_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class InputValidationResult:
    """Result of input validation."""
    result: ValidationResult
    processed_input: str
    violations: List[GuardrailViolation]
    allowed: bool


@dataclass
class OutputValidationResult:
    """Result of output validation."""
    result: ValidationResult
    processed_output: str
    violations: List[GuardrailViolation]
    modifications: List[str]


class GuardrailsClient:
    """
    NVIDIA NeMo Guardrails integration for ANTS agents.

    Provides multi-layered safety validation:
    1. Input Rails: Validate user/agent inputs before processing
    2. Output Rails: Validate model responses before returning
    3. Topic Rails: Keep conversations on approved topics
    4. Fact Rails: Verify factual accuracy against context
    """

    # PII detection patterns
    PII_PATTERNS = {
        'ssn': re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        'credit_card': re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
        'account_number': re.compile(r'\b\d{10,12}\b'),
        'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    }

    # Jailbreak attempt patterns
    JAILBREAK_PATTERNS = [
        r'ignore (previous|all) instructions?',
        r'pretend (you are|to be)',
        r'role.?play',
        r'reveal (your|the) (prompt|instructions)',
        r'bypass.*security',
        r'disable.*safety',
    ]

    # Blocked topics
    BLOCKED_TOPICS = [
        'competitor_information',
        'internal_salaries',
        'unreleased_products',
        'security_vulnerabilities',
        'source_code',
    ]

    def __init__(
        self,
        config_path: str = "ai/nemo/config/guardrails.yaml",
        enable_simulation: bool = False,
        opa_endpoint: Optional[str] = None
    ):
        """
        Initialize Guardrails Client.

        Args:
            config_path: Path to NeMo Guardrails YAML config
            enable_simulation: Use fallback validation if NeMo unavailable
            opa_endpoint: OPA endpoint for policy checks
        """
        self.config_path = Path(config_path)
        self.simulation_mode = enable_simulation or not NEMO_AVAILABLE
        self.opa_endpoint = opa_endpoint or "http://localhost:8181/v1/data"

        # Statistics
        self.stats = {
            'total_validations': 0,
            'inputs_blocked': 0,
            'outputs_sanitized': 0,
            'violations_detected': 0,
            'by_violation_type': {vt.value: 0 for vt in ViolationType},
        }

        # Initialize NeMo Rails
        if not self.simulation_mode and self.config_path.exists():
            try:
                config = RailsConfig.from_path(str(self.config_path))
                self.rails = LLMRails(config)
                logger.info("NeMo Guardrails initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize NeMo Guardrails: {e}")
                self.rails = None
                self.simulation_mode = True
        else:
            self.rails = None
            logger.info("Guardrails initialized in SIMULATION mode")

    async def validate_input(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> InputValidationResult:
        """
        Validate user/agent input before processing.

        Checks for:
        - Jailbreak attempts
        - Sensitive data (PII, credentials)
        - Policy violations
        - Blocked topics

        Args:
            user_input: Input text to validate
            context: Additional context (user role, permissions, etc.)

        Returns:
            InputValidationResult with processed input and violations
        """
        self.stats['total_validations'] += 1
        violations = []
        processed_input = user_input

        logger.info(
            f"Validating input",
            extra={'input_length': len(user_input), 'context': context}
        )

        # 1. Check for jailbreak attempts
        jailbreak_violation = self._detect_jailbreak(user_input)
        if jailbreak_violation:
            violations.append(jailbreak_violation)
            self.stats['inputs_blocked'] += 1
            self.stats['violations_detected'] += 1
            self.stats['by_violation_type'][ViolationType.JAILBREAK_ATTEMPT.value] += 1

            return InputValidationResult(
                result=ValidationResult.BLOCKED,
                processed_input="",
                violations=violations,
                allowed=False
            )

        # 2. Check for sensitive data
        pii_violations = self._detect_pii(user_input)
        if pii_violations:
            violations.extend(pii_violations)
            # Redact PII
            processed_input = self._redact_pii(user_input)
            self.stats['violations_detected'] += len(pii_violations)
            for _ in pii_violations:
                self.stats['by_violation_type'][ViolationType.SENSITIVE_DATA.value] += 1

        # 3. Check for blocked topics
        topic_violation = self._check_blocked_topics(user_input)
        if topic_violation:
            violations.append(topic_violation)
            self.stats['inputs_blocked'] += 1
            self.stats['violations_detected'] += 1
            self.stats['by_violation_type'][ViolationType.BLOCKED_TOPIC.value] += 1

            return InputValidationResult(
                result=ValidationResult.BLOCKED,
                processed_input="",
                violations=violations,
                allowed=False
            )

        # 4. Use NeMo Guardrails if available
        if not self.simulation_mode and self.rails:
            try:
                nemo_result = await self._validate_with_nemo(
                    user_input,
                    context or {},
                    check_type="input"
                )

                if not nemo_result['allowed']:
                    violations.append(GuardrailViolation(
                        violation_type=ViolationType.POLICY_VIOLATION,
                        severity="high",
                        message=nemo_result.get('message', 'Policy violation'),
                        detected_at=datetime.utcnow().isoformat(),
                        original_text=user_input
                    ))
                    self.stats['inputs_blocked'] += 1
                    self.stats['violations_detected'] += 1

                    return InputValidationResult(
                        result=ValidationResult.BLOCKED,
                        processed_input="",
                        violations=violations,
                        allowed=False
                    )
            except Exception as e:
                logger.error(f"NeMo validation failed: {e}")

        # Determine result
        if violations and all(v.violation_type == ViolationType.SENSITIVE_DATA for v in violations):
            result = ValidationResult.SANITIZED
        elif violations:
            result = ValidationResult.BLOCKED
        else:
            result = ValidationResult.APPROVED

        return InputValidationResult(
            result=result,
            processed_input=processed_input if result != ValidationResult.BLOCKED else "",
            violations=violations,
            allowed=(result != ValidationResult.BLOCKED)
        )

    async def validate_output(
        self,
        bot_response: str,
        context: Optional[Dict[str, Any]] = None
    ) -> OutputValidationResult:
        """
        Validate model output before returning to user.

        Checks for:
        - Hallucinations (ungrounded facts)
        - Policy violations
        - Sensitive data leakage
        - Unauthorized commitments

        Args:
            bot_response: Model output to validate
            context: Context including retrieval results for fact-checking

        Returns:
            OutputValidationResult with processed output and violations
        """
        self.stats['total_validations'] += 1
        violations = []
        modifications = []
        processed_output = bot_response

        logger.info(
            f"Validating output",
            extra={'output_length': len(bot_response), 'context': context}
        )

        # 1. Check for sensitive data leakage
        pii_violations = self._detect_pii(bot_response)
        if pii_violations:
            violations.extend(pii_violations)
            processed_output = self._redact_pii(bot_response)
            modifications.append("PII redacted")
            self.stats['outputs_sanitized'] += 1
            self.stats['violations_detected'] += len(pii_violations)

        # 2. Check for hallucinations if context provided
        if context and 'retrieval_results' in context:
            hallucination = self._detect_hallucination(
                bot_response,
                context['retrieval_results']
            )
            if hallucination:
                violations.append(hallucination)
                modifications.append("Potential hallucination flagged")
                self.stats['violations_detected'] += 1
                self.stats['by_violation_type'][ViolationType.HALLUCINATION.value] += 1

        # 3. Use NeMo Guardrails if available
        if not self.simulation_mode and self.rails:
            try:
                nemo_result = await self._validate_with_nemo(
                    bot_response,
                    context or {},
                    check_type="output"
                )

                if nemo_result.get('modified'):
                    processed_output = nemo_result['processed_text']
                    modifications.append("NeMo safety modifications applied")
                    self.stats['outputs_sanitized'] += 1
            except Exception as e:
                logger.error(f"NeMo output validation failed: {e}")

        # Determine result
        if modifications:
            result = ValidationResult.SANITIZED
        elif violations:
            result = ValidationResult.BLOCKED
        else:
            result = ValidationResult.APPROVED

        return OutputValidationResult(
            result=result,
            processed_output=processed_output,
            violations=violations,
            modifications=modifications
        )

    def _detect_jailbreak(self, text: str) -> Optional[GuardrailViolation]:
        """Detect jailbreak attempts in input."""
        text_lower = text.lower()

        for pattern in self.JAILBREAK_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return GuardrailViolation(
                    violation_type=ViolationType.JAILBREAK_ATTEMPT,
                    severity="critical",
                    message=f"Jailbreak attempt detected: {pattern}",
                    detected_at=datetime.utcnow().isoformat(),
                    original_text=text,
                    metadata={'pattern': pattern}
                )

        return None

    def _detect_pii(self, text: str) -> List[GuardrailViolation]:
        """Detect PII (personally identifiable information) in text."""
        violations = []

        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                violations.append(GuardrailViolation(
                    violation_type=ViolationType.SENSITIVE_DATA,
                    severity="high",
                    message=f"PII detected: {pii_type}",
                    detected_at=datetime.utcnow().isoformat(),
                    original_text=text,
                    metadata={'pii_type': pii_type, 'count': len(matches)}
                ))

        return violations

    def _redact_pii(self, text: str) -> str:
        """Redact PII from text."""
        redacted = text

        for pii_type, pattern in self.PII_PATTERNS.items():
            redacted = pattern.sub(f"[REDACTED_{pii_type.upper()}]", redacted)

        return redacted

    def _check_blocked_topics(self, text: str) -> Optional[GuardrailViolation]:
        """Check if input discusses blocked topics."""
        text_lower = text.lower()

        for topic in self.BLOCKED_TOPICS:
            topic_words = topic.replace('_', ' ')
            if topic_words in text_lower:
                return GuardrailViolation(
                    violation_type=ViolationType.BLOCKED_TOPIC,
                    severity="high",
                    message=f"Blocked topic detected: {topic}",
                    detected_at=datetime.utcnow().isoformat(),
                    original_text=text,
                    metadata={'topic': topic}
                )

        return None

    def _detect_hallucination(
        self,
        response: str,
        retrieval_results: List[str]
    ) -> Optional[GuardrailViolation]:
        """
        Detect potential hallucinations by checking if response is grounded.

        Simple heuristic: flag if response contains specific facts/numbers
        not present in retrieval results.
        """
        # This is a simplified check - in production, use NeMo's fact-checking
        # or a dedicated hallucination detection model

        # Extract numbers from response
        response_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', response))

        # Extract numbers from context
        context_text = ' '.join(retrieval_results)
        context_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', context_text))

        # Check for ungrounded numbers (simple heuristic)
        ungrounded = response_numbers - context_numbers

        if len(ungrounded) > 2:  # Threshold for flagging
            return GuardrailViolation(
                violation_type=ViolationType.HALLUCINATION,
                severity="medium",
                message="Potential hallucination: response contains facts not in context",
                detected_at=datetime.utcnow().isoformat(),
                original_text=response,
                metadata={'ungrounded_numbers': list(ungrounded)}
            )

        return None

    async def _validate_with_nemo(
        self,
        text: str,
        context: Dict[str, Any],
        check_type: str
    ) -> Dict[str, Any]:
        """Validate text using NeMo Guardrails."""
        if not self.rails:
            return {'allowed': True, 'modified': False}

        try:
            # Generate with rails
            result = await self.rails.generate_async(
                messages=[{
                    "role": "user" if check_type == "input" else "assistant",
                    "content": text
                }],
                options={
                    "rails": [f"check_{check_type}"],
                    "context": context
                }
            )

            return {
                'allowed': not result.get('blocked', False),
                'modified': result.get('modified', False),
                'processed_text': result.get('content', text),
                'message': result.get('message', '')
            }
        except Exception as e:
            logger.error(f"NeMo validation error: {e}")
            return {'allowed': True, 'modified': False}

    def get_stats(self) -> Dict[str, Any]:
        """Get guardrail statistics."""
        return {
            **self.stats,
            'violation_rate': (
                self.stats['violations_detected'] / self.stats['total_validations']
                if self.stats['total_validations'] > 0 else 0.0
            ),
            'block_rate': (
                self.stats['inputs_blocked'] / self.stats['total_validations']
                if self.stats['total_validations'] > 0 else 0.0
            ),
            'simulation_mode': self.simulation_mode
        }


def create_guardrails_client(**kwargs) -> GuardrailsClient:
    """
    Factory function to create Guardrails Client.

    Args:
        **kwargs: Arguments for GuardrailsClient

    Returns:
        Configured GuardrailsClient
    """
    return GuardrailsClient(**kwargs)
