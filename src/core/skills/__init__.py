"""
Generic Agent Skills system (SKILL.md packs + registry).

See docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.5.
"""
from src.core.skills.registry import SKILL_FILE_GLOB, Skill, SkillRegistry

__all__ = ["Skill", "SkillRegistry", "SKILL_FILE_GLOB"]
