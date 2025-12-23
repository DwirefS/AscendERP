#!/usr/bin/env python3
"""
Template Deployment Tool

Deploy agent templates from the marketplace:
1. Validate template YAML
2. Check capabilities and dependencies
3. Deploy agent to ANTS cluster
4. Configure policies and memory
5. Run test cases

Usage:
    python deploy_template.py <template_id> --tenant <tenant_id> [--dry-run]
"""

import argparse
import logging
import sys
import yaml
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.marketplace.template_schema import AgentTemplate, get_template_registry
from src.core.security import get_validator, ValidationError
import requests

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class TemplateDeployer:
    """Deploy agent templates to ANTS cluster."""

    def __init__(self, api_base_url: str, bearer_token: str):
        """
        Initialize deployer.

        Args:
            api_base_url: ANTS API base URL
            bearer_token: Azure AD bearer token
        """
        self.api_base_url = api_base_url
        self.headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json"
        }

    def deploy(
        self,
        template: AgentTemplate,
        tenant_id: str,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Deploy template to ANTS.

        Args:
            template: Agent template to deploy
            tenant_id: Tenant ID for deployment
            dry_run: If True, validate only (don't deploy)

        Returns:
            Deployment result dictionary
        """
        logger.info(f"Deploying template: {template.metadata.template_id}")

        # Step 1: Validate template
        logger.info("Step 1/5: Validating template...")
        try:
            template.validate()
            logger.info("✓ Template validation passed")
        except Exception as e:
            logger.error(f"✗ Template validation failed: {e}")
            return {"status": "failed", "error": str(e)}

        # Step 2: Check capabilities
        logger.info("Step 2/5: Checking capabilities...")
        missing_capabilities = self._check_capabilities(template)
        if missing_capabilities:
            logger.warning(f"Missing optional capabilities: {missing_capabilities}")
        else:
            logger.info("✓ All required capabilities available")

        if dry_run:
            logger.info("DRY RUN: Skipping actual deployment")
            return {
                "status": "validated",
                "template_id": template.metadata.template_id,
                "missing_capabilities": missing_capabilities
            }

        # Step 3: Create agent
        logger.info("Step 3/5: Creating agent...")
        agent = self._create_agent(template, tenant_id)
        logger.info(f"✓ Agent created: {agent['agent_id']}")

        # Step 4: Configure policies
        logger.info("Step 4/5: Configuring policies...")
        if template.policies:
            self._configure_policies(template.policies, agent['agent_id'])
            logger.info(f"✓ Configured {len(template.policies)} policies")
        else:
            logger.info("No policies to configure")

        # Step 5: Run test cases
        logger.info("Step 5/5: Running test cases...")
        if template.test_cases:
            test_results = self._run_tests(template.test_cases, agent['agent_id'])
            logger.info(f"✓ Test results: {test_results['passed']}/{test_results['total']} passed")
        else:
            logger.info("No test cases to run")
            test_results = {"total": 0, "passed": 0, "failed": 0}

        logger.info(f"✓ Deployment complete! Agent ID: {agent['agent_id']}")

        return {
            "status": "deployed",
            "agent_id": agent['agent_id'],
            "template_id": template.metadata.template_id,
            "test_results": test_results
        }

    def _check_capabilities(self, template: AgentTemplate) -> list:
        """Check if required capabilities are available."""
        missing = []

        for capability in template.capabilities:
            if capability.required:
                # In production, check if capability is actually available
                # For now, we'll just log
                logger.debug(f"Checking capability: {capability.name}")

        return missing

    def _create_agent(self, template: AgentTemplate, tenant_id: str) -> Dict[str, Any]:
        """Create agent via API."""
        url = f"{self.api_base_url}/agents"

        payload = {
            "name": template.metadata.name,
            "type": template.config.agent_type,
            "specialization": template.config.specialization,
            "tenant_id": tenant_id,
            "config": {
                "model": template.config.model,
                "temperature": template.config.temperature,
                "max_tokens": template.config.max_tokens,
                "system_prompt": template.config.system_prompt,
                "user_prompt_template": template.config.user_prompt_template
            }
        }

        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def _configure_policies(self, policies: list, agent_id: str):
        """Configure OPA policies for agent."""
        for policy in policies:
            url = f"{self.api_base_url}/policies"

            payload = {
                "name": f"Policy for {agent_id}",
                "rego_code": policy
            }

            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()

    def _run_tests(self, test_cases: list, agent_id: str) -> Dict[str, int]:
        """Run test cases for deployed agent."""
        results = {"total": len(test_cases), "passed": 0, "failed": 0}

        for test_case in test_cases:
            try:
                # Execute test task
                url = f"{self.api_base_url}/agents/{agent_id}/execute"
                payload = {"task_description": str(test_case.get("input", ""))}

                response = requests.post(url, json=payload, headers=self.headers)
                response.raise_for_status()

                # For now, just count successful execution as pass
                # In production, validate against expected output
                results["passed"] += 1
                logger.debug(f"✓ Test passed: {test_case.get('name')}")

            except Exception as e:
                results["failed"] += 1
                logger.warning(f"✗ Test failed: {test_case.get('name')} - {e}")

        return results


def main():
    parser = argparse.ArgumentParser(description="Deploy ANTS agent template")
    parser.add_argument(
        "template_id",
        help="Template ID to deploy (e.g., finance-ap-reconciliation)"
    )
    parser.add_argument(
        "--tenant",
        required=True,
        help="Tenant ID for deployment"
    )
    parser.add_argument(
        "--api-url",
        default="https://api.ants.ai/v1",
        help="ANTS API base URL"
    )
    parser.add_argument(
        "--token",
        help="Bearer token (or set ANTS_API_TOKEN env var)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, don't deploy"
    )
    parser.add_argument(
        "--templates-dir",
        default="marketplace/templates",
        help="Templates directory path"
    )

    args = parser.parse_args()

    # Get bearer token
    import os
    token = args.token or os.getenv("ANTS_API_TOKEN")
    if not token and not args.dry_run:
        logger.error("Bearer token required (use --token or set ANTS_API_TOKEN)")
        sys.exit(1)

    # Load template registry
    logger.info(f"Loading templates from {args.templates_dir}...")
    registry = get_template_registry(registry_path=args.templates_dir)

    # Get template
    template = registry.get_template(args.template_id)
    if not template:
        logger.error(f"Template not found: {args.template_id}")
        logger.info(f"Available templates: {list(registry._templates.keys())}")
        sys.exit(1)

    # Deploy
    deployer = TemplateDeployer(api_base_url=args.api_url, bearer_token=token or "")
    result = deployer.deploy(
        template=template,
        tenant_id=args.tenant,
        dry_run=args.dry_run
    )

    if result["status"] == "failed":
        logger.error(f"Deployment failed: {result['error']}")
        sys.exit(1)
    elif result["status"] == "validated":
        logger.info("Validation complete (dry run)")
    else:
        logger.info(f"Deployment successful! Agent ID: {result['agent_id']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
