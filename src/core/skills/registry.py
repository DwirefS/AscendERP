"""
Agent Skills system for ANTS (SKILL.md pattern).

Versioned markdown skill packs: YAML frontmatter (name, version, domain,
description, triggers, tools) between ``---`` fences, followed by a markdown
procedure body. A :class:`SkillRegistry` loads packs from disk, matches them
against task text, and renders matched skills into a prompt block that the
agent harness injects into the reasoning context.

Design contract: docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import structlog
import yaml

logger = structlog.get_logger()

SKILL_FILE_GLOB = "*.skill.md"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens of ``text`` (deterministic)."""
    return _TOKEN_RE.findall(text.lower())


def _as_str_list(value: Any) -> List[str]:
    """Coerce a frontmatter value into a list of strings (tolerant)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None]
    return [str(value)]


@dataclass
class Skill:
    """A single versioned skill pack (frontmatter metadata + procedure body)."""

    name: str
    version: str = "0.0.0"
    domain: str = ""
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    body: str = ""
    path: Optional[str] = None

    @staticmethod
    def from_markdown(text: str, path: Optional[str] = None) -> "Skill":
        """
        Parse a ``*.skill.md`` document.

        Expects YAML frontmatter between ``---`` fences followed by a markdown
        body. Missing optional fields are tolerated; a missing ``name`` falls
        back to the file stem (or ``"unnamed"``).
        """
        meta: Dict[str, Any] = {}
        body = text
        match = _FRONTMATTER_RE.match(text)
        if match:
            body = text[match.end():]
            try:
                loaded = yaml.safe_load(match.group(1))
                if isinstance(loaded, dict):
                    meta = loaded
            except yaml.YAMLError as exc:  # tolerate malformed frontmatter
                logger.warning("skill_frontmatter_parse_failed", path=path, error=str(exc))

        fallback_name = "unnamed"
        if path:
            fallback_name = Path(path).name.removesuffix(".skill.md").removesuffix(".md")

        return Skill(
            name=str(meta.get("name") or fallback_name),
            version=str(meta.get("version") or "0.0.0"),
            domain=str(meta.get("domain") or ""),
            description=str(meta.get("description") or ""),
            triggers=_as_str_list(meta.get("triggers")),
            tools=_as_str_list(meta.get("tools")),
            body=body.strip(),
            path=str(path) if path else None,
        )

    def render(self) -> str:
        """Render this skill as a prompt-injectable block."""
        header = f"### Skill: {self.name} (v{self.version})"
        if self.domain:
            header += f" — domain: {self.domain}"
        parts = [header]
        if self.description:
            parts.append(f"_{self.description}_")
        if self.tools:
            parts.append(f"Tools: {', '.join(self.tools)}")
        parts.append(self.body)
        return "\n\n".join(parts)


class SkillRegistry:
    """
    In-memory registry of skill packs.

    I/O happens only in :meth:`load_dir` / :meth:`add`; :meth:`match` and
    :meth:`render` are pure so they stay unit-test friendly.
    """

    def __init__(self) -> None:
        self._skills: Dict[str, Skill] = {}

    # -- loading ------------------------------------------------------------

    def add(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def load_dir(self, path: str | Path) -> int:
        """
        Recursively load all ``*.skill.md`` files under ``path``.

        Returns the number of skills loaded. Unreadable files are skipped
        with a warning rather than raising.
        """
        root = Path(path)
        loaded = 0
        for file in sorted(root.rglob(SKILL_FILE_GLOB)):
            try:
                skill = Skill.from_markdown(file.read_text(encoding="utf-8"), path=str(file))
            except OSError as exc:
                logger.warning("skill_load_failed", path=str(file), error=str(exc))
                continue
            self.add(skill)
            loaded += 1
        logger.info("skills_loaded", path=str(root), count=loaded)
        return loaded

    # -- lookup -------------------------------------------------------------

    def get(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def list(self) -> List[Skill]:
        """All registered skills, sorted by name (deterministic)."""
        return [self._skills[k] for k in sorted(self._skills)]

    # -- matching (pure) ----------------------------------------------------

    def match(self, text: str, limit: int = 3) -> List[Skill]:
        """
        Score skills against ``text`` and return the top ``limit`` matches.

        Score = (2 x trigger hits: trigger phrase appears as substring, or all
        of its tokens appear in the text) + (1 x each domain/name token that
        overlaps the text tokens). Skills with score 0 are excluded. Ties are
        broken by name, so ordering is fully deterministic.
        """
        lowered = text.lower()
        tokens = set(_tokenize(text))
        scored: List[tuple[int, str, Skill]] = []

        for skill in self.list():
            score = 0
            for trigger in skill.triggers:
                trig = trigger.lower().strip()
                if not trig:
                    continue
                trig_tokens = set(_tokenize(trig))
                if trig in lowered or (trig_tokens and trig_tokens <= tokens):
                    score += 2
            for token in set(_tokenize(skill.name)) | set(_tokenize(skill.domain)):
                if token in tokens:
                    score += 1
            if score > 0:
                scored.append((score, skill.name, skill))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [skill for _, _, skill in scored[: max(limit, 0)]]

    # -- rendering (pure) ---------------------------------------------------

    @staticmethod
    def render(skills: Iterable[Skill]) -> str:
        """Concatenate skill blocks into one prompt section."""
        blocks = [s.render() for s in skills]
        if not blocks:
            return ""
        return "## Relevant Skills\n\n" + "\n\n---\n\n".join(blocks)
