"""
Agent Template Schema

YAML-based agent template system for community-contributed agents.

Template Structure:
- Metadata (name, description, author, version, tags)
- Agent configuration (type, model, prompts)
- Required capabilities (tools, integrations)
- Default policies
- Memory configuration
- Examples and test cases

Philosophy:
- One-click deployment
- Validated before publishing
- Versioned and immutable
- Community ratings and reviews
"""

import yaml
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from jsonschema import validate, ValidationError as JSONSchemaValidationError

logger = logging.getLogger(__name__)


class AgentCategory(Enum):
    """Agent template categories."""
    FINANCE = "finance"
    HR = "hr"
    OPERATIONS = "operations"
    CYBERSECURITY = "cybersecurity"
    GOVERNANCE = "governance"
    SELFOPS = "selfops"
    CUSTOMER_SERVICE = "customer_service"
    MARKETING = "marketing"
    SALES = "sales"
    LEGAL = "legal"
    IT = "it"
    GENERAL = "general"


@dataclass
class AgentTemplateMetadata:
    """Agent template metadata."""
    template_id: str
    name: str
    description: str
    author: str
    version: str
    category: AgentCategory
    tags: List[str] = field(default_factory=list)
    license: str = "MIT"
    homepage: Optional[str] = None
    documentation: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class AgentConfig:
    """Agent configuration from template."""
    agent_type: str
    specialization: str
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None


@dataclass
class RequiredCapability:
    """Required capability (tool, integration, etc.)."""
    capability_type: str  # "tool", "integration", "mcp_server"
    name: str
    version: Optional[str] = None
    required: bool = True
    description: Optional[str] = None


@dataclass
class AgentTemplate:
    """
    Complete agent template.

    Can be serialized to/from YAML for community sharing.
    """
    metadata: AgentTemplateMetadata
    config: AgentConfig
    capabilities: List[RequiredCapability] = field(default_factory=list)
    policies: List[str] = field(default_factory=list)  # OPA Rego policies
    memory_config: Optional[Dict[str, Any]] = None
    examples: List[Dict[str, str]] = field(default_factory=list)
    test_cases: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_yaml(self) -> str:
        """Serialize to YAML."""
        data = self.to_dict()
        # Convert enums to strings
        data["metadata"]["category"] = data["metadata"]["category"].value
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "AgentTemplate":
        """Deserialize from YAML."""
        data = yaml.safe_load(yaml_str)

        # Parse metadata
        metadata = AgentTemplateMetadata(
            template_id=data["metadata"]["template_id"],
            name=data["metadata"]["name"],
            description=data["metadata"]["description"],
            author=data["metadata"]["author"],
            version=data["metadata"]["version"],
            category=AgentCategory(data["metadata"]["category"]),
            tags=data["metadata"].get("tags", []),
            license=data["metadata"].get("license", "MIT"),
            homepage=data["metadata"].get("homepage"),
            documentation=data["metadata"].get("documentation"),
            created_at=data["metadata"].get("created_at"),
            updated_at=data["metadata"].get("updated_at"),
        )

        # Parse config
        config = AgentConfig(**data["config"])

        # Parse capabilities
        capabilities = [
            RequiredCapability(**cap) for cap in data.get("capabilities", [])
        ]

        return cls(
            metadata=metadata,
            config=config,
            capabilities=capabilities,
            policies=data.get("policies", []),
            memory_config=data.get("memory_config"),
            examples=data.get("examples", []),
            test_cases=data.get("test_cases", []),
        )

    def validate(self) -> bool:
        """
        Validate template against schema.

        Returns:
            True if valid

        Raises:
            ValidationError: If template is invalid
        """
        # Basic validation
        if not self.metadata.template_id:
            raise ValueError("Template ID is required")

        if not self.metadata.name:
            raise ValueError("Template name is required")

        if not self.config.agent_type:
            raise ValueError("Agent type is required")

        if not self.config.specialization:
            raise ValueError("Agent specialization is required")

        # Temperature range
        if not (0 <= self.config.temperature <= 2):
            raise ValueError("Temperature must be between 0 and 2")

        # Max tokens range
        if not (1 <= self.config.max_tokens <= 32000):
            raise ValueError("Max tokens must be between 1 and 32000")

        # Version format (semver)
        import re
        if not re.match(r"^\d+\.\d+\.\d+$", self.metadata.version):
            raise ValueError("Version must follow semver format (e.g., 1.0.0)")

        logger.info(f"Template '{self.metadata.template_id}' validation passed")
        return True


