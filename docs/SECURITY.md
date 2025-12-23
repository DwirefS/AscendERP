# Security Hardening Guide

## Overview

ANTS implements comprehensive security hardening across all layers:

- **Secrets Management**: Azure Key Vault integration
- **Input Validation**: Defense against injection attacks
- **Rate Limiting**: DDoS protection and resource throttling
- **Audit Logging**: Tamper-evident security event tracking
- **Encryption**: AES-256-GCM for data at rest and in transit
- **Authentication**: Azure AD integration with JWT validation
- **Authorization**: RBAC and policy-based access control
- **Network Security**: Zero-trust networking, private endpoints
- **Container Security**: Pod security policies, least privilege

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Security Layers                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Azure AD     │  │   Key Vault  │  │   Defender   │     │
│  │ (AuthN/AuthZ)│  │  (Secrets)   │  │  (Threat)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                 │                  │              │
│         └─────────────────┴──────────────────┘              │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────┐       │
│  │          Security Module (Python)                │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │       │
│  │  │ Secrets  │ │Validator │ │  Audit   │        │       │
│  │  │ Manager  │ │  Input   │ │  Logger  │        │       │
│  │  └──────────┘ └──────────┘ └──────────┘        │       │
│  └──────────────────────────────────────────────────┘       │
│                           │                                 │
│  ┌────────────────────────┴────────────────────────┐       │
│  │          Agent Runtime (Kubernetes)              │       │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐        │       │
│  │  │   Pod    │ │ Network  │ │  RBAC    │        │       │
│  │  │ Security │ │ Policies │ │  Roles   │        │       │
│  │  └──────────┘ └──────────┘ └──────────┘        │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Security Components

### 1. Secrets Management

**Azure Key Vault Integration** (`src/core/security/secrets_manager.py`)

```python
from src.core.security import get_secrets_manager

# Initialize secrets manager
secrets = get_secrets_manager(
    key_vault_url="https://ants-kv-prod.vault.azure.net/",
    use_managed_identity=True
)

# Retrieve secrets
api_key = secrets.get_api_key("openai")
db_conn = secrets.get_connection_string("postgresql")

# Cache invalidation (on rotation)
secrets.invalidate_cache("openai-api-key")
```

**Features**:
- Lazy loading and caching (1-hour TTL)
- Automatic rotation detection
- Managed Identity authentication
- Audit logging for secret access
- Fallback to environment variables (dev only)

**Infrastructure** (`infra/terraform/modules/security/`):
- Private endpoints for Key Vault
- RBAC-based access control
- Network ACLs (deny all by default)
- Purge protection enabled
- 90-day soft delete retention

### 2. Input Validation

**InputValidator** (`src/core/security/input_validator.py`)

Prevents:
- Prompt injection attacks
- SQL injection
- XSS (cross-site scripting)
- Path traversal
- Command injection

```python
from src.core.security import get_validator, ValidationError

validator = get_validator()

# Validate AI prompt
try:
    safe_prompt = validator.validate_prompt(user_input)
except ValidationError as e:
    # Log security incident, reject request
    logger.warning(f"Invalid prompt rejected: {e}")

# Validate agent ID
agent_id = validator.validate_agent_id(request.agent_id)

# Validate file path
safe_path = validator.validate_file_path(
    file_path,
    allowed_base_dirs=["/data/agents"]
)

# SQL parameter validation (defense in depth)
validated_param = validator.validate_sql_parameter(user_input)
```

**Detection Patterns**:
- Prompt injection: "ignore previous instructions", "DAN mode", etc.
- SQL injection: `OR '1'='1`, `UNION SELECT`, `DROP TABLE`
- Path traversal: `../`, `..\\`, URL-encoded variants
- Command injection: `; rm -rf`, `$(command)`, backticks

### 3. Rate Limiting

**RateLimiter** (`src/core/security/rate_limiter.py`)

Token bucket algorithm with Redis backend:

```python
from src.core.security import get_rate_limiter, RateLimitExceeded, RATE_LIMIT_TIERS

limiter = get_rate_limiter(redis_client=redis_client)

# Check rate limit
try:
    limiter.check_rate_limit(
        key=f"user:{user_id}",
        config=RATE_LIMIT_TIERS["api_user"],
        cost=1
    )
    # Process request
except RateLimitExceeded as e:
    # Return 429 Too Many Requests
    return {"error": "Rate limit exceeded", "retry_after": e.retry_after}
```

