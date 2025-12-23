# Agent Template Creation Guide

Learn how to create, validate, and publish agent templates to the ANTS Marketplace.

## Table of Contents

1. [Overview](#overview)
2. [Template Structure](#template-structure)
3. [Creating a Template](#creating-a-template)
4. [Validation](#validation)
5. [Testing](#testing)
6. [Publishing](#publishing)
7. [Best Practices](#best-practices)

## Overview

Agent templates are YAML-based configurations that enable one-click deployment of pre-configured AI agents.

**Benefits**:
- Reusable agent configurations
- Community contributions
- Standardized patterns
- Quality assurance through validation
- Version management
- Easy deployment

## Template Structure

A complete agent template includes:

```yaml
metadata:
  template_id: unique-template-id
  name: Human Readable Name
  description: Detailed description
  author: Your Name or Organization
  version: 1.0.0  # Semver
  category: finance|hr|operations|cybersecurity|governance|selfops
  tags: [tag1, tag2, tag3]
  license: MIT
  homepage: https://github.com/your-org/templates
  documentation: https://docs.your-org/templates/template-id
  created_at: "2024-12-23T00:00:00Z"
  updated_at: "2024-12-23T00:00:00Z"

config:
  agent_type: finance|hr|operations|cybersecurity|governance|selfops
  specialization: specific_domain_specialization
  model: gpt-4|gpt-4-turbo|claude-3|llama-3
  temperature: 0.0-2.0
  max_tokens: 1-32000
  system_prompt: |
    Detailed system prompt defining agent behavior, rules, and responsibilities
  user_prompt_template: |
    Template with placeholders: {variable_name}

capabilities:
  - capability_type: tool|integration|mcp_server
    name: capability_name
    version: "1.0.0"  # Optional
    required: true|false
    description: What this capability does

policies:
  - |
    # OPA Rego policy code
    package ants.your_domain
    ...

memory_config:
  episodic:
    enabled: true|false
    retention_days: 90
  semantic:
    enabled: true|false
    description: What semantic memory stores
  procedural:
    enabled: true|false
    description: What procedural memory stores

examples:
  - input: Example task description
    expected_output: Example expected result

test_cases:
  - name: test_name
    description: What this test validates
    input: Test input data
    expected: Expected result
```

## Creating a Template

### Step 1: Define Metadata

Start with clear, descriptive metadata:

```yaml
metadata:
  template_id: sales-lead-qualification  # Unique, lowercase, hyphenated
  name: Sales Lead Qualification Agent
  description: |
    Automated lead scoring and qualification agent.

    Features:
    - Analyze lead data from CRM
    - Score based on BANT criteria
    - Recommend next actions
    - Integration with CRM systems

  author: ANTS Community
  version: 1.0.0
  category: sales
  tags:
    - sales
    - lead-qualification
    - crm
    - automation
  license: MIT
```

**Metadata Guidelines**:
- `template_id`: Unique, lowercase, hyphen-separated
- `name`: User-friendly display name
- `description`: Detailed (use YAML multi-line `|`)
- `version`: Follow semver (1.0.0, 1.1.0, 2.0.0)
- `category`: Must be one of predefined categories
- `tags`: 3-7 relevant keywords

### Step 2: Configure Agent Behavior

Define the agent's core configuration:

```yaml
config:
  agent_type: sales
  specialization: lead_qualification
  model: gpt-4
  temperature: 0.5  # Balanced for lead scoring
  max_tokens: 2000

  system_prompt: |
    You are an expert Sales Lead Qualification Agent.

    Your responsibilities:
    1. Analyze lead data (company, role, industry, engagement)
    2. Score leads based on BANT criteria:
       - Budget: Financial capacity to purchase
       - Authority: Decision-making power
       - Need: Pain points and requirements match
       - Timeline: Urgency and buying timeline
    3. Recommend next actions (call, email, nurture, disqualify)
    4. Generate personalized outreach suggestions

    Scoring:
    - Hot Lead (80-100): High BANT score, immediate action
    - Warm Lead (50-79): Moderate fit, nurture
    - Cold Lead (0-49): Low fit, long-term nurture or disqualify

  user_prompt_template: |
    Qualify the following lead:

    Lead Information:
    - Company: {company_name}
    - Industry: {industry}
    - Contact: {contact_name} ({job_title})
    - Email: {email}
    - Company Size: {company_size}
    - Revenue: {annual_revenue}

    Engagement:
    {engagement_data}

    Please provide lead score, qualification assessment, and recommended next steps.
```

**Configuration Guidelines**:
- `temperature`: 0.0-0.3 for factual tasks, 0.4-0.7 for balanced, 0.8-2.0 for creative
- `max_tokens`: Estimate based on task complexity
- `system_prompt`: Be specific, provide rules and examples
- `user_prompt_template`: Use `{placeholders}` for variables

### Step 3: Define Capabilities

List required tools, integrations, and MCP servers:

```yaml
capabilities:
  - capability_type: integration
    name: crm_connector
    version: "1.0.0"
    required: true
    description: CRM integration for lead data

  - capability_type: tool
    name: lead_enrichment
    required: false
    description: Enrich lead data with company information

  - capability_type: mcp_server
    name: email_sender
    required: false
    description: Send personalized outreach emails
```

**Capability Types**:
- `tool`: Python function/class that agent can call
- `integration`: External system connector (CRM, ERP, etc.)
- `mcp_server`: Model Context Protocol server for extended functionality

**Required vs. Optional**:
- `required: true`: Agent cannot function without this
- `required: false`: Enhanced functionality, but not essential

### Step 4: Add Policies

Define authorization and governance policies using OPA Rego:

```yaml
policies:
  - |
    # Sales Agent Access Policy
    package ants.sales

    import future.keywords.if

    # Sales team can execute
    allow if {
        input.user.department == "sales"
        input.action == "execute"
    }

    # Sales managers can view all leads
    allow if {
        input.user.role == "sales_manager"
        input.action == "read"
    }

  - |
    # PII Protection Policy
    package ants.sales.pii

    import future.keywords.if

    # Mask PII for users without sales role
    mask_pii if {
        not input.user.department == "sales"
    }
```

**Policy Best Practices**:
- Always include access control policies
- Protect PII and sensitive data
- Use clear, descriptive package names
- Test policies thoroughly

### Step 5: Configure Memory

Define what the agent should remember:

```yaml
memory_config:
  episodic:
    enabled: true
    retention_days: 180  # Remember past lead interactions
  semantic:
    enabled: true
    description: Store lead scoring rules, industry insights, BANT criteria
  procedural:
    enabled: true
    description: Store learned qualification workflows, successful patterns
```

### Step 6: Add Examples

Provide clear input/output examples:

```yaml
examples:
  - input: |
      Qualify lead: Acme Corp (Enterprise SaaS, 500 employees, $50M revenue)
      Contact: Jane Smith (VP Engineering)
      Engagement: Downloaded whitepaper, attended webinar, requested demo
    expected_output: |
      **Lead Score: 85/100 (HOT LEAD)**

      BANT Assessment:
      - Budget: HIGH (Enterprise company, $50M revenue)
      - Authority: HIGH (VP Engineering, decision maker for technical tools)
      - Need: HIGH (Engaged with product content, requested demo)
      - Timeline: MEDIUM (Active engagement suggests near-term interest)

      Recommendation: IMMEDIATE FOLLOW-UP
      - Schedule demo within 2 business days
      - Prepare enterprise pricing and case studies
      - Involve Solutions Engineer
      - Focus on scalability and integration capabilities

  - input: |
      Qualify lead: Small Business Inc (10 employees, $1M revenue)
      Contact: John Doe (Office Manager)
      Engagement: Visited pricing page once, no other activity
    expected_output: |
      **Lead Score: 25/100 (COLD LEAD)**

      BANT Assessment:
      - Budget: LOW (Small business, limited budget)
      - Authority: LOW (Office Manager, not decision maker)
      - Need: UNCERTAIN (Minimal engagement, unclear pain points)
      - Timeline: LOW (Single page visit, no follow-up)

      Recommendation: NURTURE CAMPAIGN
      - Add to email nurture sequence
      - Share customer success stories (SMB focus)
      - Revisit in 90 days
```

### Step 7: Create Test Cases

Write automated test cases:

```yaml
test_cases:
  - name: test_hot_lead_identification
    description: Correctly identify hot leads with high BANT score
    input:
      company_name: Enterprise Corp
      company_size: 1000
      annual_revenue: $100M
      job_title: CTO
      engagement_data:
        - Downloaded whitepaper
        - Attended webinar
        - Requested demo
    expected:
      score_range: [80, 100]
      recommendation: IMMEDIATE_FOLLOW_UP

  - name: test_cold_lead_identification
    description: Correctly identify cold leads with low BANT score
    input:
      company_name: Small Startup
      company_size: 5
      annual_revenue: $500K
      job_title: Intern
      engagement_data:
        - Visited website once
    expected:
      score_range: [0, 49]
      recommendation: NURTURE_OR_DISQUALIFY
```

## Validation

Validate your template before publishing:

```bash
# Validate template structure and schema
python marketplace/validate_template.py sales-lead-qualification

# Run dry-run deployment (no actual deployment)
python marketplace/deploy_template.py sales-lead-qualification \
    --tenant test-tenant \
    --dry-run

# Run test cases
python marketplace/test_template.py sales-lead-qualification
```

**Validation Checklist**:
- ✓ Valid YAML syntax
- ✓ All required fields present
- ✓ Valid semver version
- ✓ Temperature in range (0-2)
- ✓ Max tokens in range (1-32000)
- ✓ Template ID is unique
- ✓ System prompt is clear and detailed
- ✓ At least 2 examples provided
- ✓ At least 3 test cases with expected results
- ✓ Policies validate with OPA

## Testing

Test your template thoroughly:

### 1. Unit Tests (Test Cases)

Test cases in the template are run automatically during deployment.

### 2. Integration Tests

Deploy to staging environment and test end-to-end:

```bash
# Deploy to staging
python marketplace/deploy_template.py sales-lead-qualification \
    --tenant staging-tenant \
    --api-url https://api-staging.ants.ai/v1

# Test via API
curl -X POST https://api-staging.ants.ai/v1/agents/{agent_id}/execute \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "task_description": "Qualify lead: Acme Corp..."
  }'
```

### 3. User Acceptance Testing

Have sales team members test the agent with real lead data.

## Publishing

### Step 1: Submit to Community Templates

```bash
# Fork the ANTS repository
git clone https://github.com/your-username/ants.git

# Create feature branch
git checkout -b template/sales-lead-qualification

# Add your template
cp sales-lead-qualification.yaml marketplace/templates/

# Commit
git add marketplace/templates/sales-lead-qualification.yaml
git commit -m "Add sales lead qualification template"

# Push and create pull request
git push origin template/sales-lead-qualification
```

### Step 2: Pull Request Review

Your template will be reviewed for:
- Code quality and completeness
- Security (policies, PII protection)
- Usefulness to community
- Documentation clarity
- Test coverage

### Step 3: Publication

Once approved:
- Template is merged to main branch
- Available in marketplace
- Versioned and immutable
- Discoverable via search

## Best Practices

### 1. Clarity and Documentation

- Write clear, detailed descriptions
- Provide comprehensive examples
- Document all capabilities and requirements
- Include troubleshooting tips

### 2. Security

- Always include access control policies
- Protect PII and sensitive data
- Never hardcode credentials
- Use secrets management (Azure Key Vault)

### 3. Testability

- Write thorough test cases
- Cover edge cases and error scenarios
- Test with real data when possible
- Include performance benchmarks

### 4. Reusability

- Make templates generic and configurable
- Use prompt templates with placeholders
- Avoid hardcoding company-specific logic
- Support multiple deployment scenarios

### 5. Maintainability

- Follow semver for versioning
- Document breaking changes
- Keep dependencies minimal
- Update documentation when changing behavior

### 6. Performance

- Optimize token usage (concise prompts)
- Use appropriate temperature settings
- Consider cost implications
- Monitor CLEAR metrics

## Template Examples

Browse existing templates for inspiration:

- **Finance**: `finance-ap-reconciliation.yaml`
- **HR**: `hr-onboarding-assistant.yaml`
- **Cybersecurity**: `cybersecurity-incident-response.yaml`
- **Sales**: `sales-lead-qualification.yaml`
- **Customer Service**: `customer-service-support.yaml`

## Community

- **Discussions**: https://github.com/ants/discussions
- **Templates Repo**: https://github.com/ants-community/templates
- **Discord**: https://discord.gg/ants-community

## Support

- **Documentation**: https://docs.ants.ai
- **Issues**: https://github.com/ants/issues
- **Email**: templates@ants.ai

---

Happy template building! 🚀