class TemplateRegistry:
    """
    Agent template registry.

    Manages template catalog, versioning, ratings, and deployment.
    """

    def __init__(self, registry_path: str = "marketplace/templates"):
        """
        Initialize template registry.

        Args:
            registry_path: Path to template storage directory
        """
        self.registry_path = registry_path
        self._templates: Dict[str, AgentTemplate] = {}

    def register_template(self, template: AgentTemplate):
        """
        Register a new template.

        Args:
            template: Agent template to register

        Raises:
            ValueError: If template validation fails or already exists
        """
        # Validate template
        template.validate()

        # Check for duplicates
        if template.metadata.template_id in self._templates:
            existing = self._templates[template.metadata.template_id]
            logger.warning(
                f"Template '{template.metadata.template_id}' already exists "
                f"(version {existing.metadata.version})"
            )
            raise ValueError(
                f"Template '{template.metadata.template_id}' already registered"
            )

        # Register
        self._templates[template.metadata.template_id] = template
        logger.info(
            f"Registered template: {template.metadata.template_id} v{template.metadata.version}"
        )

        # Save to file
        self._save_template(template)

    def get_template(self, template_id: str) -> Optional[AgentTemplate]:
        """
        Get template by ID.

        Args:
            template_id: Template identifier

        Returns:
            AgentTemplate or None if not found
        """
        return self._templates.get(template_id)

    def list_templates(
        self, category: Optional[AgentCategory] = None, tags: Optional[List[str]] = None
    ) -> List[AgentTemplate]:
        """
        List all templates with optional filtering.

        Args:
            category: Filter by category
            tags: Filter by tags (any match)

        Returns:
            List of matching templates
        """
        templates = list(self._templates.values())

        # Filter by category
        if category:
            templates = [t for t in templates if t.metadata.category == category]

        # Filter by tags
        if tags:
            templates = [
                t for t in templates
                if any(tag in t.metadata.tags for tag in tags)
            ]

        return templates

    def search_templates(self, query: str) -> List[AgentTemplate]:
        """
        Search templates by name or description.

        Args:
            query: Search query

        Returns:
            List of matching templates
        """
        query_lower = query.lower()
        results = []

        for template in self._templates.values():
            if (
                query_lower in template.metadata.name.lower()
                or query_lower in template.metadata.description.lower()
                or any(query_lower in tag.lower() for tag in template.metadata.tags)
            ):
                results.append(template)

        return results

    def _save_template(self, template: AgentTemplate):
        """Save template to YAML file."""
        import os

        # Create directory if not exists
        os.makedirs(self.registry_path, exist_ok=True)

        # Save template
        filepath = os.path.join(
            self.registry_path, f"{template.metadata.template_id}.yaml"
        )

        with open(filepath, "w") as f:
            f.write(template.to_yaml())

        logger.info(f"Template saved to {filepath}")

    def load_templates_from_disk(self):
        """Load all templates from disk."""
        import os

        if not os.path.exists(self.registry_path):
            logger.warning(f"Registry path not found: {self.registry_path}")
            return

        for filename in os.listdir(self.registry_path):
            if filename.endswith(".yaml"):
                filepath = os.path.join(self.registry_path, filename)
                try:
                    with open(filepath, "r") as f:
                        template = AgentTemplate.from_yaml(f.read())
                        self._templates[template.metadata.template_id] = template
                        logger.info(f"Loaded template: {template.metadata.template_id}")
                except Exception as e:
                    logger.error(f"Error loading template {filepath}: {e}")


# Global template registry
_registry: Optional[TemplateRegistry] = None


def get_template_registry(registry_path: str = "marketplace/templates") -> TemplateRegistry:
    """
    Get or create the global TemplateRegistry instance.

    Args:
        registry_path: Path to template storage

    Returns:
        TemplateRegistry singleton
    """
    global _registry

    if _registry is None:
        _registry = TemplateRegistry(registry_path=registry_path)
        _registry.load_templates_from_disk()

    return _registry