**Rate Limit Tiers**:

| Tier | Limit | Window | Use Case |
|------|-------|--------|----------|
| `agent_execution_user` | 100 | 1 hour | Agent execution per user |
| `agent_execution_tenant` | 1,000 | 1 hour | Agent execution per tenant |
| `api_user` | 1,000 | 1 minute | API calls per user |
| `api_tenant` | 10,000 | 1 minute | API calls per tenant |
| `inference_user` | 50 | 1 minute | LLM inference per user |

### 4. Security Audit Logging

**SecurityAuditor** (`src/core/security/security_audit.py`)

Tamper-evident audit trail with hash-chaining:

```python
from src.core.security import get_security_auditor, SecurityEventType, SecuritySeverity

auditor = get_security_auditor(
    output_file="/var/log/ants/security-audit.log",
    enable_siem=True
)

# Log security event
auditor.log_event(
    event_type=SecurityEventType.AUTH_LOGIN_SUCCESS,
    severity=SecuritySeverity.INFO,
    user_id=user.id,
    tenant_id=user.tenant_id,
    ip_address=request.client.host
)

# Log incident
auditor.log_event(
    event_type=SecurityEventType.INCIDENT_PROMPT_INJECTION_DETECTED,
    severity=SecuritySeverity.WARNING,
    user_id=user.id,
    details={"prompt": masked_prompt, "pattern": pattern}
)
```

**Event Types**:
- Authentication: Login, logout, token issuance
- Authorization: Permission grants/denials, role changes
- Data Access: PII read/write/export
- Security Incidents: Injection attempts, unauthorized access
- Configuration: Policy updates, secret access

**Features**:
- Hash-chained events (tamper detection)
- Anomaly detection (failed login tracking, suspicious IPs)
- SIEM integration (Azure Sentinel)
- Compliance reporting (SOC2, HIPAA, GDPR)

### 5. Encryption

**EncryptionHelper** (`src/core/security/encryption.py`)

AES-256-GCM authenticated encryption:

```python
from src.core.security import get_encryption_helper

crypto = get_encryption_helper()

# Encrypt sensitive data
encrypted = crypto.encrypt("Sensitive customer data", associated_data=b"field_name")

# Decrypt (with authentication)
plaintext = crypto.decrypt_to_string(encrypted, associated_data=b"field_name")

# PII masking for display
masked_cc = crypto.mask_pii("4111111111111111", reveal_last=4)
# Output: "************1111"

# PII tokenization (irreversible)
token = crypto.tokenize_pii("123-45-6789", context="ssn")

# Password hashing
password_hash, salt = crypto.hash_password("SecureP@ssw0rd!")
valid = crypto.verify_password(password, password_hash, salt)

# Secure token generation
api_key = crypto.generate_api_key()  # "ants_<64-hex-chars>"
```

**Algorithms**:
- Encryption: AES-256-GCM (authenticated encryption)
- Key Derivation: PBKDF2-HMAC-SHA256 (100,000 iterations)
- Hashing: SHA-256
- Tokenization: HMAC-SHA256 (deterministic)

### 6. Authentication & Authorization

**AuthManager** (`src/core/security/auth.py`)

Azure AD integration:

```python
from src.core.security import get_auth_manager, AuthorizationError

auth = get_auth_manager(
    tenant_id=os.getenv("AZURE_TENANT_ID"),
    client_id=os.getenv("AZURE_CLIENT_ID"),
    client_secret=secrets.get_secret("azure-client-secret"),
    opa_url="http://opa:8181"
)

# Validate JWT token
try:
    user = auth.validate_jwt_token(request.headers["Authorization"])
except AuthorizationError as e:
    return {"error": "Unauthorized"}, 401

# Check permission (OPA integration)
try:
    auth.require_permission(
        user=user,
        resource=f"agent:{agent_id}",
        action="execute"
    )
except AuthorizationError as e:
    return {"error": "Forbidden"}, 403

# Service-to-service authentication
token = auth.acquire_token_for_client(
    scopes=["https://vault.azure.net/.default"]
)
```

**Authorization Flow**:
```
Request → JWT Validation → User Extraction → OPA Policy Check → Allow/Deny
```

### 7. Infrastructure Security

**Terraform** (`infra/terraform/modules/security/`):

- **Azure Key Vault**:
  - Private endpoints (no public access)
  - RBAC authorization
  - Purge protection
  - 90-day soft delete
  - Audit logging to Log Analytics

