"""
Security Auditor

Comprehensive security audit logging and monitoring:
- Authentication events (login, logout, failures)
- Authorization events (permission checks, denials)
- Data access (PII, sensitive data)
- Configuration changes
- Security incidents
- Anomaly detection

Immutable audit trail:
- Hash-chained receipts (extends existing AuditLogger)
- Tamper detection
- Compliance reporting (SOC2, HIPAA, GDPR)
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class SecurityEventType(Enum):
    """Security event types for auditing."""

    # Authentication
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILURE = "auth.login.failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_TOKEN_ISSUED = "auth.token.issued"
    AUTH_TOKEN_REVOKED = "auth.token.revoked"
    AUTH_MFA_ENABLED = "auth.mfa.enabled"
    AUTH_MFA_DISABLED = "auth.mfa.disabled"

    # Authorization
    AUTHZ_PERMISSION_GRANTED = "authz.permission.granted"
    AUTHZ_PERMISSION_DENIED = "authz.permission.denied"
    AUTHZ_ROLE_ASSIGNED = "authz.role.assigned"
    AUTHZ_ROLE_REVOKED = "authz.role.revoked"

    # Data Access
    DATA_READ_PII = "data.read.pii"
    DATA_WRITE_PII = "data.write.pii"
    DATA_DELETE_PII = "data.delete.pii"
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"

    # Configuration
    CONFIG_CHANGE = "config.change"
    CONFIG_SECRETS_ACCESS = "config.secrets.access"
    CONFIG_POLICY_UPDATE = "config.policy.update"

    # Security Incidents
    INCIDENT_RATE_LIMIT_EXCEEDED = "incident.rate_limit.exceeded"
    INCIDENT_PROMPT_INJECTION_DETECTED = "incident.prompt_injection.detected"
    INCIDENT_SQL_INJECTION_DETECTED = "incident.sql_injection.detected"
    INCIDENT_PATH_TRAVERSAL_DETECTED = "incident.path_traversal.detected"
    INCIDENT_UNAUTHORIZED_ACCESS = "incident.unauthorized_access"
    INCIDENT_SUSPICIOUS_ACTIVITY = "incident.suspicious_activity"

    # Agent Activity
    AGENT_CREATED = "agent.created"
    AGENT_DELETED = "agent.deleted"
    AGENT_EXECUTION_START = "agent.execution.start"
    AGENT_EXECUTION_COMPLETE = "agent.execution.complete"
    AGENT_EXECUTION_FAILED = "agent.execution.failed"


class SecuritySeverity(Enum):
    """Security event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security audit event."""

    event_type: SecurityEventType
    severity: SecuritySeverity
    timestamp: str
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    agent_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None  # "success", "failure", "denied"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    event_id: Optional[str] = None
    previous_hash: Optional[str] = None  # For hash-chaining
    event_hash: Optional[str] = None  # Hash of this event

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        # Convert enums to strings
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        return data

    def compute_hash(self) -> str:
        """
        Compute cryptographic hash of this event.

        Used for hash-chaining to create tamper-evident audit trail.
        """
        # Create canonical representation
        canonical = {
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "event_id": self.event_id,
            "previous_hash": self.previous_hash,
        }

        # Convert to JSON (sorted keys for determinism)
        canonical_json = json.dumps(canonical, sort_keys=True)

        # SHA-256 hash
        return hashlib.sha256(canonical_json.encode()).hexdigest()


class SecurityAuditor:
    """
    Security audit logger with tamper-evident hash-chaining.

    Extends the existing AuditLogger for security-specific events.
    """

    def __init__(
        self,
        output_file: Optional[str] = None,
        enable_siem: bool = False,
        siem_endpoint: Optional[str] = None,
    ):
        """
        Initialize Security Auditor.

        Args:
            output_file: Path to audit log file
            enable_siem: Send events to SIEM (Azure Sentinel)
            siem_endpoint: SIEM endpoint URL
        """
        self.output_file = output_file
        self.enable_siem = enable_siem
        self.siem_endpoint = siem_endpoint

        # Last event hash (for hash-chaining)
        self._last_hash: Optional[str] = None

        # Anomaly detection state
        self._failed_login_counts: Dict[str, int] = {}
        self._suspicious_ips: set = set()

    def log_event(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity = SecuritySeverity.INFO,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        result: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> SecurityEvent:
        """
        Log a security event.

        Args:
            event_type: Type of security event
            severity: Event severity
            user_id: User who triggered the event
            tenant_id: Tenant context
            agent_id: Agent context (if applicable)
            resource: Resource being accessed
            action: Action being performed
            result: Result of action (success, failure, denied)
            ip_address: Source IP address
            user_agent: User agent string
            details: Additional event details

        Returns:
            SecurityEvent object
        """
        # Create event
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            timestamp=datetime.utcnow().isoformat(),
            user_id=user_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            resource=resource,
            action=action,
            result=result,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            event_id=self._generate_event_id(),
            previous_hash=self._last_hash,
        )

        # Compute hash for this event
        event.event_hash = event.compute_hash()
        self._last_hash = event.event_hash

        # Log to file
        if self.output_file:
            self._write_to_file(event)

        # Log to standard logger
        self._log_to_stdout(event)

        # Send to SIEM
        if self.enable_siem:
            self._send_to_siem(event)

        # Anomaly detection
        self._detect_anomalies(event)

        return event

    def _generate_event_id(self) -> str:
        """Generate unique event ID."""
        import uuid

        return str(uuid.uuid4())

    def _write_to_file(self, event: SecurityEvent):
        """Write event to audit log file."""
        try:
            with open(self.output_file, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Error writing security audit log: {e}")

    def _log_to_stdout(self, event: SecurityEvent):
        """Log event to standard output."""
        log_method = {
            SecuritySeverity.INFO: logger.info,
            SecuritySeverity.WARNING: logger.warning,
            SecuritySeverity.ERROR: logger.error,
            SecuritySeverity.CRITICAL: logger.critical,
        }[event.severity]

        log_method(
            f"SECURITY AUDIT: {event.event_type.value} | "
            f"User: {event.user_id} | Tenant: {event.tenant_id} | "
            f"Resource: {event.resource} | Result: {event.result}"
        )

    def _send_to_siem(self, event: SecurityEvent):
        """Send event to SIEM (Azure Sentinel)."""
        # TODO: Implement Azure Sentinel integration
        # Uses Azure Monitor HTTP Data Collector API
        logger.debug(f"Would send to SIEM: {event.event_id}")

    def _detect_anomalies(self, event: SecurityEvent):
        """
        Detect anomalous security events.

        Patterns:
        - Multiple failed logins from same user/IP
        - Access to PII from suspicious IPs
        - Unusual agent execution patterns
        - Rate limit violations
        """
        # Failed login tracking
        if event.event_type == SecurityEventType.AUTH_LOGIN_FAILURE:
            key = f"{event.user_id}:{event.ip_address}"
            self._failed_login_counts[key] = self._failed_login_counts.get(key, 0) + 1

            if self._failed_login_counts[key] >= 5:
                # Potential brute force attack
                logger.warning(
                    f"ANOMALY DETECTED: Multiple failed logins for {event.user_id} from {event.ip_address}"
                )
                self.log_event(
                    SecurityEventType.INCIDENT_SUSPICIOUS_ACTIVITY,
                    severity=SecuritySeverity.WARNING,
                    user_id=event.user_id,
                    ip_address=event.ip_address,
                    details={
                        "reason": "multiple_failed_logins",
                        "count": self._failed_login_counts[key],
                    },
                )

                # Mark IP as suspicious
                self._suspicious_ips.add(event.ip_address)

        # Successful login resets counter
        if event.event_type == SecurityEventType.AUTH_LOGIN_SUCCESS:
            key = f"{event.user_id}:{event.ip_address}"
            if key in self._failed_login_counts:
                del self._failed_login_counts[key]

        # PII access from suspicious IP
        if (
            event.event_type in [SecurityEventType.DATA_READ_PII, SecurityEventType.DATA_WRITE_PII]
            and event.ip_address in self._suspicious_ips
        ):
            logger.error(
                f"ANOMALY DETECTED: PII access from suspicious IP {event.ip_address}"
            )
            self.log_event(
                SecurityEventType.INCIDENT_UNAUTHORIZED_ACCESS,
                severity=SecuritySeverity.ERROR,
                user_id=event.user_id,
                ip_address=event.ip_address,
                resource=event.resource,
                details={"reason": "pii_access_from_suspicious_ip"},
            )

    def verify_audit_chain(self, events: List[SecurityEvent]) -> bool:
        """
        Verify integrity of audit event chain.

        Args:
            events: List of security events (in chronological order)

        Returns:
            True if chain is valid, False if tampering detected
        """
        previous_hash = None

        for event in events:
            # Check previous hash matches
            if event.previous_hash != previous_hash:
                logger.error(
                    f"AUDIT CHAIN BROKEN: Event {event.event_id} has invalid previous_hash"
                )
                return False

            # Recompute hash and verify
            computed_hash = event.compute_hash()
            if computed_hash != event.event_hash:
                logger.error(
                    f"AUDIT CHAIN BROKEN: Event {event.event_id} has invalid hash"
                )
                return False

            previous_hash = event.event_hash

        logger.info(f"Audit chain verified: {len(events)} events, integrity intact")
        return True

    def generate_compliance_report(
        self, start_date: datetime, end_date: datetime, report_type: str = "SOC2"
    ) -> Dict[str, Any]:
        """
        Generate compliance report for audit period.

        Args:
            start_date: Report start date
            end_date: Report end date
            report_type: Type of report (SOC2, HIPAA, GDPR)

        Returns:
            Compliance report dictionary
        """
        # TODO: Implement compliance report generation
        # Read audit logs, aggregate by event type, generate statistics
        return {
            "report_type": report_type,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_events": 0,
                "auth_events": 0,
                "authz_events": 0,
                "data_access_events": 0,
                "incidents": 0,
            },
        }


# Global security auditor instance
_security_auditor: Optional[SecurityAuditor] = None


def get_security_auditor(
    output_file: Optional[str] = None,
    enable_siem: bool = False,
    siem_endpoint: Optional[str] = None,
) -> SecurityAuditor:
    """
    Get or create the global SecurityAuditor instance.

    Args:
        output_file: Path to audit log file
        enable_siem: Enable SIEM integration
        siem_endpoint: SIEM endpoint URL

    Returns:
        SecurityAuditor singleton instance
    """
    global _security_auditor

    if _security_auditor is None:
        _security_auditor = SecurityAuditor(
            output_file=output_file,
            enable_siem=enable_siem,
            siem_endpoint=siem_endpoint,
        )

    return _security_auditor