- **Managed Identities**:
  - AKS cluster identity
  - Agent workload identity
  - No credential storage

- **Network Security Groups**:
  - Deny all by default
  - Explicit allow rules
  - HTTPS only

- **Azure Defender**:
  - Key Vault threat detection
  - Kubernetes threat detection
  - Storage threat detection

**Kubernetes** (`infra/k8s/security/`):

- **Pod Security Policies**:
  - No privileged containers
  - No host networking
  - Read-only root filesystem
  - Drop all capabilities
  - Run as non-root
  - No privilege escalation

- **Network Policies** (Zero-Trust):
  - Default deny all traffic
  - Explicit allow rules
  - Namespace isolation
  - DNS access allowed
  - Azure services access (HTTPS only)

## Security Best Practices

### Development

1. **Never commit secrets**:
   - Use Key Vault or environment variables
   - `.gitignore` for `.env` files
   - Pre-commit hooks to scan for secrets

2. **Validate all input**:
   ```python
   # Always validate user input
   validated = validator.validate_prompt(user_input)

   # Use parameterized queries
   result = db.execute("SELECT * FROM users WHERE id = ?", [user_id])
   ```

3. **Principle of least privilege**:
   - Minimal RBAC roles
   - Time-limited access
   - Audit all privileged operations

4. **Defense in depth**:
   - Input validation (first line)
   - Parameterized queries (second line)
   - WAF rules (third line)

### Deployment

1. **Enable all security features**:
   ```bash
   # Set environment variables
   export KEY_VAULT_URL="https://ants-kv-prod.vault.azure.net/"
   export OPA_URL="http://opa:8181"
   export ENABLE_SIEM="true"
   ```

2. **Use Managed Identities**:
   - No credential files
   - Automatic rotation
   - Azure-managed security

3. **Network isolation**:
   - Private endpoints for all Azure services
   - Network policies in Kubernetes
   - No public IPs for agent workloads

4. **Monitor security events**:
   - Azure Defender alerts
   - Security audit logs
   - Anomaly detection
   - Failed login tracking

## Security Testing

**Run security tests**:

```bash
# Input validation tests
pytest tests/security/test_input_validation.py -v

# Encryption tests
pytest tests/security/test_encryption.py -v

# All security tests
pytest tests/security/ -v --cov=src/core/security
```

**Security scan**:

```bash
# Container image scanning
trivy image ants-agent:latest

# Dependency vulnerability scanning
safety check

# Secret scanning
truffleHog --regex --entropy=True .
```

## Incident Response

### Detected Prompt Injection

1. **Automatic**: Input validation rejects request
2. **Logging**: Security event logged with pattern
3. **Monitoring**: Alert triggered if threshold exceeded
4. **Response**: IP added to suspicious list, rate limits reduced

### Detected Brute Force

1. **Automatic**: Rate limiter blocks requests
2. **Logging**: Multiple failed logins logged
3. **Anomaly Detection**: IP marked as suspicious
4. **Response**: Temporary ban, notify user

### Compromised Secret

1. **Rotate immediately** in Key Vault
2. **Invalidate cache**: `secrets.invalidate_cache(secret_name)`
3. **Review audit logs**: Who accessed the secret?
4. **Assess impact**: What systems used this secret?
5. **Notify**: Security team, affected users

## Compliance

### SOC2

- ✅ Access controls (RBAC, OPA policies)
- ✅ Audit logging (tamper-evident, hash-chained)
- ✅ Encryption at rest and in transit
- ✅ Network security (NSGs, private endpoints)
- ✅ Change management (Terraform, GitOps)

### HIPAA

- ✅ PHI encryption (AES-256-GCM)
- ✅ Access controls (RBAC, audit logs)
- ✅ PII masking and tokenization
- ✅ Audit trail (365-day retention)
- ✅ Disaster recovery (ANF cross-region replication)

### GDPR

- ✅ Right to be forgotten (data deletion)
- ✅ Data portability (export APIs)
- ✅ Consent management (policy enforcement)
- ✅ Data minimization (PII tokenization)
- ✅ Security breach notification (SIEM alerts)

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Azure Security Baseline](https://docs.microsoft.com/azure/security/fundamentals/security-baseline)
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/security-best-practices/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)

---

**Remember**: Security is not a feature, it's a process. Continuously monitor, test, and improve.
